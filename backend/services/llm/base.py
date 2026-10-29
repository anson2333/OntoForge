"""Provider abstraction for the LLM-facing backend foundation."""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, Literal, Optional, Tuple

import httpx
from pydantic import BaseModel, Field


class LLMProviderConfig(BaseModel):
    """Provider configuration shared across concrete LLM implementations."""

    provider: Literal["disabled", "openai_compatible", "anthropic", "ollama", "mock"] = "disabled"
    model: Optional[str] = None
    api_base_url: Optional[str] = None
    api_key_env_var: Optional[str] = None
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    timeout_seconds: int = Field(default=60, ge=1)
    max_output_tokens: Optional[int] = Field(default=None, ge=1)
    enabled: bool = False


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

    def is_configured(self) -> bool:
        if not self.config.enabled:
            return False
        if self.config.provider in {"disabled", "mock"}:
            return self.config.enabled
        if not self.config.model:
            return False
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
        api_key_env_var = self.config.api_key_env_var or "ONTOFORGE_LLM_API_KEY"
        api_key = os.getenv(api_key_env_var)
        if not api_key:
            raise RuntimeError(f"Missing API key in env var {api_key_env_var}")
        return api_key

    def _base_url(self) -> str:
        return (self.config.api_base_url or "https://api.openai.com/v1").rstrip("/")

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key()}",
            "Content-Type": "application/json",
        }

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
        if self.config.max_output_tokens is not None:
            payload["max_tokens"] = self.config.max_output_tokens

        async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
            response = await client.post(
                f"{self._base_url()}/chat/completions",
                headers=self._headers(),
                json=payload,
            )
            response.raise_for_status()
            body = response.json()

        content = body["choices"][0]["message"].get("content") or "{}"
        try:
            structured_output = json.loads(content)
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
        if self.config.max_output_tokens is not None:
            payload["options"]["num_predict"] = self.config.max_output_tokens

        async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
            response = await client.post(f"{self._base_url()}/api/chat", json=payload)
            response.raise_for_status()
            body = response.json()

        content = body.get("message", {}).get("content") or "{}"
        try:
            structured_output = json.loads(content)
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

    if config.provider == "mock":
        return MockLLMProvider(config)
    if config.provider == "openai_compatible":
        return OpenAICompatibleProvider(config)
    if config.provider == "ollama":
        return OllamaProvider(config)
    return NullLLMProvider(config)