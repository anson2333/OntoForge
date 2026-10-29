"""
Neo4j Repository Layer for Node Operations
Provides CRUD operations for all graph node types.
"""

from typing import Dict, Any, List, Optional
import json
from backend.database.connection import Neo4jConnection
from backend.schemas.nodes import (
    WorkspaceNode,
    DomainNode,
    PaperNode,
    ChunkNode,
    FormulaNode,
    AssertionNode,
    HumanArbitratorNode,
    IntentBranchNode,
)


class NodeRepository:
    """Repository for node CRUD operations."""

    def __init__(self, db: Neo4jConnection):
        """
        Initialize node repository.

        Args:
            db: Neo4j connection instance
        """
        self.db = db

    def create_domain_node(self, node: DomainNode) -> Dict[str, Any]:
        """
        Create a DomainNode in the graph.

        Args:
            node: DomainNode instance

        Returns:
            Created node data
        """
        query = """
        CREATE (d:DomainNode {
            id: $id,
            name: $name,
            domain_pack_id: $domain_pack_id,
            domain_pack_version: $domain_pack_version,
            taxonomy_tree: $taxonomy_tree,
            core_metrics: $core_metrics,
            approval_status: $approval_status
        })
        RETURN d
        """
        # Convert complex types to JSON strings for Neo4j storage
        node_data = node.model_dump()
        node_data["taxonomy_tree"] = json.dumps(node_data["taxonomy_tree"])
        node_data["core_metrics"] = json.dumps(node_data["core_metrics"])
        
        result = self.db.execute_query(query, node_data)
        
        # Convert JSON strings back to dictionaries/lists in the result
        if result and "d" in result[0]:
            result_node = result[0]["d"]
            if "taxonomy_tree" in result_node:
                result_node["taxonomy_tree"] = json.loads(result_node["taxonomy_tree"])
            if "core_metrics" in result_node:
                result_node["core_metrics"] = json.loads(result_node["core_metrics"])
            return result_node
        return {}

    def create_workspace_node(self, node: WorkspaceNode) -> Dict[str, Any]:
        """
        Create a WorkspaceNode in the graph.

        Args:
            node: WorkspaceNode instance

        Returns:
            Created node data
        """
        query = """
        CREATE (w:WorkspaceNode {
            id: $id,
            name: $name,
            description: $description,
            root_path: $root_path,
            created_at: $created_at,
            last_modified_at: $last_modified_at,
            status: $status,
            owner_id: $owner_id,
            metadata: $metadata
        })
        RETURN w
        """
        node_data = node.model_dump()
        node_data["created_at"] = node_data["created_at"].isoformat()
        node_data["last_modified_at"] = node_data["last_modified_at"].isoformat()
        node_data["metadata"] = json.dumps(node_data["metadata"])

        result = self.db.execute_query(query, node_data)
        return self._deserialize_workspace_record(result[0]["w"]) if result else {}

    def get_workspace_node(self, workspace_id: str) -> Dict[str, Any]:
        query = """
        MATCH (w:WorkspaceNode {id: $workspace_id})
        RETURN w
        LIMIT 1
        """
        result = self.db.execute_query(query, {"workspace_id": workspace_id})
        return self._deserialize_workspace_record(result[0]["w"]) if result else {}

    def list_workspace_nodes(self) -> List[Dict[str, Any]]:
        query = """
        MATCH (w:WorkspaceNode)
        RETURN w
        ORDER BY w.last_modified_at DESC, w.created_at DESC, w.name ASC
        """
        result = self.db.execute_query(query)
        return [self._deserialize_workspace_record(record["w"]) for record in result if "w" in record]

    def delete_workspace_node(self, workspace_id: str) -> bool:
        """
        Delete a WorkspaceNode and all its related nodes (papers, assertions, etc.).

        Args:
            workspace_id: Workspace ID to delete

        Returns:
            True if deletion was successful
        """
        query = """
        MATCH (w:WorkspaceNode {id: $workspace_id})
        OPTIONAL MATCH (w)-[r1*]-(related)
        DETACH DELETE w, related
        RETURN count(w) as deleted_count
        """
        result = self.db.execute_query(query, {"workspace_id": workspace_id})
        return result[0]["deleted_count"] > 0 if result else False

    def _deserialize_workspace_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        workspace = dict(record)
        if "metadata" in workspace and isinstance(workspace["metadata"], str):
            workspace["metadata"] = json.loads(workspace["metadata"])
        return workspace

    def create_paper_node(self, node: PaperNode) -> Dict[str, Any]:
        """
        Create a PaperNode in the graph.

        Args:
            node: PaperNode instance

        Returns:
            Created node data
        """
        query = """
        CREATE (p:PaperNode {
            id: $id,
            doi: $doi,
            title: $title,
            authors: $authors,
            year: $year,
            venue: $venue,
            provenance_hash: $provenance_hash,
            import_status: $import_status,
            domain_pack_namespace: $domain_pack_namespace,
            workspace_id: $workspace_id
        })
        RETURN p
        """
        result = self.db.execute_query(query, node.model_dump())
        return result[0]["p"] if result else {}

    def create_chunk_node(self, node: ChunkNode) -> Dict[str, Any]:
        """
        Create a ChunkNode in the graph.

        Args:
            node: ChunkNode instance

        Returns:
            Created node data
        """
        query = """
        CREATE (c:ChunkNode {
            id: $id,
            raw_text: $raw_text,
            bounding_box: $bounding_box,
            verification_status: $verification_status,
            last_modified_by: $last_modified_by,
            last_modified_at: $last_modified_at,
            modification_count: $modification_count
        })
        RETURN c
        """
        # Convert complex types to JSON strings for Neo4j storage
        node_data = node.model_dump()
        node_data["bounding_box"] = json.dumps(node_data["bounding_box"])
        
        result = self.db.execute_query(query, node_data)
        
        # Convert JSON strings back to dictionaries in the result
        if result and "c" in result[0]:
            result_node = result[0]["c"]
            if "bounding_box" in result_node:
                result_node["bounding_box"] = json.loads(result_node["bounding_box"])
            return result_node
        return {}

    def create_formula_node(self, node: FormulaNode) -> Dict[str, Any]:
        """
        Create a FormulaNode in the graph.

        Args:
            node: FormulaNode instance

        Returns:
            Created node data
        """
        query = """
        CREATE (f:FormulaNode {
            id: $id,
            latex_string: $latex_string,
            variables_map: $variables_map,
            constraints: $constraints,
            verification_status: $verification_status,
            last_modified_by: $last_modified_by,
            last_modified_at: $last_modified_at,
            modification_count: $modification_count
        })
        RETURN f
        """
        # Convert complex types to JSON strings for Neo4j storage
        node_data = node.model_dump()
        node_data["variables_map"] = json.dumps(node_data["variables_map"])
        node_data["constraints"] = json.dumps(node_data["constraints"])
        
        result = self.db.execute_query(query, node_data)
        
        # Convert JSON strings back to dictionaries/lists in the result
        if result and "f" in result[0]:
            result_node = result[0]["f"]
            if "variables_map" in result_node:
                result_node["variables_map"] = json.loads(result_node["variables_map"])
            if "constraints" in result_node:
                result_node["constraints"] = json.loads(result_node["constraints"])
            return result_node
        return {}

    def create_assertion_node(self, node: AssertionNode) -> Dict[str, Any]:
        """
        Create an AssertionNode in the graph.

        Args:
            node: AssertionNode instance

        Returns:
            Created node data
        """
        query = """
        CREATE (a:AssertionNode {
            id: $id,
            subject: $subject,
            predicate: $predicate,
            object: $object,
            unit: $unit,
            domain_pack_namespace: $domain_pack_namespace,
            context_conditions: $context_conditions,
            status: $status,
            workspace_id: $workspace_id
        })
        RETURN a
        """
        # Convert complex types to JSON strings for Neo4j storage
        node_data = node.model_dump()
        node_data["context_conditions"] = json.dumps(node_data["context_conditions"])
        
        result = self.db.execute_query(query, node_data)
        
        # Convert JSON strings back to dictionaries in the result
        if result and "a" in result[0]:
            result_node = result[0]["a"]
            if "context_conditions" in result_node:
                result_node["context_conditions"] = json.loads(result_node["context_conditions"])
            return result_node
        return {}

    def create_arbitrator_node(self, node: HumanArbitratorNode) -> Dict[str, Any]:
        """
        Create a HumanArbitratorNode in the graph with intent support.

        Args:
            node: HumanArbitratorNode instance

        Returns:
            Created node data
        """
        query = """
        CREATE (h:HumanArbitratorNode {
            id: $id,
            user_id: $user_id,
            timestamp: $timestamp,
            arbitration_notes: $arbitration_notes,
            lock_type: $lock_type,
            intent_type: $intent_type,
            intent_scope: $intent_scope,
            generalization_hint: $generalization_hint,
            confidence_override: $confidence_override,
            intent_branch_id: $intent_branch_id,
            declaration_constraints: $declaration_constraints,
            tags: $tags
        })
        RETURN h
        """
        node_data = node.model_dump()
        if node_data["declaration_constraints"] is not None:
            node_data["declaration_constraints"] = json.dumps(node_data["declaration_constraints"])

        result = self.db.execute_query(query, node_data)
        if result and "h" in result[0]:
            return self._deserialize_arbitrator_record(result[0]["h"])
        return {}

    def _deserialize_arbitrator_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        arbitrator = dict(record)
        if "declaration_constraints" in arbitrator and isinstance(arbitrator["declaration_constraints"], str):
            arbitrator["declaration_constraints"] = json.loads(arbitrator["declaration_constraints"])
        return arbitrator

    def get_node_by_id(self, node_id: str, node_label: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a node by its ID.

        Args:
            node_id: Node ID
            node_label: Node type label (e.g., "DomainNode", "PaperNode")

        Returns:
            Node data if found, None otherwise
        """
        query = f"""
        MATCH (n:{node_label} {{id: $node_id}})
        RETURN n
        """
        result = self.db.execute_query(query, {"node_id": node_id})
        return result[0]["n"] if result else None

    def update_node(
        self, node_id: str, node_label: str, updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update node properties.

        Args:
            node_id: Node ID
            node_label: Node type label
            updates: Dictionary of properties to update

        Returns:
            Updated node data
        """
        # Build SET clause dynamically
        set_clauses = [f"n.{key} = ${key}" for key in updates.keys()]
        set_clause = ", ".join(set_clauses)

        query = f"""
        MATCH (n:{node_label} {{id: $node_id}})
        SET {set_clause}
        RETURN n
        """
        params = {"node_id": node_id, **updates}
        result = self.db.execute_query(query, params)
        return result[0]["n"] if result else {}

    def delete_node(self, node_id: str, node_label: str) -> bool:
        """
        Delete a node and all its relationships.

        Args:
            node_id: Node ID
            node_label: Node type label

        Returns:
            True if deleted, False if not found
        """
        query = f"""
        MATCH (n:{node_label} {{id: $node_id}})
        DETACH DELETE n
        RETURN count(n) as deleted_count
        """
        result = self.db.execute_query(query, {"node_id": node_id})
        return result[0]["deleted_count"] > 0 if result else False

    def get_nodes_by_label(
        self, node_label: str, limit: int = 100, skip: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get all nodes of a specific type with pagination.

        Args:
            node_label: Node type label
            limit: Maximum number of nodes to return
            skip: Number of nodes to skip

        Returns:
            List of node data
        """
        query = f"""
        MATCH (n:{node_label})
        RETURN n
        SKIP $skip
        LIMIT $limit
        """
        result = self.db.execute_query(query, {"skip": skip, "limit": limit})
        return [record["n"] for record in result]

    def count_nodes_by_label(self, node_label: str) -> int:
        """
        Count nodes of a specific type.

        Args:
            node_label: Node type label

        Returns:
            Node count
        """
        query = f"""
        MATCH (n:{node_label})
        RETURN count(n) as count
        """
        result = self.db.execute_query(query)
        return result[0]["count"] if result else 0

    # ========================================================================
    # IntentBranchNode CRUD Operations (Section 2.6.5)
    # ========================================================================

    def create_intent_branch_node(self, node: IntentBranchNode) -> Dict[str, Any]:
        """
        Create an IntentBranchNode for research context isolation.

        Args:
            node: IntentBranchNode instance

        Returns:
            Created node data
        """
        query = """
        CREATE (i:IntentBranchNode {
            id: $id,
            branch_name: $branch_name,
            description: $description,
            user_id: $user_id,
            parent_branch_id: $parent_branch_id,
            created_at: $created_at,
            active_until: $active_until,
            status: $status,
            overrides: $overrides
        })
        RETURN i
        """
        node_data = node.model_dump()
        node_data["overrides"] = json.dumps(node_data["overrides"])
        
        result = self.db.execute_query(query, node_data)
        
        if result and "i" in result[0]:
            result_node = result[0]["i"]
            if "overrides" in result_node:
                result_node["overrides"] = json.loads(result_node["overrides"])
            return result_node
        return {}

    def get_intent_branch(self, branch_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve an IntentBranchNode by ID.

        Args:
            branch_id: Intent branch ID

        Returns:
            Branch data if found, None otherwise
        """
        query = """
        MATCH (i:IntentBranchNode {id: $branch_id})
        RETURN i
        """
        result = self.db.execute_query(query, {"branch_id": branch_id})
        
        if result and "i" in result[0]:
            branch = result[0]["i"]
            if "overrides" in branch:
                branch["overrides"] = json.loads(branch["overrides"])
            return branch
        return None

    def get_active_intent_branches(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get all active intent branches for a user.

        Args:
            user_id: User identifier

        Returns:
            List of active branch data
        """
        query = """
        MATCH (i:IntentBranchNode {user_id: $user_id, status: 'active'})
        RETURN i
        ORDER BY i.created_at DESC
        """
        result = self.db.execute_query(query, {"user_id": user_id})
        
        branches = []
        for record in result:
            branch = record["i"]
            if "overrides" in branch:
                branch["overrides"] = json.loads(branch["overrides"])
            branches.append(branch)
        return branches

    def update_intent_branch_status(
        self,
        branch_id: str,
        status: str
    ) -> Dict[str, Any]:
        """
        Update intent branch status (active, archived, completed).

        Args:
            branch_id: Intent branch ID
            status: New status value

        Returns:
            Updated branch data
        """
        query = """
        MATCH (i:IntentBranchNode {id: $branch_id})
        SET i.status = $status
        RETURN i
        """
        result = self.db.execute_query(query, {"branch_id": branch_id, "status": status})
        
        if result and "i" in result[0]:
            branch = result[0]["i"]
            if "overrides" in branch:
                branch["overrides"] = json.loads(branch["overrides"])
            return branch
        return {}

    def delete_intent_branch(self, branch_id: str) -> bool:
        """
        Delete an intent branch and all associated SCOPES edges.

        Args:
            branch_id: Intent branch ID

        Returns:
            True if deleted, False if not found
        """
        query = """
        MATCH (i:IntentBranchNode {id: $branch_id})
        DETACH DELETE i
        RETURN count(i) as deleted_count
        """
        result = self.db.execute_query(query, {"branch_id": branch_id})
        return result[0]["deleted_count"] > 0 if result else False

    def execute_query(self, query: str, parameters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Execute arbitrary Cypher query (for intent learning engine).

        Args:
            query: Cypher query string
            parameters: Query parameters

        Returns:
            Query results
        """
        return self.db.execute_query(query, parameters)
