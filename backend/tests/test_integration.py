"""
Integration Tests for Neo4j Connection and Repositories
Tests database operations with actual Neo4j instance using testcontainers.
"""

import pytest
import os
from testcontainers.community.neo4j import Neo4jContainer
from backend.database import Neo4jConnection, NodeRepository, EdgeRepository, init_db, close_db, get_db
from backend.schemas.nodes import DomainNode, PaperNode, ChunkNode, FormulaNode, AssertionNode, HumanArbitratorNode
from backend.schemas.edges import BelongsToEdge, ContainsEdge, CitesEdge, LocksEdge, ApprovesEdge
from backend.config import DomainPackLoader


@pytest.fixture(scope="module")
def neo4j_container():
    """
    Provide a Neo4j instance for integration tests.

    If ``ONTOFORGE_TEST_NEO4J_URI`` (or ``NEO4J_URI``) points at a running
    instance it is used directly, otherwise a Docker test container is started.
    Integration tests are skipped when neither is available.
    """
    external_uri = os.getenv("ONTOFORGE_TEST_NEO4J_URI") or os.getenv("NEO4J_URI")
    if external_uri:
        os.environ["NEO4J_URI"] = external_uri
        os.environ.setdefault("NEO4J_USER", "neo4j")
        os.environ.setdefault("NEO4J_PASSWORD", "password")
        yield None
        return

    try:
        container = Neo4jContainer("neo4j:5")
        container.start()
    except Exception as exc:  # Docker not available
        if os.getenv("ONTOFORGE_REQUIRE_INTEGRATION", "false").lower() in {
            "1", "true", "yes", "on"
        }:
            pytest.fail(f"Neo4j integration tests are required but unavailable: {exc}")
        pytest.skip(f"Neo4j unavailable (no Docker daemon and no NEO4J_URI): {exc}")

    try:
        os.environ["NEO4J_URI"] = container.get_connection_url()
        os.environ["NEO4J_USER"] = container.username
        os.environ["NEO4J_PASSWORD"] = container.password
        yield container
    finally:
        container.stop()


@pytest.fixture
def neo4j_db(neo4j_container):
    """
    Initialize database connection for each test.
    
    Creates a fresh connection and cleans up after each test.
    """
    # Get connection info from environment (set by neo4j_container fixture)
    uri = os.environ["NEO4J_URI"]
    user = os.environ["NEO4J_USER"]
    password = os.environ["NEO4J_PASSWORD"]
    
    # Initialize connection
    init_db(uri, user, password)
    db = get_db()
    
    yield db
    
    # Cleanup: delete all nodes and relationships
    with db.session() as session:
        session.run("MATCH (n) DETACH DELETE n")
    
    # Close connection
    close_db()


