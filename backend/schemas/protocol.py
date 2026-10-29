"""
SSP Protocol Schema Definitions
Pydantic models for JSON-RPC 2.0 request/response messages as per Section 2 of the specification.
"""

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

# Import intent schemas for protocol usage (Section 2.6)
from .intent import IntentMetadata, AISuggestion, UserIntentProfile, ReviewItem, IntentBranchOverrides


# ============================================================================
# 2.1 textDocument/sspInitialize
# ============================================================================

class WorkspaceInfo(BaseModel):
    """Workspace identification and metadata."""
    id: str = Field(..., description="Unique workspace identifier, e.g., workspace_5g_backhaul_2026")
    name: str = Field(..., description="Human-readable workspace name")
    description: Optional[str] = Field(None, description="Purpose of this workspace")
    root: str = Field(..., description="Workspace root directory path")


class DomainPackConfig(BaseModel):
    """Domain pack configuration with namespace."""
    namespace: str = Field(..., description="Workspace-scoped namespace, e.g., 'optical', 'wireless'")
    config_ref: "ConfigRef" = Field(..., description="Reference to external config file")
    enabled: bool = Field(default=True, description="Whether this domain pack is active")


class ConfigRef(BaseModel):
    """Reference to external domain pack configuration file."""
    path: str = Field(..., description="Path to domain-pack.yaml")
    format: Literal["yaml", "json"] = Field(default="yaml", description="Config file format")
    watch: bool = Field(default=False, description="Enable hot-reload on config changes")


class SSPInitializeParams(BaseModel):
    """
    Parameters for sspInitialize request (Section 2.1).
    Supports workspace with multiple domain packs.
    """
    workspace: WorkspaceInfo = Field(..., description="Workspace identification")
    domain_packs: List[DomainPackConfig] = Field(..., description="List of domain packs to load")
    bootstrap_mode: Literal["workspace-first", "config-first"] = Field(
        default="workspace-first",
        description="Initialization strategy"
    )


class LoadedDomainPackInfo(BaseModel):
    """Information about a successfully loaded domain pack."""
    namespace: str
    domain_id: str
    name: str
    version: str
    metrics_count: int
    subdomains_count: int


class SSPInitializeResponse(BaseModel):
    """Response for sspInitialize."""
    workspace_id: str
    status: Literal["initialized", "error"]
    loaded_domain_packs: List[LoadedDomainPackInfo]
    total_papers: int = Field(default=0)
    ready: bool
    message: Optional[str] = None


# ============================================================================
# 2.2 textDocument/sspIngest
# ============================================================================

class ParseOptions(BaseModel):
    """Options for PDF parsing."""
    extract_figures: bool = Field(default=True)
    extract_tables: bool = Field(default=True)
    confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    auto_classify: bool = Field(default=True, description="Enable automatic subdomain classification")


class PaperMetadata(BaseModel):
    """Metadata extracted from paper."""
    title: str
    authors: List[str]
    year: int
    venue: Optional[str] = None
    doi: Optional[str] = None
    provenance_hash: str


class SSPIngestParams(BaseModel):
    """
    Parameters for sspIngest request (Section 2.2).
    Papers ingested into workspace and associated with target domain pack.
    """
    workspace_id: str = Field(..., description="Workspace ID this paper belongs to")
    target_domain_pack: str = Field(..., description="Namespace of target domain pack (e.g., 'optical')")
    paper_slug: str = Field(..., description="Unique identifier for paper")
    paper_metadata: PaperMetadata


class ExtractedChunk(BaseModel):
    """Text chunk with spatial coordinates."""
    chunk_id: str
    raw_text: str
    bounding_box: dict[str, Any]


class ExtractedFormula(BaseModel):
    """Mathematical formula with variable bindings."""
    formula_id: str
    latex_string: str
    variables_map: dict[str, str]
    bounding_box: dict[str, Any]


class EvidenceLink(BaseModel):
    """Link from assertion to evidence with confidence."""
    source_id: str = Field(..., description="chunk_id or formula_id")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="AI confidence for this evidence")


