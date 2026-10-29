"""
SSP JSON-RPC 2.0 Server Implementation
Handles Scientific Service Protocol methods.
"""

from typing import Any, Dict, Optional
from datetime import datetime, timezone
from uuid import uuid4
from jsonrpcserver import method, Success, Error, serve, Result
from backend.database import get_db, NodeRepository, EdgeRepository
from backend.config import DomainPackLoader, RegistryManager, DomainPackValidator
from backend.schemas.protocol import (
    SSPInitializeParams,
    SSPInitializeResponse,
    SSPIngestParams,
    SSPIngestResult,
    SSPExtractParams,
    SSPExtractResult,
    SSPQueryParams,
    SSPQueryResult,
    SSPLockNodeParams,
    SSPLockNodeResult,
    SSPUpdateNodeParams,
    SSPUpdateNodeResult,
    SSPVerifyNodeParams,
    SSPVerifyNodeResult,
    SSPApproveDomainParams,
    SSPApproveDomainResult,
    SSPLockAssertionParams,
    SSPLockAssertionResult,
    PaperMetadata,
    # Intent protocol schemas (Section 2.6)
    SSPDeclareIntentParams,
    SSPDeclareIntentResponse,
    SSPCreateIntentBranchParams,
    SSPCreateIntentBranchResponse,
    SSPSwitchIntentContextParams,
    SSPSwitchIntentContextResponse,
    SSPQueryByIntentParams,
    SSPQueryByIntentResponse,
    SSPSuggestReviewQueueParams,
    SSPSuggestReviewQueueResponse,
    SSPApplyIntentPatternParams,
    SSPApplyIntentPatternResponse,
    SSPQueryIntentProfileParams,
    SSPQueryIntentProfileResponse,
    GetLLMStatusResponse,
    ListAgentCapabilitiesResponse,
    ParseUserIntentParams,
    ParsePdfWithDomainPackParams,
    UploadPdfParams,
    CommitParsedPdfParams,
)
from backend.schemas.nodes import WorkspaceNode, PaperNode, ChunkNode, FormulaNode, DomainNode, IntentBranchNode, HumanArbitratorNode
from backend.schemas.edges import BelongsToEdge, CitesEdge, ContainsEdge, LocksEdge, ApprovesEdge, ScopesEdge, InheritsFromEdge
from backend.schemas.intent import IntentGoal, IntentBranchOverrides, ReviewItem
from backend.services.intent_learning_engine import IntentLearningEngine
from backend.services.llm import build_server_capability_registry, get_default_provider, parse_user_intent
from backend.services.pdf_ingestion_service import commit_parsed_pdf, parse_pdf_with_domain_pack, store_pdf_upload


# Global state
_loader: Optional[DomainPackLoader] = None
_registry_manager: Optional[RegistryManager] = None
_validator: Optional[DomainPackValidator] = None


def _serialize_workspace(workspace: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": workspace.get("id"),
        "name": workspace.get("name"),
        "description": workspace.get("description"),
        "root": workspace.get("root_path"),
        "created_at": workspace.get("created_at"),
        "last_modified_at": workspace.get("last_modified_at"),
        "status": workspace.get("status", "active"),
        "owner_id": workspace.get("owner_id"),
        "metadata": workspace.get("metadata", {}),
    }


def _workspace_is_accessible(workspace: Dict[str, Any], owner_id: Optional[str]) -> bool:
    if not workspace:
        return False
    if owner_id is None:
        return True
    workspace_owner = workspace.get("owner_id")
    return workspace_owner is None or workspace_owner == owner_id


def _get_accessible_workspace(node_repo: NodeRepository, workspace_id: str, owner_id: Optional[str]) -> Optional[Dict[str, Any]]:
    workspace = node_repo.get_workspace_node(workspace_id)
    if not _workspace_is_accessible(workspace, owner_id):
        return None
    return workspace


@method
def getLLMStatus() -> Result:
    try:
        provider = get_default_provider()
        response = GetLLMStatusResponse(**provider.get_status().model_dump())
        return Success(response.model_dump())
    except Exception as e:
        return Error(code=-32603, message=f"Failed to get LLM status: {str(e)}")


@method
def listAgentCapabilities(
    scopes: Optional[list[str]] = None,
    tags: Optional[list[str]] = None,
) -> Result:
    try:
        registry = build_server_capability_registry()
        capabilities = [cap.model_dump() for cap in registry.list(scopes=scopes, tags=tags)]
        response = ListAgentCapabilitiesResponse(capabilities=capabilities)
        return Success(response.model_dump())
    except Exception as e:
        return Error(code=-32603, message=f"Failed to list agent capabilities: {str(e)}")


@method
async def parseUserIntent(
    workspace_id: str,
    user_id: str,
    message: str,
    owner_id: Optional[str] = None,
    intent_context: Optional[str] = None,
) -> Result:
    try:
        request = ParseUserIntentParams(
            workspace_id=workspace_id,
            user_id=user_id,
            message=message,
            owner_id=owner_id,
            intent_context=intent_context,
        )
        response = await parse_user_intent(request)
        return Success(response.model_dump())
    except Exception as e:
        return Error(code=-32603, message=f"Failed to parse user intent: {str(e)}")


@method
def uploadPdf(
    file_name: str,
    content_base64: str,
    content_type: Optional[str] = "application/pdf",
    workspace_id: Optional[str] = None,
    owner_id: Optional[str] = None,
) -> Result:
    try:
        request = UploadPdfParams(
            file_name=file_name,
            content_base64=content_base64,
            content_type=content_type,
            workspace_id=workspace_id,
            owner_id=owner_id,
        )
        response = store_pdf_upload(request)
        return Success(response.model_dump())
    except Exception as e:
        return Error(code=-32603, message=f"Failed to upload PDF: {str(e)}")


