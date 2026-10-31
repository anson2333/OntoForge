"""
SSP JSON-RPC 2.0 Server Implementation
Handles Scientific Service Protocol methods.
"""

import functools
import base64
import json
import os
import re
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Optional
from datetime import datetime, timezone
from uuid import uuid4
from jsonrpcserver import method, Success, Error, serve, Result
from backend.database import get_db, NodeRepository, EdgeRepository
from backend.database.ontology_repository import OntologyRepository
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
from backend.services.pdf_ingestion_service import (
    commit_parsed_pdf,
    authorize_pdf_upload,
    load_domain_pack_config,
    paper_source_path,
    load_pdf_upload,
    parse_pdf_with_domain_pack,
    store_pdf_upload,
)
from backend.services import auth_service
from backend.services.coverage_analysis import analyze_workspace_coverage
from backend.services.comparability import compare_experiments
from backend.services.entity_resolution import EntityResolver
from backend.services.gap_analysis import analyze_gap_candidates
from backend.schemas.ontology import EntityMention, ExperimentRecord
from backend.services.auth_service import (
    AuthError,
    CODE_AUTH_REQUIRED,
    CODE_FORBIDDEN,
    ROLE_OWNER,
    authenticate as auth_authenticate,
    auth_required,
    authorize_workspace,
    create_session,
    get_current_identity,
    register_user,
    revoke_session,
    set_session_intent_branch,
    workspace_role,
)


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


def _authenticated(func):
    """Bind the request identity to ``owner_id`` and reject anonymous callers.

    The client-supplied ``owner_id`` is never trusted: it is overwritten with the
    authenticated user id, and a mismatch is reported as a permission error.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        identity = get_current_identity()
        requested_owner = kwargs.get("owner_id")
        if identity is None:
            if auth_required():
                raise AuthError(CODE_AUTH_REQUIRED, "Authentication required")
            return func(*args, **kwargs)
        if requested_owner is not None and requested_owner != identity.user_id:
            raise AuthError(
                CODE_FORBIDDEN,
                "owner_id does not match the authenticated user",
            )
        kwargs["owner_id"] = identity.user_id
        return func(*args, **kwargs)

    return wrapper


def _workspace_is_accessible(
    workspace: Dict[str, Any], owner_id: Optional[str] = None, write: bool = False
) -> bool:
    if not workspace:
        return False
    identity = get_current_identity()
    if identity is not None:
        role = workspace_role(workspace, identity)
        if role is None:
            return False
        if write and role not in {ROLE_OWNER, "editor"}:
            return False
        return True
    # Legacy/dev fallback when authentication is explicitly disabled.
    if auth_required():
        return False
    if owner_id is None:
        return True
    workspace_owner = workspace.get("owner_id")
    return workspace_owner is None or workspace_owner == owner_id


def _get_accessible_workspace(
    node_repo: NodeRepository,
    workspace_id: str,
    owner_id: Optional[str],
    write: bool = False,
) -> Optional[Dict[str, Any]]:
    workspace = node_repo.get_workspace_node(workspace_id)
    if not _workspace_is_accessible(workspace, owner_id, write=write):
        return None
    return workspace


def _authorize_workspace(workspace: Dict[str, Any], write: bool = False) -> None:
    """Raise a JsonRpcError-compatible AuthError when access is denied."""
    authorize_workspace(workspace, get_current_identity(), write=write)


def _require_identity():
    """Return the current identity or raise when authentication is required."""
    identity = get_current_identity()
    if identity is None and auth_required():
        raise AuthError(CODE_AUTH_REQUIRED, "Authentication required")
    return identity


def _authorize_evidence_node(db: Any, node_id: str, write: bool = False) -> None:
    """Authorize a paper/chunk/formula/assertion through its owning workspace."""
    if not auth_required():
        return
    records = db.execute_query(
        """
        MATCH (w:WorkspaceNode)-[:CONTAINS_PAPER]->(p:PaperNode)
        OPTIONAL MATCH (p)-[:CONTAINS]->(n)
        WITH w, p, n
        WHERE p.id = $node_id OR n.id = $node_id
        RETURN w
        LIMIT 1
        """,
        {"node_id": node_id},
    )
    if not records or "w" not in records[0]:
        raise AuthError(CODE_FORBIDDEN, "Node not found or not accessible")
    authorize_workspace(dict(records[0]["w"]), get_current_identity(), write=write)


_READ_ONLY_CYPHER_FORBIDDEN = (
    "CREATE",
    "MERGE",
    "DELETE",
    "DETACH",
    "SET",
    "REMOVE",
    "DROP",
    "LOAD",
    "CALL",
    "FOREACH",
)


def _ensure_read_only_cypher(query: str) -> None:
    """Reject Cypher statements that would mutate the graph."""
    normalized = query.upper()
    for keyword in _READ_ONLY_CYPHER_FORBIDDEN:
        if re.search(rf"\b{keyword}\b", normalized):
            raise AuthError(
                CODE_FORBIDDEN,
                f"Read-only query required: '{keyword}' is not allowed via sspQuery",
            )


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


@method
def authRegister(
    username: str,
    password: str,
    display_name: Optional[str] = None,
) -> Result:
    """Create a local account. Passwords are stored as PBKDF2 hashes."""
    try:
        user = register_user(username, password, display_name=display_name)
        return Success({"user": user})
    except AuthError:
        raise
    except Exception as e:
        return Error(code=-32603, message=f"Failed to register user: {str(e)}")


@method
def authLogin(username: str, password: str) -> Result:
    """Verify credentials and issue a session token."""
    try:
        user = auth_authenticate(username, password)
        session = create_session(user)
        return Success(session)
    except AuthError:
        raise
    except Exception as e:
        return Error(code=-32603, message=f"Failed to log in: {str(e)}")


@method
def authLogout() -> Result:
    """Revoke the current session token."""
    identity = get_current_identity()
    if identity is None or not identity.token:
        return Success({"logged_out": False})
    return Success({"logged_out": revoke_session(identity.token)})


@method
def authStatus() -> Result:
    """Return the identity bound to the current session."""
    identity = get_current_identity()
    if identity is None:
        return Success({"authenticated": False, "user": None})
    return Success(
        {
            "authenticated": True,
            "user": {
                "user_id": identity.user_id,
                "username": identity.username,
                "display_name": identity.display_name,
                "roles": list(identity.roles),
            },
        }
    )


@method
@_authenticated
def listWorkspaceMembers(workspace_id: str, owner_id: Optional[str] = None) -> Result:
    """List members and their roles for a workspace."""
    try:
        db = get_db()
        node_repo = NodeRepository(db)
        workspace = _get_accessible_workspace(node_repo, workspace_id, owner_id)
        if not workspace:
            raise AuthError(CODE_FORBIDDEN, "Workspace not found or not accessible")
        metadata = workspace.get("metadata") or {}
        members = dict(metadata.get("members") or {})
        result = []
        if workspace.get("owner_id"):
            owner = auth_service.get_user(workspace["owner_id"])
            result.append(
                {
                    "user_id": workspace["owner_id"],
                    "username": owner.get("username") if owner else None,
                    "display_name": owner.get("display_name") if owner else None,
                    "role": ROLE_OWNER,
                }
            )
        for user_id, role in members.items():
            user = auth_service.get_user(user_id)
            result.append(
                {
                    "user_id": user_id,
                    "username": user.get("username") if user else None,
                    "display_name": user.get("display_name") if user else None,
                    "role": role,
                }
            )
        return Success({"workspace_id": workspace_id, "members": result})
    except AuthError:
        raise
    except Exception as e:
        return Error(code=-32603, message=f"Failed to list workspace members: {str(e)}")


@method
@_authenticated
def addWorkspaceMember(
    workspace_id: str,
    user_id: Optional[str] = None,
    username: Optional[str] = None,
    role: str = "viewer",
    owner_id: Optional[str] = None,
) -> Result:
    """Grant a user read/write access to a workspace (owner only)."""
    try:
        db = get_db()
        node_repo = NodeRepository(db)
        workspace = _get_accessible_workspace(node_repo, workspace_id, owner_id)
        if not workspace:
            raise AuthError(CODE_FORBIDDEN, "Workspace not found or not accessible")
        identity = get_current_identity()
        if workspace_role(workspace, identity) != ROLE_OWNER:
            raise AuthError(CODE_FORBIDDEN, "Only the workspace owner can manage members")
        if not user_id and username:
            user = auth_service.find_user_by_username(username)
            user_id = user.get("user_id") if user else None
        if not user_id:
            raise AuthError(CODE_INVALID_REQUEST, "Unknown username or user_id")
        metadata = auth_service.add_workspace_member(workspace, user_id, role)
        node_repo.update_node(workspace_id, "WorkspaceNode", {"metadata": metadata})
        return Success(
            {"workspace_id": workspace_id, "user_id": user_id, "role": role}
        )
    except AuthError:
        raise
    except Exception as e:
        return Error(code=-32603, message=f"Failed to add workspace member: {str(e)}")


@method
@_authenticated
def removeWorkspaceMember(
    workspace_id: str, user_id: str, owner_id: Optional[str] = None
) -> Result:
    """Revoke a user's workspace access (owner only)."""
    try:
        db = get_db()
        node_repo = NodeRepository(db)
        workspace = _get_accessible_workspace(node_repo, workspace_id, owner_id)
        if not workspace:
            raise AuthError(CODE_FORBIDDEN, "Workspace not found or not accessible")
        identity = get_current_identity()
        if workspace_role(workspace, identity) != ROLE_OWNER:
            raise AuthError(CODE_FORBIDDEN, "Only the workspace owner can manage members")
        metadata = auth_service.remove_workspace_member(workspace, user_id)
        node_repo.update_node(workspace_id, "WorkspaceNode", {"metadata": metadata})
        return Success({"workspace_id": workspace_id, "user_id": user_id, "removed": True})
    except AuthError:
        raise
    except Exception as e:
        return Error(code=-32603, message=f"Failed to remove workspace member: {str(e)}")


