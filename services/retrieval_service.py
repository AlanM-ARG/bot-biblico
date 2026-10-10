"""
Motor RAG de Precisión y Re-ranking (Fase 1)
services/retrieval_service.py

Objetivo:
- Implementa sentence-transformers usando un modelo Cross-Encoder.
- El buscador vectorial extrae los top 50 fragmentos basándose en el universo [Alineado].
- El Re-ranker evalúa esos 50 pares (query + fragmento) y le envía solo los top 15 más precisos al LLM.
"""

import os
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

from sentence_transformers import CrossEncoder
from database.connection import get_connection
from repositories.resource_repository import ResourceRepository
from core.embeddings import get_encoder
from core.vector_db import get_chroma_client, get_collection


class RetrievalService:
    """
    Servicio de recuperación y re-ordenamiento de precisión para el pipeline RAG.
    Cumple con el principio de Responsabilidad Única (SRP).
    """

    def __init__(
        self,
        cross_encoder_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
        use_ephemeral: bool = False
    ):
        self.bi_encoder = get_encoder()
        self.cross_encoder_model_name = cross_encoder_model
        self._cross_encoder = None  # Lazy loading para optimizar tiempo de arranque
        
        if use_ephemeral:
            import chromadb
            self.client = chromadb.EphemeralClient()
            self.collection = self.client.get_or_create_collection(name="biblico_collection")
        else:
            self.client = get_chroma_client()
            self.collection = get_collection()

        self.resource_repo = ResourceRepository()

    @property
    def cross_encoder(self) -> Optional[CrossEncoder]:
        """Carga perezosa del modelo Cross-Encoder."""
        if self._cross_encoder is None:
            try:
                self._cross_encoder = CrossEncoder(self.cross_encoder_model_name)
            except Exception as e:
                print(f"⚠️ Advertencia al inicializar Cross-Encoder ({self.cross_encoder_model_name}): {e}")
                self._cross_encoder = None
        return self._cross_encoder

    def _get_aligned_universe_filters(self) -> Dict[str, Any]:
        """
        Obtiene los identificadores de recursos válidos según el inventario [Alineado]
        en document_audit y resources.
        """
        conn = get_connection()
        cursor = conn.cursor()

        # Documentos descartados o en precaución en document_audit
        cursor.execute("""
            SELECT filename FROM document_audit 
            WHERE estado IN ('[Descartar]', '[Precaución]')
        """)
        excluded_filenames = {row[0] for row in cursor.fetchall()}

        # IDs de recursos descartados
        discarded_resource_ids = self.resource_repo.get_discarded_resource_ids()

        conn.close()

        # Construir filtro de ChromaDB
        # Excluir contenido autogenerado
        where_conditions = [{"category": {"$ne": "generado_por_ia"}}]
        
        if discarded_resource_ids:
            if len(discarded_resource_ids) == 1:
                where_conditions.append({"resource_id": {"$ne": discarded_resource_ids[0]}})
            else:
                where_conditions.append({"resource_id": {"$nin": discarded_resource_ids}})

        if len(where_conditions) == 1:
            where_clause = where_conditions[0]
        else:
            where_clause = {"$and": where_conditions}

        return where_clause, excluded_filenames

    def retrieve_top_candidates(self, query: str, top_k: int = 50) -> List[Dict[str, Any]]:
        """
        Paso 1: Extrae los top 50 fragmentos basándose en el universo [Alineado].
        """
        where_clause, excluded_filenames = self._get_aligned_universe_filters()

        # Generar embedding de la consulta
        query_embedding = self.bi_encoder.encode([query]).tolist()

        try:
            results = self.collection.query(
                query_embeddings=query_embedding,
                n_results=top_k,
                where=where_clause,
                include=["documents", "metadatas", "distances"]
            )
        except Exception as e:
            print(f"Error al consultar ChromaDB: {e}")
            return []

        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        candidates = []
        for doc_text, meta, dist in zip(documents, metadatas, distances):
            filename = meta.get("filename", "")
            if filename and filename in excluded_filenames:
                continue  # Descartar preventivamente
            candidates.append({
                "text": doc_text,
                "metadata": meta,
                "vector_distance": dist
            })

        return candidates

    def rerank(self, query: str, candidates: List[Dict[str, Any]], top_n: int = 15) -> List[Dict[str, Any]]:
        """
        Paso 2: El Re-ranker Cross-Encoder evalúa los 50 pares (query + fragmento)
        y devuelve los top 15 más precisos.
        """
        if not candidates:
            return []

        # Si hay menos candidatos que top_n, devolver todos
        if len(candidates) <= top_n and self.cross_encoder is None:
            return candidates

        # Preparar pares para el Cross-Encoder
        pairs = [[query, c["text"]] for c in candidates]

        ce = self.cross_encoder
        if ce is not None:
            try:
                scores = ce.predict(pairs)
                # Aplicar puntuación Cross-Encoder base
                for candidate, score in zip(candidates, scores):
                    candidate["cross_encoder_score"] = float(score)
            except Exception as e:
                print(f"⚠️ Error al predecir con Cross-Encoder: {e}. Usando orden vectorial.")
                for candidate in candidates:
                    candidate["cross_encoder_score"] = 1.0 - candidate.get("vector_distance", 1.0)
        else:
            for candidate in candidates:
                candidate["cross_encoder_score"] = 1.0 - candidate.get("vector_distance", 1.0)

        # Aplicar ponderación adaptativa (Bandit / Feedback Loop)
        try:
            from services.rag_evaluator import RAGEvaluatorService
            evaluator = RAGEvaluatorService()
            resource_ids = [
                c["metadata"].get("resource_id") 
                for c in candidates 
                if c.get("metadata", {}).get("resource_id") is not None
            ]
            boosts = evaluator.get_adaptive_boosts(resource_ids)
            for c in candidates:
                r_id = c.get("metadata", {}).get("resource_id")
                boost = boosts.get(r_id, 0.0)
                c["adaptive_boost"] = boost
                c["final_score"] = c.get("cross_encoder_score", 0.0) + boost
            
            # Ordenar por final_score ponderado
            candidates.sort(key=lambda x: x.get("final_score", 0.0), reverse=True)
        except Exception as e:
            # Fallback a ordenar por cross_encoder_score
            candidates.sort(key=lambda x: x.get("cross_encoder_score", 0.0), reverse=True)

        # Devolver solo los top 15 más precisos
        return candidates[:top_n]

    def search_and_rerank(self, query: str, top_candidates: int = 50, final_top: int = 15) -> List[Dict[str, Any]]:
        """
        Flujo unificado: Recupera top 50 del universo [Alineado] y reordena a los top 15 más precisos.
        """
        candidates = self.retrieve_top_candidates(query=query, top_k=top_candidates)
        return self.rerank(query=query, candidates=candidates, top_n=final_top)


if __name__ == "__main__":
    service = RetrievalService()
    print("RetrievalService inicializado exitosamente.")
    test_query = "justificación por la fe en Cristo"
    results = service.search_and_rerank(test_query, top_candidates=50, final_top=15)
    print(f"Fragmentos recuperados y rerankeados: {len(results)}")
