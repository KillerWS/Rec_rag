# build_global_faiss.py
import sys
import os
from pathlib import Path
from flask import Flask
from tqdm import tqdm
import numpy as np
import json
import time
from typing import List, Dict, Any, Optional, Generator, Tuple

# 添加项目根路径
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent.parent.parent
sys.path.insert(0, str(project_root))

# 导入数据库工具
from db import init_db, execute_query

# 导入Gemini API嵌入模型
from load_embedding_model_api import get_embeddings, load_embeddings, TASK_RETRIEVAL_DOCUMENT, TASK_RETRIEVAL_QUERY

# 创建 Flask app 实例并初始化数据库
app = Flask(__name__)
init_db(app)

from langchain.schema import Document
from langchain_community.vectorstores import FAISS
from functools import lru_cache

# 输出路径配置 - 这里修改为和rag_chat.py兼容的路径
GLOBAL_FAISS_DIR = str(project_root / "faiss_indexes" / "global_reviews")

# 显示格式化的时间
def format_time(seconds):
    """将秒数格式化为人类可读的时间格式"""
    if seconds < 60:
        return f"{seconds:.1f}秒"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}分钟"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}小时"

def get_total_review_count():
    """获取数据库中符合条件的评论总数"""
    count_sql = """
        SELECT COUNT(*) as total_count
        FROM reviews r
        JOIN listings l ON l.id = r.listing_id
        WHERE r.comments IS NOT NULL AND r.comments != ''
    """
    count_df = execute_query(count_sql)
    return count_df['total_count'].iloc[0] if not count_df.empty else 0

def load_reviews_batch(batch_size: int = 5000, offset: int = 0, test_mode: bool = False):
    """分批次从数据库加载评论
    
    Args:
        batch_size: 每批查询的记录数
        offset: 起始偏移量
        test_mode: 测试模式下只查询少量数据
        
    Returns:
        查询结果DataFrame
    """
    # 限制测试模式的批次大小
    if test_mode:
        batch_size = min(batch_size, 1000)
    
    # 查询SQL
    sql = f"""
        SELECT r.id AS review_id,
               r.comments AS text,
               r.listing_id,
               l.neighbourhood_group_cleansed AS neighbourhood_group,
               l.neighbourhood_cleansed AS neighbourhood,
               l.price,
               l.room_type,
               l.number_of_reviews,
               CASE 
                 WHEN l.price BETWEEN 0 AND 40 THEN '0-40'
                 WHEN l.price BETWEEN 40 AND 80 THEN '40-80'
                 WHEN l.price BETWEEN 80 AND 120 THEN '80-120'
                 WHEN l.price BETWEEN 120 AND 160 THEN '120-160'
                 WHEN l.price BETWEEN 160 AND 200 THEN '160-200'
                 ELSE '200+' 
               END AS price_bucket
        FROM reviews r
        JOIN listings l ON l.id = r.listing_id
        WHERE r.comments IS NOT NULL AND r.comments != ''
        ORDER BY r.listing_id, LENGTH(r.comments) DESC
        LIMIT {batch_size} OFFSET {offset}
    """
    
    print(f"🔄 查询批次: OFFSET {offset}, LIMIT {batch_size}")
    start_time = time.time()
    df = execute_query(sql)
    query_time = time.time() - start_time
    print(f"✅ 查询完成，耗时: {format_time(query_time)}，获取 {len(df)} 条记录")
    
    return df

def batch_iterator(total_records: int, batch_size: int = 5000, test_mode: bool = False) -> Generator[Tuple[int, int], None, None]:
    """生成批次迭代器
    
    Args:
        total_records: 总记录数
        batch_size: 每批大小
        test_mode: 测试模式
        
    Yields:
        (offset, current_batch_size) 元组
    """
    if test_mode:
        # 测试模式下只处理前3个批次
        total_batches = 3
        total_to_process = batch_size * total_batches
        print(f"🧪 测试模式: 只处理前 {total_to_process} 条记录 ({total_batches} 个批次)")
    else:
        total_to_process = total_records
        total_batches = (total_to_process + batch_size - 1) // batch_size
        print(f"📊 完整模式: 处理全部 {total_records} 条记录 ({total_batches} 个批次)")
    
    for i in range(0, total_to_process, batch_size):
        current_batch = min(batch_size, total_to_process - i)
        yield i, current_batch

