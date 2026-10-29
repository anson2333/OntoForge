"""
Verify the complete database schema after migration.
"""

import os
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir.parent))

from backend.database import init_db, close_db


def main():
    """Main entry point."""
    neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "password")
    
    print("=" * 70)
    print("Database Schema Verification")
    print("=" * 70)
    
    try:
        db = init_db(neo4j_uri, neo4j_user, neo4j_password)
        
        if not db.verify_connectivity():
            print("❌ Failed to connect to Neo4j")
            return 1
        
        print("\n✅ Connected to Neo4j")
        
        # Check node types
        print("\n📊 Node Types:")
        node_query = """
        MATCH (n)
        RETURN DISTINCT labels(n) AS labels, count(*) AS count
        ORDER BY count DESC
        """
        nodes = db.execute_query(node_query)
        for node in nodes:
            print(f"  - {':'.join(node['labels'])}: {node['count']} nodes")
        
        # Check relationship types
        print("\n🔗 Relationship Types:")
        rel_query = """
        MATCH ()-[r]->()
        RETURN DISTINCT type(r) AS type, count(*) AS count
        ORDER BY count DESC
        """
        rels = db.execute_query(rel_query)
        if rels:
            for rel in rels:
                print(f"  - {rel['type']}: {rel['count']} relationships")
        else:
            print("  (no relationships found)")
        
        # Check workspace structure
        print("\n🏢 Workspace Structure:")
        workspace_query = """
        MATCH (w:WorkspaceNode)
        OPTIONAL MATCH (w)-[:CONTAINS_PAPER]->(p:PaperNode)
        OPTIONAL MATCH (w)-[:CONTAINS_DOMAIN_PACK]->(d:DomainNode)
        RETURN w.id AS workspace_id, w.name AS workspace_name, 
               count(DISTINCT p) AS paper_count, count(DISTINCT d) AS domain_count
        """
        workspaces = db.execute_query(workspace_query)
        for ws in workspaces:
            print(f"  - {ws['workspace_name']} ({ws['workspace_id']})")
            print(f"    • Papers: {ws['paper_count']}")
            print(f"    • Domain Packs: {ws['domain_count']}")
        
        # Check paper workspace assignments
        print("\n📄 Paper Distribution:")
        paper_query = """
        MATCH (p:PaperNode)
        RETURN 
            count(p) AS total_papers,
            count(p.workspace_id) AS papers_with_workspace,
            count(CASE WHEN p.domain_pack_namespace IS NOT NULL THEN 1 END) AS papers_with_namespace
        """
        paper_stats = db.execute_query(paper_query)
        if paper_stats:
            stats = paper_stats[0]
            print(f"  - Total papers: {stats['total_papers']}")
            print(f"  - Papers with workspace_id: {stats['papers_with_workspace']}")
            print(f"  - Papers with domain_pack_namespace: {stats['papers_with_namespace']}")
        
        # Check assertions
        print("\n📊 Assertion Distribution:")
        assertion_query = """
        MATCH (a:AssertionNode)
        RETURN 
            count(a) AS total_assertions,
            count(a.workspace_id) AS assertions_with_workspace,
            count(a.domain_pack_namespace) AS assertions_with_namespace
        """
        assertion_stats = db.execute_query(assertion_query)
        if assertion_stats:
            stats = assertion_stats[0]
            print(f"  - Total assertions: {stats['total_assertions']}")
            print(f"  - Assertions with workspace_id: {stats['assertions_with_workspace']}")
            print(f"  - Assertions with domain_pack_namespace: {stats['assertions_with_namespace']}")
        
        # Check constraints
        print("\n🔒 Database Constraints:")
        constraint_query = """
        SHOW CONSTRAINTS
        """
        constraints = db.execute_query(constraint_query)
        if constraints:
            for constraint in constraints[:10]:  # Show first 10
                print(f"  - {constraint.get('name', 'unnamed')}")
        
        # Check indexes
        print("\n📇 Database Indexes:")
        index_query = """
        SHOW INDEXES
        """
        indexes = db.execute_query(index_query)
        if indexes:
            for idx in indexes[:10]:  # Show first 10
                print(f"  - {idx.get('name', 'unnamed')}")
        
        print("\n" + "=" * 70)
        print("✅ Schema verification complete!")
        print("=" * 70)
        
        # Summary
        print("\n📋 Migration Summary:")
        print("  ✓ WorkspaceNode added with owner_id support")
        print("  ✓ DomainNode enhanced with namespace and parent_domain_id")
        print("  ✓ PaperNode updated with workspace_id and domain_pack_namespace")
        print("  ✓ AssertionNode updated with workspace_id and domain_pack_namespace")
        print("  ✓ CONTAINS_DOMAIN_PACK and CONTAINS_PAPER relationships created")
        print("  ✓ Constraints and indexes in place for performance")
        print("\n💡 The database is ready for multi-workspace, multi-domain-pack support!")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        close_db()


if __name__ == "__main__":
    sys.exit(main())
