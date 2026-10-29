"""
Test suite for subdomain classification functionality
"""

import pytest
from backend.services.subdomain_classifier import SubdomainClassifier
from backend.services.ingestion_service import IngestionService
from backend.schemas.domain_pack import DomainPackConfig, DomainInfo, TaxonomyDimension, MetricDefinition, ValidationRules
from backend.schemas.nodes import PaperNode, ChunkNode
from backend.schemas.edges import BelongsToEdge


@pytest.fixture
def sample_domain_config():
    """Create a sample domain config with subdomain mappings."""
    return DomainPackConfig(
        schema_version="1.0",
        domain=DomainInfo(
            id="domain.networking.optical",
            name="Optical Access Networks",
            parent_domain_id=None,
            taxonomy_tree=[
                TaxonomyDimension(
                    name="topology",
                    values=["mesh", "ring", "star", "free_space"],
                    subdomain_map={
                        "free_space": "domain.networking.optical.fso",
                        "mesh": "domain.networking.optical.access"
                    },
                    description="Network topology types"
                ),
                TaxonomyDimension(
                    name="switching_mechanism",
                    values=["wdm", "optical_packet", "burst_switching"],
                    subdomain_map={
                        "wdm": "domain.networking.optical.wdm",
                        "optical_packet": "domain.networking.optical.ops"
                    },
                    description="Switching technologies"
                )
            ]
        ),
        core_metrics=[
            MetricDefinition(
                name="reconfiguration_delay",
                expected_unit="ms",
                aliases=["switching_delay"],
                value_type="float"
            )
        ],
        validation=ValidationRules(
            required_context_keys=["network_load"],
            unit_normalization={"ms": ["ms", "millisecond"]}
        )
    )


@pytest.fixture
def sample_paper():
    """Create a sample paper about WDM networks."""
    return PaperNode(
        id="paper_wdm_test",
        doi="10.1109/TEST.2026.001",
        title="Advanced WDM Techniques for High-Capacity Optical Networks",
        authors=["Smith, J.", "Doe, A."],
        year=2026,
        venue="OFC 2026",
        provenance_hash="abc123",
        import_status="pending",
        workspace_id="workspace_test"
    )


@pytest.fixture
def sample_chunks():
    """Create sample text chunks mentioning WDM."""
    return [
        ChunkNode(
            id="paper_wdm_test#chunk_1",
            raw_text="This paper presents novel wavelength division multiplexing (WDM) approaches for metro networks.",
            bounding_box={"page": 1, "coords": [100, 200, 400, 250]},
            verification_status="raw",
            last_modified_by="system",
            last_modified_at="2026-05-24T10:00:00Z"
        ),
        ChunkNode(
            id="paper_wdm_test#chunk_2",
            raw_text="Our WDM system achieves 100 Gbps per wavelength with minimal cross-talk.",
            bounding_box={"page": 2, "coords": [100, 300, 400, 350]},
            verification_status="raw",
            last_modified_by="system",
            last_modified_at="2026-05-24T10:00:00Z"
        )
    ]


