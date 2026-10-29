"""Tests for authentication, session handling and workspace authorization."""

import pytest

from backend.server.app import app
from backend.services import auth_service
from backend.tests.conftest import SyncASGIClient
from backend.services.auth_service import (
    AuthError,
    CODE_FORBIDDEN,
    Identity,
    ROLE_EDITOR,
    ROLE_OWNER,
    ROLE_VIEWER,
    authorize_workspace,
    workspace_role,
)


@pytest.fixture
def client():
    return SyncASGIClient(app)


def _rpc(client, method, params=None, token=None, request_id=1):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return client.post(
        "/jsonrpc",
        json={"jsonrpc": "2.0", "method": method, "params": params or {}, "id": request_id},
        headers=headers,
    )


def _register_and_login(client, username="alice", password="alice-pass-123"):
    register = _rpc(client, "authRegister", {"username": username, "password": password})
    assert "result" in register.json(), register.json()
    login = _rpc(client, "authLogin", {"username": username, "password": password})
    return login.json()["result"]


class TestSessionProtocol:
    def test_protected_method_rejects_anonymous_callers(self, client):
        response = _rpc(client, "listWorkspaces", {})
        assert response.status_code == 200
        assert response.json()["error"]["code"] == auth_service.CODE_AUTH_REQUIRED

    def test_register_login_and_status(self, client):
        session = _register_and_login(client)
        assert session["token"]
        assert session["user"]["username"] == "alice"

        status = _rpc(client, "authStatus", {}, token=session["token"]).json()
        assert status["result"]["authenticated"] is True
        assert status["result"]["user"]["username"] == "alice"

    def test_login_with_wrong_password_fails(self, client):
        _register_and_login(client)
        login = _rpc(client, "authLogin", {"username": "alice", "password": "wrong-pass"})
        assert login.json()["error"]["code"] == auth_service.CODE_INVALID_CREDENTIALS

    def test_duplicate_username_is_rejected(self, client):
        _register_and_login(client)
        again = _rpc(client, "authRegister", {"username": "alice", "password": "another-pass"})
        assert again.json()["error"]["code"] == auth_service.CODE_USER_EXISTS

    def test_short_password_is_rejected(self, client):
        response = _rpc(client, "authRegister", {"username": "bob", "password": "short"})
        assert response.json()["error"]["code"] == auth_service.CODE_INVALID_REQUEST

    def test_logout_revokes_token(self, client):
        session = _register_and_login(client)
        assert _rpc(client, "authLogout", {}, token=session["token"]).json()["result"]["logged_out"]
        after = _rpc(client, "listWorkspaces", {}, token=session["token"])
        assert after.json()["error"]["code"] == auth_service.CODE_AUTH_REQUIRED

    def test_invalid_token_is_treated_as_anonymous(self, client):
        response = _rpc(client, "listWorkspaces", {}, token="not-a-real-token")
        assert response.json()["error"]["code"] == auth_service.CODE_AUTH_REQUIRED

    def test_demo_user_is_seeded_when_other_users_exist(self, monkeypatch):
        monkeypatch.setenv("ONTOFORGE_SEED_DEMO_USER", "true")
        auth_service.register_user("existing", "existing-pass-123")

        created = auth_service.ensure_demo_user()

        assert created is not None
        assert created["username"] == "demo"
        assert auth_service.authenticate("demo", "demo1234")["username"] == "demo"


class TestIdentitySpoofing:
    def test_owner_id_must_match_authenticated_user(self, client):
        session = _register_and_login(client)
        response = _rpc(
            client,
            "listWorkspaces",
            {"owner_id": "someone-else"},
            token=session["token"],
        )
        assert response.json()["error"]["code"] == CODE_FORBIDDEN

    def test_parse_user_intent_overrides_client_user_id(self, client, monkeypatch):
        from backend.schemas.protocol import ParseUserIntentResponse, ParsedIntentResult
        from unittest.mock import AsyncMock

        captured = {}

        async def fake_parse(request):
            captured["user_id"] = request.user_id
            captured["owner_id"] = request.owner_id
            return ParseUserIntentResponse(
                workspace_id=request.workspace_id,
                parsed_intent=ParsedIntentResult(
                    intent_type="constraint",
                    intent_scope="local",
                    description="fake",
                    constraints={},
                    generalization_hint=None,
                    confidence=0.5,
                    requires_confirmation=False,
                ),
            )

        monkeypatch.setattr("backend.server.jsonrpc_methods.parse_user_intent", fake_parse)

        session = _register_and_login(client)
        response = _rpc(
            client,
            "parseUserIntent",
            {
                "workspace_id": "workspace_test",
                "user_id": "attacker",
                "message": "hi",
            },
            token=session["token"],
        )
        assert "result" in response.json(), response.json()
        assert captured["user_id"] == session["user"]["user_id"]
        assert captured["owner_id"] == session["user"]["user_id"]


class TestWorkspaceRoles:
    def _workspace(self, owner="user_owner", members=None):
        return {
            "id": "workspace_demo",
            "owner_id": owner,
            "metadata": {"members": members or {}},
        }

    def _identity(self, user_id):
        return Identity(user_id=user_id, username=user_id, display_name=user_id)

    def test_owner_has_read_and_write(self):
        workspace = self._workspace()
        authorization = authorize_workspace
        assert workspace_role(workspace, self._identity("user_owner")) == ROLE_OWNER
        authorization(workspace, self._identity("user_owner"), write=True)

    def test_viewer_can_read_but_not_write(self):
        workspace = self._workspace(members={"user_viewer": ROLE_VIEWER})
        viewer = self._identity("user_viewer")
        assert workspace_role(workspace, viewer) == ROLE_VIEWER
        authorize_workspace(workspace, viewer, write=False)
        with pytest.raises(AuthError) as exc:
            authorize_workspace(workspace, viewer, write=True)
        assert exc.value.code == CODE_FORBIDDEN

    def test_editor_can_write(self):
        workspace = self._workspace(members={"user_editor": ROLE_EDITOR})
        authorize_workspace(workspace, self._identity("user_editor"), write=True)

    def test_non_member_is_denied(self):
        workspace = self._workspace()
        with pytest.raises(AuthError) as exc:
            authorize_workspace(workspace, self._identity("user_other"))
        assert exc.value.code == CODE_FORBIDDEN

    def test_add_and_remove_member(self):
        workspace = self._workspace(owner="user_owner")
        auth_service.register_user("carol", "carol-pass-123")
        carol = auth_service.find_user_by_username("carol")
        metadata = auth_service.add_workspace_member(workspace, carol["user_id"], ROLE_VIEWER)
        assert metadata["members"][carol["user_id"]] == ROLE_VIEWER

        updated = dict(workspace, metadata=metadata)
        assert workspace_role(updated, self._identity(carol["user_id"])) == ROLE_VIEWER

        cleared = auth_service.remove_workspace_member(updated, carol["user_id"])
        assert carol["user_id"] not in cleared["members"]


class TestQueryGuard:
    def test_ssp_query_rejects_write_statements(self, client):
        session = _register_and_login(client)
        response = _rpc(
            client,
            "sspQuery",
            {"params": {"query": "MATCH (n) DETACH DELETE n"}},
            token=session["token"],
        )
        error = response.json().get("error")
        assert error is not None
        assert error["code"] == CODE_FORBIDDEN
        assert "Read-only" in error["message"]
