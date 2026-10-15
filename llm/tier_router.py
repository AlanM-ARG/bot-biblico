"""
TierRouter: Selects the correct LLM provider based on task type, privacy
constraints, and prompt size. Implements fallback within each tier before
escalating.

Config lives in data/models_config.yaml — no providers are hardcoded here.
See contexto_aplicativo_biblico.md section 11 for the tier design rationale.
"""

import os
import logging
from typing import Optional

import yaml
from dotenv import load_dotenv

load_dotenv()

from llm.llm_client import UnifiedLLMClient, LLMCallResult

logger = logging.getLogger(__name__)

# Conservative token estimate: ~4 chars per token on average
CHARS_PER_TOKEN = 4

DEFAULT_CONFIG_PATH = os.path.join("data", "models_config.yaml")


class TierRouter:
    """
    Routes LLM calls to the correct tier/provider based on:
    1. Module → tier mapping (from config)
    2. Privacy filtering (exclude aggregators for private data)
    3. Token estimation (skip providers whose context window is too small)
    4. Ordered fallback within the tier
    5. Escalation to escalon_casi_gratis if entire tier fails
    """

    def __init__(self, config_path: str = DEFAULT_CONFIG_PATH):
        self._config = self._load_config(config_path)
        self._client = UnifiedLLMClient()

    @staticmethod
    def _load_config(config_path: str) -> dict:
        """Load and validate the YAML config file."""
        if not os.path.exists(config_path):
            raise FileNotFoundError(
                f"No se encontró el archivo de configuración de modelos: {config_path}"
            )
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        # Basic validation
        if "tiers" not in config:
            raise ValueError("models_config.yaml debe tener una sección 'tiers'")
        if "task_tier_map" not in config:
            raise ValueError("models_config.yaml debe tener una sección 'task_tier_map'")

        return config

    def _resolve_tier_name(self, module: str) -> str:
        """Map a module name to its tier. Falls back to tier_1 if unknown."""
        tier_name = self._config["task_tier_map"].get(module)
        if not tier_name:
            logger.warning(
                f"[TierRouter] Módulo '{module}' no está en task_tier_map. "
                f"Usando tier_1_contexto_grande por defecto."
            )
            tier_name = "tier_1_contexto_grande"
        return tier_name

    def _get_providers(self, tier_name: str) -> list[dict]:
        """Get the ordered list of providers for a tier."""
        tier = self._config["tiers"].get(tier_name, {})
        return tier.get("providers", [])

    def _is_private_module(self, module: str) -> bool:
        """Check if a module handles private data per config."""
        private_modules = self._config.get("private_data_modules", [])
        return module in private_modules

    def _estimate_tokens(self, text: str) -> int:
        """Conservative token estimate from character count."""
        return len(text) // CHARS_PER_TOKEN

    def route(
        self,
        prompt: str,
        module: str,
        system_prompt: str = "",
        temperature: float = 0.3,
        timeout: Optional[int] = None,
        contains_private_data: bool = False,
    ) -> LLMCallResult:
        """
        Main entry point. Routes the prompt to the correct provider.

        Args:
            prompt: The full prompt to send.
            module: The calling module (e.g. "study_guide", "chat_evangelism").
            system_prompt: Optional system prompt (prepended for OpenAI-compatible).
            temperature: LLM temperature.
            timeout: Per-provider timeout in seconds.
            contains_private_data: Explicit flag; also auto-detected from module.

        Returns:
            LLMCallResult with the response or error details.
        """
        # 1. Resolve tier
        tier_name = self._resolve_tier_name(module)

        # 2. Determine privacy constraint
        is_private = contains_private_data or self._is_private_module(module)

        # 3. Define tier progression
        if tier_name == "tier_4_local":
            tier_progression = [
                "tier_4_local",
                "tier_1_contexto_grande",
                "tier_2_disponibilidad",
                "tier_3_tareas_cortas",
                "escalon_casi_gratis",
            ]
            start_idx = 0
        else:
            tier_progression = [
                "tier_1_contexto_grande",
                "tier_2_disponibilidad",
                "tier_3_tareas_cortas",
                "escalon_casi_gratis",
                "tier_4_local",
            ]
            start_idx = tier_progression.index(tier_name) if tier_name in tier_progression else 0

        # 4. Estimate tokens
        total_text = prompt + (system_prompt or "")
        estimated_tokens = self._estimate_tokens(total_text)

        # 5. Cascading fallback through tiers
        attempts = []
        for current_tier in tier_progression[start_idx:]:
            providers = self._get_providers(current_tier)
            if not providers:
                continue

            if current_tier != tier_name:
                logger.info(
                    f"[TierRouter] Escalando a '{current_tier}' porque los anteriores fallaron."
                )

            # Timeout dinámico según el tier si no se proveyó uno
            effective_timeout = timeout
            if effective_timeout is None:
                if current_tier == "tier_1_contexto_grande":
                    effective_timeout = 180
                elif current_tier == "tier_4_local":
                    effective_timeout = 60  # Local models: timeout razonable para no congelar la UI
                else:
                    effective_timeout = 90
            result = self._try_providers(
                providers=providers,
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                timeout=effective_timeout,
                is_private=is_private,
                estimated_tokens=estimated_tokens,
                attempts=attempts,
            )

            if result and result.success:
                self._log_routing(module, current_tier, is_private, attempts)
                return result

        # 6. All failed
        self._log_routing(module, tier_name, is_private, attempts)
        last_error = attempts[-1]["error"] if attempts else "Sin proveedores disponibles"
        return LLMCallResult(
            success=False,
            error=(
                f"Todos los tiers hasta tier_4_local fallaron. "
                f"Último error: {last_error}"
            ),
        )

    def _try_providers(
        self,
        providers: list[dict],
        prompt: str,
        system_prompt: str,
        temperature: float,
        timeout: int,
        is_private: bool,
        estimated_tokens: int,
        attempts: list,
    ) -> Optional[LLMCallResult]:
        """
        Try each provider in order. Returns the first successful result,
        or None if all fail.
        """
        for provider in providers:
            provider_name = provider.get("name", "unknown")

            # Privacy filter: skip aggregators for private data
            if is_private and provider.get("is_aggregator", False):
                attempts.append({
                    "name": provider_name,
                    "success": False,
                    "error": "Excluido por privacidad (agregador)",
                    "latency_ms": 0,
                })
                logger.info(
                    f"[TierRouter] Saltando '{provider_name}' — "
                    f"es agregador y el contenido es privado."
                )
                continue

            # Context window filter: skip if prompt is too long
            max_tokens = provider.get("max_context_tokens", 0)
            if max_tokens and estimated_tokens > max_tokens:
                attempts.append({
                    "name": provider_name,
                    "success": False,
                    "error": (
                        f"Prompt estimado ({estimated_tokens} tokens) excede "
                        f"el máximo del proveedor ({max_tokens} tokens)"
                    ),
                    "latency_ms": 0,
                })
                logger.info(
                    f"[TierRouter] Saltando '{provider_name}' — "
                    f"prompt (~{estimated_tokens} tokens) > max ({max_tokens})."
                )
                continue

            # Override timeout for local models: limit to max 90s to avoid freezing the system
            actual_timeout = timeout
            if provider_name == "ollama-local" and (actual_timeout is None or actual_timeout > 90):
                actual_timeout = 90

            # Attempt the call
            result = self._client.call(
                provider_config=provider,
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                timeout=actual_timeout,
            )

            attempts.append({
                "name": result.provider_name,
                "success": result.success,
                "error": result.error if not result.success else "",
                "latency_ms": result.latency_ms,
            })

            if result.success:
                return result

            logger.warning(
                f"[TierRouter] '{provider_name}' falló: {result.error}. "
                f"Intentando siguiente proveedor..."
            )

        return None

    @staticmethod
    def _log_routing(
        module: str,
        tier_name: str,
        is_private: bool,
        attempts: list,
    ):
        """Log the routing decision and all attempts for observability."""
        successful = [a for a in attempts if a.get("success")]
        provider_used = successful[-1]["name"] if successful else "ninguno"

        logger.info(
            f"[TierRouter] Módulo='{module}' | Tier='{tier_name}' | "
            f"Privado={is_private} | Proveedor='{provider_used}' | "
            f"Intentos={len(attempts)}"
        )