class ExtractedAssertion(BaseModel):
    """Normalized scientific claim."""
    assertion_id: str
    subject: str
    predicate: Literal["equals", "is_bounded_by", "decreases_to"]
    object: str
    unit: str
    context_conditions: dict[str, Any]
    evidence_links: List[EvidenceLink]


class SSPIngestResult(BaseModel):
    """Result payload for sspIngest (simplified for Phase B)."""
    paper_id: str
    status: str
    chunks_count: int = Field(default=0, description="Chunks extracted (populated by sspExtract)")
    formulas_count: int = Field(default=0, description="Formulas extracted (populated by sspExtract)")
    assertions_count: int = Field(default=0, description="Assertions created (populated later)")



# ============================================================================
# 2.3 textDocument/sspAuditConflicts (Server -> Client Notification)
# ============================================================================

class ConflictNode(BaseModel):
    """Assertion involved in a conflict."""
    paper_id: str
    assertion_id: str
    value: str
    type: Literal["automated_extract", "human_verified"]


class Conflict(BaseModel):
    """Detected epistemic conflict."""
    conflict_id: str
    metric: str
    context_match: dict[str, Any]
    nodes: List[ConflictNode]
    status: Literal["unresolved", "under_review", "resolved"]


class SSPAuditConflictsParams(BaseModel):
    """Parameters for sspAuditConflicts notification."""
    conflicts: List[Conflict]


class SSPAuditConflictsNotification(BaseModel):
    """JSON-RPC notification for textDocument/sspAuditConflicts."""
    jsonrpc: Literal["2.0"] = "2.0"
    method: Literal["textDocument/sspAuditConflicts"] = "textDocument/sspAuditConflicts"
    params: SSPAuditConflictsParams


# ============================================================================
# 2.4 textDocument/sspResolveConflict
# ============================================================================

class ConflictResolution(BaseModel):
    """Human resolution of a conflict with optional intent metadata (Section 2.6.2)."""
    accepted_assertion_id: str
    overridden_assertion_id: str
    arbitrator_notes: str
    lock_status: Literal["permanent_human_lock", "temporary_override"]
    intent_metadata: Optional[IntentMetadata] = Field(
        None,
        description="Intent metadata for pattern learning (Section 2.6)"
    )


class SSPResolveConflictParams(BaseModel):
    """Parameters for sspResolveConflict request."""
    conflict_id: str
    resolution: ConflictResolution


class SSPResolveConflictRequest(BaseModel):
    """JSON-RPC request for textDocument/sspResolveConflict."""
    jsonrpc: Literal["2.0"] = "2.0"
    method: Literal["textDocument/sspResolveConflict"] = "textDocument/sspResolveConflict"
    params: SSPResolveConflictParams
    id: int


class SSPResolveConflictResponse(BaseModel):
    """JSON-RPC response for textDocument/sspResolveConflict."""
    jsonrpc: Literal["2.0"] = "2.0"
    result: dict[str, Any] = Field(default_factory=dict, description="Success confirmation")
    id: int


# ============================================================================
# sspExtract - Extract chunks and formulas from paper
# ============================================================================

class SSPExtractParams(BaseModel):
    """Parameters for sspExtract request."""
    paper_id: str = Field(..., description="ID of paper to extract from")
    chunks: List[ExtractedChunk] = Field(default_factory=list, description="Extracted text chunks")
    formulas: List[ExtractedFormula] = Field(default_factory=list, description="Extracted formulas")
    extraction_method: str = Field(default="manual", description="Method used for extraction")


class SSPExtractResult(BaseModel):
    """Result payload for sspExtract."""
    paper_id: str
    status: str
    chunks_created: int
    formulas_created: int
    edges_created: int


# ============================================================================
# sspQuery - Execute Cypher queries
# ============================================================================

class SSPQueryParams(BaseModel):
    """Parameters for sspQuery request."""
    query: str = Field(..., description="Cypher query string")
    parameters: Optional[dict[str, Any]] = Field(default=None, description="Query parameters")
    limit: int = Field(default=100, ge=1, le=10000, description="Maximum results to return")


