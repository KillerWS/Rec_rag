"""
Wordcloud precompute module.
Exports callable helpers:
- list_areas(level)
- list_groups()
- list_neighbourhoods_in_group(group_name)
- precompute_for_area(level, name, ngram=1, top_k_store=300)
- precompute_mixed_for_area(level, name, top_k_store=300, parent_group=None)

Cache path: chart_generators/precompute/cache/wordcloud/{level}/{AreaName}_ng{n}.json
Mixed cache: chart_generators/precompute/cache/wordcloud/{level}/{AreaName}_ngmix.json
Final cache (recommended):
- level=neighbourhood_group: chart_generators/precompute/cache/wordcloud/neighbourhood_group/{Group}.json
- level=neighbourhood:       chart_generators/precompute/cache/wordcloud/neighbourhood/{Group}/{Neighbourhood}.json
This module is intended to be invoked by the API endpoint, not as a script.
"""
import os
import re
import json
from typing import List, Dict, Tuple, Optional
import pandas as pd
from collections import Counter, defaultdict
from db import execute_query
import math
import unicodedata
import time

CACHE_ROOT = os.path.join(os.path.dirname(__file__), "cache", "wordcloud")

# ---------------------- Stopwords & Canonicalization ----------------------
# Minimal multilingual stopwords (can be expanded). Domain stopwords help reduce noise.
STOPWORDS_EN = {
    "the","a","an","and","or","but","with","without","to","from","in","on","at","for","of",
    "this","that","these","those","it","its","is","are","was","were","be","been","being",
    "very","really","just","like","can","could","should","would","will","im","we","they","you",
    "my","our","their","your","as","than","so","if","because","also","too","not","no","yes"
}
STOPWORDS_DE = {
    "der","die","das","ein","eine","und","oder","aber","mit","ohne","zu","von","im","in","auf","am","für","aus",
    "dies","diese","dieser","ist","sind","war","waren","sein","schon","sehr","wirklich","nur","wie",
    "kann","könnte","sollte","würde","wird","ich","wir","sie","du","mein","unser","ihr","dein","als","wenn","weil","auch","nicht","kein","ja"
}
STOPWORDS_ES = {
    "el","la","los","las","un","una","y","o","pero","con","sin","a","de","en","por","para","este","esta","estos","esas",
    "es","son","fue","eran","ser","muy","realmente","solo","como","puede","podría","debería","sería","será",
    "yo","nosotros","ellos","tú","mi","nuestro","su","tu","si","porque","también","no","ninguno","sí"
}
DOMAIN_STOPWORDS = {
    # domain-generic terms that add little signal
    "apartment","room","host","check","checkin","check-in","airbnb","berlin","berliner","house","flat","place","stay",
    "location","area","city","center","centre","downtown","neighborhood","neighbourhood","neighbourhoods","u","s"
}

CANONICAL_MAP: Dict[str, str] = {
    # cleanliness
    "sauber": "clean",
    "limpio": "clean",
    "sehr sauber": "clean",
    # transport
    "u bahn": "public transport",
    "ubahn": "public transport",
    "s bahn": "public transport",
    "sbahn": "public transport",
    "metro": "public transport",
    "bahn": "public transport",
    "öffentlicher verkehr": "public transport",
    "transporte publico": "public transport",
    "transporte público": "public transport",
    # quiet/noise
    "ruhig": "quiet",
    "silencioso": "quiet",
    "lärm": "noise",
    "ruidoso": "noisy",
    # bathroom/ kitchen basics
    "bad": "bathroom",
    "küche": "kitchen",
    "cocina": "kitchen",
}

# ---------------------- Utilities ----------------------

def _remove_diacritics(s: str) -> str:
    try:
        return unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode('ascii')
    except Exception:
        return s


def _detect_lang_heuristic(text: str) -> str:
    t = text or ""
    # quick heuristic by character set
    if re.search(r"[äöüß]", t.lower()):
        return "de"
    if re.search(r"[áéíóúñ]", t.lower()):
        return "es"
    return "en"


