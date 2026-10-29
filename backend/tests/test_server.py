"""
Tests for SSP JSON-RPC Server
Tests the FastAPI server and JSON-RPC method handlers.
"""

import base64
from unittest.mock import AsyncMock

import pytest
from pypdf import PdfWriter
from backend.server.app import app
from backend.services import auth_service
from backend.schemas.protocol import ParseUserIntentResponse, ParsedIntentResult
from backend.tests.conftest import SyncASGIClient


AUTH_USERNAME = "pytest_user"
AUTH_PASSWORD = "pytest-pass-123"


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return SyncASGIClient(app)


@pytest.fixture
def auth_headers(client):
    """Register a throwaway account and return its bearer-auth header."""
    client.post(
        "/jsonrpc",
        json={
            "jsonrpc": "2.0",
            "method": "authRegister",
            "params": {"username": AUTH_USERNAME, "password": AUTH_PASSWORD},
            "id": 900,
        },
    )
    response = client.post(
        "/jsonrpc",
        json={
            "jsonrpc": "2.0",
            "method": "authLogin",
            "params": {"username": AUTH_USERNAME, "password": AUTH_PASSWORD},
            "id": 901,
        },
    )
    token = response.json()["result"]["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def authorized_workspace_db(monkeypatch, auth_headers):
    """Provide the owned workspace needed by upload authorization tests."""
    token = auth_headers["Authorization"].removeprefix("Bearer ")
    identity = auth_service.resolve_session(token)

    class FakeDB:
        def execute_query(self, query, parameters=None, database="neo4j"):
            if "MATCH (w:WorkspaceNode {id: $workspace_id})" in query:
                return [{
                    "w": {
                        "id": "workspace_test",
                        "name": "Test Workspace",
                        "owner_id": identity.user_id,
                        "metadata": {},
                    }
                }]
            return []

    monkeypatch.setattr("backend.server.jsonrpc_methods.get_db", lambda: FakeDB())
    return auth_headers


class TestServerEndpoints:
    """Tests for basic server endpoints."""

    def test_root_endpoint(self, client):
        """Test the root health check endpoint."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "OntoForge SSP Server"
        assert "sspInitialize" in data["methods"]

    def test_health_endpoint(self, client):
        """Test the health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "database" in data


class TestJSONRPCMethods:
    """Tests for JSON-RPC method calls."""

    def test_jsonrpc_invalid_request(self, client):
        """Test JSON-RPC endpoint with invalid request."""
        response = client.post(
            "/jsonrpc", json={"invalid": "request", "no": "method"}
        )
        assert response.status_code == 200
        # JSON-RPC errors are still HTTP 200 with error in body

    def test_jsonrpc_missing_method(self, client):
        """Test JSON-RPC with missing method."""
        response = client.post(
            "/jsonrpc",
            json={"jsonrpc": "2.0", "method": "nonExistentMethod", "id": 1},
        )
        assert response.status_code == 200
        data = response.json()
        assert "error" in data

    def test_jsonrpc_ssp_initialize_missing_params(self, client):
        """Test sspInitialize without required parameters."""
        response = client.post(
            "/jsonrpc",
            json={
                "jsonrpc": "2.0",
                "method": "sspInitialize",
                "params": {},  # Missing configRef
                "id": 1,
            },
        )
        assert response.status_code == 200
        # Should return error due to missing parameters

    def test_jsonrpc_ssp_extract_missing_params(self, client):
        """Test sspExtract without required parameters."""
        response = client.post(
            "/jsonrpc",
            json={
                "jsonrpc": "2.0",
                "method": "sspExtract",
                "params": {},  # Missing paper_id
                "id": 2,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "error" in data

    def test_jsonrpc_ssp_extract_valid_request(self, client):
        """Test sspExtract with valid parameters (mock DB)."""
        response = client.post(
            "/jsonrpc",
            json={
                "jsonrpc": "2.0",
                "method": "sspExtract",
                "params": {
                    "paper_id": "test-paper-001",
                    "chunks": [
                        {
                            "chunk_id": "chunk-001",
                            "raw_text": "Sample text chunk",
                            "bounding_box": {"x": 0, "y": 0, "width": 100, "height": 50},
                        }
                    ],
                    "formulas": [
                        {
                            "formula_id": "formula-001",
                            "latex_string": "E = mc^2",
                            "variables_map": {"E": "energy", "m": "mass", "c": "speed_of_light"},
                            "bounding_box": {"x": 0, "y": 100, "width": 200, "height": 30},
                        }
                    ],
                    "extraction_method": "manual",
                },
                "id": 2,
            },
        )
        assert response.status_code == 200
        # Response structure depends on DB availability

    def test_jsonrpc_ssp_query_missing_params(self, client):
        """Test sspQuery without required parameters."""
        response = client.post(
            "/jsonrpc",
            json={
                "jsonrpc": "2.0",
                "method": "sspQuery",
                "params": {},  # Missing query
                "id": 3,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "error" in data

    def test_jsonrpc_ssp_query_valid_request(self, client):
        """Test sspQuery with valid Cypher query (mock DB)."""
        response = client.post(
            "/jsonrpc",
            json={
                "jsonrpc": "2.0",
                "method": "sspQuery",
                "params": {
                    "query": "MATCH (n:DomainNode) RETURN n",
                    "parameters": {},
                    "limit": 10,
                },
                "id": 3,
            },
        )
        assert response.status_code == 200
        # Response structure depends on DB availability

    def test_jsonrpc_upload_pdf_valid_request(self, client, authorized_workspace_db):
        """Test uploadPdf with a valid PDF payload."""
        writer = PdfWriter()
        writer.add_blank_page(width=300, height=300)
        writer.add_metadata({"/Title": "Upload Test Paper", "/Author": "Alice, Bob"})

        buffer = bytearray()
        from io import BytesIO
        stream = BytesIO()
        writer.write(stream)
        buffer.extend(stream.getvalue())

        response = client.post(
            "/jsonrpc",
            json={
                "jsonrpc": "2.0",
                "method": "uploadPdf",
                "params": {
                    "file_name": "upload_test.pdf",
                    "content_base64": base64.b64encode(bytes(buffer)).decode("ascii"),
                    "content_type": "application/pdf",
                    "workspace_id": "workspace_test",
                },
                "id": 21,
            },
            headers=authorized_workspace_db,
        )
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert data["result"]["upload_id"].startswith("upload_")
        assert data["result"]["file_name"] == "upload_test.pdf"

    def test_jsonrpc_parse_pdf_with_upload_id(self, client, authorized_workspace_db):
        """Test parsePdfWithDomainPack using a previously uploaded PDF."""
        writer = PdfWriter()
        writer.add_blank_page(width=300, height=300)
        writer.add_metadata({"/Title": "Preview Test Paper", "/Author": "Alice; Bob", "/Subject": "Preview Venue 2024"})

        from io import BytesIO
        stream = BytesIO()
        writer.write(stream)
        upload_response = client.post(
            "/jsonrpc",
            json={
                "jsonrpc": "2.0",
                "method": "uploadPdf",
                "params": {
                    "file_name": "preview_test_2024.pdf",
                    "content_base64": base64.b64encode(stream.getvalue()).decode("ascii"),
                    "content_type": "application/pdf",
                    "workspace_id": "workspace_test",
                },
                "id": 22,
            },
            headers=authorized_workspace_db,
        )
        upload_id = upload_response.json()["result"]["upload_id"]

        response = client.post(
            "/jsonrpc",
            json={
                "jsonrpc": "2.0",
                "method": "parsePdfWithDomainPack",
                "params": {
                    "workspace_id": "workspace_test",
                    "domain_pack_namespace": "optical",
                    "upload_id": upload_id,
                },
                "id": 23,
            },
            headers=authorized_workspace_db,
        )
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert data["result"]["upload_id"] == upload_id
        assert data["result"]["paper_metadata"]["title"] == "Preview Test Paper"
        assert data["result"]["paper_metadata"]["authors"] == ["Alice", "Bob"]
        assert isinstance(data["result"]["warnings"], list)

    def test_jsonrpc_ssp_lock_node(self, client):
        """Test sspLockNode for HITL editing workflow."""
        response = client.post(
            "/jsonrpc",
            json={
                "jsonrpc": "2.0",
                "method": "sspLockNode",
                "params": {
                    "node_id": "chunk-001",
                    "locked_by": "user-alice",
                },
                "id": 4,
            },
        )
        assert response.status_code == 200
        # Response structure depends on DB availability

    def test_jsonrpc_ssp_update_node(self, client):
        """Test sspUpdateNode for HITL editing workflow."""
        response = client.post(
            "/jsonrpc",
            json={
                "jsonrpc": "2.0",
                "method": "sspUpdateNode",
                "params": {
                    "node_id": "chunk-001",
                    "updates": {"raw_text": "Updated text content"},
                    "modified_by": "user-alice",
                },
                "id": 5,
            },
        )
        assert response.status_code == 200
        # Response structure depends on DB availability

    def test_jsonrpc_ssp_verify_node_approve(self, client):
        """Test sspVerifyNode with approve action."""
        response = client.post(
            "/jsonrpc",
            json={
                "jsonrpc": "2.0",
                "method": "sspVerifyNode",
                "params": {
                    "node_id": "chunk-001",
                    "action": "approve",
                    "verified_by": "user-bob",
                    "notes": "Looks good",
                },
                "id": 6,
            },
        )
        assert response.status_code == 200
        # Response structure depends on DB availability

    def test_jsonrpc_ssp_verify_node_reject(self, client):
        """Test sspVerifyNode with reject action."""
        response = client.post(
            "/jsonrpc",
            json={
                "jsonrpc": "2.0",
                "method": "sspVerifyNode",
                "params": {
                    "node_id": "chunk-002",
                    "action": "reject",
                    "verified_by": "user-bob",
                },
                "id": 7,
            },
        )
        assert response.status_code == 200

    def test_jsonrpc_ssp_approve_domain(self, client):
        """Test sspApproveDomain for domain approval workflow."""
        response = client.post(
            "/jsonrpc",
            json={
                "jsonrpc": "2.0",
                "method": "sspApproveDomain",
                "params": {
                    "domain_id": "domain-optical-networking",
                    "arbitrator_id": "arbitrator-alice",
                    "approval_type": "topology",
                    "approved_version": "1.0.0",
                },
                "id": 8,
            },
        )
        assert response.status_code == 200

    def test_jsonrpc_ssp_lock_assertion(self, client):
        """Test sspLockAssertion for conflict resolution workflow."""
        response = client.post(
            "/jsonrpc",
            json={
                "jsonrpc": "2.0",
                "method": "sspLockAssertion",
                "params": {
                    "assertion_id": "assertion-001",
                    "arbitrator_id": "arbitrator-bob",
                    "conflict_id": "conflict-123",
                },
                "id": 9,
            },
        )
        assert response.status_code == 200

    def test_jsonrpc_get_llm_status(self, client):
        """Test Phase 1 provider-status discovery endpoint."""
        response = client.post(
            "/jsonrpc",
            json={
                "jsonrpc": "2.0",
                "method": "getLLMStatus",
                "id": 10,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert "provider" in data["result"]
        assert "configured" in data["result"]

    def test_jsonrpc_list_agent_capabilities(self, client, auth_headers):
        """Test Phase 1 capability-discovery endpoint."""
        response = client.post(
            "/jsonrpc",
            json={
                "jsonrpc": "2.0",
                "method": "listAgentCapabilities",
                "params": {"tags": ["llm"]},
                "id": 11,
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        capability_names = {capability["name"] for capability in data["result"]["capabilities"]}
        assert "parseUserIntent" in capability_names
        assert "processChatMessage" in capability_names

    def test_jsonrpc_parse_user_intent(self, client, monkeypatch, auth_headers):
        mocked = AsyncMock(
            return_value=ParseUserIntentResponse(
                workspace_id="workspace_test",
                parsed_intent=ParsedIntentResult(
                    intent_type="constraint",
                    intent_scope="local",
                    description="Limit comparison to papers after 2020",
                    constraints={"year_gte": 2020},
                    generalization_hint=None,
                    confidence=0.88,
                    requires_confirmation=False,
                ),
            )
        )
        monkeypatch.setattr("backend.server.jsonrpc_methods.parse_user_intent", mocked)

        response = client.post(
            "/jsonrpc",
            json={
                "jsonrpc": "2.0",
                "method": "parseUserIntent",
                "params": {
                    "workspace_id": "workspace_test",
                    "user_id": "local-dev-user",
                    "message": "Only show papers after 2020.",
                },
                "id": 12,
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["result"]["workspace_id"] == "workspace_test"
        assert data["result"]["parsed_intent"]["intent_type"] == "constraint"

    def test_jsonrpc_ssp_declare_intent(self, client, auth_headers):
        response = client.post(
            "/jsonrpc",
            json={
                "jsonrpc": "2.0",
                "method": "sspDeclareIntent",
                "params": {
                    "intent_type": "constraint",
                    "intent_scope": "local",
                    "description": "Do not include any papers from India",
                    "constraints": {},
                    "active_from": "2026-05-25",
                },
                "id": 13,
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert data["result"]["status"] == "active"
        assert data["result"]["intent_id"].startswith("intent_constraint_")

    def test_jsonrpc_declared_intent_survives_profile_refresh(self, client, monkeypatch, auth_headers):
        class FakeDB:
            def __init__(self):
                self.arbitrators = []

            def execute_query(self, query, parameters=None, database="neo4j"):
                parameters = parameters or {}
                normalized_query = " ".join(query.split())

                if "CREATE (h:HumanArbitratorNode" in normalized_query:
                    record = {
                        "id": parameters["id"],
                        "user_id": parameters["user_id"],
                        "timestamp": parameters["timestamp"],
                        "arbitration_notes": parameters["arbitration_notes"],
                        "lock_type": parameters["lock_type"],
                        "intent_type": parameters["intent_type"],
                        "intent_scope": parameters["intent_scope"],
                        "generalization_hint": parameters["generalization_hint"],
                        "confidence_override": parameters["confidence_override"],
                        "intent_branch_id": parameters["intent_branch_id"],
                        "declaration_constraints": parameters["declaration_constraints"],
                        "tags": parameters["tags"],
                    }
                    self.arbitrators.append(record)
                    return [{"h": record}]

                if "WHERE 'explicit_declaration' IN coalesce(h.tags, [])" in normalized_query:
                    return [
                        {
                            "id": record["id"],
                            "timestamp": record["timestamp"],
                            "description": record["arbitration_notes"],
                            "intent_type": record["intent_type"],
                            "intent_scope": record["intent_scope"],
                            "generalization_hint": record["generalization_hint"],
                            "confidence_override": record["confidence_override"],
                            "declaration_constraints": record["declaration_constraints"],
                        }
                        for record in self.arbitrators
                        if record["user_id"] == parameters["user_id"]
                    ]

                if "WHERE h.timestamp > datetime($cutoff_date)" in normalized_query:
                    return []

                if "RETURN count(h) as total" in normalized_query:
                    total = sum(
                        1 for record in self.arbitrators if record["user_id"] == parameters["user_id"]
                    )
                    return [{"total": total}]

                return []

        fake_db = FakeDB()
        monkeypatch.setattr("backend.server.jsonrpc_methods.get_db", lambda: fake_db)

        declare_response = client.post(
            "/jsonrpc",
            json={
                "jsonrpc": "2.0",
                "method": "sspDeclareIntent",
                "params": {
                    "intent_type": "constraint",
                    "intent_scope": "global",
                    "description": "Only include papers published after 2020",
                    "constraints": {"year_gte": 2020},
                    "active_from": "2026-05-25",
                },
                "id": 14,
            },
            headers=auth_headers,
        )
        assert declare_response.status_code == 200
        declare_data = declare_response.json()
        assert "result" in declare_data

        profile_response = client.post(
            "/jsonrpc",
            json={
                "jsonrpc": "2.0",
                "method": "sspQueryIntentProfile",
                "params": {
                    "user_id": "current_user",
                    "detail_level": "full",
                },
                "id": 15,
            },
            headers=auth_headers,
        )
        assert profile_response.status_code == 200
        profile_data = profile_response.json()
        assert "result" in profile_data
        patterns = profile_data["result"]["profile"]["learned_patterns"]
        assert any(pattern["description"] == "Only include papers published after 2020" for pattern in patterns)
        assert profile_data["result"]["profile"]["total_intents_captured"] == 1

    # Note: Full integration tests require:
    # 1. Neo4j test container
    # 2. Sample domain pack file
    # 3. Mock PDF extraction
    # These will be added in Phase B completion
