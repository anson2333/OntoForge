"""Failed model credentials must be caught before saving or starting bulk extraction."""
import json

import httpx
import pytest

from backend.server.app import app
from backend.services import llm_profiles
from backend.services.llm.base import LLMProviderConfig, MockLLMProvider, OpenAICompatibleProvider, StructuredOutputResult
from backend.services.llm.semantic_extractor import SemanticExtractor
from backend.services.pdf_ingestion_service import load_domain_pack_config
from backend.schemas.protocol import ExtractedChunk
from backend.tests.conftest import SyncASGIClient
from backend.tests.test_auth import _rpc, _register_and_login


@pytest.mark.asyncio
@pytest.mark.parametrize("protocol", ["openai_compatible", "anthropic", "ollama"])
async def test_connection_probe_accepts_plain_text_without_json_mode(monkeypatch, protocol):
    from backend.server.jsonrpc_methods import _check_model_configuration
    original_client = httpx.AsyncClient
    def respond(request):
        payload = json.loads(request.content)
        assert "response_format" not in payload and "format" not in payload
        assert "schema" not in payload.get("system", "").lower()
        if protocol == "anthropic":
            body = {"content": [{"type": "text", "text": "你好，接口连接正常。"}], "stop_reason": "end_turn"}
        elif protocol == "ollama":
            body = {"message": {"content": "你好，接口连接正常。"}}
        else:
            body = {"choices": [{"message": {"content": "你好，接口连接正常。"}, "finish_reason": "stop"}]}
        return httpx.Response(200, json=body)
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original_client(transport=httpx.MockTransport(respond), **kwargs))
    config = LLMProviderConfig(provider=protocol, model="fixture", enabled=True, api_base_url="http://fixture.invalid/v1", api_key_env_var="FIXTURE_KEY")
    monkeypatch.setenv("FIXTURE_KEY", "test-key")
    result = await _check_model_configuration(config)
    assert result["healthy"] and "正常回复" in result["message"]


def test_save_validates_before_persisting_or_activating(monkeypatch):
    client = SyncASGIClient(app)
    login = _register_and_login(client, "save_validation")
    token = login["token"]
    user = login["user"]["user_id"]
    profile = {"name": "Verified", "provider": "openai_compatible", "api_base_url": "https://fixture.invalid/v1", "model": "test", "api_key": "valid"}
    calls = []
    async def invoke(self, request):
        key = self._api_key()
        calls.append(key)
        if key != "valid":
            response = httpx.Response(401, request=httpx.Request("POST", "https://fixture.invalid"))
            raise httpx.HTTPStatusError("must not leak a key", request=response.request, response=response)
        return StructuredOutputResult(provider="openai_compatible", structured_output={"ok": True}, raw_text="OK")
    monkeypatch.setattr(OpenAICompatibleProvider, "invoke_structured", invoke)
    bad = _rpc(client, "saveLLMProfile", {"profile": {**profile, "api_key": "invalid"}, "activate": True}, token=token).json()
    assert "401" in bad["error"]["message"]
    assert llm_profiles.list_profiles(user)["profiles"] == []
    saved = _rpc(client, "saveLLMProfile", {"profile": profile, "activate": True}, token=token).json()["result"]
    profile_id = saved["profile"]["id"]
    failed_edit = _rpc(client, "saveLLMProfile", {"profile": {**profile, "id": profile_id, "api_key": "invalid"}, "activate": True}, token=token).json()
    assert "error" in failed_edit
    assert llm_profiles.profile_configuration(user).api_key.get_secret_value() == "valid"
    assert llm_profiles.active_connection(user)["healthy"]
    assert calls == ["invalid", "valid", "invalid"]


@pytest.mark.asyncio
async def test_401_aborts_remaining_batches_without_repeating_request(monkeypatch):
    monkeypatch.setenv("ONTOFORGE_LLM_CHUNK_BATCH_SIZE", "1")
    calls = []
    class Provider(MockLLMProvider):
        async def invoke_structured(self, request):
            calls.append(request)
            response = httpx.Response(401, request=httpx.Request("POST", "https://fixture.invalid"))
            raise httpx.HTTPStatusError("sensitive body hidden", request=response.request, response=response)
    extractor = SemanticExtractor(Provider(LLMProviderConfig(provider="mock", enabled=True)))
    result = await extractor.extract_assertions([ExtractedChunk(chunk_id=str(i), raw_text="text", bounding_box={}) for i in range(3)], [],
        load_domain_pack_config("optical"), "optical")
    assert not result and len(calls) == 1
    assert extractor.diagnostics["skipped_batches"] == [1, 2]
    assert not extractor.diagnostics["retryable"]
    assert "401" in extractor.diagnostics["warnings"][0]
    assert "sensitive body" not in json.dumps(extractor.diagnostics)


def test_old_runtime_failure_cannot_mark_changed_credentials_bad():
    profile = llm_profiles.ProfileInput(name="A", model="test", api_base_url="https://fixture.invalid", api_key="old")
    saved = llm_profiles.save_profile("alice", profile, True)
    old_config = llm_profiles.profile_configuration("alice")
    llm_profiles.save_profile("alice", profile.model_copy(update={"id": saved["id"], "api_key": "new"}))
    llm_profiles.record_connection(old_config, False, "old request failed")
    assert llm_profiles.active_connection("alice") is None
