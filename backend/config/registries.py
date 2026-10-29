"""
Domain Pack Registries
In-memory registries for fast lookup of metrics, aliases, and unit normalizations.
"""

from typing import List, Optional

from backend.schemas.domain_pack import DomainPackConfig, MetricDefinition


class MetricRegistry:
    """
    Fast lookup for valid metrics in the domain.
    Built from DomainPackConfig.core_metrics.
    """

    def __init__(self):
        self._metrics: dict[str, MetricDefinition] = {}

    def build_from_config(self, config: DomainPackConfig) -> None:
        """Populate registry from domain pack config."""
        self._metrics.clear()
        for metric in config.core_metrics:
            self._metrics[metric.name] = metric

    def get(self, metric_name: str) -> Optional[MetricDefinition]:
        """Retrieve metric definition by name."""
        return self._metrics.get(metric_name)

    def exists(self, metric_name: str) -> bool:
        """Check if metric exists in registry."""
        return metric_name in self._metrics

    def list_all(self) -> List[str]:
        """Get list of all registered metric names."""
        return list(self._metrics.keys())

    def get_expected_unit(self, metric_name: str) -> Optional[str]:
        """Get expected unit for a metric."""
        metric = self.get(metric_name)
        return metric.expected_unit if metric else None


class AliasRegistry:
    """
    Bidirectional mapping between metric aliases and canonical names.
    Built from MetricDefinition.aliases.
    """

    def __init__(self):
        self._alias_to_canonical: dict[str, str] = {}

    def build_from_config(self, config: DomainPackConfig) -> None:
        """Populate registry from domain pack config."""
        self._alias_to_canonical.clear()
        for metric in config.core_metrics:
            # Canonical name maps to itself
            self._alias_to_canonical[metric.name] = metric.name
            # Aliases map to canonical name
            for alias in metric.aliases:
                self._alias_to_canonical[alias] = metric.name

    def resolve(self, alias: str) -> Optional[str]:
        """
        Resolve an alias to its canonical metric name.

        Args:
            alias: Metric name or alias

        Returns:
            Canonical metric name, or None if not found
        """
        return self._alias_to_canonical.get(alias)

    def is_valid_alias(self, alias: str) -> bool:
        """Check if an alias is registered."""
        return alias in self._alias_to_canonical


class UnitRegistry:
    """
    Unit normalization registry mapping unit synonyms to standard units.
    Built from ValidationRules.unit_normalization.
    """

    def __init__(self):
        self._synonym_to_standard: dict[str, str] = {}

    def build_from_config(self, config: DomainPackConfig) -> None:
        """Populate registry from domain pack config."""
        self._synonym_to_standard.clear()
        for standard_unit, synonyms in config.validation.unit_normalization.items():
            for synonym in synonyms:
                self._synonym_to_standard[synonym.lower()] = standard_unit

    def normalize(self, unit: str) -> str:
        """
        Normalize a unit string to its standard form.

        Args:
            unit: Raw unit string (e.g., "millisecond", "ms")

        Returns:
            Normalized unit (e.g., "ms")
        """
        return self._synonym_to_standard.get(unit.lower(), unit)

    def is_valid_unit(self, unit: str, expected_unit: str) -> bool:
        """
        Check if a unit matches the expected unit after normalization.

        Args:
            unit: Raw unit string
            expected_unit: Expected standard unit

        Returns:
            True if normalized unit matches expected unit
        """
        return self.normalize(unit) == expected_unit


class RegistryManager:
    """
    Manages all registries as a cohesive unit.
    Provides convenient access to metrics, aliases, and units.
    """

    def __init__(self):
        self.metrics = MetricRegistry()
        self.aliases = AliasRegistry()
        self.units = UnitRegistry()

    def build_from_config(self, config: DomainPackConfig) -> None:
        """Build all registries from domain pack config."""
        self.metrics.build_from_config(config)
        self.aliases.build_from_config(config)
        self.units.build_from_config(config)

    def validate_metric_with_unit(self, metric_name: str, unit: str) -> tuple[bool, Optional[str]]:
        """
        Validate that a metric exists and has the correct unit.

        Args:
            metric_name: Metric name or alias
            unit: Unit string

        Returns:
            (is_valid, error_message)
        """
        # Resolve alias to canonical name
        canonical_name = self.aliases.resolve(metric_name)
        if not canonical_name:
            return False, f"Unknown metric: {metric_name}"

        # Get expected unit
        expected_unit = self.metrics.get_expected_unit(canonical_name)
        if not expected_unit:
            return False, f"Metric {canonical_name} has no expected unit defined"

        # Normalize and compare
        if not self.units.is_valid_unit(unit, expected_unit):
            normalized = self.units.normalize(unit)
            return False, f"Unit mismatch for {canonical_name}: got '{unit}' (normalized: '{normalized}'), expected '{expected_unit}'"

        return True, None
