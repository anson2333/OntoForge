"""Provider abstraction for the LLM-facing backend foundation."""

from __future__ import annotations

import json
import os
import re
from abc import ABC, abstractmethod
from typing import Any, Dict, Literal, Optional, Tuple

import httpx
from pydantic import BaseModel, Field, SecretStr


class LLMProviderConfig(BaseModel):
    """Provider configuration shared across concrete LLM implementations."""

    provider: Literal["disabled", "openai_compatible", "anthropic", "ollama", "mock"] = "disabled"
    model: Optional[str] = None
    api_base_url: Optional[str] = None
    api_key_env_var: Optional[str] = None
    api_key: Optional[SecretStr] = Field(default=None, exclude=True, repr=False)
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    timeout_seconds: int = Field(default=60, ge=1)
    max_output_tokens: Optional[int] = Field(default=None, ge=1)
    enabled: bool = False
    vendor: str = "custom"
    profile_id: Optional[str] = Field(default=None, exclude=True)
    profile_user_id: Optional[str] = Field(default=None, exclude=True, repr=False)
    profile_revision: Optional[str] = Field(default=None, exclude=True, repr=False)


class LLMProviderStatus(BaseModel):
    """Inspectable runtime status for an LLM provider."""

    provider: str
    model: Optional[str] = None
    enabled: bool
    configured: bool
    healthy: bool
    message: str


class StructuredOutputRequest(BaseModel):
    """Normalized structured-output request passed to a provider."""

    system_prompt: str
    user_prompt: str
    response_schema_name: str
    response_schema: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class StructuredOutputResult(BaseModel):
    """Normalized structured-output result returned by a provider."""

    provider: str
    model: Optional[str] = None
    structured_output: Dict[str, Any] = Field(default_factory=dict)
    raw_text: Optional[str] = None
    usage: Dict[str, Any] = Field(default_factory=dict)
    finish_reason: Optional[str] = None


class LLMProvider(ABC):
    """Abstract provider interface for structured LLM requests."""

    def __init__(self, config: LLMProviderConfig):
        self.config = config

    @property
    def name(self) -> str:
        return self.config.provider

    def record_connection(self, healthy: bool, message: str) -> None:
        from backend.services.llm_profiles import record_connection
        record_connection(self.config, healthy, message)

    def is_configured(self) -> bool:
        if not self.config.enabled:
            return False
        if self.config.provider in {"disabled", "mock"}:
            return self.config.enabled
        if not self.config.model:
            return False
        if self.config.api_key is not None:
            if self.config.vendor in {"deepseek", "zhipu", "kimi", "claude"}:
                return bool(self.config.api_key.get_secret_value())
            return True  # Custom profiles may intentionally use a keyless local endpoint.
        if self.config.api_key_env_var:
            return bool(os.getenv(self.config.api_key_env_var))
        return True

    def check_health(self) -> Tuple[bool, str]:
        """Perform a cheap configuration or connectivity health check."""
        if not self.config.enabled:
            return False, "LLM provider is disabled (paper ingestion will use fallback classification)"
        if not self.is_configured():
            return False, "LLM provider is enabled but not fully configured"
        return True, "LLM provider is configured"

    def get_status(self) -> LLMProviderStatus:
        configured = self.is_configured()
        healthy, message = self.check_health()

        return LLMProviderStatus(
            provider=self.name,
            model=self.config.model,
            enabled=self.config.enabled,
            configured=configured,
            healthy=healthy,
            message=message,
        )

    @abstractmethod
    async def invoke_structured(self, request: StructuredOutputRequest) -> StructuredOutputResult:
        """Execute a structured LLM request."""


class NullLLMProvider(LLMProvider):
    """Safe default provider used before a real model integration exists."""

    async def invoke_structured(self, request: StructuredOutputRequest) -> StructuredOutputResult:
        raise RuntimeError("LLM provider is not configured")


class MockLLMProvider(LLMProvider):
    """Deterministic provider used for local development and smoke testing."""

    async def invoke_structured(self, request: StructuredOutputRequest) -> StructuredOutputResult:
        return StructuredOutputResult(
            provider=self.name,
            model=self.config.model or "mock-model",
            structured_output={
                "schema": request.response_schema_name,
                "echo": request.user_prompt,
                "metadata": request.metadata,
            },
            raw_text=json.dumps({"ok": True}),
            usage={"input_tokens": 0, "output_tokens": 0},
            finish_reason="stop",
        )


