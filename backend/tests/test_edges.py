"""
Tests for Edge Schema Definitions
"""

import pytest
from pydantic import ValidationError

from backend.schemas.edges import (
    HasBranchEdge,
    BelongsToEdge,
    CitesEdge,
    ContainsEdge,
    EvidencedByEdge,
    ContradictsEdge,
    LocksEdge,
    ApprovesEdge,
)


class TestEvidencedByEdge:
    """Tests for EvidencedByEdge schema with confidence_score."""

    def test_valid_evidenced_by_edge(self):
        """Test creation of valid EvidencedByEdge."""
        edge = EvidencedByEdge(
            from_node_id="chunk_1",
            to_node_id="assert_001",
            confidence_score=0.95,
        )
        assert edge.confidence_score == 0.95

    def test_confidence_score_bounds(self):
        """Test confidence_score must be between 0.0 and 1.0."""
        # Valid boundaries
        edge_min = EvidencedByEdge(
            from_node_id="chunk_1",
            to_node_id="assert_001",
            confidence_score=0.0,
        )
        assert edge_min.confidence_score == 0.0

        edge_max = EvidencedByEdge(
            from_node_id="chunk_1",
            to_node_id="assert_001",
            confidence_score=1.0,
        )
        assert edge_max.confidence_score == 1.0

        # Invalid: below 0
        with pytest.raises(ValidationError):
            EvidencedByEdge(
                from_node_id="chunk_1",
                to_node_id="assert_001",
                confidence_score=-0.1,
            )

        # Invalid: above 1
        with pytest.raises(ValidationError):
            EvidencedByEdge(
                from_node_id="chunk_1",
                to_node_id="assert_001",
                confidence_score=1.5,
            )


class TestContradictsEdge:
    """Tests for ContradictsEdge schema."""

    def test_valid_contradicts_edge(self):
        """Test creation of valid ContradictsEdge."""
        edge = ContradictsEdge(
            from_node_id="assert_001",
            to_node_id="assert_104",
            conflict_id="conf_089",
        )
        assert edge.conflict_id == "conf_089"

    def test_missing_conflict_id(self):
        """Test ContradictsEdge requires conflict_id."""
        with pytest.raises(ValidationError):
            ContradictsEdge(
                from_node_id="assert_001",
                to_node_id="assert_104",
                # Missing conflict_id
            )


class TestContainsEdge:
    """Tests for ContainsEdge schema."""

    def test_contains_edge_with_extraction_method(self):
        """Test ContainsEdge with optional extraction_method."""
        edge = ContainsEdge(
            from_node_id="paper_1",
            to_node_id="chunk_1",
            extraction_method="Marker",
        )
        assert edge.extraction_method == "Marker"

    def test_contains_edge_without_extraction_method(self):
        """Test ContainsEdge without extraction_method (optional)."""
        edge = ContainsEdge(
            from_node_id="paper_1",
            to_node_id="chunk_1",
        )
        assert edge.extraction_method is None


class TestBasicEdges:
    """Tests for basic edge schemas without extra properties."""

    def test_has_branch_edge(self):
        """Test HasBranchEdge creation."""
        edge = HasBranchEdge(
            from_node_id="domain.networking",
            to_node_id="domain.networking.optical",
        )
        assert edge.from_node_id == "domain.networking"

    def test_belongs_to_edge(self):
        """Test BelongsToEdge creation."""
        edge = BelongsToEdge(
            from_node_id="paper_1",
            to_node_id="domain.networking.optical",
        )
        assert edge.to_node_id == "domain.networking.optical"

    def test_cites_edge(self):
        """Test CitesEdge creation."""
        edge = CitesEdge(
            from_node_id="paper_1",
            to_node_id="paper_2",
        )
        assert edge.from_node_id == "paper_1"

    def test_locks_edge(self):
        """Test LocksEdge creation."""
        edge = LocksEdge(
            from_node_id="arbitrator_alice",
            to_node_id="assert_001",
        )
        assert edge.from_node_id == "arbitrator_alice"


class TestApprovesEdge:
    """Tests for ApprovesEdge schema."""

    def test_valid_approves_edge(self):
        """Test creation of valid ApprovesEdge."""
        edge = ApprovesEdge(
            from_node_id="arbitrator_alice_20260523_143022",
            to_node_id="domain.networking.optical",
            approval_type="taxonomy_change",
            approved_version="1.1",
        )
        assert edge.approval_type == "taxonomy_change"
        assert edge.approved_version == "1.1"

    def test_approves_edge_all_approval_types(self):
        """Test ApprovesEdge with all valid approval types."""
        approval_types = ["initial_approval", "taxonomy_change", "metric_addition"]
        for approval_type in approval_types:
            edge = ApprovesEdge(
                from_node_id="arbitrator_bob",
                to_node_id="domain.test",
                approval_type=approval_type,
                approved_version="1.0",
            )
            assert edge.approval_type == approval_type

    def test_invalid_approval_type(self):
        """Test ApprovesEdge creation fails with invalid approval type."""
        with pytest.raises(ValidationError):
            ApprovesEdge(
                from_node_id="arbitrator_alice",
                to_node_id="domain.test",
                approval_type="invalid_type",  # Must be one of the literals
                approved_version="1.0",
            )

    def test_missing_required_field(self):
        """Test ApprovesEdge requires all fields."""
        with pytest.raises(ValidationError):
            ApprovesEdge(
                from_node_id="arbitrator_alice",
                to_node_id="domain.test",
                approval_type="taxonomy_change",
                # Missing approved_version
            )