def _normalize_text(text: str) -> str:
    if not isinstance(text, str):
        return ""
    s = text.lower()
    s = s.replace("-", " ").replace("_", " ")
    s = _remove_diacritics(s)
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _tokenize_and_filter(text: str, lang: str) -> List[str]:
    s = _normalize_text(text)
    tokens = s.split(" ") if s else []
    if lang == "de":
        stop = STOPWORDS_DE
    elif lang == "es":
        stop = STOPWORDS_ES
    else:
        stop = STOPWORDS_EN
    out: List[str] = []
    for t in tokens:
        if not t or len(t) <= 2:
            continue
        if t in stop or t in DOMAIN_STOPWORDS:
            continue
        if t.isdigit():
            continue
        out.append(t)
    return out


def _clean_text_to_tokens(text: str) -> List[str]:
    # kept for backward compatibility (english-only basic cleaning)
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


def _fetch_reviews_for_area(level: str, name: str) -> pd.DataFrame:
    safe = name.replace("'", "''")
    if level == "neighbourhood":
        area_cond = f"l.neighbourhood_cleansed = '{safe}'"
    else:
        area_cond = f"l.neighbourhood_group_cleansed = '{safe}'"
    sql = f"""
    SELECT r.id AS review_id,
           r.listing_id,
           r.date,
           l.review_scores_rating AS rating,
           r.comments
    FROM reviews r
    JOIN listings l ON l.id = r.listing_id
    WHERE r.comments IS NOT NULL AND LENGTH(r.comments) > 0 AND {area_cond}
    """
    return execute_query(sql)


# ---------------------- Per-ngram compute (existing) ----------------------

def _compute_entries(df_reviews: pd.DataFrame, ngram: int, top_k_store: int) -> Dict:
    term_counter: Counter = Counter()
    term_docset: Dict[str, set] = defaultdict(set)
    pos_counter: Counter = Counter()
    neu_counter: Counter = Counter()
    neg_counter: Counter = Counter()
    total_ngrams = 0

    for _, row in df_reviews.iterrows():
        rid = row.get("review_id")
        rating_raw = row.get("rating")
        try:
            rating = float(rating_raw) if rating_raw not in (None, '') else None
        except Exception:
            rating = None
        # basic english-only cleaning (legacy)
        tokens = _clean_text_to_tokens(row.get("comments"))
        grams = _make_ngrams(tokens, ngram)
        total_ngrams += len(grams)
        seen: set = set()
        for g in grams:
            term_counter[g] += 1
            if g not in seen:
                term_docset[g].add(rid)
                seen.add(g)
        if rating is not None:
            if rating >= 4.5:
                for g in seen:
                    pos_counter[g] += 1
            elif rating <= 3.0:
                for g in seen:
                    neg_counter[g] += 1
            else:
                for g in seen:
                    neu_counter[g] += 1

    total_ngrams = float(total_ngrams)
    rows: List[Dict] = []
    for kw, freq in term_counter.items():
        pos = pos_counter.get(kw, 0)
        neu = neu_counter.get(kw, 0)
        neg = neg_counter.get(kw, 0)
        fpmw = 0.0 if total_ngrams == 0 else (freq / total_ngrams) * 1_000_000.0
        conf = float(freq) / (float(freq) + 5.0)
        rows.append({
            "keyword": kw,
            "freq": int(freq),
            "fpmw": round(float(fpmw), 2),
            "tfidf": None,
            "pmi": None,
            "sentiment": {
                "pos": round(float(pos) / max(1.0, pos + neu + neg), 3) if (pos + neu + neg) > 0 else 0.0,
                "neu": round(float(neu) / max(1.0, pos + neu + neg), 3) if (pos + neu + neg) > 0 else 0.0,
                "neg": round(float(neg) / max(1.0, pos + neu + neg), 3) if (pos + neu + neg) > 0 else 0.0,
                "conf": round(float(conf), 3),
            },
            "examples": []
        })

    rows.sort(key=lambda r: (r["fpmw"], r["freq"]), reverse=True)
    if top_k_store is not None and top_k_store > 0:
        rows = rows[:top_k_store]
    return {
        "entries": rows,
        "sample_tokens": int(total_ngrams),
        "sample_reviews": int(df_reviews.shape[0])
    }