class TestNodeRepository:
    """Tests for NodeRepository CRUD operations with real Neo4j."""

    def test_create_domain_node(self, neo4j_db):
        """Test creating a DomainNode in Neo4j."""
        repo = NodeRepository(neo4j_db)

        domain_node = DomainNode(
            id="domain.test",
            name="Test Domain",
            namespace="test",
            domain_pack_id="test_pack",
            domain_pack_version="1.0",
            taxonomy_tree={"optical": ["coherent", "direct-detect"]},
            core_metrics=["spectral_efficiency", "reach"],
        )

        result = repo.create_domain_node(domain_node)
        assert result is not None
        assert result["id"] == "domain.test"
        assert result["name"] == "Test Domain"

    def test_create_paper_node(self, neo4j_db):
        """Test creating a PaperNode in Neo4j."""
        repo = NodeRepository(neo4j_db)

        paper_node = PaperNode(
            id="paper_test_2026",
            doi="10.1109/test.2026",
            title="Test Paper on Optical Networks",
            authors=["Alice Smith", "Bob Jones"],
            year=2026,
            venue="OFC Conference",
            provenance_hash="abc123def456",
            workspace_id="workspace_test",
        )

        result = repo.create_paper_node(paper_node)
        assert result is not None
        assert result["id"] == "paper_test_2026"
        assert result["title"] == "Test Paper on Optical Networks"
        assert len(result["authors"]) == 2

    def test_create_chunk_node(self, neo4j_db):
        """Test creating a ChunkNode in Neo4j."""
        repo = NodeRepository(neo4j_db)

        chunk_node = ChunkNode(
            id="paper_test#chunk_1",
            raw_text="We demonstrate spectral efficiency of 10 bits/s/Hz.",
            bounding_box={"page": 1, "x": 100, "y": 200, "width": 400, "height": 50},
            verification_status="raw",
        )

        result = repo.create_chunk_node(chunk_node)
        assert result is not None
        assert result["id"] == "paper_test#chunk_1"
        assert result["verification_status"] == "raw"

    def test_create_formula_node(self, neo4j_db):
        """Test creating a FormulaNode in Neo4j."""
        repo = NodeRepository(neo4j_db)

        formula_node = FormulaNode(
            id="paper_test#formula_1",
            latex_string="SE = \\log_2(1 + SNR)",
            variables_map={"SE": "spectral_efficiency", "SNR": "signal_to_noise_ratio"},
            constraints={"valid_range": "SNR > 0"},
            verification_status="raw",
        )

        result = repo.create_formula_node(formula_node)
        assert result is not None
        assert result["id"] == "paper_test#formula_1"
        assert "log_2" in result["latex_string"]

    def test_get_node_by_id(self, neo4j_db):
        """Test retrieving a node by ID."""
        repo = NodeRepository(neo4j_db)

        # Create a node first
        domain_node = DomainNode(
            id="domain.retrieve_test",
            name="Retrieve Test Domain",
            namespace="test",
            domain_pack_id="test_pack",
            domain_pack_version="1.0",
            taxonomy_tree={},
            core_metrics=[],
        )
        repo.create_domain_node(domain_node)

        # Retrieve it
        result = repo.get_node_by_id("domain.retrieve_test", "DomainNode")
        assert result is not None
        assert result["id"] == "domain.retrieve_test"
        assert result["name"] == "Retrieve Test Domain"

    def test_update_node(self, neo4j_db):
        """Test updating node properties."""
        repo = NodeRepository(neo4j_db)

        # Create a chunk node
        chunk_node = ChunkNode(
            id="chunk_update_test",
            raw_text="Original text",
            bounding_box={},
            verification_status="raw",
        )
        repo.create_chunk_node(chunk_node)

        # Update it
        updates = {
            "raw_text": "Updated text content",
            "verification_status": "pending_verification",
            "last_modified_by": "user-alice",
            "modification_count": 1,
        }
        result = repo.update_node("chunk_update_test", "ChunkNode", updates)
        assert result is not None
        assert result["raw_text"] == "Updated text content"
        assert result["verification_status"] == "pending_verification"

    def test_delete_node(self, neo4j_db):
        """Test deleting a node."""
        repo = NodeRepository(neo4j_db)

        # Create a node
        paper_node = PaperNode(
            id="paper_delete_test",
            doi="10.1109/delete",
            title="Delete Test",
            authors=["Test Author"],
            year=2026,
            venue="Test",
            provenance_hash="delete123",
            workspace_id="workspace_test",
        )
        repo.create_paper_node(paper_node)

        # Delete it
        repo.delete_node("paper_delete_test", "PaperNode")

        # Verify it's gone
        result = repo.get_node_by_id("paper_delete_test", "PaperNode")
        assert result is None