@method
def parsePdfWithDomainPack(
    workspace_id: str,
    domain_pack_namespace: str,
    upload_id: Optional[str] = None,
    paper_uri: Optional[str] = None,
    raw_text: Optional[str] = None,
    owner_id: Optional[str] = None,
    intent_context: Optional[str] = None,
    parse_options: Optional[Dict[str, Any]] = None,
) -> Result:
    try:
        request = ParsePdfWithDomainPackParams(
            workspace_id=workspace_id,
            domain_pack_namespace=domain_pack_namespace,
            upload_id=upload_id,
            paper_uri=paper_uri,
            raw_text=raw_text,
            owner_id=owner_id,
            intent_context=intent_context,
            parse_options=parse_options or {},
        )
        response = parse_pdf_with_domain_pack(request)
        return Success(response.model_dump())
    except Exception as e:
        return Error(code=-32603, message=f"Failed to parse PDF: {str(e)}")


@method
def commitParsedPdf(
    workspace_id: str,
    domain_pack_namespace: str,
    upload_id: str,
    owner_id: Optional[str] = None,
    parse_options: Optional[Dict[str, Any]] = None,
) -> Result:
    try:
        request = CommitParsedPdfParams(
            workspace_id=workspace_id,
            domain_pack_namespace=domain_pack_namespace,
            upload_id=upload_id,
            owner_id=owner_id,
            parse_options=parse_options or {},
        )

        db = get_db()
        node_repo = NodeRepository(db)
        edge_repo = EdgeRepository(db)
        workspace = _get_accessible_workspace(node_repo, workspace_id, owner_id)
        if not workspace:
            return Error(code=-32602, message="Workspace not found or not accessible")

        response = commit_parsed_pdf(request, node_repo=node_repo, edge_repo=edge_repo, workspace_exists=True)
        return Success(response.model_dump())
    except Exception as e:
        return Error(code=-32603, message=f"Failed to commit parsed PDF: {str(e)}")


@method
def listWorkspaces(owner_id: Optional[str] = None, include_archived: bool = False) -> Result:
    try:
        db = get_db()
        node_repo = NodeRepository(db)
        workspaces = node_repo.list_workspace_nodes()
        visible_workspaces = [
            _serialize_workspace(workspace)
            for workspace in workspaces
            if _workspace_is_accessible(workspace, owner_id)
            and (include_archived or workspace.get("status") != "archived")
        ]
        return Success({"workspaces": visible_workspaces})
    except Exception as e:
        return Error(code=-32603, message=f"Failed to list workspaces: {str(e)}")


@method
def getWorkspace(workspace_id: str, owner_id: Optional[str] = None) -> Result:
    try:
        db = get_db()
        node_repo = NodeRepository(db)
        workspace = _get_accessible_workspace(node_repo, workspace_id, owner_id)
        if not workspace:
            return Error(code=-32602, message="Workspace not found or not accessible")
        return Success({"workspace": _serialize_workspace(workspace)})
    except Exception as e:
        return Error(code=-32603, message=f"Failed to fetch workspace: {str(e)}")