def process_documents(df, vectordb_builder=None) -> Tuple[List[Document], List[str], FAISS]:
    """处理一批数据，构建文档并向量化
    
    Args:
        df: 数据批次
        vectordb_builder: 用于添加向量的FAISS构建器
        
    Returns:
        (文档列表, 文本列表, 更新后的向量数据库)
    """
    # 构建文档对象并提取文本
    docs = []
    texts = []
    
    for row in tqdm(df.itertuples(), total=len(df), desc="📝 文档构建", ncols=100, leave=False):
        # 处理价格字符串
        price_str = str(row.price) if row.price is not None else "0"
        price_cleaned = price_str.replace('$', '').replace(',', '')
        try:
            price_float = float(price_cleaned)
        except ValueError:
            price_float = 0.0
            
        # 构建元数据
        meta = {
            "review_id": row.review_id,
            "listing_id": row.listing_id,
            "neighbourhood_group": row.neighbourhood_group,
            "neighbourhood": row.neighbourhood,
            "price": price_float,
            "room_type": row.room_type,
            "n_reviews": row.number_of_reviews,
            "price_bucket": getattr(row, "price_bucket", "unknown")
        }
        content = row.text.strip()
        if content:
            docs.append(Document(page_content=content, metadata=meta))
            texts.append(content)
    
    # 确保有文档需要处理
    if not texts:
        return docs, texts, vectordb_builder
        
    # 获取嵌入模型
    embeddings_model = get_embeddings()
    if embeddings_model is None:
        print("❌ 嵌入模型未初始化")
        return docs, texts, vectordb_builder
        
    # 批量嵌入文本
    embedding_batch_size = 32  # API调用的批量大小
    all_vectors = []
    all_ids = []
    
    print(f"🔢 向量化 {len(texts)} 条文本...")
    embed_start = time.time()
    
    for i in tqdm(range(0, len(texts), embedding_batch_size), desc="🔢 API批次", ncols=100, leave=False):
        batch = texts[i:i + embedding_batch_size]
        try:
            vecs = embeddings_model.embed_documents(batch)
            all_vectors.extend(vecs)
            all_ids.extend(range(i, min(i + len(vecs), len(texts))))
        except Exception as e:
            print(f"❌ 批次嵌入失败: {e}")
    
    embed_time = time.time() - embed_start
    print(f"✅ 向量化完成，耗时: {format_time(embed_time)}")
    print(f"📊 成功率: {len(all_vectors)}/{len(texts)} ({len(all_vectors)/len(texts):.1%})")
    
    # 只保留成功向量化的文档
    successful_docs = [docs[i] for i in all_ids]
    
    # 更新或创建向量数据库
    if vectordb_builder is None:
        print("🏗️ 创建新的FAISS索引...")
        vectordb_builder = FAISS.from_documents(successful_docs, embeddings_model)
        print(f"✅ 创建了包含 {vectordb_builder.index.ntotal} 个向量的新索引")
    else:
        print(f"🔄 更新现有索引，当前有 {vectordb_builder.index.ntotal} 个向量")
        vectordb_builder.add_documents(successful_docs)
        print(f"✅ 索引已更新，现在包含 {vectordb_builder.index.ntotal} 个向量")
    
    return successful_docs, texts, vectordb_builder

