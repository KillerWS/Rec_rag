import pandas as pd
from db import execute_query
from collections import Counter
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from load_llm import get_llm  # 🔹 你的 LLM 加载模块
import time
import traceback
import random
import json
import re
import itertools

# 这个模块是做word cloud 高频短语的抽取s


# 🔹 Prompt模板
SUMMARY_PROMPT = """
You are an AI assistant helping to summarize Airbnb guest reviews.

Task:
- Read the following guest reviews.
- Extract the core feedback points strictly in English.
- Summarize each feedback into a short phrase (3-8 words), ASCII letters only.
- Only focus on concrete aspects like host responsiveness, location convenience, room cleanliness, facilities, check-in/out, noise level, transport access.
- Ignore generic words like "great", "nice", "good", "well".
- If reviews are not in English, translate them to English first.

Reviews:
{reviews_text}

Output rules:
- Return ONLY a JSON array of strings. No extra keys or text.
- Each item must be a standalone English short phrase, e.g. ["fast host response", "reliable wifi connection", "quiet neighborhood", "clean and tidy room"].
- Do NOT include numbering, bullets, or any non-English characters.
"""

REPAIR_PROMPT = """
You are polishing a list of feedback phrases extracted from Airbnb guest reviews.

Task:
- Produce EXACTLY 12 high-quality English short phrases (3-8 words), ASCII letters only.
- Each phrase must describe an accommodation aspect + an opinion, e.g. "fast host response", "reliable wifi connection", "clean bathroom", "easy self check-in", "quiet neighborhood".
- Focus on host responsiveness, check-in/out, cleanliness, facilities, wifi/internet, heating/AC, noise, space, location & transport.
- Remove incomplete or generic fragments (e.g., "location is", "hotel in", "good", "nice").
- Translate non-English content to English.

Input reviews:
{reviews_text}

Output rules:
- Return ONLY a JSON array of 12 strings. No extra keys or text.
"""

# 领域关键词集合（用于过滤）
DOMAIN_KEYWORDS = set([
    'wifi','wi-fi','internet','network','speed','signal',
    'host','response','reply','communication','contact','support','helpful','friendly',
    'check','checkin','check-in','checkout','check-out','self','self-checkin',
    'door','lock','key','code',
    'location','area','neighborhood','neighbourhood','transport','metro','subway','ubahn','u-bahn','sbahn','s-bahn','train','bus','tram','station',
    'clean','cleanliness','cleaning','tidy','hygiene','bathroom','toilet','kitchen','shower','water','hot','cold','heating','heater','radiator','ac','air','aircon','conditioning',
    'bed','mattress','pillow','linen','towel',
    'noise','quiet','calm','silent','soundproof',
    'view','balcony','terrace','window',
    'spacious','space','small','tiny','cozy','cozy',
    'appliances','fridge','microwave','oven','stove','washer','dryer',
    'supermarket','bakery','cafe','restaurant','coffee'
])

# 意见/描述关键词集合（要求至少包含其中一个）
OPINION_KEYWORDS = set([
    'fast','quick','prompt','responsive','reliable','stable','strong','weak','slow',
    'clean','tidy','dirty','fresh',
    'quiet','noisy','loud','calm','peaceful',
    'easy','smooth','complicated','difficult',
    'convenient','central','close','near','walkable','accessible',
    'spacious','large','roomy','small','tiny','cozy','comfortable','comfy',
    'helpful','friendly','kind','attentive','rude',
    'modern','new','old','outdated','dated','renovated',
    'working','functional','broken','faulty'
])

# 常见非英文停用词（用于最后一道防线过滤）
NON_EN_STOPWORDS = set([
    # Spanish
    'gracias','por','muchas','una','que','para','sin','duda','muy','zona','pas','est','es','del','la','el','las','los','de','en','y','un','una','unos','unas','al','lo','como','con','su','sus','nos','nosotros','ellos','ellas','muy','bueno','buen','buenos','buenas','bien',
    # German
    'und','die','der','das','ist','mit','nicht','ein','eine','einer','einem','zu','im','am','den','dem','auf','für','von','sehr','ganz',
    # French
    'nous','avoir','accueillis','merci','pour','tres','tres','bien','etre','etre','de','la','le','les','au','aux','du','des'
])

