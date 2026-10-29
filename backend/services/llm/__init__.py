"""LLM foundation services for provider abstraction and capability surfacing."""

from .base import (
    LLMProvider,
    LLMProviderConfig,
    LLMProviderStatus,
    StructuredOutputRequest,
    StructuredOutputResult,
    NullLLMProvider,
    MockLLMProvider,
    OpenAICompatibleProvider,
    OllamaProvider,
    get_default_provider,
)
from .capability_registry import (
    CapabilityDefinition,
    CapabilityRegistry,
    build_server_capability_registry,
)
from .intent_parser import parse_user_intent
from .domain_pack_bootstrapper import (
    DomainPackBootstrapper,
    create_domain_pack_bootstrapper,
)

__all__ = [
    "LLMProvider",
    "LLMProviderConfig",
    "LLMProviderStatus",
    "StructuredOutputRequest",
    "StructuredOutputResult",
    "NullLLMProvider",
    "MockLLMProvider",
    "OpenAICompatibleProvider",
    "OllamaProvider",
    "get_default_provider",
    "CapabilityDefinition",
    "CapabilityRegistry",
    "build_server_capability_registry",
    "parse_user_intent",
    "DomainPackBootstrapper",
    "create_domain_pack_bootstrapper",
]