def _cache_path(level: str, name: str, ngram: int) -> str:
    safe_level = "neighbourhood" if level == "neighbourhood" else "neighbourhood_group"
    safe_name = re.sub(r"[^a-zA-Z0-9_-]+", "_", name.strip()) if name else "UNKNOWN"
    dir_path = os.path.join(CACHE_ROOT, safe_level)
    os.makedirs(dir_path, exist_ok=True)
    return os.path.join(dir_path, f"{safe_name}_ng{ngram}.json")


def _cache_path_mixed(level: str, name: str) -> str:
    safe_level = "neighbourhood" if level == "neighbourhood" else "neighbourhood_group"
    safe_name = re.sub(r"[^a-zA-Z0-9_-]+", "_", name.strip()) if name else "UNKNOWN"
    dir_path = os.path.join(CACHE_ROOT, safe_level)
    os.makedirs(dir_path, exist_ok=True)
    return os.path.join(dir_path, f"{safe_name}_ngmix.json")


def _cache_path_final(level: str, name: str, parent_group: Optional[str] = None) -> str:
    if level == "neighbourhood" and parent_group:
        safe_group = re.sub(r"[^a-zA-Z0-9_-]+", "_", parent_group.strip())
        dir_path = os.path.join(CACHE_ROOT, "neighbourhood", safe_group)
        os.makedirs(dir_path, exist_ok=True)
        safe_name = re.sub(r"[^a-zA-Z0-9_-]+", "_", name.strip()) if name else "UNKNOWN"
        return os.path.join(dir_path, f"{safe_name}.json")
    safe_level = "neighbourhood" if level == "neighbourhood" else "neighbourhood_group"
    safe_name = re.sub(r"[^a-zA-Z0-9_-]+", "_", name.strip()) if name else "UNKNOWN"
    dir_path = os.path.join(CACHE_ROOT, safe_level)
    os.makedirs(dir_path, exist_ok=True)
    return os.path.join(dir_path, f"{safe_name}.json")


# ---------------------- Mixed compute (new) ----------------------

def _compute_all_ngrams_clean(df_reviews: pd.DataFrame) -> Tuple[Dict[int, Counter], Dict[int, Dict[str,set]], Dict[int,int], Dict[str, Counter]]:
    """Return per-ngram counters/docsets/totals and sentiment doc counters by term.
    sentiment term counters stored in a dict label->Counter (pos/neu/neg).
    """
    term_counter_by_n: Dict[int, Counter] = {1: Counter(), 2: Counter(), 3: Counter()}
    term_docset_by_n: Dict[int, Dict[str, set]] = {1: defaultdict(set), 2: defaultdict(set), 3: defaultdict(set)}
    total_by_n: Dict[int, int] = {1: 0, 2: 0, 3: 0}
    sent_pos_by_n: Dict[int, Counter] = {1: Counter(), 2: Counter(), 3: Counter()}
    sent_neu_by_n: Dict[int, Counter] = {1: Counter(), 2: Counter(), 3: Counter()}
    sent_neg_by_n: Dict[int, Counter] = {1: Counter(), 2: Counter(), 3: Counter()}

    for _, row in df_reviews.iterrows():
        rid = row.get("review_id")
        rating_raw = row.get("rating")
        try:
            rating = float(rating_raw) if rating_raw not in (None, '') else None
        except Exception:
            rating = None
        original_text = row.get("comments") or ""
        lang = _detect_lang_heuristic(original_text)
        tokens = _tokenize_and_filter(original_text, lang)
        grams1 = _make_ngrams(tokens, 1)
        grams2 = _make_ngrams(tokens, 2)
        grams3 = _make_ngrams(tokens, 3)
        for n, grams in ((1, grams1), (2, grams2), (3, grams3)):
            total_by_n[n] += len(grams)
            seen: set = set()
            for g in grams:
                term_counter_by_n[n][g] += 1
                if g not in seen:
                    term_docset_by_n[n][g].add(rid)
                    seen.add(g)
            if rating is not None:
                if rating >= 4.5:
                    for g in seen:
                        sent_pos_by_n[n][g] += 1
                elif rating <= 3.0:
                    for g in seen:
                        sent_neg_by_n[n][g] += 1
                else:
                    for g in seen:
                        sent_neu_by_n[n][g] += 1
    sentiment_by_n = {
        "pos": sent_pos_by_n,
        "neu": sent_neu_by_n,
        "neg": sent_neg_by_n,
    }
    return term_counter_by_n, term_docset_by_n, total_by_n, sentiment_by_n