@method
def getLLMStatus() -> Result:
    try:
        provider = get_default_provider()
        configured = provider.is_configured()
        from backend.services.llm_profiles import active_connection
        identity = get_current_identity()
        connection = active_connection(identity.user_id) if identity else None
        response = GetLLMStatusResponse(provider=provider.name, model=provider.config.model,
            enabled=provider.config.enabled, configured=configured, healthy=bool(configured and connection and connection.get("healthy")),
            message=connection["message"] if configured and connection else ("已配置，尚未验证连接" if configured else "尚未配置模型或 API Key"))
        return Success(response.model_dump())
    except Exception as e:
        return Error(code=-32603, message=f"Failed to get LLM status: {str(e)}")


def _profile_user():
    identity = get_current_identity()
    if identity is None:
        raise AuthError(CODE_AUTH_REQUIRED, "Sign in to manage model endpoints")
    return identity.user_id


@method
def listLLMProfiles() -> Result:
    from backend.services.llm_profiles import list_profiles
    return Success(list_profiles(_profile_user()))


@method
def listLLMPresets() -> Result:
    from backend.services.llm_presets import PRESETS
    _profile_user()
    return Success({"presets": PRESETS, "verified_on": "2026-10-29"})


@method
async def saveLLMProfile(profile: Dict[str, Any], activate: bool = False) -> Result:
    from backend.services.llm_profiles import ProfileInput, save_profile, draft_configuration, profile_configuration, record_connection
    from pydantic import ValidationError
    user = _profile_user()
    try:
        validated = ProfileInput.model_validate(profile)
        connection = await _check_model_configuration(draft_configuration(user, validated))
        if not connection["healthy"]:
            return Error(code=-32006, message="未保存或启用：" + connection["message"])
        saved = save_profile(user, validated, activate)
        record_connection(profile_configuration(user, saved["id"]), True, connection["message"])
        return Success({"profile": saved, "connection": connection})
    except ValidationError as exc:
        return Error(code=-32602, message="; ".join(f"{'.'.join(map(str, error['loc']))}: {error['msg']}" for error in exc.errors(include_input=False)))
    except ValueError as exc:
        return Error(code=-32004, message=str(exc))


