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

The mock workspace is owned by the seeded demo account so it is visible after signing in. Start the backend once (step 6) before loading data so `backend/data/users.json` exists, or pass the owner explicitly:

```bash
ONTOFORGE_MOCK_OWNER_ID=<user_id> python -m backend.scripts.load_mock_data
```

If no demo account exists, the loader falls back to a workspace without an owner, which any signed-in user can read (but not modify).

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

### Sign in

The backend seeds a demo account on first start:

- Username: `demo`
- Password: `demo1234`

The desktop app shows the sign-in screen until a valid session exists, and keeps the session token in `localStorage` (`ontoforge-session-token`). The toolbar has a **Sign out** button. You can also register a new account from the same screen.

Authentication-related environment variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `ONTOFORGE_AUTH_REQUIRED` | `true` | Reject unauthenticated JSON-RPC calls with error `-32001` |
| `ONTOFORGE_SEED_DEMO_USER` | `true` | Create the `demo` account on startup |
| `ONTOFORGE_DEMO_PASSWORD` | `demo1234` | Password for the demo account |
| `ONTOFORGE_USER_STORE` | `backend/data/users.json` | Path to the local user database |
| `ONTOFORGE_SESSION_TTL_SECONDS` | `28800` | Session lifetime |

Users are also available over JSON-RPC: `authRegister`, `authLogin`, `authLogout`, `authStatus`, plus `listWorkspaceMembers`, `addWorkspaceMember`, and `removeWorkspaceMember` for workspace sharing.

## One-command browser demo

After installing the backend and frontend dependencies once, run this from the repository root:

```bash
./scripts/run_ui_demo.sh
```

The script automatically chooses an available database runtime. It uses Docker when the daemon is accessible; otherwise it uses the portable JRE and Neo4j archive under `~/.local/ontoforge-runtime/`. On the current development machine no Docker permission or sudo is required.

If Docker is installed but `docker info` reports permission denied, use per-command sudo without changing your permanent group membership:

```bash
sudo -v
ONTOFORGE_DOCKER_USE_SUDO=true ./scripts/run_ui_demo.sh
```

The command starts an isolated Neo4j instance, seeds the demo account and mock data, starts the backend and Vite, opens Chromium, and automatically walks through Matrix, evidence, Graph, coverage analysis, workspace, and domain-pack views. No clicks are required. Screenshots are saved under `frontend/demo-screenshots/`; backend and frontend logs are written under `.demo/`.

The demo deliberately uses separate resources so it cannot clear the normal development database:

| Resource | Demo default |
| --- | --- |
| Neo4j HTTP / Bolt | `17474` / `17687` |
| Neo4j volumes | `ontoforge_demo_*` |
| Backend | `http://127.0.0.1:18765` |
| Frontend | `http://127.0.0.1:15173` |
| User store | `.demo/users.json` |

Either Docker or the portable Neo4j runtime must exist. `backend/.venv`, `frontend/node_modules`, and the Playwright Chromium browser must also be installed. Install the browser once if needed:

```bash
cd frontend
npx playwright install chromium
cd ..
```

Optional controls:

```bash
# Keep each view visible for 3 seconds and the final view for 10 seconds.
ONTOFORGE_DEMO_STEP_DELAY_MS=3000 ONTOFORGE_DEMO_FINAL_HOLD_MS=10000 ./scripts/run_ui_demo.sh

# Validate without opening a visible browser; screenshots are still produced.
ONTOFORGE_DEMO_HEADLESS=true ./scripts/run_ui_demo.sh
```

The app processes are stopped after the walkthrough. The isolated Neo4j container remains available for another run and can be stopped with `docker compose -p ontoforge-demo -f compose.yaml stop neo4j`.

## Complete automated test

Run the complete validation from the repository root:

```bash
./scripts/test_all.sh
```

For a Docker socket permission error:

```bash
sudo -v
ONTOFORGE_DOCKER_USE_SUDO=true ./scripts/test_all.sh
```

This command deliberately requires a running Docker daemon and performs all four stages:

1. All backend unit/protocol tests plus the 13 real Neo4j repository integration tests, with coverage.
2. Frontend TypeScript checking.
3. Frontend ESLint and production build.
4. A headless Playwright walkthrough against an isolated, seeded Neo4j database.

The command fails if the integration database is unavailable; skipped Neo4j tests are not accepted as a complete result. Successful UI screenshots are stored under `frontend/demo-screenshots/`, with backend/frontend logs under `.demo/`.

## Terminal demo walkthrough

The fastest reproducible demo is the walkthrough script; it exercises the real backend and prints each step.

```bash
# Requires Neo4j + backend running and mock data loaded (steps 1-6).
backend/.venv/bin/python backend/scripts/demo_walkthrough.py --namespace wireless

# Optional: include the PDF ingest loop (upload -> parse -> commit -> idempotent re-commit).
backend/.venv/bin/python backend/scripts/demo_walkthrough.py --namespace wireless --pdf OntoForge.pdf

# Same coverage story for the optical pack.
backend/.venv/bin/python backend/scripts/demo_walkthrough.py --namespace optical
```

