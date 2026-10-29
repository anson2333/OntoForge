"""
Domain Pack Configuration Schema
Pydantic model for external domain-pack.yaml as per Section 2.1.1 of the specification.
"""

from typing import List, Literal, Union, Optional
from pydantic import BaseModel, ConfigDict, Field


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


class ValidationRules(BaseModel):
    """Validation constraints for extracted data."""
    required_context_keys: List[str] = Field(..., description="Mandatory context variables for assertions")
    unit_normalization: dict[str, List[str]] = Field(..., description="Unit synonyms mapping")


class DomainPackConfig(BaseModel):
    """
    Root configuration for a domain pack.
    Loaded from domain-pack.yaml to define ontology, metrics, and validation rules.
    """
    schema_version: str = Field(..., description="Config schema version (e.g., '1.0')")
    domain: DomainInfo = Field(..., description="Domain metadata and taxonomy")
    core_metrics: List[MetricDefinition] = Field(..., description="Valid metrics for this domain")
    validation: ValidationRules = Field(..., description="Validation and normalization rules")

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