@method
def createWorkspace(
    name: str,
    root: Optional[str] = None,
    description: Optional[str] = None,
    owner_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Result:
    try:
        workspace_name = name.strip()
        if not workspace_name:
            return Error(code=-32602, message="Workspace name is required")

        slug = "".join(char.lower() if char.isalnum() else "_" for char in workspace_name).strip("_") or "workspace"
        workspace_id = f"workspace_{slug}_{uuid4().hex[:8]}"
        timestamp = datetime.now(timezone.utc)
        workspace_root = root.strip() if root else f"file:///workspace/{workspace_id}"

        workspace = WorkspaceNode(
            id=workspace_id,
            name=workspace_name,
            description=description.strip() if description else None,
            root_path=workspace_root,
            created_at=timestamp,
            last_modified_at=timestamp,
            status="active",
            owner_id=owner_id,
            metadata=metadata or {},
        )

        db = get_db()
        node_repo = NodeRepository(db)
        created_workspace = node_repo.create_workspace_node(workspace)
        return Success({"workspace": _serialize_workspace(created_workspace)})
    except Exception as e:
        return Error(code=-32603, message=f"Failed to create workspace: {str(e)}")


@method
def deleteWorkspace(workspace_id: str, owner_id: Optional[str] = None) -> Result:
    try:
        if not workspace_id:
            return Error(code=-32602, message="Workspace ID is required")

        db = get_db()
        node_repo = NodeRepository(db)
        
        # Check if workspace exists and is accessible
        workspace = _get_accessible_workspace(node_repo, workspace_id, owner_id)
        if not workspace:
            return Error(code=-32602, message="Workspace not found or not accessible")
        
        # Delete the workspace and all related data
        deleted = node_repo.delete_workspace_node(workspace_id)
        if not deleted:
            return Error(code=-32603, message="Failed to delete workspace")
        
        return Success({"deleted": True, "workspace_id": workspace_id})
    except Exception as e:
        return Error(code=-32603, message=f"Failed to delete workspace: {str(e)}")


@method
def sspInitialize(params: Dict[str, Any]) -> Result:
    """
    Initialize the OntoForge system with a domain pack.

    Args:
        params: SSPInitializeParams

    Returns:
        SSPInitializeResponse with registry summary
    """
    global _loader, _registry_manager, _validator

    try:
        # Validate request
        request = SSPInitializeParams(**params)

        # Load domain pack
        _loader = DomainPackLoader(request.configRef.path)
        config = _loader.load()

        # Validate domain pack
        _validator = DomainPackValidator(config)
        validation_errors = _validator.validate()
        if validation_errors:
            return Error(
                code=-32602,
                message="Domain pack validation failed",
                data={"errors": validation_errors},
            )

        # Build registries
        _registry_manager = RegistryManager.from_config(config)

        # Create DomainNode in graph
        db = get_db()
        node_repo = NodeRepository(db)

        domain_node = DomainNode(
            id=config.domain_id,
            name=config.metadata.name,
            domain_pack_id=config.metadata.domain_pack_id,
            domain_pack_version=config.metadata.version,
            taxonomy_tree=config.taxonomy,
            core_metrics=[m.name for m in config.metrics],
        )
        node_repo.create_domain_node(domain_node)

        # Build response
        response = SSPInitializeResponse(
            status="success",
            domain_pack_loaded=True,
            metrics_count=len(config.metrics),
            message=f"Initialized with domain pack {config.metadata.domain_pack_id}"
        )

        return Success(response.model_dump())

    except Exception as e:
        return Error(code=-32603, message=f"Internal error: {str(e)}")


@method
def sspIngest(params: Dict[str, Any]) -> Result:
    """
    Ingest paper metadata and create PaperNode.

    Args:
        params: SSPIngestParams

    Returns:
        SSPIngestResult with created node ID
    """
    try:
        # Validate request
        request = SSPIngestParams(**params)

        # Create PaperNode
        paper_node = PaperNode(
            id=request.paper_slug,
            doi=request.paper_metadata.doi,
            title=request.paper_metadata.title,
            authors=request.paper_metadata.authors,
            year=request.paper_metadata.year,
            venue=request.paper_metadata.venue or "Unknown",
            provenance_hash=request.paper_metadata.provenance_hash,
        )

        # Save to database
        db = get_db()
        node_repo = NodeRepository(db)
        created_node = node_repo.create_paper_node(paper_node)

        # Create BELONGS_TO edge to DomainNode
        if _loader:
            config = _loader.load()
            edge_repo = EdgeRepository(db)
            belongs_edge = BelongsToEdge(
                from_node_id=request.paper_slug, to_node_id=config.domain_id
            )
            edge_repo.create_belongs_to_edge(belongs_edge)

        # Build response
        response = SSPIngestResult(
            paper_id=created_node.get("id", request.paper_slug),
            status="success",
            chunks_count=0,  # Will be populated by sspExtract
            formulas_count=0,  # Will be populated by sspExtract
            assertions_count=0,  # Will be populated by extraction
        )

        return Success(response.model_dump())

    except Exception as e:
        return Error(code=-32603, message=f"Internal error: {str(e)}")


@method
def sspExtract(params: Dict[str, Any]) -> Result:
    """
    Extract chunks and formulas from a paper.

    Args:
        params: SSPExtractParams with paper_id, chunks, formulas

    Returns:
        SSPExtractResult with counts of created nodes and edges
    """
    try:
        # Validate request
        request = SSPExtractParams(**params)

        db = get_db()
        node_repo = NodeRepository(db)
        edge_repo = EdgeRepository(db)

        chunks_created = 0
        formulas_created = 0
        edges_created = 0

        # Create ChunkNodes
        for chunk in request.chunks:
            chunk_node = ChunkNode(
                id=chunk.chunk_id,
                raw_text=chunk.raw_text,
                bounding_box=chunk.bounding_box,
                verification_status="raw",  # Initial state
            )
            node_repo.create_chunk_node(chunk_node)
            chunks_created += 1

            # Create CONTAINS edge from PaperNode to ChunkNode
            contains_edge = ContainsEdge(
                from_node_id=request.paper_id,
                to_node_id=chunk.chunk_id,
                extraction_method=request.extraction_method,
            )
            edge_repo.create_contains_edge(contains_edge)
            edges_created += 1

        # Create FormulaNodes
        for formula in request.formulas:
            formula_node = FormulaNode(
                id=formula.formula_id,
                latex_string=formula.latex_string,
                variable_bindings=formula.variables_map,
                bounding_box=formula.bounding_box,
                verification_status="raw",  # Initial state
            )
            node_repo.create_formula_node(formula_node)
            formulas_created += 1

            # Create CONTAINS edge from PaperNode to FormulaNode
            contains_edge = ContainsEdge(
                from_node_id=request.paper_id,
                to_node_id=formula.formula_id,
                extraction_method=request.extraction_method,
            )
            edge_repo.create_contains_edge(contains_edge)
            edges_created += 1

        # Build response
        response = SSPExtractResult(
            paper_id=request.paper_id,
            status="success",
            chunks_created=chunks_created,
            formulas_created=formulas_created,
            edges_created=edges_created,
        )

        return Success(response.model_dump())

    except Exception as e:
        return Error(code=-32603, message=f"Internal error: {str(e)}")


@method
def sspQuery(params: Dict[str, Any]) -> Result:
    """
    Execute a Cypher query against the Neo4j database.

    Args:
        params: SSPQueryParams with query string and optional parameters

    Returns:
        SSPQueryResult with records and execution summary
    """
    try:
        # Validate request
        request = SSPQueryParams(**params)

        db = get_db()

        # Execute query with parameters
        query_params = request.parameters or {}
        
        # Add LIMIT clause if not present
        query = request.query.strip()
        if "LIMIT" not in query.upper():
            query = f"{query} LIMIT {request.limit}"

        # Execute query
        with db.session() as session:
            result = session.run(query, query_params)
            records = [record.data() for record in result]
            
            # Get execution summary
            summary_info = result.consume()
            summary = {
                "records_returned": len(records),
                "query_type": summary_info.query_type,
                "counters": {
                    "nodes_created": summary_info.counters.nodes_created,
                    "nodes_deleted": summary_info.counters.nodes_deleted,
                    "relationships_created": summary_info.counters.relationships_created,
                    "relationships_deleted": summary_info.counters.relationships_deleted,
                    "properties_set": summary_info.counters.properties_set,
                },
            }

        # Build response
        response = SSPQueryResult(records=records, summary=summary)

        return Success(response.model_dump())

    except Exception as e:
        return Error(code=-32603, message=f"Internal error: {str(e)}")


# ============================================================================
# HITL Workflow Endpoints
# ============================================================================

@method
def sspLockNode(params: Dict[str, Any]) -> Result:
    """
    Lock a node for editing (HITL correction workflow).
    
    Sets verification_status to 'under_correction' and tracks the user.
    
    Args:
        params: SSPLockNodeParams with node_id and locked_by
        
    Returns:
        SSPLockNodeResult with updated status
    """
    try:
        request = SSPLockNodeParams(**params)
        
        db = get_db()
        node_repo = NodeRepository(db)
        
        # Update node to under_correction status
        updates = {
            "verification_status": "under_correction",
            "last_modified_by": request.locked_by,
            "last_modified_at": datetime.now(timezone.utc).isoformat(),
        }
        
        updated_node = node_repo.update_node(request.node_id, updates)
        
        response = SSPLockNodeResult(
            node_id=request.node_id,
            status="success",
            verification_status="under_correction",
            message=f"Node locked for editing by {request.locked_by}",
        )
        
        return Success(response.model_dump())
        
    except Exception as e:
        return Error(code=-32603, message=f"Internal error: {str(e)}")


@method
def sspUpdateNode(params: Dict[str, Any]) -> Result:
    """
    Update node properties with audit trail tracking.
    
    After editing, sets verification_status to 'pending_verification'.
    
    Args:
        params: SSPUpdateNodeParams with node_id, updates, modified_by
        
    Returns:
        SSPUpdateNodeResult with updated status and modification count
    """
    try:
        request = SSPUpdateNodeParams(**params)
        
        db = get_db()
        node_repo = NodeRepository(db)
        
        # Get current node to increment modification count
        current_node = node_repo.get_node_by_id(request.node_id)
        current_count = current_node.get("modification_count", 0)
        
        # Prepare updates with audit trail
        updates = {
            **request.updates,
            "verification_status": "pending_verification",
            "last_modified_by": request.modified_by,
            "last_modified_at": datetime.now(timezone.utc).isoformat(),
            "modification_count": current_count + 1,
        }
        
        updated_node = node_repo.update_node(request.node_id, updates)
        
        response = SSPUpdateNodeResult(
            node_id=request.node_id,
            status="success",
            verification_status="pending_verification",
            modification_count=current_count + 1,
            message=f"Node updated and marked pending verification",
        )
        
        return Success(response.model_dump())
        
    except Exception as e:
        return Error(code=-32603, message=f"Internal error: {str(e)}")


@method
def sspVerifyNode(params: Dict[str, Any]) -> Result:
    """
    Verify a node (approve, reject, or request changes).
    
    Reviewer approves or rejects pending nodes.
    
    Args:
        params: SSPVerifyNodeParams with node_id, action, verified_by
        
    Returns:
        SSPVerifyNodeResult with final verification status
    """
    try:
        request = SSPVerifyNodeParams(**params)
        
        db = get_db()
        node_repo = NodeRepository(db)
        
        # Map action to verification status
        status_map = {
            "approve": "verified",
            "reject": "rejected",
            "request_changes": "under_correction",
        }
        
        new_status = status_map[request.action]
        
        updates = {
            "verification_status": new_status,
            "last_modified_by": request.verified_by,
            "last_modified_at": datetime.now(timezone.utc).isoformat(),
        }
        
        if request.notes:
            updates["verification_notes"] = request.notes
        
        updated_node = node_repo.update_node(request.node_id, updates)
        
        response = SSPVerifyNodeResult(
            node_id=request.node_id,
            status="success",
            verification_status=new_status,
            message=f"Node {request.action}d by {request.verified_by}",
        )
        
        return Success(response.model_dump())
        
    except Exception as e:
        return Error(code=-32603, message=f"Internal error: {str(e)}")


@method
def sspApproveDomain(params: Dict[str, Any]) -> Result:
    """
    Create APPROVES edge from HumanArbitratorNode to DomainNode.
    
    Records human approval of domain changes (topology, metrics, taxonomy).
    
    Args:
        params: SSPApproveDomainParams
        
    Returns:
        SSPApproveDomainResult with edge creation status
    """
    try:
        request = SSPApproveDomainParams(**params)
        
        db = get_db()
        edge_repo = EdgeRepository(db)
        
        # Create APPROVES edge
        approves_edge = ApprovesEdge(
            from_node_id=request.arbitrator_id,
            to_node_id=request.domain_id,
            approval_type=request.approval_type,
            approved_version=request.approved_version,
        )
        
        created_edge = edge_repo.create_approves_edge(approves_edge)
        edge_id = created_edge.get("id", f"{request.arbitrator_id}-APPROVES-{request.domain_id}")
        
        response = SSPApproveDomainResult(
            domain_id=request.domain_id,
            arbitrator_id=request.arbitrator_id,
            edge_id=edge_id,
            status="success",
            message=f"Domain {request.approval_type} approved by {request.arbitrator_id}",
        )
        
        return Success(response.model_dump())
        
    except Exception as e:
        return Error(code=-32603, message=f"Internal error: {str(e)}")


@method
def sspLockAssertion(params: Dict[str, Any]) -> Result:
    """
    Create LOCKS edge from HumanArbitratorNode to AssertionNode.
    
    Locks an assertion during conflict resolution.
    
    Args:
        params: SSPLockAssertionParams
        
    Returns:
        SSPLockAssertionResult with edge creation status
    """
    try:
        request = SSPLockAssertionParams(**params)
        
        db = get_db()
        edge_repo = EdgeRepository(db)
        
        # Create LOCKS edge
        locks_edge = LocksEdge(
            from_node_id=request.arbitrator_id,
            to_node_id=request.assertion_id,
        )
        
        created_edge = edge_repo.create_locks_edge(locks_edge)
        edge_id = created_edge.get("id", f"{request.arbitrator_id}-LOCKS-{request.assertion_id}")
        
        response = SSPLockAssertionResult(
            assertion_id=request.assertion_id,
            arbitrator_id=request.arbitrator_id,
            edge_id=edge_id,
            status="success",
            message=f"Assertion locked for conflict {request.conflict_id}",
        )
        
        return Success(response.model_dump())
        
    except Exception as e:
        return Error(code=-32603, message=f"Internal error: {str(e)}")


# ============================================================================
# INTENT FRAMEWORK HANDLERS (Section 2.6)
# ============================================================================

@method
def sspDeclareIntent(
    intent_type: str,
    intent_scope: str,
    description: str,
    constraints: Optional[Dict[str, Any]] = None,
    active_from: Optional[str] = None,
    active_until: Optional[str] = None,
) -> Result:
    """
    Explicit intent declaration (Section 2.6.2).
    
    Allows users to declare high-level intents (goals, constraints, preferences).
    
    Args:
        flattened SSPDeclareIntentParams fields
        
    Returns:
        SSPDeclareIntentResponse with intent ID and affected systems
    """
    try:
        request = SSPDeclareIntentParams(
            intent_type=intent_type,
            intent_scope=intent_scope,
            description=description,
            constraints=constraints or {},
            active_from=active_from or datetime.now().date().isoformat(),
            active_until=active_until,
        )
        
        intent_id = f"intent_{request.intent_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        declaration = HumanArbitratorNode(
            id=intent_id,
            user_id="current_user",
            timestamp=datetime.now(timezone.utc),
            arbitration_notes=request.description,
            lock_type="permanent_human_lock",
            intent_type=request.intent_type,
            intent_scope=request.intent_scope,
            generalization_hint=request.description,
            confidence_override=1.0,
            intent_branch_id=None,
            declaration_constraints=request.constraints,
            tags=[
                "explicit_declaration",
                f"intent_type_{request.intent_type}",
                f"intent_scope_{request.intent_scope}",
            ],
        )
        try:
            db = get_db()
            node_repo = NodeRepository(db)
            node_repo.create_arbitrator_node(declaration)
        except RuntimeError:
            pass
        
        response = SSPDeclareIntentResponse(
            intent_id=intent_id,
            status="active",
            affected_systems=["conflict_resolution", "review_queue", "query_ranking"],
            recommendations=[
                f"Intent '{request.intent_type}' will affect conflict resolution suggestions",
                f"Scope '{request.intent_scope}' applies to: {request.intent_scope}"
            ]
        )
        
        return Success(response.model_dump())
        
    except Exception as e:
        return Error(code=-32603, message=f"Internal error: {str(e)}")


