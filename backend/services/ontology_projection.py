"""Convert the legacy assertion preview into a versioned ontology projection."""

from __future__ import annotations

import hashlib
import re
from collections import OrderedDict
from typing import Any

from backend.database.ontology_repository import OntologyRepository
from backend.schemas.domain_pack import DomainPackConfig
from backend.schemas.ontology import (
    EntityType,
    EvidenceBundle,
    EvidenceItem,
    ExperimentRecord,
    ExtractionRunRecord,
    FieldSupport,
    MeasurementRecord,
    QualityState,
    SourceVersionRecord,
    SupportStatus,
)
from backend.services.entity_resolution import normalized_mention, scoped_entity_id
from backend.services.experiment_identity import build_experiment_identity
from backend.services.ontology_constraints import validate_experiment_measurement


def _stable_id(prefix: str, *parts: str) -> str:
    return prefix + hashlib.sha256("\0".join(parts).encode()).hexdigest()


def _context_value(context: dict[str, Any], *names: str, default: str = "unknown") -> str:
    for name in names:
        value = context.get(name)
        if value is not None and str(value).strip():
            return str(value).strip()
    return default


def _canonical_definition(config: DomainPackConfig, entity_type: EntityType, mention: str):
    key = normalized_mention(mention)
    for definition in config.ontology.entities:
        if definition.entity_type != entity_type.value:
            continue
        if any(normalized_mention(term) == key for term in [definition.name, *definition.aliases]):
            return definition
    return None


def _entity(
    repo: OntologyRepository,
    config: DomainPackConfig,
    workspace_id: str,
    entity_type: EntityType,
    mention: str,
) -> str:
    definition = _canonical_definition(config, entity_type, mention)
    local_id = definition.id if definition else f"unresolved.{normalized_mention(mention) or 'unknown'}"
    entity_id = scoped_entity_id(workspace_id, config.domain.id, entity_type.value, local_id)
    repo.merge_canonical_entity(
        entity_id=entity_id,
        entity_type=entity_type,
        workspace_id=workspace_id,
        domain_id=config.domain.id,
        canonical_name=definition.name if definition else mention or "unknown",
        aliases=definition.aliases if definition else [],
    )
    return entity_id


def _split_mentions(value: str) -> list[str]:
    text = value.strip()
    if not text or text.lower() in {"unknown", "not_applicable"}:
        return []
    # Composite splits (07+12 and 07++12) have their own canonical identity.
    return [text]


def _numeric(value: str) -> float | None:
    match = re.fullmatch(r"\s*[~≈]?\s*([-+]?\d+(?:\.\d+)?)\s*", value or "")
    return float(match.group(1)) if match else None


def _measurement_semantics(metric_name: str, unit: str, context: dict[str, Any]):
    metric_lower = metric_name.lower()
    if "latency" in metric_lower or "time" in metric_lower:
        denominator = _context_value(context, "denominator", "timing_denominator")
        if denominator not in {"image", "dataset", "batch", "unknown", "not_applicable"}:
            denominator = "unknown"
        timing_scope = context.get("timing_scope", "unknown")
        scope_map = {
            "end_to_end": "full_pipeline",
            "detector_only_excludes_proposals": "detector_only",
            "proposal_only": "proposal_only",
            "component_only": "component_only",
        }
        return denominator, "not_applicable", scope_map.get(timing_scope, "unknown")
    aggregation = _context_value(context, "aggregation", default="overall")
    if aggregation not in {"overall", "per_class", "relative", "unknown", "not_applicable"}:
        aggregation = "unknown"
    return "not_applicable", aggregation, "not_applicable"


