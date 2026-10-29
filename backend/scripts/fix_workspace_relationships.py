"""
Fix workspace relationships for existing data.
This script ensures all papers and domains are properly linked to a workspace.
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


DEFAULT_WORKSPACE_ID = "workspace_default_migration"


def main():
    """Main entry point."""
    neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "password")
    
    print("🔧 Fixing workspace relationships...")
    
    try:
        db = init_db(neo4j_uri, neo4j_user, neo4j_password)
        edge_repo = EdgeRepository(db)
        
        if not db.verify_connectivity():
            print("❌ Failed to connect to Neo4j")
            return 1
        
        # Check current state
        check_query = """
        MATCH (p:PaperNode)
        RETURN 
            count(p) AS total_papers,
            count(p.workspace_id) AS papers_with_workspace,
            collect(DISTINCT p.workspace_id)[0..5] AS sample_workspace_ids
        """
        result = db.execute_query(check_query)
        if result:
            print(f"\n📊 Current state:")
            print(f"  - Total papers: {result[0]['total_papers']}")
            print(f"  - Papers with workspace_id: {result[0]['papers_with_workspace']}")
            print(f"  - Sample workspace_ids: {result[0]['sample_workspace_ids']}")
        
        # Check if default workspace exists
        workspace_check = """
        MATCH (w:WorkspaceNode)
        RETURN w.id AS id, w.name AS name
        """
        workspaces = db.execute_query(workspace_check)
        print(f"\n🏢 Existing workspaces:")
        for ws in workspaces:
            print(f"  - {ws['id']}: {ws['name']}")
        
        # Get the first workspace ID (could be the demo one)
        target_workspace_id = workspaces[0]['id'] if workspaces else DEFAULT_WORKSPACE_ID
        print(f"\n🎯 Using workspace: {target_workspace_id}")
        
        # Update papers without workspace_id
        update_papers_query = """
        MATCH (p:PaperNode)
        WHERE p.workspace_id IS NULL
        SET p.workspace_id = $workspace_id
        RETURN count(p) AS updated_count
        """
        result = db.execute_query(update_papers_query, {'workspace_id': target_workspace_id})
        if result:
            print(f"  ✓ Updated {result[0]['updated_count']} papers with workspace_id")
        
        # Get all papers for this workspace and create edges
        get_papers_query = """
        MATCH (p:PaperNode {workspace_id: $workspace_id})
        RETURN p.id AS paper_id
        """
        papers = db.execute_query(get_papers_query, {'workspace_id': target_workspace_id})
        
        created_count = 0
        for paper in papers:
            # Check if edge already exists
            check_edge_query = """
            MATCH (w:WorkspaceNode {id: $workspace_id})-[r:CONTAINS_PAPER]->(p:PaperNode {id: $paper_id})
            RETURN count(r) AS count
            """
            edge_exists = db.execute_query(check_edge_query, {
                'workspace_id': target_workspace_id,
                'paper_id': paper['paper_id']
            })
            
            if not edge_exists or edge_exists[0]['count'] == 0:
                try:
                    edge = ContainsPaperEdge(
                        from_node_id=target_workspace_id,
                        to_node_id=paper['paper_id']
                    )
                    edge_repo.create_contains_paper_edge(edge)
                    created_count += 1
                except Exception as e:
                    print(f"  ⚠️  Warning creating edge for paper {paper['paper_id']}: {e}")
        
        print(f"  ✓ Created {created_count} CONTAINS_PAPER relationships")
        
        # Also create CONTAINS_DOMAIN_PACK edges if domains exist
        get_domains_query = """
        MATCH (d:DomainNode)
        RETURN d.id AS domain_id
        """
        domains = db.execute_query(get_domains_query)
        
        if domains:
            domain_count = 0
            for domain in domains:
                check_edge_query = """
                MATCH (w:WorkspaceNode {id: $workspace_id})-[r:CONTAINS_DOMAIN_PACK]->(d:DomainNode {id: $domain_id})
                RETURN count(r) AS count
                """
                edge_exists = db.execute_query(check_edge_query, {
                    'workspace_id': target_workspace_id,
                    'domain_id': domain['domain_id']
                })
                
                if not edge_exists or edge_exists[0]['count'] == 0:
                    try:
                        edge = ContainsDomainPackEdge(
                            from_node_id=target_workspace_id,
                            to_node_id=domain['domain_id']
                        )
                        edge_repo.create_contains_domain_pack_edge(edge)
                        domain_count += 1
                    except Exception as e:
                        print(f"  ⚠️  Warning creating edge for domain {domain['domain_id']}: {e}")
            
            print(f"  ✓ Created {domain_count} CONTAINS_DOMAIN_PACK relationships")
        
        # Verify
        verify_query = """
        MATCH (w:WorkspaceNode)-[:CONTAINS_PAPER]->(p:PaperNode)
        RETURN w.id AS workspace_id, count(p) AS paper_count
        """
        verify_result = db.execute_query(verify_query)
        print(f"\n✅ Verification:")
        for row in verify_result:
            print(f"  - Workspace {row['workspace_id']}: {row['paper_count']} papers")
        
        print("\n✅ Workspace relationships fixed!")
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
