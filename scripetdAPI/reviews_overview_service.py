from typing import Dict, List, Optional, Tuple
from collections import Counter, defaultdict
import re
from datetime import datetime, timedelta
import time

from db import execute_query

try:
    from llm_pipeline.review_opinions_extractor import extract_review_opinions
    from llm_pipeline.review_opinions_extractor import ASPECT_KEYWORDS as _ASPECT_KEYS  # type: ignore
except Exception:
    extract_review_opinions = None  # type: ignore
    _ASPECT_KEYS = {
        "wifi","internet","clean","cleanliness","noise","quiet","location","transport","metro","ubahn","s-bahn","subway","host","responsive","check-in","checkin","price","value","bed","bathroom","kitchen","heating","ac","aircon","view","safety","neighborhood","neighbourhood","space","spacious","comfortable","soundproof","tram","bus"
    }


WORD_RE = re.compile(r"[a-z]+")
_URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
_WS_RE = re.compile(r"\s+")
_SENT_SPLIT_RE = re.compile(r"(?<=[\.!?])\s+")

# Minimal English stopword list (kept local to avoid external deps)
STOPWORDS = {
    "a","an","and","the","is","are","was","were","be","been","being","am",
    "in","on","at","to","for","from","of","by","with","as","that","this","these","those",
    "it","its","it's","they","them","their","there","here","or","if","but","so","than","then",
    "very","really","just","quite","too","also","not","no","yes","you","your","we","our",
    "i","he","she","his","her","my","me","us","do","did","does","done","have","has","had",
}

# Lightweight lexicon for rule-based sentiment
POSITIVE_WORDS = {
    "clean","friendly","spacious","comfortable","cozy","great","amazing","fantastic","excellent",
    "perfect","beautiful","lovely","quiet","safe","modern","helpful","responsive","nice","welcoming",
    "convenient","close","central","affordable","value","fast","good","recommend","recommendation",
}
NEGATIVE_WORDS = {
    "dirty","noisy","loud","small","tiny","bad","terrible","awful","poor","disappointing","smell",
    "smelly","cold","hot","broken","slow","unsafe","far","distant","old","outdated","rude","problem",
    "issues","bugs","bugs","mold","mould","leak","leaking","no","not","never","wouldn't","won't",
}

# Whitelist/blacklist roots to lightly adjust phrase ranking
WHITELIST_ROOTS = {"wifi","quiet","host","clean","metro","subway","transport","location","checkin","check","check-in"}
BLACKLIST_ROOTS = {"very","really","nice","good","great"}

# In-memory cache for scoped comments
_COMMENTS_CACHE: Dict[Tuple, Dict[str, object]] = {}
_CACHE_TTL_SECONDS_DEFAULT = 120


def _tokenize(text: str) -> List[str]:
    if not text:
        return []
    text = text.lower()
    return [m.group(0) for m in WORD_RE.finditer(text)]


def _classify_sentiment(tokens: List[str]) -> int:
    """
    Return 1 for positive, -1 for negative, 0 for neutral based on simple lexicon counts.
    """
    if not tokens:
        return 0
    pos = sum(1 for t in tokens if t in POSITIVE_WORDS)
    neg = sum(1 for t in tokens if t in NEGATIVE_WORDS)
    if pos - neg >= 1 and pos > 0:
        return 1
    if neg - pos >= 1 and neg > 0:
        return -1
    return 0


def _extract_phrases(tokens: List[str]) -> List[Tuple[str, int]]:
    """
    Extract bigrams and trigrams as phrases from tokens; returns list of (phrase, 1) occurrences.
    """
    content = [t for t in tokens if t not in STOPWORDS and len(t) > 1]
    phrases: List[str] = []
    # bigrams
    for i in range(len(content) - 1):
        a, b = content[i], content[i + 1]
        if a in STOPWORDS or b in STOPWORDS:
            continue
        phrases.append(f"{a} {b}")
    # trigrams (limited)
    for i in range(len(content) - 2):
        a, b, c = content[i], content[i + 1], content[i + 2]
        if a in STOPWORDS or b in STOPWORDS or c in STOPWORDS:
            continue
        phrases.append(f"{a} {b} {c}")
    return [(p, 1) for p in phrases]


def _rank_phrases(counter: Counter, top_n: int, min_count: int) -> List[Dict[str, object]]:
    items = []
    for phrase, cnt in counter.items():
        if cnt < min_count:
            continue
        roots = set(phrase.split())
        bonus = 0
        if roots & WHITELIST_ROOTS:
            bonus += 2
        if roots & BLACKLIST_ROOTS:
            bonus -= 1
        score = cnt * (1 + 0.1 * bonus)
        items.append((phrase, cnt, score))
    items.sort(key=lambda x: (x[2], x[1]), reverse=True)
    return [{"text": p, "count": c} for p, c, _ in items[:top_n]]