@method
def activateLLMProfile(profile_id: Optional[str] = None) -> Result:
    from backend.services.llm_profiles import activate_profile
    user = _profile_user()
    try:
        return Success(activate_profile(user, profile_id))
    except ValueError as exc:
        return Error(code=-32004, message=str(exc))


@method
def deleteLLMProfile(profile_id: str) -> Result:
    from backend.services.llm_profiles import delete_profile
    user = _profile_user()
    try:
        return Success(delete_profile(user, profile_id))
    except ValueError as exc:
        return Error(code=-32004, message=str(exc))


async def _check_model_configuration(config):
    import time
    from backend.services.llm.base import provider_from_config, StructuredOutputRequest
    from backend.services.llm_errors import model_error
    started = time.perf_counter()
    provider = provider_from_config(config)
    if not provider.is_configured():
        return {"healthy": False, "seconds": 0, "message": "请填写对应厂商的 API Key 和模型名称"}
    try:
        test_limit = 1024 if config.provider == "anthropic" or config.vendor == "kimi" else 128
        provider = provider_from_config(config.model_copy(update={"max_output_tokens": min(config.max_output_tokens or test_limit, test_limit)}))
        result = await provider.invoke_structured(StructuredOutputRequest(
            system_prompt="You are testing API connectivity. Reply briefly.",
            user_prompt="Please reply: OK", response_schema_name="EndpointTest", metadata={"connection_probe": True},
            response_schema={"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"]}))
        healthy = bool((result.raw_text or "").strip())
        message = "连接验证成功，模型已正常回复" if healthy else "接口已响应，但模型没有返回文本；请检查模型或增加最大输出 tokens"
        provider.record_connection(healthy, message)
        return {"healthy": healthy, "message": message, "seconds": round(time.perf_counter() - started, 3),
                "usage": {key: value for key, value in result.usage.items() if isinstance(value, (int, float))}}
    except Exception as exc:
        error = model_error(exc)
        provider.record_connection(False, error["message"])
        return {"healthy": False, "seconds": round(time.perf_counter() - started, 3), "message": error["message"]}


@method
async def testLLMProfile(profile_id: str) -> Result:
    from backend.services.llm_profiles import profile_configuration
    user = _profile_user()
    try:
        return Success(await _check_model_configuration(profile_configuration(user, profile_id)))
    except ValueError:
        return Error(code=-32004, message="Profile not found or configuration invalid")


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
        identity = _require_identity()
        if identity is not None:
            # The authenticated identity always wins over client-supplied ids.
            user_id = identity.user_id
            owner_id = identity.user_id

        request = ParseUserIntentParams(
            workspace_id=workspace_id,
            user_id=user_id,
            message=message,
            owner_id=owner_id,
            intent_context=intent_context,
        )
        response = await parse_user_intent(request)
        return Success(response.model_dump())
    except AuthError:
        raise
    except Exception as e:
        return Error(code=-32603, message=f"Failed to parse user intent: {str(e)}")


@method
@_authenticated
def uploadPdf(
    file_name: str,
    content_base64: str,
    content_type: Optional[str] = "application/pdf",
    workspace_id: Optional[str] = None,
    owner_id: Optional[str] = None,
) -> Result:
    try:
        if workspace_id:
            db = get_db()
            workspace = _get_accessible_workspace(
                NodeRepository(db), workspace_id, owner_id, write=True
            )
            if not workspace:
                raise AuthError(CODE_FORBIDDEN, "Workspace not found or not accessible")
        request = UploadPdfParams(
            file_name=file_name,
            content_base64=content_base64,
            content_type=content_type,
            workspace_id=workspace_id,
            owner_id=owner_id,
        )
        response = store_pdf_upload(request)
        return Success(response.model_dump())
    except AuthError:
        raise
    except Exception as e:
        return Error(code=-32603, message=f"Failed to upload PDF: {str(e)}")


@method
@_authenticated
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
        identity = get_current_identity()
        db = get_db()
        workspace = _get_accessible_workspace(
            NodeRepository(db), workspace_id, owner_id, write=True
        )
        if not workspace:
            raise AuthError(CODE_FORBIDDEN, "Workspace not found or not accessible")
        if upload_id:
            authorize_pdf_upload(upload_id, workspace_id, identity.user_id if identity else None)
        if paper_uri:
            allow_local = os.getenv("ONTOFORGE_ALLOW_LOCAL_PAPER_URI", "false").lower() in {
                "1", "true", "yes", "on"
            }
            allowed_root = os.getenv("ONTOFORGE_LOCAL_PAPER_ROOT", "").strip()
            if not allow_local or not allowed_root:
                raise AuthError(CODE_FORBIDDEN, "Server-local paper_uri access is disabled")
            candidate = Path(paper_uri).expanduser().resolve()
            root = Path(allowed_root).expanduser().resolve()
            if candidate != root and root not in candidate.parents:
                raise AuthError(CODE_FORBIDDEN, "paper_uri is outside the allowed root")

        request = ParsePdfWithDomainPackParams(
            workspace_id=workspace_id,
            domain_pack_namespace=domain_pack_namespace,
            upload_id=upload_id,
            paper_uri=paper_uri,
            raw_text=raw_text,
            owner_id=identity.user_id if identity else None,
            intent_context=intent_context,
            parse_options=parse_options or {},
        )
        response = parse_pdf_with_domain_pack(request)
        return Success(response.model_dump())
    except AuthError:
        raise
    except Exception as e:
        return Error(code=-32603, message=f"Failed to parse PDF: {str(e)}")


