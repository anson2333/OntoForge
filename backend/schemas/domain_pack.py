"""
Domain Pack Configuration Schema
Pydantic model for external domain-pack.yaml as per Section 2.1.1 of the specification.
"""

from typing import List, Literal, Union, Optional
import math
from pydantic import BaseModel, ConfigDict, Field, model_validator


class TaxonomyDimension(BaseModel):
    """A single dimension of the taxonomy with subdomain mappings."""
    name: str = Field(..., description="Dimension name (e.g., 'topology', 'switching_mechanism')")
    values: List[str] = Field(..., description="Possible values for this dimension")
    subdomain_map: dict[str, str] = Field(default_factory=dict, description="Maps values to subdomain IDs")
    description: str = Field(default="", description="Human-readable description of this dimension")


class DomainInfo(BaseModel):
    """Domain identification and taxonomy with subdomain support."""
    id: str = Field(..., description="Unique domain identifier (e.g., domain.networking.optical)")
    name: str = Field(..., description="Human-readable domain name")
    taxonomy_tree: Union[List[str], List[TaxonomyDimension]] = Field(..., description="Hierarchical classification categories or structured dimensions")
    parent_domain_id: Optional[str] = Field(default=None, description="Parent domain ID for subdomains")


class MetricDefinition(BaseModel):
    """Core metric definition with aliases and normalization rules."""
    name: str = Field(..., description="Primary metric name")
    expected_unit: str = Field(..., description="Standard unit for this metric")
    aliases: List[str] = Field(default_factory=list, description="Alternative names for this metric")
    value_type: Literal["float", "int", "string", "bool"] = Field(default="float", description="Data type")
    description: str = ""
    minimum: Optional[float] = Field(default=None, allow_inf_nan=False)
    maximum: Optional[float] = Field(default=None, allow_inf_nan=False)
    unit_conversions: dict[str, float] = Field(default_factory=dict, description="Canonical source unit to multiplicative factor for expected_unit")

    @model_validator(mode='after')
    def valid_numeric_policy(self):
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError('Metric minimum exceeds maximum')
        if any(not math.isfinite(factor) or factor <= 0 for factor in self.unit_conversions.values()):
            raise ValueError('Unit conversion factors must be finite and positive')
        return self


class ValidationRules(BaseModel):
    """Validation constraints for extracted data."""
    required_context_keys: List[str] = Field(..., description="Mandatory context variables for assertions")
    unit_normalization: dict[str, List[str]] = Field(..., description="Unit synonyms mapping")
    extraction_instructions: List[str] = Field(default_factory=list)
    require_numeric_evidence: bool = False
    mark_missing_context: bool = False
    require_condition_evidence: bool = False
    document_families: dict[str, List[str]] = Field(default_factory=dict)
    excluded_result_roles: List[str] = Field(default_factory=list)
    excluded_result_terms: List[str] = Field(default_factory=list)
    max_batch_characters: Optional[int] = Field(default=None, ge=1000)


class CanonicalEntityDefinition(BaseModel):
    """A workspace-local canonical entity declared by a domain pack."""

    id: str = Field(..., pattern=r"^[a-z0-9][a-z0-9_.-]*$")
    entity_type: Literal[
        "Model", "ModelVariant", "Component", "Backbone", "Dataset", "DatasetSplit", "Metric"
    ]
    name: str
    aliases: List[str] = Field(default_factory=list)
    parent_id: Optional[str] = None
    role: Optional[str] = None
    members: List[str] = Field(default_factory=list)


class OntologyRelationRule(BaseModel):
    """Domain-pack extension of the fixed ontology relation whitelist."""

    relation_type: Literal[
        "HAS_VARIANT", "HAS_COMPONENT", "USES_BACKBONE", "HAS_SPLIT", "HAS_MEMBER"
    ]
    source_type: str
    target_type: str


class OntologyConfig(BaseModel):
    """Deterministic entity-resolution vocabulary and its version."""

    rule_version: str = "1.0"
    entities: List[CanonicalEntityDefinition] = Field(default_factory=list)
    relation_rules: List[OntologyRelationRule] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_entities(self):
        ids = [entity.id for entity in self.entities]
        if len(ids) != len(set(ids)):
            raise ValueError("Ontology entity ids must be unique")
        typed_terms: dict[tuple[str, str], str] = {}
        for entity in self.entities:
            for term in [entity.name, *entity.aliases]:
                semantic_term = term.casefold().replace("++", " plus_plus ").replace("+", " plus ")
                key = (entity.entity_type, "".join(ch for ch in semantic_term if ch.isalnum()))
                if key in typed_terms and typed_terms[key] != entity.id:
                    raise ValueError(
                        f"Ontology aliases must be unique within a type: {entity.entity_type}/{term}"
                    )
                typed_terms[key] = entity.id
        return self


class DomainPackConfig(BaseModel):
    """
    Root configuration for a domain pack.
    Loaded from domain-pack.yaml to define ontology, metrics, and validation rules.
    """
    schema_version: str = Field(..., description="Config schema version (e.g., '1.0')")
    domain: DomainInfo = Field(..., description="Domain metadata and taxonomy")
    core_metrics: List[MetricDefinition] = Field(..., description="Valid metrics for this domain")
    validation: ValidationRules = Field(..., description="Validation and normalization rules")
    ontology: OntologyConfig = Field(
        default_factory=OntologyConfig,
        description="Typed canonical entities used by deterministic resolution",
    )

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "schema_version": "1.0",
            "domain": {
                "id": "domain.networking.optical",
                "name": "Optical Access Networks",
                "parent_domain_id": None,
                "taxonomy_tree": [
                    {
                        "name": "topology",
                        "values": ["mesh", "ring", "star", "free_space"],
                        "subdomain_map": {
                            "free_space": "domain.networking.optical.fso",
                            "mesh": "domain.networking.optical.access"
                        },
                        "description": "Network topology types"
                    },
                    {
                        "name": "switching_mechanism",
                        "values": ["wdm", "optical_packet", "burst_switching", "circuit_switching"],
                        "subdomain_map": {
                            "wdm": "domain.networking.optical.wdm",
                            "optical_packet": "domain.networking.optical.ops"
                        },
                        "description": "Switching technologies"
                    }
                ]
            },
            "core_metrics": [
                {
                    "name": "reconfiguration_delay",
                    "expected_unit": "ms",
                    "aliases": ["switching_delay", "matrix_latency"],
                    "value_type": "float"
                },
                {
                    "name": "cross_talk",
                    "expected_unit": "dB",
                    "aliases": ["crosstalk"],
                    "value_type": "float"
                }
            ],
            "validation": {
                "required_context_keys": ["network_load", "topology"],
                "unit_normalization": {
                    "ms": ["ms", "millisecond", "milliseconds"],
                    "dB": ["dB", "db"]
                }
            }
        }
    })
