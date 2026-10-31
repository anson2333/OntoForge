"""Executable ontology contracts for the CV literature knowledge graph.

These models deliberately separate raw mentions, machine decisions, evidence
support and human review.  A Pydantic model is not an ontology reasoner; the
semantic domain/range and measurement rules live in ontology_constraints.py.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, model_validator


class EntityType(StrEnum):
    PAPER = "Paper"
    SOURCE_VERSION = "SourceVersion"
    MODEL = "Model"
    MODEL_VARIANT = "ModelVariant"
    COMPONENT = "Component"
    BACKBONE = "Backbone"
    DATASET = "Dataset"
    DATASET_SPLIT = "DatasetSplit"
    EXPERIMENT = "Experiment"
    MEASUREMENT = "Measurement"
    METRIC = "Metric"
    EVIDENCE = "Evidence"
    EVIDENCE_BUNDLE = "EvidenceBundle"
    EXTRACTION_RUN = "ExtractionRun"
    RESOLUTION_DECISION = "ResolutionDecision"
    REVIEW_EVENT = "ReviewEvent"


class SupportStatus(StrEnum):
    SUPPORTED = "supported"
    CONTRADICTED = "contradicted"
    UNRESOLVED = "unresolved"
    NOT_APPLICABLE = "not_applicable"


class QualityState(StrEnum):
    RAW = "raw"
    MACHINE_CHECKED = "machine_checked"
    NEEDS_REVIEW = "needs_review"
    HUMAN_VERIFIED = "human_verified"
    REJECTED = "rejected"
    LEGACY_UNRESOLVED = "legacy_unresolved"


class ResolutionKind(StrEnum):
    SAME_ENTITY = "same_entity"
    VARIANT_OF = "variant_of"
    COMPONENT_OF = "component_of"
    DISTINCT = "distinct"
    UNRESOLVED = "unresolved"


class EvidenceItem(BaseModel):
    id: str
    source_version_id: str
    item_type: Literal["chunk", "table", "table_cell", "caption", "footnote", "formula"]
    source_node_id: str
    quote: Optional[str] = None
    page: Optional[int] = Field(default=None, ge=1)
    bounding_box: Optional[dict[str, Any]] = None
    coordinate_status: Literal["available", "page_only", "unavailable"] = "unavailable"


class FieldSupport(BaseModel):
    field_name: str
    status: SupportStatus
    evidence_item_ids: list[str] = Field(default_factory=list)
    origin: Literal["program", "model", "human"] = "program"
    rule_id: str
    reason: str = ""


class EvidenceBundle(BaseModel):
    id: str
    workspace_id: str
    source_version_id: str
    items: list[EvidenceItem] = Field(min_length=1)
    field_support: list[FieldSupport] = Field(default_factory=list)
    rule_version: str

    @model_validator(mode="after")
    def references_local_items(self):
        item_ids = {item.id for item in self.items}
        for support in self.field_support:
            missing = set(support.evidence_item_ids) - item_ids
            if missing:
                raise ValueError(f"Field support references missing evidence items: {sorted(missing)}")
        return self


class EntityMention(BaseModel):
    id: str
    workspace_id: str
    domain_id: str
    text: str = Field(min_length=1)
    entity_type: EntityType
    source_version_id: Optional[str] = None
    evidence_ids: list[str] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)


class EntityCandidate(BaseModel):
    entity_id: str
    canonical_name: str
    entity_type: EntityType
    score: float = Field(ge=0.0, le=1.0)
    matched_alias: Optional[str] = None


class EntityResolutionDecision(BaseModel):
    id: str
    workspace_id: str
    domain_id: str
    mention: EntityMention
    candidates: list[EntityCandidate] = Field(default_factory=list)
    selected_entity_id: Optional[str] = None
    decision: ResolutionKind
    rule_id: str
    rule_version: str
    reason: str
    evidence_ids: list[str] = Field(default_factory=list)
    active: bool = True
    reviewed_by: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="after")
    def selected_candidate_is_consistent(self):
        candidate_ids = {candidate.entity_id for candidate in self.candidates}
        if self.selected_entity_id and self.selected_entity_id not in candidate_ids:
            raise ValueError("selected_entity_id must refer to a candidate")
        if self.decision in {ResolutionKind.SAME_ENTITY, ResolutionKind.VARIANT_OF, ResolutionKind.COMPONENT_OF}:
            if not self.selected_entity_id:
                raise ValueError(f"{self.decision} requires selected_entity_id")
        return self


class SourceVersionRecord(BaseModel):
    id: str
    workspace_id: str
    paper_id: str
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    version_label: str = "imported-pdf"


class ExtractionRunRecord(BaseModel):
    id: str
    workspace_id: str
    source_version_id: str
    domain_id: str
    schema_version: str
    rule_version: str
    extractor: str
    provider: str
    model: Optional[str] = None
    status: Literal["previewed", "committed", "failed", "superseded"] = "committed"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ExperimentRecord(BaseModel):
    id: str
    workspace_id: str
    source_version_id: str
    extraction_run_id: str
    model_variant_id: str
    component_ids: list[str] = Field(default_factory=list)
    backbone_ids: list[str] = Field(default_factory=list)
    training_split_ids: list[str] = Field(default_factory=list)
    test_split_id: Optional[str] = None
    evaluation_protocol: str = "unknown"
    hardware: str = "unknown"
    input_resolution: str = "unknown"
    batch_size: str = "unknown"
    timing_scope: Literal[
        "end_to_end", "detector_only_excludes_proposals", "proposal_only",
        "component_only", "unknown", "not_applicable"
    ] = "unknown"
    evidence_bundle_ids: list[str] = Field(default_factory=list)
    identity_basis: dict[str, Any] = Field(default_factory=dict)
    quality_state: QualityState = QualityState.NEEDS_REVIEW


class MeasurementRecord(BaseModel):
    id: str
    workspace_id: str
    experiment_id: str
    extraction_run_id: str
    metric_id: str
    metric_name: str
    reported_value: str
    reported_unit: str
    normalized_value: Optional[float] = None
    normalized_unit: Optional[str] = None
    denominator: Literal["image", "dataset", "batch", "unknown", "not_applicable"] = "unknown"
    aggregation: Literal["overall", "per_class", "relative", "unknown", "not_applicable"] = "unknown"
    measurement_scope: Literal[
        "full_pipeline", "detector_only", "proposal_only", "component_only",
        "unknown", "not_applicable"
    ] = "unknown"
    evidence_bundle_ids: list[str] = Field(min_length=1)
    approximate: bool = False
    quality_state: QualityState = QualityState.NEEDS_REVIEW
    legacy_assertion_id: Optional[str] = None


class ConstraintViolation(BaseModel):
    rule_id: str
    severity: Literal["error", "warning"]
    message: str
    node_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)


class ComparabilityResult(BaseModel):
    experiment_ids: list[str] = Field(min_length=2, max_length=2)
    policy_id: str
    status: Literal["comparable", "partially_comparable", "not_comparable"]
    matched_fields: list[str] = Field(default_factory=list)
    mismatches: dict[str, list[str]] = Field(default_factory=dict)
    unresolved_fields: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)


class SupportingPath(BaseModel):
    node_ids: list[str]
    edge_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    paper_ids: list[str] = Field(default_factory=list)


class GapCandidate(BaseModel):
    id: str
    kind: Literal["coverage_missing", "alignment_or_conflict_issue", "research_hypothesis_candidate"]
    workspace_id: str
    source_run_ids: list[str]
    rule_id: str
    rule_version: str
    supporting_paths: list[SupportingPath]
    missing_relation: Optional[dict[str, Any]] = None
    issue: Optional[dict[str, Any]] = None
    checks: dict[str, Any]
    exclusions: list[str] = Field(default_factory=list)
    unresolved: list[str] = Field(default_factory=list)
    status: Literal["candidate", "needs_evidence", "excluded", "retracted"]
    claim: str
    verification_question: str
    score_signals: dict[str, float] = Field(default_factory=dict)
    synthetic: bool = False
