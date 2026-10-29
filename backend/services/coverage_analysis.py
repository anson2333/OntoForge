"""Coverage analysis across method × scenario × metric combinations.

The report answers two questions over a workspace graph:

- Coverage: which (method, scenario, metric) cells already have evidence?
- Gaps: which combinations have no assertions yet, ranked by how strongly the
  surrounding evidence suggests they are worth investigating.

Method and scenario are read from assertion context conditions (for example
``{"method": "wdm", "scenario": "access_network"}``) and normalized so that the
same concept is never counted twice because of casing or separators.
"""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional, Sequence

from backend.schemas.domain_pack import DomainPackConfig
from backend.services.normalization import (
    canonical_metric_from_subject,
    normalize_dimension_value,
)
from backend.services.pdf_ingestion_service import load_domain_pack_config

METHOD_CONTEXT_KEYS = ("method", "switching_mechanism", "technology", "technique")
SCENARIO_CONTEXT_KEYS = (
    "scenario",
    "topology",
    "application_domain",
    "network_layer",
    "deployment",
)
UNSPECIFIED = "unspecified"


def _parse_context(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _first_context_value(context: Dict[str, Any], keys: Sequence[str]) -> Any:
    for key in keys:
        value = context.get(key)
        if value is not None and str(value).strip():
            return value
    return None


def derive_method(context: Dict[str, Any]) -> str:
    """Extract the research method from assertion context conditions."""
    return normalize_dimension_value(_first_context_value(context, METHOD_CONTEXT_KEYS))


def derive_scenario(context: Dict[str, Any]) -> str:
    """Extract the application scenario from assertion context conditions."""
    return normalize_dimension_value(_first_context_value(context, SCENARIO_CONTEXT_KEYS))


def _record_get(record: Any, key: str, default: Any = None) -> Any:
    try:
        value = record.get(key, default)
    except AttributeError:
        value = getattr(record, key, default)
    return default if value is None else value


def build_assertion_rows(
    records: Iterable[Any],
    config: Optional[DomainPackConfig],
) -> List[Dict[str, Any]]:
    """Convert Neo4j assertion records into normalized coverage rows."""
    rows: List[Dict[str, Any]] = []
    seen: set[str] = set()

    for record in records:
        assertion_id = _record_get(record, "assertion_id", "")
        if not assertion_id or assertion_id in seen:
            continue
        seen.add(assertion_id)

        context = _parse_context(_record_get(record, "context_conditions", {}))
        subject = _record_get(record, "subject", "")
        rows.append(
            {
                "assertion_id": assertion_id,
                "paper_id": _record_get(record, "paper_id", None),
                "metric": canonical_metric_from_subject(subject, config),
                "method": derive_method(context),
                "scenario": derive_scenario(context),
                "status": _record_get(record, "status", "pending"),
            }
        )
    return rows


def _taxonomy_values(config: Optional[DomainPackConfig], dimension_names: Sequence[str]) -> List[str]:
    if config is None:
        return []
    values: List[str] = []
    for dimension in config.domain.taxonomy_tree or []:
        name = getattr(dimension, "name", None)
        entries = getattr(dimension, "values", None)
        if name in dimension_names and entries:
            values.extend(normalize_dimension_value(entry) for entry in entries)
    return values


def _dedupe(values: Iterable[str]) -> List[str]:
    return list(dict.fromkeys(value for value in values if value))


def collect_dimensions(
    config: Optional[DomainPackConfig],
    rows: List[Dict[str, Any]],
    *,
    metrics: Optional[Sequence[str]] = None,
    methods: Optional[Sequence[str]] = None,
    scenarios: Optional[Sequence[str]] = None,
) -> Dict[str, List[str]]:
    """Merge requested, declared (domain pack), and observed dimension values."""
    declared_metrics = [metric.name for metric in config.core_metrics] if config else []
    observed_metrics = [row["metric"] for row in rows if row["metric"]]
    requested_metrics = [
        canonical_metric_from_subject(value, config) for value in (metrics or [])
    ]

    return {
        "metrics": _dedupe(requested_metrics) or _dedupe(declared_metrics + observed_metrics),
        "methods": _dedupe(
            normalize_dimension_value(value) for value in (methods or [])
        )
        or _dedupe(
            _taxonomy_values(config, ("switching_mechanism", "method", "technology"))
            + [row["method"] for row in rows]
        ),
        "scenarios": _dedupe(
            normalize_dimension_value(value) for value in (scenarios or [])
        )
        or _dedupe(
            _taxonomy_values(config, ("topology", "application_domain", "scenario", "network_layer"))
            + [row["scenario"] for row in rows]
        ),
    }


def _empty_cell() -> Dict[str, Any]:
    return {"count": 0, "assertion_ids": [], "paper_ids": []}


def build_coverage_report(
    rows: List[Dict[str, Any]],
    *,
    metrics: Sequence[str],
    methods: Sequence[str],
    scenarios: Sequence[str],
    gap_limit: int = 20,
) -> Dict[str, Any]:
    """Build the coverage matrix and ranked gap candidates from normalized rows."""
    matrix: Dict[tuple[str, str], Dict[str, Dict[str, Any]]] = {
        (method, scenario): {metric: _empty_cell() for metric in metrics}
        for method in methods
        for scenario in scenarios
    }

    for row in rows:
        cell_group = matrix.get((row["method"], row["scenario"]))
        if cell_group is None or row["metric"] not in cell_group:
            continue
        cell = cell_group[row["metric"]]
        cell["count"] += 1
        cell["assertion_ids"].append(row["assertion_id"])
        if row["paper_id"]:
            cell["paper_ids"].append(row["paper_id"])

    covered_cells = 0
    metric_coverage = {metric: 0 for metric in metrics}
    method_coverage = {method: 0 for method in methods}
    scenario_coverage = {scenario: 0 for scenario in scenarios}

    for method in methods:
        for scenario in scenarios:
            for metric in metrics:
                if matrix[(method, scenario)][metric]["count"] > 0:
                    covered_cells += 1
                    metric_coverage[metric] += 1
                    method_coverage[method] += 1
                    scenario_coverage[scenario] += 1

    total_cells = len(metrics) * len(methods) * len(scenarios)
    report_matrix = [
        {
            "method": method,
            "scenario": scenario,
            "cells": matrix[(method, scenario)],
        }
        for method in methods
        for scenario in scenarios
    ]

    gaps = []
    for method in methods:
        if method == UNSPECIFIED:
            continue
        for scenario in scenarios:
            if scenario == UNSPECIFIED:
                continue
            for metric in metrics:
                if matrix[(method, scenario)][metric]["count"] > 0:
                    continue
                # All three signals count covered (method, scenario, metric) cells:
                # how many papers report this metric at all, and how active the
                # method and scenario are elsewhere. Subtracting one axis from
                # the other would mix dimensions and can go negative.
                metric_demand = metric_coverage[metric]
                method_activity = method_coverage[method]
                scenario_activity = scenario_coverage[scenario]
                gaps.append(
                    {
                        "method": method,
                        "scenario": scenario,
                        "metric": metric,
                        "metric_demand": metric_demand,
                        "method_activity": method_activity,
                        "scenario_activity": scenario_activity,
                        "score": round(
                            (metric_demand + 1) * (method_activity + scenario_activity + 1),
                            3,
                        ),
                    }
                )

    gaps.sort(key=lambda gap: (-gap["score"], gap["method"], gap["scenario"], gap["metric"]))

    return {
        "metrics": list(metrics),
        "methods": list(methods),
        "scenarios": list(scenarios),
        "matrix": report_matrix,
        "coverage": {
            "covered_cells": covered_cells,
            "total_cells": total_cells,
            "ratio": round(covered_cells / total_cells, 4) if total_cells else 0.0,
            "by_metric": {
                metric: {"covered_cells": count, "total_cells": len(methods) * len(scenarios)}
                for metric, count in metric_coverage.items()
            },
            "by_method": {
                method: {"covered_cells": count, "total_cells": len(scenarios) * len(metrics)}
                for method, count in method_coverage.items()
            },
            "by_scenario": {
                scenario: {"covered_cells": count, "total_cells": len(methods) * len(metrics)}
                for scenario, count in scenario_coverage.items()
            },
        },
        "gaps": gaps[: max(0, gap_limit)],
        "gap_count": len(gaps),
    }


def analyze_workspace_coverage(
    db: Any,
    workspace_id: str,
    domain_pack_namespace: Optional[str] = None,
    *,
    metrics: Optional[Sequence[str]] = None,
    methods: Optional[Sequence[str]] = None,
    scenarios: Optional[Sequence[str]] = None,
    gap_limit: int = 20,
) -> Dict[str, Any]:
    """Query workspace assertions and build the coverage/gap report."""
    conditions = ["a.workspace_id = $workspace_id"]
    params: Dict[str, Any] = {"workspace_id": workspace_id}
    if domain_pack_namespace:
        conditions.append("a.domain_pack_namespace = $namespace")
        params["namespace"] = domain_pack_namespace

    query = f"""
    MATCH (a:AssertionNode)
    WHERE {' AND '.join(conditions)}
    OPTIONAL MATCH (p:PaperNode)-[:CONTAINS]->(a)
    RETURN a.id AS assertion_id,
           a.subject AS subject,
           a.status AS status,
           a.context_conditions AS context_conditions,
           p.id AS paper_id
    """

    records = list(db.execute_query(query, params))
    config = load_domain_pack_config(domain_pack_namespace) if domain_pack_namespace else None
    rows = build_assertion_rows(records, config)
    dimensions = collect_dimensions(
        config,
        rows,
        metrics=metrics,
        methods=methods,
        scenarios=scenarios,
    )

    return build_coverage_report(
        rows,
        metrics=dimensions["metrics"],
        methods=dimensions["methods"],
        scenarios=dimensions["scenarios"],
        gap_limit=gap_limit,
    )
