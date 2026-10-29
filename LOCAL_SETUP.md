# OntoForge Local Setup

This setup keeps all Docker changes scoped to this repository. It does not reset Docker Desktop, delete any global Docker files, or prune containers, images, networks, or volumes used by other projects.

## What this repository expects

- Neo4j on `bolt://localhost:7687`
- Backend SSP server on `http://localhost:8765`
- Frontend Electron app talking to the backend on `http://localhost:8765`

## 1. Create local environment file

From the repository root:

```bash
cp .env.example .env
```

If another project already uses `7474` or `7687`, change `NEO4J_HTTP_PORT` and `NEO4J_BOLT_PORT` in `.env`, then update `NEO4J_URI` to match the new Bolt port.

Example:

```bash
NEO4J_URI=bolt://localhost:8687
NEO4J_HTTP_PORT=8474
NEO4J_BOLT_PORT=8687
```

## 2. Backend Python environment

Use Python 3.11 or newer for local development. The backend test suite is verified on Python 3.11, and the PDF Marker integration also requires Python 3.10+.

The repository includes a `.python-version` file pinned to the verified local baseline: `3.11.15`.

Verify your interpreter first:

```bash
python3.11 --version
```

```bash
python3.11 -m venv backend/.venv
source backend/.venv/bin/activate
python -m pip install --upgrade pip
pip install -r backend/requirements.txt
```

If `python3.11` is not on your `PATH`, use the full interpreter path provided by your package manager, then create the virtual environment with that executable.

### Optional: Marker PDF environment

Keep Marker in a separate virtual environment so the backend can call it as an external CLI without coupling its dependencies to the backend runtime.

For installation, backend wiring, optional flags, smoke checks, and the verified macOS x86_64 runtime limitation, use [MARKER_SETUP.md](MARKER_SETUP.md).

## 3. Frontend dependencies

```bash
cd frontend
npm install
cd ..
```

## 4. Start Neo4j with repo-local Docker Compose

```bash
docker compose up -d neo4j
docker compose ps
```

The compose project name is `ontoforge-local` and the named volumes are prefixed with `ontoforge_`, so they remain isolated from your other Docker-based projects.

## 5. Load mock database data

From the repository root:

```bash
source backend/.venv/bin/activate
set -a
source .env
set +a
python -m backend.scripts.load_mock_data
```

This clears the OntoForge Neo4j database and reloads the repository's mock workspace, papers, chunks, formulas, and assertions.

## 6. Start the backend

From the repository root:

```bash
source backend/.venv/bin/activate
set -a
source .env
set +a
python -m uvicorn backend.server.app:app --reload --host "${BACKEND_HOST:-0.0.0.0}" --port "${BACKEND_PORT:-8765}"
```

Health check:

```bash
curl http://localhost:8765/health
```

## 7. Start the frontend

In a second terminal:

```bash
cd frontend
npm run electron:dev
```

## Useful commands

Stop Neo4j:

```bash
docker compose stop neo4j
```

Restart Neo4j:

```bash
docker compose restart neo4j
```

View Neo4j logs:

```bash
docker compose logs -f neo4j
```

Run backend tests:

```bash
source backend/.venv/bin/activate
cd backend
pytest
```

Run a focused Python/version smoke check:

```bash
source backend/.venv/bin/activate
python --version
python -c 'import fastapi, uvicorn, pydantic, neo4j, pypdf, jsonrpcserver; print("backend imports ok")'
```

## Notes

- Do not run `docker system prune`, `docker volume prune`, or any Docker reset commands for this project.
- `python -m backend.scripts.load_mock_data` deliberately clears the OntoForge graph before reloading mock data. It only affects the Neo4j database reached through `NEO4J_URI`.
- If you change the Neo4j Bolt port in `.env`, keep the backend and loader pointed at the same `NEO4J_URI`.
- The backend test suite is currently validated on Python 3.11.
- Marker should be installed in its own virtual environment and wired in with `ONTOFORGE_PDF_EXTRACTOR=marker` plus `ONTOFORGE_MARKER_COMMAND=/absolute/path/to/marker_single`. The complete setup and usage guide lives in [MARKER_SETUP.md](MARKER_SETUP.md).