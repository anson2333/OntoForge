"""
Tests for Node Schema Definitions
"""

from datetime import datetime
import pytest
from pydantic import ValidationError

from backend.schemas.nodes import (
    DomainNode,
    PaperNode,
    ChunkNode,
    FormulaNode,
    AssertionNode,
    HumanArbitratorNode,
)


class TestDomainNode:
    """Tests for DomainNode schema."""

    def test_valid_domain_node(self):
        """Test creation of valid DomainNode."""
        node = DomainNode(
            id="domain.networking.optical",
            name="Optical Access Networks",
            namespace="optical",
            domain_pack_id="optical_networks_v1",
            domain_pack_version="1.0",
            taxonomy_tree={"topology": ["mesh", "ring", "star"]},
            core_metrics=["reconfiguration_delay", "cross_talk"],
        )
        assert node.id == "domain.networking.optical"
        assert len(node.core_metrics) == 2
        assert node.approval_status == "draft"  # Default value

    def test_domain_node_with_approval_status(self):
        """Test DomainNode with explicit approval status."""
        node = DomainNode(
            id="domain.networking.optical",
            name="Optical Access Networks",
            namespace="optical",
            domain_pack_id="optical_networks_v1",
            domain_pack_version="1.0",
            taxonomy_tree={},
            core_metrics=[],
            approval_status="approved",
        )
        assert node.approval_status == "approved"

    def test_invalid_approval_status(self):
        """Test DomainNode creation fails with invalid approval status."""
        with pytest.raises(ValidationError):
            DomainNode(
                id="domain.test",
                name="Test",
                namespace="optical",
                domain_pack_id="test",
                domain_pack_version="1.0",
                taxonomy_tree={},
                core_metrics=[],
                approval_status="invalid_status",  # Must be draft/approved/deprecated
            )

    def test_missing_required_field(self):
        """Test DomainNode creation fails with missing field."""
        with pytest.raises(ValidationError):
            DomainNode(
                id="domain.test",
                name="Test Domain",
                namespace="optical",
                # Missing domain_pack_id
                domain_pack_version="1.0",
                taxonomy_tree={},
                core_metrics=[],
            )


class TestPaperNode:
    """Tests for PaperNode schema."""

    def test_valid_paper_node(self):
        """Test creation of valid PaperNode."""
        node = PaperNode(
            id="paper_satellite_2026",
            doi="10.1109/JLT.2026.123456",
            title="On-Board Optical Packet Switching",
            authors=["Zhang, X.", "Li, Y."],
            year=2026,
            venue="OFC 2026",
            provenance_hash="abc123def456",
            workspace_id="workspace_test",
        )
        assert node.doi == "10.1109/JLT.2026.123456"
        assert len(node.authors) == 2
        assert node.import_status == "pending"  # Default value

    def test_paper_node_with_import_status(self):
        """Test PaperNode with explicit import status."""
        node = PaperNode(
            id="paper_test",
            doi="10.1109/test",
            title="Test Paper",
            authors=["Author"],
            year=2026,
            venue="Test Venue",
            provenance_hash="hash",
            import_status="verified",
            workspace_id="workspace_test",
        )
        assert node.import_status == "verified"

    def test_invalid_import_status(self):
        """Test PaperNode creation fails with invalid import status."""
        with pytest.raises(ValidationError):
            PaperNode(
                id="paper_test",
                doi="10.1109/test",
                title="Test Paper",
                authors=["Author"],
                year=2026,
                venue="Test Venue",
                provenance_hash="hash",
                import_status="invalid_status",  # Must be pending/verified/rejected
                workspace_id="workspace_test",
            )

    def test_year_type_coercion(self):
        """Test PaperNode coerces string year to int (Pydantic v2 behavior)."""
        node = PaperNode(
            id="paper_test",
            doi="10.1109/test",
            title="Test Paper",
            authors=["Author"],
            year="2026",  # Pydantic v2 coerces string to int
            venue="Test Venue",
            provenance_hash="hash",
            workspace_id="workspace_test",
        )
        assert isinstance(node.year, int)
        assert node.year == 2026


