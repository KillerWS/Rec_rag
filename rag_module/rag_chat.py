import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Dict, Any, Tuple, Optional
from langchain.embeddings.base import Embeddings
from sql_generator import validate_preferences, build_sql_from_preferences, apply_fallback_for_empty_results

#from load_embedding_model import get_embeddings
from load_embedding_model_api import get_embeddings
from langchain_community.embeddings import HuggingFaceBgeEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.messages import AIMessage, HumanMessage
from langchain.schema import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from db import execute_query, get_listing_by_id
import uuid
import json


TEMP_INDEX_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "rag_indexes"))
# 确保目录存在
os.makedirs(TEMP_INDEX_DIR, exist_ok=True)

from functools import lru_cache
from langchain_community.vectorstores import FAISS


GLOBAL_FAISS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "faiss_indexes", "global_reviews")
)

@lru_cache(maxsize=1)
def get_global_vectordb() -> FAISS:
    """
    首次调用时把 55 万评论的全局向量库加载进内存，
    后续直接复用，避免重复 IO / 反序列化。
    """
    print("⚡ Loading global FAISS index ...")
    try:
        embeddings = safe_get_embeddings()
        vectordb = FAISS.load_local(
            GLOBAL_FAISS_DIR,
            embeddings=embeddings,
            allow_dangerous_deserialization=True
        )
        print("✅ Global FAISS ready")
        return vectordb
    except ValueError as e:
        print(f"Error loading global vectordb: {e}")
        raise

prefs = {
    "neighbourhood_group_cleansed": "Berlin",
    "neighbourhood_cleansed": None,          # may be None
    "price_min":  50,
    "price_max": 150,
    "room_type": "Private room",
    "min_reviews": 20               # 自己定阈值
}

def build_sql_from_pref(pref: dict, limit: int = 300) -> str:
    """
    根据偏好动态拼 SQL；只有非空字段才加入 WHERE。
    这里继续用字符串插值，**确保所有值都已校验/转义**。
    """
    # Validate preferences first
    validated_pref = validate_preferences(pref)
    
    # Use the build_sql_from_preferences function
    return build_sql_from_preferences(validated_pref, limit)

def build_sql_from_pref_with_fallback(pref: dict, limit: int = 300) -> Tuple[str, dict]:
    """
    Build SQL with validation and fallback for when no results are found.
    Returns both the SQL query and the validated preferences used.
    """
    # Validate preferences first
    validated_pref = validate_preferences(pref)
    
    # Build initial SQL
    sql = build_sql_from_preferences(validated_pref, limit)
    
    # Return both SQL and validated preferences
    return sql, validated_pref

def apply_fallback_strategy(pref: dict, limit: int = 300) -> Tuple[str, dict]:
    """
    Apply fallback strategy by removing min_reviews constraint
    """
    return apply_fallback_for_empty_results(pref, limit)

def coarse_recall_ids(pref: dict, limit: int = 300) -> list[int]:
    """
    Perform coarse recall of listing IDs based on preferences with fallback strategy.
    If no results are found with current preferences, try removing min_reviews constraint.
    """
    # First try with all validated preferences
    sql, validated_pref = build_sql_from_pref_with_fallback(pref, limit)
    df = execute_query(sql)
    print("# --------- 1) 结构化 SQL 粗召回 ----------")
    print(df)
    
    # If no results found, apply fallback by removing min_reviews constraint
    if df.empty and 'min_reviews' in validated_pref:
        print("No results found with current filters. Applying fallback strategy...")
        fallback_sql, fallback_pref = apply_fallback_strategy(validated_pref, limit)
        df = execute_query(fallback_sql)
        print("# --------- 1.1) 应用回退策略 - 移除评论数限制 ----------")
        print(df)
    
    return df["id"].tolist() if not df.empty else []

def make_filter(candidate_ids: set[int]):
    def _filter(m: dict) -> bool:
        return m["listing_id"] in candidate_ids
    print("_filter")
    print(_filter)
    return _filter