def build_global_index(test_mode: bool = False, db_batch_size: int = 5000, embedding_batch_size: int = 32, resume_from: Optional[int] = None):
    """分批构建全局向量索引
    
    Args:
        test_mode: 测试模式，只处理少量数据
        db_batch_size: 数据库查询的批次大小
        embedding_batch_size: API嵌入的批次大小
        resume_from: 从哪个批次开始恢复，如果为None则从头开始
    """
    global_start_time = time.time()
    
    # 获取总记录数
    print("🔢 统计数据库中的评论数量...")
    total_reviews = get_total_review_count()
    print(f"📊 数据库中共有 {total_reviews} 条评论")
    
    # 确保嵌入模型已加载
    print(f"⚙️ 加载嵌入模型 (任务类型: TASK_RETRIEVAL_DOCUMENT, 维度: 1536)...")
    load_embeddings(task_type=TASK_RETRIEVAL_DOCUMENT, dimension=1536)
    
    # 批次处理
    vectordb = None
    total_processed = 0
    total_vectorized = 0
    
    # 创建批次迭代器
    batch_iter = batch_iterator(total_reviews, db_batch_size, test_mode)
    
    # 创建总进度条
    if test_mode:
        total_to_process = min(db_batch_size * 3, total_reviews)
    else:
        total_to_process = total_reviews
    
    progress_bar = tqdm(total=total_to_process, desc="🔄 总体进度", position=0, ncols=100)
    
    # 处理每个批次
    batch_number = resume_from if resume_from else 0
    for offset, current_batch_size in batch_iter:
        batch_number += 1
        batch_start_time = time.time()
        
        print(f"\n==== 批次 #{batch_number} - 偏移量: {offset} ====")
        
        # 加载批次数据
        df = load_reviews_batch(current_batch_size, offset, test_mode)
        if df.empty:
            print("⚠️ 未查询到数据，跳过此批次")
            continue
        
        # 处理批次
        docs, texts, vectordb = process_documents(df, vectordb)
        
        # 更新统计信息 - 修复这里的属性名
        current_processed = len(texts)
        current_vectorized = vectordb.index.ntotal - total_vectorized if vectordb else 0
        total_processed += current_processed
        total_vectorized = vectordb.index.ntotal if vectordb else 0
        
        # 更新进度条
        progress_bar.update(current_processed)
        
        # 显示批次统计
        batch_time = time.time() - batch_start_time
        print(f"📊 批次 #{batch_number} 统计:")
        print(f"  - 处理文档: {current_processed} 条")
        print(f"  - 向量化成功: {current_vectorized} 个向量")
        print(f"  - 批次耗时: {format_time(batch_time)}")
        print(f"  - 总进度: {total_processed}/{total_to_process} ({total_processed/total_to_process:.1%})")
        
        # 保存中间结果
        if vectordb and batch_number % 5 == 0:
            print(f"💾 保存中间结果 (批次 #{batch_number})...")
            checkpoint_dir = f"{GLOBAL_FAISS_DIR}_checkpoint_{batch_number}"
            os.makedirs(checkpoint_dir, exist_ok=True)
            vectordb.save_local(checkpoint_dir)
            print(f"✅ 中间结果已保存到: {checkpoint_dir}")
        
        # 测试模式下限制批次数
        if test_mode and batch_number >= 3:
            print("🧪 测试模式已完成指定批次数，结束处理")
            break
    
    # 关闭进度条
    progress_bar.close()
    
    # 保存最终结果
    if vectordb:
        print("\n💾 保存最终向量库...")
        os.makedirs(GLOBAL_FAISS_DIR, exist_ok=True)
        vectordb.save_local(GLOBAL_FAISS_DIR)
        
        # 保存构建信息
        total_time = time.time() - global_start_time
        build_info = {
            "total_documents_processed": total_processed,
            "vectorized_documents": total_vectorized,
            "success_rate": total_vectorized / total_processed if total_processed > 0 else 0,
            "test_mode": test_mode,
            "timestamp": str(time.time()),
            "task_type": "RETRIEVAL_DOCUMENT",
            "dimension": 1536,
            "processing_time_seconds": total_time,
            "db_batch_size": db_batch_size,
            "embedding_batch_size": embedding_batch_size,
            "total_batches_processed": batch_number
        }
        
        with open(os.path.join(GLOBAL_FAISS_DIR, "build_info.json"), "w") as f:
            json.dump(build_info, f, indent=2)
        
        print(f"✅ 全局向量库保存成功: {GLOBAL_FAISS_DIR}")
        print(f"📊 最终统计:")
        print(f"  - 总处理文档: {total_processed} 条")
        print(f"  - 总向量化文档: {total_vectorized} 条")
        print(f"  - 总成功率: {total_vectorized/total_processed:.1%}")
        print(f"  - 总处理时间: {format_time(total_time)}")
    else:
        print("❌ 处理失败，未能创建向量库")
    
    return vectordb

