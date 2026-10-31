# OntoForge

> **课程实现版本。** P0 范围、P1 本体/实体消解、P2 实验与测量投影、P3 增量图存储、P4 可解释空白规则已形成可运行闭环。人工 gold、留出论文质量评价和开放式科研 Agent 仍需课程成员真实参与，不得由 AI 伪造完成。

运行环境和私人模型密钥不随仓库分享。真实运行资料见 `docs/cv-validation/condition-guard-final/`，其中8条展示记录尚非独立人工金标准。

Windows 日常使用：双击根目录 **启动OntoForge.cmd**，自动启动并打开页面；双击 **停止OntoForge.cmd** 结束前后端。已有论文与模型接口配置保留。

本地修复与验收入口：[Windows 运行说明](docs/WINDOWS_SETUP.md)、[CV 历史/后期文献清单](docs/cv-validation/README.md)、[交付验收状态](docs/DELIVERY_ACCEPTANCE.md)。同学版本已保存在独立 Git 提交中，后续修复不覆盖原始贡献记录。

OntoForge is a literature evidence workspace that turns domain-grounded PDF extraction into a traceable Neo4j graph. It connects paper ingestion, structured metric assertions, evidence review, graph/matrix exploration, and scoped coverage-gap analysis in one authenticated desktop/web interface.

OntoForge 是一个面向科研文献的证据工作台：将 PDF 中的论文、指标、断言和证据片段转换成可追溯的 Neo4j 图谱，并通过 Matrix、Graph、Coverage 与人工审核界面完成检索、比较和知识空白分析。

## 可演示 MVP

当前 MVP 围绕 **CV 目标检测论文** 展示一条可验证闭环：

```text
PDF 上传
  -> pypdf / Marker 解析
  -> LLM 或规则抽取候选事实
  -> 人工预览确认
  -> 版本化 Neo4j 本体图谱
  -> Matrix / Graph / Evidence
  -> 实验可比性与证据质量过滤
  -> 带支撑路径的候选研究问题
```

### MVP 能演示什么

| 演示点 | 可观察结果 |
| --- | --- |
| 登录与工作区权限 | owner/editor/viewer 权限由后端校验，非成员请求被拒绝 |
| PDF 导入 | 上传、解析诊断、候选预览、确认入库和原 PDF 回查 |
| 可追溯证据 | 测量可沿 `Measurement -> Experiment -> ExtractionRun -> EvidenceBundle -> PDF` 回查 |
| 实体消解 | `VGG-16`/`VGG16` 合并；Fast/Faster R-CNN、整机/RPN、`07+12`/`07++12` 不误合并 |
| 版本管理 | 同一 PDF 重抽形成新 ExtractionRun；旧 run 保留，新查询默认使用有效 run |
| 实验比较 | 准确率与速度使用不同策略，返回匹配字段、冲突字段和未决字段 |
| 空白候选 | 只消费达到质量门槛的事实，返回规则、支撑路径、缺失关系、范围声明和验证问题 |
| 人工纠错 | 消解决策可确认或撤销，机器校验状态不会冒充人工核验 |

### 首次安装

要求：Python 3.11+、Node.js 20+、Docker/Neo4j。Docker 方式还需要 Compose v2。

```bash
git clone https://github.com/anson2333/OntoForge.git
cd OntoForge
git switch handoff

python -m venv backend/.venv
source backend/.venv/bin/activate
pip install -r backend/requirements.txt

cd frontend
npm ci
npx playwright install chromium
cd ..
```

Windows 用户可参考 [Windows 运行说明](docs/WINDOWS_SETUP.md)，依赖准备完成后双击 `启动OntoForge.cmd`。

### 路线 A：一键自动演示

```bash
./scripts/run_ui_demo.sh
```

脚本使用独立端口、独立用户存储和独立 Neo4j 演示卷，自动完成：

1. 启动 Neo4j、FastAPI 和 Vite。
2. 写入明确标记的合成论文与断言。
3. 使用 `demo` / `demo1234` 登录。
4. 依次展示 Matrix、Evidence、Graph、Coverage、Workspace 和领域规则。
5. 将浏览器截图保存到 `frontend/demo-screenshots/`，日志保存到 `.demo/`。

无头验收模式：

```bash
ONTOFORGE_DEMO_HEADLESS=true ./scripts/run_ui_demo.sh
```

需要演示结束后保留页面一小时：

```bash
ONTOFORGE_DEMO_FINAL_HOLD_MS=3600000 ./scripts/run_ui_demo.sh
```

### 路线 B：现场手动演示

先启动数据库和后端：

```bash
cp .env.example .env
docker compose up -d neo4j

source backend/.venv/bin/activate
python -m uvicorn backend.server.app:app --host 127.0.0.1 --port 8765
```

另开终端启动前端：

```bash
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

打开 `http://127.0.0.1:5173`，新环境默认演示账号为 `demo` / `demo1234`。推荐现场顺序：

1. 创建工作区并添加 `CV Detection` 领域规则。
2. 上传一篇目标检测 PDF，查看解析器、抽取方式、失败批次和警告。
3. 在 Preview 中检查指标、模型变体、数据集、条件和来源片段，再确认提交。
4. 在 Matrix/Evidence 中从数值回查原文，在 Graph 中查看论文与证据关系。
5. 在 Coverage & gaps 中对比“覆盖空格线索”和“经过质量过滤的证据化候选”。
6. 勾选“纳入程序校验通过的事实”，观察可信输入数、未决数、支撑路径与验证问题变化。

未配置 LLM 时仍可演示上传、解析、规则回退、预览、图存储和查询；真实 LLM 抽取需要在设置页配置自己的 provider，密钥不会提交到 Git。

### 本体语义反例演示

以下命令不调用真实模型，也不连接正常用户数据库：

```bash
backend/.venv/bin/python -m pytest backend/tests/test_ontology_core.py -q --no-cov
```

测试固定展示 VGG 别名、Fast/Faster、组件/整机、训练集组合、全数据集耗时、可比性、工作区隔离以及两条图空白规则。完整验收可运行：

```bash
./scripts/test_all.sh
```

### 演示边界

- 自动演示数据是 synthetic，并在界面中标识；它证明软件链路，不证明抽取准确率或科研新颖性。
- “候选研究空白”只表示当前工作区导入文献中缺少满足条件的证据，不代表整个研究领域无人研究。
- 当前没有伪造人工 gold。真实质量汇报仍需成员按 [标注指南](docs/evaluation/annotation-guide.md) 核对固定 PDF。
- 软件当前采用受约束的 Neo4j 属性图和显式语义规则，不宣称已经集成 OWL 推理机。

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
- Typed CV ontology nodes for source versions, extraction runs, model variants, components, backbones, dataset splits, experiments, measurements and evidence bundles.
- Workspace-scoped, explainable entity resolution with reversible decisions; typed aliases merge VGG variants without merging Fast/Faster R-CNN or `07+12`/`07++12`.
- Policy-specific experiment comparability and semantic constraints for component/whole-model scope, AP aggregation and time denominators.
- Quality-filtered graph rules that return supporting paths, missing relations, scope limits and verification questions instead of claiming global novelty.
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

## Automated demo details

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

## Manual development reference

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
| `backend/schemas/ontology.py` | Typed ontology, evidence, experiment and gap contracts |
| `backend/services/entity_resolution.py` | Typed alias resolution and auditable decisions |
| `backend/services/comparability.py` | Accuracy/speed comparability policies |
| `backend/services/gap_analysis.py` | Quality-filtered, path-explained graph rules |
| `backend/database/ontology_repository.py` | Versioned Neo4j ontology projection and queries |
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
