from typing import Dict, Optional, List, Tuple
from db import execute_query
from .utils import generate_error_response
import pandas as pd
import numpy as np
import re
from collections import Counter, defaultdict
import os
import json
import unicodedata

CACHE_ROOT = os.path.join(os.path.dirname(__file__), "precompute", "cache", "wordcloud")


def _parse_prefs(preferences: Dict) -> Dict:
    level = preferences.get("level") or "neighbourhood_group"
    name = preferences.get("name")
    top_n = int(preferences.get("top_n", 50))
    measure = (preferences.get("measure") or "freq").lower()
    ngram_raw = preferences.get("ngram", "mixed")  # default mixed
    if isinstance(ngram_raw, str) and ngram_raw.lower() in ("mix", "mixed", "all"):
        ngram = "mixed"
    else:
        try:
            ngram = int(ngram_raw)
            ngram = max(1, min(3, ngram))
        except Exception:
            ngram = "mixed"
    # optional group to enable direct nested lookup for neighbourhood
    group = preferences.get("group") or preferences.get("neighbourhood_group")
    # server-side fixed; do not depend on filters to select cache
    return {
        "level": level,
        "name": name,
        "top_n": top_n,
        "measure": measure,
        "ngram": ngram,
        "group": group,
    }


def _build_listing_filters(p: Dict) -> List[str]:
    where = ["r.comments IS NOT NULL", "LENGTH(r.comments) > 0"]
    if p.get("name"):
        safe = str(p["name"]).replace("'", "''")
        if p.get("level") == "neighbourhood":
            where.append(f"l.neighbourhood_cleansed = '{safe}'")
        else:
            where.append(f"l.neighbourhood_group_cleansed = '{safe}'")
    if p.get("price_min") is not None:
        where.append(f"l.price >= {float(p['price_min'])}")
    if p.get("price_max") is not None:
        where.append(f"l.price <= {float(p['price_max'])}")
    if p.get("room_type"):
        safe_rt = str(p['room_type']).replace("'", "''")
        where.append(f"l.room_type = '{safe_rt}'")
    if p.get("min_reviews") is not None:
        where.append(f"l.number_of_reviews >= {int(p['min_reviews'])}")
    return where


def _fetch_area_reviews(p: Dict) -> pd.DataFrame:
    where_area = _build_listing_filters(p)
    where_area_sql = " AND ".join(where_area) if where_area else "TRUE"
    sql = f"""
    SELECT 
      r.id AS review_id,
      r.listing_id,
      r.date,
      l.review_scores_rating AS rating,
      r.comments
    FROM reviews r
    JOIN listings l ON l.id = r.listing_id
    WHERE {where_area_sql}
    """
    return execute_query(sql)


def _clean_text_to_tokens(text: str) -> List[str]:
    if not isinstance(text, str):
        return []
    s = text.lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s.split(" ") if s else []


def _make_ngrams(tokens: List[str], n: int) -> List[str]:
    if n <= 1:
        return [t for t in tokens if len(t) > 2]
    grams: List[str] = []
    for i in range(len(tokens) - n + 1):
        gram = " ".join(tokens[i:i+n])
        if len(gram.replace(" ", "")) > 2:
            grams.append(gram)
    return grams


def _german_transliterate(s: str) -> str:
    if not isinstance(s, str):
        return ""
    mapping = {
        "ä": "ae", "Ä": "Ae",
        "ö": "oe", "Ö": "Oe",
        "ü": "ue", "Ü": "Ue",
        "ß": "ss",
    }
    out = []
    for ch in s:
        out.append(mapping.get(ch, ch))
    return "".join(out)


def _ascii_fold(s: str) -> str:
    if not isinstance(s, str):
        return ""
    nfkd = unicodedata.normalize("NFKD", s)
    return nfkd.encode("ascii", "ignore").decode("ascii")


def _slug_basic(s: str) -> str:
    # keep a-zA-Z0-9_- and replace others with underscore, trim repeated underscores
    tmp = re.sub(r"[^a-zA-Z0-9_-]+", "_", s.strip())
    tmp = re.sub(r"_+", "_", tmp)
    return tmp.strip("_")


def _slug_variants(s: str) -> List[str]:
    # Generate multiple possible filesystem-safe variants to maximize hit chances
    variants: List[str] = []
    candidates = [s]
    candidates.append(_german_transliterate(s))
    candidates.append(_ascii_fold(s))
    for cand in candidates:
        if not cand:
            continue
        slug = _slug_basic(cand)
        if slug and slug not in variants:
            variants.append(slug)
    # Also try lowercase versions to be safe on case-sensitive fs (even though Windows is not)
    lower_variants = [v.lower() for v in variants]
    for v in lower_variants:
        if v and v not in variants:
            variants.append(v)
    return variants


