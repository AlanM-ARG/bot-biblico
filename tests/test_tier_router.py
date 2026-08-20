"""
Tests for the TierRouter: validates routing, privacy, and context-window logic.

These tests mock UnifiedLLMClient.call() to avoid real API calls.
"""

import os
import pytest
from unittest.mock import patch, MagicMock

from llm.tier_router import TierRouter
from llm.llm_client import LLMCallResult


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def router():
    """Create a TierRouter using the real config file."""
    config_path = os.path.join("data", "models_config.yaml")
    return TierRouter(config_path=config_path)


def _make_success(provider_name="test", model_name="test-model"):
    """Helper to create a successful LLMCallResult."""
    return LLMCallResult(
        content="Test response",
        provider_name=provider_name,
        model_name=model_name,
        latency_ms=100,
        success=True,
    )


def _make_failure(provider_name="test", model_name="test-model", error="Rate limited"):
    """Helper to create a failed LLMCallResult."""
    return LLMCallResult(
        provider_name=provider_name,
        model_name=model_name,
        latency_ms=50,
        success=False,
        error=error,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Test 1: Long prompt never routes to Cerebras
# ─────────────────────────────────────────────────────────────────────────────

def test_long_prompt_never_routes_to_cerebras(router):
    """
    A prompt estimated at >200K tokens must never be sent to Cerebras
    (max_context_tokens: 8000), even if Cerebras is available.
    """
    # Create a prompt that's ~200K tokens (800K chars at ~4 chars/token)
    long_prompt = "x" * 800_000

    providers_called = []

    def mock_call(provider_config, prompt, **kwargs):
        name = provider_config.get("name", "unknown")
        providers_called.append(name)
        # All providers fail so router tries all of them
        return _make_failure(provider_name=name, error="Simulated failure")

    with patch.object(router._client, "call", side_effect=mock_call):
        result = router.route(
            prompt=long_prompt,
            module="etl_classify",  # maps to tier_3_tareas_cortas (Cerebras)
        )

    # Cerebras should have been SKIPPED, not called
    assert "cerebras" not in providers_called, (
        f"Cerebras was called with a {len(long_prompt)}-char prompt! "
        f"Providers attempted: {providers_called}"
    )
    # The call should have failed since the only provider in tier 3 was skipped
    assert not result.success


# ─────────────────────────────────────────────────────────────────────────────
# Test 2: Private data never routes to aggregator
# ─────────────────────────────────────────────────────────────────────────────

def test_private_data_never_routes_to_aggregator(router):
    """
    When contains_private_data=True, aggregator providers (is_aggregator: true)
    must be excluded from the selection, even if they're the only ones with
    quota available. The system must fail gracefully rather than breach privacy.
    """
    providers_called = []

    def mock_call(provider_config, prompt, **kwargs):
        name = provider_config.get("name", "unknown")
        is_agg = provider_config.get("is_aggregator", False)
        providers_called.append({"name": name, "is_aggregator": is_agg})
        # All providers fail to force trying all of them
        return _make_failure(provider_name=name, error="Simulated failure")

    with patch.object(router._client, "call", side_effect=mock_call):
        result = router.route(
            prompt="Contenido sensible del diario personal del usuario.",
            module="life_alert",
            contains_private_data=True,
        )

    # Verify no aggregator was ever called
    aggregators_called = [p for p in providers_called if p["is_aggregator"]]
    assert len(aggregators_called) == 0, (
        f"Aggregator providers were called with private data! "
        f"Called: {[p['name'] for p in aggregators_called]}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Test 3: Fallback within tier before escalating
# ─────────────────────────────────────────────────────────────────────────────

def test_fallback_within_tier(router):
    """
    If the first provider in tier_1_contexto_grande fails, the router must
    try the second provider in the SAME tier before escalating to the
    escalon_casi_gratis.
    """
    call_count = 0
    providers_called = []

    def mock_call(provider_config, prompt, **kwargs):
        nonlocal call_count
        name = provider_config.get("name", "unknown")
        providers_called.append(name)
        call_count += 1

        # First call (gemini-3.6-flash) fails
        if call_count == 1:
            return _make_failure(
                provider_name=name,
                error="503 Service Unavailable",
            )
        # Second call (gemini-3.7-flash) succeeds
        # Second call succeeds
        return _make_success(provider_name=name, model_name=provider_config.get("model", ""))

    with patch.object(router._client, "call", side_effect=mock_call):
        result = router.route(
            prompt="Genera una guía de estudio para Romanos 8.",
            module="study_guide",
        )

    # Should have tried ollama-local first, then gemini-3.6-flash
    assert len(providers_called) >= 2, (
        f"Expected at least 2 providers to be tried, but only got: {providers_called}"
    )
    assert providers_called[0] == "ollama-local"
    assert providers_called[1] == "gemini-3.6-flash"

    # The second attempt should have succeeded
    assert result.success
    assert result.provider_name == "gemini-3.6-flash"


# ─────────────────────────────────────────────────────────────────────────────
# Additional: Module→tier mapping
# ─────────────────────────────────────────────────────────────────────────────

def test_module_tier_mapping(router):
    """Verify that modules are mapped to the correct tiers."""
    assert router._resolve_tier_name("study_guide") == "tier_1_contexto_grande"
    assert router._resolve_tier_name("topic_study") == "tier_1_contexto_grande"
    assert router._resolve_tier_name("chat_evangelism") == "tier_2_disponibilidad"
    assert router._resolve_tier_name("hermeneutic_challenge") == "tier_2_disponibilidad"
    assert router._resolve_tier_name("etl_classify") == "tier_3_tareas_cortas"


def test_privacy_module_detection(router):
    """Verify that private modules are correctly detected."""
    assert router._is_private_module("life_alert")
    assert router._is_private_module("family_devotional")
    assert not router._is_private_module("study_guide")
    assert not router._is_private_module("chat_evangelism")
