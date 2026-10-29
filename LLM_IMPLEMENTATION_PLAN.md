# LLM Implementation Plan

This document captures the near-term implementation plan for the LLM-facing side of OntoForge. It is intentionally grounded in the current codebase rather than the earlier greenfield specification.

## Goal

Add a backend-first LLM orchestration layer that can:

- parse PDF files using the active domain-pack configuration
- parse freeform user intent into existing structured intent models
- parse and route user chatbox input into assistant responses and app actions
- surface local and server-side functions through a controlled tool framework so the app can evolve toward an agentic workflow
- provide a foundation for additional model-backed workflows without duplicating provider logic

## Current Baseline

The existing system already provides several useful building blocks:

- `backend/services/ingestion_service.py` persists paper, chunk, formula, and subdomain-classification results, but does not perform real PDF parsing
- `backend/services/intent_learning_engine.py` learns from resolved intent history, but does not parse fresh freeform user intent
- `frontend/renderer/services/intent_service.ts` exposes intent-related API calls, but currently acts mostly as a client wrapper with mock fallback behavior
- the frontend has no dedicated chatbox pipeline yet; intent-related text entry exists only through focused forms and modals

This means the first useful implementation slice should be backend-first and provider-agnostic.

## Design Principles

1. Reuse one shared LLM orchestration layer.
Avoid separate ad hoc model integrations for PDF extraction, intent parsing, and chat.

2. Keep model outputs structured.
All LLM-facing endpoints should return validated structured payloads rather than raw text whenever possible.

3. Preserve workspace isolation.
Every LLM request must carry `workspace_id`, active domain-pack context, and optional `owner_id` / intent-branch context where relevant.

4. Let the backend own orchestration.
The frontend should not know about prompts, provider selection, or tool-level routing.

5. Build the cheap high-value paths first.
Intent parsing and chat routing are cheaper to validate than full PDF ingestion and should be implemented first.

6. Prepare for agentic execution without exposing the whole app blindly.
Local and server-side functions should be surfaced through an explicit capability layer with typed inputs, permission boundaries, and auditable execution.

## Planned Architecture

### 1. Provider Abstraction Layer

Add a backend LLM provider interface that supports:

- model selection
- structured output requests
- retries and timeouts
- provider-specific configuration
- optional streaming support later

Expected first responsibility:

- normalize calls to one initial provider while keeping room for OpenAI-compatible, Anthropic, or local/Ollama backends

Likely new backend surface:

- `backend/services/llm/` or equivalent provider package

### 2. PDF Parsing Orchestrator

Add a backend orchestration service for domain-pack-grounded PDF ingestion.

Responsibilities:

- accept a PDF or extracted PDF text plus selected domain pack / workspace context
- extract paper metadata
- extract chunks and formulas
- normalize candidate assertions against the active domain pack
- hand off persistence/classification to the existing ingestion pipeline

This service should sit above `backend/services/ingestion_service.py`, which remains the persistence and subdomain-classification stage.

### 3. Intent Parsing Service

Add a backend service that turns freeform intent text into structured intent metadata compatible with existing schemas.

Examples:

- “prefer ASIC baselines for reconfiguration delay”
- “focus on WDM papers from 2020 onward”
- “treat this assertion as locked ground truth”

Responsibilities:

- detect intent type
- detect intent scope
- extract constraints and generalization hints
- return data suitable for `sspDeclareIntent` and related intent flows

### 4. Chat Orchestration Service

Add a backend service that accepts chatbox messages and routes them into one of several app-relevant actions.

Initial route classes:

- ingest or analyze a paper
- declare or refine user intent
- query workspace/domain-pack/assertion data
- explain current app state or research context
- request suggested UI/app actions

This service should return:

- assistant-visible response text
- structured action metadata
- optional recommended follow-up operations

### 5. Frontend Chat Entry Point

After backend routes exist, add a minimal chat UI to the frontend.

Initial scope:

- message list
- composer input
- send action
- rendering of structured assistant responses

The first version should be thin and call a dedicated frontend service wrapper rather than embedding logic in components.

### 6. Agentic Function Surface

Design a framework that exposes selected local and server-side functions as structured capabilities that an assistant can inspect, plan against, and invoke.

Goals:

- make app actions available to future agent workflows without coupling the model directly to implementation details
- unify local UI actions and backend/server actions behind one typed contract
- keep permission checks, confirmation rules, and logging outside the model prompt layer