def _compute_measures_for_n(n: int, term_counter: Counter, term_docset: Dict[str,set], total_tokens: int, num_docs: int,
                             unigram_counter: Counter) -> Dict[str, Dict[str, float]]:
    """Compute fpmw, tfidf, pmi for each term in this n-gram space.
    For PMI on bigram/trigram we approximate with product of unigrams.
    Returns a dict: term -> measure dict.
    """
    measures: Dict[str, Dict[str, float]] = {}
    N = max(1, num_docs)
    total = float(max(1, total_tokens))
    # prepare unigram probabilities
    total_uni = float(max(1, sum(unigram_counter.values())))
    p_uni: Dict[str, float] = {}
    if total_uni > 0:
        for t, c in unigram_counter.items():
            p_uni[t] = float(c) / total_uni
    for term, tf in term_counter.items():
        df = len(term_docset.get(term, set()))
        fpmw = (float(tf) / total) * 1_000_000.0
        idf = math.log((N) / (1.0 + float(df))) if df > 0 else 0.0
        tfidf = float(tf) * idf
        pmi = None
        if n >= 2:
            parts = term.split(" ")
            denom = 1.0
            for p in parts:
                denom *= max(1e-12, p_uni.get(p, 1e-12))
            p_term = float(tf) / float(sum(term_counter.values()) or 1)
            if p_term > 0 and denom > 0:
                pmi = math.log(p_term / denom)
        measures[term] = {"fpmw": round(fpmw, 2), "tfidf": round(tfidf, 3), "pmi": (round(pmi, 3) if pmi is not None else None), "df": float(df)}
    return measures


def _canonical_of(term: str) -> str:
    t = term.strip().lower()
    if t in CANONICAL_MAP:
        return CANONICAL_MAP[t]
    return t


def _guess_lang_from_term(term: str) -> str:
    return _detect_lang_heuristic(term)