def get_relevant_listing_ids():
    """🔹获取热门房源ID（按评论数排序） 按number_of_reviews 排序抽取10个"""
    sql = """
    SELECT id 
    FROM listings 
    ORDER BY number_of_reviews DESC 
    LIMIT 10
    """
    df = execute_query(sql)
    return df['id'].tolist() if not df.empty else []

def get_reviews_with_metadata(listing_ids, limit=30):
    """🔹获取评论及关联的元数据（修复版）"""
    if not listing_ids:
        return []

    ids_str = ",".join(str(id) for id in listing_ids)
    sql = f"""
    SELECT 
      r.comments,
      l.room_type,
      l.price,
      r.listing_id,  -- 🚩 新增关联字段
      CASE 
        WHEN l.price BETWEEN 0 AND 40 THEN '0-40'
        WHEN l.price BETWEEN 40 AND 80 THEN '40-80'
        WHEN l.price BETWEEN 80 AND 120 THEN '80-120'
        WHEN l.price BETWEEN 120 AND 160 THEN '120-160'
        WHEN l.price BETWEEN 160 AND 200 THEN '160-200'
        ELSE '200+' 
      END AS price_bucket
    FROM 
      reviews r
    JOIN 
      listings l ON r.listing_id = l.id
    WHERE 
      r.listing_id IN ({ids_str})
      AND r.comments IS NOT NULL
    LIMIT {limit}
    """
    df = execute_query(sql)
    return df.to_dict('records') if not df.empty else []

# def get_reviews_by_listing_ids(listing_ids, limit=30):
#     """🔹根据id查reviews，限制总量"""
#     if not listing_ids:
#         return []

#     ids_str = ",".join(str(id) for id in listing_ids)
#     sql = f"""
#     SELECT comments 
#     FROM reviews 
#     WHERE listing_id IN ({ids_str}) 
#     AND comments IS NOT NULL 
#     LIMIT {limit}
#     """
#     df = execute_query(sql)
#     return df['comments'].dropna().tolist() if not df.empty else []

def parse_history(history):
    parsed = []
    for msg in history:
        if msg["type"] == "user":  # 用户消息 → HumanMessage
            parsed.append(HumanMessage(content=msg["data"]))
        elif msg["type"] == "system":  # 系统消息 → AIMessage
            parsed.append(AIMessage(content=msg["data"]))
    return parsed

def build_sub_documents(reviews_with_metadata):
    """🔹将评论分块并携带元数据"""
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    
    # 🚩 创建携带元数据的文档
    docs = [
        Document(
            page_content=item["comments"],  # 文本内容
            metadata={
                "room_type": item["room_type"],
                "price_bucket": item["price_bucket"],
                "listing_id": item.get("listing_id", "")  # 可选：关联房源ID
            }
        ) 
        for item in reviews_with_metadata
    ]
    
    # 🚩 分割时继承元数据
    split_docs = splitter.split_documents(docs)
    return split_docs

def create_temp_retriever(docs):
    """🔹创建临时检索器"""
    try:
        embeddings = safe_get_embeddings()
        vectordb = FAISS.from_documents(docs, embeddings)
        retriever = vectordb.as_retriever(search_kwargs={"k": 5})
        return retriever
    except ValueError as e:
        print(f"Error creating temp retriever: {e}")
        return None

def safe_get_embeddings() -> Embeddings:
    """
    Safely get embeddings model, raising exception if it can't be loaded
    to prevent typing issues.
    """
    embedding_model = get_embeddings()
    if embedding_model is None:
        raise ValueError("Failed to load embedding model")
    return embedding_model

# ✅ 准备阶段
def rag_prepare():
    listing_ids = get_relevant_listing_ids()
    reviews = get_reviews_with_metadata(listing_ids)
    if not reviews:
        return None
    
    # 🚩 生成携带元数据的文档
    docs = build_sub_documents(reviews)

    try:
        embeddings = safe_get_embeddings()
        print(docs)
        vectordb = FAISS.from_documents(docs, embeddings)
        
        index_id = str(uuid.uuid4())
        save_path = os.path.join(TEMP_INDEX_DIR, index_id)
        vectordb.save_local(save_path)

        print(f"✅ RAG context saved at {save_path}")
        return index_id
    except ValueError as e:
        print(f"Error in rag_prepare: {e}")
        return None

