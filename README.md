# OntoForge

OntoForge is a literature evidence workspace that turns domain-grounded PDF extraction into a traceable Neo4j graph. It connects paper ingestion, structured metric assertions, evidence review, graph/matrix exploration, and scoped coverage-gap analysis in one authenticated desktop/web interface.

OntoForge 是一个面向科研文献的证据工作台：将 PDF 中的论文、指标、断言和证据片段转换成可追溯的 Neo4j 图谱，并通过 Matrix、Graph、Coverage 与人工审核界面完成检索、比较和知识空白分析。

## Development history

This repository was developed in three stages:

1. **Original baseline**: the teacher-provided project was preserved in commit `724a553`.
2. **Trae CLI implementation**: conversation `2e389ba1-4d8f-496b-a627-2fd1b9e2b851` implemented the first end-to-end application flow.
3. **Codex completion and hardening**: the partial implementation was audited, completed, secured, documented, and exercised through an automated browser demo.

### Work completed by Trae CLI

- Added local user authentication, session handling, workspace ownership, and the initial permission model.
- Connected the React frontend to the JSON-RPC backend instead of relying only on browser fixtures.
- Expanded PDF ingestion with upload, parsing, long-document LLM batching, semantic extraction, normalization, preview, and commit flows.
- Added the first backend coverage/gap analysis services.
- Added optical/wireless domain-pack examples, deterministic mock literature, and the terminal demo walkthrough.
- Added the initial login UI, workspace integration, backend service status, mock-data loader changes, and Playwright dependency.
- Started the automated UI walkthrough, but the session ended before the script and one-command launcher were complete.

### Work completed by Codex

- Audited the Trae CLI session and completed its interrupted UI demo and launcher work.
- Hardened authorization for workspace members, PDF uploads, evidence mutation, intent branches, raw Cypher, and server-local file access.
- Fixed workspace deletion so graph traversal cannot delete data belonging to other workspaces.
- Added upload size/type checks, prompt-injection guidance, safe Neo4j property/label handling, and session-derived actor identity.
- Completed the Coverage UI, workspace member management, runtime backend configuration, and frontend lint/type/build configuration.
- Connected evidence approve/reject/request-review/correction/history-restore actions to real backend methods and corrected their state transitions.
- Completed intent branch creation, session context switching, scoped intent queries, review queues, and real pattern-impact previews.
- Added portable Neo4j fallback for machines where Docker is unavailable or its socket is inaccessible.
- Fixed top-level Matrix/Graph/Coverage navigation and verified all six demo views with Playwright screenshots.
- Added full project documentation, strict integration-test entry points, repository safety tests, and compatibility fixes for the FastAPI/HTTPX test stack.

The development history is included for attribution and reproducibility; the current source tree is the integrated result of all three stages.

## What works

- Local accounts, expiring sessions, workspace ownership, viewer/editor membership, and backend authorization.
- Backend-managed PDF upload, pypdf or Marker extraction, long-document LLM batching, rule fallback, preview, and idempotent commit.
- Globally scoped paper evidence IDs, metric/unit normalization, source chunks, page/region metadata, and human verification updates.
- Matrix and graph views backed by Neo4j data rather than generated browser fixtures.
- Method × scenario × metric coverage analysis with ranked candidate gaps and supporting-paper counts.
- Optical and wireless domain-pack examples, reproducible mock literature, terminal walkthrough, and automated browser walkthrough.

Candidate gaps mean that the papers imported into the selected workspace do not cover a combination. They are not claims that the wider research field has never studied it.

## Architecture

```text
React + Vite / Electron
        |
        | JSON-RPC 2.0 + bearer session
        v
FastAPI SSP server
  |       |        |
  |       |        +-- LLM provider / rule fallback
  |       +----------- pypdf / Marker extraction
  +------------------- Neo4j evidence graph
```

The frontend uses `VITE_ONTOFORGE_BACKEND_URL` when supplied and otherwise connects to `http://localhost:8765`. The backend derives user identity from the session token; client-provided owner IDs are never authoritative.

## Fastest demo

Install the backend/frontend dependencies and Playwright Chromium once, then run:

```bash
./scripts/run_ui_demo.sh
```

The script automatically uses Docker when available, or the portable runtime under `~/.local/ontoforge-runtime/` when Docker is inaccessible. It uses isolated demo data, loads deterministic sample literature, opens Chromium, and walks through the working UI without manual clicks. It does not clear the normal development database.

The walkthrough covers Matrix, evidence review, Graph, Coverage, workspace overview, and domain-pack detail. Use a longer final hold when you want to inspect the live UI manually:

```bash
ONTOFORGE_DEMO_FINAL_HOLD_MS=3600000 ./scripts/run_ui_demo.sh
```

See [LOCAL_SETUP.md](LOCAL_SETUP.md) for prerequisites, manual startup, environment variables, the terminal walkthrough, and the acceptance checklist.

## Complete validation

With Docker running, execute the entire backend, Neo4j integration, frontend build, and Playwright UI flow with one command:

```bash
./scripts/test_all.sh
```

Unlike a normal `pytest` run, this command fails if Neo4j integration tests cannot start instead of reporting them as skipped. UI screenshots are written to `frontend/demo-screenshots/` and service logs to `.demo/`.

## Manual development

```bash
cp .env.example .env
docker compose up -d neo4j

source backend/.venv/bin/activate
set -a && source .env && set +a
python -m backend.scripts.load_mock_data
python -m uvicorn backend.server.app:app --reload --port 8765
```

In another terminal:

```bash
cd frontend
npm run dev
```

Open `http://localhost:5173` and sign in with `demo` / `demo1234` on a fresh local setup.

## Repository map

| Path | Responsibility |
| --- | --- |
| `backend/server` | FastAPI transport and JSON-RPC methods |
| `backend/services/pdf_ingestion_service.py` | Upload, extraction, preview, and graph commit |
| `backend/services/llm` | Provider abstraction, intent parsing, and semantic extraction |
| `backend/services/coverage_analysis.py` | Coverage matrix and gap ranking |
| `backend/database` | Neo4j connection and repositories |
| `backend/config`, `backend/configs` | Domain-pack definitions |
| `frontend/renderer` | React workbench, authentication, evidence, graph, and coverage UI |
| `backend/scripts/demo_walkthrough.py` | API-level narrated demonstration |
| `scripts/run_ui_demo.sh` | Isolated one-command browser demonstration |
| `scripts/test_all.sh` | Backend, Neo4j, frontend, and Playwright validation |

## Operational boundaries

- LLM extraction requires an explicitly configured provider. Without one, ingestion still stores the paper/chunks and uses the domain-pack rule fallback where possible.
- The bundled sample coverage context is synthetic and marked as mock-generated; real imports depend on extracted context quality.
- Accounts are stored in a local PBKDF2-protected JSON registry. This is suitable for a course/local deployment, not a replacement for an institutional identity provider.
- Sessions are in memory and expire on restart. Committed graph data and users remain persistent.
- Exact PDF image crops are not retained after commit; the UI shows extracted source text plus available page/region metadata.
- Raw Cypher and server-local `paper_uri` access are disabled by default because they bypass normal workspace/file boundaries.

## Useful checks

```bash
backend/.venv/bin/python -m pytest backend/tests -q --no-cov
cd frontend && npm run type-check && npm run lint && npm run build
```

The Docker-backed Neo4j integration suite is skipped when neither Docker nor `ONTOFORGE_TEST_NEO4J_URI` is available.