class OpenAICompatibleProvider(LLMProvider):
    """Provider for OpenAI-compatible chat-completions APIs."""

    def _api_key(self) -> str:
        if self.config.api_key is not None:
            return self.config.api_key.get_secret_value()
        api_key_env_var = self.config.api_key_env_var or "ONTOFORGE_LLM_API_KEY"
        api_key = os.getenv(api_key_env_var)
        if not api_key:
            raise RuntimeError(f"Missing API key in env var {api_key_env_var}")
        return api_key

    def _base_url(self) -> str:
        return (self.config.api_base_url or "https://api.openai.com/v1").rstrip("/")

    def _headers(self) -> Dict[str, str]:
        key = self._api_key()
        return {"Content-Type": "application/json", **({"Authorization": f"Bearer {key}"} if key else {})}

    def check_health(self) -> Tuple[bool, str]:
        configured, message = super().check_health()
        if not configured:
            return configured, message

        try:
            with httpx.Client(timeout=self.config.timeout_seconds) as client:
                response = client.get(f"{self._base_url()}/models", headers=self._headers())
                response.raise_for_status()
            return True, "OpenAI-compatible provider is reachable"
        except Exception as exc:
            return False, f"OpenAI-compatible provider health check failed: {exc}"

    async def invoke_structured(self, request: StructuredOutputRequest) -> StructuredOutputResult:
        payload: Dict[str, Any] = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
            "temperature": self.config.temperature,
            "response_format": {"type": "json_object"},
        }
        if (request.metadata.get("connection_probe") or request.metadata.get("flexible_output")):
            payload.pop("response_format", None)
        if self.config.max_output_tokens is not None:
            token_parameter = "max_completion_tokens" if self.config.vendor == "kimi" and (self.config.model or "").startswith("kimi-k3") else "max_tokens"
            payload[token_parameter] = self.config.max_output_tokens
        if self.config.vendor in {"kimi", "deepseek", "zhipu"}:
            payload.pop("temperature", None)
        if self.config.vendor == "kimi":
            if (self.config.model or "").startswith("kimi-k2.6"):
                payload["thinking"] = {"type": "disabled"}
            elif (self.config.model or "").startswith("kimi-k3"):
                payload["reasoning_effort"] = "low"
        if self.config.vendor == "zhipu" and (self.config.model or "").lower().startswith("glm-4.7"):
            # Structured extraction needs answer tokens rather than spending the
            # entire configured output budget on GLM-4.7's default thinking.
            payload["thinking"] = {"type": "disabled"}
        if self.config.vendor == "deepseek" and request.metadata.get("flexible_output"):
            # Extraction needs the answer within the configured output budget.
            payload["thinking"] = {"type": "disabled"}

        async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
            post = client.post
            if self.config.vendor == "zhipu":
                from backend.services.llm.zhipu_requests import post_serialized
                async def post(url, **kwargs):
                    return await post_serialized(client, url, **kwargs)
            response = await post(
                f"{self._base_url()}/chat/completions",
                headers=self._headers(),
                json=payload,
            )
            response.raise_for_status()
            body = response.json()

        content = body["choices"][0]["message"].get("content") or ""
        try:
            structured_output = {} if (request.metadata.get("connection_probe") or request.metadata.get("flexible_output")) else json.loads(content)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Provider returned non-JSON structured output: {exc}") from exc

        return StructuredOutputResult(
            provider=self.name,
            model=body.get("model", self.config.model),
            structured_output=structured_output,
            raw_text=content,
            usage=body.get("usage", {}),
            finish_reason=body["choices"][0].get("finish_reason"),
        )


class AnthropicProvider(OpenAICompatibleProvider):
    """Claude's native Messages protocol; structured JSON is prompted and validated."""

    def _base_url(self) -> str:
        base = (self.config.api_base_url or "https://api.anthropic.com/v1").rstrip("/")
        return base if base.endswith("/v1") else base + "/v1"

    def _headers(self) -> Dict[str, str]:
        key = self._api_key()
        return {"Content-Type": "application/json", "anthropic-version": "2026-10-21",
                **({"Authorization": f"Bearer {key}"} if key else {})}

    async def invoke_structured(self, request: StructuredOutputRequest) -> StructuredOutputResult:
        payload = {"model": self.config.model, "max_tokens": self.config.max_output_tokens or 4096,
                   "system": request.system_prompt + "\nReturn only a valid JSON object matching this schema (no markdown):\n" + json.dumps(request.response_schema),
                   "messages": [{"role": "user", "content": request.user_prompt}]}
        if (request.metadata.get("connection_probe") or request.metadata.get("flexible_output")):
            payload["system"] = request.system_prompt
        async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
            response = await client.post(f"{self._base_url()}/messages", headers=self._headers(), json=payload)
            response.raise_for_status()
            body = response.json()
        if body.get("stop_reason") == "max_tokens":
            raise RuntimeError("Model output was truncated; increase the output token limit")
        content = "\n".join(block["text"] for block in body.get("content", []) if block.get("type") == "text").strip()
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", content).strip()
        try:
            output = {} if (request.metadata.get("connection_probe") or request.metadata.get("flexible_output")) else json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Claude did not return valid JSON") from exc
        if not isinstance(output, dict):
            raise RuntimeError("Claude must return a JSON object")
        return StructuredOutputResult(provider=self.name, model=body.get("model", self.config.model),
            structured_output=output, raw_text=content, usage=body.get("usage", {}), finish_reason=body.get("stop_reason"))


