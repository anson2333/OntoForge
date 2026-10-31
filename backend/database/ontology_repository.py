"""Neo4j persistence for the versioned ontology projection."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Iterable, Optional

from backend.schemas.ontology import (
    EntityResolutionDecision,
    EntityType,
    EvidenceBundle,
    ExperimentRecord,
    ExtractionRunRecord,
    MeasurementRecord,
    SourceVersionRecord,
)
from backend.services.ontology_constraints import (
    ONTOLOGY_RELATIONSHIPS,
    properties_for_storage,
    validate_graph_identifier,
    validate_relation,
)


GRAPH_LABELS = {
    EntityType.PAPER: "PaperNode",
    **{entity: entity.value for entity in EntityType if entity != EntityType.PAPER},
}
ALLOWED_GRAPH_LABELS = frozenset(GRAPH_LABELS.values())


def _neo4j_properties(payload: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in payload.items():
        if isinstance(value, (dict, list)) and not (
            isinstance(value, list) and all(isinstance(item, (str, int, float, bool)) for item in value)
        ):
            result[key] = json.dumps(value, ensure_ascii=False, sort_keys=True)
        elif isinstance(value, datetime):
            result[key] = value.isoformat()
        else:
            result[key] = value
    return result


def _decode_properties(payload: dict[str, Any]) -> dict[str, Any]:
    decoded = dict(payload)
    for key, value in list(decoded.items()):
        if isinstance(value, str) and value[:1] in {"{", "["}:
            try:
                decoded[key] = json.loads(value)
            except json.JSONDecodeError:
                pass
    return decoded


class OntologyRepository:
    def __init__(self, db: Any):
        self.db = db

    def merge_record(self, label: EntityType, record: Any) -> dict[str, Any]:
        safe_label = validate_graph_identifier(GRAPH_LABELS[label], ALLOWED_GRAPH_LABELS)
        properties = _neo4j_properties(properties_for_storage(record))
        records = self.db.execute_query(
            f"MERGE (n:{safe_label} {{id: $id}}) "
            "ON CREATE SET n = $properties "
            "ON MATCH SET n += $properties RETURN properties(n) AS node",
            {"id": properties["id"], "properties": properties},
        )
        return _decode_properties(records[0]["node"]) if records and "node" in records[0] else {}

    def get_run(self, run_id: str) -> dict[str, Any]:
        records = self.db.execute_query(
            "MATCH (run:ExtractionRun {id: $run_id}) RETURN properties(run) AS run",
            {"run_id": run_id},
        )
        return _decode_properties(records[0]["run"]) if records and records[0].get("run") else {}

    def merge_canonical_entity(
        self,
        *,
        entity_id: str,
        entity_type: EntityType,
        workspace_id: str,
        domain_id: str,
        canonical_name: str,
        aliases: list[str],
    ) -> None:
        label = validate_graph_identifier(GRAPH_LABELS[entity_type], ALLOWED_GRAPH_LABELS)
        self.db.execute_query(
            f"MERGE (n:{label} {{id: $id}}) SET n.workspace_id = $workspace_id, "
            "n.domain_id = $domain_id, n.canonical_name = $canonical_name, n.aliases = $aliases",
            {
                "id": entity_id, "workspace_id": workspace_id, "domain_id": domain_id,
                "canonical_name": canonical_name, "aliases": aliases,
            },
        )

    def merge_relation(
        self,
        source_id: str,
        source_type: EntityType,
        relation_type: str,
        target_id: str,
        target_type: EntityType,
        properties: Optional[dict[str, Any]] = None,
    ) -> bool:
        validate_relation(relation_type, source_type, target_type)
        relation = validate_graph_identifier(relation_type, ONTOLOGY_RELATIONSHIPS)
        source_label = validate_graph_identifier(GRAPH_LABELS[source_type], ALLOWED_GRAPH_LABELS)
        target_label = validate_graph_identifier(GRAPH_LABELS[target_type], ALLOWED_GRAPH_LABELS)
        records = self.db.execute_query(
            f"MATCH (source:{source_label} {{id: $source_id}}) "
            f"MATCH (target:{target_label} {{id: $target_id}}) "
            f"MERGE (source)-[r:{relation}]->(target) SET r += $properties RETURN count(r) AS count",
            {"source_id": source_id, "target_id": target_id, "properties": properties or {}},
        )
        return bool(records and records[0].get("count"))

    def persist_projection(
        self,
        source: SourceVersionRecord,
        run: ExtractionRunRecord,
        bundles: Iterable[EvidenceBundle],
        experiments: Iterable[ExperimentRecord],
        measurements: Iterable[MeasurementRecord],
    ) -> None:
        self.merge_record(EntityType.SOURCE_VERSION, source)
        self.db.execute_query(
            """
            MATCH (old:ExtractionRun {workspace_id: $workspace_id, source_version_id: $source_version_id})
            WHERE old.id <> $run_id AND old.status = 'committed'
            SET old.status = 'superseded'
            """,
            {
                "workspace_id": run.workspace_id,
                "source_version_id": run.source_version_id,
                "run_id": run.id,
            },
        )
        self.merge_record(EntityType.EXTRACTION_RUN, run)
        self.merge_relation(
            source.paper_id, EntityType.PAPER, "HAS_SOURCE_VERSION",
            source.id, EntityType.SOURCE_VERSION,
        )
        for bundle in bundles:
            self.merge_record(EntityType.EVIDENCE_BUNDLE, bundle)
        for experiment in experiments:
            self.merge_record(EntityType.EXPERIMENT, experiment)
            self.merge_relation(
                run.id, EntityType.EXTRACTION_RUN, "PRODUCED", experiment.id, EntityType.EXPERIMENT
            )
            self.merge_relation(
                experiment.id, EntityType.EXPERIMENT, "EVALUATES",
                experiment.model_variant_id, EntityType.MODEL_VARIANT,
            )
            if experiment.test_split_id:
                self.merge_relation(
                    experiment.id, EntityType.EXPERIMENT, "TESTED_ON",
                    experiment.test_split_id, EntityType.DATASET_SPLIT,
                )
            for split_id in experiment.training_split_ids:
                self.merge_relation(
                    experiment.id, EntityType.EXPERIMENT, "TRAINED_ON",
                    split_id, EntityType.DATASET_SPLIT,
                )
            for bundle_id in experiment.evidence_bundle_ids:
                self.merge_relation(
                    experiment.id, EntityType.EXPERIMENT, "SUPPORTED_BY",
                    bundle_id, EntityType.EVIDENCE_BUNDLE,
                )
        for measurement in measurements:
            self.merge_record(EntityType.MEASUREMENT, measurement)
            self.merge_relation(
                run.id, EntityType.EXTRACTION_RUN, "PRODUCED", measurement.id, EntityType.MEASUREMENT
            )
            self.merge_relation(
                measurement.experiment_id, EntityType.EXPERIMENT, "HAS_MEASUREMENT",
                measurement.id, EntityType.MEASUREMENT,
            )
            self.merge_relation(
                measurement.id, EntityType.MEASUREMENT, "MEASURES_METRIC",
                measurement.metric_id, EntityType.METRIC,
            )
            for bundle_id in measurement.evidence_bundle_ids:
                self.merge_relation(
                    measurement.id, EntityType.MEASUREMENT, "SUPPORTED_BY",
                    bundle_id, EntityType.EVIDENCE_BUNDLE,
                )

    def persist_resolution(self, decision: EntityResolutionDecision) -> None:
        self.merge_record(EntityType.RESOLUTION_DECISION, decision)

    def get_experiments(
        self,
        workspace_id: str,
        *,
        experiment_ids: Optional[list[str]] = None,
        model_variant_id: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        records = self.db.execute_query(
            """
            MATCH (run:ExtractionRun {workspace_id: $workspace_id, status: 'committed'})-[:PRODUCED]->(e:Experiment)
            WHERE ($experiment_ids IS NULL OR e.id IN $experiment_ids)
              AND ($model_variant_id IS NULL OR e.model_variant_id = $model_variant_id)
            OPTIONAL MATCH (e)-[:HAS_MEASUREMENT]->(m:Measurement)
            WITH e, collect(properties(m)) AS measurements
            RETURN properties(e) AS experiment, measurements
            ORDER BY e.id LIMIT $limit
            """,
            {
                "workspace_id": workspace_id, "experiment_ids": experiment_ids,
                "model_variant_id": model_variant_id, "limit": max(1, min(limit, 500)),
            },
        )
        return [
            {
                "experiment": _decode_properties(record["experiment"]),
                "measurements": [_decode_properties(item) for item in record.get("measurements", []) if item],
            }
            for record in records
        ]

    def get_gap_observations(self, workspace_id: str) -> list[dict[str, Any]]:
        records = self.db.execute_query(
            """
            MATCH (run:ExtractionRun)-[:PRODUCED]->(e:Experiment)-[:HAS_MEASUREMENT]->(m:Measurement)
            WHERE e.workspace_id = $workspace_id AND run.workspace_id = $workspace_id
              AND run.status = 'committed'
            OPTIONAL MATCH (m)-[:SUPPORTED_BY]->(bundle:EvidenceBundle)
            OPTIONAL MATCH (source:SourceVersion {id: e.source_version_id})
            OPTIONAL MATCH (paper:PaperNode {id: source.paper_id})
            RETURN run.id AS run_id, e.id AS experiment_id,
                   e.model_variant_id AS model_variant_id, e.test_split_id AS test_split_id,
                   m.id AS measurement_id, m.metric_id AS metric_id, m.metric_name AS metric_name,
                   m.quality_state AS quality_state, collect(DISTINCT bundle.id) AS evidence_ids,
                   paper.id AS paper_id, coalesce(e.component_ids, []) AS component_ids
            """,
            {"workspace_id": workspace_id},
        )
        return [dict(record) for record in records]

    def get_entity_subgraph(self, workspace_id: str, entity_id: str, limit: int = 100) -> dict[str, Any]:
        records = self.db.execute_query(
            """
            MATCH (root {id: $entity_id, workspace_id: $workspace_id})
            OPTIONAL MATCH (root)-[r]-(neighbor)
            WHERE neighbor.workspace_id = $workspace_id
            RETURN labels(root) AS root_labels, properties(root) AS root,
                   type(r) AS relation, properties(r) AS relation_properties,
                   labels(neighbor) AS neighbor_labels, properties(neighbor) AS neighbor
            LIMIT $limit
            """,
            {"entity_id": entity_id, "workspace_id": workspace_id, "limit": max(1, min(limit, 500))},
        )
        if not records:
            return {"root": None, "nodes": [], "edges": []}
        nodes: dict[str, dict[str, Any]] = {}
        edges = []
        for record in records:
            root = _decode_properties(record["root"])
            nodes[root["id"]] = {**root, "labels": record.get("root_labels", [])}
            neighbor = record.get("neighbor")
            if neighbor:
                neighbor = _decode_properties(neighbor)
                nodes[neighbor["id"]] = {**neighbor, "labels": record.get("neighbor_labels", [])}
                edges.append({
                    "type": record.get("relation"),
                    "properties": record.get("relation_properties") or {},
                    "node_ids": [root["id"], neighbor["id"]],
                })
        root_id = records[0]["root"]["id"]
        return {"root": nodes[root_id], "nodes": list(nodes.values()), "edges": edges}