@method
@_authenticated
def commitParsedPdf(
    workspace_id: str,
    domain_pack_namespace: str,
    upload_id: str,
    preview_id: str,
    owner_id: Optional[str] = None,
    parse_options: Optional[Dict[str, Any]] = None,
) -> Result:
    try:
        identity = get_current_identity()
        authorize_pdf_upload(upload_id, workspace_id, identity.user_id if identity else None)
        request = CommitParsedPdfParams(
            workspace_id=workspace_id,
            domain_pack_namespace=domain_pack_namespace,
            upload_id=upload_id,
            preview_id=preview_id,
            owner_id=identity.user_id if identity else None,
            parse_options=parse_options or {},
        )

        db = get_db()
        node_repo = NodeRepository(db)
        edge_repo = EdgeRepository(db)
        workspace = _get_accessible_workspace(node_repo, workspace_id, owner_id, write=True)
        if not workspace:
            raise AuthError(CODE_FORBIDDEN, "Workspace not found or not accessible")

        response = commit_parsed_pdf(request, node_repo=node_repo, edge_repo=edge_repo, workspace_exists=True)
        return Success(response.model_dump())
    except AuthError:
        raise
    except Exception as e:
        return Error(code=-32603, message=f"Failed to commit parsed PDF: {str(e)}")


@method
@_authenticated
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
@_authenticated
def getWorkspace(workspace_id: str, owner_id: Optional[str] = None) -> Result:
    try:
        db = get_db()
        node_repo = NodeRepository(db)
        workspace = _get_accessible_workspace(node_repo, workspace_id, owner_id)
        if not workspace:
            raise AuthError(CODE_FORBIDDEN, "Workspace not found or not accessible")
        return Success({"workspace": _serialize_workspace(workspace)})
    except AuthError:
        raise
    except Exception as e:
        return Error(code=-32603, message=f"Failed to fetch workspace: {str(e)}")