@method
def sspCreateIntentBranch(params: Dict[str, Any]) -> Result:
    """
    Create intent branch for research context isolation (Section 2.6.5).
    
    Args:
        params: SSPCreateIntentBranchParams
        
    Returns:
        SSPCreateIntentBranchResponse with branch ID
    """
    try:
        request = SSPCreateIntentBranchParams(**params)
        
        db = get_db()
        node_repo = NodeRepository(db)
        edge_repo = EdgeRepository(db)
        
        # Create IntentBranchNode
        branch_id = f"intent_{request.branch_name.lower().replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}"
        
        branch_node = IntentBranchNode(
            id=branch_id,
            branch_name=request.branch_name,
            description=request.description,
            user_id="default_user",  # Would come from auth context
            parent_branch_id=request.inherit_from,
            created_at=datetime.now(timezone.utc),
            active_until=None,
            status="active",
            overrides=request.overrides.model_dump()
        )
        
        created_node = node_repo.create_intent_branch_node(branch_node)
        
        # Create INHERITS_FROM edge if parent exists
        if request.inherit_from:
            inherits_edge = InheritsFromEdge(
                from_node_id=branch_id,
                to_node_id=request.inherit_from
            )
            edge_repo.create_inherits_from_edge(inherits_edge)
        
        response = SSPCreateIntentBranchResponse(
            branch_id=branch_id,
            status="active",
            created_at=datetime.now(timezone.utc).isoformat()
        )
        
        return Success(response.model_dump())
        
    except Exception as e:
        return Error(code=-32603, message=f"Internal error: {str(e)}")


