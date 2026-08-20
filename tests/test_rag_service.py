import pytest
from unittest.mock import MagicMock, patch
import os
from services.rag_service import RAGService
from models.user import User

@pytest.fixture
def mock_dependencies():
    with patch('services.rag_service.UserRepository') as MockUserRepo, \
         patch('services.rag_service.CacheAuditRepository') as MockCacheRepo, \
         patch('services.rag_service.chromadb.EphemeralClient') as MockChroma, \
         patch('services.rag_service.SentenceTransformer') as MockEncoder:
         
        mock_user = User(id=1, username="test_user", display_name="Test", study_level="moderado", family_mode=False)
        MockUserRepo.return_value.get_user_by_id.return_value = mock_user
        
        yield {
            "user_repo": MockUserRepo.return_value,
            "cache_repo": MockCacheRepo.return_value,
            "chroma": MockChroma.return_value,
            "encoder": MockEncoder.return_value,
            "mock_user": mock_user
        }

def test_build_prompt_includes_fallback_rule(mock_dependencies):
    rag = RAGService(use_ephemeral_db=True)
    prompt = rag._build_prompt(mock_dependencies["mock_user"], "Romanos 8", ["Contexto irrelevante"])
    
    assert "REGLA DE CONTEXTO INSUFICIENTE (fallback educativo" in prompt
    assert "Marcá `\"fallback_no_rag\": true` en la salida" in prompt

def test_build_prompt_injects_study_level(mock_dependencies):
    rag = RAGService(use_ephemeral_db=True)
    mock_dependencies["mock_user"].study_level = "complejo"
    prompt = rag._build_prompt(mock_dependencies["mock_user"], "Romanos 8", ["Contexto"])
    
    assert "NIVEL DE ESTUDIO: complejo" in prompt

@patch.object(RAGService, '_call_llm')
def test_generate_roadmap_returns_json(mock_call_llm, mock_dependencies):
    mock_call_llm.return_value = '''{
  "content": "```json\\n{\\"topic\\": \\"Gracia\\", \\"weeks\\": []}\\n```",
  "sources_used": ["source1"],
  "fallback_no_rag": false,
  "recommended_resources": []
}'''
    
    rag = RAGService(use_ephemeral_db=True)
    rag.collection = MagicMock()
    rag.collection.query.return_value = {'documents': [["text"]], 'distances': [[0.5]], 'ids': [["doc1"]]}
    
    result = rag.generate_roadmap(1, "Gracia")
    assert "```json" in result.content
    assert '"topic": "Gracia"' in result.content
    assert result.fallback_no_rag is False

@patch.object(RAGService, '_call_llm')
def test_generate_gym_exercise(mock_call_llm, mock_dependencies):
    mock_call_llm.return_value = '''{
  "content": "Desafío de Poesía Hebrea: ¿Qué tipo de paralelismo ves aquí?",
  "sources_used": ["Salmo 1"],
  "fallback_no_rag": false,
  "recommended_resources": []
}'''
    rag = RAGService(use_ephemeral_db=True)
    rag.collection = MagicMock()
    rag.collection.query.return_value = {'documents': [["text"]], 'distances': [[0.5]], 'ids': [["doc1"]]}
    
    result = rag.generate_gym_exercise(1, "Poesía Hebrea", "Salmo 1")
    assert "Desafío de Poesía Hebrea" in result.content
    mock_call_llm.assert_called_once()

@patch.object(RAGService, '_call_llm')
def test_evaluate_gym_answer(mock_call_llm, mock_dependencies):
    mock_call_llm.return_value = '''{
  "content": "Evaluación: Tu respuesta es correcta, es un paralelismo antitético.",
  "sources_used": ["Contexto"],
  "fallback_no_rag": false,
  "recommended_resources": []
}'''
    rag = RAGService(use_ephemeral_db=True)
    result = rag.evaluate_gym_answer(1, "Poesía Hebrea", "Desafío: ...", "Es antitético")
    
    assert "Evaluación:" in result.content
    mock_call_llm.assert_called_once()

