import pytest
from unittest.mock import MagicMock, patch
from services.propositional_service import PropositionalService
from llm.llm_client import LLMCallResult

def test_format_text_separates_connectors():
    svc = PropositionalService()
    # Forzar fallback regex para probar la lógica sintáctica pura
    with patch.object(svc.tier_router, 'route') as mock_route:
        mock_route.return_value = LLMCallResult(
            provider_name="test", model_name="test", success=False, error="Simulated fallback"
        )
        text = "Dios es amor, porque Él nos amó primero; por tanto, amémonos."
        formatted = svc.format_text(text)
        
        # "porque" y "por tanto" son conectores.
        # El servicio debería ponerlos en nuevas líneas o indentarlos.
        assert "porque" in formatted.lower()
        assert "\n" in formatted # Debería haber saltos de línea introducidos

def test_format_text_preserves_verses():
    svc = PropositionalService()
    with patch.object(svc.tier_router, 'route') as mock_route:
        mock_route.return_value = LLMCallResult(
            provider_name="test", model_name="test", success=False, error="Simulated fallback"
        )
        text = "**1** En el principio creó Dios los cielos y la tierra."
        formatted = svc.format_text(text)
        
        assert "**1**" in formatted
        assert "En el principio" in formatted

def test_format_text_uses_llm_when_successful():
    svc = PropositionalService()
    with patch.object(svc.tier_router, 'route') as mock_route:
        mock_route.return_value = LLMCallResult(
            provider_name="ollama-local", model_name="llama3.1", success=True, 
            content="Dios es amor,\n> porque Él nos amó primero"
        )
        text = "Dios es amor, porque Él nos amó primero"
        formatted = svc.format_text(text)
        assert "> porque Él nos amó primero" in formatted