class SSPQueryResult(BaseModel):
    """Result payload for sspQuery."""
    records: List[dict[str, Any]] = Field(default_factory=list, description="Query result records")
    summary: dict[str, Any] = Field(default_factory=dict, description="Query execution summary")


# ============================================================================
# HITL Workflow Endpoints
# ============================================================================

class SSPLockNodeParams(BaseModel):
    """Parameters for sspLockNode request."""
    node_id: str = Field(..., description="ID of node to lock for editing")
    locked_by: str = Field(..., description="User ID locking the node")


class SSPLockNodeResult(BaseModel):
    """Result payload for sspLockNode."""
    node_id: str
    status: str
    verification_status: str
    message: str


class SSPUpdateNodeParams(BaseModel):
    """Parameters for sspUpdateNode request."""
    node_id: str = Field(..., description="ID of node to update")
    updates: dict[str, Any] = Field(..., description="Properties to update")
    modified_by: str = Field(..., description="User ID making the update")


class SSPUpdateNodeResult(BaseModel):
    """Result payload for sspUpdateNode."""
    node_id: str
    status: str
    verification_status: str
    modification_count: int
    message: str


class SSPVerifyNodeParams(BaseModel):
    """Parameters for sspVerifyNode request."""
    node_id: str = Field(..., description="ID of node to verify")
    action: Literal["approve", "reject", "request_changes"] = Field(..., description="Verification action")
    verified_by: str = Field(..., description="User ID performing verification")
    notes: Optional[str] = Field(default=None, description="Optional verification notes")


class SSPVerifyNodeResult(BaseModel):
    """Result payload for sspVerifyNode."""
    node_id: str
    status: str
    verification_status: str
    message: str


class SSPApproveDomainParams(BaseModel):
    """Parameters for sspApproveDomain request."""
    domain_id: str = Field(..., description="ID of domain to approve")
    arbitrator_id: str = Field(..., description="ID of HumanArbitratorNode")
    approval_type: Literal["topology", "metrics", "taxonomy"] = Field(..., description="Type of approval")
    approved_version: str = Field(..., description="Version being approved")


class SSPApproveDomainResult(BaseModel):
    """Result payload for sspApproveDomain."""
    domain_id: str
    arbitrator_id: str
    edge_id: str
    status: str
    message: str


class SSPLockAssertionParams(BaseModel):
    """Parameters for sspLockAssertion request."""
    assertion_id: str = Field(..., description="ID of assertion to lock")
    arbitrator_id: str = Field(..., description="ID of HumanArbitratorNode locking the assertion")
    conflict_id: str = Field(..., description="ID of conflict being resolved")


class SSPLockAssertionResult(BaseModel):
    """Result payload for sspLockAssertion."""
    assertion_id: str
    arbitrator_id: str
    edge_id: str
    status: str
    message: str


# ============================================================================
# INTENT FRAMEWORK PROTOCOLS (Section 2.6)
# ============================================================================

# 2.6.2: textDocument/sspDeclareIntent
class SSPDeclareIntentParams(BaseModel):
    """Parameters for explicit intent declaration (Section 2.6.2)."""
    intent_type: Literal["correction", "preference", "priority", "constraint", "goal"]
    intent_scope: Literal["local", "pattern", "global"]
    description: str
    constraints: Dict[str, Any] = Field(default_factory=dict)
    active_from: str = Field(..., description="ISO 8601 datetime")
    active_until: Optional[str] = Field(None, description="ISO 8601 datetime")


class SSPDeclareIntentResponse(BaseModel):
    """Response for sspDeclareIntent."""
    intent_id: str
    status: Literal["active", "paused"]
    affected_systems: List[str]
    recommendations: List[str]


# 2.6.5: textDocument/sspCreateIntentBranch
class SSPCreateIntentBranchParams(BaseModel):
    """Parameters for creating intent branch (Section 2.6.5)."""
    branch_name: str
    description: str
    inherit_from: Optional[str] = Field(None, description="Parent branch ID")
    overrides: IntentBranchOverrides = Field(default_factory=lambda: IntentBranchOverrides())


class SSPCreateIntentBranchResponse(BaseModel):
    """Response for sspCreateIntentBranch."""
    branch_id: str
    status: Literal["active", "archived", "completed"]
    created_at: str


