"""
Ingestion Service
Handles paper ingestion with automatic subdomain classification.
"""

from typing import List, Dict, Any
from backend.database.node_repository import NodeRepository
from backend.database.edge_repository import EdgeRepository
from backend.services.subdomain_classifier import SubdomainClassifier
from backend.schemas.nodes import PaperNode, ChunkNode, FormulaNode
from backend.schemas.edges import BelongsToEdge, ContainsEdge
from backend.schemas.domain_pack import DomainPackConfig


class IngestionService:
    """
    Orchestrates paper ingestion with automatic subdomain classification.
    """

    def __init__(
        self,
        node_repo: NodeRepository,
        edge_repo: EdgeRepository,
        domain_config: DomainPackConfig,
        llm_client=None
    ):
        """
        Initialize ingestion service.
        
        Args:
            node_repo: Node repository for database operations
            edge_repo: Edge repository for relationship operations
            domain_config: Domain pack configuration
            llm_client: Optional LLM client for AI-based classification
        """
        self.node_repo = node_repo
        self.edge_repo = edge_repo
        self.domain_config = domain_config
        self.llm_client = llm_client
        self.classifier = SubdomainClassifier(domain_config)

    async def ingest_paper(
        self,
        paper: PaperNode,
        chunks: List[ChunkNode],
        formulas: List[FormulaNode],
        auto_classify: bool = True
    ) -> Dict[str, Any]:
        """
        Ingest a paper with automatic subdomain classification.
        
        Args:
            paper: Paper metadata
            chunks: Extracted text chunks
            formulas: Extracted formulas
            auto_classify: Whether to automatically classify into subdomains
        
        Returns:
            Dict with ingestion results including subdomain assignments
        """
        # 1. Ensure subdomain nodes exist
        created_subdomains = self.classifier.ensure_subdomains_exist(self.node_repo)

        # 2. Create paper node
        self.node_repo.create_paper_node(paper)

        # 3. Create chunk nodes
        for chunk in chunks:
            self.node_repo.create_chunk_node(chunk)
            # Link chunk to paper
            self.edge_repo.create_contains_edge(
                ContainsEdge(
                    from_node_id=paper.id,
                    to_node_id=chunk.id,
                    extraction_method="marker"  # or passed as parameter
                )
            )

        # 4. Create formula nodes
        for formula in formulas:
            self.node_repo.create_formula_node(formula)
            # Link formula to paper
            self.edge_repo.create_contains_edge(
                ContainsEdge(
                    from_node_id=paper.id,
                    to_node_id=formula.id,
                    extraction_method="marker"
                )
            )

        # 5. Classify paper into subdomains
        subdomain_assignments = []
        if auto_classify:
            assignments = await self.classifier.classify_paper(
                paper=paper,
                extracted_chunks=chunks,
                llm_client=self.llm_client
            )

            # Create BELONGS_TO edges for each subdomain
            primary = True  # First subdomain is primary
            for subdomain_id, confidence, dimension in assignments:
                belongs_to_edge = BelongsToEdge(
                    from_node_id=paper.id,
                    to_node_id=subdomain_id,
                    confidence=confidence,
                    primary=primary,
                    classification_method="llm" if self.llm_client else "rule_based"
                )

                self.edge_repo.create_belongs_to_edge(belongs_to_edge)
                
                subdomain_assignments.append({
                    "subdomain_id": subdomain_id,
                    "confidence": confidence,
                    "dimension": dimension,
                    "primary": primary
                })
                
                primary = False  # Subsequent ones are secondary

        else:
            # Manual classification: assign to parent domain only
            belongs_to_edge = BelongsToEdge(
                from_node_id=paper.id,
                to_node_id=self.domain_config.domain.id,
                confidence=1.0,
                primary=True,
                classification_method="manual"
            )
            self.edge_repo.create_belongs_to_edge(belongs_to_edge)
            
            subdomain_assignments.append({
                "subdomain_id": self.domain_config.domain.id,
                "confidence": 1.0,
                "dimension": "parent",
                "primary": True
            })

        # 6. Return ingestion summary
        return {
            "paper_id": paper.id,
            "chunks_created": len(chunks),
            "formulas_created": len(formulas),
            "subdomain_assignments": subdomain_assignments,
            "created_subdomains": created_subdomains
        }

    def get_papers_by_subdomain(self, subdomain_id: str) -> List[PaperNode]:
        """
        Get all papers assigned to a specific subdomain.
        
        Args:
            subdomain_id: Subdomain identifier
        
        Returns:
            List of PaperNode objects
        """
        query = """
        MATCH (p:PaperNode)-[:BELONGS_TO]->(d:DomainNode {id: $subdomain_id})
        RETURN p
        ORDER BY p.year DESC
        """
        
        result = self.node_repo.db.execute_query(query, {"subdomain_id": subdomain_id})
        papers = []
        for record in result:
            papers.append(PaperNode(**record["p"]))
        
        return papers

    def get_subdomain_distribution(self) -> Dict[str, int]:
        """
        Get paper count distribution across subdomains.
        
        Returns:
            Dict mapping subdomain IDs to paper counts
        """
        query = """
        MATCH (p:PaperNode)-[:BELONGS_TO]->(d:DomainNode)
        WHERE d.id STARTS WITH $domain_prefix
        RETURN d.id as subdomain_id, d.name as subdomain_name, count(p) as paper_count
        ORDER BY paper_count DESC
        """
        
        domain_prefix = self.domain_config.domain.id
        result = self.node_repo.db.execute_query(query, {"domain_prefix": domain_prefix})
        
        distribution = {}
        for record in result:
            distribution[record["subdomain_id"]] = {
                "name": record["subdomain_name"],
                "count": record["paper_count"]
            }
        
        return distribution

    def reclassify_paper(
        self,
        paper_id: str,
        new_subdomain_id: str,
        confidence: float = 1.0,
        classification_method: str = "manual"
    ) -> bool:
        """
        Manually reclassify a paper to a different subdomain.
        
        Args:
            paper_id: Paper identifier
            new_subdomain_id: New subdomain to assign
            confidence: Confidence score
            classification_method: Method used for reclassification
        
        Returns:
            True if successful
        """
        # Remove existing BELONGS_TO edges
        delete_query = """
        MATCH (p:PaperNode {id: $paper_id})-[r:BELONGS_TO]->(:DomainNode)
        DELETE r
        """
        self.node_repo.db.execute_query(delete_query, {"paper_id": paper_id})

        # Create new BELONGS_TO edge
        belongs_to_edge = BelongsToEdge(
            from_node_id=paper_id,
            to_node_id=new_subdomain_id,
            confidence=confidence,
            primary=True,
            classification_method=classification_method
        )
        
        self.edge_repo.create_belongs_to_edge(belongs_to_edge)
        return True