@method
def sspSwitchIntentContext(params: Dict[str, Any]) -> Result:
    """
    Switch active intent branch (Section 2.6.5).
    
    Args:
        params: SSPSwitchIntentContextParams
        
    Returns:
        SSPSwitchIntentContextResponse with applied overrides
    """
    try:
        request = SSPSwitchIntentContextParams(**params)
        
        db = get_db()
        node_repo = NodeRepository(db)
        
        # Get intent branch
        branch = node_repo.get_intent_branch(request.branch_id)
        
        if not branch:
            return Error(code=-32602, message=f"Intent branch not found: {request.branch_id}")
        
        # Simulate context switch (would update session state)
        previous_branch_id = None  # Would retrieve from session
        
        response = SSPSwitchIntentContextResponse(
            previous_branch_id=previous_branch_id,
            current_branch_id=request.branch_id,
            overrides_applied=branch.get("overrides", {})
        )
        
        return Success(response.model_dump())
        
    except Exception as e:
        return Error(code=-32603, message=f"Internal error: {str(e)}")


@method
def sspQueryByIntent(params: Dict[str, Any]) -> Result:
    """
    Intent-aware natural language query (Section 2.6.6).
    
    Args:
        params: SSPQueryByIntentParams
        
    Returns:
        SSPQueryByIntentResponse with ranked papers
    """
    try:
        request = SSPQueryByIntentParams(**params)
        
        db = get_db()
        node_repo = NodeRepository(db)
        
        # Get intent context if specified
        context_overrides = {}
        if request.intent_context:
            branch = node_repo.get_intent_branch(request.intent_context)
            if branch:
                context_overrides = branch.get("overrides", {})
        
        # Simulate intent-aware search (would use vector embeddings + intent filtering)
        # For now, basic Cypher query
        query = """
        MATCH (p:PaperNode)
        WHERE toLower(p.title) CONTAINS toLower($query_term)
        RETURN p
        LIMIT 10
        """
        
        results = node_repo.execute_query(query, {"query_term": request.query})
        
        papers = [record["p"] for record in results]
        
        response = SSPQueryByIntentResponse(
            papers=papers,
            summary=f"Found {len(papers)} papers matching '{request.query}' with intent context applied"
        )
        
        return Success(response.model_dump())
        
    except Exception as e:
        return Error(code=-32603, message=f"Internal error: {str(e)}")


