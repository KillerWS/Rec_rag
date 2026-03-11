# load_embedding_model_api.py
from langchain_google_genai import GoogleGenerativeAIEmbeddings
import os
from google import genai
from google.genai import types
import numpy as np

# 嵌入模型全局变量
_embeddings = None
_dimension = 1536  # 默认维度
_client = None
_task_type = None  # 任务类型

# 任务类型常量
TASK_SEMANTIC_SIMILARITY = "SEMANTIC_SIMILARITY"  # 语义相似度评估
TASK_CLASSIFICATION = "CLASSIFICATION"  # 文本分类
TASK_CLUSTERING = "CLUSTERING"  # 文本聚类
TASK_RETRIEVAL_DOCUMENT = "RETRIEVAL_DOCUMENT"  # 文档索引（建库时使用）
TASK_RETRIEVAL_QUERY = "RETRIEVAL_QUERY"  # 查询检索（查询时使用）
TASK_CODE_RETRIEVAL_QUERY = "CODE_RETRIEVAL_QUERY"  # 代码检索查询
TASK_QUESTION_ANSWERING = "QUESTION_ANSWERING"  # 问答系统
TASK_FACT_VERIFICATION = "FACT_VERIFICATION"  # 事实验证

def load_embeddings(task_type=None, dimension=1536):
    """🔹 初始化嵌入模型（只调用一次）
    
    Args:
        task_type (str, optional): 嵌入任务类型，可选值包括：
            - SEMANTIC_SIMILARITY: 文本相似度评估
            - CLASSIFICATION: 文本分类
            - CLUSTERING: 文本聚类
            - RETRIEVAL_DOCUMENT: 文档检索优化（建库时使用）
            - RETRIEVAL_QUERY: 查询检索优化（查询时使用）
            - CODE_RETRIEVAL_QUERY: 代码检索查询
            - QUESTION_ANSWERING: 问答系统
            - FACT_VERIFICATION: 事实验证
        dimension (int, optional): 嵌入向量维度，推荐值: 768, 1536, 3072
    """
    global _embeddings, _dimension, _client, _task_type
    _dimension = dimension
    _task_type = task_type  # 保存任务类型到全局变量
    
    # 从环境变量获取API密钥
    api_key = os.environ.get("GOOGLE_API_KEY")
    
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY not set. Please create a .env file and set GOOGLE_API_KEY=YOUR_KEY")
        
    try:
        # 创建API客户端
        _client = genai.Client(api_key=api_key)
        
        # 使用原生genai方式直接进行嵌入
        def _embed_query(text):
            config = types.EmbedContentConfig()
            if task_type:
                config.task_type = task_type
            if dimension != 3072:  # 只有非默认维度时才设置
                config.output_dimensionality = dimension
            
            result = _client.embed_content(
                model="text-embedding-004",  # 使用正确的模型名称
                contents=text,
                config=config
            )
            # 返回嵌入向量
            return result.embeddings[0].values
            
        # 初始化Gemini嵌入模型 - 仍保留，为兼容其他代码
        _embeddings = GoogleGenerativeAIEmbeddings(
            model="models/embedding-004",  # LangChain使用的格式
            google_api_key=api_key
        )
        
        # 替换内部嵌入方法，确保正确设置维度
        _embeddings._embed_query = _embed_query
        
        print(f"✅ Gemini嵌入模型加载成功 (维度: {dimension}, 任务类型: {task_type or '默认'})")
        return True
    except Exception as e:
        print(f"❌ Gemini嵌入模型加载失败: {e}")
        return False

def get_task_type():
    """获取当前任务类型"""
    return _task_type

def set_task_type(task_type):
    """修改当前任务类型"""
    global _task_type
    _task_type = task_type
    print(f"✅ 任务类型已更新为: {task_type}")

def get_embeddings():
    """🔹 获取嵌入模型实例"""
    return _embeddings

def get_client():
    """🔹 获取API客户端实例"""
    return _client

def normalize_embedding(embedding):
    """对嵌入向量进行归一化"""
    embedding_np = np.array(embedding)
    norm = np.linalg.norm(embedding_np)
    if norm > 0:  # 避免除零错误
        normalized = embedding_np / norm
        return normalized.tolist()
    return embedding  # 如果是零向量，返回原始向量