@method
@_authenticated
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
@_authenticated
def deleteWorkspace(workspace_id: str, owner_id: Optional[str] = None) -> Result:
    try:
        if not workspace_id:
            return Error(code=-32602, message="Workspace ID is required")

        db = get_db()
        node_repo = NodeRepository(db)
        
        # Check if workspace exists and is accessible
        workspace = _get_accessible_workspace(node_repo, workspace_id, owner_id, write=True)
        if not workspace:
            raise AuthError(CODE_FORBIDDEN, "Workspace not found or not accessible")
        identity = get_current_identity()
        if identity is not None and workspace_role(workspace, identity) != ROLE_OWNER:
            raise AuthError(CODE_FORBIDDEN, "Only the workspace owner can delete it")
        
        # Delete the workspace and all related data
        deleted = node_repo.delete_workspace_node(workspace_id)
        if not deleted:
            return Error(code=-32603, message="Failed to delete workspace")
        
        return Success({"deleted": True, "workspace_id": workspace_id})
    except AuthError:
        raise
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
        _require_identity()
        if os.getenv("ONTOFORGE_ENABLE_RAW_CYPHER", "false").lower() not in {
            "1", "true", "yes", "on"
        }:
            raise AuthError(
                CODE_FORBIDDEN,
            "Raw Cypher is disabled; use Read-only workspace-scoped query methods",
            )
        _ensure_read_only_cypher(request.query)

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

    except AuthError:
        raise
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
        identity = _require_identity()
        request = SSPLockNodeParams(**params)
        if identity is not None:
            request.locked_by = identity.user_id
        
        db = get_db()
        _authorize_evidence_node(db, request.node_id, write=True)
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
        
    except AuthError:
        raise
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
        identity = _require_identity()
        request = SSPUpdateNodeParams(**params)
        if identity is not None:
            request.modified_by = identity.user_id
        
        db = get_db()
        _authorize_evidence_node(db, request.node_id, write=True)
        node_repo = NodeRepository(db)
        
        # Get current node to increment modification count
        current_node = node_repo.get_node_by_id(request.node_id)
        if current_node is None:
            raise AuthError(CODE_FORBIDDEN, "Node not found or not accessible")
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
        
    except AuthError:
        raise
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
        identity = _require_identity()
        request = SSPVerifyNodeParams(**params)
        if identity is not None:
            request.verified_by = identity.user_id
        
        db = get_db()
        _authorize_evidence_node(db, request.node_id, write=True)
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
        
    except AuthError:
        raise
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
        identity = _require_identity()
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
            user_id=identity.user_id if identity else "current_user",
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
        
    except AuthError:
        raise
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
        identity = _require_identity()
        request = SSPCreateIntentBranchParams(**params)
        
        db = get_db()
        node_repo = NodeRepository(db)
        edge_repo = EdgeRepository(db)
        
        # Create IntentBranchNode
        branch_slug = re.sub(r"[^a-z0-9]+", "_", request.branch_name.lower()).strip("_")
        branch_id = f"intent_{branch_slug}_{uuid4().hex[:10]}"

        if request.inherit_from:
            parent = node_repo.get_intent_branch(request.inherit_from)
            if not parent or parent.get("user_id") != identity.user_id:
                raise AuthError(CODE_FORBIDDEN, "Parent intent branch is not accessible")
        
        branch_node = IntentBranchNode(
            id=branch_id,
            branch_name=request.branch_name,
            description=request.description,
            user_id=identity.user_id,
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
        
    except AuthError:
        raise
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
        identity = _require_identity()
        request = SSPSwitchIntentContextParams(**params)

        if not request.branch_id.strip():
            previous_branch_id = set_session_intent_branch(identity, None)
            return Success(
                SSPSwitchIntentContextResponse(
                    previous_branch_id=previous_branch_id,
                    current_branch_id="",
                    overrides_applied={},
                ).model_dump()
            )
        
        db = get_db()
        node_repo = NodeRepository(db)
        
        # Get intent branch
        branch = node_repo.get_intent_branch(request.branch_id)
        
        if not branch:
            return Error(code=-32602, message=f"Intent branch not found: {request.branch_id}")
        if branch.get("user_id") != identity.user_id:
            raise AuthError(CODE_FORBIDDEN, "Intent branch is not accessible")
        
        previous_branch_id = set_session_intent_branch(identity, request.branch_id)
        
        response = SSPSwitchIntentContextResponse(
            previous_branch_id=previous_branch_id,
            current_branch_id=request.branch_id,
            overrides_applied=branch.get("overrides", {})
        )
        
        return Success(response.model_dump())
        
    except AuthError:
        raise
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
        identity = _require_identity()
        request = SSPQueryByIntentParams(**params)
        
        db = get_db()
        node_repo = NodeRepository(db)
        
        # Get intent context if specified
        context_overrides = {}
        if request.intent_context:
            branch = node_repo.get_intent_branch(request.intent_context)
            if not branch or branch.get("user_id") != identity.user_id:
                raise AuthError(CODE_FORBIDDEN, "Intent branch is not accessible")
            context_overrides = branch.get("overrides", {})
            if isinstance(context_overrides, str):
                context_overrides = json.loads(context_overrides)

        accessible_workspaces = [
            workspace
            for workspace in node_repo.list_workspace_nodes()
            if _workspace_is_accessible(workspace, identity.user_id if identity else None)
        ]
        if request.workspace_id:
            accessible_workspaces = [
                workspace for workspace in accessible_workspaces
                if workspace.get("id") == request.workspace_id
            ]
        workspace_ids = [workspace["id"] for workspace in accessible_workspaces]
        if not workspace_ids:
            return Success(
                SSPQueryByIntentResponse(papers=[], summary="No accessible workspace matches the query scope").model_dump()
            )

        terms = [term.lower() for term in re.findall(r"[\w.-]+", request.query) if len(term) > 1]
        if not terms:
            return Error(code=-32602, message="Query must contain a searchable term")

        temporal_filter = context_overrides.get("temporal_filter", {})
        min_year = temporal_filter.get("min_year")
        max_year = temporal_filter.get("max_year")
        excluded_papers = context_overrides.get("excluded_papers", [])
        focus_subdomains = context_overrides.get("focus_subdomains", [])
        query = """
        MATCH (w:WorkspaceNode)-[:CONTAINS_PAPER]->(p:PaperNode)
        OPTIONAL MATCH (p)-[:BELONGS_TO]->(d:DomainNode)
        WHERE w.id IN $workspace_ids
          AND any(term IN $terms WHERE
              toLower(coalesce(p.title, '')) CONTAINS term OR
              toLower(coalesce(p.venue, '')) CONTAINS term OR
              any(author IN coalesce(p.authors, []) WHERE toLower(author) CONTAINS term))
          AND NOT p.id IN $excluded_papers
          AND ($min_year IS NULL OR p.year >= $min_year)
          AND ($max_year IS NULL OR p.year <= $max_year)
          AND (size($focus_subdomains) = 0 OR d.id IN $focus_subdomains)
        RETURN DISTINCT p
        ORDER BY p.year DESC, p.title ASC
        LIMIT 10
        """

        results = node_repo.execute_query(
            query,
            {
                "workspace_ids": workspace_ids,
                "terms": terms,
                "excluded_papers": excluded_papers,
                "min_year": min_year,
                "max_year": max_year,
                "focus_subdomains": focus_subdomains,
            },
        )
        
        papers = [record["p"] for record in results]
        
        response = SSPQueryByIntentResponse(
            papers=papers,
            summary=f"Found {len(papers)} papers matching '{request.query}' with intent context applied"
        )
        
        return Success(response.model_dump())
        
    except AuthError:
        raise
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
        identity = _require_identity()
        request = SSPSuggestReviewQueueParams(**params)
        
        db = get_db()
        node_repo = NodeRepository(db)
        workspace = _get_accessible_workspace(
            node_repo,
            request.workspace_id,
            identity.user_id if identity else None,
        )
        if workspace is None:
            raise AuthError(CODE_FORBIDDEN, "Workspace not found or not accessible")

        # Get unresolved conflicts
        query = """
        MATCH (a1:AssertionNode)-[c:CONTRADICTS]->(a2:AssertionNode)
        WHERE a1.workspace_id = $workspace_id
          AND a2.workspace_id = $workspace_id
          AND NOT EXISTS((a1)<-[:LOCKS]-(:HumanArbitratorNode))
        RETURN a1, a2, c
        LIMIT $limit
        """

        results = node_repo.execute_query(
            query,
            {"workspace_id": request.workspace_id, "limit": request.limit},
        )
        
        # Create ReviewItem for each conflict
        review_items = []
        for i, record in enumerate(results):
            assertion_a = dict(record["a1"])
            assertion_b = dict(record["a2"])
            conflict = dict(record["c"])
            relevance = 0.9 if request.strategy == "intent_aligned" else 0.75
            item = ReviewItem(
                item_id=conflict.get("conflict_id") or f"conflict_{i}",
                item_type="conflicting_assertions",
                reason=(
                    f"Conflicting values for {assertion_a.get('subject', 'the same metric')}: "
                    f"{assertion_a.get('object', 'unknown')} vs "
                    f"{assertion_b.get('object', 'unknown')}"
                ),
                intent_relevance=relevance,
                estimated_time="5 minutes",
                priority="high" if relevance >= 0.85 else "medium",
            )
            review_items.append(item)
        
        total_time = len(review_items) * 5  # 5 minutes per item
        
        response = SSPSuggestReviewQueueResponse(
            review_items=review_items,
            total_pending=len(review_items),
            estimated_total_time=f"{total_time} minutes"
        )
        
        return Success(response.model_dump())
        
    except AuthError:
        raise
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
        identity = _require_identity()
        request = SSPApplyIntentPatternParams(**params)

        workspace_id = request.scope.get("workspace_id")
        if not isinstance(workspace_id, str) or not workspace_id.strip():
            return Error(code=-32602, message="scope.workspace_id is required")
        if not request.dry_run:
            return Error(
                code=-32602,
                message=(
                    "Automatic conflict resolution requires explicit assertion selections; "
                    "preview the pattern with dry_run=true"
                ),
            )

        db = get_db()
        node_repo = NodeRepository(db)
        edge_repo = EdgeRepository(db)
        workspace = _get_accessible_workspace(
            node_repo,
            workspace_id,
            identity.user_id if identity else None,
        )
        if workspace is None:
            raise AuthError(CODE_FORBIDDEN, "Workspace not found or not accessible")

        learning_engine = IntentLearningEngine(node_repo, edge_repo)
        profile = learning_engine.build_user_intent_profile_sync(
            identity.user_id if identity else "current_user"
        )
        pattern = next(
            (item for item in profile.learned_patterns if item.pattern_id == request.pattern_id),
            None,
        )
        if pattern is None:
            return Error(code=-32602, message=f"Intent pattern not found: {request.pattern_id}")

        matches = node_repo.execute_query(
            """
            MATCH (a1:AssertionNode)-[c:CONTRADICTS]->(a2:AssertionNode)
            WHERE a1.workspace_id = $workspace_id
              AND a2.workspace_id = $workspace_id
              AND NOT EXISTS((a1)<-[:LOCKS]-(:HumanArbitratorNode))
              AND NOT EXISTS((a2)<-[:LOCKS]-(:HumanArbitratorNode))
            RETURN count(c) AS conflict_count
            """,
            {"workspace_id": workspace_id},
        )
        conflict_count = int(matches[0]["conflict_count"]) if matches else 0
        pattern_confidence = pattern.confidence
        
        response = SSPApplyIntentPatternResponse(
            # In dry-run mode these fields report the projected impact.
            conflicts_resolved=conflict_count,
            assertions_locked=conflict_count,
            pattern_confidence=pattern_confidence,
            user_review_recommended=pattern_confidence < 0.8
        )
        
        return Success(response.model_dump())

    except AuthError:
        raise
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
        identity = _require_identity()
        if identity is not None:
            user_id = identity.user_id
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
        
    except AuthError:
        raise
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
@_authenticated
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
            raise AuthError(CODE_FORBIDDEN, "Workspace not found or not accessible")
        
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
        
    except AuthError:
        raise
    except Exception as e:
        return Error(code=-32603, message=f"Failed to fetch papers: {str(e)}")


@method
@_authenticated
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
            raise AuthError(CODE_FORBIDDEN, "Workspace not found or not accessible")
        
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
        
        query += "\nOPTIONAL MATCH (e)-[:EVIDENCED_BY]->(a)\nRETURN p.id as paper_id, a, count(DISTINCT e) as evidence_count"
        
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
                    'evidenceCount': record.get('evidence_count', 0),
                    'domain_pack_namespace': assertion_data.get('domain_pack_namespace')
                })
        
        return Success({'assertions': assertions})
        
    except AuthError:
        raise
    except Exception as e:
        return Error(code=-32603, message=f"Failed to fetch assertions: {str(e)}")


