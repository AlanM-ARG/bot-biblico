"""
Despachador Asíncrono de Feedback y Evaluaciones RAG
services/async_feedback_dispatcher.py

Objetivo:
- Ejecutar evaluaciones de calidad RAG (RAGEvaluatorService) en segundo plano
  sin bloquear las respuestas de la UI ni añadir latencia percibida al usuario.
- Disparar de inmediato el análisis y purga de documentos doctrinales degradados
  (FeedbackAnalyzer) cuando se registra un reporte negativo explícito en feedback_beta.
"""

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional

logger = logging.getLogger("AsyncFeedbackDispatcher")


class AsyncFeedbackDispatcher:
    _instance = None
    _executor: Optional[ThreadPoolExecutor] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AsyncFeedbackDispatcher, cls).__new__(cls)
            # Pool limitado para no competir con el servidor Streamlit/LiteLLM
            cls._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="FeedbackWorker")
        return cls._instance

    @classmethod
    def get_executor(cls) -> ThreadPoolExecutor:
        if cls._executor is None:
            cls._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="FeedbackWorker")
        return cls._executor

    @classmethod
    def dispatch_rag_evaluation(
        cls,
        query: str,
        response_text: str,
        retrieved_chunks: List[str],
        interaction_id: Optional[str] = None,
        module: str = "general"
    ):
        """
        Envía la evaluación de fidelidad documental al ThreadPool.
        Si la fidelidad es < 0.70 o la relevancia es < 0.60, RAGEvaluatorService
        generará automáticamente un ticket en temas_pendientes.
        """
        def _task():
            try:
                from services.rag_evaluator import RAGEvaluatorService
                evaluator = RAGEvaluatorService()
                evaluator.evaluate_interaction(
                    query=query,
                    response_text=response_text,
                    retrieved_chunks=retrieved_chunks,
                    interaction_id=interaction_id,
                    module=module
                )
            except Exception as e:
                logger.warning(f"[AsyncFeedbackDispatcher] Error en evaluación asíncrona de RAG: {e}")

        try:
            cls.get_executor().submit(_task)
        except Exception as e:
            logger.warning(f"[AsyncFeedbackDispatcher] No se pudo encolar evaluación: {e}")

    @classmethod
    def dispatch_feedback_analysis(cls):
        """
        Dispara el procesamiento de penalizaciones doctrinales en segundo plano.
        Si algún documento acumula 3 fallos, FeedbackAnalyzer cambiará su estado a [Precaución]
        y purgará sus vectores de ChromaDB.
        """
        def _task():
            try:
                from services.feedback_analyzer import FeedbackAnalyzer
                analyzer = FeedbackAnalyzer()
                analyzer.process_doctrinal_penalties()
            except Exception as e:
                logger.warning(f"[AsyncFeedbackDispatcher] Error al procesar penalizaciones doctrinales: {e}")

        try:
            cls.get_executor().submit(_task)
        except Exception as e:
            logger.warning(f"[AsyncFeedbackDispatcher] No se pudo encolar análisis de feedback: {e}")

    @classmethod
    def shutdown(cls, wait: bool = False):
        if cls._executor is not None:
            cls._executor.shutdown(wait=wait)
            cls._executor = None