EN_WORD_RE = re.compile(r"^[A-Za-z][A-Za-z\- ]+[A-Za-z]$")

def _is_valid_english_phrase(text: str) -> bool:
    if not isinstance(text, str):
        return False
    s = text.strip()
    if len(s) < 3:
        return False
    # ASCII letters and spaces/hyphen
    if not EN_WORD_RE.match(s):
        return False
    # tokenization
    words = [w for w in re.findall(r"[A-Za-z]+", s.lower())]
    if len(words) < 2:
        return False
    # avoid fragments ending with prepositions or verbs without complement
    if words[-1] in {'in','at','of','to','is','are','was','were'}:
        return False
    # drop if dominated by obvious non-English stopwords (last defense)
    if any(w in NON_EN_STOPWORDS for w in words):
        return False
    # must contain at least one domain keyword
    joined = ' '.join(words)
    if not any(kw in joined for kw in DOMAIN_KEYWORDS):
        return False
    # must contain at least one opinion keyword
    if not any(ow in joined for ow in OPINION_KEYWORDS):
        return False
    return True

def _normalize_phrase(text: str) -> str:
    s = re.sub(r"\s+", " ", text.strip())
    # lower for counting, but keep as-is for display later if needed
    return s.lower()

def postprocess_phrases(candidates):
    seen = set()
    result = []
    for cand in candidates:
        if not isinstance(cand, str):
            continue
        cand = clean_phrase(cand)
        if not _is_valid_english_phrase(cand):
            continue
        norm = _normalize_phrase(cand)
        if norm in seen:
            continue
        seen.add(norm)
        result.append(norm)
    return result

def get_sampled_reviews(sample_size=1000, min_length=30):
    """从 reviews 表中抽取样本"""
    t_start = time.time()
    print(f"[reviews_summary.get_sampled_reviews] start: sample_size={sample_size}, min_length={min_length}")

    # 当样本量较小的时候，尽量避免全表扫描
    if sample_size <= 50:
        # 尝试用主键范围随机抽样（更快），需要知道 id 上下界
        try:
            print("[reviews_summary.get_sampled_reviews] trying fast id-range sampling")
            # 猜测表有自增主键 id；获取范围
            bounds = execute_query("SELECT MIN(id) AS min_id, MAX(id) AS max_id FROM reviews")
            if not bounds.empty and pd.notna(bounds['min_id'].iloc[0]) and pd.notna(bounds['max_id'].iloc[0]):
                min_id = int(bounds['min_id'].iloc[0])
                max_id = int(bounds['max_id'].iloc[0])
                candidate_ids = set()
                for _ in range(sample_size * 3):  # 过采样避免空洞
                    candidate_ids.add(random.randint(min_id, max_id))
                id_list = ','.join(str(i) for i in sorted(candidate_ids))
                query = f"""
                    SELECT comments FROM reviews 
                    WHERE id IN ({id_list})
                      AND comments IS NOT NULL 
                      AND CHAR_LENGTH(comments) >= {int(min_length)}
                    LIMIT {int(sample_size)}
                """
                df = execute_query(query)
                if not df.empty and len(df) >= 1:
                    print(f"[reviews_summary.get_sampled_reviews] id-range sampling got {len(df)} rows in {time.time()-t_start:.3f}s")
                    return df['comments'].dropna().tolist()[:sample_size]
                else:
                    print("[reviews_summary.get_sampled_reviews] id-range sampling returned empty, fallback to RAND()")
            else:
                print("[reviews_summary.get_sampled_reviews] cannot get id bounds, fallback to RAND()")
        except Exception as e:
            print(f"[reviews_summary.get_sampled_reviews] id-range sampling failed: {e}, fallback to RAND()")

        # 小样本退回 RAND()（虽然慢，但规模小还能接受）
        try:
            print("[reviews_summary.get_sampled_reviews] using SQL-level random sampling (ORDER BY RAND())")
            query = f"""
                SELECT comments FROM reviews 
                WHERE comments IS NOT NULL AND CHAR_LENGTH(comments) >= {int(min_length)}
                ORDER BY RAND()
                LIMIT {int(sample_size)}
            """
            df = execute_query(query)
            print(f"[reviews_summary.get_sampled_reviews] SQL RAND() sampling done in {time.time()-t_start:.3f}s, df.empty={df.empty}")
            if df.empty:
                return []
            return df['comments'].dropna().tolist()
        except Exception as e:
            print(f"[reviews_summary.get_sampled_reviews] SQL-level RAND() sampling failed: {e}")
            # 继续走下方的客户端采样逻辑

    query = "SELECT comments FROM reviews WHERE comments IS NOT NULL"
    print("[reviews_summary.get_sampled_reviews] executing query for comments (client-side sampling)...")
    df = execute_query(query)
    print(f"[reviews_summary.get_sampled_reviews] query done in {time.time()-t_start:.3f}s, df.empty={df.empty}")
    
    if df.empty:
        return []
    
    comments = df['comments'].dropna()
    before_filter = len(comments)
    comments = comments[comments.str.len() >= min_length]
    after_filter = len(comments)
    
    sampled_n = min(sample_size, len(comments))
    print(f"[reviews_summary.get_sampled_reviews] comments before_filter={before_filter}, after_filter(min_len)={after_filter}, sampled_n={sampled_n}")
    
    sampled = comments.sample(n=sampled_n, random_state=42).tolist()
    print(f"[reviews_summary.get_sampled_reviews] sampling done in {time.time()-t_start:.3f}s")
    return sampled

