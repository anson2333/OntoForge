"""
Create workspace relationships for the Demo Workspace.
"""

import os
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir.parent))

from backend.database import init_db, close_db, get_db
from backend.database.edge_repository import EdgeRepository
from backend.schemas.edges import ContainsPaperEdge, ContainsDomainPackEdge


DEMO_WORKSPACE_ID = "550e8400-e29b-41d4-a716-446655440000"


def main():
    """Main entry point."""
    neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "password")
    
    print("🔧 Creating workspace relationships for Demo Workspace...")
    
    try:
        db = init_db(neo4j_uri, neo4j_user, neo4j_password)
        edge_repo = EdgeRepository(db)
        
        if not db.verify_connectivity():
            print("❌ Failed to connect to Neo4j")
            return 1
        
        # Get all papers for the demo workspace
        get_papers_query = """
        MATCH (p:PaperNode)
        WHERE p.workspace_id = $workspace_id
        RETURN p.id AS paper_id
        """
        papers = db.execute_query(get_papers_query, {'workspace_id': DEMO_WORKSPACE_ID})
        
        print(f"\n📄 Found {len(papers)} papers for Demo Workspace")
        
        created_count = 0
        for paper in papers:
            try:
                edge = ContainsPaperEdge(
                    from_node_id=DEMO_WORKSPACE_ID,
                    to_node_id=paper['paper_id']
                )
                edge_repo.create_contains_paper_edge(edge)
                created_count += 1
                print(f"  ✓ Created relationship: {DEMO_WORKSPACE_ID} -> {paper['paper_id']}")
            except Exception as e:
                if "already exists" in str(e).lower():
                    print(f"  ℹ️  Relationship already exists for paper {paper['paper_id']}")
                else:
                    print(f"  ⚠️  Warning: {e}")
        
        print(f"\n✅ Created {created_count} new CONTAINS_PAPER relationships")
        
        # Verify
        verify_query = """
        MATCH (w:WorkspaceNode {id: $workspace_id})-[:CONTAINS_PAPER]->(p:PaperNode)
        RETURN count(p) AS paper_count
        """
        verify_result = db.execute_query(verify_query, {'workspace_id': DEMO_WORKSPACE_ID})
        if verify_result:
            print(f"✅ Verification: Demo Workspace has {verify_result[0]['paper_count']} paper relationships")
        
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
