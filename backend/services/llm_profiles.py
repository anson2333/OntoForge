"""User-scoped, persistent endpoint profiles. Saved credentials never leave the server."""
from __future__ import annotations

import base64
import ctypes
import json
import hashlib
from datetime import datetime, timezone
import os
import threading
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

_lock = threading.RLock()


class ProfileInput(BaseModel):
    id: str | None = None
    name: str = Field(min_length=1, max_length=100)
    provider: str = "openai_compatible"
    vendor: str = "custom"
    api_base_url: str
    model: str = Field(min_length=1, max_length=200)
    api_key: str | None = Field(default=None, repr=False, exclude=True)
    clear_api_key: bool = False
    timeout_seconds: int = Field(default=60, ge=1, le=600)
    temperature: float = Field(default=0, ge=0, le=2)
    max_output_tokens: int | None = Field(default=4096, ge=1, le=131072)

    @field_validator("name", "model", "api_base_url", "api_key", mode="before")
    @classmethod
    def trim(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("provider")
    @classmethod
    def provider_type(cls, value):
        if value not in {"openai_compatible", "ollama", "anthropic"}:
            raise ValueError("Choose openai_compatible, anthropic or ollama")
        return value

    @field_validator("vendor")
    @classmethod
    def vendor_type(cls, value):
        from backend.services.llm_presets import get_preset
        if value != "custom" and get_preset(value) is None:
            raise ValueError("Unknown vendor preset")
        return value

    @field_validator("api_base_url")
    @classmethod
    def endpoint(cls, value):
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("Use a complete http:// or https:// base URL")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Keep credentials, query parameters and fragments out of the base URL")
        if parsed.path.rstrip("/").endswith(("/chat/completions", "/models", "/messages")):
            raise ValueError("Use the base URL (usually ending /v1), not a specific API route")
        return value.rstrip("/")


def _path():
    return Path(os.getenv("ONTOFORGE_LLM_PROFILE_STORE", str(Path(__file__).resolve().parents[1] / "data/llm-profiles.json")))


def _read():
    path = _path()
    if not path.exists():
        return {"version": 1, "users": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def _write(data):
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_name(f"{path.name}.{uuid4().hex}.tmp")
    try:
        pending.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        pending.chmod(0o600)
        pending.replace(path)
    finally:
        pending.unlink(missing_ok=True)


def _dpapi(raw: bytes, decrypt=False) -> bytes:
    """Bind Windows secrets to the OS account running this backend."""
    from ctypes import wintypes
    class Blob(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_ubyte))]
    buffer = ctypes.create_string_buffer(raw)
    source = Blob(len(raw), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    output = Blob()
    crypt = ctypes.windll.crypt32
    if decrypt:
        success = crypt.CryptUnprotectData(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(output))
    else:
        success = crypt.CryptProtectData(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(output))
    if not success:
        raise OSError("Windows credential protection failed")
    try:
        return ctypes.string_at(output.data, output.size)
    finally:
        ctypes.windll.kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        ctypes.windll.kernel32.LocalFree(output.data)


def _protect(value: str):
    raw = value.encode()
    return ("dpapi:" + base64.b64encode(_dpapi(raw)).decode()) if os.name == "nt" else "local:" + value


def _unprotect(value: str):
    if value.startswith("dpapi:"):
        if os.name != "nt":
            raise ValueError("This credential must be re-entered on the current OS account")
        return _dpapi(base64.b64decode(value[6:]), decrypt=True).decode()
    return value.removeprefix("local:")


def _user(data, user_id):
    return data["users"].setdefault(user_id, {"active_id": None, "profiles": []})


def _public(row):
    return {**{key: value for key, value in row.items() if key != "credential"}, "has_api_key": bool(row.get("credential"))}


def list_profiles(user_id):
    with _lock:
        user = _user(_read(), user_id)
        return {"profiles": [_public(row) for row in user["profiles"]], "active_id": user["active_id"],
                "credential_protection": "Windows DPAPI" if os.name == "nt" else "Local file permissions (0600)"}


def save_profile(user_id, profile: ProfileInput, activate=False):
    with _lock:
        data = _read()
        user = _user(data, user_id)
        old = next((row for row in user["profiles"] if row["id"] == profile.id), None)
        if profile.id and old is None:
            raise ValueError("Profile not found")
        if old and old.get("credential") and not profile.api_key and not profile.clear_api_key:
            if (urlsplit(old["api_base_url"]).netloc.lower() != urlsplit(profile.api_base_url).netloc.lower()
                    or old["provider"] != profile.provider):
                raise ValueError("接口地址或协议已变更，请重新输入对应密钥，或勾选清除旧密钥")
        row = profile.model_dump(exclude={"clear_api_key"})
        row["id"] = profile.id or f"llm_{uuid4().hex}"
        row["credential"] = "" if profile.clear_api_key else (old or {}).get("credential", "")
        if profile.api_key and not profile.clear_api_key:
            row["credential"] = _protect(profile.api_key.strip())
        user["profiles"] = [item for item in user["profiles"] if item["id"] != row["id"]] + [row]
        if activate:
            user["active_id"] = row["id"]
        _write(data)
        return _public(row)


def activate_profile(user_id, profile_id):
    with _lock:
        data = _read()
        user = _user(data, user_id)
        if profile_id is not None and not any(row["id"] == profile_id for row in user["profiles"]):
            raise ValueError("Profile not found")
        user["active_id"] = profile_id
        _write(data)
        return {"active_id": profile_id}


def delete_profile(user_id, profile_id):
    with _lock:
        data = _read()
        user = _user(data, user_id)
        if not any(row["id"] == profile_id for row in user["profiles"]):
            raise ValueError("Profile not found")
        user["profiles"] = [row for row in user["profiles"] if row["id"] != profile_id]
        if user["active_id"] == profile_id:
            user["active_id"] = None
        _write(data)
        return {"deleted": True, "active_id": user["active_id"]}


def profile_configuration(user_id, profile_id=None):
    """Return a server-only config; None means use the environment fallback."""
    from pydantic import SecretStr
    from backend.services.llm.base import LLMProviderConfig
    with _lock:
        user = _user(_read(), user_id)
        target = profile_id if profile_id is not None else user["active_id"]
        if target is None:
            return None
        row = next((row for row in user["profiles"] if row["id"] == target), None)
        if row is None:
            raise ValueError("Profile not found")
        return LLMProviderConfig(**{key: row[key] for key in ["provider", "model", "api_base_url", "timeout_seconds", "temperature", "max_output_tokens"]},
                                 enabled=True, vendor=row.get("vendor", "custom"), api_key_env_var=None,
                                 profile_id=row["id"], profile_user_id=user_id, profile_revision=_revision(row),
                                 api_key=SecretStr(_unprotect(row["credential"]) if row.get("credential") else ""))


def _revision(row):
    return hashlib.sha256(json.dumps({k: v for k, v in row.items() if k != "connection"}, sort_keys=True).encode()).hexdigest()


def record_connection(config, healthy, message):
    if not config.profile_id or not config.profile_user_id:
        return
    with _lock:
        data = _read()
        row = next((row for row in _user(data, config.profile_user_id)["profiles"] if row["id"] == config.profile_id), None)
        if row is not None and _revision(row) == config.profile_revision:
            row["connection"] = {"healthy": healthy, "message": message, "checked_at": datetime.now(timezone.utc).isoformat()}
            _write(data)


def active_connection(user_id):
    with _lock:
        user = _user(_read(), user_id)
        row = next((row for row in user["profiles"] if row["id"] == user["active_id"]), None)
        return row.get("connection") if row else None


def draft_configuration(user_id, profile):
    """Resolve a draft key without persisting or changing the active profile."""
    from pydantic import SecretStr
    from backend.services.llm.base import LLMProviderConfig
    with _lock:
        user = _user(_read(), user_id)
        old = next((row for row in user["profiles"] if row["id"] == profile.id), None)
        if profile.id and old is None:
            raise ValueError("Profile not found")
        key = profile.api_key or ""
        if old and old.get("credential") and not key and not profile.clear_api_key:
            if (urlsplit(old["api_base_url"]).netloc.lower() != urlsplit(profile.api_base_url).netloc.lower()
                    or old["provider"] != profile.provider):
                raise ValueError("接口地址或协议已变更，请重新输入对应密钥，或勾选清除旧密钥")
            key = _unprotect(old["credential"])
        if profile.clear_api_key:
            key = ""
        return LLMProviderConfig(**profile.model_dump(exclude={"id", "name", "clear_api_key"}),
                                 enabled=True, api_key=SecretStr(key), api_key_env_var=None)
