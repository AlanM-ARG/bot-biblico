"""
Singleton para el cliente ChromaDB.
Evita crear 4-5 conexiones PersistentClient al mismo directorio vector_db/
desde servicios distintos (RAGService, VectorService, RetrievalService, etc.).
"""

import os
import chromadb

_client = None
_VECTOR_DB_PATH = os.environ.get("CHROMA_DB_PATH", os.path.join(os.path.dirname(os.path.dirname(__file__)), "vector_db"))

def get_chroma_client(path: str = None) -> chromadb.ClientAPI:
    """Returns a shared ChromaDB PersistentClient instance (lazy-loaded singleton)."""
    global _client
    if _client is None:
        db_path = path or _VECTOR_DB_PATH
        os.makedirs(db_path, exist_ok=True)
        _client = chromadb.PersistentClient(path=db_path)
    return _client


def get_collection(name: str = "biblico_collection"):
    """Returns the default ChromaDB collection, creating it if needed."""
    return get_chroma_client().get_or_create_collection(name=name)