def _build_listing_where(area: Optional[str], bmin: Optional[float], bmax: Optional[float]) -> str:
    # Qualify columns with listings alias 'l.' to be safe when used in JOIN queries
    conds = ["l.id IS NOT NULL"]
    if area:
        safe = area.replace("'", "''")
        # Be flexible: match either neighbourhood group or specific neighbourhood
        conds.append(f"(l.neighbourhood_group_cleansed = '{safe}' OR l.neighbourhood_cleansed = '{safe}')")
    if bmin is not None:
        conds.append(f"l.price IS NOT NULL AND l.price >= {float(bmin)}")
    if bmax is not None:
        conds.append(f"l.price IS NOT NULL AND l.price <= {float(bmax)}")
    where_clause = " AND ".join(conds)
    print(f"🧱 [reviews] WHERE: {where_clause}")
    return where_clause


def _fetch_scope_counts(where_clause: str) -> Tuple[int, int]:
    sql_listings = f"""
    SELECT COUNT(*) AS cnt FROM listings l WHERE {where_clause}
    """
    df_l = execute_query(sql_listings)
    print(f"🔎 [reviews] listings_count_sql: {sql_listings.strip()}")
    listings_cnt = int(df_l.iloc[0]["cnt"]) if df_l is not None and not df_l.empty else 0

    # Reviews count (join on scope)
    sql_reviews = f"""
    SELECT COUNT(*) AS cnt
    FROM reviews r
    JOIN listings l ON r.listing_id = l.id
    WHERE {where_clause} AND r.comments IS NOT NULL AND r.comments != ''
    """
    df_r = execute_query(sql_reviews)
    print(f"🔎 [reviews] reviews_count_sql: {sql_reviews.strip()}")
    reviews_cnt = int(df_r.iloc[0]["cnt"]) if df_r is not None and not df_r.empty else 0
    return listings_cnt, reviews_cnt


def _fetch_reviews_sample(where_clause: str, recent_months: Optional[int], sample_size: int, sample_strategy: str) -> List[str]:
    base_sql = f"""
    SELECT r.comments
    FROM reviews r
    JOIN listings l ON r.listing_id = l.id
    WHERE {where_clause} AND r.comments IS NOT NULL AND r.comments != ''
    """
    order_limit = ""
    strategy = (sample_strategy or "recent").lower()
    n = max(1, int(sample_size))
    if strategy == "random":
        # ORDER BY RAND() is OK for small n; otherwise fallback to recent
        if n <= 5000:
            order_limit = f" ORDER BY RAND() LIMIT {n}"
        else:
            order_limit = f" ORDER BY r.id DESC LIMIT {n}"
    else:
        order_limit = f" ORDER BY r.id DESC LIMIT {n}"

    # 🔧 修复：先尝试带日期过滤的查询
    sql = base_sql + order_limit
    if recent_months and recent_months > 0:
        try:
            sql_with_date = base_sql + f" AND r.date >= DATE_SUB(CURDATE(), INTERVAL {int(recent_months)} MONTH)" + order_limit
            print(f"🧪 [reviews] sample_sql_with_date: {sql_with_date.strip()}")
            df = execute_query(sql_with_date)
            if df is not None and not getattr(df, 'empty', False):
                print(f"🔍 [fetch_reviews_sample] 使用recent_months={recent_months}过滤，找到{len(df)}条评论")
                try:
                    return [str(x) for x in df["comments"].tolist()]
                except Exception:
                    pass
            else:
                print(f"⚠️ [fetch_reviews_sample] recent_months={recent_months}过滤后无评论，回退到无日期过滤")
        except Exception as e:
            print(f"⚠️ [fetch_reviews_sample] 日期过滤失败: {e}，回退到无日期过滤")
    
    # 回退：不使用日期过滤
    df = execute_query(sql)
    print(f"🧪 [reviews] sample_sql_no_date: {sql.strip()}")
    if df is None or getattr(df, 'empty', False):
        print(f"❌ [fetch_reviews_sample] 无日期过滤也无评论数据")
        return []
    try:
        comments = [str(x) for x in df["comments"].tolist()]
        print(f"✅ [fetch_reviews_sample] 回退成功，获取到{len(comments)}条评论")
        return comments
    except Exception as e:
        print(f"❌ [fetch_reviews_sample] 处理评论数据失败: {e}")
        return []