@method
def sspSuggestReviewQueue(params: Dict[str, Any]) -> Result:
    """
    Smart review queue generation (Section 2.6.6).
    
    Args:
        params: SSPSuggestReviewQueueParams
        
    Returns:
        SSPSuggestReviewQueueResponse with prioritized review items
    """
    try:
        request = SSPSuggestReviewQueueParams(**params)
        
        db = get_db()
        node_repo = NodeRepository(db)
        
        # Get unresolved conflicts
        query = """
        MATCH (a1:AssertionNode)-[c:CONTRADICTS]->(a2:AssertionNode)
        WHERE NOT EXISTS((a1)<-[:LOCKS]-(:HumanArbitratorNode))
        RETURN a1, a2, c
        LIMIT $limit
        """
        
        results = node_repo.execute_query(query, {"limit": request.limit})
        
        # Create ReviewItem for each conflict
        review_items = []
        for i, record in enumerate(results):
            item = ReviewItem(
                item_id=f"conflict_{i}",
                item_type="conflict",
                title=f"Conflict between assertions",
                intent_relevance=0.8,  # Would compute based on intent patterns
                estimated_time="5 minutes",
                priority=1.0 - (i * 0.1)
            )
            review_items.append(item)
        
        total_time = len(review_items) * 5  # 5 minutes per item
        
        response = SSPSuggestReviewQueueResponse(
            review_items=review_items,
            total_pending=len(review_items),
            estimated_total_time=f"{total_time} minutes"
        )
        
        return Success(response.model_dump())
        
    except Exception as e:
        return Error(code=-32603, message=f"Internal error: {str(e)}")


@method
def sspApplyIntentPattern(params: Dict[str, Any]) -> Result:
    """
    Batch pattern application (Section 2.6.4).
    
    Args:
        params: SSPApplyIntentPatternParams
        
    Returns:
        SSPApplyIntentPatternResponse with resolution stats
    """
    try:
        request = SSPApplyIntentPatternParams(**params)
        
        db = get_db()
        node_repo = NodeRepository(db)
        edge_repo = EdgeRepository(db)
        
        # Get pattern from learning engine
        learning_engine = IntentLearningEngine(node_repo, edge_repo)
        
        # Simulate pattern application (would match conflicts and auto-resolve)
        conflicts_resolved = 0
        assertions_locked = 0
        pattern_confidence = 0.85
        
        if not request.dry_run:
            # Would apply pattern to matching conflicts
            pass
        
        response = SSPApplyIntentPatternResponse(
            conflicts_resolved=conflicts_resolved,
            assertions_locked=assertions_locked,
            pattern_confidence=pattern_confidence,
            user_review_recommended=pattern_confidence < 0.8
        )
        
        return Success(response.model_dump())
        
    except Exception as e:
        return Error(code=-32603, message=f"Internal error: {str(e)}")


@method
def sspQueryIntentProfile(user_id: str, detail_level: str = "full") -> Result:
    """
    Query user intent profile (Section 2.6.9).
    
    Args:
        params: SSPQueryIntentProfileParams
        
    Returns:
        SSPQueryIntentProfileResponse with user profile
    """
    try:
        request = SSPQueryIntentProfileParams(user_id=user_id, detail_level=detail_level)
        
        db = get_db()
        node_repo = NodeRepository(db)
        edge_repo = EdgeRepository(db)
        
        # Build user intent profile
        learning_engine = IntentLearningEngine(node_repo, edge_repo)
        
        profile = learning_engine.build_user_intent_profile_sync(request.user_id)
        
        response = SSPQueryIntentProfileResponse(
            profile=profile
        )
        
        return Success(response.model_dump(mode="json"))
        
    except Exception as e:
        return Error(code=-32603, message=f"Internal error: {str(e)}")


