from typing import List, Optional, Sequence

try:
    from sentence_transformers import CrossEncoder  # Optional dependency
except Exception:
    CrossEncoder = None  # Graceful fallback if not installed

try:
    # Prefer the Document from langchain
    from langchain.schema import Document
except Exception:  # Minimal fallback type if langchain isn't available at import time
    class Document:  # type: ignore
        def __init__(self, page_content: str, metadata: Optional[dict] = None):
            self.page_content = page_content
            self.metadata = metadata or {}


class Reranker:
    """
    Generic reranker that prefers a CrossEncoder when available, falling back to a
    lightweight embedding-similarity reranker using the project's embedding model.

    Notes
    - The CrossEncoder path requires the optional dependency `sentence-transformers`.
    - The fallback path uses the already-configured embedding model via
      `load_embedding_model_api.get_embeddings()` and computes cosine similarity.
    - This module is implemented but not wired into the RAG pipeline yet.
    """

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2", device: Optional[str] = None):
        self.model_name = model_name
        self.device = device
        self._ce_model: Optional[object] = None

    def _ensure_cross_encoder(self) -> None:
        if CrossEncoder is None:
            return
        if self._ce_model is None:
            self._ce_model = CrossEncoder(self.model_name, device=self.device)  # type: ignore[arg-type]

    def rerank(self, query: str, documents: Sequence[Document], top_k: Optional[int] = None) -> List[Document]:
        if not documents:
            return []

        # Preferred: CrossEncoder reranking (if sentence-transformers is available)
        if CrossEncoder is not None:
            self._ensure_cross_encoder()
            assert self._ce_model is not None  # for type checkers
            pairs = [[query, doc.page_content] for doc in documents]
            scores = self._ce_model.predict(pairs)  # type: ignore[attr-defined]
            scored = list(zip(documents, scores))
            scored.sort(key=lambda x: float(x[1]), reverse=True)
            reranked_docs = [d for d, _ in scored]
        else:
            # Fallback: embedding similarity reranker (no extra deps)
            try:
                from load_embedding_model_api import get_embeddings
            except Exception:
                # If embedding pipeline is unavailable at import, just return as-is
                return list(documents)[:top_k] if top_k else list(documents)

            embeddings = get_embeddings()
            if embeddings is None:
                return list(documents)[:top_k] if top_k else list(documents)

            query_vec = embeddings.embed_query(query)
            doc_texts = [doc.page_content for doc in documents]
            doc_vecs = embeddings.embed_documents(doc_texts)

            # Cosine similarity
            def cosine(a, b):
                import math
                dot = sum(x * y for x, y in zip(a, b))
                na = math.sqrt(sum(x * x for x in a))
                nb = math.sqrt(sum(y * y for y in b))
                return dot / (na * nb + 1e-12)

            scores = [cosine(query_vec, v) for v in doc_vecs]
            reranked_docs = [d for d, _ in sorted(zip(documents, scores), key=lambda x: float(x[1]), reverse=True)]

        if top_k is not None:
            reranked_docs = reranked_docs[:top_k]
        return reranked_docs


def rerank_documents(query: str, documents: Sequence[Document], top_k: Optional[int] = None, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2", device: Optional[str] = None) -> List[Document]:
    """
    Convenience function to rerank a collection of Documents for a query.
    Currently unused in the pipeline; provided for future integration.
    """
    reranker = Reranker(model_name=model_name, device=device)
    return reranker.rerank(query=query, documents=list(documents), top_k=top_k) 