def _build_mixed_entries(level: str, name: str, df_reviews: pd.DataFrame, top_k_store: int) -> Dict:
    t0 = time.time()
    print(f"   · building entries (clean+ngrams+measures) ...", flush=True)
    term_counter_by_n, term_docset_by_n, total_by_n, sentiment_by_n = _compute_all_ngrams_clean(df_reviews)
    num_docs = int(df_reviews.shape[0])
    print(f"     docs={num_docs}, tokens(n1/n2/n3)={[total_by_n[1], total_by_n[2], total_by_n[3]]}", flush=True)
    # measures per n
    measures_by_n: Dict[int, Dict[str, Dict[str, float]]] = {}
    for n in (1, 2, 3):
        measures_by_n[n] = _compute_measures_for_n(
            n,
            term_counter_by_n[n],
            term_docset_by_n[n],
            total_by_n[n],
            num_docs,
            unigram_counter=term_counter_by_n[1]
        )

    # assemble candidates with features
    candidates: List[Dict] = []
    for n in (1, 2, 3):
        term_counter = term_counter_by_n[n]
        pos_c = sentiment_by_n["pos"][n]
        neu_c = sentiment_by_n["neu"][n]
        neg_c = sentiment_by_n["neg"][n]
        for term, freq in term_counter.items():
            m = measures_by_n[n].get(term, {})
            pos = pos_c.get(term, 0)
            neu = neu_c.get(term, 0)
            neg = neg_c.get(term, 0)
            total_sent = float(max(1, pos + neu + neg))
            cand = {
                "term": term,
                "ngram": n,
                "freq": int(freq),
                "fpmw": float(m.get("fpmw", 0.0)),
                "tfidf": float(m.get("tfidf", 0.0)),
                "pmi": (float(m["pmi"]) if m.get("pmi") is not None else None),
                "df": int(m.get("df", 0.0)),
                "sentiment": {
                    "pos": round(float(pos) / total_sent, 3),
                    "neu": round(float(neu) / total_sent, 3),
                    "neg": round(float(neg) / total_sent, 3),
                    "conf": round(float(freq) / (float(freq) + 5.0), 3)
                }
            }
            # apply simple PMI filter for n>=2 to keep collocations
            if n >= 2 and (cand["pmi"] is None or cand["pmi"] < 1.5 or freq < (8 if n == 2 else 5)):
                continue
            candidates.append(cand)
    print(f"     candidates={len(candidates)}", flush=True)

    # group by canonical english
    concepts: Dict[str, Dict] = {}
    for c in candidates:
        can = _canonical_of(c["term"])
        lang = _guess_lang_from_term(c["term"]) if can != c["term"] else "en"
        entry = concepts.get(can)
        if entry is None:
            entry = {
                "canonical": can,
                "ngram": c["ngram"],  # prefer first n; may be updated to the max n with highest score later
                "variants": [],
                "freq": 0,
                "fpmw": 0.0,
                "tfidf": 0.0,
                "pmi": None,
                "sent_pos": 0.0,
                "sent_neu": 0.0,
                "sent_neg": 0.0,
                "sent_conf": 0.0,
                "df": 0,
                "rf": 0,
                "lang_coverage": defaultdict(int),
            }
            concepts[can] = entry
        entry["variants"].append({"text": c["term"], "lang": lang, "score": c.get("pmi") or c.get("tfidf") or c.get("fpmw")})
        entry["freq"] += c["freq"]
        entry["rf"] += c["freq"]
        entry["df"] += int(c.get("df", 0))
        entry["fpmw"] += c.get("fpmw", 0.0)
        entry["tfidf"] += c.get("tfidf", 0.0)
        if c.get("pmi") is not None:
            entry["pmi"] = max(entry["pmi"] or c["pmi"], c["pmi"]) if entry["pmi"] is not None else c["pmi"]
        entry["sent_pos"] += c["sentiment"]["pos"] * c["freq"]
        entry["sent_neu"] += c["sentiment"]["neu"] * c["freq"]
        entry["sent_neg"] += c["sentiment"]["neg"] * c["freq"]
        entry["sent_conf"] += c["sentiment"]["conf"] * c["freq"]
        entry["lang_coverage"][lang] += c["freq"]
        # prefer larger n when similar terms exist with higher PMI
        if c["ngram"] > entry["ngram"] and (c.get("pmi") or 0) >= (entry.get("pmi") or 0):
            entry["ngram"] = c["ngram"]

    # finalize aggregates and compute salience score
    finalized: List[Dict] = []
    total_freq = float(max(1, sum(e["freq"] for e in concepts.values())))
    for can, e in concepts.items():
        freq = e["freq"]
        # normalize averages
        k = max(1, len(e["variants"]))
        fpmw = e["fpmw"] / k
        tfidf = e["tfidf"] / k
        pmi = e["pmi"]
        sent_total_w = float(max(1, e["rf"]))
        sent = {
            "pos": round(e["sent_pos"] / sent_total_w, 3),
            "neu": round(e["sent_neu"] / sent_total_w, 3),
            "neg": round(e["sent_neg"] / sent_total_w, 3),
            "conf": round(e["sent_conf"] / sent_total_w, 3)
        }
        lang_cov_raw = dict(e["lang_coverage"])
        total_lang = float(max(1, sum(lang_cov_raw.values())))
        lang_coverage = {k2: round(v2 / total_lang, 3) for k2, v2 in lang_cov_raw.items()}
        # salience: weighted mix; bounded
        salience = 0.5 * (freq / total_freq) + 0.3 * (tfidf / (tfidf + 5.0)) + 0.2 * (max(pmi or 0.0, 0.0) / 5.0)
        finalized.append({
            "canonical": can,
            "ngram": int(e["ngram"]),
            "variants": e["variants"],
            "freq": int(freq),
            "fpmw": round(fpmw, 2),
            "tfidf": round(tfidf, 3),
            "pmi": (round(pmi, 3) if pmi is not None else None),
            "sentiment": sent,
            "lang_coverage": lang_coverage,
            "examples": [],
            "scores": {
                "salience": round(float(salience), 4),
                "representativeness": round(float(freq / total_freq), 4),
                "confidence": round(float(min(1.0, freq / (freq + 5.0))), 3)
            },
            "meta": {"df": int(e["df"]), "rf": int(e["rf"]), "source": "cache"}
        })

    # simple quota by n-gram to keep diversity
    quota_uni = int(top_k_store * 0.5)
    quota_bi = int(top_k_store * 0.35)
    quota_tri = top_k_store - quota_uni - quota_bi

    # rank per n by salience
    uni = [x for x in finalized if x["ngram"] == 1]
    bi = [x for x in finalized if x["ngram"] == 2]
    tri = [x for x in finalized if x["ngram"] == 3]
    uni.sort(key=lambda x: (x["scores"]["salience"], x["freq"]), reverse=True)
    bi.sort(key=lambda x: (x["scores"]["salience"], x["freq"]), reverse=True)
    tri.sort(key=lambda x: (x["scores"]["salience"], x["freq"]), reverse=True)

    mixed = uni[:quota_uni] + bi[:quota_bi] + tri[:quota_tri]
    # if not enough, fill from remaining
    rest = uni[quota_uni:] + bi[quota_bi:] + tri[quota_tri:]
    rest.sort(key=lambda x: (x["scores"]["salience"], x["freq"]), reverse=True)
    if len(mixed) < top_k_store:
        mixed.extend(rest[: (top_k_store - len(mixed))])

    print(f"     finalized={len(finalized)}, mixed_top={len(mixed)}, took={time.time()-t0:.2f}s", flush=True)
    # build output
    out = {
        "success": True,
        "meta": {
            "level": level,
            "name": name,
            "ngram": "mixed",
            "top_k_stored": int(top_k_store),
            "sample_tokens": int(sum(total_by_n.values())),
            "sample_reviews": int(df_reviews.shape[0]),
            "generated_at": pd.Timestamp.now().isoformat()
        },
        "entries_mixed": mixed
    }
    return out


