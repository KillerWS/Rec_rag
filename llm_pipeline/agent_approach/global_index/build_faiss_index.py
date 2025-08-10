import sys
import os
from pathlib import Path
from flask import Flask
from tqdm import tqdm
import numpy as np
from langchain_community.docstore.in_memory import InMemoryDocstore
import faiss

# 添加项目根路径，确保能 import db.py
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent.parent.parent
project_root1 = current_dir.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

# ✅ 导入数据库工具
from db import init_db, execute_query

# 导入Gemini嵌入模型
from load_embedding_model_api import get_embeddings, load_embeddings

# ✅ 创建 Flask app 实例并初始化数据库
app = Flask(__name__)
init_db(app)

from langchain.schema import Document
from langchain_community.vectorstores import FAISS
from functools import lru_cache

# 修改输出文件夹名
INDEX_PATH = str(project_root / "faiss_indexes" / "gemini_reviews")
MODEL_DIR = str(project_root1 / "models" / "embedding" / "BAAI" / "bge-large-en-v1.5")  # 保留作为备用

def load_reviews(limit_per_listing: int = 5, max_listings: int = None):
    """从数据库加载评论与地理信息，可选限制处理的房源数量"""
    # 修改SQL查询以适应新的数据库结构
    sql = """
        SELECT r.id AS review_id,
               r.comments AS text,
               r.listing_id,
               l.neighbourhood_group_cleansed AS neighbourhood_group,
               l.neighbourhood_cleansed AS neighbourhood,
               l.price,
               l.room_type,
               l.number_of_reviews
        FROM reviews r
        JOIN listings l ON l.id = r.listing_id
        WHERE r.comments IS NOT NULL AND r.comments != ''
        ORDER BY r.listing_id, LENGTH(r.comments) DESC
    """
    
    # 如果指定了最大房源数，添加LIMIT子句
    if max_listings is not None:
        sql += f"""
        LIMIT {max_listings * limit_per_listing}  -- 每个房源取{limit_per_listing}条评论
        """
    
    df = execute_query(sql)

    # 统计数据库中评论总数
    count_sql = """
        SELECT COUNT(*) as total_count
        FROM reviews r
        JOIN listings l ON l.id = r.listing_id
        WHERE r.comments IS NOT NULL AND r.comments != ''
    """
    count_df = execute_query(count_sql)
    total_count = count_df['total_count'].iloc[0] if not count_df.empty else 0

    # groupby-sample：每个 listing 取前 N 条
    reduced = (
        df.groupby("listing_id", as_index=False)
          .head(limit_per_listing)          # 已按长度降序，直接 head
    )
    
    # 打印数据量信息
    print(f"📊 数据库中总评论数: {total_count}")
    print(f"📊 本次处理评论数: {len(reduced)}")
    print(f"📊 向量化比例: {len(reduced) / total_count:.2%}")
    
    return reduced

def build(test_mode: bool = False):
    """构建并保存 FAISS 向量索引
    
    Args:
        test_mode: 如果为True，仅处理少量数据进行测试
    """
    # 测试模式下只处理20个房源的数据 (降低到20个，更快测试)
    max_listings = 20 if test_mode else None
    limit_per_listing = 3  # 每个房源只取前3条评论
    
    df = load_reviews(limit_per_listing=limit_per_listing, max_listings=max_listings)
    print(f"📄 查询到评论数量: {len(df)}")

    # 1️⃣ 构建文档对象并提取文本
    docs = []
    texts = []

    for row in tqdm(df.itertuples(), total=len(df), desc="📦 构建文档"):
            meta = {
                "review_id": row.review_id,
                "listing_id": row.listing_id,
                "neighbourhood_group": row.neighbourhood_group,
                "neighbourhood": row.neighbourhood,
                "price": float(row.price.replace('$', '').replace(',', '')) if row.price is not None else 0.0,
                "room_type": row.room_type,
                "n_reviews": row.number_of_reviews,
            }
            content = row.text.strip()
            if content:
                docs.append(Document(page_content=content, metadata=meta))
                texts.append(content)

    # 2️⃣ 使用 Gemini API 嵌入模型向量化文本
    print("🚀 开始使用 Gemini API 向量化文本...")
    
    # 确保嵌入模型已加载
    load_embeddings()
    embeddings_model = get_embeddings()
    
    if embeddings_model is None:
        print("❌ 无法加载嵌入模型，请检查API密钥设置")
        return
        
    batch_size = 16  # Gemini API可能需要较小的批量
    all_vectors = []
    
    for i in tqdm(range(0, len(texts), batch_size), desc="🔢 文本 → 向量"):
        batch = texts[i : i + batch_size]
        try:
            vecs = embeddings_model.embed_documents(batch)
            all_vectors.extend(vecs)
        except Exception as e:
            print(f"❌ 批次{i}向量化失败: {e}")
            # 继续处理下一批次
    
    # 记录向量化成功率
    success_rate = len(all_vectors) / len(texts) if texts else 0
    print(f"📊 向量化成功率: {success_rate:.2%} ({len(all_vectors)}/{len(texts)})")
    
    if not all_vectors:
        print("❌ 没有成功向量化的文本，无法创建索引")
        return

    # 构建 FAISS 索引
    embedding_dim = len(all_vectors[0])
    index = faiss.IndexFlatL2(embedding_dim)

    print("💾 逐批写入 FAISS 索引 …")
    step = 10_000  # 减小批次大小，避免内存问题
    for i in range(0, len(all_vectors), step):
        batch_vec = np.asarray(all_vectors[i:i+step], dtype=np.float32)
        index.add(batch_vec)
    print(f"✅ 已写入 {index.ntotal} 条向量")

    docstore = InMemoryDocstore({str(i): docs[i] for i in range(len(all_vectors))})
    id_map = {i: str(i) for i in range(len(all_vectors))}

    vectordb = FAISS(
        embedding_function = embeddings_model.embed_documents,
        index=index,
        docstore=docstore,
        index_to_docstore_id=id_map
    )

    os.makedirs(INDEX_PATH, exist_ok=True)
    vectordb.save_local(INDEX_PATH)
    print(f"✅ 向量库保存成功: {INDEX_PATH}")
    print(f"📊 索引统计: 共处理 {len(texts)} 条文本，成功向量化 {len(all_vectors)} 条")
    
    # 返回创建的向量数据库以便可以立即测试
    return vectordb

