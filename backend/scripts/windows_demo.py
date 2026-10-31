"""Start an isolated UI demo on Windows (or another Python-supported platform)."""
from __future__ import annotations
import os
import subprocess
import sys
import time
from pathlib import Path
import httpx

ROOT = Path(__file__).resolve().parents[2]


def main():
    uri = os.getenv("ONTOFORGE_TEST_NEO4J_URI")
    if not uri:
        raise SystemExit("Set ONTOFORGE_TEST_NEO4J_URI to an isolated test DB. Mock loader clears it.")
    runtime = ROOT / ".demo/windows"
    runtime.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "NEO4J_URI": uri, "ONTOFORGE_USER_STORE": str(runtime / "users.json"),
           "ONTOFORGE_UPLOAD_DIR": str(runtime / "uploads"), "ONTOFORGE_SEED_DEMO_USER": "true",
           "PYTHONIOENCODING": "utf-8", "VITE_ONTOFORGE_BACKEND_URL": "http://localhost:28765"}
    subprocess.run([sys.executable, "-c", "from backend.services.auth_service import ensure_demo_user; ensure_demo_user()"], cwd=ROOT, env=env, check=True)
    subprocess.run([sys.executable, "-m", "backend.scripts.load_mock_data"], cwd=ROOT, env=env, check=True)
    processes, logs = [], []
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    try:
        commands = [([sys.executable, "-m", "uvicorn", "backend.server.app:app", "--host", "127.0.0.1", "--port", "28765"], ROOT),
                    (["node", "node_modules/vite/bin/vite.js", "--host", "127.0.0.1", "--port", "25173", "--strictPort"], ROOT / "frontend")]
        for index, (command, cwd) in enumerate(commands):
            log = (runtime / f"service-{index}.log").open("w", encoding="utf-8")
            logs.append(log)
            processes.append(subprocess.Popen(command, cwd=cwd, env=env, stdout=log, stderr=log, creationflags=flags))
        with httpx.Client(trust_env=False) as client:
            for url in ["http://localhost:28765/health", "http://localhost:25173"]:
                for attempt in range(60):
                    if any(process.poll() is not None for process in processes):
                        raise RuntimeError("Demo service exited; inspect .demo/windows/service-*.log")
                    try:
                        response = client.get(url, timeout=2)
                        response.raise_for_status()
                        break
                    except httpx.HTTPError:
                        if attempt == 59:
                            raise
                        time.sleep(1)
        subprocess.run(["node", "scripts/ui_demo.mjs", "--headless", "--url=http://localhost:25173", "--slow=200", "--hold=0"],
                       cwd=ROOT / "frontend", env=env, check=True)
        subprocess.run(["node", "scripts/llm_profiles_demo.mjs"], cwd=ROOT / "frontend", env=env, check=True)
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
        for log in logs:
            log.close()


if __name__ == "__main__":
    main()
