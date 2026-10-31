"""Vendor defaults and protocol-specific payloads, without paid network requests."""
import json

import httpx
import pytest
from pydantic import SecretStr

from backend.services.llm.base import AnthropicProvider, LLMProviderConfig, OpenAICompatibleProvider, StructuredOutputRequest, provider_from_config
from backend.services.llm_presets import PRESETS
from backend.services import llm_profiles


def test_required_vendors_and_persistence():
    catalog = {item["id"]: item for item in PRESETS}
    assert {"deepseek", "zhipu", "kimi", "claude"} <= catalog.keys()
    for vendor in ["deepseek", "zhipu", "kimi", "claude"]:
        item = catalog[vendor]
        row = llm_profiles.save_profile("alice", llm_profiles.ProfileInput(
            name=item["name"], provider=item["provider"], vendor=vendor,
            api_base_url=item["api_base_url"], model=item["models"][0], api_key="fixture-key"), activate=True)
        config = llm_profiles.profile_configuration("alice")
        assert config.vendor == row["vendor"] == vendor
        assert config.provider == item["provider"]
    assert isinstance(provider_from_config(config), AnthropicProvider)


def test_credentials_cannot_silently_follow_changed_host():
    first = llm_profiles.save_profile("alice", llm_profiles.ProfileInput(name="A", model="a",
        api_base_url="https://api.deepseek.com", api_key="secret"), True)
    changed = llm_profiles.ProfileInput(**{**first, "api_base_url": "https://api.moonshot.cn/v1"})
    with pytest.raises(ValueError, match="密钥"):
        llm_profiles.save_profile("alice", changed)
    result = llm_profiles.save_profile("alice", changed.model_copy(update={"clear_api_key": True}))
    assert not result["has_api_key"]


def request():
    return StructuredOutputRequest(system_prompt="Extract data", user_prompt="Reply with JSON", response_schema_name="Test",
                                   response_schema={"type": "object", "properties": {"ok": {"type": "boolean"}}})


@pytest.mark.asyncio
async def test_anthropic_native_messages_and_text_blocks(monkeypatch):
    original = httpx.AsyncClient
    def handler(req):
        assert str(req.url) == "https://api.anthropic.com/v1/messages"
        assert req.headers["Authorization"] == "Bearer fixture-key"
        assert req.headers["anthropic-version"] == "2026-10-21"
        body = json.loads(req.content)
        assert body["max_tokens"] == 1024
        assert "temperature" not in body and "response_format" not in body
        assert [m["role"] for m in body["messages"]] == ["user"]
        assert "schema" in body["system"]
        return httpx.Response(200, json={"model": "claude-sonnet-5-5", "stop_reason": "end_turn",
            "content": [{"type": "thinking", "thinking": "private reasoning"}, {"type": "text", "text": '```json\n{"ok":true}\n```'}],
            "usage": {"input_tokens": 12, "output_tokens": 8}})
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs))
    provider = provider_from_config(LLMProviderConfig(provider="anthropic", enabled=True, model="claude-sonnet-5-5",
        api_base_url="https://api.anthropic.com", api_key=SecretStr("fixture-key"), max_output_tokens=1024))
    result = await provider.invoke_structured(request())
    assert result.structured_output == {"ok": True}
    assert "private reasoning" not in result.raw_text
    assert result.usage["output_tokens"] == 8


@pytest.mark.asyncio
@pytest.mark.parametrize("vendor,model", [("kimi", "kimi-k3.1-pro"), ("kimi", "kimi-k2.6"), ("deepseek", "deepseek-flash"), ("zhipu", "glm-4.7-flash")])
async def test_openai_vendor_parameter_compatibility(monkeypatch, vendor, model):
    original = httpx.AsyncClient
    def handler(req):
        body = json.loads(req.content)
        assert "temperature" not in body
        assert body["response_format"] == {"type": "json_object"}
        if model.startswith("kimi-k3"):
            assert body["max_completion_tokens"] == 4096 and "max_tokens" not in body
            assert body["reasoning_effort"] == "low"
        elif model == "kimi-k2.6":
            assert body["thinking"] == {"type": "disabled"}
        elif vendor == "zhipu":
            assert body["thinking"] == {"type": "disabled"}
        else:
            assert "thinking" not in body
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"ok":true}'}}]})
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs))
    provider = OpenAICompatibleProvider(LLMProviderConfig(provider="openai_compatible", vendor=vendor, model=model,
        enabled=True, api_base_url="https://fixture.invalid/v1", api_key=SecretStr("key"), max_output_tokens=4096))
    assert (await provider.invoke_structured(request())).structured_output["ok"]
