"""
Domain Pack Validator
Validates domain pack configuration against business rules and constraints.
"""

from typing import List, Tuple

from backend.schemas.domain_pack import DomainPackConfig


class ValidationError(Exception):
    """Raised when domain pack validation fails."""
    pass


class DomainPackValidator:
    """
    Validates domain pack configuration for consistency and completeness.
    Checks business rules beyond basic Pydantic schema validation.
    """

    @staticmethod
    def validate(config: DomainPackConfig) -> Tuple[bool, List[str]]:
        """
        Validate domain pack configuration.

        Args:
            config: DomainPackConfig instance

        Returns:
            (is_valid, list of error messages)
        """
        errors = []

        # Check 1: Domain ID follows naming convention
        if not config.domain.id.startswith("domain."):
            errors.append(
                f"Domain ID must start with 'domain.' prefix. Got: {config.domain.id}"
            )

        # Check 2: At least one core metric defined
        if not config.core_metrics:
            errors.append("At least one core metric must be defined")

        # Check 3: Metric names are unique
        metric_names = [m.name for m in config.core_metrics]
        if len(metric_names) != len(set(metric_names)):
            duplicates = [name for name in metric_names if metric_names.count(name) > 1]
            errors.append(f"Duplicate metric names found: {set(duplicates)}")

        # Check 4: Aliases don't conflict with metric names
        all_aliases = []
        for metric in config.core_metrics:
            all_aliases.extend(metric.aliases)

        conflicting_aliases = set(metric_names) & set(all_aliases)
        if conflicting_aliases:
            errors.append(
                f"Aliases conflict with metric names: {conflicting_aliases}"
            )

        # Check 5: Aliases are unique across metrics
        if len(all_aliases) != len(set(all_aliases)):
            duplicates = [a for a in all_aliases if all_aliases.count(a) > 1]
            errors.append(f"Duplicate aliases found: {set(duplicates)}")

        # Check 6: Unit normalization covers expected units
        expected_units = {m.expected_unit for m in config.core_metrics}
        normalized_units = set(config.validation.unit_normalization.keys())

        missing_units = expected_units - normalized_units
        if missing_units:
            errors.append(
                f"Expected units missing from unit_normalization: {missing_units}"
            )

        # Check 7: Unit normalization has no empty synonym lists
        for unit, synonyms in config.validation.unit_normalization.items():
            if not synonyms:
                errors.append(f"Unit '{unit}' has no synonyms defined")

        # Check 8: Taxonomy tree is not empty
        if not config.domain.taxonomy_tree:
            errors.append("Taxonomy tree cannot be empty")

        # Check 9: Required context keys are not empty
        if not config.validation.required_context_keys:
            errors.append("Required context keys cannot be empty")

        # Check 10: Expected units are not empty strings
        for metric in config.core_metrics:
            if not metric.expected_unit or not metric.expected_unit.strip():
                errors.append(f"Metric '{metric.name}' has empty expected_unit")

        return len(errors) == 0, errors

    @staticmethod
    def validate_or_raise(config: DomainPackConfig) -> None:
        """
        Validate domain pack configuration and raise on failure.

        Args:
            config: DomainPackConfig instance

        Raises:
            ValidationError: If validation fails
        """
        is_valid, errors = DomainPackValidator.validate(config)
        if not is_valid:
            error_msg = "Domain pack validation failed:\n" + "\n".join(
                f"  - {err}" for err in errors
            )
            raise ValidationError(error_msg)
