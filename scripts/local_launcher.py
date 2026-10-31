"""Start/stop the regular local application without modifying research data."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import ctypes
import importlib.util
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
from urllib.parse import urlsplit
from urllib.request import build_opener, ProxyHandler
import venv
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "backend/data/launcher"
STATE = RUNTIME / "state.json"
PYTHON = ROOT / "backend/.venv/Scripts/python.exe"
FLAGS = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def run(command, **kwargs):
    return subprocess.run(command, cwd=kwargs.pop("cwd", ROOT), creationflags=FLAGS, **kwargs)


def process_stamp(pid):
    """Windows creation time prevents accidentally terminating a reused PID."""
    if os.name != "nt":
        raise RuntimeError("This launcher is for Windows")
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        return None
    try:
        exit_code = wintypes.DWORD()
        if not kernel.GetExitCodeProcess(handle, ctypes.byref(exit_code)) or exit_code.value != 259:
            return None
        created, exited, system, user = [wintypes.FILETIME() for _ in range(4)]
        if not kernel.GetProcessTimes(handle, ctypes.byref(created), ctypes.byref(exited), ctypes.byref(system), ctypes.byref(user)):
            return None
        return (created.dwHighDateTime << 32) | created.dwLowDateTime
    finally:
        kernel.CloseHandle(handle)


def owned(record):
    return bool(record and record.get("created") is not None and process_stamp(record["pid"]) == record["created"])


def stop_process(record):
    if owned(record):
        # This PID is verified as a child started by this launcher, including its children.
        run(["taskkill", "/PID", str(record["pid"]), "/T", "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)


def read_state():
    return json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}


def write_state(state):
    pending = STATE.with_suffix(".tmp")
    pending.write_text(json.dumps(state, indent=2), encoding="utf-8")
    pending.replace(STATE)


@contextmanager
def launcher_lock():
    import msvcrt
    RUNTIME.mkdir(parents=True, exist_ok=True)
    with (RUNTIME / "controller.lock").open("a+b") as handle:
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            raise RuntimeError("Another start/stop is in progress. Please wait for it to finish.") from None
        try:
            yield
        finally:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


def port_free(port):
    with socket.socket() as probe:
        try:
            probe.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def get_json(url):
    with build_opener(ProxyHandler({})).open(url, timeout=2) as response:
        return json.load(response)


def services_ready(state):
    if not all(owned(state.get(role)) for role in ("backend", "frontend")):
        return False
    try:
        root = get_json(state["backend_url"] + "/")
        health = get_json(state["backend_url"] + "/health")
        with build_opener(ProxyHandler({})).open(state["url"], timeout=2) as response:
            return root.get("service") == "OntoForge SSP Server" and health.get("database") == "connected" and response.status == 200
    except Exception:
        return False


def dependencies():
    if not PYTHON.exists():
        print("Preparing the project's Python environment...", flush=True)
        venv.EnvBuilder(with_pip=True).create(PYTHON.parents[1])
    if Path(sys.executable).resolve() != PYTHON.resolve():
        return False
    modules = ["fastapi", "uvicorn", "neo4j", "pydantic", "pypdf", "dotenv", "yaml", "httpx", "jsonrpcserver", "watchdog", "fontTools"]
    if any(importlib.util.find_spec(module) is None for module in modules):
        print("Installing missing backend dependencies...", flush=True)
        run([str(PYTHON), "-m", "pip", "install", "-r", str(ROOT / "backend/requirements.txt")], check=True)
    if not shutil.which("node"):
        raise RuntimeError("Install Node.js (including npm), then double-click Start again.")
    if not (ROOT / "frontend/node_modules/vite/bin/vite.js").exists():
        npm = shutil.which("npm")
        npm_cli = Path(npm).parent / "node_modules/npm/bin/npm-cli.js" if npm else None
        if not npm_cli or not npm_cli.exists():
            raise RuntimeError("npm was not found. Reinstall Node.js with npm enabled.")
        print("Installing frontend dependencies...", flush=True)
        run([shutil.which("node"), str(npm_cli), "ci"], cwd=ROOT / "frontend", check=True)
    return True


def configuration(args):
    from dotenv import dotenv_values
    if not (ROOT / ".env").exists():
        shutil.copyfile(ROOT / ".env.example", ROOT / ".env")
    env = {**{key: value for key, value in dotenv_values(ROOT / ".env").items() if value is not None}, **os.environ}
    backend = args.backend_port or int(env.get("ONTOFORGE_BACKEND_PORT", "8765"))
    frontend = args.frontend_port or int(env.get("ONTOFORGE_FRONTEND_PORT", "5173"))
    if not all(1 <= value <= 65535 for value in (backend, frontend)) or backend == frontend:
        raise ValueError("Choose two different valid frontend/backend ports")
    env.setdefault("NEO4J_URI", f"bolt://localhost:{env.get('NEO4J_BOLT_PORT', '7687')}")
    env.update({"VITE_ONTOFORGE_BACKEND_URL": f"http://127.0.0.1:{backend}", "PYTHONIOENCODING": "utf-8"})
    return env, backend, frontend


def ensure_database(env):
    from neo4j import GraphDatabase
    from neo4j.exceptions import AuthError
    uri = env["NEO4J_URI"]
    def ready():
        try:
            with GraphDatabase.driver(uri, auth=(env.get("NEO4J_USER", "neo4j"), env.get("NEO4J_PASSWORD", "password")),
                                      connection_timeout=2, max_connection_pool_size=1) as driver:
                driver.verify_connectivity()
            return True
        except AuthError:
            raise RuntimeError("Neo4j rejected the credentials. Check .env; existing database passwords are not reset automatically.") from None
        except Exception:
            return False
    if ready():
        return
    if urlsplit(uri).hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise RuntimeError("Configured external Neo4j is unavailable. Check its connection settings.")
    docker = shutil.which("docker")
    if not docker:
        raise RuntimeError("Neo4j is unavailable. Install/start Docker Desktop or configure an existing Neo4j in .env.")
    def docker_ready():
        try:
            return run([docker, "info", "--format", "{{.ServerVersion}}"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=4).returncode == 0
        except subprocess.TimeoutExpired:
            return False
    if not docker_ready():
        desktop = Path(os.getenv("ProgramFiles", "C:/Program Files")) / "Docker/Docker/Docker Desktop.exe"
        if not desktop.exists():
            raise RuntimeError("Start Docker Desktop, then double-click Start again.")
        print("Starting Docker Desktop...", flush=True)
        info = subprocess.STARTUPINFO()
        info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        info.wShowWindow = 0
        subprocess.Popen([str(desktop)], startupinfo=info, creationflags=FLAGS)
        for _ in range(60):
            if docker_ready():
                break
            time.sleep(1)
        else:
            raise RuntimeError("Docker is still starting. Wait for Docker Desktop to be ready and try again.")
    print("Starting the project database (existing data is preserved)...", flush=True)
    run([docker, "compose", "-f", str(ROOT / "compose.yaml"), "up", "-d", "neo4j"], env=env, check=True)
    for _ in range(90):
        if ready():
            return
        time.sleep(1)
    raise RuntimeError("Neo4j did not become ready. Check Docker Desktop and .env.")


def launch(command, cwd, env, name):
    with (RUNTIME / f"{name}.log").open("w", encoding="utf-8") as log:
        process = subprocess.Popen(command, cwd=cwd, env=env, stdout=log, stderr=log, creationflags=FLAGS)
    return {"pid": process.pid, "created": process_stamp(process.pid)}


def start(args):
    previous = read_state()
    if services_ready(previous):
        print(f"Already running: {previous['url']}", flush=True)
        if not args.no_browser:
            webbrowser.open(previous["url"])
        return
    for role in ("frontend", "backend"):
        stop_process(previous.get(role))
    env, backend, frontend = configuration(args)
    for port in (backend, frontend):
        if not port_free(port):
            raise RuntimeError(f"Port {port} is occupied by another program. Stop that program or set ONTOFORGE_BACKEND_PORT / ONTOFORGE_FRONTEND_PORT in .env.")
    print("Checking the database...", flush=True)
    ensure_database(env)
    state = {"url": f"http://127.0.0.1:{frontend}", "backend_url": f"http://127.0.0.1:{backend}"}
    try:
        state["backend"] = launch([str(PYTHON), "-m", "uvicorn", "backend.server.app:app", "--host", "127.0.0.1", "--port", str(backend)], ROOT, env, "backend")
        write_state(state)
        state["frontend"] = launch([shutil.which("node"), "node_modules/vite/bin/vite.js", "--host", "127.0.0.1", "--port", str(frontend), "--strictPort"], ROOT / "frontend", env, "frontend")
        write_state(state)
        print("Starting frontend and backend...", flush=True)
        for _ in range(60):
            if not all(owned(state[role]) for role in ("backend", "frontend")):
                raise RuntimeError("A service exited. See the launcher logs.")
            if services_ready(state):
                print(f"Ready: {state['url']}\nLogs: {RUNTIME}", flush=True)
                if not args.no_browser:
                    webbrowser.open(state["url"])
                return
            time.sleep(1)
        raise RuntimeError("Services did not become ready. See the launcher logs.")
    except BaseException:
        for role in ("frontend", "backend"):
            stop_process(state.get(role))
        STATE.unlink(missing_ok=True)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["start", "stop", "status"], nargs="?", default="start")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--backend-port", type=int)
    parser.add_argument("--frontend-port", type=int)
    args = parser.parse_args()
    if os.name != "nt":
        raise SystemExit("Use this launcher on Windows.")
    if args.action == "start":
        with launcher_lock():
            prepared = dependencies()
        if not prepared:
            raise SystemExit(run([str(PYTHON), str(Path(__file__).resolve()), *sys.argv[1:]]).returncode)
    with launcher_lock():
        if args.action == "start":
            start(args)
        elif args.action == "stop":
            state = read_state()
            for role in ("frontend", "backend"):
                stop_process(state.get(role))
            STATE.unlink(missing_ok=True)
            print("Frontend/backend stopped. Database and saved data are preserved.")
        else:
            state = read_state()
            print(f"Running: {state['url']}" if services_ready(state) else "Not running")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\nStartup/stop failed: {exc}\nLogs: {RUNTIME}", file=sys.stderr)
        raise SystemExit(1)