def summarize_reviews_with_llm(reviews_batch):
    """对一批 reviews 调用 LLM 总结观点"""
    t0 = time.time()
    print(f"[reviews_summary.summarize_reviews_with_llm] start: batch_size={len(reviews_batch)}")
    try:
        print("[reviews_summary.summarize_reviews_with_llm] loading LLM via get_llm() ...")
        llm = get_llm()
        print(f"[reviews_summary.summarize_reviews_with_llm] LLM loaded in {time.time()-t0:.3f}s: type={type(llm)}")
    except Exception as e:
        print(f"⚠️ get_llm() failed: {e}\n{traceback.format_exc()}")
        return []

    if llm is None:
        print("[reviews_summary.summarize_reviews_with_llm] LLM is None, skip summarization")
        return []

    prompt = PromptTemplate(input_variables=["reviews_text"], template=SUMMARY_PROMPT)
    chain = LLMChain(llm=llm, prompt=prompt, output_key="summary")

    joined_reviews = "\n".join(reviews_batch)
    print(f"[reviews_summary.summarize_reviews_with_llm] invoking chain.invoke, reviews_text_len={len(joined_reviews)}")

    points_raw = []
    try:
        t1 = time.time()
        response = chain.invoke({"reviews_text": joined_reviews})
        if isinstance(response, dict) and "summary" in response:
            response_text = response["summary"]
        else:
            response_text = str(response)
        print(f"[reviews_summary.summarize_reviews_with_llm] chain.invoke done in {time.time()-t1:.3f}s, total_elapsed={time.time()-t0:.3f}s")
        preview = str(response_text)[:500].replace('\n', '\\n')
        print(f"[reviews_summary.summarize_reviews_with_llm] raw_response_preview=\"{preview}\"")
    except Exception as e:
        print(f"⚠️ LLM summarization failed: {e}\n{traceback.format_exc()}")
        return []

    # 先 JSON 解析
    try:
        if isinstance(response_text, str) and response_text.strip().startswith('['):
            parsed = json.loads(response_text)
            if isinstance(parsed, list):
                points_raw = [str(x) for x in parsed if isinstance(x, str)]
    except Exception as e:
        print(f"[reviews_summary.summarize_reviews_with_llm] JSON parse failed: {e}")

    # 若 JSON 为空，逐行解析
    if not points_raw:
        for line in str(response_text).split("\n"):
            clean_line = re.sub(r"^\s*(?:[-*•\u2022]|\d+[\.)])\s*", "", line).strip()
            if clean_line:
                points_raw.append(clean_line)

    # 过滤与规范化
    points = postprocess_phrases(points_raw)

    # 若数量太少或为空，走修复提示词再试一次
    if len(points) < 6:
        print(f"[reviews_summary.summarize_reviews_with_llm] too few valid phrases ({len(points)}), trying repair prompt")
        repair_prompt = PromptTemplate(input_variables=["reviews_text"], template=REPAIR_PROMPT)
        repair_chain = LLMChain(llm=llm, prompt=repair_prompt, output_key="phrases")
        try:
            t2 = time.time()
            repair_resp = repair_chain.invoke({"reviews_text": joined_reviews})
            if isinstance(repair_resp, dict) and "phrases" in repair_resp:
                repair_text = repair_resp["phrases"]
            else:
                repair_text = str(repair_resp)
            preview2 = str(repair_text)[:500].replace('\n', '\\n')
            print(f"[reviews_summary.summarize_reviews_with_llm] repair_raw_preview=\"{preview2}\"")
            # parse JSON
            repaired = []
            try:
                if isinstance(repair_text, str) and repair_text.strip().startswith('['):
                    repaired = json.loads(repair_text)
                    if not isinstance(repaired, list):
                        repaired = []
            except Exception:
                repaired = [s.strip() for s in str(repair_text).split("\n") if s.strip()]
            points = postprocess_phrases(repaired)
            print(f"[reviews_summary.summarize_reviews_with_llm] repair produced {len(points)} valid phrases")
        except Exception as e:
            print(f"⚠️ repair prompt failed: {e}\n{traceback.format_exc()}")

    print(f"[reviews_summary.summarize_reviews_with_llm] parsed {len(points)} points from response")
    return points