# 2.6.5: textDocument/sspSwitchIntentContext
class SSPSwitchIntentContextParams(BaseModel):
    """Parameters for switching active intent branch."""
    branch_id: str


class SSPSwitchIntentContextResponse(BaseModel):
    """Response for sspSwitchIntentContext."""
    previous_branch_id: Optional[str]
    current_branch_id: str
    overrides_applied: Dict[str, Any]


# 2.6.6: textDocument/sspQueryByIntent
class SSPQueryByIntentParams(BaseModel):
    """Parameters for intent-aware natural language query (Section 2.6.6)."""
    query: str
    intent_context: Optional[str] = Field(None, description="Active intent branch ID")
    workspace_id: Optional[str] = Field(None, description="Optional workspace scope")


class SSPQueryByIntentResponse(BaseModel):
    """Response for sspQueryByIntent."""
    papers: List[Dict[str, Any]]
    summary: str


# 2.6.6: textDocument/sspSuggestReviewQueue
class SSPSuggestReviewQueueParams(BaseModel):
    """Parameters for smart review queue (Section 2.6.6)."""
    strategy: Literal["intent_aligned", "confidence_based", "temporal"] = "intent_aligned"
    limit: int = Field(default=10, ge=1, le=100)
    workspace_id: str = Field(..., description="Workspace containing review candidates")


class SSPSuggestReviewQueueResponse(BaseModel):
    """Response for sspSuggestReviewQueue."""
    review_items: List[ReviewItem]
    total_pending: int
    estimated_total_time: str


# 2.6.4: textDocument/sspApplyIntentPattern
class SSPApplyIntentPatternParams(BaseModel):
    """Parameters for batch pattern application (Section 2.6.4)."""
    pattern_id: str
    scope: Dict[str, Any]
    dry_run: bool = False


class SSPApplyIntentPatternResponse(BaseModel):
    """Response for sspApplyIntentPattern."""
    conflicts_resolved: int
    assertions_locked: int
    pattern_confidence: float
    user_review_recommended: bool


# 2.6.9: textDocument/sspQueryIntentProfile
class SSPQueryIntentProfileParams(BaseModel):
    """Parameters for querying user intent profile (Section 2.6.9)."""
    user_id: str
    detail_level: Literal["summary", "full"] = "summary"


class SSPQueryIntentProfileResponse(BaseModel):
    """Response for sspQueryIntentProfile."""
    profile: UserIntentProfile


# Enhanced Conflict with AI Suggestion (Section 2.6.4)
class ConflictWithSuggestion(BaseModel):
    """Conflict with AI-suggested resolution based on learned patterns."""
    conflict_id: str
    metric: str
    context_match: Dict[str, Any]
    nodes: List[Dict[str, Any]]
    status: Literal["unresolved", "resolved", "locked"]
    ai_suggestion: Optional[AISuggestion] = None


# ============================================================================
# LLM FOUNDATION PROTOCOLS (Phase 1)
# ============================================================================

class ParsedIntentResult(BaseModel):
    """Structured freeform intent parsing result."""
    intent_type: Literal["correction", "preference", "priority", "constraint", "goal"]
    intent_scope: Literal["local", "pattern", "global"]
    description: str
    constraints: Dict[str, Any] = Field(default_factory=dict)
    generalization_hint: Optional[str] = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    requires_confirmation: bool = Field(default=False)


class UploadPdfParams(BaseModel):
    """Parameters for uploading a PDF to backend-managed temporary storage."""
    file_name: str
    content_base64: str
    content_type: Optional[str] = Field(default="application/pdf")
    workspace_id: Optional[str] = None
    owner_id: Optional[str] = None


class UploadPdfResponse(BaseModel):
    """Response for a stored PDF upload."""
    upload_id: str
    file_name: str
    content_type: Optional[str] = None
    size_bytes: int
    sha256: str
    expires_at: Optional[str] = None


class CommitParsedPdfParams(BaseModel):
    """Parameters for committing a previously uploaded and parsed PDF into the graph."""
    workspace_id: str
    domain_pack_namespace: str
    upload_id: str
    owner_id: Optional[str] = None
    parse_options: ParseOptions = Field(default_factory=ParseOptions)


