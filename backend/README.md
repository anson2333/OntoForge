# OntoForge Backend

## Phase A: Data Contracts + Config Loader

This is the initial implementation of the OntoForge backend, focusing on establishing type-safe data contracts and configuration loading infrastructure.

## Architecture

The backend implements a multi-tier layered system with cognitive decoupling:

- **Tier 1**: Macro Domain & Graph Topology (Strategic Intent)
- **Tier 2**: Claims & Semantic Alignment (The Matrix View)
- **Tier 3**: Physical Evidence & Symbols (Ground Truth)
- **Tier 4**: Presentation & Source Assets (PDF/Visual Surface)

## Project Structure

```
backend/
├── schemas/              # Pydantic data models
│   ├── nodes.py         # Graph node types (workspace, paper, assertion, intent, etc.)
│   ├── edges.py         # 7 graph relationship types
│   ├── protocol.py      # SSP v1.0 JSON-RPC request/response schemas
│   └── domain_pack.py   # External configuration schema
├── config/              # Configuration management
│   ├── loader.py        # YAML/JSON parser with version checking
│   ├── registries.py    # In-memory metric/alias/unit registries
│   ├── validator.py     # Business rule validation
│   ├── watcher.py       # File watcher for hot-reload
│   └── domain-pack.yaml # Sample domain configuration
└── tests/               # Unit tests (pytest)
    ├── test_nodes.py
    ├── test_edges.py
    ├── test_config_loader.py
    ├── test_registries.py
    └── test_validator.py
```

## Installation

### Prerequisites

- Python 3.11+
- pip

### Setup

```bash
# From the repo root, create the backend virtual environment with Python 3.11+
python3.11 -m venv backend/.venv
source backend/.venv/bin/activate
python -m pip install --upgrade pip

# Install dependencies
cd backend
pip install -r requirements.txt
```

If `python3.11` is not on `PATH`, use the full interpreter path from your system package manager.

## Recent Database Schema Changes

The backend now uses a workspace-isolated Neo4j model rather than treating papers/assertions as one implicit global dataset.

### Implemented changes

- `WorkspaceNode` gained optional `owner_id`
- `PaperNode` gained required `workspace_id`
- `AssertionNode` gained required `workspace_id`
- `PaperNode.domain_pack_namespace` is now used as an operational grouping/filtering field in the workspace-aware frontend
- `NodeRepository` now supports `create_workspace_node`, `get_workspace_node`, and `list_workspace_nodes`

### Query expectations

- Paper reads must filter by `workspace_id`
- Assertion reads must filter by `workspace_id`
- Workspace reads may be filtered by `owner_id`
- Seed data must create a workspace first, then insert papers/assertions with matching `workspace_id`

### Why this matters

- Prevents cross-workspace data leakage in the matrix UI
- Supports backend-managed workspace switching
- Prepares the model for future auth/authz without breaking local development

