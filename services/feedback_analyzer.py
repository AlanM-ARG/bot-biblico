"""
Microservicio de Castigo Automático (Fase 1)
services/feedback_analyzer.py

Objetivo: Proceso asíncrono e idempotente que revisa la tabla feedback_beta.
- Si una respuesta obtiene rating = -1 por "Error Doctrinal", identifica qué documento se usó en sources_used.
- Si un documento acumula 3 fallos (fallos_doctrinales_reportados), su estado cambia a [Precaución]
  y se eliminan sus vectores de la base de datos ChromaDB automáticamente.
- Garantiza idempotencia mediante la columna feedback_beta.procesado = 1.
"""

import os
import json
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional

from database.connection import get_connection
from services.vector_service import VectorService


class FeedbackAnalyzer:
    """
    Analizador de retroalimentación de usuario y ejecutor de penalizaciones doctrinales.
    Cumple con el principio de Responsabilidad Única (SRP) e idempotencia.
    """

    def __init__(self, db_conn=None, vector_service: Optional[VectorService] = None):
        self._db_conn = db_conn
        self._vector_service = vector_service

    def _get_db(self):
        return self._db_conn or get_connection()

    @property
    def vector_service(self) -> VectorService:
        if self._vector_service is None:
            self._vector_service = VectorService()
        return self._vector_service

    def _parse_sources(self, sources_raw: Optional[str]) -> List[str]:
        """Extrae la lista de fuentes a partir del campo sources_used."""
        if not sources_raw:
            return []
        
        # Intentar JSON
        try:
            parsed = json.loads(sources_raw)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if item]
        except Exception:
            pass

        # Fallback a split por coma o saltos de línea
        items = [s.strip() for s in sources_raw.replace("\n", ",").split(",") if s.strip()]
        return items

    def process_doctrinal_penalties(self) -> Dict[str, Any]:
        """
        Revisa las entradas en feedback_beta con rating = -1, motivo = 'Error Doctrinal'
        y que aún no hayan sido procesadas (procesado = 0).
        Aplica penalizaciones acumulativas a los documentos causantes y las marca como procesadas.
        """
        conn = self._get_db()
        cursor = conn.cursor()

        query = """
            SELECT 
                f.id AS feedback_id,
                f.interaction_id,
                f.rating,
                f.motivo,
                r.sources_used
            FROM feedback_beta f
            INNER JOIN rag_interactions r ON f.interaction_id = r.id
            WHERE f.rating = -1 
              AND (f.motivo LIKE '%Error Doctrinal%' OR f.motivo = 'Error Doctrinal')
              AND (f.procesado = 0 OR f.procesado IS NULL)
        """
        cursor.execute(query)
        rows = cursor.fetchall()

        processed_count = 0
        penalized_docs = {}
        purged_docs = []

        for row in rows:
            feedback_id = row["feedback_id"] if isinstance(row, dict) or hasattr(row, "keys") else row[0]
            sources_raw = row["sources_used"] if isinstance(row, dict) or hasattr(row, "keys") else row[4]
            sources_used = self._parse_sources(sources_raw)

            for source in sources_used:
                source_clean = Path(source).name

                # Buscar en document_audit por coincidencia de filename o id
                cursor.execute("""
                    SELECT id, filename, estado, fallos_doctrinales_reportados
                    FROM document_audit
                    WHERE filename = ? OR id = ? OR filename LIKE ?
                """, (source_clean, source, f"%{source_clean}%"))
                doc_row = cursor.fetchone()

                if doc_row:
                    doc_id = doc_row["id"] if isinstance(doc_row, dict) or hasattr(doc_row, "keys") else doc_row[0]
                    filename = doc_row["filename"] if isinstance(doc_row, dict) or hasattr(doc_row, "keys") else doc_row[1]
                    estado = doc_row["estado"] if isinstance(doc_row, dict) or hasattr(doc_row, "keys") else doc_row[2]
                    prev_fallos = (doc_row["fallos_doctrinales_reportados"] if isinstance(doc_row, dict) or hasattr(doc_row, "keys") else doc_row[3]) or 0
                    current_fallos = prev_fallos + 1

                    # Actualizar fallos en document_audit
                    cursor.execute("""
                        UPDATE document_audit
                        SET fallos_doctrinales_reportados = ?
                        WHERE id = ?
                    """, (current_fallos, doc_id))

                    penalized_docs[filename] = current_fallos

                    # Si acumula 3 fallos -> degradar a [Precaución] y purgar vectores de ChromaDB
                    if current_fallos >= 3 and estado != "[Precaución]":
                        print(f"⚠️ [CASTIGO AUTOMÁTICO] Documento {filename} acumuló {current_fallos} fallos doctrinales.")
                        print(f"🔄 Cambiando estado a [Precaución] y purgando vectores...")

                        cursor.execute("""
                            UPDATE document_audit
                            SET estado = '[Precaución]'
                            WHERE id = ?
                        """, (doc_id,))

                        # También actualizar en resources si existe
                        cursor.execute("""
                            UPDATE resources
                            SET category = 'precaucion', is_vectorized = 0
                            WHERE filename = ?
                        """, (filename,))

                        # Purgar vectores en ChromaDB
                        try:
                            self.vector_service.delete_document_vectors(filename)
                            self.vector_service.delete_document_vectors(doc_id)
                        except Exception as e:
                            print(f"⚠️ Error al purgar vectores para {filename}: {e}")
                            
                        purged_docs.append(filename)

            # Marcar el feedback como procesado para garantizar idempotencia
            cursor.execute("UPDATE feedback_beta SET procesado = 1 WHERE id = ?", (feedback_id,))
            processed_count += 1

        conn.commit()
        if not self._db_conn:
            conn.close()

        return {
            "feedbacks_revisados": len(rows),
            "documentos_penalizados": penalized_docs,
            "documentos_purgados": purged_docs
        }

    async def run_async_loop(self, poll_interval_seconds: int = 60):
        """Ejecuta el monitoreo de feedback_beta en segundo plano de forma asíncrona."""
        print(f"🚀 [FeedbackAnalyzer] Monitor asíncrono iniciado (Intervalo: {poll_interval_seconds}s)")
        try:
            while True:
                results = self.process_doctrinal_penalties()
                if results["documentos_purgados"]:
                    print(f"🔔 [FeedbackAnalyzer] Purgados por desviación doctrinal: {results['documentos_purgados']}")
                await asyncio.sleep(poll_interval_seconds)
        except asyncio.CancelledError:
            print("🛑 [FeedbackAnalyzer] Monitor asíncrono detenido.")


if __name__ == "__main__":
    analyzer = FeedbackAnalyzer()
    res = analyzer.process_doctrinal_penalties()
    print("Resultado de penalizaciones doctrinales:", json.dumps(res, indent=2, ensure_ascii=False))