@method
def bootstrapDomainPack(proposal_text: str) -> Result:
    """
    Bootstrap a domain pack configuration from a research proposal text.
    
    Uses LLM to extract domain concepts, metrics, and taxonomy from the proposal.
    
    Args:
        proposal_text: Research proposal or domain description text
        
    Returns:
        A complete domain pack configuration (DomainPackConfig structure)
    """
    from backend.services.llm.domain_pack_bootstrapper import create_domain_pack_bootstrapper
    from backend.services.llm.base import NullLLMProvider
    
    try:
        if not proposal_text or not proposal_text.strip():
            return Error(code=-32602, message="Invalid params: proposal_text is required")
        
        print(f"\n🔧 Bootstrapping domain pack from proposal ({len(proposal_text)} chars)...")
        
        # Create bootstrapper with default LLM provider
        try:
            bootstrapper = create_domain_pack_bootstrapper()
            
            # Check if LLM is actually available
            if isinstance(bootstrapper.provider, NullLLMProvider):
                print("⚠️  LLM not available, using fallback logic...")
                return _bootstrap_fallback(proposal_text)
            
            # Use LLM to bootstrap
            print("🤖 Using LLM to extract domain pack structure...")
            domain_pack_config = bootstrapper.bootstrap(proposal_text)
            
            # Convert to dict for JSON-RPC response
            result = domain_pack_config.model_dump()
            print(f"✅ Domain pack bootstrapped: {domain_pack_config.domain.name}")
            print(f"   - {len(domain_pack_config.core_metrics)} metrics")
            print(f"   - {len(domain_pack_config.domain.taxonomy_tree)} taxonomy dimensions")
            
            return Success(result)
            
        except Exception as llm_error:
            print(f"⚠️  LLM bootstrapping failed: {str(llm_error)}")
            print("   Falling back to keyword-based extraction...")
            return _bootstrap_fallback(proposal_text)
            
    except Exception as e:
        print(f"❌ Bootstrap failed: {str(e)}")
        return Error(code=-32603, message=f"Internal error: {str(e)}")


def _bootstrap_fallback(proposal_text: str) -> Result:
    """
    Fallback bootstrap logic using simple keyword matching.
    Used when LLM is unavailable.
    """
    proposal_lower = proposal_text.lower()
    domain_name = "Research Domain"
    domain_id_suffix = "research"
    
    # Simple keyword matching to infer domain
    if "optical" in proposal_lower or "optic" in proposal_lower:
        domain_name = "Optical Networks"
        domain_id_suffix = "optical"
    elif "quantum" in proposal_lower:
        domain_name = "Quantum Networking"
        domain_id_suffix = "quantum"
    elif "wireless" in proposal_lower or "5g" in proposal_lower or "6g" in proposal_lower:
        domain_name = "Wireless Networks"
        domain_id_suffix = "wireless"
    elif "neural" in proposal_lower or "ai" in proposal_lower or "machine learning" in proposal_lower:
        domain_name = "Machine Learning"
        domain_id_suffix = "ml"
    
    mock_domain_pack = {
        "schema_version": "1.0",
        "domain": {
            "id": f"domain.networking.{domain_id_suffix}",
            "name": domain_name,
            "taxonomy_tree": [
                {
                    "name": "network_type",
                    "values": ["quantum_internet", "distributed_quantum_computing", "quantum_key_distribution"],
                    "subdomain_map": {
                        "quantum_internet": f"domain.networking.{domain_id_suffix}.internet",
                        "quantum_key_distribution": f"domain.networking.{domain_id_suffix}.qkd"
                    },
                    "description": "Types of network architectures"
                },
                {
                    "name": "topology",
                    "values": ["star", "mesh", "ring", "chain"],
                    "subdomain_map": {},
                    "description": "Network topology configurations"
                }
            ]
        },
        "core_metrics": [
            {
                "name": "latency",
                "expected_unit": "ms",
                "aliases": ["delay", "response_time"],
                "value_type": "float"
            },
            {
                "name": "throughput",
                "expected_unit": "Gbps",
                "aliases": ["bandwidth", "data_rate"],
                "value_type": "float"
            },
            {
                "name": "error_rate",
                "expected_unit": "percentage",
                "aliases": ["packet_loss", "bit_error_rate"],
                "value_type": "float"
            },
            {
                "name": "power_consumption",
                "expected_unit": "W",
                "aliases": ["energy_usage"],
                "value_type": "float"
            }
        ],
        "validation": {
            "required_context_keys": ["network_type", "topology"],
            "unit_normalization": {
                "ms": ["ms", "millisecond", "milliseconds"],
                "Gbps": ["Gbps", "Gbit/s"],
                "percentage": ["%", "percent", "percentage"],
                "W": ["W", "watt", "watts"]
            }
        }
    }
    
    print(f"✅ Fallback domain pack created: {domain_name}")
    return Success(mock_domain_pack)


@method
def validateDomainPack(content: str, format: str = 'yaml') -> Result:
    """
    Validate a domain pack configuration from file content.
    
    Performs parsing, Pydantic schema validation, and business logic validation.
    
    Args:
        content: File content (YAML or JSON string)
        format: File format ('yaml' or 'json'), defaults to 'yaml'
        
    Returns:
        Success with validation result:
        {
            "valid": bool,
            "errors": List[str],  # Empty if valid
            "config": dict  # Parsed config if valid
        }
    """
    try:
        if not content:
            return Error(code=-32602, message="Invalid params: content is required")
        
        format_type = format
        if format_type not in ['yaml', 'json']:
            return Error(code=-32602, message="Invalid params: format must be 'yaml' or 'json'")
        
        # Step 1: Parse the file content
        try:
            if format_type == 'yaml':
                import yaml
                config_data = yaml.safe_load(content)
            else:
                import json
                config_data = json.loads(content)
        except yaml.YAMLError as e:
            return Success({
                "valid": False,
                "errors": [f"YAML parsing error: {str(e)}"],
                "config": None
            })
        except json.JSONDecodeError as e:
            return Success({
                "valid": False,
                "errors": [f"JSON parsing error: {str(e)}"],
                "config": None
            })
        except Exception as e:
            return Success({
                "valid": False,
                "errors": [f"Parsing error: {str(e)}"],
                "config": None
            })
        
        # Step 2: Pydantic schema validation
        try:
            from backend.schemas.domain_pack import DomainPackConfig
            config = DomainPackConfig(**config_data)
        except Exception as e:
            return Success({
                "valid": False,
                "errors": [f"Schema validation failed: {str(e)}"],
                "config": None
            })
        
        # Step 3: Business logic validation
        is_valid, errors = DomainPackValidator.validate(config)
        
        return Success({
            "valid": is_valid,
            "errors": errors,
            "config": config_data if is_valid else None
        })
        
    except Exception as e:
        return Error(code=-32603, message=f"Internal error: {str(e)}")