def _cache_paths_order(level: str, name: Optional[str], ngram, group: Optional[str] = None) -> List[str]:
    if not name:
        return []
    name_variants = _slug_variants(name)
    # Only support final cache locations per new layout
    if level == "neighbourhood_group":
        paths: List[str] = []
        base_dir = os.path.join(CACHE_ROOT, "neighbourhood_group")
        for nv in name_variants:
            paths.append(os.path.join(base_dir, f"{nv}.json"))
        return paths
    # neighbourhood: nested under group folder
    paths: List[str] = []
    neigh_root = os.path.join(CACHE_ROOT, "neighbourhood")
    if group:
        for gv in _slug_variants(group):
            for nv in name_variants:
                paths.append(os.path.join(neigh_root, gv, f"{nv}.json"))
        return paths
    try:
        for group_dir in os.listdir(neigh_root):
            full_dir = os.path.join(neigh_root, group_dir)
            if not os.path.isdir(full_dir):
                continue
            for nv in name_variants:
                paths.append(os.path.join(full_dir, f"{nv}.json"))
    except Exception:
        pass
    return paths


def _try_read_cache(p: Dict) -> Optional[Dict]:
    level = p.get("level")
    name = p.get("name")
    ngram = p.get("ngram", "mixed")
    group = p.get("group")
    for pth in _cache_paths_order(level, name, ngram, group):
        if pth and os.path.exists(pth):
            try:
                with open(pth, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return data
            except Exception:
                continue
    return None


def generate(preferences: Dict, context: Optional[Dict] = None) -> Dict:
    try:
        p = _parse_prefs(preferences or {})

        # Require level and name for cache lookup
        if not p.get("name"):
            return generate_error_response("Missing 'name' for wordcloud cache lookup (district or neighbourhood name)")

        cache = _try_read_cache(p)
        if not cache:
            return {
                "success": False,
                "error": "wordcloud cache not found",
                "data": None,
                "metadata": {
                    "meta": {
                        "level": p["level"],
                        "name": p["name"],
                        "ngram": "mixed",
                        "top_n": int(p["top_n"]),
                        "source": "cache-miss"
                    }
                }
            }

        if not cache.get("success", True):
            return generate_error_response("Invalid cache content")

        measure = p["measure"]
        top_n = max(1, int(p["top_n"]))

        entries_mixed = cache.get("entries_mixed")
        if entries_mixed:
            def _score(e):
                if measure == "tfidf":
                    return (float(e.get("tfidf") or 0.0), float(e.get("freq") or 0))
                if measure == "pmi":
                    return (float(e.get("pmi") or 0.0), float(e.get("freq") or 0))
                return (float(e.get("fpmw") or 0.0), float(e.get("freq") or 0))
            sorted_entries = sorted(entries_mixed, key=_score, reverse=True)[:top_n]
            words = [e.get("canonical", "") for e in sorted_entries]
            counts = [int(e.get("freq", 0)) for e in sorted_entries]
            meta = cache.get("meta", {})
            meta.update({"measure": measure, "top_n": top_n, "source": "cache"})
            return {
                "success": True,
                "chart_config": {"type": "wordcloud", "title": "Review Keywords Wordcloud"},
                "data": {"words": words, "counts": counts, "entries_mixed": sorted_entries},
                "metadata": {"distinct_words": len(sorted_entries), "meta": meta}
            }

        entries = cache.get("entries", [])
        if entries:
            if measure == "tfidf":
                entries_sorted = sorted(entries, key=lambda x: ((x.get("tfidf") or 0.0), x.get("freq", 0)), reverse=True)
            elif measure == "pmi":
                entries_sorted = sorted(entries, key=lambda x: ((x.get("pmi") or 0.0), x.get("freq", 0)), reverse=True)
            else:
                entries_sorted = sorted(entries, key=lambda x: ((x.get("fpmw") or 0.0), x.get("freq", 0)), reverse=True)
            entries_out = entries_sorted[:top_n]
            words = [e.get("keyword", "") for e in entries_out]
            counts = [int(e.get("freq", 0)) for e in entries_out]
            meta = cache.get("meta", {})
            meta.update({"measure": measure, "top_n": top_n, "source": "cache"})
            return {
                "success": True,
                "chart_config": {"type": "wordcloud", "title": "Review Keywords Wordcloud"},
                "data": {"words": words, "counts": counts, "entries": entries_out},
                "metadata": {"distinct_words": len(entries_out), "meta": meta}
            }

        return generate_error_response("Cache file has no entries")

    except Exception as e:
        return generate_error_response(f"Wordcloud generation failed: {str(e)}") 