@method
@_authenticated
def resolveEntityMentions(
    workspace_id: str,
    domain_pack_namespace: str,
    mentions: list[dict[str, Any]],
    persist: bool = True,
    owner_id: Optional[str] = None,
) -> Result:
    """Resolve typed mentions with auditable decisions; fuzzy matches never auto-merge."""
    try:
        db = get_db()
        node_repo = NodeRepository(db)
        workspace = _get_accessible_workspace(node_repo, workspace_id, owner_id, write=persist)
        if not workspace:
            raise AuthError(CODE_FORBIDDEN, "Workspace not found or not accessible")
        config = load_domain_pack_config(domain_pack_namespace)
        if config is None:
            return Error(code=-32602, message="Unknown domain pack")
        resolver = EntityResolver(config)
        decisions = []
        repository = OntologyRepository(db)
        with db.transaction() if persist else _null_context():
            for payload in mentions[:500]:
                mention = EntityMention(
                    **{key: value for key, value in payload.items() if key not in {"workspace_id", "domain_id"}},
                    workspace_id=workspace_id,
                    domain_id=config.domain.id,
                )
                decision = resolver.resolve_mention(mention)
                decisions.append(decision)
                if persist:
                    if decision.selected_entity_id and decision.candidates:
                        candidate = next(
                            item for item in decision.candidates
                            if item.entity_id == decision.selected_entity_id
                        )
                        repository.merge_canonical_entity(
                            entity_id=candidate.entity_id, entity_type=candidate.entity_type,
                            workspace_id=workspace_id, domain_id=config.domain.id,
                            canonical_name=candidate.canonical_name, aliases=[],
                        )
                    repository.persist_resolution(decision)
        return Success({"decisions": [item.model_dump(mode="json") for item in decisions]})
    except AuthError:
        raise
    except Exception as exc:
        return Error(code=-32602, message=f"Entity resolution failed: {exc}")


@contextmanager
def _null_context():
    yield


@method
@_authenticated
def getExperiments(
    workspace_id: str,
    experiment_ids: Optional[list[str]] = None,
    model_variant_id: Optional[str] = None,
    limit: int = 100,
    owner_id: Optional[str] = None,
) -> Result:
    try:
        db = get_db()
        workspace = _get_accessible_workspace(NodeRepository(db), workspace_id, owner_id)
        if not workspace:
            raise AuthError(CODE_FORBIDDEN, "Workspace not found or not accessible")
        experiments = OntologyRepository(db).get_experiments(
            workspace_id, experiment_ids=experiment_ids,
            model_variant_id=model_variant_id, limit=limit,
        )
        return Success({"experiments": experiments, "count": len(experiments)})
    except AuthError:
        raise
    except Exception as exc:
        return Error(code=-32603, message=f"Failed to fetch experiments: {exc}")