def _get_cache_key(area: Optional[str], bmin: Optional[float], bmax: Optional[float], recent_months: Optional[int], sample_size: int, sample_strategy: str) -> Tuple:
    norm_area = None if area is None else str(area).strip()
    norm_bmin = None if bmin is None else float(bmin)
    norm_bmax = None if bmax is None else float(bmax)
    norm_rm = None if recent_months is None else int(recent_months)
    norm_n = max(1, int(sample_size))
    norm_strategy = (sample_strategy or "recent").lower()
    return (norm_area, norm_bmin, norm_bmax, norm_rm, norm_n, norm_strategy)


def get_scoped_comments_cached(
    area: Optional[str],
    budget_min: Optional[float],
    budget_max: Optional[float],
    recent_months: Optional[int] = None,
    sample_size: int = 4000,
    sample_strategy: str = "recent",
    cache_ttl_seconds: int = _CACHE_TTL_SECONDS_DEFAULT,
) -> Dict[str, object]:
    """
    Return cached sampled comments and scope counts for given filters.
    { comments: List[str], listings_in_scope: int, reviews_count: int, cache: {hit: bool, age: float}}
    """
    key = _get_cache_key(area, budget_min, budget_max, recent_months, sample_size, sample_strategy)
    now = time.time()
    entry = _COMMENTS_CACHE.get(key)
    if entry and (now - float(entry.get("ts", 0))) <= max(1, cache_ttl_seconds):
        return {
            "comments": entry.get("comments", []),
            "listings_in_scope": int(entry.get("listings_in_scope", 0)),
            "reviews_count": int(entry.get("reviews_count", 0)),
            "cache": {"hit": True, "age": round(now - float(entry.get("ts", 0)), 3)}
        }

    where_clause = _build_listing_where(area, budget_min, budget_max)
    listings_in_scope, total_reviews = _fetch_scope_counts(where_clause)
    comments = _fetch_reviews_sample(where_clause, recent_months, sample_size, sample_strategy)

    # Fallbacks when no comments are found
    fallback_used = False
    fallback_stage = None
    fallback_where = None
    if not comments:
        # A1: keep area, drop budget limits
        where_a1 = _build_listing_where(area, None, None)
        li_a1, rv_a1 = _fetch_scope_counts(where_a1)
        if rv_a1 > 0 or li_a1 > 0:
            tmp = _fetch_reviews_sample(where_a1, recent_months, sample_size, sample_strategy)
            if tmp:
                comments = tmp
                listings_in_scope, total_reviews = li_a1, rv_a1
                fallback_used, fallback_stage, fallback_where = True, "area_only", where_a1
        
    if not comments:
        # A2: drop area, keep original budget
        where_a2 = _build_listing_where(None, budget_min, budget_max)
        li_a2, rv_a2 = _fetch_scope_counts(where_a2)
        if rv_a2 > 0 or li_a2 > 0:
            tmp = _fetch_reviews_sample(where_a2, recent_months, sample_size, sample_strategy)
            if tmp:
                comments = tmp
                listings_in_scope, total_reviews = li_a2, rv_a2
                fallback_used, fallback_stage, fallback_where = True, "budget_only", where_a2

    if not comments:
        # A3: drop both area and budget
        where_a3 = _build_listing_where(None, None, None)
        li_a3, rv_a3 = _fetch_scope_counts(where_a3)
        if rv_a3 > 0 or li_a3 > 0:
            tmp = _fetch_reviews_sample(where_a3, recent_months, sample_size, sample_strategy)
            if tmp:
                comments = tmp
                listings_in_scope, total_reviews = li_a3, rv_a3
                fallback_used, fallback_stage, fallback_where = True, "global", where_a3

    _COMMENTS_CACHE[key] = {
        "ts": now,
        "comments": comments,
        "listings_in_scope": listings_in_scope,
        "reviews_count": total_reviews,
    }

    return {
        "comments": comments,
        "listings_in_scope": listings_in_scope,
        "reviews_count": total_reviews,
        "cache": {"hit": False, "age": 0.0},
        "fallback": {"used": fallback_used, "stage": fallback_stage, "where": fallback_where}
    }


