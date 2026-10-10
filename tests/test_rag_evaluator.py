"""
Pruebas unitarias para RAGEvaluatorService y ciclo de auto-backlog (Fase 1).
"""

import sqlite3
import pytest
from services.rag_evaluator import RAGEvaluatorService


@pytest.fixture
def memory_db():
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    
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
        CREATE TABLE rag_evaluations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            interaction_id TEXT,
            query TEXT,
            faithfulness REAL,
            context_relevancy REAL,
            answer_relevancy REAL,
            low_fidelity_flag BOOLEAN DEFAULT 0,
            backlog_ticket_id INTEGER,
            evaluated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(interaction_id) REFERENCES rag_interactions(id),
            FOREIGN KEY(backlog_ticket_id) REFERENCES temas_pendientes(id)
        )
    """)
    
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
    
    conn.commit()
    yield conn
    conn.close()


def test_low_fidelity_creates_backlog_ticket(memory_db):
    evaluator = RAGEvaluatorService(db_conn=memory_db)
    
    # Evaluar con lista vacía de fragmentos -> fuerza baja fidelidad
    result = evaluator.evaluate_interaction(
        query="Libro de Habacuc",
        response_text="Una respuesta inventada sin fuentes.",
        retrieved_chunks=[],
        interaction_id="inter_001",
        module="study_guide"
    )
    
    assert result["low_fidelity_flag"] is True
    assert result["faithfulness"] < 0.70
    assert result["backlog_ticket_id"] is not None
    
    cursor = memory_db.cursor()
    cursor.execute("SELECT tema_o_libro, prioridad, estado FROM temas_pendientes WHERE id = ?", (result["backlog_ticket_id"],))
    ticket = cursor.fetchone()
    assert ticket is not None
    assert ticket[0] == "Libro de Habacuc"
    assert ticket[1] == "Alta"
    assert ticket[2] == "Pendiente"


def test_adaptive_boosts_penalize_reported_errors(memory_db):
    cursor = memory_db.cursor()
    cursor.execute("INSERT INTO document_audit (id, filename, fallos_doctrinales_reportados) VALUES ('doc_1', 'falso_maestro.md', 2)")
    cursor.execute("INSERT INTO document_audit (id, filename, fallos_doctrinales_reportados) VALUES ('doc_2', 'puritano_sano.md', 0)")
    memory_db.commit()
    
    evaluator = RAGEvaluatorService(db_conn=memory_db)
    boosts = evaluator.get_adaptive_boosts(['doc_1', 'doc_2'])
    
    assert boosts['doc_1'] < 0.0  # Penalizado por fallos
    assert boosts['doc_2'] == 0.0 # Sin penalización
