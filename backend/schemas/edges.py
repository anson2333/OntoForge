"""
Edge Schema Definitions
Pydantic models for all graph relationship types as per Section 3.2 of the specification.
"""

from pydantic import BaseModel, ConfigDict, Field
from typing import Literal, Optional


class ContainsDomainPackEdge(BaseModel):
    """
    (:WorkspaceNode)-[:CONTAINS_DOMAIN_PACK]->(:DomainNode)
    Links workspace to loaded domain packs (Section 2.0).
    """
    from_node_id: str = Field(..., description="Source WorkspaceNode ID")
    to_node_id: str = Field(..., description="Target DomainNode ID")


class ContainsPaperEdge(BaseModel):
    """
    (:WorkspaceNode)-[:CONTAINS_PAPER]->(:PaperNode)
    Papers belong to workspace, can reference multiple domain packs (Section 2.0).
    """
    from_node_id: str = Field(..., description="Source WorkspaceNode ID")
    to_node_id: str = Field(..., description="Target PaperNode ID")


class HasBranchEdge(BaseModel):
    """
    (:DomainNode)-[:HAS_BRANCH]->(:DomainNode)
    Represents hierarchical relationships between domains.
    """
    from_node_id: str = Field(..., description="Source DomainNode ID")
    to_node_id: str = Field(..., description="Target DomainNode ID")


class BelongsToEdge(BaseModel):
    """
    (:PaperNode)-[:BELONGS_TO]->(:DomainNode)
    Links a paper to its research domain or subdomain.
    Supports multi-subdomain classification with confidence scores.
    """
    from_node_id: str = Field(..., description="Source PaperNode ID")
    to_node_id: str = Field(..., description="Target DomainNode ID")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="AI classification confidence score")
    primary: bool = Field(default=True, description="Whether this is the primary subdomain assignment")
    classification_method: str = Field(default="manual", description="Classification method: manual|llm|embedding|rule_based")


class CitesEdge(BaseModel):
    """
    (:PaperNode)-[:CITES]->(:PaperNode)
    Represents citation relationships between papers.
    """
    from_node_id: str = Field(..., description="Citing PaperNode ID")
    to_node_id: str = Field(..., description="Cited PaperNode ID")


class ContainsEdge(BaseModel):
    """
    (:PaperNode)-[:CONTAINS]->(:ChunkNode|:FormulaNode)
    Links a paper to its extracted content elements.
    """
    from_node_id: str = Field(..., description="Source PaperNode ID")
    to_node_id: str = Field(..., description="Target ChunkNode or FormulaNode ID")
    extraction_method: Optional[str] = Field(None, description="Method used for extraction (e.g., 'Marker', 'Nougat')")


class EvidencedByEdge(BaseModel):
    """
    (:ChunkNode|:FormulaNode)-[:EVIDENCED_BY]->(:AssertionNode)
    Links evidence to the assertions it supports, with AI confidence score.
    Edge property confidence_score represents AI's confidence that this specific evidence supports the assertion (0.0-1.0).
    """
    from_node_id: str = Field(..., description="Source ChunkNode or FormulaNode ID")
    to_node_id: str = Field(..., description="Target AssertionNode ID")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="AI extraction confidence (range 0.0-1.0)")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "from_node_id": "chunk_p4_c2",
            "to_node_id": "assert_001",
            "confidence_score": 0.95
        }
    })


class ContradictsEdge(BaseModel):
    """
    (:AssertionNode)-[:CONTRADICTS]->(:AssertionNode)
    Bi-directional link populated dynamically by the background Audit Engine.
    Represents epistemic conflicts between assertions with identical contexts but different values.
    """
    from_node_id: str = Field(..., description="Source AssertionNode ID")
    to_node_id: str = Field(..., description="Target AssertionNode ID")
    conflict_id: str = Field(..., description="Unique identifier for this conflict")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "from_node_id": "assert_001",
            "to_node_id": "assert_104",
            "conflict_id": "conf_089"
        }
    })


class LocksEdge(BaseModel):
    """
    (:HumanArbitratorNode)-[:LOCKS]->(:AssertionNode)
    Represents a human decision that prevents automated updates to an assertion.
    """
    from_node_id: str = Field(..., description="Source HumanArbitratorNode ID")
    to_node_id: str = Field(..., description="Target AssertionNode ID (locked)")


class ApprovesEdge(BaseModel):
    """
    (:HumanArbitratorNode)-[:APPROVES]->(:DomainNode)
    Represents human approval of domain structure changes.
    """
    from_node_id: str = Field(..., description="Source HumanArbitratorNode ID")
    to_node_id: str = Field(..., description="Target DomainNode ID (approved)")
    approval_type: Literal["initial_approval", "taxonomy_change", "metric_addition"] = Field(
        ...,
        description="Type of approval action"
    )
    approved_version: str = Field(..., description="domain_pack_version that was approved")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "from_node_id": "arbitrator_alice_20260523_143022",
            "to_node_id": "domain.networking.optical",
            "approval_type": "taxonomy_change",
            "approved_version": "1.1"
        }
    })


class ScopesEdge(BaseModel):
    """
    (:IntentBranchNode)-[:SCOPES]->(:HumanArbitratorNode)
    Links intent decisions to research context branches (Section 2.6.5).
    """
    from_node_id: str = Field(..., description="Source IntentBranchNode ID")
    to_node_id: str = Field(..., description="Target HumanArbitratorNode ID")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "from_node_id": "intent_wdm_survey_2026",
            "to_node_id": "arbitrator_alice_20260524_103045"
        }
    })


class InheritsFromEdge(BaseModel):
    """
    (:IntentBranchNode)-[:INHERITS_FROM]->(:IntentBranchNode)
    Intent branch inheritance hierarchy (Section 2.6.5).
    """
    from_node_id: str = Field(..., description="Child IntentBranchNode ID")
    to_node_id: str = Field(..., description="Parent IntentBranchNode ID")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "from_node_id": "intent_wdm_survey_2026_v2",
            "to_node_id": "intent_wdm_survey_2026"
        }
    })


class MatchesPatternEdge(BaseModel):
    """
    (:HumanArbitratorNode)-[:MATCHES_PATTERN]->(:HumanArbitratorNode)
    Connects similar intent patterns for learning (Section 2.6.3).
    """
    from_node_id: str = Field(..., description="Source HumanArbitratorNode ID")
    to_node_id: str = Field(..., description="Target HumanArbitratorNode ID (similar pattern)")
    pattern_id: str = Field(..., description="Identified pattern ID, e.g., 'hardware_preference_asic_over_fpga'")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Similarity confidence score")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "from_node_id": "arbitrator_alice_20260523_143022",
            "to_node_id": "arbitrator_alice_20260520_091034",
            "pattern_id": "hardware_preference_asic_over_fpga",
            "confidence": 0.91
        }
    })
