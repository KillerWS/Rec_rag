# embedding_model.py
import os
from functools import lru_cache
import torch
from sentence_transformers import SentenceTransformer
from langchain_community.embeddings import Embeddings

MODEL_PATH = os.path.join(
    os.path.dirname(__file__),
    "../models/embedding/BAAI/bge-large-en-v1.5"   # 也可以是 huggingface 名称
)

class BGEEmbedder(Embeddings):
    """把 SentenceTransformer 封装成 LangChain Embeddings."""
    def __init__(self, model_path: str = MODEL_PATH):
        self.model = SentenceTransformer(
            model_path,
            device="cuda" if torch.cuda.is_available() else "cpu",
            trust_remote_code=True           # BGE 需要
        )
        # fp16 可再快 30%+
        if torch.cuda.is_available():
            self.model = self.model.half()

    # ---- LangChain 接口 ----
    def embed_documents(self, texts, **kwargs):
        return self.model.encode(
            texts,
            batch_size=64,                   # 你写死也行
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        ).tolist()

    def embed_query(self, text, **kwargs):
        return self.embed_documents([text])[0]


# -------- 全局单例 getter --------
@lru_cache(maxsize=1)
def get_embeddings() -> BGEEmbedder:
    print("🔌 loading BGE embedder ...")
    return BGEEmbedder()
