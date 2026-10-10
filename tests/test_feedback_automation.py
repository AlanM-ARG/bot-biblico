"""
Pruebas unitarias y de integración para la automatización del proceso de feedback,
idempotencia de FeedbackAnalyzer y despacho asíncrono de evaluación RAG.
"""

import sqlite3
import pytest
from unittest.mock import MagicMock, patch

from services.feedback_analyzer import FeedbackAnalyzer
from services.async_feedback_dispatcher import AsyncFeedbackDispatcher
from models.rag_response import RAGResponse
from models.feedback import FeedbackBeta
from repositories.feedback_repository import FeedbackRepository


@pytest.fixture
def mock_db():
    """Base de datos en memoria con esquema completo para feedback y auditoría."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE document_audit (
            id TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            estado TEXT DEFAULT '[Pendiente]',
            fecha_ingesta DATETIME DEFAULT CURRENT_TIMESTAMP,
            fecha_auditoria DATETIME,
            fallos_doctrinales_reportados INTEGER DEFAULT 0
        )
    """)

    cursor.execute("""
        CREATE TABLE resources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            category TEXT,
            is_vectorized INTEGER DEFAULT 0
        )
    """)

    cursor.execute("""
        CREATE TABLE rag_interactions (
            id TEXT PRIMARY KEY,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            query TEXT,
            model_used TEXT,
            module TEXT,
            sources_used TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE feedback_beta (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            interaction_id TEXT,
            rating INTEGER,
            motivo TEXT,
            comentario_libre TEXT,
            procesado INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(interaction_id) REFERENCES rag_interactions(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE temas_pendientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tema_o_libro TEXT NOT NULL,
            motivo_necesidad TEXT,
            tipo_recurso_requerido TEXT,
            estado TEXT DEFAULT 'Pendiente',
            prioridad TEXT DEFAULT 'Media',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE rag_evaluations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            interaction_id TEXT,
            query TEXT,
            faithfulness REAL,
            context_relevancy REAL,
            answer_relevancy REAL,
            low_fidelity_flag BOOLEAN DEFAULT 0,
            backlog_ticket_id INTEGER,
            evaluated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    yield conn
    conn.close()


def test_feedback_analyzer_idempotency(mock_db):
    """
    Verifica que FeedbackAnalyzer penaliza el documento la primera vez y marca procesado=1,
    de modo que ejecuciones sucesivas NO vuelven a penalizarlo.
    """
    cursor = mock_db.cursor()
    cursor.execute("INSERT INTO document_audit (id, filename, estado, fallos_doctrinales_reportados) VALUES ('doc_1', 'doctrina_dudosa.md', '[Alineado]', 0)")
    cursor.execute("INSERT INTO rag_interactions (id, query, model_used, module, sources_used) VALUES ('inter_1', '¿Qué es el libre albedrío?', 'gemini-3.6-flash', 'study_guide', '[\"doctrina_dudosa.md\"]')")
    cursor.execute("INSERT INTO feedback_beta (interaction_id, rating, motivo, comentario_libre, procesado) VALUES ('inter_1', -1, 'Error Doctrinal', 'Niega la gracia eficaz', 0)")
    mock_db.commit()

    mock_vector_service = MagicMock()
    analyzer = FeedbackAnalyzer(db_conn=mock_db, vector_service=mock_vector_service)

    # 1. Primera ejecución: procesa y penaliza
    res1 = analyzer.process_doctrinal_penalties()
    assert res1["feedbacks_revisados"] == 1
    assert res1["documentos_penalizados"].get("doctrina_dudosa.md") == 1

    cursor.execute("SELECT fallos_doctrinales_reportados FROM document_audit WHERE id = 'doc_1'")
    assert cursor.fetchone()[0] == 1

    cursor.execute("SELECT procesado FROM feedback_beta WHERE interaction_id = 'inter_1'")
    assert cursor.fetchone()[0] == 1

    # 2. Segunda ejecución inmediata: no debe reprocesar ni incrementar fallos
    res2 = analyzer.process_doctrinal_penalties()
    assert res2["feedbacks_revisados"] == 0
    assert len(res2["documentos_penalizados"]) == 0

    cursor.execute("SELECT fallos_doctrinales_reportados FROM document_audit WHERE id = 'doc_1'")
    assert cursor.fetchone()[0] == 1  # Sigue en 1, no subió a 2


def test_feedback_analyzer_purges_on_third_strike(mock_db):
    """
    Verifica que al llegar al tercer fallo doctrinal, el documento cambia a [Precaución]
    y se purgan automáticamente sus vectores de ChromaDB.
    """
    cursor = mock_db.cursor()
    # Ya tiene 2 fallos previos
    cursor.execute("INSERT INTO document_audit (id, filename, estado, fallos_doctrinales_reportados) VALUES ('doc_peligroso', 'herejia.md', '[Alineado]', 2)")
    cursor.execute("INSERT INTO resources (filename, category, is_vectorized) VALUES ('herejia.md', 'general', 1)")
    cursor.execute("INSERT INTO rag_interactions (id, query, model_used, module, sources_used) VALUES ('inter_3', 'consulta', 'gemini-3.6-flash', 'study_guide', '[\"herejia.md\"]')")
    cursor.execute("INSERT INTO feedback_beta (interaction_id, rating, motivo, procesado) VALUES ('inter_3', -1, 'Error Doctrinal', 0)")
    mock_db.commit()

    mock_vector_service = MagicMock()
    analyzer = FeedbackAnalyzer(db_conn=mock_db, vector_service=mock_vector_service)

    res = analyzer.process_doctrinal_penalties()
    assert res["feedbacks_revisados"] == 1
    assert "herejia.md" in res["documentos_purgados"]

    # Verificar estado degradado en document_audit
    cursor.execute("SELECT estado, fallos_doctrinales_reportados FROM document_audit WHERE id = 'doc_peligroso'")
    row = cursor.fetchone()
    assert row[0] == "[Precaución]"
    assert row[1] == 3

    # Verificar actualización en resources
    cursor.execute("SELECT category, is_vectorized FROM resources WHERE filename = 'herejia.md'")
    res_row = cursor.fetchone()
    assert res_row[0] == "precaucion"
    assert res_row[1] == 0

    # Verificar que se llamó a delete_document_vectors
    assert mock_vector_service.delete_document_vectors.called


def test_async_feedback_dispatcher_does_not_block():
    """Verifica que el despachador encole tareas asíncronas sin lanzar excepciones."""
    with patch("services.rag_evaluator.RAGEvaluatorService") as MockEvaluator:
        AsyncFeedbackDispatcher.dispatch_rag_evaluation(
            query="Prueba async",
            response_text="Respuesta de prueba",
            retrieved_chunks=["chunk_1"],
            interaction_id="test_inter_async",
            module="test"
        )

    with patch("services.feedback_analyzer.FeedbackAnalyzer") as MockAnalyzer:
        AsyncFeedbackDispatcher.dispatch_feedback_analysis()


def test_rag_response_carries_interaction_id():
    """Verifica que RAGResponse acepte y conserve interaction_id."""
    resp = RAGResponse(
        content="Respuesta bíblica",
        sources_used=["fuente1.md"],
        interaction_id="uuid-12345"
    )
    assert resp.interaction_id == "uuid-12345"
    assert resp.content == "Respuesta bíblica"