@method
@_authenticated
def compareExperiments(
    workspace_id: str,
    experiment_ids: list[str],
    policy_id: str,
    owner_id: Optional[str] = None,
) -> Result:
    try:
        if len(experiment_ids) != 2 or experiment_ids[0] == experiment_ids[1]:
            return Error(code=-32602, message="Exactly two distinct experiment_ids are required")
        db = get_db()
        workspace = _get_accessible_workspace(NodeRepository(db), workspace_id, owner_id)
        if not workspace:
            raise AuthError(CODE_FORBIDDEN, "Workspace not found or not accessible")
        records = OntologyRepository(db).get_experiments(
            workspace_id, experiment_ids=experiment_ids, limit=2,
        )
        indexed = {item["experiment"]["id"]: item["experiment"] for item in records}
        if set(experiment_ids) != set(indexed):
            return Error(code=-32004, message="Experiment not found in this workspace")
        result = compare_experiments(
            ExperimentRecord(**indexed[experiment_ids[0]]),
            ExperimentRecord(**indexed[experiment_ids[1]]),
            policy_id,
        )
        return Success({"comparison": result.model_dump(mode="json")})
    except AuthError:
        raise
    except ValueError as exc:
        return Error(code=-32602, message=str(exc))
    except Exception as exc:
        return Error(code=-32603, message=f"Comparison failed: {exc}")


@method
@_authenticated
def getEntitySubgraph(
    workspace_id: str,
    entity_id: str,
    limit: int = 100,
    owner_id: Optional[str] = None,
) -> Result:
    try:
        db = get_db()
        workspace = _get_accessible_workspace(NodeRepository(db), workspace_id, owner_id)
        if not workspace:
            raise AuthError(CODE_FORBIDDEN, "Workspace not found or not accessible")
        graph = OntologyRepository(db).get_entity_subgraph(workspace_id, entity_id, limit)
        if graph["root"] is None:
            return Error(code=-32004, message="Entity not found in this workspace")
        return Success({"subgraph": graph})
    except AuthError:
        raise
    except Exception as exc:
        return Error(code=-32603, message=f"Subgraph query failed: {exc}")


@method
@_authenticated
def reviewResolution(
    workspace_id: str,
    decision_id: str,
    action: str,
    reason: str,
    owner_id: Optional[str] = None,
) -> Result:
    """Confirm or retract a mapping without deleting its mention or provenance."""
    try:
        if action not in {"confirm", "retract"}:
            return Error(code=-32602, message="action must be confirm or retract")
        if not reason.strip():
            return Error(code=-32602, message="A review reason is required")
        identity = _require_identity()
        db = get_db()
        workspace = _get_accessible_workspace(NodeRepository(db), workspace_id, owner_id, write=True)
        if not workspace:
            raise AuthError(CODE_FORBIDDEN, "Workspace not found or not writable")
        event_id = f"review_{uuid4().hex}"
        now = datetime.now(timezone.utc).isoformat()
        records = db.execute_query(
            """
            MATCH (d:ResolutionDecision {id: $decision_id, workspace_id: $workspace_id})
            SET d.active = $active, d.reviewed_by = $actor_id
            CREATE (event:ReviewEvent {
              id: $event_id, workspace_id: $workspace_id, actor_id: $actor_id,
              action: $action, reason: $reason, created_at: $created_at
            })-[:REVIEWS]->(d)
            RETURN properties(d) AS decision, properties(event) AS event
            """,
            {
                "decision_id": decision_id, "workspace_id": workspace_id,
                "active": action == "confirm", "actor_id": identity.user_id if identity else "local",
                "event_id": event_id, "action": action, "reason": reason.strip(), "created_at": now,
            },
        )
        if not records:
            return Error(code=-32004, message="Resolution decision not found")
        return Success({"decision": records[0]["decision"], "review_event": records[0]["event"]})
    except AuthError:
        raise
    except Exception as exc:
        return Error(code=-32603, message=f"Resolution review failed: {exc}")


@method
@_authenticated
def analyzeResearchGaps(
    workspace_id: str,
    include_machine_checked: bool = False,
    limit: int = 50,
    owner_id: Optional[str] = None,
) -> Result:
    try:
        db = get_db()
        workspace = _get_accessible_workspace(NodeRepository(db), workspace_id, owner_id)
        if not workspace:
            raise AuthError(CODE_FORBIDDEN, "Workspace not found or not accessible")
        trusted = {"human_verified"}
        if include_machine_checked:
            trusted.add("machine_checked")
        report = analyze_gap_candidates(
            OntologyRepository(db).get_gap_observations(workspace_id),
            workspace_id=workspace_id, trusted_states=frozenset(trusted),
            limit=max(0, min(int(limit), 200)),
        )
        return Success({"analysis": report})
    except AuthError:
        raise
    except Exception as exc:
        return Error(code=-32603, message=f"Research-gap analysis failed: {exc}")


@method
@_authenticated
def getCoverageAnalysis(
    workspace_id: str,
    domain_pack_namespace: Optional[str] = None,
    methods: Optional[list] = None,
    scenarios: Optional[list] = None,
    metrics: Optional[list] = None,
    gap_limit: int = 20,
    owner_id: Optional[str] = None,
) -> Result:
    """Report method × scenario × metric coverage and ranked gap candidates."""
    try:
        db = get_db()
        node_repo = NodeRepository(db)
        workspace = _get_accessible_workspace(node_repo, workspace_id, owner_id)
        if not workspace:
            raise AuthError(CODE_FORBIDDEN, "Workspace not found or not accessible")

        report = analyze_workspace_coverage(
            db,
            workspace_id,
            domain_pack_namespace,
            methods=methods,
            scenarios=scenarios,
            metrics=metrics,
            gap_limit=max(0, min(int(gap_limit), 200)),
        )
        return Success({"coverage": report})

    except AuthError:
        raise
    except Exception as e:
        return Error(code=-32603, message=f"Failed to analyze coverage: {str(e)}")


@method
@_authenticated
def getGapCandidates(
    workspace_id: str,
    domain_pack_namespace: Optional[str] = None,
    methods: Optional[list] = None,
    scenarios: Optional[list] = None,
    metrics: Optional[list] = None,
    limit: int = 20,
    owner_id: Optional[str] = None,
) -> Result:
    """Return only the ranked candidate gaps for a workspace."""
    try:
        db = get_db()
        node_repo = NodeRepository(db)
        workspace = _get_accessible_workspace(node_repo, workspace_id, owner_id)
        if not workspace:
            raise AuthError(CODE_FORBIDDEN, "Workspace not found or not accessible")

        report = analyze_workspace_coverage(
            db,
            workspace_id,
            domain_pack_namespace,
            methods=methods,
            scenarios=scenarios,
            metrics=metrics,
            gap_limit=max(0, min(int(limit), 200)),
        )
        return Success(
            {
                "gaps": report["gaps"],
                "gap_count": report["gap_count"],
                "coverage": report["coverage"],
            }
        )

    except AuthError:
        raise
    except Exception as e:
        return Error(code=-32603, message=f"Failed to compute gaps: {str(e)}")


