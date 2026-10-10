"""
Singleton para el modelo de embeddings SentenceTransformer.
Evita cargar el modelo 4 veces en memoria (RAGService, VectorService,
CrossReferenceService, RetrievalService).
"""

from sentence_transformers import SentenceTransformer

_encoder = None

def get_encoder(model_name: str = "all-MiniLM-L6-v2") -> SentenceTransformer:
    """Returns a shared SentenceTransformer instance (lazy-loaded singleton)."""
    global _encoder
    if _encoder is None:
        _encoder = SentenceTransformer(model_name)
    return _encoder