class TestChunkNode:
    """Tests for ChunkNode schema."""

    def test_valid_chunk_node(self):
        """Test creation of valid ChunkNode."""
        node = ChunkNode(
            id="paper_test#chunk_1",
            raw_text="This is extracted text.",
            bounding_box={"page": 1, "coords": [100, 200, 300, 400]},
            verification_status="raw",
        )
        assert node.verification_status == "raw"
        assert node.bounding_box["page"] == 1
        assert node.modification_count == 0
        assert node.last_modified_by is None

    def test_chunk_node_all_verification_states(self):
        """Test ChunkNode with all valid verification states."""
        states = ["raw", "under_correction", "pending_verification", "verified", "rejected"]
        for state in states:
            node = ChunkNode(
                id="paper_test#chunk_1",
                raw_text="Text",
                bounding_box={"page": 1, "coords": [0, 0, 10, 10]},
                verification_status=state,
            )
            assert node.verification_status == state

    def test_chunk_node_with_audit_trail(self):
        """Test ChunkNode with edit audit trail."""
        node = ChunkNode(
            id="paper_test#chunk_1",
            raw_text="Corrected text after OCR fix",
            bounding_box={"page": 1, "coords": [0, 0, 10, 10]},
            verification_status="pending_verification",
            last_modified_by="arbitrator_alice_20260523_143022",
            last_modified_at="2026-05-23T14:30:22Z",
            modification_count=2,
        )
        assert node.last_modified_by == "arbitrator_alice_20260523_143022"
        assert node.modification_count == 2

    def test_invalid_verification_status(self):
        """Test ChunkNode creation fails with invalid status."""
        with pytest.raises(ValidationError):
            ChunkNode(
                id="chunk_1",
                raw_text="Text",
                bounding_box={"page": 1, "coords": []},
                verification_status="invalid_status",  # Must be valid state
            )


class TestFormulaNode:
    """Tests for FormulaNode schema."""

    def test_valid_formula_node(self):
        """Test creation of valid FormulaNode."""
        node = FormulaNode(
            id="form_eq_1",
            latex_string=r"\tau = N \cdot \Delta t",
            variables_map={"\\tau": "latency", "N": "count"},
            constraints={"valid_for": "mesh topology"},
        )
        assert r"\tau" in node.variables_map
        assert node.constraints["valid_for"] == "mesh topology"
        assert node.verification_status == "raw"  # Default value
        assert node.modification_count == 0

    def test_formula_node_all_verification_states(self):
        """Test FormulaNode with all valid verification states."""
        states = ["raw", "under_correction", "pending_verification", "verified", "rejected"]
        for state in states:
            node = FormulaNode(
                id="form_eq_1",
                latex_string=r"E = mc^2",
                variables_map={},
                verification_status=state,
            )
            assert node.verification_status == state

    def test_formula_node_with_verification_status(self):
        """Test FormulaNode with explicit verification status and audit trail."""
        node = FormulaNode(
            id="form_eq_2",
            latex_string=r"E = mc^2",
            variables_map={"E": "energy", "m": "mass"},
            verification_status="verified",
            last_modified_by="arbitrator_bob_20260523",
            last_modified_at="2026-05-23T15:00:00Z",
            modification_count=1,
        )
        assert node.verification_status == "verified"
        assert node.last_modified_by == "arbitrator_bob_20260523"

    def test_invalid_verification_status(self):
        """Test FormulaNode creation fails with invalid verification status."""
        with pytest.raises(ValidationError):
            FormulaNode(
                id="form_eq_3",
                latex_string=r"x = y",
                variables_map={},
                verification_status="invalid_status",  # Must be valid state
            )

    def test_formula_with_empty_constraints(self):
        """Test FormulaNode with no constraints (default)."""
        node = FormulaNode(
            id="form_eq_2",
            latex_string=r"E = mc^2",
            variables_map={"E": "energy", "m": "mass"},
        )
        assert node.constraints == {}


class TestAssertionNode:
    """Tests for AssertionNode schema."""

    def test_valid_assertion_node(self):
        """Test creation of valid AssertionNode."""
        node = AssertionNode(
            id="assert_001",
            subject="optical:reconfiguration_delay",
            predicate="equals",
            object="12.5",
            unit="ms",
            domain_pack_namespace="optical",
            context_conditions={"network_load": "80%", "topology": "mesh"},
            status="pending",
            workspace_id="workspace_test",
        )
        assert node.predicate == "equals"
        assert node.status == "pending"

    def test_invalid_predicate(self):
        """Test AssertionNode creation fails with invalid predicate."""
        with pytest.raises(ValidationError):
            AssertionNode(
                id="assert_002",
                subject="optical:metric",
                predicate="invalid_predicate",  # Must be one of the literals
                object="10",
                unit="ms",
                domain_pack_namespace="optical",
                context_conditions={},
                workspace_id="workspace_test",
            )


class TestHumanArbitratorNode:
    """Tests for HumanArbitratorNode schema."""

    def test_valid_arbitrator_node(self):
        """Test creation of valid HumanArbitratorNode."""
        timestamp = datetime(2026, 5, 23, 14, 30, 22)
        node = HumanArbitratorNode(
            id="arbitrator_alice_123",
            user_id="alice@research.org",
            timestamp=timestamp,
            arbitration_notes="Accepted Paper A baseline",
            lock_type="permanent_human_lock",
        )
        assert node.user_id == "alice@research.org"
        assert node.lock_type == "permanent_human_lock"

    def test_invalid_lock_type(self):
        """Test HumanArbitratorNode creation fails with invalid lock type."""
        with pytest.raises(ValidationError):
            HumanArbitratorNode(
                id="arbitrator_bob",
                user_id="bob@test.com",
                timestamp=datetime.now(),
                arbitration_notes="Notes",
                lock_type="invalid_lock",  # Must be one of the literals
            )