@method
@_authenticated
def getPaperSource(workspace_id: str, paper_id: str, owner_id: Optional[str] = None) -> Result:
    """Download the preserved original; workspace authorization is mandatory."""
    db = get_db()
    repo = NodeRepository(db)
    if not _get_accessible_workspace(repo, workspace_id, owner_id):
        raise AuthError(CODE_FORBIDDEN, "Workspace not accessible")
    paper = repo.get_node_by_id(paper_id, "PaperNode")
    if not paper or paper.get("workspace_id") != workspace_id:
        raise AuthError(CODE_FORBIDDEN, "Paper not accessible")
    try:
        path = paper_source_path(paper_id)
        if not path.exists():
            return Error(code=-32004, message="Original PDF unavailable for this legacy or demo paper")
        return Success({"file_name": f"{paper_id}.pdf", "content_type": "application/pdf",
                        "content_base64": base64.b64encode(path.read_bytes()).decode("ascii")})
    except ValueError as exc:
        return Error(code=-32004, message=str(exc))


@method
@_authenticated
def getEvidence(
    workspace_id: str,
    paper_id: str,
    metric_name: str,
    owner_id: Optional[str] = None,
) -> Result:
    """Return the chunks/formulas that support a paper's assertion for a metric."""
    try:
        db = get_db()
        node_repo = NodeRepository(db)
        workspace = _get_accessible_workspace(node_repo, workspace_id, owner_id)
        if not workspace:
            raise AuthError(CODE_FORBIDDEN, "Workspace not found or not accessible")

        suffix = metric_name.rsplit(":", 1)[-1]
        query = """
        MATCH (p:PaperNode {id: $paper_id})-[:CONTAINS]->(a:AssertionNode)
        WHERE a.workspace_id = $workspace_id
          AND (a.subject = $metric_name OR a.subject ENDS WITH $suffix)
        OPTIONAL MATCH (e)-[r:EVIDENCED_BY]->(a)
        RETURN a.id AS assertion_id,
               a.object AS value,
               a.unit AS unit,
               a.status AS status,
               a.context_conditions AS context_conditions,
               e.id AS evidence_id,
               labels(e) AS labels,
               e.raw_text AS raw_text,
               e.latex_string AS latex_string,
               e.bounding_box AS bounding_box,
               e.verification_status AS verification_status,
               e.modification_count AS modification_count,
               e.last_modified_at AS last_modified_at,
               r.confidence_score AS confidence
        """
        records = db.execute_query(
            query,
            {
                "workspace_id": workspace_id,
                "paper_id": paper_id,
                "metric_name": metric_name,
                "suffix": suffix,
            },
        )

        evidence: list[dict] = []
        seen: set[str] = set()
        assertion_meta: Optional[dict] = None
        for record in records:
            if assertion_meta is None:
                context = record.get("context_conditions")
                if isinstance(context, str):
                    try:
                        context = json.loads(context)
                    except json.JSONDecodeError:
                        context = {}
                assertion_meta = {
                    "assertion_id": record.get("assertion_id"),
                    "value": record.get("value"),
                    "unit": record.get("unit"),
                    "status": record.get("status"),
                    "confidence": (context or {}).get("confidence", 0.0),
                }

            evidence_id = record.get("evidence_id")
            if not evidence_id or evidence_id in seen:
                continue
            seen.add(evidence_id)

            labels = record.get("labels") or []
            evidence_type = "formula" if "FormulaNode" in labels else "chunk"
            bounding_box = record.get("bounding_box")
            if isinstance(bounding_box, str):
                try:
                    bounding_box = json.loads(bounding_box)
                except json.JSONDecodeError:
                    bounding_box = {}
            evidence.append(
                {
                    "id": evidence_id,
                    "type": evidence_type,
                    "text": record.get("latex_string") or record.get("raw_text") or "",
                    "confidence": record.get("confidence") or 0.0,
                    "bounding_box": bounding_box or {},
                    "verification_status": record.get("verification_status") or "raw",
                    "modification_count": record.get("modification_count") or 0,
                    "last_modified_at": record.get("last_modified_at"),
                }
            )

        if assertion_meta is None:
            return Success({"evidence": [], "assertion": None})
        return Success({"evidence": evidence, "assertion": assertion_meta})

    except AuthError:
        raise
    except Exception as e:
        return Error(code=-32603, message=f"Failed to fetch evidence: {str(e)}")


@method
@_authenticated
def listDomainPacks(owner_id: Optional[str] = None) -> Result:
    """List domain pack configurations available on the backend."""
    try:
        loader = DomainPackLoader()
        base_dir = Path(__file__).resolve().parents[1]
        candidates = [base_dir / "config" / "domain-pack.yaml"]
        configs_dir = base_dir / "configs"
        if configs_dir.exists():
            candidates.extend(sorted(configs_dir.glob("*.yaml")))
            candidates.extend(sorted(configs_dir.glob("*.yml")))

        packs: list[dict] = []
        seen_namespaces: set[str] = set()
        for candidate in candidates:
            if not candidate.exists():
                continue
            try:
                config = loader.load(candidate)
            except Exception as exc:
                print(f"⚠️  Skipping domain pack {candidate.name}: {exc}")
                continue
            namespace = config.domain.id.split(".")[-1]
            if namespace in seen_namespaces:
                continue
            seen_namespaces.add(namespace)
            packs.append(
                {
                    "namespace": namespace,
                    "source": candidate.name,
                    "config": config.model_dump(),
                }
            )

        return Success({"domain_packs": packs})

    except Exception as e:
        return Error(code=-32603, message=f"Failed to list domain packs: {str(e)}")