def clean_phrase(text):
    """清理LLM输出的每个短语"""
    if not isinstance(text, str):
        return ""

    # 去除多余的引号和大括号
    text = text.strip()
    text = re.sub(r"^[{\"\':,.\s]+", "", text)  # 去掉开头的 { " , .
    text = re.sub(r"[}\"\',.\s]+$", "", text)    # 去掉结尾的 } " , .
    
    return text

def curate_phrases_with_llm(reviews_batch, target_n: int = 20):
    """使用修复提示词，直接生成高质量英文短语列表"""
    try:
        llm = get_llm()
    except Exception as e:
        print(f"⚠️ get_llm() in curate failed: {e}")
        return []
    if llm is None:
        return []

    joined_reviews = "\n".join(reviews_batch)
    repair_prompt = PromptTemplate(input_variables=["reviews_text"], template=REPAIR_PROMPT)
    repair_chain = LLMChain(llm=llm, prompt=repair_prompt, output_key="phrases")
    try:
        resp = repair_chain.invoke({"reviews_text": joined_reviews})
        if isinstance(resp, dict) and "phrases" in resp:
            text = resp["phrases"]
        else:
            text = str(resp)
        preview_text = str(text)[:400].replace('\n', '\\n')
        print(f"[reviews_summary.curate] raw_preview=\"{preview_text}\"")
        curated = []
        try:
            if isinstance(text, str) and text.strip().startswith("["):
                parsed = json.loads(text)
                if isinstance(parsed, list):
                    curated = [s for s in parsed if isinstance(s, str)]
        except Exception:
            curated = [s.strip() for s in str(text).split("\n") if s.strip()]
        curated = postprocess_phrases(curated)
        # 截断到目标数量
        if target_n and len(curated) > target_n:
            curated = curated[:target_n]
        print(f"[reviews_summary.curate] curated={len(curated)}")
        return curated
    except Exception as e:
        print(f"⚠️ curate_phrases_with_llm failed: {e}\n{traceback.format_exc()}")
        return []