def test():
    """测试数据库中评论数量"""
    sql = """
        SELECT COUNT(*) FROM reviews r
        JOIN listings l ON l.id = r.listing_id
        WHERE r.comments IS NOT NULL AND r.comments != ''
    """
    return execute_query(sql)

@lru_cache(maxsize=1)
def get_test_vectordb() -> FAISS:
    """
    加载测试向量索引
    """
    print("⚡ 加载测试索引...")
    try:
        # 确保嵌入模型已加载
        load_embeddings()
        embeddings = get_embeddings()
        
        if embeddings is None:
            raise ValueError("嵌入模型加载失败")
            
        vectordb = FAISS.load_local(
            INDEX_PATH,
            embeddings=embeddings,
            allow_dangerous_deserialization=True
        )
        print("✅ 测试索引加载成功")
        return vectordb
    except Exception as e:
        print(f"❌ 测试索引加载失败: {e}")
        raise

def simple_rag_query(query_text, k=3):
    """
    简单的RAG工作流测试函数
    
    Args:
        query_text: 用户查询文本
        k: 返回的相关文档数量
        
    Returns:
        dict: 包含查询结果的字典
    """
    print(f"📝 处理查询: '{query_text}'")
    
    try:
        # 步骤1: 加载向量数据库
        print("步骤1: 加载向量数据库")
        vectordb = get_test_vectordb()
        
        # 步骤2: 将查询转化为向量并搜索相似文档
        print("步骤2: 向量搜索相似文档")
        docs = vectordb.similarity_search(query_text, k=k)
        
        # 步骤3: 提取和格式化结果
        print("步骤3: 提取结果")
        results = []
        for i, doc in enumerate(docs):
            results.append({
                "rank": i + 1,
                "content": doc.page_content,
                "metadata": doc.metadata,
                "listing_id": doc.metadata["listing_id"]
            })
            
        print(f"✅ 查询成功, 找到 {len(results)} 个相关文档")
        
        # 打印结果预览
        for i, res in enumerate(results):
            print(f"\n结果 #{i+1} (listing_id: {res['listing_id']}):")
            print(f"- 内容: {res['content'][:100]}...")
            
        return {
            "query": query_text,
            "results": results,
            "total_found": len(results)
        }
        
    except Exception as e:
        print(f"❌ 查询失败: {e}")
        return {
            "query": query_text,
            "error": str(e),
            "results": []
        }

# ✅ 主执行入口
if __name__ == "__main__":
    with app.app_context():
        # 1. 构建小型测试索引
        print("\n===== 步骤1: 构建小型测试索引 =====")
        vectordb = build(test_mode=True)
        
        # 2. 测试查询功能
        print("\n===== 步骤2: 测试RAG查询 =====")
        if input("是否进行测试查询? (y/n): ").lower() == 'y':
            test_queries = [
                "clean and comfortable apartment",
                "close to public transportation",
                "great host and communication"
            ]
            
            for query in test_queries:
                result = simple_rag_query(query)
                print(f"\n查询: '{query}'")
                print(f"找到 {len(result['results'])} 个相关结果")
                
            # 允许用户输入自定义查询
            user_query = input("\n请输入自定义查询 (或按Enter跳过): ")
            if user_query:
                simple_rag_query(user_query)