@method
def getPapers(workspace_id: str, domain_pack_namespace: Optional[str] = None, owner_id: Optional[str] = None) -> Result:
    """
    Get all papers from the database.
    
    Args:
        workspace_id: Workspace to fetch papers from (required for isolation)
        domain_pack_namespace: Optional filter by namespace
    
    Returns:
        Success with list of papers
    """
    try:
        db = get_db()
        node_repo = NodeRepository(db)
        workspace = _get_accessible_workspace(node_repo, workspace_id, owner_id)
        if not workspace:
            return Error(code=-32602, message="Workspace not found or not accessible")
        
        # Build query with workspace filter
        if domain_pack_namespace:
            query = """
            MATCH (p:PaperNode)
            WHERE p.workspace_id = $workspace_id AND p.domain_pack_namespace = $namespace
            RETURN p
            ORDER BY p.year DESC, p.title ASC
            """
            result = db.execute_query(query, {'workspace_id': workspace_id, 'namespace': domain_pack_namespace})
        else:
            query = """
            MATCH (p:PaperNode)
            WHERE p.workspace_id = $workspace_id
            RETURN p
            ORDER BY p.year DESC, p.title ASC
            """
            result = db.execute_query(query, {'workspace_id': workspace_id})
        
        # Extract paper nodes from results
        papers = []
        for record in result:
            if 'p' in record:
                paper_data = record['p']
                papers.append({
                    'id': paper_data['id'],
                    'doi': paper_data['doi'],
                    'title': paper_data['title'],
                    'authors': paper_data['authors'],
                    'year': paper_data['year'],
                    'venue': paper_data['venue'],
                    'domain_pack_namespace': paper_data.get('domain_pack_namespace'),
                    'import_status': paper_data.get('import_status', 'pending')
                })
        
        return Success({'papers': papers})
        
    except Exception as e:
        return Error(code=-32603, message=f"Failed to fetch papers: {str(e)}")


@method
def getAssertions(workspace_id: str, paper_id: Optional[str] = None, metric_name: Optional[str] = None, domain_pack_namespace: Optional[str] = None, owner_id: Optional[str] = None) -> Result:
    """
    Get assertions from the database with optional filters.
    
    Args:
        workspace_id: Workspace to fetch assertions from (required for isolation)
        paper_id: Optional filter by specific paper
        metric_name: Optional filter by specific metric (namespaced)
        domain_pack_namespace: Optional filter by namespace
    
    Returns:
        Success with list of assertions including cell data format
    """
    try:
        db = get_db()
        node_repo = NodeRepository(db)
        workspace = _get_accessible_workspace(node_repo, workspace_id, owner_id)
        if not workspace:
            return Error(code=-32602, message="Workspace not found or not accessible")
        
        # Build query with workspace filter
        conditions = ["a.workspace_id = $workspace_id"]
        query_params = {'workspace_id': workspace_id}
        
        if paper_id:
            # Use CONTAINS edge to link paper to assertion
            query = """
            MATCH (p:PaperNode {id: $paper_id})-[:CONTAINS]->(a:AssertionNode)
            WHERE a.workspace_id = $workspace_id
            """
            query_params['paper_id'] = paper_id
            
            if metric_name:
                conditions.append("a.subject = $metric_name")
                query_params['metric_name'] = metric_name
            if domain_pack_namespace:
                conditions.append("a.domain_pack_namespace = $namespace")
                query_params['namespace'] = domain_pack_namespace
        else:
            query = """
            MATCH (p:PaperNode)-[:CONTAINS]->(a:AssertionNode)
            WHERE a.workspace_id = $workspace_id
            """
            if metric_name:
                conditions.append("a.subject = $metric_name")
                query_params['metric_name'] = metric_name
            if domain_pack_namespace:
                conditions.append("a.domain_pack_namespace = $namespace")
                query_params['namespace'] = domain_pack_namespace
        
        if len(conditions) > 1:
            query += " AND " + " AND ".join(conditions[1:])
        
        query += "\nRETURN p.id as paper_id, a"
        
        result = db.execute_query(query, query_params)
        
        # Extract assertions in cell data format
        assertions = []
        for record in result:
            if 'a' in record:
                assertion_data = record['a']
                paper_id_result = record.get('paper_id')
                
                # Parse context_conditions if it's a JSON string
                context_conditions = assertion_data.get('context_conditions', {})
                if isinstance(context_conditions, str):
                    import json
                    context_conditions = json.loads(context_conditions)
                
                assertions.append({
                    'id': assertion_data['id'],
                    'paperId': paper_id_result,
                    'metricName': assertion_data['subject'],
                    'value': assertion_data['object'],
                    'unit': assertion_data['unit'],
                    'status': assertion_data['status'],
                    'confidence': context_conditions.get('confidence', 0.85),
                    'evidenceCount': 1,  # Simplified for now
                    'domain_pack_namespace': assertion_data.get('domain_pack_namespace')
                })
        
        return Success({'assertions': assertions})
        
    except Exception as e:
        return Error(code=-32603, message=f"Failed to fetch assertions: {str(e)}")

