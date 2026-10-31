"""Counterexamples required by the ontology handoff contract."""

from __future__ import annotations

import pytest

from backend.config.loader import DomainPackLoader
from backend.schemas.ontology import (
    EntityMention,
    EntityType,
    ExperimentRecord,
    MeasurementRecord,
    QualityState,
)
from backend.services.comparability import compare_experiments
from backend.services.entity_resolution import EntityResolver
from backend.services.experiment_identity import build_experiment_identity
from backend.services.gap_analysis import analyze_gap_candidates
from backend.services.ontology_constraints import validate_experiment_measurement, validate_relation


@pytest.fixture(scope="module")
def cv_config():
    return DomainPackLoader().load("backend/configs/domain-pack-cv-detection.yaml")


def mention(text, entity_type, **context):
    return EntityMention(
        id=f"mention_{text}", workspace_id="workspace_a",
        domain_id="domain.vision.cv_detection", text=text,
        entity_type=entity_type, context=context,
    )


def test_typed_aliases_merge_vgg_but_not_fast_and_faster(cv_config):
    resolver = EntityResolver(cv_config)
    vgg_hyphen = resolver.resolve_mention(mention("VGG-16", EntityType.BACKBONE))
    vgg_plain = resolver.resolve_mention(mention("VGG16", EntityType.BACKBONE))
    assert vgg_hyphen.selected_entity_id == vgg_plain.selected_entity_id
    fast = resolver.resolve_mention(mention("Fast R-CNN", EntityType.MODEL))
    faster = resolver.resolve_mention(mention("Faster R-CNN", EntityType.MODEL))
    assert fast.selected_entity_id != faster.selected_entity_id
    proposed_wrong_merge = resolver.resolve_mention(mention(
        "Fast R-CNN", EntityType.MODEL, proposed_entity_id=faster.selected_entity_id,
    ))
    assert proposed_wrong_merge.decision.value == "distinct"
    assert proposed_wrong_merge.rule_id == "typed_exact_conflict_v1"


def test_type_and_role_prevent_component_model_merge(cv_config):
    resolver = EntityResolver(cv_config)
    as_backbone = resolver.resolve_mention(mention("VGG16", EntityType.BACKBONE))
    as_model = resolver.resolve_mention(mention("VGG16", EntityType.MODEL))
    assert as_backbone.decision.value == "same_entity"
    assert as_model.decision.value == "unresolved"
    rpn = resolver.resolve_mention(mention(
        "RPN", EntityType.COMPONENT, resolution_relation="component_of",
    ))
    assert rpn.decision.value == "component_of"


def test_dataset_compositions_remain_distinct(cv_config):
    resolver = EntityResolver(cv_config)
    voc07_12 = resolver.resolve_mention(mention("07+12", EntityType.DATASET_SPLIT))
    voc07pp12 = resolver.resolve_mention(mention("07++12", EntityType.DATASET_SPLIT))
    assert voc07_12.selected_entity_id != voc07pp12.selected_entity_id


def test_workspace_scope_changes_canonical_entity_id(cv_config):
    resolver = EntityResolver(cv_config)
    first = resolver.resolve_mention(mention("VGG16", EntityType.BACKBONE))
    second_mention = mention("VGG16", EntityType.BACKBONE)
    second_mention.workspace_id = "workspace_b"
    second = resolver.resolve_mention(second_mention)
    assert first.selected_entity_id != second.selected_entity_id


def test_unknown_conditions_do_not_merge_experiments():
    kwargs = {
        "workspace_id": "workspace_a", "source_version_id": "source_a",
        "extraction_run_id": "run_a",
        "context": {"model_variant": "unknown", "scenario": "unknown"},
    }
    first, first_basis = build_experiment_identity(assertion_id="assert_1", **kwargs)
    second, second_basis = build_experiment_identity(assertion_id="assert_2", **kwargs)
    assert first != second
    assert first_basis["unresolved_identity_guard"] == "assert_1"
    assert second_basis["unresolved_identity_guard"] == "assert_2"


def experiment(identifier, **updates):
    values = {
        "id": identifier, "workspace_id": "workspace_a", "source_version_id": "source_a",
        "extraction_run_id": "run_a", "model_variant_id": "variant_a",
        "training_split_ids": ["voc07_12"], "test_split_id": "voc2007_test",
        "evaluation_protocol": "voc07_11_point", "hardware": "Titan X",
        "input_resolution": "600px", "batch_size": "1", "timing_scope": "end_to_end",
        "quality_state": QualityState.MACHINE_CHECKED,
    }
    values.update(updates)
    return ExperimentRecord(**values)


