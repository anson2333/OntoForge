"""
Authentication and authorization service for OntoForge.

Provides:
- File-backed user registry with PBKDF2 password hashing
- In-memory session tokens with expiry
- Request-scoped identity via contextvars
- Workspace-level access control (owner / members with roles)

The JSON-RPC layer resolves the identity from the login session (token) and
never trusts ``owner_id`` supplied by the caller.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import threading
import time
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from jsonrpcserver.exceptions import JsonRpcError

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

# JSON-RPC server error codes (application range -32000..-32099)
CODE_AUTH_REQUIRED = -32001
CODE_INVALID_CREDENTIALS = -32002
CODE_FORBIDDEN = -32003
CODE_INVALID_REQUEST = -32004
CODE_USER_EXISTS = -32005


class AuthError(JsonRpcError):
    """Raised when authentication or authorization fails.

    Inherits from ``JsonRpcError`` so the JSON-RPC dispatcher converts it into a
    protocol-level error response instead of a generic internal error.
    """

    def __init__(self, code: int, message: str):
        super().__init__(code, message)
        self.code = code
        self.message = message


# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------

ROLE_OWNER = "owner"
ROLE_EDITOR = "editor"
ROLE_VIEWER = "viewer"

_WRITE_ROLES = {ROLE_OWNER, ROLE_EDITOR}


@dataclass(frozen=True)
class Identity:
    """Authenticated caller identity resolved from a session token."""

    user_id: str
    username: str
    display_name: str
    roles: tuple[str, ...] = ("researcher",)
    token: Optional[str] = field(default=None, repr=False)


_current_identity: ContextVar[Optional[Identity]] = ContextVar(
    "ontoforge_current_identity", default=None
)


def get_current_identity() -> Optional[Identity]:
    """Return the identity bound to the current request, if any."""
    return _current_identity.get()


def set_current_identity(identity: Optional[Identity]):
    """Bind an identity to the current context; returns a reset token."""
    return _current_identity.set(identity)


def reset_current_identity(token) -> None:
    _current_identity.reset(token)


def auth_required() -> bool:
    """Whether unauthenticated access to protected methods is rejected."""
    return os.getenv("ONTOFORGE_AUTH_REQUIRED", "true").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


# ---------------------------------------------------------------------------
# User registry
# ---------------------------------------------------------------------------

_DEFAULT_STORE = Path(__file__).resolve().parents[1] / "data" / "users.json"
_USERNAME_RE = re.compile(r"^[A-Za-z0-9_.@-]{3,64}$")
_PBKDF2_ITERATIONS = 200_000


def _store_path() -> Path:
    configured = os.getenv("ONTOFORGE_USER_STORE", "").strip()
    return Path(configured).expanduser() if configured else _DEFAULT_STORE


_lock = threading.RLock()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_store() -> Dict[str, Any]:
    path = _store_path()
    if not path.exists():
        return {"version": 1, "users": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"version": 1, "users": {}}
    data.setdefault("version", 1)
    data.setdefault("users", {})
    return data


def _save_store(data: Dict[str, Any]) -> None:
    path = _store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def _hash_password(password: str, salt: str) -> str:
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), _PBKDF2_ITERATIONS
    )
    return digest.hex()


def _public_user(record: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "user_id": record["user_id"],
        "username": record["username"],
        "display_name": record.get("display_name") or record["username"],
        "roles": list(record.get("roles", ["researcher"])),
        "created_at": record.get("created_at"),
    }


def register_user(
    username: str,
    password: str,
    display_name: Optional[str] = None,
    roles: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Register a new user. Raises AuthError on invalid or duplicate input."""
    username = (username or "").strip()
    if not _USERNAME_RE.match(username):
        raise AuthError(
            CODE_INVALID_REQUEST,
            "Username must be 3-64 characters (letters, digits, . _ @ -)",
        )
    if not password or len(password) < 8:
        raise AuthError(CODE_INVALID_REQUEST, "Password must be at least 8 characters")

    with _lock:
        store = _load_store()
        if username.lower() in {name.lower() for name in store["users"]}:
            raise AuthError(CODE_USER_EXISTS, "Username already exists")

        salt = secrets.token_hex(16)
        user_id = f"user_{username.lower().replace('.', '_').replace('@', '_')}_{uuid_suffix()}"
        record = {
            "user_id": user_id,
            "username": username,
            "display_name": (display_name or username).strip(),
            "roles": roles or ["researcher"],
            "salt": salt,
            "password_hash": _hash_password(password, salt),
            "created_at": _now_iso(),
        }
        store["users"][username] = record
        _save_store(store)
        return _public_user(record)


