"""
Tests de integración para la conexión RetrievalService ↔ RAGService.
Verifica que _retrieve_with_reranking() devuelve el mismo contrato
(context_docs, is_covered, distances) y cae al bi-encoder en modo efímero.
"""
import pytest
from unittest.mock import MagicMock, patch
from services.rag_service import RAGService
from services.rag_logger import RAGLogEntry
from models.user import User


@pytest.fixture
def mock_rag_deps():
    """Configura RAGService en modo efímero con dependencias mockeadas."""
    with patch('services.rag_service.UserRepository') as MockUserRepo, \
         patch('services.rag_service.CacheAuditRepository') as MockCacheRepo, \
         patch('chromadb.EphemeralClient') as MockChroma, \
         patch('services.rag_service.get_encoder') as MockGetEncoder:

        mock_encoder = MagicMock()
        MockGetEncoder.return_value = mock_encoder
        mock_user = User(id=1, username="test_user", display_name="Test",
                         study_level="moderado", family_mode=False)
        MockUserRepo.return_value.get_user_by_id.return_value = mock_user

        yield {
            "user_repo": MockUserRepo.return_value,
            "encoder": mock_encoder,
            "mock_user": mock_user,
        }


def test_retrieve_with_reranking_falls_back_in_ephemeral(mock_rag_deps):
    """En modo efímero (tests), _retrieve_with_reranking debe caer al bi-encoder clásico."""
    rag = RAGService(use_ephemeral_db=True)
    rag.collection = MagicMock()
    rag.collection.query.return_value = {
        'documents': [["Texto de prueba sobre justificación"]],
        'distances': [[0.5]],
        'ids': [["chunk_1"]],
    }

    log_entry = RAGLogEntry(module="test", query="justificación")
    docs, is_covered, distances = rag._retrieve_with_reranking(
        "justificación por la fe", log_entry=log_entry,
        top_candidates=50, final_top=15
    )

    assert isinstance(docs, list)
    assert isinstance(is_covered, bool)
    assert isinstance(distances, list)
    assert is_covered is True  # distance 0.5 < 1.5 threshold
    assert len(docs) > 0
    assert len(log_entry.chunks_retrieved) > 0


def test_retrieve_with_reranking_returns_same_contract(mock_rag_deps):
    """Ambos métodos deben devolver el mismo contrato: (list, bool, list)."""
    rag = RAGService(use_ephemeral_db=True)
    rag.collection = MagicMock()
    rag.collection.query.return_value = {
        'documents': [["Doc A", "Doc B"]],
        'distances': [[0.3, 0.8]],
        'ids': [["c1", "c2"]],
    }

    result_classic = rag._retrieve_and_check_coverage("test query", n_results=2)
    result_reranking = rag._retrieve_with_reranking("test query", final_top=2)

    # Mismo contrato: tuple de 3 elementos
    assert len(result_classic) == 3
    assert len(result_reranking) == 3

    # Mismos tipos
    assert type(result_classic[0]) == type(result_reranking[0])  # list
    assert type(result_classic[1]) == type(result_reranking[1])  # bool
    assert type(result_classic[2]) == type(result_reranking[2])  # list


def test_retrieve_with_reranking_fallback_on_exception(mock_rag_deps):
    """Si RetrievalService lanza una excepción, debe caer al bi-encoder."""
    rag = RAGService(use_ephemeral_db=False)
    rag.collection = MagicMock()
    rag.collection.query.return_value = {
        'documents': [["Fallback doc"]],
        'distances': [[0.7]],
        'ids': [["fb_1"]],
    }

    # Forzar que el import de RetrievalService falle
    with patch.dict('sys.modules', {'services.retrieval_service': None}):
        log_entry = RAGLogEntry(module="test_fallback", query="prueba fallback")
        docs, is_covered, distances = rag._retrieve_with_reranking(
            "prueba fallback", log_entry=log_entry
        )

    assert len(docs) > 0
    assert is_covered is True  # 0.7 < 1.5
    assert len(log_entry.chunks_retrieved) > 0


def test_retrieve_with_reranking_no_coverage_sets_flag(mock_rag_deps):
    """Si todos los documentos están lejos (distancia > threshold), is_covered debe ser False."""
    rag = RAGService(use_ephemeral_db=True)
    rag.collection = MagicMock()
    rag.collection.query.return_value = {
        'documents': [["Doc lejano"]],
        'distances': [[2.5]],  # > 1.5 threshold
        'ids': [["far_1"]],
    }

    log_entry = RAGLogEntry(module="test", query="tema sin cobertura")
    docs, is_covered, distances = rag._retrieve_with_reranking(
        "tema sin cobertura", log_entry=log_entry
    )

    assert is_covered is False
    assert log_entry.fallback_no_rag is True