@lru_cache(maxsize=1)
def get_global_vectordb() -> FAISS:
    """
    加载全局向量库，与rag_chat.py中的同名函数保持一致
    """
    print("⚡ 加载全局向量库...")
    try:
        # 确保嵌入模型已加载，注意查询时应使用TASK_RETRIEVAL_QUERY任务类型
        load_embeddings(task_type=TASK_RETRIEVAL_QUERY, dimension=1536)
        embeddings = get_embeddings()
        
        if embeddings is None:
            raise ValueError("嵌入模型加载失败")
            
        vectordb = FAISS.load_local(
            GLOBAL_FAISS_DIR,
            embeddings=embeddings,
            allow_dangerous_deserialization=True
        )
        print(f"✅ 全局向量库加载成功，包含 {vectordb.index.ntotal} 个向量")
        return vectordb
    except Exception as e:
        print(f"❌ 全局向量库加载失败: {e}")
        raise

def test_metadata_filter(listing_ids: List[int] = None, query: str = "clean and nice apartment"):
    """
    测试元数据过滤功能
    
    Args:
        listing_ids: 要过滤的房源ID列表，如果不提供则使用默认列表
        query: 查询文本
    """
    print("\n===== 测试元数据过滤 =====")
    
    # 如果没有提供listing_ids，使用一个默认列表
    if listing_ids is None or not listing_ids:
        # 从数据库获取一些热门listing_ids
        sql = """
        SELECT id FROM listings 
        ORDER BY number_of_reviews DESC 
        LIMIT 10
        """
        df = execute_query(sql)
        listing_ids = df['id'].tolist() if not df.empty else []
        
        if not listing_ids:
            print("❌ 无法获取房源ID")
            return
    
    try:
        # 确保使用TASK_RETRIEVAL_QUERY进行搜索
        load_embeddings(task_type=TASK_RETRIEVAL_QUERY, dimension=1536)
        
        # 加载向量库
        vectordb = get_global_vectordb()
        
        # 创建检索器，使用与rag_chat.py相同的过滤方式
        print(f"🔍 使用listing_ids过滤: {listing_ids[:5]}...")
        retriever = vectordb.as_retriever(
            search_kwargs={
                "k": 5,
                "fetch_k": 50,  # 先获取更多结果，然后过滤
                "filter": {"listing_id": {"$in": listing_ids}}
            }
        )
        
        # 执行查询
        print(f"🔍 查询: '{query}'")
        docs = retriever.get_relevant_documents(query)
        
        # 显示结果
        print(f"✅ 查询成功, 找到 {len(docs)} 个相关文档")
        
        # 验证所有返回的文档确实包含在过滤条件中
        filtered_correctly = all(doc.metadata["listing_id"] in listing_ids for doc in docs)
        print(f"✅ 元数据过滤正常工作: {filtered_correctly}")
        
        # 打印一些结果
        for i, doc in enumerate(docs[:3]):  # 只显示前3个
            print(f"\n结果 #{i+1} (listing_id: {doc.metadata['listing_id']}):")
            print(f"- 内容: {doc.page_content[:100]}...")
            print(f"- 元数据: {doc.metadata}")
        
        return docs
    
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return None