def compute_reviews_overview(
    area: Optional[str],
    budget_min: Optional[float],
    budget_max: Optional[float],
    top_n: int = 5,
    min_count: int = 20,
    recent_months: Optional[int] = None,
    sample_size: int = 4000,
    sample_strategy: str = "recent",
) -> Dict[str, object]:
    scoped = get_scoped_comments_cached(
        area=area,
        budget_min=budget_min,
        budget_max=budget_max,
        recent_months=recent_months,
        sample_size=sample_size,
        sample_strategy=sample_strategy,
    )

    comments = scoped.get("comments", [])
    listings_in_scope = int(scoped.get("listings_in_scope", 0))
    reviews_count = int(scoped.get("reviews_count", 0))

    # Sentiment aggregation
    pos = neu = neg = 0
    phrase_counter: Counter = Counter()
    for text in comments:
        tokens = _tokenize(text)
        s = _classify_sentiment(tokens)
        if s > 0:
            pos += 1
        elif s < 0:
            neg += 1
        else:
            neu += 1
        for p, one in _extract_phrases(tokens):
            phrase_counter[p] += one

    total = pos + neu + neg or 1
    sentiment = {
        "positive": round(pos / total, 4),
        "neutral": round(neu / total, 4),
        "negative": round(neg / total, 4),
    }

    top_phrases = _rank_phrases(phrase_counter, top_n=top_n, min_count=min_count)

    return {
        "scope": {
            "area": area,
            "budget_min": budget_min,
            "budget_max": budget_max,
            "listings_in_scope": listings_in_scope,
            "reviews_count": reviews_count,
            "is_citywide": area is None or str(area).strip() == "" or str(area).strip().upper() == "ALL",
        },
        "sentiment": sentiment,
        "top_phrases": top_phrases,
    }


def compute_reviews_sentiment(
    area: Optional[str],
    budget_min: Optional[float],
    budget_max: Optional[float],
    recent_months: Optional[int] = None,
    sample_size: int = 4000,
    sample_strategy: str = "recent",
) -> Dict[str, object]:
    """Return only sentiment distribution and scope counts."""
    scoped = get_scoped_comments_cached(
        area=area,
        budget_min=budget_min,
        budget_max=budget_max,
        recent_months=recent_months,
        sample_size=sample_size,
        sample_strategy=sample_strategy,
    )
    comments = scoped.get("comments", [])
    listings_in_scope = int(scoped.get("listings_in_scope", 0))

    pos = neu = neg = 0
    for text in comments:
        s = _classify_sentiment(_tokenize(text))
        if s > 0:
            pos += 1
        elif s < 0:
            neg += 1
        else:
            neu += 1
    total = pos + neu + neg or 1
    return {
        "scope": {
            "area": area,
            "budget_min": budget_min,
            "budget_max": budget_max,
            "listings_in_scope": listings_in_scope,
            "reviews_count": int(scoped.get("reviews_count", len(comments))),
            "is_citywide": area is None or str(area).strip() == "" or str(area).strip().upper() == "ALL",
        },
        "sentiment": {
            "positive": round(pos / total, 4),
            "neutral": round(neu / total, 4),
            "negative": round(neg / total, 4),
        }
    }


def _normalize_text(text: str, per_comment_limit: int) -> str:
    t = text or ""
    t = _URL_RE.sub("", t)
    t = t.strip()
    if len(t) > per_comment_limit:
        t = t[:per_comment_limit]
    t = _WS_RE.sub(" ", t)
    return t


def _split_sentences(text: str) -> List[str]:
    # Simple sentence split; if no punctuation, return as single unit
    if not text:
        return []
    parts = _SENT_SPLIT_RE.split(text)
    return [p.strip() for p in parts if p and len(p.strip()) >= 10]


def _contains_aspect(s: str) -> bool:
    low = s.lower()
    for k in _ASPECT_KEYS:
        if k in low:
            return True
    return False