class TestEdgeRepository:
    """Tests for EdgeRepository CRUD operations with real Neo4j."""

    def test_create_belongs_to_edge(self, neo4j_db):
        """Test creating a BELONGS_TO relationship."""
        node_repo = NodeRepository(neo4j_db)
        edge_repo = EdgeRepository(neo4j_db)

        # Create nodes first
        domain = DomainNode(
            id="domain.edge_test",
            name="Edge Test Domain",
            namespace="test",
            domain_pack_id="test",
            domain_pack_version="1.0",
            taxonomy_tree={},
            core_metrics=[],
        )
        node_repo.create_domain_node(domain)

        paper = PaperNode(
            id="paper_edge_test",
            doi="10.1109/edge",
            title="Edge Test Paper",
            authors=["Test"],
            year=2026,
            venue="Test",
            provenance_hash="edge123",
            workspace_id="workspace_test",
        )
        node_repo.create_paper_node(paper)

        # Create edge
        edge = BelongsToEdge(from_node_id="paper_edge_test", to_node_id="domain.edge_test")
        result = edge_repo.create_belongs_to_edge(edge)
        assert result is not None

    def test_create_contains_edge(self, neo4j_db):
        """Test creating a CONTAINS relationship."""
        node_repo = NodeRepository(neo4j_db)
        edge_repo = EdgeRepository(neo4j_db)

        # Create paper and chunk
        paper = PaperNode(
            id="paper_contains_test",
            doi="10.1109/contains",
            title="Contains Test",
            authors=["Test"],
            year=2026,
            venue="Test",
            provenance_hash="contains123",
            workspace_id="workspace_test",
        )
        node_repo.create_paper_node(paper)

        chunk = ChunkNode(
            id="chunk_contains_test",
            raw_text="Test chunk",
            bounding_box={},
        )
        node_repo.create_chunk_node(chunk)

        # Create edge with extraction method
        edge = ContainsEdge(
            from_node_id="paper_contains_test",
            to_node_id="chunk_contains_test",
            extraction_method="manual",
        )
        result = edge_repo.create_contains_edge(edge)
        assert result is not None
        assert result.get("extraction_method") == "manual"

    def test_create_approves_edge(self, neo4j_db):
        """Test creating an APPROVES relationship."""
        node_repo = NodeRepository(neo4j_db)
        edge_repo = EdgeRepository(neo4j_db)

        # Create arbitrator and domain
        arbitrator = HumanArbitratorNode(
            id="arbitrator_test",
            user_id="test@example.com",
            timestamp="2026-01-01T00:00:00Z",
            arbitration_notes="Test arbitration",
            lock_type="permanent_human_lock",
        )
        node_repo.create_arbitrator_node(arbitrator)

        domain = DomainNode(
            id="domain.approve_test",
            name="Approve Test Domain",
            namespace="test",
            domain_pack_id="test",
            domain_pack_version="1.0",
            taxonomy_tree={},
            core_metrics=[],
        )
        node_repo.create_domain_node(domain)

        # Create APPROVES edge
        edge = ApprovesEdge(
            from_node_id="arbitrator_test",
            to_node_id="domain.approve_test",
            approval_type="taxonomy_change",
            approved_version="1.0",
        )
        result = edge_repo.create_approves_edge(edge)
        assert result is not None
        assert result.get("approval_type") == "taxonomy_change"

    def test_create_locks_edge(self, neo4j_db):
        """Test creating a LOCKS relationship."""
        node_repo = NodeRepository(neo4j_db)
        edge_repo = EdgeRepository(neo4j_db)

        # Create arbitrator and assertion
        arbitrator = HumanArbitratorNode(
            id="arbitrator_lock_test",
            user_id="lock_test@example.com",
            timestamp="2026-01-01T00:00:00Z",
            arbitration_notes="Lock test arbitration",
            lock_type="temporary_override",
        )
        node_repo.create_arbitrator_node(arbitrator)

        assertion = AssertionNode(
            id="assertion_lock_test",
            subject="optical:spectral_efficiency",
            predicate="equals",
            object="10",
            unit="bits_per_second_per_hertz",
            domain_pack_namespace="optical",
            context_conditions={},
            status="pending",
            workspace_id="workspace_test",
        )
        node_repo.create_assertion_node(assertion)

        # Create LOCKS edge
        edge = LocksEdge(
            from_node_id="arbitrator_lock_test",
            to_node_id="assertion_lock_test",
        )
        result = edge_repo.create_locks_edge(edge)
        assert result is not None


