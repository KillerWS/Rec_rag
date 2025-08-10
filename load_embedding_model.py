# embedding_model.py
from langchain_community.embeddings import HuggingFaceBgeEmbeddings

import os

# ✅ 动态获取当前脚本的绝对路径
current_dir = os.path.dirname(os.path.abspath(__file__))

# ✅ 拼接 reviews.csv 的绝对路径
# _embeddings_path = os.path.join(current_dir, "../models/embedding/BAAI/bge-large-en-v1.5")
_embeddings_path = os.path.join(current_dir, "../models/embedding/BAAI/bge-large-en-v1.5")

# 先用base 因为全局索引是用base embedding的


# 嵌入模型全局变量
_embeddings = None

def load_embeddings():
    """🔹 初始化嵌入模型（只调用一次）"""
    global _embeddings
    try:
        _embeddings = HuggingFaceBgeEmbeddings(
            model_name=_embeddings_path
        )
        print("✅ 嵌入模型加载成功")
    except Exception as e:
        print(f"❌ 嵌入模型加载失败: {e}")

def get_embeddings():
    """🔹 获取嵌入模型实例"""
    return _embeddings