def embed_query(text, task_type=None):
    """生成并返回归一化的嵌入向量
    
    Args:
        text: 要嵌入的文本
        task_type: 可选，为此查询指定任务类型（覆盖全局设置）
    """
    if _embeddings is None or _client is None:
        print("❌ 嵌入模型尚未加载，请先调用load_embeddings()")
        return None
    
    try:
        # 确定使用的任务类型
        current_task = task_type if task_type else _task_type
        
        # 创建配置
        config = types.EmbedContentConfig()
        if current_task:
            config.task_type = current_task
        if _dimension != 3072:
            config.output_dimensionality = _dimension
            
        # 调用API
        result = _client.embed_content(
            model="text-embedding-004",
            contents=text,
            config=config
        )
        
        # 返回嵌入向量
        embedding = result.embeddings[0].values
        return normalize_embedding(embedding)
    except Exception as e:
        print(f"❌ 嵌入生成失败: {e}")
        return None

def embed_documents(texts, task_type=None):
    """批量生成并返回归一化的嵌入向量
    
    Args:
        texts: 要嵌入的文本列表
        task_type: 可选，为此批量嵌入指定任务类型（覆盖全局设置）
    """
    if _embeddings is None or _client is None:
        print("❌ 嵌入模型尚未加载，请先调用load_embeddings()")
        return None
    
    try:
        # 确定使用的任务类型
        current_task = task_type if task_type else _task_type
        
        # 创建配置
        config = types.EmbedContentConfig()
        if current_task:
            config.task_type = current_task
        if _dimension != 3072:
            config.output_dimensionality = _dimension
        
        # 调用批量API
        result = _client.embed_content(
            model="text-embedding-004",
            contents=texts,
            config=config
        )
        
        # 处理结果
        embeddings = [emb.values for emb in result.embeddings]
        return [normalize_embedding(emb) for emb in embeddings]
    except Exception as e:
        print(f"❌ 批量嵌入生成失败: {e}")
        # 回退到单个处理
        results = []
        for text in texts:
            results.append(embed_query(text, task_type=current_task))
        return results

def test_connectivity(text="Hello, world!"):
    """测试与Gemini API的连接并验证嵌入生成是否正常"""
    if _embeddings is None:
        print("❌ 嵌入模型尚未加载，请先调用load_embeddings()")
        return False
    
    try:
        embedding = embed_query(text)
        if embedding:
            print(f"✅ 连接测试成功！生成的嵌入向量维度: {len(embedding)}")
            print(f"✅ 嵌入向量示例 (前5个值): {embedding[:5]}")
            
            # 验证向量是否已归一化
            norm = np.linalg.norm(np.array(embedding))
            print(f"✅ 向量范数: {norm:.6f} (应接近1.0)")
            return True
        else:
            return False
    except Exception as e:
        print(f"❌ 连接测试失败: {e}")
        return False

def similarity(text1, text2, task_type=None):
    """计算两段文本的余弦相似度
    
    Args:
        text1: 第一段文本
        text2: 第二段文本
        task_type: 可选，为此相似度计算指定任务类型（推荐SEMANTIC_SIMILARITY）
    """
    if _embeddings is None:
        print("❌ 嵌入模型尚未加载，请先调用load_embeddings()")
        return None
    
    try:
        # 默认使用SEMANTIC_SIMILARITY任务类型计算相似度
        if not task_type and not _task_type:
            task_type = TASK_SEMANTIC_SIMILARITY
            
        emb1 = np.array(embed_query(text1, task_type=task_type))
        emb2 = np.array(embed_query(text2, task_type=task_type))
        
        # 计算余弦相似度
        cos_sim = np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2))
        return float(cos_sim)  # 确保返回Python标量
    except Exception as e:
        print(f"❌ 相似度计算失败: {e}")
        return None