class TestSSPWorkflows:
    """Integration tests for complete SSP workflows."""

    def test_full_ingest_and_extract_workflow(self, neo4j_db):
        """Test complete workflow: sspInitialize → sspIngest → sspExtract."""
        node_repo = NodeRepository(neo4j_db)
        edge_repo = EdgeRepository(neo4j_db)

        # Step 1: Initialize domain
        domain = DomainNode(
            id="domain.optical",
            name="Optical Networking",
            namespace="optical",
            domain_pack_id="optical_v1",
            domain_pack_version="1.0.0",
            taxonomy_tree={"modulation": ["qpsk", "16qam"]},
            core_metrics=["spectral_efficiency"],
        )
        node_repo.create_domain_node(domain)

        # Step 2: Ingest paper
        paper = PaperNode(
            id="paper_workflow_test",
            doi="10.1109/workflow.2026",
            title="Workflow Test Paper",
            authors=["Workflow Author"],
            year=2026,
            venue="Test Conference",
            provenance_hash="workflow123",
            workspace_id="workspace_test",
        )
        node_repo.create_paper_node(paper)

        # Create BELONGS_TO edge
        belongs_edge = BelongsToEdge(
            from_node_id="paper_workflow_test",
            to_node_id="domain.optical",
        )
        edge_repo.create_belongs_to_edge(belongs_edge)

        # Step 3: Extract chunks and formulas
        chunk = ChunkNode(
            id="paper_workflow_test#chunk_1",
            raw_text="We achieve 10 bits/s/Hz spectral efficiency.",
            bounding_box={"page": 1},
        )
        node_repo.create_chunk_node(chunk)

        contains_edge_chunk = ContainsEdge(
            from_node_id="paper_workflow_test",
            to_node_id="paper_workflow_test#chunk_1",
            extraction_method="automated",
        )
        edge_repo.create_contains_edge(contains_edge_chunk)

        formula = FormulaNode(
            id="paper_workflow_test#formula_1",
            latex_string="SE = 10",
            variables_map={"SE": "spectral_efficiency"},
            constraints={},
        )
        node_repo.create_formula_node(formula)

        contains_edge_formula = ContainsEdge(
            from_node_id="paper_workflow_test",
            to_node_id="paper_workflow_test#formula_1",
            extraction_method="automated",
        )
        edge_repo.create_contains_edge(contains_edge_formula)

        # Verify complete workflow
        domain_result = node_repo.get_node_by_id("domain.optical", "DomainNode")
        assert domain_result is not None

        paper_result = node_repo.get_node_by_id("paper_workflow_test", "PaperNode")
        assert paper_result is not None

        chunk_result = node_repo.get_node_by_id("paper_workflow_test#chunk_1", "ChunkNode")
        assert chunk_result is not None

        formula_result = node_repo.get_node_by_id("paper_workflow_test#formula_1", "FormulaNode")
        assert formula_result is not None

    def test_hitl_correction_workflow(self, neo4j_db):
        """Test HITL 5-state correction workflow: raw → under_correction → pending_verification → verified."""
        node_repo = NodeRepository(neo4j_db)

        # Create chunk in raw state
        chunk = ChunkNode(
            id="chunk_hitl_test",
            raw_text="Original extracted text",
            bounding_box={},
            verification_status="raw",
        )
        node_repo.create_chunk_node(chunk)

        # State 1: Lock for editing (raw → under_correction)
        updates_lock = {
            "verification_status": "under_correction",
            "last_modified_by": "editor-alice",
            "last_modified_at": "2026-05-23T10:00:00Z",
        }
        result = node_repo.update_node("chunk_hitl_test", "ChunkNode", updates_lock)
        assert result["verification_status"] == "under_correction"

        # State 2: Save edits (under_correction → pending_verification)
        updates_edit = {
            "raw_text": "Corrected text by human",
            "verification_status": "pending_verification",
            "last_modified_by": "editor-alice",
            "last_modified_at": "2026-05-23T10:15:00Z",
            "modification_count": 1,
        }
        result = node_repo.update_node("chunk_hitl_test", "ChunkNode", updates_edit)
        assert result["verification_status"] == "pending_verification"
        assert result["raw_text"] == "Corrected text by human"
        assert result["modification_count"] == 1

        # State 3: Reviewer approves (pending_verification → verified)
        updates_verify = {
            "verification_status": "verified",
            "last_modified_by": "reviewer-bob",
            "last_modified_at": "2026-05-23T11:00:00Z",
        }
        result = node_repo.update_node("chunk_hitl_test", "ChunkNode", updates_verify)
        assert result["verification_status"] == "verified"

        # Verify final state
        final = node_repo.get_node_by_id("chunk_hitl_test", "ChunkNode")
        assert final["verification_status"] == "verified"
        assert final["modification_count"] == 1

    # NOTE: Duplicate test removed - belongs in unit test file with mock_db fixture