def test_comparability_is_policy_specific_and_propagates_unknown():
    first = experiment("experiment_a")
    different_training = experiment("experiment_b", training_split_ids=["voc07pp12"])
    accuracy = compare_experiments(first, different_training, "accuracy_v1")
    assert accuracy.status == "not_comparable"
    assert "training_split_ids" in accuracy.mismatches
    unknown_hardware = experiment("experiment_c", hardware="unknown")
    speed = compare_experiments(first, unknown_hardware, "speed_v1")
    assert speed.status == "partially_comparable"
    assert "hardware" in speed.unresolved_fields


def test_dataset_total_time_cannot_be_per_image_latency():
    exp = experiment("experiment_a")
    measurement = MeasurementRecord(
        id="measurement_a", workspace_id="workspace_a", experiment_id=exp.id,
        extraction_run_id="run_a", metric_id="metric_latency", metric_name="inference_latency",
        reported_value="110", reported_unit="s", normalized_value=110000,
        normalized_unit="ms", denominator="dataset", aggregation="not_applicable",
        measurement_scope="full_pipeline", evidence_bundle_ids=["bundle_a"],
    )
    violations = validate_experiment_measurement(exp, measurement)
    assert {item.rule_id for item in violations} == {"dataset_time_not_per_image_v1"}


def test_relation_domain_and_range_are_executable():
    validate_relation("EVALUATES", EntityType.EXPERIMENT, EntityType.MODEL_VARIANT)
    with pytest.raises(ValueError, match="expects"):
        validate_relation("EVALUATES", EntityType.MODEL, EntityType.EXPERIMENT)
    with pytest.raises(ValueError, match="Unknown"):
        validate_relation("LLM_INVENTED", EntityType.MODEL, EntityType.MODEL)


def test_gap_rules_filter_pending_and_explain_paths():
    observations = [
        {
            "run_id": "run_a", "experiment_id": "exp_a", "model_variant_id": "model_a",
            "test_split_id": "voc07", "measurement_id": "m_a", "metric_id": "map",
            "quality_state": "human_verified", "evidence_ids": ["e_a"], "paper_id": "p_a",
            "component_ids": ["rpn"],
        },
        {
            "run_id": "run_b", "experiment_id": "exp_b", "model_variant_id": "model_b",
            "test_split_id": "voc12", "measurement_id": "m_b", "metric_id": "map",
            "quality_state": "human_verified", "evidence_ids": ["e_b"], "paper_id": "p_b",
            "component_ids": [],
        },
        {
            "run_id": "run_c", "experiment_id": "exp_pending", "model_variant_id": "model_a",
            "test_split_id": "voc12", "measurement_id": "m_pending", "metric_id": "map",
            "quality_state": "needs_review", "evidence_ids": ["e_c"], "paper_id": "p_c",
            "component_ids": ["rpn"],
        },
    ]
    report = analyze_gap_candidates(
        observations, workspace_id="workspace_a", synthetic=True,
    )
    assert report["input_counts"] == {"total": 3, "trusted": 2, "excluded_or_unresolved": 1}
    rules = {item["rule_id"] for item in report["candidates"]}
    assert "missing_applicable_evaluation_v1" in rules
    assert "component_transfer_question_v1" in rules
    assert all(item["supporting_paths"] for item in report["candidates"])
    assert all(item["synthetic"] for item in report["candidates"])
    assert "do not establish" in report["scope_statement"]


def test_gap_rule_requires_semantically_adjacent_metric():
    rows = [
        {
            "run_id": "run_a", "experiment_id": "exp_a", "model_variant_id": "model_a",
            "test_split_id": "voc07", "measurement_id": "m_a", "metric_id": "map",
            "quality_state": "human_verified", "evidence_ids": ["e_a"], "paper_id": "p_a",
        },
        {
            "run_id": "run_b", "experiment_id": "exp_b", "model_variant_id": "model_b",
            "test_split_id": "voc12", "measurement_id": "m_b", "metric_id": "latency",
            "quality_state": "human_verified", "evidence_ids": ["e_b"], "paper_id": "p_b",
        },
    ]
    report = analyze_gap_candidates(rows, workspace_id="workspace_a", synthetic=True)
    assert report["candidate_count"] == 0