Capability categories:

- **server functions**: JSON-RPC methods, graph queries, ingestion routines, intent operations
- **local functions**: UI state changes, file picker actions, workspace switching, domain-pack loading, view navigation
- **hybrid workflows**: model proposes action plan, app resolves which local/server capabilities to invoke

Minimum framework requirements:

- typed function registry with name, description, input schema, output schema, and execution scope
- explicit distinction between read-only, mutating, and side-effectful actions
- confirmation policy for destructive or high-impact actions
- workspace and ownership context injected automatically rather than inferred from freeform prompts
- audit trail of assistant-requested function calls and their results
- capability filtering so the model only sees functions relevant to the current workspace/view/task

Suggested implementation shape:

- backend capability registry for server-executable functions
- frontend capability registry for local/Electron/UI functions
- shared action envelope that lets chat orchestration return either prose, proposed actions, or executable tool calls
- policy layer that decides whether an action runs automatically, requires confirmation, or is rejected

This capability layer should be designed early, even if only a few functions are initially exposed, because it defines the migration path from assistant-style chat to an agentic workflow.

## Planned JSON-RPC Surface

The first backend-facing LLM methods should be small and explicit:

- `parsePdfWithDomainPack`
- `parseUserIntent`
- `processChatMessage`
- optionally `getLLMStatus` or `listAvailableModels`

For the agentic function surface, the plan should also reserve space for capability-discovery and action-execution endpoints or equivalent local registries.

All of these should be workspace-aware.

## Recommended Implementation Order

### Phase 1: Foundation

- implement provider abstraction and configuration
- add shared structured-output helpers
- define request/response schemas for the new JSON-RPC methods
- define the capability registry contract for local and server-side functions

### Phase 2: Intent Parsing

- implement freeform intent parser
- expose backend endpoint
- connect existing frontend intent service to real backend parsing results

### Phase 3: Chat Routing

- implement chat message classification/routing
- expose chat endpoint
- add a thin frontend chat surface

### Phase 3.5: Agentic Capability Framework

- implement typed capability registry for backend/server actions
- design parallel registry for frontend/local actions
- add policy and confirmation rules for assistant-invoked actions
- return structured proposed actions from chat orchestration

### Phase 4: PDF Ingestion Orchestration

- implement domain-pack-grounded PDF parsing flow
- feed parsed outputs into the current ingestion/persistence pipeline
- add validation and fallback behavior for partial extraction

### Phase 5: Hardening

- tests for prompt-to-schema parsing
- mocked provider tests for routing behavior
- JSON-RPC handler tests
- integration tests for PDF ingestion orchestration
- documentation and operational guidance

## Expected File Touchpoints

Existing files likely to change first:

- `backend/services/ingestion_service.py`
- `backend/services/intent_learning_engine.py`
- `backend/server/jsonrpc_methods.py`
- `frontend/renderer/services/intent_service.ts`

Likely new files:

- backend LLM provider service(s)
- backend intent parser service
- backend chat orchestration service
- backend capability registry / action-policy service
- frontend chat service wrapper
- frontend capability registry
- frontend chat panel component

## Key Constraints

- preserve workspace isolation and current owner-aware data access
- do not reintroduce implicit global data assumptions in the model layer
- prefer structured outputs over raw prose from the model
- keep provider-specific code contained to one backend layer
- make the initial UI thin until the backend orchestration layer is stable
- expose agent-usable functions selectively rather than handing the assistant unrestricted access to app internals

## Open Decisions Before Full Implementation

1. Which provider should be supported first: OpenAI-compatible, Anthropic, or local/Ollama?
2. Should PDF parsing consume raw PDFs directly, or extracted text/layout data from a separate document parser first?
3. Should the first chat version be assistant-only, or should it also trigger app actions such as switching workspace or loading domain packs?
4. Which local and server-side functions are safe to expose in the first capability registry, and which must remain confirmation-gated?

## Summary

The recommended path is backend-first:

1. provider abstraction
2. intent parsing
3. chat routing
4. agentic capability framework
5. PDF ingestion orchestration
6. thin frontend chat UI
7. tests and hardening

This sequence minimizes architectural churn and lets the team validate the LLM integration layer on cheaper, more deterministic slices before taking on full PDF extraction.