def compare_with_unfiltered(query: str = "clean and nice apartment", k: int = 5):
    """
    比较有过滤和无过滤的查询结果差异
    """
    try:
        # 确保使用TASK_RETRIEVAL_QUERY进行搜索
        load_embeddings(task_type=TASK_RETRIEVAL_QUERY, dimension=1536)
        
        vectordb = get_global_vectordb()
        
        # 无过滤查询
        print("\n🔍 无过滤查询...")
        unfiltered_docs = vectordb.similarity_search(query, k=k)
        
        # 获取一些房源ID进行过滤
        listing_ids = [doc.metadata["listing_id"] for doc in unfiltered_docs]
        
        # 有过滤查询
        print("\n🔍 有过滤查询...")
        retriever = vectordb.as_retriever(
            search_kwargs={
                "k": k,
                "filter": {"listing_id": {"$in": listing_ids[:2]}}  # 只用前两个ID进行过滤
            }
        )
        filtered_docs = retriever.get_relevant_documents(query)
        
        # 比较结果
        print(f"\n📊 无过滤查询结果: {len(unfiltered_docs)} 个文档")
        print(f"📊 有过滤查询结果: {len(filtered_docs)} 个文档")
        
        print("\n无过滤查询找到的房源IDs:")
        print([doc.metadata["listing_id"] for doc in unfiltered_docs])
        
        print("\n有过滤查询找到的房源IDs:")
        print([doc.metadata["listing_id"] for doc in filtered_docs])
        
        return {
            "unfiltered": unfiltered_docs,
            "filtered": filtered_docs
        }
    
    except Exception as e:
        print(f"❌ 比较失败: {e}")
        return None

# ✅ 主执行入口
if __name__ == "__main__":
    with app.app_context():
        print("==== 全局向量索引构建工具 ====")
        print("1. 构建测试索引 (少量数据)")
        print("2. 构建完整索引 (全量数据)")
        print("3. 从检查点恢复构建")
        print("4. 测试元数据过滤")
        print("5. 比较过滤与非过滤结果")
        print("6. 退出")
        
        choice = input("\n请选择操作 (1-6): ")
        
        if choice == "1":
            # 构建测试索引
            build_global_index(test_mode=True, db_batch_size=1000, embedding_batch_size=32)
            
            # 询问是否测试
            if input("\n是否测试刚构建的索引? (y/n): ").lower() == 'y':
                test_metadata_filter()
                
        elif choice == "2":
            # 构建完整索引
            print("\n⚠️ 警告: 构建完整索引将耗费较长时间")
            if input("确定要继续吗? (y/n): ").lower() == 'y':
                db_batch_size = int(input("请输入数据库批次大小 (推荐5000-10000): ") or "5000")
                embedding_batch_size = int(input("请输入API批次大小 (推荐16-32): ") or "16")
                resume = input("是否从检查点恢复? (y/n): ").lower() == 'y'
                resume_batch = None
                if resume:
                    resume_batch = int(input("从哪个批次恢复? (例如: 5): ") or "0")
                build_global_index(test_mode=False, db_batch_size=db_batch_size, 
                                   embedding_batch_size=embedding_batch_size, 
                                   resume_from=resume_batch)
                
        elif choice == "3":
            # 从检查点恢复构建
            resume_batch = int(input("请输入要恢复的检查点批次号: "))
            db_batch_size = int(input("请输入数据库批次大小 (推荐5000-10000): ") or "5000")
            embedding_batch_size = int(input("请输入API批次大小 (推荐32-64): ") or "32")
            build_global_index(test_mode=False, db_batch_size=db_batch_size, 
                             embedding_batch_size=embedding_batch_size, resume_from=resume_batch)
                
        elif choice == "4":
            # 测试元数据过滤
            test_metadata_filter()
            
        elif choice == "5":
            # 比较过滤与非过滤结果
            query = input("\n请输入查询文本 (默认: clean and nice apartment): ") or "clean and nice apartment"
            compare_with_unfiltered(query)
            
        else:
            print("已退出")