See [OntoForge.md Section 3.4](../OntoForge.md#34-implemented-schema-revision-workspace-isolation-may-2026) for the normative schema revision note.

## Usage

### Loading a Domain Pack

```python
from backend.config import DomainPackLoader, RegistryManager, DomainPackValidator

# Load and validate domain configuration
loader = DomainPackLoader()
config = loader.load("config/domain-pack.yaml", format="yaml")

# Validate business rules
DomainPackValidator.validate_or_raise(config)

# Build registries for fast lookups
manager = RegistryManager()
manager.build_from_config(config)

# Use registries
print(manager.metrics.list_all())  # List all metrics
canonical = manager.aliases.resolve("switching_delay")  # Resolve alias
normalized_unit = manager.units.normalize("millisecond")  # Normalize unit
```

### Hot-Reload Configuration

```python
from backend.config import ConfigWatcher

def on_config_change():
    print("Config changed, reloading...")
    loader.reload()
    manager.build_from_config(loader.current_config)

# Watch for file changes
watcher = ConfigWatcher(
    config_path=Path("config/domain-pack.yaml"),
    on_change_callback=on_config_change
)
watcher.start()

# ... watcher runs in background ...

watcher.stop()
```

### Using Pydantic Schemas

```python
from backend.schemas import AssertionNode, EvidencedByEdge

# Create an assertion node
assertion = AssertionNode(
    id="assert_001",
    subject="optical:reconfiguration_delay",
    predicate="equals",
    object="12.5",
    unit="ms",
    domain_pack_namespace="optical",
    context_conditions={"network_load": "80%", "topology": "mesh"},
    status="pending",
    workspace_id="workspace_5g_backhaul_2026"
)

# Create evidence edge with confidence score
evidence = EvidencedByEdge(
    from_node_id="chunk_p4_c2",
    to_node_id="assert_001",
    confidence_score=0.95
)

# Validation happens automatically
print(assertion.model_dump_json(indent=2))
```

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=backend --cov-report=term-missing

# Run specific test file
pytest tests/test_nodes.py

# Run specific test
pytest tests/test_nodes.py::TestAssertionNode::test_valid_assertion_node
```

### Inspecting PDF Parse Output

Use the inspection script to dump either the normalized snapshot view or the full parse response for a real PDF:

```bash
cd backend
python scripts/inspect_pdf_parse.py /absolute/path/to/paper.pdf
python scripts/inspect_pdf_parse.py /absolute/path/to/paper.pdf --full

# From the repo root, this also works:
python3 backend/scripts/inspect_pdf_parse.py /absolute/path/to/paper.pdf

# If you want to call the repo virtualenv interpreter directly, the script path
# must come immediately after the interpreter:
backend/.venv/bin/python backend/scripts/inspect_pdf_parse.py /absolute/path/to/paper.pdf --full
```

The default output is a concise JSON view of metadata, markdown, chunks, formulas, assertions, and warnings. Use `--full` to inspect the entire `ParsePdfWithDomainPackResponse` payload.

### Selecting A PDF Extractor

The backend now supports pluggable PDF extractors behind `parsePdfWithDomainPack`.

Default extractor:

```bash
export ONTOFORGE_PDF_EXTRACTOR=basic_pypdf
```

Optional Marker-backed extractor:

```bash
export ONTOFORGE_PDF_EXTRACTOR=marker
export ONTOFORGE_MARKER_COMMAND=/absolute/path/to/marker_single
```

Then point `ONTOFORGE_MARKER_COMMAND` at `.venvs/marker/bin/marker_single`. Additional optional flags can be controlled with:

```bash
export ONTOFORGE_MARKER_FORCE_OCR=true
export ONTOFORGE_MARKER_USE_LLM=true
export ONTOFORGE_MARKER_REDO_INLINE_MATH=true
export ONTOFORGE_MARKER_PAGE_RANGE="0-4"
```

The Marker extractor is invoked as an external command so the backend can remain usable even if Marker runs in a separate Python environment. For the complete Marker installation and usage guide, including the verified macOS x86_64 limitation, see [MARKER_SETUP.md](../MARKER_SETUP.md).

## Phase A Success Criteria

- [x] All node schemas defined with proper types (6 types)
- [x] All edge schemas defined with proper types (8 types)
- [x] SSP protocol request/response schemas complete (4 methods)
- [x] Domain pack configuration schema complete
- [x] Config loader with version checking
- [x] In-memory registries (metric, alias, unit)
- [x] Business rule validator
- [x] File watcher for hot-reload
- [x] Sample domain-pack.yaml for optical networking
- [x] Comprehensive unit tests
- [x] HITL verification fields on all node types
- [x] Test coverage ≥80% (93% achieved)

## Key Design Decisions

### 1. confidence_score Placement

The `confidence_score` is placed on the `[:EVIDENCED_BY]` edge, not on `AssertionNode`:

- **Rationale**: Maintains separation between Tier 2 (semantic assertions) and Tier 3 (extraction metadata)
- **Benefit**: Multiple evidence sources can have different confidence scores for the same assertion
- **Trade-off**: Requires edge traversal to compute aggregate confidence

See [OntoForge.md Section 3.3](../OntoForge.md#33-design-considerations) for detailed analysis.

### 2. External Domain Pack Configuration

Domain definitions are loaded from external YAML files, not hardcoded:

- **Rationale**: Enables domain-specific customization without code changes
- **Benefit**: Hot-reloadable configuration for rapid iteration
- **Protocol**: Loaded via `sspInitialize` with `configRef` parameter

### 3. Multi-Registry Architecture

Separate registries for metrics, aliases, and units:

- **MetricRegistry**: Fast lookup of metric definitions
- **AliasRegistry**: Bidirectional alias resolution
- **UnitRegistry**: Unit normalization and validation
- **RegistryManager**: Unified interface for all registries

### 4. HITL Verification Fields

Each tier has verification status fields to ensure "each tier assumes the layer beneath it is 100% deterministic":

- **Tier 1 (DomainNode)**: `approval_status: "draft" | "approved" | "deprecated"`
  - HITL gate for domain taxonomy changes (temporal inversions, metric changes)
  - Tracked via `[:APPROVES]` edge from `HumanArbitratorNode`

- **Tier 2 (AssertionNode)**: `status: "pending" | "resolved" | "locked"` ✅ (already existed)
  - HITL gate for semantic alignment conflicts
  - Tracked via `[:LOCKS]` edge from `HumanArbitratorNode`

- **Tier 3 (ChunkNode, FormulaNode)**: **5-state correction loop**
  - States: `"raw" | "under_correction" | "pending_verification" | "verified" | "rejected"`
  - **Edit surfaces**: Humans can correct OCR errors, fix LaTeX parsing
  - **Audit trail**: `last_modified_by`, `last_modified_at`, `modification_count`
  - Enables Digital Microscope workflow for iterative corrections
  - See [HITL_CORRECTION_LOOP.md](HITL_CORRECTION_LOOP.md) for full state machine

- **Tier 4 (PaperNode)**: `import_status: "pending" | "verified" | "rejected"`
  - HITL gate for source artifact integrity
  - Prevents extraction from corrupt/incomplete PDFs

## Next Steps (Phase B)

Phase B will implement the Mock Ingest Service:

- FastAPI server with JSON-RPC 2.0 over HTTP
- Implement `sspInitialize`, `sspIngest`, `sspAuditConflicts`, `sspResolveConflict`
- Mock PDF parser (returns hardcoded extraction results)
- Integration tests for full protocol flow

## License

[To Be Determined]

## Contributing

[To Be Determined]