#  意图检测模块， 对应简单问答! 因为始终走RAG ， prompt 约束力不够强
import re
from typing import List

# ── ① 词库：可按需继续扩充 ────────────────────────────
_GREET_WORDS   = r"(hi|hello|hey|yo|hola|hallo|ciao|bonjour)"
_THANK_WORDS   = r"(thanks|thank you|thx|cheers|danke|gracias)"
_OTHER_SMALL   = r"(good\s*(morning|afternoon|evening|night))"
_EMOJI         = r"[\U0001F600-\U0001F64F\U0001F44D]"   # 😃 👍 等

_PATTERN = re.compile(
    rf"^({ _GREET_WORDS }|{ _THANK_WORDS }|{ _OTHER_SMALL }|{ _EMOJI }|\s|[!.,?])+?$",
    re.I
)

def is_small_talk(msg: str,
                  max_tokens: int = 4,
                  delimiters: str = r"[ ,.!?]+"  # 简易 tokenizer
                 ) -> bool:
    """
    只在『整句都由寒暄词 + 标点 / 空白 / emoji 组成』且 token 数很少时返回 True。
    """
    text = msg.strip()

    # A. 长文本直接认为有信息量
    if len(text) > 40:           # 可以调优
        return False

    # B. token 数过多 → 可能带有效信息
    tokens: List[str] = re.split(delimiters, text.lower())
    tokens = [t for t in tokens if t]          # 去空
    if len(tokens) > max_tokens:
        return False

    # C. 逐 token 检查是否都在词库，否则 fallback 到整体正则
    for t in tokens:
        if not re.fullmatch(
            rf"{ _GREET_WORDS }|{ _THANK_WORDS }|{ _OTHER_SMALL }", t, re.I
        ):
            return False

    # D. 最终用 regex 验证整体仅含闲聊元素（emoji/空白/标点）
    return bool(_PATTERN.match(text))

def classify_intent(user_message):
    # 简单但有效的规则匹配
    greeting_patterns = [
        r'^(hi|hello|hey|hiya)\s*[!.]*$',
        r'^(good\s+(morning|afternoon|evening))\s*[!.]*$',
        r'^(thanks?|thank\s+you|thx)\s*[!.]*$',
        r'^(glad\s+to\s+see\s+you)\s*[!.]*$',
        r'^[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF]+$'  # emoji only
    ]
    
    message_clean = user_message.lower().strip()
    
    for pattern in greeting_patterns:
        if re.match(pattern, message_clean, re.IGNORECASE):
            return "greeting"
    
    return "query"



