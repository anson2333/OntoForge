"""Policy-specific experiment comparability with uncertainty propagation."""

from __future__ import annotations

from backend.schemas.ontology import ComparabilityResult, ExperimentRecord


UNKNOWN = {None, "", "unknown", "unresolved", "unspecified"}

POLICIES: dict[str, tuple[str, ...]] = {
    "accuracy_v1": (
        "model_variant_id", "training_split_ids", "test_split_id", "evaluation_protocol"
    ),
    "speed_v1": (
        "test_split_id", "hardware", "input_resolution", "batch_size", "timing_scope"
    ),
}


def compare_experiments(
    first: ExperimentRecord,
    second: ExperimentRecord,
    policy_id: str,
) -> ComparabilityResult:
    if first.workspace_id != second.workspace_id:
        return ComparabilityResult(
            experiment_ids=[first.id, second.id], policy_id=policy_id,
            status="not_comparable", mismatches={"workspace_id": [first.workspace_id, second.workspace_id]},
            reasons=["Experiments from different workspaces cannot be compared"],
        )
    fields = POLICIES.get(policy_id)
    if fields is None:
        raise ValueError(f"Unknown comparability policy: {policy_id}")

    matched: list[str] = []
    unresolved: list[str] = []
    mismatches: dict[str, list[str]] = {}
    for field in fields:
        left = getattr(first, field)
        right = getattr(second, field)
        left_unknown = not left if isinstance(left, list) else left in UNKNOWN
        right_unknown = not right if isinstance(right, list) else right in UNKNOWN
        if left_unknown or right_unknown:
            unresolved.append(field)
        elif left == right:
            matched.append(field)
        else:
            mismatches[field] = [str(left), str(right)]

    hard_mismatch_fields = {
        "accuracy_v1": {"training_split_ids", "test_split_id", "evaluation_protocol"},
        "speed_v1": {"hardware", "input_resolution", "batch_size", "timing_scope"},
    }[policy_id]
    if set(mismatches) & hard_mismatch_fields:
        status = "not_comparable"
    elif mismatches or unresolved:
        status = "partially_comparable"
    else:
        status = "comparable"
    reasons = [f"Mismatch: {field}" for field in mismatches]
    reasons.extend(f"Unresolved: {field}" for field in unresolved)
    if not reasons:
        reasons.append(f"All fields required by {policy_id} match")
    return ComparabilityResult(
        experiment_ids=[first.id, second.id], policy_id=policy_id, status=status,
        matched_fields=matched, mismatches=mismatches, unresolved_fields=unresolved,
        reasons=reasons,
    )
