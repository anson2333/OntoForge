"""
Tests for Domain Pack Registries
"""

import pytest

from backend.schemas.domain_pack import (
    DomainPackConfig,
    DomainInfo,
    MetricDefinition,
    ValidationRules,
)
from backend.config.registries import (
    MetricRegistry,
    AliasRegistry,
    UnitRegistry,
    RegistryManager,
)


@pytest.fixture
def sample_config():
    """Sample domain pack configuration for testing."""
    return DomainPackConfig(
        schema_version="1.0",
        domain=DomainInfo(
            id="domain.test",
            name="Test Domain",
            taxonomy_tree=["category_1", "category_2"],
        ),
        core_metrics=[
            MetricDefinition(
                name="latency",
                expected_unit="ms",
                aliases=["delay", "lag"],
                value_type="float",
            ),
            MetricDefinition(
                name="throughput",
                expected_unit="Gbps",
                aliases=["bandwidth"],
                value_type="float",
            ),
        ],
        validation=ValidationRules(
            required_context_keys=["load", "topology"],
            unit_normalization={
                "ms": ["ms", "millisecond", "milliseconds"],
                "Gbps": ["Gbps", "gbps", "Gigabit/s"],
            },
        ),
    )


class TestMetricRegistry:
    """Tests for MetricRegistry."""

    def test_build_from_config(self, sample_config):
        """Test building metric registry from config."""
        registry = MetricRegistry()
        registry.build_from_config(sample_config)

        assert registry.exists("latency")
        assert registry.exists("throughput")
        assert not registry.exists("nonexistent")

    def test_get_metric(self, sample_config):
        """Test retrieving metric definition."""
        registry = MetricRegistry()
        registry.build_from_config(sample_config)

        metric = registry.get("latency")
        assert metric is not None
        assert metric.name == "latency"
        assert metric.expected_unit == "ms"

    def test_get_expected_unit(self, sample_config):
        """Test retrieving expected unit for metric."""
        registry = MetricRegistry()
        registry.build_from_config(sample_config)

        assert registry.get_expected_unit("latency") == "ms"
        assert registry.get_expected_unit("throughput") == "Gbps"
        assert registry.get_expected_unit("nonexistent") is None

    def test_list_all_metrics(self, sample_config):
        """Test listing all registered metrics."""
        registry = MetricRegistry()
        registry.build_from_config(sample_config)

        metrics = registry.list_all()
        assert "latency" in metrics
        assert "throughput" in metrics
        assert len(metrics) == 2


class TestAliasRegistry:
    """Tests for AliasRegistry."""

    def test_build_from_config(self, sample_config):
        """Test building alias registry from config."""
        registry = AliasRegistry()
        registry.build_from_config(sample_config)

        # Canonical names should map to themselves
        assert registry.resolve("latency") == "latency"
        assert registry.resolve("throughput") == "throughput"

        # Aliases should map to canonical names
        assert registry.resolve("delay") == "latency"
        assert registry.resolve("lag") == "latency"
        assert registry.resolve("bandwidth") == "throughput"

    def test_resolve_unknown_alias(self, sample_config):
        """Test resolving unknown alias returns None."""
        registry = AliasRegistry()
        registry.build_from_config(sample_config)

        assert registry.resolve("unknown") is None

    def test_is_valid_alias(self, sample_config):
        """Test checking if alias is valid."""
        registry = AliasRegistry()
        registry.build_from_config(sample_config)

        assert registry.is_valid_alias("latency")
        assert registry.is_valid_alias("delay")
        assert not registry.is_valid_alias("unknown")


class TestUnitRegistry:
    """Tests for UnitRegistry."""

    def test_build_from_config(self, sample_config):
        """Test building unit registry from config."""
        registry = UnitRegistry()
        registry.build_from_config(sample_config)

        assert registry.normalize("ms") == "ms"
        assert registry.normalize("millisecond") == "ms"
        assert registry.normalize("MILLISECONDS") == "ms"  # Case insensitive

    def test_normalize_unknown_unit(self, sample_config):
        """Test normalizing unknown unit returns original."""
        registry = UnitRegistry()
        registry.build_from_config(sample_config)

        assert registry.normalize("unknown_unit") == "unknown_unit"

    def test_is_valid_unit(self, sample_config):
        """Test checking if unit matches expected unit."""
        registry = UnitRegistry()
        registry.build_from_config(sample_config)

        assert registry.is_valid_unit("ms", "ms")
        assert registry.is_valid_unit("millisecond", "ms")
        assert not registry.is_valid_unit("seconds", "ms")


class TestRegistryManager:
    """Tests for RegistryManager."""

    def test_build_all_registries(self, sample_config):
        """Test building all registries at once."""
        manager = RegistryManager()
        manager.build_from_config(sample_config)

        assert manager.metrics.exists("latency")
        assert manager.aliases.resolve("delay") == "latency"
        assert manager.units.normalize("millisecond") == "ms"

    def test_validate_metric_with_unit_success(self, sample_config):
        """Test successful metric and unit validation."""
        manager = RegistryManager()
        manager.build_from_config(sample_config)

        is_valid, error = manager.validate_metric_with_unit("latency", "ms")
        assert is_valid
        assert error is None

        # Test with alias and synonym
        is_valid, error = manager.validate_metric_with_unit("delay", "millisecond")
        assert is_valid
        assert error is None

    def test_validate_unknown_metric(self, sample_config):
        """Test validation fails for unknown metric."""
        manager = RegistryManager()
        manager.build_from_config(sample_config)

        is_valid, error = manager.validate_metric_with_unit("unknown", "ms")
        assert not is_valid
        assert "Unknown metric" in error

    def test_validate_wrong_unit(self, sample_config):
        """Test validation fails for wrong unit."""
        manager = RegistryManager()
        manager.build_from_config(sample_config)

        is_valid, error = manager.validate_metric_with_unit("latency", "seconds")
        assert not is_valid
        assert "Unit mismatch" in error