It prints: health check, anonymous vs signed-in identity, accessible workspace, 25 papers / 70 assertions, one evidence chunk with its page box, the method × scenario × metric coverage summary, and the top ranked gap candidates. With `--pdf` it also shows `uploadPdf` → `parsePdfWithDomainPack` → `commitParsedPdf` and the duplicate-import guard. Restore the demo data afterwards with `python -m backend.scripts.load_mock_data`.

For the UI demo, Electron is not required:

```bash
cd frontend
npm run dev
```

Open `http://localhost:5173` (CORS already allows this origin) and sign in as `demo` / `demo1234`:

1. Workspace sidebar → **Demo Workspace**.
2. **Matrix** tab: click a cell to open the evidence panel (chunk text, confidence, page box).
3. **Graph** tab: domain → subdomain → paper → assertion.
4. Open a domain pack node and drop a PDF to run preview → commit.
5. **Coverage** tab: inspect the method × scenario × metric matrix and ranked candidate gaps.

## End-to-end acceptance checklist

The following flow was verified on a real Neo4j instance (`bolt://localhost:7687`) with Python 3.10 and the frontend production build.

### 1. Build and static checks

```bash
cd frontend
npm install
npm run type-check   # passes
npm run build        # passes
```

```bash
backend/.venv/bin/python -m pytest backend/tests -q --no-cov
# 185 passed, 13 skipped (integration tests need Docker/testcontainers)
```

### 2. Authentication

Using the running backend on `http://localhost:8765/jsonrpc`:

| Step | Call | Expected |
| --- | --- | --- |
| Anonymous status | `authStatus` | `{"authenticated": false, "user": null}` |
| Register | `authRegister` with `username` / `password` | `user` object only; call `authLogin` to obtain a token |
| Login | `authLogin` with `demo` / `demo1234` | session `token` + `user` |
| Authenticated status | `authStatus` with `Bearer <token>` | `authenticated: true` |
| Unauthenticated data call | `getAssertions` without token | JSON-RPC error `-32001` |
| Foreign owner id | `getPapers` with `owner_id` of another user | JSON-RPC error `-32003` |
| Cross-user workspace | second account calling `getPapers` / `deleteWorkspace` on the demo workspace | JSON-RPC error `-32003` |
| Logout | `authLogout` | `logged_out: true`; old token becomes anonymous |

### 3. Workspace and data flow

1. Sign in as `demo` in the desktop app; the workspace sidebar lists **Demo Workspace** (mock data) or the workspace you created.
2. Create a workspace from the UI (`createWorkspace`) and confirm it appears in `listWorkspaces` for the same account only.
3. Upload a PDF, preview the parse result, and commit it (`uploadPdf` → `parsePdfWithDomainPack` → `commitParsedPdf`); the paper appears in the matrix and graph views.
4. Click a matrix cell to open the evidence panel (`getEvidence`); mock data ships one supporting chunk per assertion.
5. `getCoverageAnalysis` returns the method × scenario × metric coverage payload for the workspace.

During verification `OntoForge.pdf` (1.6 MB) was uploaded, parsed with the `pypdf` extractor, and committed: the backend reported `status: committed` and created one `PaperNode` with 44 linked `ChunkNode`s in the workspace. Re-running `commitParsedPdf` with the same `upload_id` returned `status: committed` plus the warning `Paper was already committed; duplicate write skipped (idempotent import).` and did not create a second paper. With the LLM provider disabled the ingest produced 0 assertions and the warning `No domain-grounded assertions were extracted from the parsed chunks.`

### Known limitations / not implemented

- **No LLM provider configured by default**: `getLLMStatus` reports `provider: disabled`, so PDF ingestion stores chunks and papers but extracts no assertions. Configure an LLM provider to exercise semantic extraction.
- **Mock coverage context is synthetic**: the mock loader labels each paper with one method and one scenario (rotating through the pack taxonomy), so coverage numbers are realistic but not extracted from papers. `optical` reports 31/450 covered cells and 419 candidates; `wireless` reports 16/64 and 48. Several candidates can share a score when their method × scenario structure is identical; real LLM extraction produces more varied context.
- **Workspace-level domain-pack selection and the pending paper-import queue are still stored in browser `localStorage`** (`ontoforge-domain-pack-registry-v1`, `ontoforge-paper-registry-v1`). Domain pack configurations themselves now come from the backend (`listDomainPacks`); there is no backend endpoint for per-workspace pack binding or for listing staged imports.
- **Workspace membership is local-account based**: owners can add registered usernames as viewer/editor from the workspace action menu. There is no email invitation or external identity provider integration.
- **Committed imports retain extracted text and page/region metadata, not the original PDF image**: the evidence editor can show the source passage and coordinates but cannot render a pixel-perfect crop after the temporary upload expires.
- Integration tests that need Docker (`test_integration.py`) are skipped when Docker is unavailable.

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
