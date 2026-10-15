import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from server import app
from schemas.api_dto import EstudioRequest, RAGResponse, TipoEstudio, NivelProfundidad

client = TestClient(app)


def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["app"] == "Teos AI - Backend API"
    assert data["status"] == "online"
    assert "/openapi.json" in data["openapi"]


def test_health_check_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"
    assert "total_libros_auditados" in data
    assert data["total_libros_auditados"] is not None
    assert data["total_libros_auditados"] >= 0


def test_get_auditoria_endpoint():
    response = client.get("/api/auditoria?limit=5")
    assert response.status_code == 200
    items = response.json()
    assert isinstance(items, list)
    if items:
        first = items[0]
        assert "titulo" in first
        assert "autor" in first
        assert "estado" in first
        assert first["estado"] in ["Alineado", "Precaución", "Descartar", "Pendiente"]


def test_get_auditoria_filter_by_estado():
    response = client.get("/api/auditoria?estado=Alineado&limit=5")
    assert response.status_code == 200
    items = response.json()
    assert isinstance(items, list)
    for it in items:
        assert it["estado"] == "Alineado"


def test_get_auditoria_search():
    response = client.get("/api/auditoria?search=Keller&limit=5")
    assert response.status_code == 200
    items = response.json()
    assert isinstance(items, list)
    for it in items:
        assert "keller" in it["autor"].lower() or "keller" in it["titulo"].lower()


def test_get_backlog_endpoint():
    response = client.get("/api/backlog?limit=5")
    assert response.status_code == 200
    items = response.json()
    assert isinstance(items, list)
    if items:
        first = items[0]
        assert "tema_o_libro" in first
        assert "estado" in first


def test_exportar_pdf_endpoint():
    payload = {
        "contenido_markdown": "# Justificación por la Fe\n\nTexto de prueba para el documento PDF.\n\n- Punto 1\n- Punto 2",
        "titulo": "estudio_justificacion"
    }
    response = client.post("/api/exportar-pdf", json=payload)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "attachment; filename=\"estudio_justificacion.pdf\"" in response.headers["content-disposition"]
    # PDF magic bytes
    assert response.content.startswith(b"%PDF")


def test_exportar_pdf_empty_content():
    response = client.post("/api/exportar-pdf", json={"contenido_markdown": "", "titulo": "vacio"})
    assert response.status_code == 422  # pydantic min_length=1 validation error


@patch("server.get_rag_service")
def test_post_estudio_exegetico(mock_get_rag):
    mock_rag = MagicMock()
    mock_rag.generate_study_guide.return_value = RAGResponse(
        content="## Exégesis de Romanos 8:28\n\nEl amor soberano de Dios...",
        sources_used=["Comentario a Romanos (Hodge)", "Biblia NTV"],
        fallback_no_rag=False,
        recommended_resources=[],
        missing_topics=[]
    )
    mock_get_rag.return_value = mock_rag

    payload = {
        "tema_o_versiculo": "Romanos 8:28",
        "tipo_estudio": "exegetico",
        "nivel_profundidad": "inductivo",
        "lente": "Lente Inductivo",
        "user_id": 1
    }
    response = client.post("/api/estudio", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "content" in data
    assert "Romanos 8:28" in data["content"]
    assert "sources_used" in data
    assert len(data["sources_used"]) == 2
    assert data["fallback_no_rag"] is False
    mock_rag.generate_study_guide.assert_called_once()


@patch("server.get_rag_service")
def test_post_estudio_tematico(mock_get_rag):
    mock_rag = MagicMock()
    mock_rag.generate_topic_study.return_value = RAGResponse(
        content="## La Soberanía de Dios\n\nEstudio temático sistemático...",
        sources_used=["Confesión de Fe de Londres 1689", "Institución (Calvino)"],
        fallback_no_rag=False,
        recommended_resources=[],
        missing_topics=[]
    )
    mock_get_rag.return_value = mock_rag

    payload = {
        "tema_o_versiculo": "La Soberanía de Dios",
        "tipo_estudio": "tematico",
        "nivel_profundidad": "pastoral",
        "user_id": 1
    }
    response = client.post("/api/estudio", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "content" in data
    assert "Soberanía de Dios" in data["content"]
    assert data["fallback_no_rag"] is False
    mock_rag.generate_topic_study.assert_called_once()


def test_estudio_request_normalization():
    # Test synonym mappings (e.g. 'principiante' -> 'basico')
    req = EstudioRequest(
        tema_o_versiculo="Gálatas 1",
        tipo_estudio="exegético",
        nivel_profundidad="principiante"
    )
    assert req.tipo_estudio == TipoEstudio.EXEGETICO
    assert req.nivel_profundidad == NivelProfundidad.BASICO


def test_openapi_schema_endpoint():
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert "paths" in schema
    assert "/api/estudio" in schema["paths"]
    assert "/api/auditoria" in schema["paths"]
    assert "/api/backlog" in schema["paths"]
    assert "/api/exportar-pdf" in schema["paths"]
    assert "EstudioRequest" in schema["components"]["schemas"]
    assert "RAGResponse" in schema["components"]["schemas"]
    assert "AuditoriaItem" in schema["components"]["schemas"]
    assert "BacklogItem" in schema["components"]["schemas"]