def uuid_suffix() -> str:
    return secrets.token_hex(4)


def authenticate(username: str, password: str) -> Dict[str, Any]:
    """Verify credentials and return the public user record."""
    username = (username or "").strip()
    with _lock:
        store = _load_store()
        record = store["users"].get(username)
        if record is None:
            # case-insensitive fallback
            for name, candidate in store["users"].items():
                if name.lower() == username.lower():
                    record = candidate
                    break
        if record is None:
            raise AuthError(CODE_INVALID_CREDENTIALS, "Invalid username or password")

        expected = record.get("password_hash", "")
        actual = _hash_password(password or "", record.get("salt", ""))
        if not secrets.compare_digest(expected, actual):
            raise AuthError(CODE_INVALID_CREDENTIALS, "Invalid username or password")
        return _public_user(record)


def get_user(user_id: str) -> Optional[Dict[str, Any]]:
    with _lock:
        store = _load_store()
        for record in store["users"].values():
            if record.get("user_id") == user_id:
                return _public_user(record)
    return None


def find_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    with _lock:
        store = _load_store()
        record = store["users"].get(username)
        if record is None:
            for name, candidate in store["users"].items():
                if name.lower() == (username or "").lower():
                    record = candidate
                    break
        return _public_user(record) if record else None


def user_exists(user_id: str) -> bool:
    return get_user(user_id) is not None


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

_SESSION_TTL_SECONDS = int(os.getenv("ONTOFORGE_SESSION_TTL_SECONDS", "28800"))

_sessions: Dict[str, Dict[str, Any]] = {}
_sessions_lock = threading.RLock()


def create_session(user: Dict[str, Any]) -> Dict[str, Any]:
    """Create a session token for a user record (public form)."""
    token = secrets.token_urlsafe(32)
    now = time.time()
    expires_at = now + _SESSION_TTL_SECONDS
    with _sessions_lock:
        _prune_sessions_locked(now)
        _sessions[token] = {
            "user_id": user["user_id"],
            "username": user["username"],
            "display_name": user.get("display_name") or user["username"],
            "roles": tuple(user.get("roles", ["researcher"])),
            "created_at": now,
            "expires_at": expires_at,
        }
    return {
        "token": token,
        "user": {
            "user_id": user["user_id"],
            "username": user["username"],
            "display_name": user.get("display_name") or user["username"],
            "roles": list(user.get("roles", ["researcher"])),
        },
        "expires_at": datetime.fromtimestamp(expires_at, timezone.utc).isoformat(),
    }


def _prune_sessions_locked(now: float) -> None:
    expired = [token for token, data in _sessions.items() if data["expires_at"] <= now]
    for token in expired:
        _sessions.pop(token, None)


def resolve_session(token: Optional[str]) -> Optional[Identity]:
    """Resolve a session token into an Identity, or None if invalid/expired."""
    if not token:
        return None
    now = time.time()
    with _sessions_lock:
        data = _sessions.get(token)
        if data is None:
            return None
        if data["expires_at"] <= now:
            _sessions.pop(token, None)
            return None
        return Identity(
            user_id=data["user_id"],
            username=data["username"],
            display_name=data["display_name"],
            roles=tuple(data["roles"]),
            token=token,
        )


def revoke_session(token: Optional[str]) -> bool:
    if not token:
        return False
    with _sessions_lock:
        return _sessions.pop(token, None) is not None


