"""Entity normalization helpers shared by extraction and coverage analysis.

Metric aliases and unit synonyms are declared in the domain pack. Both the LLM
extractor and the coverage report must map free-form terms back to the single
canonical entity so the graph does not fragment into duplicate metrics.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from backend.schemas.domain_pack import DomainPackConfig


def _term_key(value: str) -> str:
    return re.sub(r"\s+", "_", (value or "").strip().lower())


def build_metric_alias_map(config: DomainPackConfig) -> dict[str, str]:
    """Map every metric name/alias (case-insensitive) to its canonical name."""
    aliases: dict[str, str] = {}
    for metric in config.core_metrics:
        aliases[_term_key(metric.name)] = metric.name
        for alias in metric.aliases:
            aliases[_term_key(alias)] = metric.name
    return aliases


def resolve_metric_name(name: str, config: Optional[DomainPackConfig]) -> Optional[str]:
    """Resolve a metric name or alias to the canonical name, or None if unknown."""
    if config is None:
        return None
    return build_metric_alias_map(config).get(_term_key(name))


def build_unit_alias_map(config: DomainPackConfig) -> dict[str, str]:
    """Map every unit synonym (case-insensitive) to its canonical unit."""
    aliases: dict[str, str] = {}
    for canonical, variants in config.validation.unit_normalization.items():
        aliases[canonical.lower()] = canonical
        for variant in variants:
            aliases[(variant or "").lower()] = canonical
    return aliases


def normalize_unit(unit: str, config: Optional[DomainPackConfig], fallback: str = "") -> str:
    """Resolve a unit synonym to its canonical form."""
    if config is None:
        return unit or fallback
    alias_map = build_unit_alias_map(config)
    normalized = alias_map.get((unit or "").strip().lower())
    return normalized or fallback or unit


def canonical_metric_from_subject(subject: str, config: Optional[DomainPackConfig]) -> str:
    """Strip an optional namespace prefix and canonicalize the metric term."""
    term = (subject or "").strip()
    if ":" in term:
        term = term.rsplit(":", 1)[-1]
    return resolve_metric_name(term, config) or term


def normalize_dimension_value(value: Any) -> str:
    """Normalize a context value (method/scenario) into a stable snake_case key."""
    if value is None:
        return "unspecified"
    text = str(value).strip().lower()
    if not text:
        return "unspecified"
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_") or "unspecified"