class TestSubdomainClassifier:
    """Tests for SubdomainClassifier."""

    def test_parse_taxonomy_dimensions(self, sample_domain_config):
        """Test parsing of structured taxonomy dimensions."""
        classifier = SubdomainClassifier(sample_domain_config)
        
        assert len(classifier.taxonomy_dimensions) == 2
        assert classifier.taxonomy_dimensions[0].name == "topology"
        assert "mesh" in classifier.taxonomy_dimensions[0].values
        assert classifier.taxonomy_dimensions[0].subdomain_map["mesh"] == "domain.networking.optical.access"

    def test_rule_based_classification(self, sample_domain_config, sample_paper, sample_chunks):
        """Test keyword-based subdomain classification."""
        classifier = SubdomainClassifier(sample_domain_config)
        
        classification = classifier._rule_based_classify(sample_paper, sample_chunks)
        
        # Should classify into WDM subdomain based on keywords
        assert "switching_mechanism" in classification
        assert classification["switching_mechanism"]["value"] == "wdm"
        assert classification["switching_mechanism"]["confidence"] > 0.3

    @pytest.mark.asyncio
    async def test_classify_paper_without_llm(self, sample_domain_config, sample_paper, sample_chunks):
        """Test paper classification using rule-based method."""
        classifier = SubdomainClassifier(sample_domain_config)
        
        assignments = await classifier.classify_paper(
            paper=sample_paper,
            extracted_chunks=sample_chunks,
            llm_client=None  # No LLM, use rule-based
        )
        
        # Should return at least one subdomain assignment
        assert len(assignments) > 0
        
        # First assignment should be WDM subdomain
        subdomain_id, confidence, dimension = assignments[0]
        assert "wdm" in subdomain_id
        assert 0.0 < confidence <= 1.0
        assert dimension == "switching_mechanism"

    def test_subdomain_hierarchy(self, sample_domain_config):
        """Test subdomain hierarchy extraction."""
        classifier = SubdomainClassifier(sample_domain_config)
        
        hierarchy = classifier.get_subdomain_hierarchy()
        
        assert "domain.networking.optical" in hierarchy
        subdomains = hierarchy["domain.networking.optical"]
        
        # Should include all mapped subdomains
        assert "domain.networking.optical.fso" in subdomains
        assert "domain.networking.optical.wdm" in subdomains
        assert "domain.networking.optical.access" in subdomains
        assert "domain.networking.optical.ops" in subdomains


class TestBelongsToEdgeSchema:
    """Tests for enhanced BelongsToEdge schema."""

    def test_belongs_to_edge_with_confidence(self):
        """Test creating BELONGS_TO edge with confidence score."""
        edge = BelongsToEdge(
            from_node_id="paper_123",
            to_node_id="domain.networking.optical.wdm",
            confidence=0.85,
            primary=True,
            classification_method="llm"
        )
        
        assert edge.confidence == 0.85
        assert edge.primary is True
        assert edge.classification_method == "llm"

    def test_belongs_to_edge_defaults(self):
        """Test default values for BELONGS_TO edge."""
        edge = BelongsToEdge(
            from_node_id="paper_123",
            to_node_id="domain.networking.optical"
        )
        
        assert edge.confidence == 1.0
        assert edge.primary is True
        assert edge.classification_method == "manual"


# Example usage script
if __name__ == "__main__":
    print("=" * 60)
    print("Subdomain Classification Example")
    print("=" * 60)
    
    # Create domain config
    config = DomainPackConfig(
        schema_version="1.0",
        domain=DomainInfo(
            id="domain.networking.optical",
            name="Optical Access Networks",
            parent_domain_id=None,
            taxonomy_tree=[
                TaxonomyDimension(
                    name="topology",
                    values=["mesh", "ring", "star", "free_space"],
                    subdomain_map={
                        "free_space": "domain.networking.optical.fso",
                        "mesh": "domain.networking.optical.access"
                    },
                    description="Network topology types"
                ),
                TaxonomyDimension(
                    name="switching_mechanism",
                    values=["wdm", "optical_packet", "burst_switching"],
                    subdomain_map={
                        "wdm": "domain.networking.optical.wdm",
                        "optical_packet": "domain.networking.optical.ops"
                    },
                    description="Switching technologies"
                )
            ]
        ),
        core_metrics=[
            MetricDefinition(
                name="reconfiguration_delay",
                expected_unit="ms",
                aliases=["switching_delay"],
                value_type="float"
            )
        ],
        validation=ValidationRules(
            required_context_keys=["network_load"],
            unit_normalization={"ms": ["ms", "millisecond"]}
        )
    )
    
    # Initialize classifier
    classifier = SubdomainClassifier(config)
    
    print("\n📊 Taxonomy Dimensions:")
    for dim in classifier.taxonomy_dimensions:
        print(f"\n  {dim.name}:")
        print(f"    Values: {dim.values}")
        print(f"    Subdomain Mappings:")
        for value, subdomain in dim.subdomain_map.items():
            print(f"      - {value} → {subdomain}")
    
    print("\n🏗️  Subdomain Hierarchy:")
    hierarchy = classifier.get_subdomain_hierarchy()
    for parent, children in hierarchy.items():
        print(f"\n  {parent}:")
        for child in children:
            print(f"    └─ {child}")
    
    print("\n" + "=" * 60)
    print("✅ Subdomain classification system ready!")
    print("=" * 60)