def set_session_intent_branch(
    identity: Optional[Identity], branch_id: Optional[str]
) -> Optional[str]:
    """Set the active intent branch for this login session and return the previous one."""
    if identity is None or not identity.token:
        return None
    with _sessions_lock:
        session = _sessions.get(identity.token)
        if session is None:
            return None
        previous = session.get("active_intent_branch")
        if branch_id:
            session["active_intent_branch"] = branch_id
        else:
            session.pop("active_intent_branch", None)
        return previous


def session_count() -> int:
    with _sessions_lock:
        _prune_sessions_locked(time.time())
        return len(_sessions)


# ---------------------------------------------------------------------------
# Workspace authorization
# ---------------------------------------------------------------------------


def workspace_role(workspace: Dict[str, Any], identity: Optional[Identity]) -> Optional[str]:
    """Return the caller's role in a workspace, or None without access."""
    if not workspace or identity is None:
        return None

    metadata = workspace.get("metadata") or {}
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except json.JSONDecodeError:
            metadata = {}

    owner_id = workspace.get("owner_id")
    members = metadata.get("members") or {}
    if owner_id == identity.user_id:
        return ROLE_OWNER
    if identity.user_id in members:
        role = members[identity.user_id]
        return role if role in {ROLE_OWNER, ROLE_EDITOR, ROLE_VIEWER} else ROLE_VIEWER

    # Legacy workspaces created before the owner field existed stay readable,
    # but are only writable by the authenticated owner.
    if owner_id is None:
        return ROLE_VIEWER
    return None


def can_access_workspace(workspace: Dict[str, Any], identity: Optional[Identity]) -> bool:
    if identity is None:
        return False
    return workspace_role(workspace, identity) is not None


def can_write_workspace(workspace: Dict[str, Any], identity: Optional[Identity]) -> bool:
    return workspace_role(workspace, identity) in _WRITE_ROLES


def authorize_workspace(
    workspace: Dict[str, Any], identity: Optional[Identity], write: bool = False
) -> None:
    """Raise AuthError when the caller may not access the workspace."""
    if identity is None:
        raise AuthError(CODE_AUTH_REQUIRED, "Authentication required")
    role = workspace_role(workspace, identity)
    if role is None:
        raise AuthError(CODE_FORBIDDEN, "Workspace not found or not accessible")
    if write and role not in _WRITE_ROLES:
        raise AuthError(CODE_FORBIDDEN, "Write access denied for this workspace")


def add_workspace_member(
    workspace: Dict[str, Any], user_id: str, role: str = ROLE_VIEWER
) -> Dict[str, Any]:
    """Return updated workspace metadata with a new member entry."""
    if role not in {ROLE_OWNER, ROLE_EDITOR, ROLE_VIEWER}:
        raise AuthError(CODE_INVALID_REQUEST, f"Unknown role: {role}")
    if not user_exists(user_id):
        raise AuthError(CODE_INVALID_REQUEST, "Unknown user_id")
    if workspace.get("owner_id") == user_id:
        raise AuthError(CODE_INVALID_REQUEST, "Owner is already a member")

    metadata = dict(workspace.get("metadata") or {})
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except json.JSONDecodeError:
            metadata = {}
    members = dict(metadata.get("members") or {})
    members[user_id] = role
    metadata["members"] = members
    return metadata


def remove_workspace_member(workspace: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    metadata = dict(workspace.get("metadata") or {})
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except json.JSONDecodeError:
            metadata = {}
    members = dict(metadata.get("members") or {})
    if user_id not in members:
        raise AuthError(CODE_INVALID_REQUEST, "User is not a member of this workspace")
    members.pop(user_id)
    metadata["members"] = members
    return metadata


# ---------------------------------------------------------------------------
# Demo bootstrap
# ---------------------------------------------------------------------------


def ensure_demo_user() -> Optional[Dict[str, Any]]:
    """Create a demo account on first start so the app is usable out of the box."""
    if os.getenv("ONTOFORGE_SEED_DEMO_USER", "true").strip().lower() in {
        "0",
        "false",
        "no",
        "off",
    }:
        return None

    existing = find_user_by_username("demo")
    if existing:
        return None

    password = os.getenv("ONTOFORGE_DEMO_PASSWORD", "demo1234")
    try:
        return register_user("demo", password, display_name="Demo Researcher")
    except AuthError:
        return None