# 以下是测试代码，与核心功能分开
def run_simple_test():
    """运行简单的API测试"""
    print("===== 运行简单API测试 =====")
    try:
        # 配置API密钥
        api_key = os.environ.get("GOOGLE_API_KEY")
        
        # 创建客户端并测试嵌入
        client = genai.Client(api_key=api_key)
        text = "Hello World!"
        result = client.embed_content(
            model="text-embedding-004",
            contents=text,
            config=types.EmbedContentConfig(output_dimensionality=10),
        )
        print(f"测试嵌入向量维度: {len(result.embeddings[0].values)}")
        print(f"测试嵌入向量值: {result.embeddings[0].values}")
        return True
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False

def run_similarity_test():
    """运行文本相似度测试"""
    print("===== 运行文本相似度测试 =====")
    
    # 测试数据
    texts = [
        "什么是人生的意义？", 
        "人类存在的目的是什么？", 
        "如何烤蛋糕？"
    ]
    
    try:
        # 确保使用SEMANTIC_SIMILARITY任务类型
        set_task_type(TASK_SEMANTIC_SIMILARITY)
        
        # 获取嵌入
        embeddings = embed_documents(texts)
        if not embeddings:
            return False
            
        # 转换为numpy数组
        embeddings_matrix = np.array(embeddings)
        
        # 计算相似度矩阵
        from sklearn.metrics.pairwise import cosine_similarity
        similarity_matrix = cosine_similarity(embeddings_matrix)
        
        # 打印结果
        for i, text1 in enumerate(texts):
            for j in range(i + 1, len(texts)):
                text2 = texts[j]
                similarity = similarity_matrix[i, j]
                print(f"'{text1}' 与 '{text2}' 的相似度: {similarity:.4f}")
                
        return True
    except Exception as e:
        print(f"❌ 相似度测试失败: {e}")
        return False

def run_retrieval_test():
    """运行文档检索测试 - 展示不同任务类型的用法"""
    print("===== 运行文档检索测试 =====")
    
    try:
        # 1. 准备文档集合（通常会存入向量数据库）
        documents = [
            "柏林是德国的首都和最大城市",
            "纽约是美国最大的城市，但不是首都",
            "东京是日本的首都和最大城市",
            "巴黎是法国的首都和最大城市"
        ]
        
        # 2. 使用RETRIEVAL_DOCUMENT任务类型为文档生成嵌入（建库阶段）
        print("生成文档嵌入 (使用RETRIEVAL_DOCUMENT任务类型)...")
        doc_embeddings = embed_documents(documents, task_type=TASK_RETRIEVAL_DOCUMENT)
        
        # 3. 准备查询
        query = "德国的首都是哪里？"
        
        # 4. 使用RETRIEVAL_QUERY任务类型为查询生成嵌入（查询阶段）
        print(f"生成查询嵌入 (使用RETRIEVAL_QUERY任务类型)...")
        query_embedding = embed_query(query, task_type=TASK_RETRIEVAL_QUERY)
        
        # 5. 计算相似度并排序
        print("计算查询与文档的相似度...")
        similarities = []
        for i, doc_embedding in enumerate(doc_embeddings):
            # 计算余弦相似度
            doc_embed_np = np.array(doc_embedding)
            query_embed_np = np.array(query_embedding)
            similarity = np.dot(doc_embed_np, query_embed_np) / (np.linalg.norm(doc_embed_np) * np.linalg.norm(query_embed_np))
            similarities.append((i, similarity, documents[i]))
        
        # 6. 排序并返回结果
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        # 7. 打印结果
        print("\n检索结果 (按相关性排序):")
        for i, similarity, document in similarities:
            print(f"相似度: {similarity:.4f} - 文档: {document}")
            
        return True
    except Exception as e:
        print(f"❌ 检索测试失败: {e}")
        return False

if __name__ == "__main__":
    # 运行独立的API测试
    if run_simple_test():
        print("\n✅ API测试成功，继续进行完整功能测试...\n")
        
        # 初始化嵌入模型
        if load_embeddings(dimension=1536):
            # 测试连接
            test_connectivity()
            
            # 运行相似度测试
            run_similarity_test()
            
            # 运行检索测试
            run_retrieval_test()
    else:
        print("\n❌ API测试失败，请检查环境配置和API密钥") 