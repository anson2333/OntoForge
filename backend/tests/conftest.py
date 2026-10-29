"""
Pytest configuration for OntoForge backend tests.
Configures Docker environment for testcontainers.
"""

import os
import pytest
import tempfile
import json


@pytest.fixture(scope="session", autouse=True)
def configure_docker():
    """
    Configure Docker environment for testcontainers on macOS.
    
    Docker Desktop on macOS uses a non-standard socket location.
    This fixture ensures testcontainers can find the Docker daemon.
    """
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