class CommitParsedPdfResponse(BaseModel):
    """Result of persisting a parsed PDF into the graph."""
    status: Literal["committed", "needs_review"]
    workspace_id: str
    domain_pack_namespace: str
    upload_id: str
    paper_id: str
    chunks_created: int = 0
    formulas_created: int = 0
    assertions_created: int = 0
    warnings: List[str] = Field(default_factory=list)


class ParsePdfWithDomainPackParams(BaseModel):
    """Parameters for domain-pack-grounded PDF parsing."""
    workspace_id: str
    domain_pack_namespace: str
    upload_id: Optional[str] = Field(None, description="Backend-managed upload identifier")
    paper_uri: Optional[str] = Field(None, description="URI or absolute path to a PDF")
    raw_text: Optional[str] = Field(None, description="Pre-extracted text fallback for parser orchestration")
    owner_id: Optional[str] = None
    intent_context: Optional[str] = None
    parse_options: ParseOptions = Field(default_factory=ParseOptions)


class ParsePdfWithDomainPackResponse(BaseModel):
    """Structured PDF parsing response before persistence."""
    status: Literal["accepted", "parsed", "needs_review"]
    workspace_id: str
    domain_pack_namespace: str
    upload_id: Optional[str] = None
    markdown_text: str = ""
    paper_metadata: Optional[PaperMetadata] = None
    chunks: List[ExtractedChunk] = Field(default_factory=list)
    formulas: List[ExtractedFormula] = Field(default_factory=list)
    assertions: List[ExtractedAssertion] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    extraction_method: Optional[str] = Field(
        None, description="PDF text extractor used: pypdf, marker or raw_text"
    )
    assertion_extraction_method: Optional[str] = Field(
        None, description="Assertion source: llm, heuristic or none"
    )


class ParseUserIntentParams(BaseModel):
    """Parameters for freeform user-intent parsing."""
    workspace_id: str
    user_id: str
    message: str
    owner_id: Optional[str] = None
    intent_context: Optional[str] = None


class ParseUserIntentResponse(BaseModel):
    """Response for freeform intent parsing."""
    workspace_id: str
    parsed_intent: ParsedIntentResult


class SuggestedAction(BaseModel):
    """Structured action proposal emitted by chat orchestration."""
    action_type: str
    title: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    requires_confirmation: bool = Field(default=False)


class ProcessChatMessageParams(BaseModel):
    """Parameters for chat-message routing/orchestration."""
    workspace_id: str
    message: str
    owner_id: Optional[str] = None
    intent_context: Optional[str] = None
    active_domain_packs: List[str] = Field(default_factory=list)


class ProcessChatMessageResponse(BaseModel):
    """Response from chat-message orchestration."""
    route: Literal[
        "pdf_ingestion",
        "intent_declaration",
        "workspace_query",
        "explanation",
        "action_request",
        "unknown",
    ]
    response_text: str
    suggested_actions: List[SuggestedAction] = Field(default_factory=list)
    parsed_intent: Optional[ParsedIntentResult] = None


class CapabilityDescriptor(BaseModel):
    """Typed capability surfaced to an assistant or agentic planner."""
    name: str
    description: str
    execution_scope: Literal["server", "local", "hybrid"]
    mutability: Literal["read", "write", "side_effect"]
    confirmation_policy: Literal["auto", "confirm", "deny"]
    input_schema: Dict[str, Any] = Field(default_factory=dict)
    output_schema: Dict[str, Any] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)


class ListAgentCapabilitiesParams(BaseModel):
    """Parameters for capability discovery."""
    scopes: List[Literal["server", "local", "hybrid"]] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)


class ListAgentCapabilitiesResponse(BaseModel):
    """Response for capability discovery."""
    capabilities: List[CapabilityDescriptor]


class GetLLMStatusResponse(BaseModel):
    """Runtime status for the configured LLM provider."""
    provider: str
    model: Optional[str] = None
    enabled: bool
    configured: bool
    healthy: bool
    message: str
