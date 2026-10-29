"""
Tests for Domain Pack Validator
"""

import pytest

from backend.schemas.domain_pack import (
    DomainPackConfig,
    DomainInfo,
    MetricDefinition,
    ValidationRules,
)
from backend.config.validator import DomainPackValidator, ValidationError


class TestDomainPackValidator:
    """Tests for DomainPackValidator."""

    def test_validate_valid_config(self):
        """Test validation succeeds for valid config."""
        config = DomainPackConfig(
            schema_version="1.0",
            domain=DomainInfo(
                id="domain.test",
                name="Test Domain",
                taxonomy_tree=["category_1"],
            ),
            core_metrics=[
                MetricDefinition(
                    name="metric_1",
                    expected_unit="ms",
                    aliases=["alias_1"],
                    value_type="float",
                ),
            ],
            validation=ValidationRules(
                required_context_keys=["key_1"],
                unit_normalization={"ms": ["ms", "millisecond"]},
            ),
        )

        is_valid, errors = DomainPackValidator.validate(config)
        assert is_valid
        assert len(errors) == 0

    def test_validate_missing_domain_prefix(self):
        """Test validation fails if domain ID doesn't start with 'domain.'"""
        config = DomainPackConfig(
            schema_version="1.0",
            domain=DomainInfo(
                id="invalid_id",  # Should start with "domain."
                name="Test Domain",
                taxonomy_tree=["category_1"],
            ),
            core_metrics=[
                MetricDefinition(
                    name="metric_1",
                    expected_unit="ms",
                    aliases=[],
                    value_type="float",
                ),
            ],
            validation=ValidationRules(
                required_context_keys=["key_1"],
                unit_normalization={"ms": ["ms"]},
            ),
        )

        is_valid, errors = DomainPackValidator.validate(config)
        assert not is_valid
        assert any("must start with 'domain.'" in err for err in errors)

    def test_validate_no_metrics(self):
        """Test validation fails if no core metrics defined."""
        config = DomainPackConfig(
            schema_version="1.0",
            domain=DomainInfo(
                id="domain.test",
                name="Test Domain",
                taxonomy_tree=["category_1"],
            ),
            core_metrics=[],  # Empty metrics
            validation=ValidationRules(
                required_context_keys=["key_1"],
                unit_normalization={},
            ),
        )

        is_valid, errors = DomainPackValidator.validate(config)
        assert not is_valid
        assert any("At least one core metric" in err for err in errors)

    def test_validate_duplicate_metric_names(self):
        """Test validation fails for duplicate metric names."""
        config = DomainPackConfig(
            schema_version="1.0",
            domain=DomainInfo(
                id="domain.test",
                name="Test Domain",
                taxonomy_tree=["category_1"],
            ),
            core_metrics=[
                MetricDefinition(
                    name="metric_1",
                    expected_unit="ms",
                    aliases=[],
                    value_type="float",
                ),
                MetricDefinition(
                    name="metric_1",  # Duplicate
                    expected_unit="s",
                    aliases=[],
                    value_type="float",
                ),
            ],
            validation=ValidationRules(
                required_context_keys=["key_1"],
                unit_normalization={"ms": ["ms"], "s": ["s"]},
            ),
        )

        is_valid, errors = DomainPackValidator.validate(config)
        assert not is_valid
        assert any("Duplicate metric names" in err for err in errors)

    def test_validate_alias_conflicts_with_metric_name(self):
        """Test validation fails if alias conflicts with metric name."""
        config = DomainPackConfig(
            schema_version="1.0",
            domain=DomainInfo(
                id="domain.test",
                name="Test Domain",
                taxonomy_tree=["category_1"],
            ),
            core_metrics=[
                MetricDefinition(
                    name="metric_1",
                    expected_unit="ms",
                    aliases=["metric_2"],  # Alias conflicts with metric_2
                    value_type="float",
                ),
                MetricDefinition(
                    name="metric_2",
                    expected_unit="s",
                    aliases=[],
                    value_type="float",
                ),
            ],
            validation=ValidationRules(
                required_context_keys=["key_1"],
                unit_normalization={"ms": ["ms"], "s": ["s"]},
            ),
        )

        is_valid, errors = DomainPackValidator.validate(config)
        assert not is_valid
        assert any("Aliases conflict with metric names" in err for err in errors)

    def test_validate_duplicate_aliases(self):
        """Test validation fails for duplicate aliases across metrics."""
        config = DomainPackConfig(
            schema_version="1.0",
            domain=DomainInfo(
                id="domain.test",
                name="Test Domain",
                taxonomy_tree=["category_1"],
            ),
            core_metrics=[
                MetricDefinition(
                    name="metric_1",
                    expected_unit="ms",
                    aliases=["common_alias"],
                    value_type="float",
                ),
                MetricDefinition(
                    name="metric_2",
                    expected_unit="s",
                    aliases=["common_alias"],  # Duplicate
                    value_type="float",
                ),
            ],
            validation=ValidationRules(
                required_context_keys=["key_1"],
                unit_normalization={"ms": ["ms"], "s": ["s"]},
            ),
        )

        is_valid, errors = DomainPackValidator.validate(config)
        assert not is_valid
        assert any("Duplicate aliases" in err for err in errors)

    def test_validate_missing_unit_normalization(self):
        """Test validation fails if expected units not in unit_normalization."""
        config = DomainPackConfig(
            schema_version="1.0",
            domain=DomainInfo(
                id="domain.test",
                name="Test Domain",
                taxonomy_tree=["category_1"],
            ),
            core_metrics=[
                MetricDefinition(
                    name="metric_1",
                    expected_unit="ms",
                    aliases=[],
                    value_type="float",
                ),
            ],
            validation=ValidationRules(
                required_context_keys=["key_1"],
                unit_normalization={},  # Missing "ms"
            ),
        )

        is_valid, errors = DomainPackValidator.validate(config)
        assert not is_valid
        assert any("Expected units missing from unit_normalization" in err for err in errors)

    def test_validate_empty_taxonomy_tree(self):
        """Test validation fails for empty taxonomy tree."""
        config = DomainPackConfig(
            schema_version="1.0",
            domain=DomainInfo(
                id="domain.test",
                name="Test Domain",
                taxonomy_tree=[],  # Empty
            ),
            core_metrics=[
                MetricDefinition(
                    name="metric_1",
                    expected_unit="ms",
                    aliases=[],
                    value_type="float",
                ),
            ],
            validation=ValidationRules(
                required_context_keys=["key_1"],
                unit_normalization={"ms": ["ms"]},
            ),
        )

        is_valid, errors = DomainPackValidator.validate(config)
        assert not is_valid
        assert any("Taxonomy tree cannot be empty" in err for err in errors)

    def test_validate_or_raise_success(self):
        """Test validate_or_raise doesn't raise for valid config."""
        config = DomainPackConfig(
            schema_version="1.0",
            domain=DomainInfo(
                id="domain.test",
                name="Test Domain",
                taxonomy_tree=["category_1"],
            ),
            core_metrics=[
                MetricDefinition(
                    name="metric_1",
                    expected_unit="ms",
                    aliases=[],
                    value_type="float",
                ),
            ],
            validation=ValidationRules(
                required_context_keys=["key_1"],
                unit_normalization={"ms": ["ms"]},
            ),
        )

        # Should not raise
        DomainPackValidator.validate_or_raise(config)

    def test_validate_or_raise_failure(self):
        """Test validate_or_raise raises ValidationError for invalid config."""
        config = DomainPackConfig(
            schema_version="1.0",
            domain=DomainInfo(
                id="invalid_id",  # Missing "domain." prefix
                name="Test Domain",
                taxonomy_tree=["category_1"],
            ),
            core_metrics=[
                MetricDefinition(
                    name="metric_1",
                    expected_unit="ms",
                    aliases=[],
                    value_type="float",
                ),
            ],
            validation=ValidationRules(
                required_context_keys=["key_1"],
                unit_normalization={"ms": ["ms"]},
            ),
        )

        with pytest.raises(ValidationError, match="Domain pack validation failed"):
            DomainPackValidator.validate_or_raise(config)