def precompute_for_area(level: str, name: str, ngram: int = 1, top_k_store: int = 300) -> str:
    df_reviews = _fetch_reviews_for_area(level, name)
    result = _compute_entries(df_reviews, ngram, top_k_store)
    out = {
        "success": True,
        "meta": {
            "level": level,
            "name": name,
            "ngram": int(ngram),
            "top_k_stored": int(top_k_store),
            "sample_tokens": result["sample_tokens"],
            "sample_reviews": result["sample_reviews"],
            "generated_at": pd.Timestamp.now().isoformat()
        },
        "entries": result["entries"]
    }
    path = _cache_path(level, name, ngram)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)
    return path


def precompute_mixed_for_area(level: str, name: str, top_k_store: int = 300, parent_group: Optional[str] = None) -> str:
    print(f"   → fetching reviews for [{level}] {name} ...", flush=True)
    t_sql = time.time()
    df_reviews = _fetch_reviews_for_area(level, name)
    print(f"     fetched rows={df_reviews.shape[0] if df_reviews is not None else 0} in {time.time()-t_sql:.2f}s", flush=True)
    out = _build_mixed_entries(level, name, df_reviews, top_k_store)
    # write final (recommended)
    path_final = _cache_path_final(level, name, parent_group=parent_group)
    dir_path = os.path.dirname(path_final)
    os.makedirs(dir_path, exist_ok=True)
    with open(path_final, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)
    print(f"     wrote final cache: {path_final}", flush=True)
    return path_final


def list_areas(level: str) -> List[str]:
    col = "neighbourhood_cleansed" if level == "neighbourhood" else "neighbourhood_group_cleansed"
    sql = f"""
    SELECT DISTINCT {col} AS name
    FROM listings
    WHERE {col} IS NOT NULL AND {col} <> ''
    ORDER BY name
    """
    df = execute_query(sql)
    return [str(x) for x in df["name"].dropna().tolist()]


def list_groups() -> List[str]:
    sql = """
    SELECT DISTINCT neighbourhood_group_cleansed AS name
    FROM listings
    WHERE neighbourhood_group_cleansed IS NOT NULL AND neighbourhood_group_cleansed <> ''
    ORDER BY name
    """
    df = execute_query(sql)
    return [str(x) for x in df["name"].dropna().tolist()]


def list_neighbourhoods_in_group(group_name: str) -> List[str]:
    safe = group_name.replace("'", "''")
    sql = f"""
    SELECT DISTINCT neighbourhood_cleansed AS name
    FROM listings
    WHERE neighbourhood_group_cleansed = '{safe}'
      AND neighbourhood_cleansed IS NOT NULL AND neighbourhood_cleansed <> ''
    ORDER BY name
    """
    df = execute_query(sql)
    return [str(x) for x in df["name"].dropna().tolist()] 