# ✅ 对话阶段
def rag_chat_with_memory_focused(message: str, history, pref: dict, global_search: bool = False):
    """专注的RAG函数：只在确定需要检索时调用

    当 global_search 为 True 时：跳过候选ID过滤，直接在全局评论向量库检索。
    """
    print("执行专注的RAG检索")
    print(f"原始偏好: {pref}")
    
    # 加载历史记录
    chat_history = parse_history(history)
    
    # 确保偏好是dict格式
    if pref is None:
        pref = {}
    elif not isinstance(pref, dict):
        pref = json.loads(pref)
    
    # Validate preferences
    validated_pref = validate_preferences(pref)
    print(f"验证后的偏好: {validated_pref}")

    # --------- 1) 结构化 SQL 粗召回 ----------
    cand_ids = set(coarse_recall_ids(validated_pref, limit=300))
    print(f"🔍 SQL粗召回获取了 {len(cand_ids)} 个候选ID")
    # 当不处于 global_search 且没有候选ID时，自动回退为全局检索
    if not cand_ids and not global_search:
        print("🔁 无候选ID，自动回退到全局向量检索模式")
        use_global_search = True
    else:
        use_global_search = global_search

    # --------- 2) 全量向量库 + metadata filter ----------
    try:
        vectordb = get_global_vectordb()              # 👈 只加载一次/only load once
        if use_global_search:
            search_kwargs = {"k": 50, "fetch_k": 1000}
            print("🌐 全局搜索已开启：不使用listing_id过滤器")
        else:
            search_kwargs = {
                "k": 50,
                "fetch_k": 1000,
                "filter": {"listing_id": {"$in": list(cand_ids)}}
            }
        retriever = vectordb.as_retriever(search_kwargs=search_kwargs)
        
        # 🔍 调试: 检查retriever是否正确获取
        print(f"🔍 retriever初始化完成，类型: {type(retriever)}")
        print(f"🔍 retriever搜索参数: k={retriever.search_kwargs.get('k')}, fetch_k={retriever.search_kwargs.get('fetch_k')}")
        if use_global_search:
            print("🔍 retriever未设置过滤器（全局检索模式）")
        else:
            print(f"🔍 retriever过滤器包含 {len(retriever.search_kwargs.get('filter', {}).get('listing_id', {}).get('$in', []))} 个ID")

        from rag_module.rag_chain import get_rag_chain_for_listings
        # 使用专门的RAG提示词
        rag_chain = get_rag_chain_for_listings(retriever)
        
        # 🔍 调试: 检查RAG链准备情况
        print(f"🔍 RAG链准备完成，类型: {type(rag_chain)}")

        # 执行查询（第一次：按需带过滤器）
        print(f"🔍 开始执行RAG查询: '{message}'")
        result = rag_chain.invoke({
            "question": message,
            "chat_history": chat_history
        })

        # 如果不是全局模式且第一次结果为空，则回退到全局检索重试
        need_global_fallback = (not use_global_search) and (len(result.get("source_documents", [])) == 0)
        if need_global_fallback:
            print("🔁 过滤检索未命中文档，回退到全局向量检索重试")
            retriever = vectordb.as_retriever(search_kwargs={"k": 50, "fetch_k": 1000})
            rag_chain = get_rag_chain_for_listings(retriever)
            result = rag_chain.invoke({
                "question": message,
                "chat_history": chat_history
            })
        
        # 🔍 调试: 检查RAG结果内容
        print(f"🔍 RAG查询完成，结果键: {list(result.keys())}")
        if "source_documents" in result:
            print(f"🔍 找到 {len(result['source_documents'])} 个源文档")
            # 检查前两个文档的内容样例
            for i, doc in enumerate(result['source_documents'][:2]):
                print(f"🔍 文档 #{i+1} - metadata: {doc.metadata}")
                print(f"🔍 文档 #{i+1} - 内容前50字符: {doc.page_content[:50]}...")
        else:
            print("❗ RAG结果中没有source_documents键")
        
        # 构建返回结果
        response = {
            "answer": result["answer"],
            "source_documents": [
                {
                    "listing_id": doc.metadata["listing_id"],
                    "room_type": doc.metadata["room_type"],
                    "price_bucket": doc.metadata.get("price_bucket", "unknown"),
                    "snippet": doc.page_content,
                    "item_detail": get_listing_by_id(doc.metadata["listing_id"])
                }
                for doc in result["source_documents"]
            ] if "source_documents" in result else []
        }
        
        # 🔍 调试: 检查最终返回的结构
        print(f"🔍 最终返回包含 {len(response.get('source_documents', []))} 个文档")
        return response
        
    except Exception as e:
        import traceback
        print(f"RAG检索失败: {e}")
        print(f"❗ 详细错误: {traceback.format_exc()}")
        return {
            "answer": "I'm having trouble accessing the listings database. Could you try again with your question?",
            "source_documents": []
        }