class OllamaProvider(LLMProvider):
    """Provider for Ollama chat/generate APIs."""

    def _base_url(self) -> str:
        return (self.config.api_base_url or "http://localhost:11434").rstrip("/")

    def check_health(self) -> Tuple[bool, str]:
        configured, message = super().check_health()
        if not configured:
            return configured, message

        try:
            with httpx.Client(timeout=self.config.timeout_seconds) as client:
                response = client.get(f"{self._base_url()}/api/tags")
                response.raise_for_status()
            return True, "Ollama provider is reachable"
        except Exception as exc:
            return False, f"Ollama provider health check failed: {exc}"

    async def invoke_structured(self, request: StructuredOutputRequest) -> StructuredOutputResult:
        payload: Dict[str, Any] = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
            "stream": False,
            "format": "json",
            "options": {
                "temperature": self.config.temperature,
            },
        }
        if (request.metadata.get("connection_probe") or request.metadata.get("flexible_output")):
            payload.pop("format", None)
        if self.config.max_output_tokens is not None:
            payload["options"]["num_predict"] = self.config.max_output_tokens

        async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
            response = await client.post(f"{self._base_url()}/api/chat", json=payload)
            response.raise_for_status()
            body = response.json()

        content = body.get("message", {}).get("content") or ""
        try:
            structured_output = {} if (request.metadata.get("connection_probe") or request.metadata.get("flexible_output")) else json.loads(content)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Provider returned non-JSON structured output: {exc}") from exc

        return StructuredOutputResult(
            provider=self.name,
            model=body.get("model", self.config.model),
            structured_output=structured_output,
            raw_text=content,
            usage={
                "prompt_eval_count": body.get("prompt_eval_count"),
                "eval_count": body.get("eval_count"),
            },
            finish_reason=body.get("done_reason"),
        )


def get_default_provider() -> LLMProvider:
    """Construct the default provider from environment configuration."""

    from backend.services.auth_service import get_current_identity
    from backend.services.llm_profiles import profile_configuration
    identity = get_current_identity()
    if identity is not None:
        saved = profile_configuration(identity.user_id)
        if saved is not None:
            return provider_from_config(saved)
    provider_name = os.getenv("ONTOFORGE_LLM_PROVIDER", "disabled")
    config = LLMProviderConfig(
        provider=provider_name if provider_name in {"disabled", "openai_compatible", "anthropic", "ollama", "mock"} else "disabled",
        model=os.getenv("ONTOFORGE_LLM_MODEL"),
        api_base_url=os.getenv("ONTOFORGE_LLM_API_BASE_URL"),
        api_key_env_var=os.getenv("ONTOFORGE_LLM_API_KEY_ENV", "ONTOFORGE_LLM_API_KEY"),
        temperature=float(os.getenv("ONTOFORGE_LLM_TEMPERATURE", "0.0")),
        timeout_seconds=int(os.getenv("ONTOFORGE_LLM_TIMEOUT_SECONDS", "60")),
        max_output_tokens=int(os.getenv("ONTOFORGE_LLM_MAX_OUTPUT_TOKENS")) if os.getenv("ONTOFORGE_LLM_MAX_OUTPUT_TOKENS") else None,
        enabled=os.getenv("ONTOFORGE_LLM_ENABLED", "false").lower() == "true",
    )

    return provider_from_config(config)


def provider_from_config(config: LLMProviderConfig) -> LLMProvider:
    if config.provider == "mock":
        return MockLLMProvider(config)
    if config.provider == "openai_compatible":
        return OpenAICompatibleProvider(config)
    if config.provider == "anthropic":
        return AnthropicProvider(config)
    if config.provider == "ollama":
        return OllamaProvider(config)
    return NullLLMProvider(config)