def get_review_insights(sample_size=1000, batch_size=20, top_n=50, min_length=30):
    """
    主函数：返回词云数据
    
    参数：
    - sample_size: 总共抽取多少条评论
    - batch_size: 每一批送给 LLM 多少条评论
    - top_n: 最后统计出现频率最多的短语数
    - min_length: 最短评论长度过滤
    """

    t_start = time.time()
    print(f"[reviews_summary.get_review_insights] called with sample_size={sample_size}, batch_size={batch_size}, top_n={top_n}, min_length={min_length}")
    print("🔹get_review_insights called,  开始抽取评论样本，总共抽取 {} 条评论".format(sample_size))
    sampled_reviews = get_sampled_reviews(sample_size=sample_size, min_length=min_length)
    print(f"[reviews_summary.get_review_insights] sampling complete in {time.time()-t_start:.3f}s, sampled_reviews={len(sampled_reviews)}")

    if not sampled_reviews:
        print("[reviews_summary.get_review_insights] no sampled reviews, returning empty list")
        return []

    all_points = []

    total_batches = (len(sampled_reviews) + batch_size - 1) // batch_size
    print(f"[reviews_summary.get_review_insights] total_batches={total_batches}")
    for i in range(0, len(sampled_reviews), batch_size):
        batch_idx = i // batch_size + 1
        batch = sampled_reviews[i:i+batch_size]
        print(f"[reviews_summary.get_review_insights] processing batch {batch_idx}/{total_batches}, size={len(batch)}")
        batch_points = summarize_reviews_with_llm(batch)
        all_points.extend(batch_points)
        print(f"✅ Processed batch {batch_idx} ({len(batch)} reviews), points_collected={len(all_points)}")

    # 先过滤 LLM 原始短语
    filtered_points = [ _normalize_phrase(p) for p in all_points if _is_valid_english_phrase(p) ]

    # 使用策划器生成高质量候选短语
    curated = curate_phrases_with_llm(sampled_reviews, target_n=top_n)

    if curated:
        # 用原始过滤后的计数给策划短语打权重
        counter = Counter(filtered_points)
        def phrase_match_score(cur: str) -> int:
            score = 0
            for p, c in counter.items():
                if cur in p or p in cur:
                    score += c
            return score
        scored = [(cur, phrase_match_score(cur)) for cur in curated]
        # 若全为0，则给一个最小计数1
        if all(s == 0 for _, s in scored):
            scored = [(cur, 1) for cur, _ in scored]
        # 排序截断
        scored.sort(key=lambda x: x[1], reverse=True)
        top_pairs = scored[:top_n]
        wordcloud_data = [{"name": clean_phrase(cur), "value": int(score)} for cur, score in top_pairs]
        print(f"[reviews_summary.get_review_insights] curated final={len(wordcloud_data)}")
        return wordcloud_data

    # 无法策划，则走严格 n-gram 兜底
    print("[reviews_summary.get_review_insights] curated empty, using strict n-gram fallback")
    anchor_keywords = DOMAIN_KEYWORDS
    phrase_counter = Counter()
    for rv in sampled_reviews:
        tokens = re.findall(r"[A-Za-z]{2,}", str(rv).lower())
        if not tokens:
            continue
        bigrams = [f"{a} {b}" for a, b in zip(tokens, tokens[1:])]
        trigrams = [f"{a} {b} {c}" for a, b, c in zip(tokens, tokens[1:], tokens[2:])]
        candidates = bigrams + trigrams
        for phrase in candidates:
            if not re.search(r"[A-Za-z]", phrase):
                continue
            if not any(kw in phrase for kw in anchor_keywords):
                continue
            if any(w in {'the','and','for','with','from','that','this','have','has','was','were','are','you','your','our','very','just','only','also','more','than','been'} for w in phrase.split()):
                continue
            if not _is_valid_english_phrase(phrase):
                continue
            phrase_counter.update([_normalize_phrase(phrase)])
    top_points_pairs = phrase_counter.most_common(top_n)
    wordcloud_data = [{"name": clean_phrase(p), "value": c} for p, c in top_points_pairs if clean_phrase(p)]
    print(f"[reviews_summary.get_review_insights] fallback produced {len(wordcloud_data)} items")
    return wordcloud_data
