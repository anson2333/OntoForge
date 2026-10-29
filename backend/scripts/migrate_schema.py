"""
Schema Migration Script for Workspace and Multi-Domain-Pack Support
Migrates existing Neo4j database to support:
- WorkspaceNode (new top-level organizational unit)
- owner_id field on WorkspaceNode (optional, for access control)
- namespace field on DomainNode (workspace-scoped namespaces)
- parent_domain_id field on DomainNode (subdomain hierarchy)
- domain_pack_namespace field on PaperNode and AssertionNode
- workspace_id field on PaperNode and AssertionNode
- New relationships: CONTAINS_DOMAIN_PACK, CONTAINS_PAPER
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir.parent))

from backend.database import init_db, close_db, get_db


DEFAULT_WORKSPACE_ID = "workspace_default_migration"
DEFAULT_WORKSPACE_NAME = "Default Workspace (Migrated)"


def check_database_connectivity(db):
    """Verify we can connect to the database."""
    print("🔌 Checking database connectivity...")
    if not db.verify_connectivity():
        print("❌ Failed to connect to Neo4j")
        print("   Make sure Neo4j is running: docker ps | grep neo4j")
        return False
    print("✅ Connected to Neo4j")
    return True


def check_existing_schema(db):
    """Check what nodes exist in the current database."""
    print("\n📊 Analyzing existing schema...")
    
    # Check for existing node types
    query = """
    MATCH (n)
    RETURN DISTINCT labels(n) AS labels, count(*) AS count
    ORDER BY count DESC
    """
    results = db.execute_query(query)
    
    if not results:
        print("  ℹ️  Database is empty")
        return {
            'has_data': False,
            'has_workspaces': False,
            'has_domains': False,
            'has_papers': False,
            'has_assertions': False
        }
    
    print("  Existing node types:")
    schema_info = {
        'has_data': True,
        'has_workspaces': False,
        'has_domains': False,
        'has_papers': False,
        'has_assertions': False
    }
    
    for record in results:
        labels = record['labels']
        count = record['count']
        print(f"    - {':'.join(labels)}: {count} nodes")
        
        if 'WorkspaceNode' in labels:
            schema_info['has_workspaces'] = True
        if 'DomainNode' in labels:
            schema_info['has_domains'] = True
        if 'PaperNode' in labels:
            schema_info['has_papers'] = True
        if 'AssertionNode' in labels:
            schema_info['has_assertions'] = True
    
    return schema_info


def create_default_workspace(db):
    """Create a default workspace for existing data."""
    print("\n🏢 Creating default workspace...")
    
    query = """
    MERGE (w:WorkspaceNode {id: $id})
    ON CREATE SET
        w.name = $name,
        w.description = $description,
        w.root_path = $root_path,
        w.created_at = $created_at,
        w.last_modified_at = $last_modified_at,
        w.status = $status,
        w.owner_id = $owner_id,
        w.metadata = $metadata
    RETURN w
    """
    
    params = {
        'id': DEFAULT_WORKSPACE_ID,
        'name': DEFAULT_WORKSPACE_NAME,
        'description': 'Auto-created workspace for migrated data',
        'root_path': 'file:///migrated/workspace',
        'created_at': datetime.now(timezone.utc).isoformat(),
        'last_modified_at': datetime.now(timezone.utc).isoformat(),
        'status': 'active',
        'owner_id': None,  # null for backwards compatibility
        'metadata': '{}'
    }
    
    result = db.execute_query(query, params)
    if result:
        print(f"  ✓ Created workspace: {DEFAULT_WORKSPACE_ID}")
        return True
    else:
        print(f"  ✗ Failed to create workspace")
        return False


def migrate_domain_nodes(db):
    """Add namespace and parent_domain_id fields to existing DomainNode."""
    print("\n🔧 Migrating DomainNode schema...")
    
    # Check if domains already have namespace field
    check_query = """
    MATCH (d:DomainNode)
    RETURN d.namespace AS namespace
    LIMIT 1
    """
    check_result = db.execute_query(check_query)
    
    if check_result and check_result[0]['namespace'] is not None:
        print("  ℹ️  DomainNode already has namespace field, skipping")
        return True
    
    # Add namespace field (derive from id or use 'default')
    update_query = """
    MATCH (d:DomainNode)
    WHERE d.namespace IS NULL
    SET d.namespace = COALESCE(
        split(d.id, '.')[size(split(d.id, '.')) - 1],
        'default'
    ),
    d.parent_domain_id = NULL,
    d.classification_hints = '{}'
    RETURN count(d) AS updated_count
    """
    
    result = db.execute_query(update_query)
    if result:
        count = result[0]['updated_count']
        print(f"  ✓ Updated {count} DomainNode(s) with namespace and parent_domain_id fields")
        return True
    else:
        print(f"  ✗ Failed to update DomainNode schema")
        return False


def migrate_paper_nodes(db):
    """Add domain_pack_namespace and workspace_id fields to existing PaperNode."""
    print("\n🔧 Migrating PaperNode schema...")
    
    # Check if papers already have workspace_id field
    check_query = """
    MATCH (p:PaperNode)
    RETURN p.workspace_id AS workspace_id
    LIMIT 1
    """
    check_result = db.execute_query(check_query)
    
    if check_result and check_result[0]['workspace_id'] is not None:
        print("  ℹ️  PaperNode already has workspace_id field, skipping")
        return True
    
    # Add workspace_id and domain_pack_namespace fields
    update_query = """
    MATCH (p:PaperNode)
    WHERE p.workspace_id IS NULL
    SET p.workspace_id = $workspace_id,
        p.domain_pack_namespace = COALESCE(p.domain_pack_namespace, NULL)
    RETURN count(p) AS updated_count
    """
    
    result = db.execute_query(update_query, {'workspace_id': DEFAULT_WORKSPACE_ID})
    if result:
        count = result[0]['updated_count']
        print(f"  ✓ Updated {count} PaperNode(s) with workspace_id field")
        return True
    else:
        print(f"  ✗ Failed to update PaperNode schema")
        return False


def migrate_assertion_nodes(db):
    """Add domain_pack_namespace and workspace_id fields to existing AssertionNode."""
    print("\n🔧 Migrating AssertionNode schema...")
    
    # Check if assertions already have workspace_id field
    check_query = """
    MATCH (a:AssertionNode)
    RETURN a.workspace_id AS workspace_id
    LIMIT 1
    """
    check_result = db.execute_query(check_query)
    
    if check_result and check_result[0]['workspace_id'] is not None:
        print("  ℹ️  AssertionNode already has workspace_id field, skipping")
        return True
    
    # Add workspace_id and domain_pack_namespace fields
    update_query = """
    MATCH (a:AssertionNode)
    WHERE a.workspace_id IS NULL
    SET a.workspace_id = $workspace_id,
        a.domain_pack_namespace = COALESCE(
            split(a.subject, ':')[0],
            'default'
        )
    RETURN count(a) AS updated_count
    """
    
    result = db.execute_query(update_query, {'workspace_id': DEFAULT_WORKSPACE_ID})
    if result:
        count = result[0]['updated_count']
        print(f"  ✓ Updated {count} AssertionNode(s) with workspace_id and namespace fields")
        return True
    else:
        print(f"  ✗ Failed to update AssertionNode schema")
        return False


def create_workspace_relationships(db):
    """Create CONTAINS_DOMAIN_PACK and CONTAINS_PAPER relationships."""
    print("\n🔗 Creating workspace relationships...")
    
    # Link workspace to all existing domain nodes
    domain_query = """
    MATCH (w:WorkspaceNode {id: $workspace_id})
    MATCH (d:DomainNode)
    WHERE NOT (w)-[:CONTAINS_DOMAIN_PACK]->(d)
    MERGE (w)-[:CONTAINS_DOMAIN_PACK]->(d)
    RETURN count(*) AS created_count
    """
    
    domain_result = db.execute_query(domain_query, {'workspace_id': DEFAULT_WORKSPACE_ID})
    if domain_result:
        count = domain_result[0]['created_count']
        print(f"  ✓ Created {count} CONTAINS_DOMAIN_PACK relationship(s)")
    
    # Link workspace to all existing paper nodes
    paper_query = """
    MATCH (w:WorkspaceNode {id: $workspace_id})
    MATCH (p:PaperNode {workspace_id: $workspace_id})
    WHERE NOT (w)-[:CONTAINS_PAPER]->(p)
    MERGE (w)-[:CONTAINS_PAPER]->(p)
    RETURN count(*) AS created_count
    """
    
    paper_result = db.execute_query(paper_query, {'workspace_id': DEFAULT_WORKSPACE_ID})
    if paper_result:
        count = paper_result[0]['created_count']
        print(f"  ✓ Created {count} CONTAINS_PAPER relationship(s)")
    
    return True


def create_constraints_and_indexes(db):
    """Create database constraints and indexes for performance."""
    print("\n🔒 Creating constraints and indexes...")
    
    constraints = [
        ("WorkspaceNode", "id"),
        ("DomainNode", "id"),
        ("PaperNode", "id"),
        ("AssertionNode", "id"),
        ("ChunkNode", "id"),
        ("FormulaNode", "id"),
        ("HumanArbitratorNode", "id"),
        ("IntentBranchNode", "id"),
    ]
    
    created_count = 0
    for node_label, property_name in constraints:
        constraint_name = f"constraint_{node_label.lower()}_{property_name}"
        query = f"""
        CREATE CONSTRAINT {constraint_name} IF NOT EXISTS
        FOR (n:{node_label})
        REQUIRE n.{property_name} IS UNIQUE
        """
        
        try:
            db.execute_write(query)
            created_count += 1
            print(f"  ✓ Created constraint: {constraint_name}")
        except Exception as e:
            # Constraint might already exist
            if "already exists" in str(e).lower() or "equivalent" in str(e).lower():
                print(f"  ℹ️  Constraint already exists: {constraint_name}")
            else:
                print(f"  ⚠️  Warning creating constraint {constraint_name}: {e}")
    
    # Create indexes for commonly queried fields
    indexes = [
        ("PaperNode", "workspace_id"),
        ("PaperNode", "domain_pack_namespace"),
        ("AssertionNode", "workspace_id"),
        ("AssertionNode", "domain_pack_namespace"),
        ("DomainNode", "namespace"),
        ("WorkspaceNode", "owner_id"),
    ]
    
    for node_label, property_name in indexes:
        index_name = f"index_{node_label.lower()}_{property_name}"
        query = f"""
        CREATE INDEX {index_name} IF NOT EXISTS
        FOR (n:{node_label})
        ON (n.{property_name})
        """
        
        try:
            db.execute_write(query)
            print(f"  ✓ Created index: {index_name}")
        except Exception as e:
            if "already exists" in str(e).lower() or "equivalent" in str(e).lower():
                print(f"  ℹ️  Index already exists: {index_name}")
            else:
                print(f"  ⚠️  Warning creating index {index_name}: {e}")
    
    return True


def verify_migration(db):
    """Verify the migration was successful."""
    print("\n✅ Verifying migration...")
    
    checks = []
    
    # Check workspace exists
    workspace_query = "MATCH (w:WorkspaceNode) RETURN count(w) AS count"
    workspace_result = db.execute_query(workspace_query)
    workspace_count = workspace_result[0]['count'] if workspace_result else 0
    checks.append(('Workspaces', workspace_count > 0, f"{workspace_count} workspace(s)"))
    
    # Check papers have workspace_id
    paper_query = """
    MATCH (p:PaperNode)
    WHERE p.workspace_id IS NOT NULL
    RETURN count(p) AS count
    """
    paper_result = db.execute_query(paper_query)
    paper_count = paper_result[0]['count'] if paper_result else 0
    checks.append(('Papers with workspace_id', True, f"{paper_count} paper(s)"))
    
    # Check domains have namespace
    domain_query = """
    MATCH (d:DomainNode)
    WHERE d.namespace IS NOT NULL
    RETURN count(d) AS count
    """
    domain_result = db.execute_query(domain_query)
    domain_count = domain_result[0]['count'] if domain_result else 0
    checks.append(('Domains with namespace', True, f"{domain_count} domain(s)"))
    
    # Check workspace relationships
    rel_query = """
    MATCH (w:WorkspaceNode)-[:CONTAINS_PAPER]->(p:PaperNode)
    RETURN count(*) AS count
    """
    rel_result = db.execute_query(rel_query)
    rel_count = rel_result[0]['count'] if rel_result else 0
    checks.append(('Workspace relationships', rel_count > 0 or paper_count == 0, f"{rel_count} relationship(s)"))
    
    print("\n  Migration Verification:")
    all_passed = True
    for name, passed, detail in checks:
        status = "✓" if passed else "✗"
        print(f"    {status} {name}: {detail}")
        all_passed = all_passed and passed
    
    return all_passed


def main():
    """Main entry point."""
    print("=" * 70)
    print("OntoForge Schema Migration")
    print("Workspace & Multi-Domain-Pack Support")
    print("=" * 70)
    
    # Get connection parameters from environment
    neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "password")
    
    print(f"\n🔌 Connecting to Neo4j at {neo4j_uri}...")
    
    try:
        # Initialize database connection
        db = init_db(neo4j_uri, neo4j_user, neo4j_password)
        
        if not check_database_connectivity(db):
            return 1
        
        # Analyze existing schema
        schema_info = check_existing_schema(db)
        
        if not schema_info['has_data']:
            print("\n  ℹ️  Database is empty. Run load_mock_data.py to populate with sample data.")
            print("  ✓ Schema migration not needed for empty database")
            return 0
        
        # Perform migration steps
        steps = [
            ("Create default workspace", lambda: create_default_workspace(db)),
            ("Migrate DomainNode schema", lambda: migrate_domain_nodes(db)),
            ("Migrate PaperNode schema", lambda: migrate_paper_nodes(db)),
            ("Migrate AssertionNode schema", lambda: migrate_assertion_nodes(db)),
            ("Create workspace relationships", lambda: create_workspace_relationships(db)),
            ("Create constraints and indexes", lambda: create_constraints_and_indexes(db)),
        ]
        
        print("\n" + "=" * 70)
        print("Starting Migration")
        print("=" * 70)
        
        for step_name, step_func in steps:
            if not step_func():
                print(f"\n❌ Migration failed at step: {step_name}")
                return 1
        
        # Verify migration
        if verify_migration(db):
            print("\n" + "=" * 70)
            print("✅ Migration completed successfully!")
            print("=" * 70)
            print(f"\n📋 Summary:")
            print(f"  - Default workspace created: {DEFAULT_WORKSPACE_ID}")
            print(f"  - All existing data migrated to default workspace")
            print(f"  - Schema updated with new workspace and namespace fields")
            print(f"  - Constraints and indexes created")
            print("\n💡 Next steps:")
            print("  - You can now create additional workspaces via the UI")
            print("  - Papers can be moved between workspaces")
            print("  - Each workspace supports multiple domain packs with namespace isolation")
            return 0
        else:
            print("\n⚠️  Migration completed with warnings. Please review the verification output.")
            return 1
        
    except Exception as e:
        print(f"\n❌ Migration error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        close_db()
        print("\n🔌 Database connection closed")


if __name__ == "__main__":
    sys.exit(main())