def _preprocess_comments_for_llm(
    comments: List[str],
    max_total_chars: int = 20000,
    per_comment_limit: int = 220,
    prefer_aspect_sentences: bool = True,
) -> List[str]:
    """
    Reduce LLM context by:
    - removing URLs/whitespace noise
    - truncating per-comment length
    - splitting into sentences and keeping aspect-focused ones
    - deduplicating sentences
    - enforcing a total character budget
    """
    print(f"🧠 [opinions] preprocess: in={len(comments)}, budget={max_total_chars}, per_comment_limit={per_comment_limit}, aspect_only={prefer_aspect_sentences}")
    if not comments:
        return []

    seen: set = set()
    budget = max_total_chars
    prepared: List[str] = []
    kept_aspect = 0

    # First pass: collect aspect-focused sentences
    for raw in comments:
        if budget <= 0:
            break
        norm = _normalize_text(raw, per_comment_limit)
        if not norm:
            continue
        units = _split_sentences(norm) if prefer_aspect_sentences else [norm]
        if prefer_aspect_sentences:
            units = [u for u in units if _contains_aspect(u)] or []
        for u in units:
            key = u.lower()
            if key in seen:
                continue
            seen.add(key)
            prepared.append(u)
            kept_aspect += 1
            budget -= len(u) + 1
            if budget <= 0:
                break

    # Fallback: if too few, add raw normalized snippets
    added_raw = 0
    if len(prepared) < 20 and budget > 0:
        for raw in comments:
            if budget <= 0:
                break
            norm = _normalize_text(raw, per_comment_limit)
            key = norm.lower()
            if not norm or key in seen:
                continue
            seen.add(key)
            prepared.append(norm)
            added_raw += 1
            budget -= len(norm) + 1

    print(f"🧠 [opinions] preprocess: prepared={len(prepared)} (aspect_sentences={kept_aspect}, raw_fallback={added_raw}), remaining_budget={budget}")
    return prepared


def compute_reviews_top_phrases(
    area: Optional[str],
    budget_min: Optional[float],
    budget_max: Optional[float],
    top_n: int = 5,
    recent_months: Optional[int] = None,
    sample_size: int = 4000,
    sample_strategy: str = "recent",
) -> Dict[str, object]:
    """Return only top opinion phrases (LLM-based, English) and scope counts.
    Always try LLM first; if it returns empty, fall back to n-grams.
    """
    print(
        "🧠 [opinions] service.compute_reviews_top_phrases: ",
        {
            "area": area,
            "bmin": budget_min,
            "bmax": budget_max,
            "top_n": top_n,
            "recent_months": recent_months,
            "sample_size": sample_size,
            "sample_strategy": sample_strategy,
        }
    )

    scoped = get_scoped_comments_cached(
        area=area,
        budget_min=budget_min,
        budget_max=budget_max,
        recent_months=recent_months,
        sample_size=sample_size,
        sample_strategy=sample_strategy,
    )
    comments = scoped.get("comments", [])
    listings_in_scope = int(scoped.get("listings_in_scope", 0))
    reviews_count = int(scoped.get("reviews_count", 0))

    print(
        f"🧠 [opinions] service: listings_in_scope={listings_in_scope}, total_reviews={reviews_count}, fetched_comments={len(comments)}"
    )

    # New: compress and deduplicate context for LLM to reduce latency
    prepared_comments = _preprocess_comments_for_llm(
        comments,
        max_total_chars=20000,
        per_comment_limit=220,
        prefer_aspect_sentences=True,
    )

    items: List[Dict[str, object]] = []

    # LLM-based opinions (English)
    llm_attempted = False
    llm_error: Optional[str] = None
    if extract_review_opinions is not None:
        try:
            print(
                f"🧠 [opinions] service: calling LLM extractor with prepared={len(prepared_comments)} (fallback to raw if 0)"
            )
            llm_attempted = True
            items = extract_review_opinions(
                comments=prepared_comments if prepared_comments else comments,
                top_n=top_n,
            ) or []
            print(f"🧠 [opinions] service: LLM extractor returned items={len(items)}")
        except Exception as e:
            import traceback
            llm_attempted = True
            llm_error = str(e)
            print(f"❌ [opinions] service: LLM extractor failed: {e}\n{traceback.format_exc()}")
            items = []
    else:
        print("⚠️ [opinions] service: extract_review_opinions not available")
        llm_error = "extractor_not_available"

    # 不再进行 n-gram 回退；当 LLM 失败或返回空时，返回带有重试提示的结构化结果
    success = bool(items)
    print(f"🧠 [opinions] service: final_items={len(items)} success={success}")
    next_sample_size = max(30, int(sample_size) - 5) if not success else int(sample_size)

    return {
        "success": success,
        "scope": {
            "area": area,
            "budget_min": budget_min,
            "budget_max": budget_max,
            "listings_in_scope": listings_in_scope,
            "reviews_count": int(scoped.get("reviews_count", len(comments))),
            "reviews_used": len(comments),
            "is_citywide": area is None or str(area).strip() == "" or str(area).strip().upper() == "ALL",
        },
        "top_phrases": items,
        # 重试提示（仅当失败时）
        "retry": (not success),
        "retry_reason": ("llm_empty" if llm_attempted and not items and not llm_error else ("llm_error" if llm_error else None)),
        "llm_error": llm_error,
        "attempted_sample_size": int(sample_size),
        "next_sample_size": next_sample_size,
    } 