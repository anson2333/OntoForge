"""Endpoint profile persistence, credential safety and request-scoped switching."""
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.services import llm_profiles as profiles
from backend.services.auth_service import Identity, set_current_identity, reset_current_identity
from backend.services.llm.base import get_default_provider, OpenAICompatibleProvider, StructuredOutputResult
from backend.server.app import app, redact_payload
from backend.tests.conftest import SyncASGIClient
from backend.tests.test_auth import _rpc, _register_and_login


def draft(**changes):
    return profiles.ProfileInput(name="Primary", model="model-a", api_base_url="https://example.invalid/v1",
                                 **changes)


def test_secret_is_protected_and_never_returned(monkeypatch):
    import os
    saved = profiles.save_profile("alice", draft(api_key="secret-for-test"), activate=True)
    assert saved["has_api_key"]
    assert "secret-for-test" not in json.dumps(saved)
    assert "credential" not in saved
    path = profiles._path()
    assert path.exists()
    if os.name == "nt":
        assert "secret-for-test" not in path.read_text(encoding="utf-8")
    config = profiles.profile_configuration("alice")
    assert config.api_key.get_secret_value() == "secret-for-test"
    assert "secret-for-test" not in repr(config)
    assert "api_key" not in config.model_dump()


def test_edit_keeps_key_and_clear_removes_it():
    saved = profiles.save_profile("alice", draft(api_key="first-key"), True)
    edited = profiles.ProfileInput(**{**saved, "api_key": "", "model": "model-b"})
    profiles.save_profile("alice", edited)
    assert profiles.profile_configuration("alice").api_key.get_secret_value() == "first-key"
    profiles.save_profile("alice", edited.model_copy(update={"clear_api_key": True}))
    assert not profiles.list_profiles("alice")["profiles"][0]["has_api_key"]
    assert profiles.profile_configuration("alice").api_key.get_secret_value() == ""


def test_switch_is_persistent_user_scoped_and_does_not_change_environment(monkeypatch):
    monkeypatch.setenv("ONTOFORGE_LLM_PROVIDER", "disabled")
    a = profiles.save_profile("alice", draft(api_key="alice-key"), True)
    b = profiles.save_profile("alice", draft(api_key="second-key").model_copy(update={"name": "Secondary", "model": "model-b"}))
    profiles.activate_profile("alice", b["id"])
    identity = set_current_identity(Identity(user_id="alice", username="alice", display_name="Alice"))
    try:
        assert get_default_provider().config.model == "model-b"
        profiles.activate_profile("alice", a["id"])
        assert get_default_provider().config.model == "model-a"
    finally:
        reset_current_identity(identity)
    assert get_default_provider().name == "disabled"
    assert profiles.list_profiles("bob")["profiles"] == []
    with pytest.raises(ValueError):
        profiles.activate_profile("bob", a["id"])
    with pytest.raises(ValueError):
        profiles.delete_profile("bob", a["id"])
    with pytest.raises(ValueError):
        profiles.save_profile("bob", draft(id=a["id"]))
    profiles.delete_profile("alice", a["id"])
    assert profiles.profile_configuration("alice") is None


def test_parallel_saves_do_not_lose_profiles():
    with ThreadPoolExecutor(max_workers=3) as workers:
        list(workers.map(lambda i: profiles.save_profile("alice", draft().model_copy(update={"name": str(i)})), range(8)))
    assert len(profiles.list_profiles("alice")["profiles"]) == 8


@pytest.mark.parametrize("url", ["file:///tmp/key", "https://user:pass@example.org/v1", "https://example.org?api_key=key", "https://example.org/v1/chat/completions"])
def test_invalid_urls_are_rejected(url):
    with pytest.raises(ValidationError):
        profiles.ProfileInput(name="A", model="A", api_base_url=url)


def test_keyless_profile_never_reuses_environment_key(monkeypatch):
    monkeypatch.setenv("ONTOFORGE_LLM_API_KEY", "environment-secret")
    profiles.save_profile("alice", draft(), True)
    provider = OpenAICompatibleProvider(profiles.profile_configuration("alice"))
    assert "Authorization" not in provider._headers()


def test_profile_api_authentication_and_testing(monkeypatch):
    client = SyncASGIClient(app)
    for method, params in [("listLLMProfiles", {}), ("saveLLMProfile", {"profile": {}}),
                           ("activateLLMProfile", {}), ("deleteLLMProfile", {"profile_id": "x"}),
                           ("testLLMProfile", {"profile_id": "x"})]:
        assert _rpc(client, method, params).json()["error"]["code"] == -32001
    alice = _register_and_login(client, "profile_alice")
    bob = _register_and_login(client, "profile_bob")
    params = {"profile": {"name": "A", "model": "model-a", "api_base_url": "https://example.invalid/v1", "api_key": "secret-for-test"}, "activate": True}
    async def fake_call(self, request):
        assert self._headers()["Authorization"] == "Bearer secret-for-test"
        return StructuredOutputResult(provider="openai_compatible", structured_output={"ok": True}, raw_text="OK", usage={"total_tokens": 4})
    monkeypatch.setattr(OpenAICompatibleProvider, "invoke_structured", fake_call)
    result = _rpc(client, "saveLLMProfile", params, token=alice["token"]).json()["result"]
    profile_id = result["profile"]["id"]
    assert "secret-for-test" not in json.dumps(result)
    assert _rpc(client, "listLLMProfiles", token=bob["token"]).json()["result"]["profiles"] == []
    assert "error" in _rpc(client, "activateLLMProfile", {"profile_id": profile_id}, token=bob["token"]).json()
    tested = _rpc(client, "testLLMProfile", {"profile_id": profile_id}, token=alice["token"]).json()["result"]
    assert tested["healthy"] and tested["usage"]["total_tokens"] == 4
    monkeypatch.setattr(OpenAICompatibleProvider, "check_health", lambda _: (_ for _ in ()).throw(AssertionError("status must not call network")))
    assert _rpc(client, "getLLMStatus", token=alice["token"]).json()["result"]["model"] == "model-a"
    async def failed_call(self, request):
        raise RuntimeError("sensitive secret-for-test in upstream exception")
    monkeypatch.setattr(OpenAICompatibleProvider, "invoke_structured", failed_call)
    failed = _rpc(client, "testLLMProfile", {"profile_id": profile_id}, token=alice["token"]).json()["result"]
    assert not failed["healthy"] and "secret-for-test" not in json.dumps(failed)
    assert redact_payload({"profile": {"api_key": "secret-for-test"}})["profile"]["api_key"] == "<hidden>"
