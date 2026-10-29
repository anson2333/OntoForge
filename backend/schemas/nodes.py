"""
Node Schema Definitions
Pydantic models for all graph node types as per Section 3.1 of the specification.
"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class WorkspaceNode(BaseModel):
    """
    Top-level organizational unit representing a bounded research project.
    Each workspace can contain multiple domain packs for interdisciplinary research.
    Section 2.0 of specification.
    """
    id: str = Field(..., description="Primary Key, e.g., workspace_5g_backhaul_2026")
    name: str = Field(..., description="Human-readable workspace name")
    description: Optional[str] = Field(None, description="Purpose of this workspace")
    root_path: str = Field(..., description="File system path to workspace directory")
    created_at: datetime = Field(..., description="When this workspace was created")
    last_modified_at: datetime = Field(..., description="Last modification timestamp")
    status: Literal["active", "archived", "readonly"] = Field(
        default="active",
        description="Current status of the workspace"
    )
    owner_id: Optional[str] = Field(
        default=None,
        description="Owning principal for authorization; may be null for legacy local workspaces"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional, custom workspace metadata"
    )

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "id": "workspace_5g_backhaul_2026",
            "name": "5G Backhaul Comparison Study",
            "description": "Comparing optical and wireless backhaul technologies for 5G networks",
            "root_path": "file:///Users/scholar/research/5g_backhaul_study",
            "created_at": "2026-05-24T00:00:00Z",
            "last_modified_at": "2026-05-24T12:30:00Z",
            "status": "active",
            "owner_id": "local-dev-user",
            "metadata": {
                "tags": ["5G", "backhaul", "comparison"],
                "collaborators": ["alice@research.org", "bob@research.org"]
            }
        }
    })


class DomainNode(BaseModel):
    """
    Tier 1: Macro Domain & Graph Topology
    Represents a research domain with its taxonomy and metric definitions.
    Enhanced with namespace for workspace isolation.
    """
    id: str = Field(..., description="Primary Key, e.g., domain.networking.optical")
    name: str = Field(..., description="Human-readable domain name")
    namespace: str = Field(..., description="Workspace-scoped namespace, e.g., 'optical', 'wireless'")
    domain_pack_id: str = Field(..., description="External config identifier")
    domain_pack_version: str = Field(..., description="Version from external config")
    taxonomy_tree: dict[str, Any] = Field(..., description="Hierarchical classification skeleton")
    core_metrics: List[str] = Field(..., description="Valid metrics with namespace prefix, e.g., ['optical:reconfiguration_delay']")
    parent_domain_id: Optional[str] = Field(None, description="Optional, for subdomain hierarchy")
    classification_hints: Optional[dict[str, Any]] = Field(None, description="Keywords for rule-based subdomain classification")
    approval_status: Literal["draft", "approved", "deprecated"] = Field(
        default="draft",
        description="Human approval of domain taxonomy structure"
    )

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "id": "domain.networking.optical",
            "name": "Optical Access Networks",
            "namespace": "optical",
            "domain_pack_id": "optical_networks_v1",
            "domain_pack_version": "1.0",
            "taxonomy_tree": {
                "topology": ["mesh", "ring", "star"],
                "switching_mechanism": ["optical", "electronic", "hybrid"]
            },
            "core_metrics": ["optical:reconfiguration_delay", "optical:cross_talk"],
            "parent_domain_id": None,
            "classification_hints": {
                "keywords": ["optical", "photonic", "switching"]
            }
        }
    })


class PaperNode(BaseModel):
    """
    Tier 4: Source document metadata
    Represents a scientific paper with bibliographic information.
    """
    id: str = Field(..., description="Primary Key, derived unique slug or DOI")
    doi: str = Field(..., description="Digital Object Identifier")
    title: str = Field(..., description="Paper title")
    authors: List[str] = Field(..., description="List of author names")
    year: int = Field(..., description="Publication year")
    venue: str = Field(..., description="Publication venue (conference or journal)")
    provenance_hash: str = Field(..., description="SHA-256 fingerprint of the source PDF")
    import_status: Literal["pending", "verified", "rejected"] = Field(
        default="pending",
        description="Human verification of source artifact integrity"
    )
    domain_pack_namespace: Optional[str] = Field(
        default=None,
        description="Optional domain pack namespace this paper belongs to (e.g., 'optical', 'wireless')"
    )
    workspace_id: str = Field(..., description="Workspace this paper belongs to for multi-user isolation")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "id": "paper_satellite_switching_2026",
            "doi": "10.1109/JLT.2026.123456",
            "title": "On-Board Optical Packet Switching for Mega-Constellations",
            "authors": ["Zhang, X.", "Li, Y."],
            "year": 2026,
            "venue": "OFC 2026",
            "provenance_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "domain_pack_namespace": "optical",
            "workspace_id": "workspace_5g_backhaul_2026"
        }
    })


class ChunkNode(BaseModel):
    """
    Tier 3: Physical Evidence & Symbols
    Represents a text chunk extracted from a paper with spatial coordinates.
    """
    id: str = Field(..., description="Primary Key, e.g., paper_slug#chunk_idx")
    raw_text: str = Field(..., description="Extracted text content")
    bounding_box: dict[str, Any] = Field(..., description="Pixel coordinates: {page: INT, coords: [x1, y1, x2, y2]}")
    verification_status: Literal["raw", "under_correction", "pending_verification", "verified", "rejected"] = Field(
        default="raw",
        description="HITL correction workflow status"
    )
    last_modified_by: Optional[str] = Field(default=None, description="arbitrator_id who last edited this node")
    last_modified_at: Optional[str] = Field(default=None, description="ISO 8601 timestamp of last edit")
    modification_count: int = Field(default=0, description="Number of times this node has been edited")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "id": "paper_satellite_switching_2026#chunk_p4_c2",
            "raw_text": "The experimental setup achieves a total matrix reconfiguration latency of approximately 12.5 ms under a 80% network load.",
            "bounding_box": {"page": 4, "coords": [100, 200, 450, 280]},
            "verification_status": "raw"
        }
    })


class FormulaNode(BaseModel):
    """
    Tier 3: Physical Evidence & Symbols
    Represents a mathematical formula extracted from a paper.
    """
    id: str = Field(..., description="Primary Key")
    latex_string: str = Field(..., description="LaTeX representation of the formula")
    variables_map: dict[str, str] = Field(..., description="Key-value semantic bindings of symbols")
    constraints: dict[str, Any] = Field(default_factory=dict, description="Boundary conditions under which equations hold true")
    verification_status: Literal["raw", "under_correction", "pending_verification", "verified", "rejected"] = Field(
        default="raw",
        description="HITL correction workflow status"
    )
    last_modified_by: Optional[str] = Field(default=None, description="arbitrator_id who last edited this node")
    last_modified_at: Optional[str] = Field(default=None, description="ISO 8601 timestamp of last edit")
    modification_count: int = Field(default=0, description="Number of times this node has been edited")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "id": "form_eq_3",
            "latex_string": r"\tau_{total} = N \cdot \Delta t_{gate} + \delta_{propagation}",
            "variables_map": {
                r"\tau_{total}": "total_latency",
                "N": "port_count",
                r"\Delta t_{gate}": "gate_reconfiguration_time"
            },
            "constraints": {
                "valid_for": "mesh topology",
                "temperature_range": "0-70C"
            }
        }
    })


class AssertionNode(BaseModel):
    """
    Tier 2: Claims & Semantic Alignment
    Represents a normalized scientific claim bound to specific metrics and conditions.
    Enhanced with namespace to support multi-domain-pack workspaces.
    """
    id: str = Field(..., description="Primary Key")
    subject: str = Field(..., description="Namespaced metric name, e.g., 'optical:reconfiguration_delay'")
    predicate: Literal["equals", "is_bounded_by", "decreases_to"] = Field(..., description="Relationship type")
    object: str = Field(..., description="Quantitative or qualitative output value")
    unit: str = Field(..., description="Unit of measurement")
    domain_pack_namespace: str = Field(..., description="Which domain pack this assertion belongs to")
    context_conditions: dict[str, Any] = Field(..., description="Environmental limits (e.g., load, temperature, topology)")
    status: Literal["pending", "resolved", "locked"] = Field(default="pending", description="Processing state")
    workspace_id: str = Field(..., description="Workspace this assertion belongs to for multi-user isolation")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "id": "assert_001",
            "subject": "optical:reconfiguration_delay",
            "predicate": "equals",
            "object": "12.5",
            "unit": "ms",
            "domain_pack_namespace": "optical",
            "context_conditions": {
                "network_load": "80%",
                "topology": "mesh"
            },
            "status": "pending",
            "workspace_id": "workspace_5g_backhaul_2026"
        }
    })


class HumanArbitratorNode(BaseModel):
    """
    Tier 1: Human-in-the-Loop intervention record
    Represents a human decision that overrides automated extraction.
    Enhanced with intent metadata for pattern learning (Section 2.6).
    """
    id: str = Field(..., description="Primary Key, e.g., arbitrator_user_session_timestamp")
    user_id: str = Field(..., description="Identifier of the human who made the decision")
    timestamp: datetime = Field(..., description="When the arbitration was committed")
    arbitration_notes: str = Field(..., description="Human rationale for the decision")
    lock_type: Literal["permanent_human_lock", "temporary_override"] = Field(..., description="Lock persistence level")
    
    # Intent Framework fields (Section 2.6.1)
    intent_type: Optional[Literal["correction", "preference", "priority", "constraint", "goal"]] = Field(
        None,
        description="Classifies the intent level - see Section 2.6.1"
    )
    intent_scope: Optional[Literal["local", "pattern", "global"]] = Field(
        None,
        description="Defines generalization potential"
    )
    generalization_hint: Optional[str] = Field(
        None,
        description="Human-readable pattern description: 'Prefer ASIC over FPGA for baseline selection'"
    )
    confidence_override: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="User's confidence in this decision, 0.0-1.0"
    )
    intent_branch_id: Optional[str] = Field(
        None,
        description="References IntentBranchNode for context isolation"
    )
    declaration_constraints: Optional[Dict[str, Any]] = Field(
        None,
        description="Structured constraints captured for explicit declarations"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Categorization tags: ['hardware_preference', 'baseline_selection']"
    )

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "id": "arbitrator_alice_20260523_143022",
            "user_id": "alice@research.org",
            "timestamp": "2026-05-23T14:30:22Z",
            "arbitration_notes": "Paper B used unoptimized FPGA logic; accepted Paper A's ASIC baseline for core system specification.",
            "lock_type": "permanent_human_lock",
            "intent_type": "priority",
            "intent_scope": "pattern",
            "generalization_hint": "Prefer ASIC over FPGA for reconfiguration_delay baselines",
            "confidence_override": 1.0,
            "intent_branch_id": None,
            "declaration_constraints": {"metric": "reconfiguration_delay"},
            "tags": ["hardware_preference", "baseline_selection"]
        }
    })


class IntentBranchNode(BaseModel):
    """
    Intent Framework: Research Context Branch
    Represents an isolated decision context for multi-project workflows (Section 2.6.5).
    """
    id: str = Field(..., description="Primary Key, e.g., intent_wdm_survey_2026")
    branch_name: str = Field(..., description="Human-readable name")
    description: str = Field(..., description="Purpose of this intent context")
    user_id: str = Field(..., description="Owner of this intent branch")
    parent_branch_id: Optional[str] = Field(None, description="Optional, for branching from existing contexts")
    created_at: datetime = Field(..., description="When this branch was created")
    active_until: Optional[datetime] = Field(None, description="Optional, auto-deactivation for time-bound projects")
    status: Literal["active", "archived", "completed"] = Field(
        default="active",
        description="Current status of this branch"
    )
    overrides: dict[str, Any] = Field(
        default_factory=dict,
        description="Context-specific preferences: subdomain filters, temporal ranges, metric priorities"
    )

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "id": "intent_wdm_survey_2026",
            "branch_name": "WDM Survey Paper 2026",
            "description": "For OFC 2026 WDM performance survey",
            "user_id": "alice@research.org",
            "parent_branch_id": None,
            "created_at": "2026-05-24T00:00:00Z",
            "active_until": "2026-08-15T23:59:59Z",
            "status": "active",
            "overrides": {
                "focus_subdomains": ["domain.networking.optical.wdm"],
                "temporal_filter": {"min_year": 2020},
                "priority_metrics": ["reconfiguration_delay", "spectral_efficiency"]
            }
        }
    })