def persist_preview_projection(
    *,
    repo: OntologyRepository,
    workspace_id: str,
    paper_id: str,
    provenance_hash: str,
    preview_id: str,
    parse_result: Any,
    config: DomainPackConfig,
    global_evidence_id,
) -> dict[str, Any]:
    source_id = _stable_id("source_", workspace_id, paper_id, provenance_hash)
    run_id = "run_" + preview_id.removeprefix("preview_")
    existing_run = repo.get_run(run_id)
    if existing_run:
        return {
            "run_id": run_id, "experiments_created": 0, "measurements_created": 0,
            "constraint_violations": [],
        }
    source = SourceVersionRecord(
        id=source_id, workspace_id=workspace_id, paper_id=paper_id, sha256=provenance_hash,
    )
    run = ExtractionRunRecord(
        id=run_id, workspace_id=workspace_id, source_version_id=source_id,
        domain_id=config.domain.id, schema_version=config.schema_version,
        rule_version=config.ontology.rule_version,
        extractor=parse_result.extraction_method or "unknown",
        provider=parse_result.assertion_extraction_method or "unknown",
    )

    bundles: list[EvidenceBundle] = []
    experiments_by_id: OrderedDict[str, ExperimentRecord] = OrderedDict()
    measurements: list[MeasurementRecord] = []
    violations = []
    for assertion in parse_result.assertions:
        assertion_id = f"{paper_id}::{assertion.assertion_id}"
        context = dict(assertion.context_conditions or {})
        evidence_items = []
        for index, link in enumerate(assertion.evidence_links):
            evidence_items.append(EvidenceItem(
                id=_stable_id("evidence_item_", run_id, assertion_id, str(index)),
                source_version_id=source_id,
                item_type="chunk",
                source_node_id=global_evidence_id(link.source_id),
                coordinate_status="page_only",
            ))
        if not evidence_items:
            continue
        issues = set(context.get("condition_validation_issues") or [])
        support = [FieldSupport(
            field_name="measurement.value", status=SupportStatus.SUPPORTED,
            evidence_item_ids=[item.id for item in evidence_items], origin="program",
            rule_id="legacy_evidence_link_v1",
            reason="The extracted assertion cites existing source chunks; semantic review remains separate",
        )]
        for field in ("detector_backbone", "proposal_backbone", "timing_scope"):
            status = SupportStatus.UNRESOLVED if any(field in issue for issue in issues) else SupportStatus.SUPPORTED
            if context.get(field) == "not_applicable":
                status = SupportStatus.NOT_APPLICABLE
            support.append(FieldSupport(
                field_name=f"experiment.{field}", status=status,
                evidence_item_ids=[item.id for item in evidence_items] if status == SupportStatus.SUPPORTED else [],
                origin="program", rule_id="condition_guard_projection_v1",
                reason="Projected from the condition guard without claiming human verification",
            ))
        bundle = EvidenceBundle(
            id=_stable_id("bundle_", run_id, assertion_id), workspace_id=workspace_id,
            source_version_id=source_id, items=evidence_items, field_support=support,
            rule_version=config.ontology.rule_version,
        )
        bundles.append(bundle)

        model_mention = _context_value(context, "model_variant", "detector_family")
        model_id = _entity(repo, config, workspace_id, EntityType.MODEL_VARIANT, model_mention)
        test_mention = _context_value(context, "test_split", "scenario")
        test_split_id = None
        if test_mention not in {"unknown", "unspecified", "not_applicable"}:
            test_split_id = _entity(repo, config, workspace_id, EntityType.DATASET_SPLIT, test_mention)
        training_split_ids = [
            _entity(repo, config, workspace_id, EntityType.DATASET_SPLIT, mention)
            for mention in _split_mentions(_context_value(context, "training_data"))
        ]
        experiment_id, identity_basis = build_experiment_identity(
            workspace_id=workspace_id, source_version_id=source_id,
            extraction_run_id=run_id,
            context=context, assertion_id=assertion_id,
        )
        machine_checked = (
            context.get("condition_validation") == "quote_grounded_not_human_verified" and not issues
        )
        quality = QualityState.MACHINE_CHECKED if machine_checked else QualityState.NEEDS_REVIEW
        if experiment_id not in experiments_by_id:
            component_ids = []
            proposal = _context_value(context, "proposal_component", default="unknown")
            if proposal not in {"unknown", "not_applicable"}:
                component_ids.append(_entity(repo, config, workspace_id, EntityType.COMPONENT, proposal))
            backbone_ids = []
            for field in ("detector_backbone", "proposal_backbone"):
                mention = _context_value(context, field)
                if mention not in {"unknown", "not_applicable"}:
                    backbone_ids.append(_entity(repo, config, workspace_id, EntityType.BACKBONE, mention))
            timing_scope = _context_value(context, "timing_scope")
            if timing_scope not in {
                "end_to_end", "detector_only_excludes_proposals", "proposal_only",
                "component_only", "unknown", "not_applicable",
            }:
                timing_scope = "unknown"
            experiments_by_id[experiment_id] = ExperimentRecord(
                id=experiment_id, workspace_id=workspace_id, source_version_id=source_id,
                extraction_run_id=run_id, model_variant_id=model_id,
                component_ids=list(dict.fromkeys(component_ids)),
                backbone_ids=list(dict.fromkeys(backbone_ids)),
                training_split_ids=training_split_ids, test_split_id=test_split_id,
                evaluation_protocol=_context_value(context, "evaluation_protocol"),
                hardware=_context_value(context, "hardware"),
                input_resolution=_context_value(context, "input_resolution"),
                batch_size=_context_value(context, "batch_size"),
                timing_scope=timing_scope,
                evidence_bundle_ids=[bundle.id], identity_basis=identity_basis,
                quality_state=quality,
            )
        else:
            experiments_by_id[experiment_id].evidence_bundle_ids.append(bundle.id)

        metric_name = assertion.subject.rsplit(":", 1)[-1]
        metric_id = _entity(repo, config, workspace_id, EntityType.METRIC, metric_name)
        denominator, aggregation, measurement_scope = _measurement_semantics(
            metric_name, assertion.unit, context
        )
        value = _numeric(assertion.object)
        normalized_value = value
        normalized_unit = assertion.unit
        metric_definition = next((item for item in config.core_metrics if item.name == metric_name), None)
        if metric_definition and value is not None:
            factor = metric_definition.unit_conversions.get(assertion.unit)
            if factor:
                normalized_value = value * factor
                normalized_unit = metric_definition.expected_unit
        measurement = MeasurementRecord(
            id=_stable_id("measurement_", run_id, assertion_id), workspace_id=workspace_id,
            experiment_id=experiment_id, extraction_run_id=run_id, metric_id=metric_id,
            metric_name=metric_name,
            reported_value=assertion.object, reported_unit=assertion.unit,
            normalized_value=normalized_value, normalized_unit=normalized_unit,
            denominator=denominator, aggregation=aggregation, measurement_scope=measurement_scope,
            evidence_bundle_ids=[bundle.id], approximate=bool(re.search(r"[~≈]", assertion.object)),
            quality_state=quality, legacy_assertion_id=assertion_id,
        )
        violations.extend(validate_experiment_measurement(experiments_by_id[experiment_id], measurement))
        measurements.append(measurement)

    repo.persist_projection(source, run, bundles, experiments_by_id.values(), measurements)
    return {
        "run_id": run_id,
        "experiments_created": len(experiments_by_id),
        "measurements_created": len(measurements),
        "constraint_violations": [item.model_dump(mode="json") for item in violations],
    }
