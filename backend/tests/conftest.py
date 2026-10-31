"""
Pytest configuration for OntoForge backend tests.
Configures Docker environment for testcontainers.
"""

import os
import sys
import asyncio
import pytest
import tempfile
import json
import httpx


class SyncASGIClient:
    """Small synchronous facade over HTTPX's thread-free ASGI transport.

    Starlette's TestClient relies on an AnyIO cross-thread portal. That portal
    can deadlock under some Python/AnyIO combinations before the app receives a
    request. Running each test request in its own event loop is deterministic
    and is sufficient here because these tests do not exercise app lifespan.
    """

    def __init__(self, app):
        self.app = app

    def request(self, method: str, url: str, **kwargs):
        async def send():
            transport = httpx.ASGITransport(app=self.app)
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                return await client.request(method, url, **kwargs)

        return asyncio.run(send())

    def get(self, url: str, **kwargs):
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs):
        return self.request("POST", url, **kwargs)


@pytest.fixture(autouse=True)
def isolate_auth_store(tmp_path, monkeypatch):
    """Keep the user registry out of the repository during tests."""
    monkeypatch.setenv("ONTOFORGE_USER_STORE", str(tmp_path / "users.json"))
    monkeypatch.setenv("ONTOFORGE_LLM_PROFILE_STORE", str(tmp_path / "llm-profiles.json"))
    monkeypatch.setenv("ONTOFORGE_SEED_DEMO_USER", "false")
    monkeypatch.setenv("ONTOFORGE_AUTH_REQUIRED", "true")
    yield


@pytest.fixture(scope="session", autouse=True)
def configure_docker():
    """
    Configure Docker environment for testcontainers.

    The macOS-specific socket/credential-helper workarounds are only applied on
    macOS; on Linux the Docker daemon defaults are used.
    """
    if sys.platform != "darwin":
        yield
        return

    # Set Docker socket location for macOS Docker Desktop
    docker_host = "unix:///Users/sunweiqiang/.docker/run/docker.sock"
    os.environ["DOCKER_HOST"] = docker_host
    
    # Add Docker binaries to PATH for credential helpers
    docker_bin_path = "/Applications/Docker.app/Contents/Resources/bin"
    current_path = os.environ.get("PATH", "")
    if docker_bin_path not in current_path:
        os.environ["PATH"] = f"{docker_bin_path}:{current_path}"
    
    # Create temporary Docker config that doesn't use credential store
    # This avoids issues with docker-credential-osxkeychain not being in PATH
    temp_docker_dir = tempfile.mkdtemp()
    docker_config = {
        "auths": {},
        "credsStore": ""  # Disable credential store
    }
    
    config_path = os.path.join(temp_docker_dir, "config.json")
    with open(config_path, "w") as f:
        json.dump(docker_config, f)
    
    # Point Docker to use this temporary config
    os.environ["DOCKER_CONFIG"] = temp_docker_dir
    
    # Also set testcontainers-specific env vars
    os.environ["TC_HOST"] = docker_host
    
    yield
    
    # Cleanup: remove temporary config
    try:
        os.remove(config_path)
        os.rmdir(temp_docker_dir)
    except:
        pass
