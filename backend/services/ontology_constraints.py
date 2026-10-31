"""Semantic constraints which are not expressible through Pydantic alone."""

from __future__ import annotations

from typing import Any

from backend.schemas.ontology import (
    ConstraintViolation,
    EntityType,
    ExperimentRecord,
    MeasurementRecord,
    QualityState,
)


RELATION_SIGNATURES: dict[str, tuple[set[EntityType], set[EntityType]]] = {
    "HAS_SOURCE_VERSION": ({EntityType.PAPER}, {EntityType.SOURCE_VERSION}),
    "HAS_EVIDENCE": ({EntityType.SOURCE_VERSION}, {EntityType.EVIDENCE}),
    "HAS_VARIANT": ({EntityType.MODEL}, {EntityType.MODEL_VARIANT}),
    "HAS_COMPONENT": ({EntityType.MODEL, EntityType.MODEL_VARIANT}, {EntityType.COMPONENT}),
    "USES_BACKBONE": (
        {EntityType.MODEL_VARIANT, EntityType.COMPONENT},
        {EntityType.BACKBONE},
    ),
    "HAS_SPLIT": ({EntityType.DATASET}, {EntityType.DATASET_SPLIT}),
    "HAS_MEMBER": ({EntityType.DATASET_SPLIT}, {EntityType.DATASET_SPLIT}),
    "EVALUATES": ({EntityType.EXPERIMENT}, {EntityType.MODEL_VARIANT}),
    "TRAINED_ON": ({EntityType.EXPERIMENT}, {EntityType.DATASET_SPLIT}),
    "TESTED_ON": ({EntityType.EXPERIMENT}, {EntityType.DATASET_SPLIT}),
    "HAS_MEASUREMENT": ({EntityType.EXPERIMENT}, {EntityType.MEASUREMENT}),
    "MEASURES_METRIC": ({EntityType.MEASUREMENT}, {EntityType.METRIC}),
    "SUPPORTED_BY": (
        {EntityType.EXPERIMENT, EntityType.MEASUREMENT},
        {EntityType.EVIDENCE_BUNDLE},
    ),
    "PRODUCED": (
        {EntityType.EXTRACTION_RUN},
        {EntityType.EXPERIMENT, EntityType.MEASUREMENT, EntityType.RESOLUTION_DECISION},
    ),
    "REVIEWS": ({EntityType.REVIEW_EVENT}, {EntityType.RESOLUTION_DECISION, EntityType.MEASUREMENT}),
}

ONTOLOGY_LABELS = frozenset(entity.value for entity in EntityType)
ONTOLOGY_RELATIONSHIPS = frozenset(RELATION_SIGNATURES)
SAFE_PROPERTY_NAMES = frozenset(
    {
        "id", "workspace_id", "domain_id", "name", "canonical_name", "entity_type",
        "source_version_id", "paper_id", "sha256", "version_label", "extraction_run_id",
        "model_variant_id", "training_split_ids", "test_split_id", "evaluation_protocol",
        "experiment_id",
        "component_ids", "backbone_ids",
        "hardware", "input_resolution", "batch_size", "timing_scope", "identity_basis",
        "quality_state", "metric_id", "reported_value", "reported_unit", "normalized_value",
        "metric_name",
        "normalized_unit", "denominator", "aggregation", "measurement_scope", "approximate",
        "legacy_assertion_id", "rule_version", "extractor", "provider", "model", "status",
        "schema_version",
        "created_at", "items", "field_support", "mention", "candidates", "selected_entity_id",
        "decision", "rule_id", "reason", "evidence_ids", "active", "reviewed_by",
        "evidence_bundle_ids",
    }
)


def validate_relation(relation_type: str, source_type: EntityType, target_type: EntityType) -> None:
    """Reject unknown relations and domain/range violations before Cypher execution."""
    signature = RELATION_SIGNATURES.get(relation_type)
    if signature is None:
        raise ValueError(f"Unknown ontology relation: {relation_type}")
    sources, targets = signature
    if source_type not in sources or target_type not in targets:
        raise ValueError(
            f"{relation_type} expects {sorted(item.value for item in sources)} -> "
            f"{sorted(item.value for item in targets)}, got {source_type.value} -> {target_type.value}"
        )


def validate_graph_identifier(value: str, allowed: frozenset[str]) -> str:
    """Return an identifier only when it comes from a static whitelist."""
    if value not in allowed:
        raise ValueError(f"Graph identifier is not allowed: {value}")
    return value


def validate_experiment_measurement(
    experiment: ExperimentRecord,
    measurement: MeasurementRecord,
) -> list[ConstraintViolation]:
    violations: list[ConstraintViolation] = []
    node_ids = [experiment.id, measurement.id]
    if experiment.workspace_id != measurement.workspace_id:
        violations.append(ConstraintViolation(
            rule_id="workspace_scope_v1", severity="error",
            message="Experiment and measurement belong to different workspaces", node_ids=node_ids,
        ))
    if experiment.extraction_run_id != measurement.extraction_run_id:
        violations.append(ConstraintViolation(
            rule_id="run_provenance_v1", severity="error",
            message="Measurement must be produced by the experiment extraction run", node_ids=node_ids,
        ))
    if measurement.experiment_id != experiment.id:
        violations.append(ConstraintViolation(
            rule_id="measurement_owner_v1", severity="error",
            message="Measurement does not reference its owning experiment", node_ids=node_ids,
        ))

    metric = measurement.metric_name.lower()
    if "latency" in metric or metric.endswith("time"):
        if measurement.denominator == "dataset" and measurement.measurement_scope in {
            "full_pipeline", "detector_only"
        }:
            violations.append(ConstraintViolation(
                rule_id="dataset_time_not_per_image_v1", severity="error",
                message="Dataset-total time cannot be used as per-image detector latency", node_ids=node_ids,
            ))
        if measurement.denominator == "image" and experiment.timing_scope in {
            "proposal_only", "component_only"
        }:
            violations.append(ConstraintViolation(
                rule_id="component_time_not_detector_latency_v1", severity="error",
                message="Component timing cannot be represented as detector latency", node_ids=node_ids,
            ))

    if measurement.aggregation == "per_class" and "map" in metric:
        violations.append(ConstraintViolation(
            rule_id="per_class_not_overall_map_v1", severity="error",
            message="Per-class AP cannot be represented as overall mAP", node_ids=node_ids,
        ))
    if measurement.aggregation == "relative" and measurement.normalized_value is not None:
        violations.append(ConstraintViolation(
            rule_id="relative_not_absolute_v1", severity="error",
            message="Relative improvement cannot be normalized as an absolute metric", node_ids=node_ids,
        ))
    if not experiment.test_split_id and measurement.quality_state in {
        QualityState.MACHINE_CHECKED, QualityState.HUMAN_VERIFIED
    } and any(token in metric for token in ("map", "ap")):
        violations.append(ConstraintViolation(
            rule_id="accuracy_requires_test_split_v1", severity="error",
            message="Verified accuracy requires a resolved evaluation split", node_ids=node_ids,
        ))
    return violations


def properties_for_storage(model: Any) -> dict[str, Any]:
    """Serialize model properties and reject accidental unbounded graph fields."""
    payload = model.model_dump(mode="json", exclude_none=True)
    unknown = set(payload) - SAFE_PROPERTY_NAMES
    if unknown:
        raise ValueError(f"Ontology storage properties are not whitelisted: {sorted(unknown)}")
    return payload
