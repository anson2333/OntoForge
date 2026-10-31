"""
Neo4j Repository Layer for Edge Operations
Provides CRUD operations for all graph edge types.
"""

from typing import Dict, Any, List
from backend.database.connection import Neo4jConnection
from backend.schemas.edges import (
    ContainsDomainPackEdge,
    ContainsPaperEdge,
    HasBranchEdge,
    BelongsToEdge,
    CitesEdge,
    ContainsEdge,
    EvidencedByEdge,
    ContradictsEdge,
    LocksEdge,
    ApprovesEdge,
    ScopesEdge,
    InheritsFromEdge,
    MatchesPatternEdge,
)


class EdgeRepository:
    """Repository for edge CRUD operations."""

    def __init__(self, db: Neo4jConnection):
        """
        Initialize edge repository.

        Args:
            db: Neo4j connection instance
        """
        self.db = db

    def create_contains_domain_pack_edge(self, edge: ContainsDomainPackEdge) -> Dict[str, Any]:
        """Create a CONTAINS_DOMAIN_PACK relationship linking workspace to domain pack."""
        query = """
        MATCH (from_node:WorkspaceNode {id: $from_node_id})
        MATCH (to_node:DomainNode {id: $to_node_id})
        CREATE (from_node)-[r:CONTAINS_DOMAIN_PACK]->(to_node)
        RETURN properties(r) as props
        """
        result = self.db.execute_query(query, edge.model_dump())
        return result[0]["props"] if result else {}

    def create_contains_paper_edge(self, edge: ContainsPaperEdge) -> Dict[str, Any] | None:
        """Create a CONTAINS_PAPER relationship linking workspace to paper."""
        query = """
        MATCH (from_node:WorkspaceNode {id: $from_node_id})
        MATCH (to_node:PaperNode {id: $to_node_id})
        CREATE (from_node)-[r:CONTAINS_PAPER]->(to_node)
        RETURN properties(r) as props
        """
        result = self.db.execute_query(query, edge.model_dump())
        return result[0]["props"] if result else None

    def create_has_branch_edge(self, edge: HasBranchEdge) -> Dict[str, Any]:
        """Create a HAS_BRANCH relationship."""
        query = """
        MATCH (from_node {id: $from_node_id})
        MATCH (to_node {id: $to_node_id})
        CREATE (from_node)-[r:HAS_BRANCH]->(to_node)
        RETURN properties(r) as props
        """
        result = self.db.execute_query(query, edge.model_dump())
        return result[0]["props"] if result else {}

    def create_belongs_to_edge(self, edge: BelongsToEdge) -> Dict[str, Any] | None:
        """Create a BELONGS_TO relationship with confidence and classification metadata."""
        query = """
        MATCH (from_node {id: $from_node_id})
        MATCH (to_node {id: $to_node_id})
        CREATE (from_node)-[r:BELONGS_TO {
            confidence: $confidence,
            primary: $primary,
            classification_method: $classification_method
        }]->(to_node)
        RETURN properties(r) as props
        """
        result = self.db.execute_query(query, edge.model_dump())
        return result[0]["props"] if result else None

    def create_cites_edge(self, edge: CitesEdge) -> Dict[str, Any]:
        """Create a CITES relationship."""
        query = """
        MATCH (from_node {id: $from_node_id})
        MATCH (to_node {id: $to_node_id})
        CREATE (from_node)-[r:CITES]->(to_node)
        RETURN properties(r) as props
        """
        result = self.db.execute_query(query, edge.model_dump())
        return result[0]["props"] if result else {}

    def create_contains_edge(self, edge: ContainsEdge) -> Dict[str, Any] | None:
        """Create a CONTAINS relationship with optional extraction_method property."""
        query = """
        MATCH (from_node {id: $from_node_id})
        MATCH (to_node {id: $to_node_id})
        CREATE (from_node)-[r:CONTAINS {extraction_method: $extraction_method}]->(to_node)
        RETURN properties(r) as props
        """
        result = self.db.execute_query(query, edge.model_dump())
        return result[0]["props"] if result else None

    def create_evidenced_by_edge(self, edge: EvidencedByEdge) -> Dict[str, Any] | None:
        """Create an EVIDENCED_BY relationship with confidence_score."""
        query = """
        MATCH (from_node {id: $from_node_id})
        MATCH (to_node {id: $to_node_id})
        CREATE (from_node)-[r:EVIDENCED_BY {
            confidence_score: $confidence_score
        }]->(to_node)
        RETURN properties(r) as props
        """
        result = self.db.execute_query(query, edge.model_dump())
        return result[0]["props"] if result else None

    def create_contradicts_edge(self, edge: ContradictsEdge) -> Dict[str, Any]:
        """Create a CONTRADICTS relationship with conflict_id."""
        query = """
        MATCH (from_node {id: $from_node_id})
        MATCH (to_node {id: $to_node_id})
        CREATE (from_node)-[r:CONTRADICTS {
            conflict_id: $conflict_id
        }]->(to_node)
        RETURN properties(r) as props
        """
        result = self.db.execute_query(query, edge.model_dump())
        return result[0]["props"] if result else {}

    def create_locks_edge(self, edge: LocksEdge) -> Dict[str, Any]:
        """Create a LOCKS relationship."""
        query = """
        MATCH (from_node {id: $from_node_id})
        MATCH (to_node {id: $to_node_id})
        CREATE (from_node)-[r:LOCKS]->(to_node)
        RETURN properties(r) as props
        """
        result = self.db.execute_query(query, edge.model_dump())
        return result[0]["props"] if result else {}

    def create_approves_edge(self, edge: ApprovesEdge) -> Dict[str, Any]:
        """Create an APPROVES relationship with approval metadata."""
        query = """
        MATCH (from_node {id: $from_node_id})
        MATCH (to_node {id: $to_node_id})
        CREATE (from_node)-[r:APPROVES {
            approval_type: $approval_type,
            approved_version: $approved_version
        }]->(to_node)
        RETURN properties(r) as props
        """
        result = self.db.execute_query(query, edge.model_dump())
        return result[0]["props"] if result else {}

    def get_relationships(
        self, from_node_id: str, relationship_type: str = None
    ) -> List[Dict[str, Any]]:
        """
        Get all relationships from a node.

        Args:
            from_node_id: Source node ID
            relationship_type: Optional relationship type filter

        Returns:
            List of relationship data with target nodes
        """
        if relationship_type:
            query = f"""
            MATCH (from_node {{id: $from_node_id}})-[r:{relationship_type}]->(to_node)
            RETURN r, to_node
            """
        else:
            query = """
            MATCH (from_node {id: $from_node_id})-[r]->(to_node)
            RETURN r, to_node, type(r) as rel_type
            """

        result = self.db.execute_query(query, {"from_node_id": from_node_id})
        return result

    def delete_relationship(
        self, from_node_id: str, to_node_id: str, relationship_type: str
    ) -> bool:
        """
        Delete a specific relationship.

        Args:
            from_node_id: Source node ID
            to_node_id: Target node ID
            relationship_type: Relationship type

        Returns:
            True if deleted, False if not found
        """
        query = f"""
        MATCH (from_node {{id: $from_node_id}})-[r:{relationship_type}]->(to_node {{id: $to_node_id}})
        DELETE r
        RETURN count(r) as deleted_count
        """
        result = self.db.execute_query(
            query, {"from_node_id": from_node_id, "to_node_id": to_node_id}
        )
        return result[0]["deleted_count"] > 0 if result else False

    # ========================================================================
    # Intent Edge Operations (Section 2.6)
    # ========================================================================

    def create_scopes_edge(self, edge: ScopesEdge) -> Dict[str, Any]:
        """Create a SCOPES relationship (IntentBranchNode -> HumanArbitratorNode)."""
        query = """
        MATCH (from_node:IntentBranchNode {id: $from_node_id})
        MATCH (to_node:HumanArbitratorNode {id: $to_node_id})
        CREATE (from_node)-[r:SCOPES]->(to_node)
        RETURN properties(r) as props
        """
        result = self.db.execute_query(query, edge.model_dump())
        return result[0]["props"] if result else {}

    def create_inherits_from_edge(self, edge: InheritsFromEdge) -> Dict[str, Any]:
        """Create an INHERITS_FROM relationship (IntentBranchNode -> IntentBranchNode)."""
        query = """
        MATCH (from_node:IntentBranchNode {id: $from_node_id})
        MATCH (to_node:IntentBranchNode {id: $to_node_id})
        CREATE (from_node)-[r:INHERITS_FROM]->(to_node)
        RETURN properties(r) as props
        """
        result = self.db.execute_query(query, edge.model_dump())
        return result[0]["props"] if result else {}

    def create_matches_pattern_edge(self, edge: MatchesPatternEdge) -> Dict[str, Any]:
        """Create a MATCHES_PATTERN relationship with pattern metadata."""
        query = """
        MATCH (from_node:HumanArbitratorNode {id: $from_node_id})
        MATCH (to_node:HumanArbitratorNode {id: $to_node_id})
        CREATE (from_node)-[r:MATCHES_PATTERN {
            pattern_id: $pattern_id,
            confidence: $confidence
        }]->(to_node)
        RETURN properties(r) as props
        """
        result = self.db.execute_query(query, edge.model_dump())
        return result[0]["props"] if result else {}

    def get_arbitrators_by_intent_branch(self, branch_id: str) -> List[Dict[str, Any]]:
        """Get all HumanArbitratorNodes scoped to a specific intent branch."""
        query = """
        MATCH (branch:IntentBranchNode {id: $branch_id})-[:SCOPES]->(h:HumanArbitratorNode)
        RETURN h
        ORDER BY h.timestamp DESC
        """
        result = self.db.execute_query(query, {"branch_id": branch_id})
        return [record["h"] for record in result]

    def get_intent_branch_hierarchy(self, branch_id: str) -> List[Dict[str, Any]]:
        """Get intent branch inheritance chain."""
        query = """
        MATCH path = (child:IntentBranchNode {id: $branch_id})-[:INHERITS_FROM*]->(parent:IntentBranchNode)
        WITH nodes(path) as branch_chain
        UNWIND branch_chain as branch
        RETURN DISTINCT branch
        ORDER BY branch.created_at ASC
        """
        result = self.db.execute_query(query, {"branch_id": branch_id})
        return [record["branch"] for record in result]

    def get_similar_arbitrations(self, arbitrator_id: str, min_confidence: float = 0.7) -> List[Dict[str, Any]]:
        """Get similar arbitrator decisions via MATCHES_PATTERN edges."""
        query = """
        MATCH (current:HumanArbitratorNode {id: $arbitrator_id})-[r:MATCHES_PATTERN]->(similar:HumanArbitratorNode)
        WHERE r.confidence >= $min_confidence
        RETURN similar, r.confidence as confidence, r.pattern_id as pattern_id
        ORDER BY r.confidence DESC
        """
        result = self.db.execute_query(query, {"arbitrator_id": arbitrator_id, "min_confidence": min_confidence})
        return [{
            "arbitrator": record["similar"],
            "confidence": record["confidence"],
            "pattern_id": record["pattern_id"]
        } for record in result]
