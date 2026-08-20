"""
UnifiedLLMClient: Single entry point for calling any LLM provider.

Supports two integration types:
- "openai_compatible": Groq, Mistral, OpenRouter, GitHub Models, Z.AI, Cerebras, DeepSeek
  (all use the same OpenAI SDK format with different base_url/api_key/model)
- "gemini": Google AI Studio (uses the google-genai SDK)
- "eden_ai": Placeholder for future Eden AI integration

See data/models_config.yaml for the full provider list.
"""

import os
import time
import logging
import traceback
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class LLMCallResult:
    """Result of a single LLM call attempt."""
    content: str = ""
    provider_name: str = ""
    model_name: str = ""
    latency_ms: int = 0
    success: bool = False
    error: str = ""


class UnifiedLLMClient:
    """
    Wraps all supported LLM providers behind a single `call()` method.
    Provider-specific logic is isolated here — callers only see LLMCallResult.
    """

    def call(
        self,
        provider_config: dict,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.3,
        timeout: int = 30,
    ) -> LLMCallResult:
        """
        Dispatch to the correct provider based on provider_config['type'].
        Returns LLMCallResult with success/error status and timing.
        """
        provider_type = provider_config.get("type", "")
        provider_name = provider_config.get("name", "unknown")
        model_name = provider_config.get("model", "unknown")
        api_key_env = provider_config.get("api_key_env", "")
        api_key = os.getenv(api_key_env, "")
        
        # Bypass empty API key check for local models that don't need one
        if not api_key and api_key_env == "DUMMY_KEY_LOCAL":
            api_key = "ollama-dummy-key"

        if not api_key:
            return LLMCallResult(
                provider_name=provider_name,
                model_name=model_name,
                success=False,
                error=f"API key no configurada ({api_key_env})",
            )

        start = time.perf_counter()

        try:
            if provider_type == "openai_compatible":
                content = self._call_openai_compatible(
                    base_url=provider_config.get("base_url", ""),
                    api_key=api_key,
                    model=model_name,
                    prompt=prompt,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    timeout=timeout,
                )
            elif provider_type == "gemini":
                content = self._call_gemini(
                    api_key=api_key,
                    model=model_name,
                    prompt=prompt,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    timeout=timeout,
                )
            elif provider_type == "eden_ai":
                content = self._call_eden_ai(
                    api_key=api_key,
                    model=model_name,
                    prompt=prompt,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    timeout=timeout,
                )
            else:
                return LLMCallResult(
                    provider_name=provider_name,
                    model_name=model_name,
                    success=False,
                    error=f"Tipo de proveedor desconocido: '{provider_type}'",
                )

            elapsed_ms = int((time.perf_counter() - start) * 1000)
            return LLMCallResult(
                content=content,
                provider_name=provider_name,
                model_name=model_name,
                latency_ms=elapsed_ms,
                success=True,
            )

        except Exception as e:
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            full_error = f"{type(e).__name__}: {str(e)} | Details: {traceback.format_exc()}"
            logger.warning(
                f"[LLMClient] Error con {provider_name}/{model_name}:\n{full_error}"
            )
            return LLMCallResult(
                provider_name=provider_name,
                model_name=model_name,
                latency_ms=elapsed_ms,
                success=False,
                error=full_error,
            )

    # ─────────────────────────────────────────────────────────────────────
    # Provider-specific implementations
    # ─────────────────────────────────────────────────────────────────────

    @staticmethod
    def _call_openai_compatible(
        base_url: str,
        api_key: str,
        model: str,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.3,
        timeout: int = 30,
    ) -> str:
        """
        Single implementation for all OpenAI-compatible providers:
        Groq, Mistral, OpenRouter, GitHub Models, Z.AI, Cerebras, DeepSeek.
        """
        from openai import OpenAI

        client = OpenAI(base_url=base_url, api_key=api_key, timeout=timeout)

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
        )
        return response.choices[0].message.content or ""

    @staticmethod
    def _call_gemini(
        api_key: str,
        model: str,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.3,
        timeout: int = 30,
    ) -> str:
        """
        Google AI Studio via the google-genai SDK.
        """
        from google import genai
        from google.genai import types
        import httpx
        from google.genai.errors import APIError

        # Use native http_options with httpx.Timeout to separate connection/read timeouts
        client = genai.Client(
            api_key=api_key,
            http_options={
                'client_args': {
                    'timeout': httpx.Timeout(connect=30.0, read=float(timeout), write=30.0, pool=30.0)
                }
            }
        )

        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n---\n\n{prompt}"

        try:
            response = client.models.generate_content(
                model=model,
                contents=full_prompt,
                config=types.GenerateContentConfig(
                    temperature=temperature,
                )
            )
            return response.text or ""
        except APIError as e:
            # Fallback a capturar errores nativos de google genai
            raise RuntimeError(f"Error de API de Gemini: {e}") from e
        except Exception as e:
            # Capturar timeouts nativos que genai propague
            e_str = str(e).lower()
            if "timeout" in e_str or "timed out" in e_str:
                raise TimeoutError(
                    f"Gemini falló por timeout. Configurado: {timeout}s. Detalle: {e}"
                ) from e
            raise

    @staticmethod
    def _call_eden_ai(
        api_key: str,
        model: str,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.3,
        timeout: int = 30,
    ) -> str:
        """
        Eden AI text chat generation endpoint.
        model usually comes as 'provider/model' (e.g. 'google/gemma-4').
        """
        import requests

        url = "https://api.edenai.run/v2/text/chat"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        # Split 'google/gemma-4' into provider='google'
        parts = model.split("/")
        provider = parts[0] if len(parts) > 0 else "google"

        payload = {
            "providers": provider,
            "text": prompt,
            "chatbot_global_action": system_prompt,
            "previous_history": [],
            "temperature": temperature,
            "max_tokens": 1500
        }

        resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        
        # Parse standard Eden AI response format
        if provider in data and "generated_text" in data[provider]:
            return data[provider]["generated_text"] or ""
            
        raise ValueError(f"Formato de respuesta inesperado de Eden AI: {data}")
