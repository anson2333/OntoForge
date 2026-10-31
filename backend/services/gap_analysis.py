"""Explainable graph-rule research gap candidates.

The rules operate on graph observations returned by OntologyRepository.  They
never create missing facts and never claim novelty outside the selected corpus.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from typing import Any, Iterable

from backend.schemas.ontology import GapCandidate, SupportingPath


DEFAULT_TRUSTED_STATES = frozenset({"human_verified"})


def _candidate_id(rule_id: str, payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=True, default=str)
    return "gap_" + hashlib.sha256(f"{rule_id}\0{encoded}".encode()).hexdigest()


def _path(row: dict[str, Any]) -> SupportingPath:
    nodes = [
        row.get("experiment_id"), row.get("model_variant_id"), row.get("test_split_id"),
        row.get("measurement_id"), row.get("metric_id"),
    ]
    return SupportingPath(
        node_ids=[item for item in nodes if item],
        edge_ids=list(row.get("edge_ids") or []),
        evidence_ids=list(row.get("evidence_ids") or []),
        paper_ids=[row["paper_id"]] if row.get("paper_id") else [],
    )


def analyze_gap_candidates(
    observations: Iterable[dict[str, Any]],
    *,
    workspace_id: str,
    trusted_states: frozenset[str] = DEFAULT_TRUSTED_STATES,
    synthetic: bool = False,
    limit: int = 50,
) -> dict[str, Any]:
    rows = [dict(row) for row in observations]
    trusted = [row for row in rows if row.get("quality_state") in trusted_states]
    unresolved_count = len(rows) - len(trusted)
    run_ids = sorted({row.get("run_id") for row in trusted if row.get("run_id")})
    candidates: list[GapCandidate] = []

    # Rule A: a model has trusted evaluation on one setting, a second setting is
    # populated by neighboring models, but this model-setting edge is absent.
    by_model: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_split: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in trusted:
        if row.get("model_variant_id") and row.get("test_split_id"):
            by_model[row["model_variant_id"]].append(row)
            by_split[row["test_split_id"]].append(row)

    for model_id, model_rows in sorted(by_model.items()):
        covered = {row["test_split_id"] for row in model_rows}
        for split_id, split_rows in sorted(by_split.items()):
            if split_id in covered:
                continue
            shared_metrics = sorted(
                {row.get("metric_id") for row in model_rows if row.get("metric_id")}
                & {row.get("metric_id") for row in split_rows if row.get("metric_id")}
            )
            if not shared_metrics:
                continue
            support = [model_rows[0], split_rows[0]]
            payload = {
                "model_variant_id": model_id, "test_split_id": split_id,
                "shared_metrics": shared_metrics,
            }
            candidates.append(GapCandidate(
                id=_candidate_id("missing_applicable_evaluation_v1", payload),
                kind="coverage_missing", workspace_id=workspace_id,
                source_run_ids=run_ids, rule_id="missing_applicable_evaluation_v1", rule_version="1.0",
                supporting_paths=[_path(row) for row in support],
                missing_relation={
                    "type": "TESTED_ON", "from_type": "Experiment", "from": "hypothetical",
                    "to": split_id, "model_variant_id": model_id,
                },
                checks={
                    "applicable": True, "critical_context_resolved": True,
                    "shared_metric_ids": shared_metrics,
                },
                status="candidate",
                claim=(
                    "Within the selected, quality-filtered corpus, this model variant has neighboring "
                    "evaluation evidence but no report on the target split. This is not a global novelty claim."
                ),
                verification_question=f"Has {model_id} been evaluated on {split_id} under comparable conditions?",
                score_signals={"model_support": float(len(model_rows)), "setting_support": float(len(split_rows))},
                synthetic=synthetic,
            ))

    # Rule B: a component has trusted evidence in setting A, while setting B is
    # active in the corpus but no trusted experiment using that component exists.
    by_component: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in trusted:
        for component_id in row.get("component_ids") or []:
            by_component[component_id].append(row)
    for component_id, component_rows in sorted(by_component.items()):
        covered = {row.get("test_split_id") for row in component_rows}
        for split_id, split_rows in sorted(by_split.items()):
            if split_id in covered:
                continue
            shared_metrics = sorted(
                {row.get("metric_id") for row in component_rows if row.get("metric_id")}
                & {row.get("metric_id") for row in split_rows if row.get("metric_id")}
            )
            if not shared_metrics:
                continue
            payload = {
                "component_id": component_id, "test_split_id": split_id,
                "shared_metrics": shared_metrics,
            }
            candidates.append(GapCandidate(
                id=_candidate_id("component_transfer_question_v1", payload),
                kind="research_hypothesis_candidate", workspace_id=workspace_id,
                source_run_ids=run_ids, rule_id="component_transfer_question_v1", rule_version="1.0",
                supporting_paths=[_path(component_rows[0]), _path(split_rows[0])],
                missing_relation={
                    "type": "TESTED_ON", "from_type": "hypothetical Experiment",
                    "component_id": component_id, "to": split_id,
                },
                checks={
                    "applicable": True, "critical_context_resolved": True,
                    "shared_metric_ids": shared_metrics,
                },
                status="needs_evidence",
                claim=(
                    "The component has supported results in another setting, while the target setting has "
                    "neighboring evidence. Transfer effectiveness remains an untested hypothesis."
                ),
                verification_question=f"Does {component_id} retain its measured effect on {split_id}?",
                score_signals={"component_support": float(len(component_rows)), "setting_support": float(len(split_rows))},
                synthetic=synthetic,
            ))

    candidates.sort(
        key=lambda candidate: (
            -sum(candidate.score_signals.values()), candidate.kind, candidate.id
        )
    )
    return {
        "candidates": [candidate.model_dump(mode="json") for candidate in candidates[: max(0, limit)]],
        "candidate_count": len(candidates),
        "quality_policy": {"trusted_states": sorted(trusted_states)},
        "input_counts": {
            "total": len(rows), "trusted": len(trusted), "excluded_or_unresolved": unresolved_count,
        },
        "scope_statement": (
            "Candidates describe missing evidence in the selected workspace corpus; "
            "they do not establish that the wider field has not studied the question."
        ),
    }
