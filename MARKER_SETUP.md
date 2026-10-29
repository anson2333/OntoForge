# Marker Setup And Usage

This document is the single source of truth for installing and using Marker with OntoForge.

## What OntoForge expects

OntoForge does not import Marker as a Python library inside the backend environment. The backend shells out to an external `marker_single` command from `backend/services/pdf_ingestion_service.py`.

The integration expects the modern Marker CLI that supports:

- `--output_dir`
- `--output_format`

When `ONTOFORGE_PDF_EXTRACTOR=marker`, OntoForge runs Marker twice for each PDF:

- once with `--output_format markdown`
- once with `--output_format json`

The old `marker-pdf` CLI line from older releases is not sufficient for this workflow.

## Python requirement

Use Python 3.11 for local setup in this repository.

The repository baseline is pinned in `.python-version`:

```text
3.11.15
```

## Recommended installation layout

Keep Marker in its own virtual environment instead of installing it into `backend/.venv`.

This keeps the backend runtime isolated and lets OntoForge call Marker as an external tool.

From the repository root:

```bash
python3.11 -m venv .venvs/marker
source .venvs/marker/bin/activate
python -m pip install --upgrade pip
pip install torch marker-pdf
```

Verify that the CLI matches what OntoForge expects:

```bash
.venvs/marker/bin/marker_single --help
```

You should see options including `--output_dir` and `--output_format`.

## Wiring Marker into OntoForge

Set the backend to use the Marker extractor and point it at the external CLI:

```bash
export ONTOFORGE_PDF_EXTRACTOR=marker
export ONTOFORGE_MARKER_COMMAND=/absolute/path/to/marker_single
```

Example using the repository-local Marker environment:

```bash
export ONTOFORGE_PDF_EXTRACTOR=marker
export ONTOFORGE_MARKER_COMMAND=/Users/sunweiqiang/Documents/Projects/OntoForge/.venvs/marker/bin/marker_single
```

Start the backend after exporting those variables:

```bash
source backend/.venv/bin/activate
set -a
source .env
set +a
python -m uvicorn backend.server.app:app --reload --host "${BACKEND_HOST:-0.0.0.0}" --port "${BACKEND_PORT:-8765}"
```

## Optional Marker flags supported by OntoForge

The backend currently forwards these environment variables to `marker_single`:

```bash
export ONTOFORGE_MARKER_FORCE_OCR=true
export ONTOFORGE_MARKER_USE_LLM=true
export ONTOFORGE_MARKER_REDO_INLINE_MATH=true
export ONTOFORGE_MARKER_PAGE_RANGE="0-4"
```

Mapping:

- `ONTOFORGE_MARKER_FORCE_OCR=true` adds `--force_ocr`
- `ONTOFORGE_MARKER_USE_LLM=true` adds `--use_llm`
- `ONTOFORGE_MARKER_REDO_INLINE_MATH=true` adds `--redo_inline_math`
- `ONTOFORGE_MARKER_PAGE_RANGE="0-4"` adds `--page_range 0-4`

If `ONTOFORGE_MARKER_COMMAND` is unset, the backend falls back to `marker_single` from `PATH`.

## Quick smoke checks

### 1. Verify package versions

```bash
source .venvs/marker/bin/activate
python -c 'import importlib.metadata as m; print(m.version("marker-pdf")); print(m.version("surya-ocr")); print(m.version("torch"))'
```

### 2. Verify the CLI is available

```bash
source .venvs/marker/bin/activate
marker_single --help
```

### 3. Run a direct Marker conversion test

```bash
source .venvs/marker/bin/activate
marker_single /absolute/path/to/paper.pdf --output_dir /tmp/marker-out --output_format markdown
marker_single /absolute/path/to/paper.pdf --output_dir /tmp/marker-json --output_format json
```

If these commands fail, OntoForge will fail for the same reason because it uses the same CLI surface.

## Current verified status on this Mac

The current repository machine is macOS x86_64. Marker installation is only partially successful here.

Verified state:

- `marker-pdf==1.10.2`
- `surya-ocr==0.17.1`
- `torch==2.2.2`

What works:

- `marker_single` installs
- `marker_single --help` works
- the CLI shape matches what OntoForge expects

What does not work reliably:

- full PDF conversion at runtime

Why:

- current upstream `marker-pdf` and `surya-ocr` require `torch>=2.7`
- on this macOS x86_64 host, available PyTorch wheels stop at `2.2.2`
- forcing `TORCH_DEVICE=cpu` avoids the MPS `bfloat16` error, but conversion still fails later because newer Torch APIs are missing

## Supported path for production use

If you need Marker-backed extraction to actually run, use one of these environments:

- Linux host with supported PyTorch wheels
- containerized Linux runtime
- another supported machine where `torch>=2.7` is available

Then point `ONTOFORGE_MARKER_COMMAND` at that working `marker_single` binary or wrapper.

## Troubleshooting

### `Marker extractor selected but command 'marker_single' is not available`

Set `ONTOFORGE_MARKER_COMMAND` to a real executable path:

```bash
export ONTOFORGE_MARKER_COMMAND=/absolute/path/to/marker_single
```

### CLI exists, but conversion fails

Run the command directly outside the backend first:

```bash
source .venvs/marker/bin/activate
marker_single /absolute/path/to/paper.pdf --output_dir /tmp/marker-out --output_format markdown
```

If the direct command fails, the issue is the Marker runtime, not OntoForge.

### MPS `bfloat16` failure on macOS

You can try CPU mode:

```bash
export TORCH_DEVICE=cpu
```

On this machine that only gets past the first failure mode; it does not make the full conversion path supported.