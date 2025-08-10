#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
RAG测试脚本 - 用于测试已构建的全局向量库和嵌入模型

这个脚本提供了一系列测试函数，用于验证:
1. 全局向量库的加载与查询
2. 文本嵌入的归一化效果
3. 语义相似度计算
4. 元数据过滤查询

通过这些测试可以验证RAG管道各个组件的正确性和性能。
"""

import sys
import os
import time
from pathlib import Path
import json
from typing import List, Dict, Any, Optional, Union

# 添加项目根路径
current_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(current_dir))

# 导入数据库工具
from db import init_db, execute_query
from flask import Flask

# 导入嵌入模型 - 注意这里使用了包含归一化功能的API
from load_embedding_model_api import (
    load_embeddings, 
    get_embeddings,
    normalize_embedding,  # 这是新添加的归一化函数
    TASK_RETRIEVAL_QUERY, 
    TASK_SEMANTIC_SIMILARITY
)

# 导入向量库
from langchain_community.vectorstores import FAISS
from langchain.schema import Document

# 设置Flask应用和数据库连接
app = Flask(__name__)
init_db(app)

# 全局FAISS索引路径
GLOBAL_FAISS_DIR = os.path.join(current_dir, "faiss_indexes", "global_reviews")

def format_time(seconds: float) -> str:
    """
    将秒数格式化为人类可读的时间格式（秒/分钟/小时）
    
    Args:
        seconds: 需要格式化的秒数
        
    Returns:
        str: 格式化后的时间字符串，如"1.5秒"、"2.3分钟"或"1.2小时"
    """
    if seconds < 60:
        return f"{seconds:.1f}秒"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}分钟"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}小时"

def load_global_vectordb() -> FAISS:
    """
    加载全局向量库，并计算加载时间
    
    加载过程:
    1. 初始化嵌入模型，使用TASK_RETRIEVAL_QUERY任务类型
    2. 验证向量库文件存在
    3. 加载FAISS索引并返回
    
    Returns:
        FAISS: 加载成功的FAISS向量数据库实例
        
    Raises:
        ValueError: 嵌入模型加载失败时抛出
        FileNotFoundError: 向量库文件未找到时抛出
        Exception: 其他加载错误
    """
    print("⚡ 加载全局向量库...")
    start_time = time.time()
    
    try:
        # 确保嵌入模型已加载，注意查询时应使用TASK_RETRIEVAL_QUERY任务类型
        print("🔄 加载嵌入模型...")
        load_embeddings(task_type=TASK_RETRIEVAL_QUERY, dimension=1536)
        embeddings = get_embeddings()
        
        if embeddings is None:
            raise ValueError("嵌入模型加载失败")
        
        # 检查向量库是否存在
        if not os.path.exists(GLOBAL_FAISS_DIR):
            raise FileNotFoundError(f"全局向量库未找到: {GLOBAL_FAISS_DIR}")
        
        # 加载向量库
        vectordb = FAISS.load_local(
            GLOBAL_FAISS_DIR,
            embeddings=embeddings,
            allow_dangerous_deserialization=True
        )
        
        load_time = time.time() - start_time
        print(f"✅ 全局向量库加载成功，包含 {vectordb.index.ntotal} 个向量")
        print(f"⏱️ 加载时间: {format_time(load_time)}")
        
        return vectordb
    except Exception as e:
        print(f"❌ 全局向量库加载失败: {e}")
        raise

def get_relevant_listing_ids(limit: int = 10) -> List[int]:
    """
    从数据库获取热门房源ID（按评论数排序）
    
    Args:
        limit: 要获取的房源数量上限，默认为10
        
    Returns:
        List[int]: 房源ID列表，按评论数降序排列
        如果查询失败或无结果，则返回空列表
    """
    sql = f"""
    SELECT id 
    FROM listings 
    ORDER BY number_of_reviews DESC 
    LIMIT {limit}
    """
    df = execute_query(sql)
    ids = df['id'].tolist() if not df.empty else []
    print(f"📊 获取了 {len(ids)} 个热门房源ID")
    return ids

def get_listing_by_id(listing_id: int) -> Optional[Dict[str, Any]]:
    """
    根据ID获取单个房源的详细信息
    
    Args:
        listing_id: 要查询的房源ID
        
    Returns:
        Dict[str, Any]: 包含房源详细信息的字典，包括名称、描述、位置、类型、价格等
        如果查询失败或房源不存在，则返回None
    """
    sql = f"""
    SELECT id, name, description, neighbourhood_cleansed, 
           neighbourhood_group_cleansed, room_type, price, number_of_reviews
    FROM listings 
    WHERE id = {listing_id}
    """
    df = execute_query(sql)
    if df.empty:
        return None
    return df.iloc[0].to_dict()

def test_simple_query(query_text: str, vectordb: FAISS, listing_ids: Optional[List[int]] = None, k: int = 5) -> List[Document]:
    """
    测试简单查询功能，可选择是否使用元数据过滤
    
    此函数执行以下步骤:
    1. 如果提供listing_ids，使用元数据过滤进行查询
    2. 如果未提供listing_ids，执行全库相似度搜索
    3. 打印查询结果和相关房源详情
    
    Args:
        query_text: 用户查询文本
        vectordb: FAISS向量数据库实例
        listing_ids: 可选的房源ID列表，用于元数据过滤
        k: 返回的相似文档数量，默认为5
        
    Returns:
        List[Document]: 检索到的相关文档列表
        如果查询失败，则返回空列表
    """
    print(f"\n==== 测试查询: '{query_text}' ====")
    start_time = time.time()
    
    try:
        # 如果提供了listing_ids，使用元数据过滤
        if listing_ids:
            print(f"🔍 使用 {len(listing_ids)} 个房源ID进行过滤...")
            retriever = vectordb.as_retriever(
                search_kwargs={
                    "k": k,
                    "fetch_k": k*4,  # 先获取更多，然后过滤
                    "filter": {"listing_id": {"$in": listing_ids}}
                }
            )
            docs = retriever.get_relevant_documents(query_text)
        else:
            # 不过滤，直接搜索
            print("🔍 不使用过滤进行全库搜索...")
            docs = vectordb.similarity_search(query_text, k=k)
        
        query_time = time.time() - start_time
        print(f"✅ 查询成功，耗时: {format_time(query_time)}")
        print(f"📄 找到 {len(docs)} 个相关文档")
        
        # 打印结果
        for i, doc in enumerate(docs):
            listing_id = doc.metadata.get("listing_id", "未知")
            listing_info = get_listing_by_id(listing_id) if listing_id != "未知" else None
            
            print(f"\n--- 文档 #{i+1} ---")
            print(f"房源ID: {listing_id}")
            if listing_info:
                print(f"房源名称: {listing_info.get('name', '未知')}")
                print(f"房源类型: {listing_info.get('room_type', '未知')}")
                print(f"价格: {listing_info.get('price', '未知')}")
                print(f"位置: {listing_info.get('neighbourhood_cleansed', '未知')}, "
                      f"{listing_info.get('neighbourhood_group_cleansed', '未知')}")
            print(f"评论内容: {doc.page_content[:200]}..." if len(doc.page_content) > 200 else doc.page_content)
        
        return docs
    except Exception as e:
        print(f"❌ 查询失败: {e}")
        return []

def test_queries_with_preferences() -> None:
    """
    使用不同偏好和查询条件测试向量检索系统
    
    测试内容:
    1. 带房源ID过滤的查询
    2. 不带过滤的全库查询
    3. 语义相似度计算
    
    该函数将执行一系列预定义的查询，并展示系统的多种用例
    """
    # 测试多个不同的查询
    test_queries = [
        "I need a place with a comfortable bed and quiet neighborhood",
        "Looking for apartments close to public transportation",
        "I want to stay in a place with a nice view",
        "What places have good WiFi for working remotely?",
        "Places with a kitchen where I can cook"
    ]
    
    # 加载向量库
    vectordb = load_global_vectordb()
    
    # 获取热门房源进行过滤测试
    popular_listings = get_relevant_listing_ids(limit=50)
    
    # 测试带过滤的查询
    print("\n==== 带过滤的查询测试 ====")
    for query in test_queries[:2]:  # 只测试前两个查询
        test_simple_query(query, vectordb, listing_ids=popular_listings, k=3)
    
    # 测试不带过滤的查询
    print("\n==== 不带过滤的查询测试 ====")
    for query in test_queries[2:4]:  # 测试另外两个查询
        test_simple_query(query, vectordb, k=3)
    
    # 测试语义相似度功能
    test_semantic_similarity()

def test_semantic_similarity() -> None:
    """
    测试语义相似度功能
    
    此函数使用SEMANTIC_SIMILARITY任务类型加载嵌入模型，
    并计算多对文本之间的语义相似度。测试包括:
    1. 语义相似的文本对
    2. 语义不同的文本对
    
    测试结果会显示每对文本的余弦相似度
    """
    print("\n==== 测试语义相似度 ====")
    
    # 确保使用SEMANTIC_SIMILARITY任务类型
    load_embeddings(task_type=TASK_SEMANTIC_SIMILARITY, dimension=1536)
    
    # 准备测试文本对
    text_pairs = [
        ("I need a quiet place to stay", "Looking for a peaceful accommodation"),
        ("I want a room with a view", "Need accommodation with scenic outlook"),
        ("Looking for cheap accommodation", "I need an expensive luxury apartment"),
        ("Place close to public transport", "Location near restaurants and bars")
    ]
    
    # 测试每对文本的相似度
    for text1, text2 in text_pairs:
        try:
            from load_embedding_model_api import similarity
            sim_score = similarity(text1, text2)
            print(f"文本1: '{text1}'")
            print(f"文本2: '{text2}'")
            print(f"相似度: {sim_score:.4f}")
            print("---")
        except Exception as e:
            print(f"❌ 相似度计算失败: {e}")

def test_normalize_embedding() -> None:
    """
    测试向量归一化功能
    
    此函数验证normalize_embedding函数的效果:
    1. 生成文本的嵌入向量
    2. 计算归一化后向量的L2范数（应接近1.0）
    3. 如果可能，比较原始向量和归一化向量的差异
    
    归一化对于余弦相似度计算非常重要，这个测试验证了其正确性
    """
    print("\n==== 测试向量归一化 ====")
    
    # 确保嵌入模型已加载
    load_embeddings()
    
    # 测试文本
    test_text = "This is a test sentence for embedding normalization"
    
    try:
        # 生成嵌入
        from load_embedding_model_api import embed_query
        embedding = embed_query(test_text)
        
        # 计算范数
        import numpy as np
        norm = np.linalg.norm(np.array(embedding))
        
        print(f"测试文本: '{test_text}'")
        print(f"嵌入维度: {len(embedding)}")
        print(f"嵌入向量的L2范数: {norm:.6f}")
        print(f"是否已归一化: {'是' if abs(norm - 1.0) < 0.0001 else '否'}")
        
        # 测试不使用normalize_embedding的结果
        # 这部分仅用于对比，实际应用中我们总是使用归一化的向量
        if hasattr(get_embeddings(), '_embed_query'):
            original_embed_query = get_embeddings()._embed_query
            raw_embedding = original_embed_query(test_text)
            raw_norm = np.linalg.norm(np.array(raw_embedding))
            print(f"\n未归一化的原始向量范数: {raw_norm:.6f}")
            print(f"归一化效果: {abs(norm - 1.0):.6f} vs {abs(raw_norm - 1.0):.6f}")
    except Exception as e:
        print(f"❌ 归一化测试失败: {e}")

if __name__ == "__main__":
    with app.app_context():
        print("==== RAG检索测试工具 ====")
        print("1. 测试全部功能")
        print("2. 只测试简单查询")
        print("3. 只测试语义相似度")
        print("4. 测试向量归一化")
        print("5. 退出")
        
        choice = input("\n请选择操作 (1-5): ")
        
        if choice == "1":
            test_queries_with_preferences()
            test_normalize_embedding()
        elif choice == "2":
            vectordb = load_global_vectordb()
            query = input("请输入查询文本: ")
            use_filter = input("是否使用过滤? (y/n): ").lower() == 'y'
            listing_ids = get_relevant_listing_ids(50) if use_filter else None
            test_simple_query(query, vectordb, listing_ids=listing_ids)
        elif choice == "3":
            test_semantic_similarity()
        elif choice == "4":
            test_normalize_embedding()
        else:
            print("已退出") 