# ========== 测试函数：全局模式请求 ==========
def test_rag_chat_global_mode():
    """模拟真实请求：sub_mode=review_qa + global_search=True（全局检索，不限 listing 过滤）"""
    try:
        from flask import Flask
        from db import init_db
        from load_llm import load_llm
        from load_embedding_model_api import load_embeddings

        app = Flask(__name__)
        init_db(app)
        load_llm()
        load_embeddings()

        # 英文消息（真实用户问题示例）
        message = "What do most guests say about Airbnb stays in Berlin?"

        # 模拟前端的对话历史（与 parse_history 期望结构一致）
        history = [
            {"type": "user", "data": "Hi"},
            {"type": "system", "data": "Hello! How can I help you?"},
        ]

        # 全局模式不需要偏好
        pref = {}

        with app.app_context():
            print("\n===== [Global Test] sub_mode=review_qa, global_search=True =====")
            res = rag_chat_with_memory_focused(
                message=message,
                history=history,
                pref=pref,
                global_search=True,
            )
            src_docs = res.get("source_documents", [])
            print(f"Global mode - source_documents: {len(src_docs)}")
            if src_docs:
                preview_ids = [d.get("listing_id") for d in src_docs[:5]]
                print(f"Global mode - first listing_ids: {preview_ids}")
            print(f"Global mode - answer preview: {res.get('answer', '')[:300]}...")

            return {
                "num_docs": len(src_docs),
                "first_listing_ids": [d.get("listing_id") for d in src_docs[:5]],
                "answer": res.get("answer", ""),
            }
    except Exception as e:
        print(f"❗ Global test failed: {e}")
        return {"error": str(e)}


# ===== 预设偏好（根据实际日志提供的示例） =====
DEFAULT_PRESET_PREF = {
    "room_type": "Entire home/apt",
    "price_min": 400,
    "price_max": 800,
    # 两种字段并存，后续验证会用 *_cleansed
    "neighbourhood_group": "Pankow",
    "neighbourhood": None,
    "minimum_nights": 3,
    "maximum_nights": 3,
    "min_reviews": 10,
    "reviews_per_month_min": None,
    "availability_min": None,
    "amenities_keywords": [],
    "location_keywords": ["berlin"],
    "experience_keywords": ["conference"],
    "semantic_query": "",
    "missing_dimension": [],
    "comfort_keywords": [],
    "neighbourhood_group_cleansed": "Pankow",
    "user_care": "✨ premium service expected",
}

# ========== 测试函数：带过滤请求 ==========
def test_rag_chat_filtered_mode():
    """模拟真实请求：sub_mode=review_qa + global_search=False（带 listing_id 过滤）"""
    try:
        from flask import Flask
        from db import init_db
        from load_llm import load_llm
        from load_embedding_model_api import load_embeddings

        app = Flask(__name__)
        init_db(app)
        load_llm()
        load_embeddings()

        # 英文消息（真实用户问题示例）
        message = "What do most guests say about Airbnb stays in Berlin?"

        # 模拟前端的对话历史
        history = [
            {"type": "user", "data": "I want a private entire home between 400€ and 800€ in Pankow, minimum 3 nights"},
            {"type": "system", "data": "Sure, I will look for options."},
        ]

        # 使用预设偏好（与日志一致）
        pref = DEFAULT_PRESET_PREF.copy()

        with app.app_context():
            print("\n===== [Filtered Test] sub_mode=review_qa, global_search=False =====")
            res = rag_chat_with_memory_focused(
                message=message,
                history=history,
                pref=pref,
                global_search=False,
            )
            src_docs = res.get("source_documents", [])
            print(f"Filtered mode - source_documents: {len(src_docs)}")
            if src_docs:
                preview_ids = [d.get("listing_id") for d in src_docs[:5]]
                print(f"Filtered mode - first listing_ids: {preview_ids}")
            print(f"Filtered mode - answer preview: {res.get('answer', '')[:300]}...")

            return {
                "num_docs": len(src_docs),
                "first_listing_ids": [d.get("listing_id") for d in src_docs[:5]],
                "answer": res.get("answer", ""),
            }
    except Exception as e:
        print(f"❗ Filtered test failed: {e}")
        return {"error": str(e)}


if __name__ == "__main__":
    # 允许直接通过命令行运行：python rag_module/rag_chat.py
    test_rag_chat_global_mode()
    # test_rag_chat_filtered_mode()