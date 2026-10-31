"""Stable experiment identity without treating shared unknowns as evidence."""

from __future__ import annotations

import hashlib
import json
from typing import Any


UNKNOWN_VALUES = {None, "", "unknown", "unspecified", "unresolved"}


def _known(value: Any) -> bool:
    if isinstance(value, list):
        return bool(value) and all(_known(item) for item in value)
    return value not in UNKNOWN_VALUES


def build_experiment_identity(
    *,
    workspace_id: str,
    source_version_id: str,
    extraction_run_id: str,
    context: dict[str, Any],
    assertion_id: str,
) -> tuple[str, dict[str, Any]]:
    """Return an id and its auditable basis.

    An explicit experiment/table-row id is preferred.  Otherwise a conservative
    tuple is used only when model and evaluation split are known.  If critical
    identity fields are unresolved, assertion_id is included so two unknowns do
    not silently become one experiment.
    """
    explicit = context.get("experiment_id") or context.get("source_table_row")
    model = context.get("model_variant") or context.get("detector_family")
    test_split = context.get("test_split") or context.get("scenario")
    basis: dict[str, Any] = {
        "source_version_id": source_version_id,
        "extraction_run_id": extraction_run_id,
        "model_variant": model or "unknown",
        "training_data": context.get("training_data", "unknown"),
        "test_split": test_split or "unknown",
        "evaluation_protocol": context.get("evaluation_protocol", "unknown"),
        "hardware": context.get("hardware", "unknown"),
        "input_resolution": context.get("input_resolution", "unknown"),
        "batch_size": context.get("batch_size", "unknown"),
        "timing_scope": context.get("timing_scope", "unknown"),
    }
    if explicit:
        basis["explicit_source_key"] = explicit
    elif not (_known(model) and _known(test_split)):
        basis["unresolved_identity_guard"] = assertion_id

    encoded = json.dumps(basis, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    digest = hashlib.sha256(f"{workspace_id}\0{encoded}".encode()).hexdigest()
    return f"experiment_{digest}", basis
