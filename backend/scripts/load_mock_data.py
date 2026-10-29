"""
Script to load mock papers and assertions into Neo4j database.
Run this script to populate the database with sample data for development.
"""

import os
import sys
import hashlib
import math
from pathlib import Path
from datetime import datetime, timezone

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir.parent))

from backend.database import init_db, close_db, get_db
from backend.database.node_repository import NodeRepository
from backend.database.edge_repository import EdgeRepository
from backend.schemas.nodes import PaperNode, AssertionNode, ChunkNode, WorkspaceNode
from backend.schemas.edges import ContainsEdge, EvidencedByEdge


# Default workspace for mock data (fixed UUID for consistency)
WORKSPACE_ID = "550e8400-e29b-41d4-a716-446655440000"
WORKSPACE_NAME = "Demo Workspace"


# Mock papers data (matching frontend/renderer/services/workspace.ts)
MOCK_PAPERS = [
    {
        'id': 'paper1',
        'doi': '10.1109/JLT.2024.001',
        'title': 'High-Speed Optical Switching in Access Networks',
        'authors': ['Zhang, Wei', 'Liu, Chen'],
        'year': 2024,
        'venue': 'IEEE Journal of Lightwave Technology',
        'domain_pack_namespace': 'optical'
    },
    {
        'id': 'paper2',
        'doi': '10.1109/JLT.2023.456',
        'title': 'Low-Latency Reconfiguration in PON Systems',
        'authors': ['Smith, John', 'Brown, Sarah'],
        'year': 2023,
        'venue': 'IEEE Journal of Lightwave Technology',
        'domain_pack_namespace': 'optical'
    },
    {
        'id': 'paper3',
        'doi': '10.1364/OE.2024.789',
        'title': 'Crosstalk Mitigation in WDM Networks',
        'authors': ['Kumar, Raj', 'Patel, Anita'],
        'year': 2024,
        'venue': 'Optics Express',
        'domain_pack_namespace': 'optical'
    },
    {
        'id': 'paper4',
        'doi': '10.1109/TWC.2024.123',
        'title': 'mmWave Backhaul for Ultra-Dense Networks',
        'authors': ['Lee, Min', 'Park, Jun'],
        'year': 2024,
        'venue': 'IEEE Transactions on Wireless Communications',
        'domain_pack_namespace': 'wireless'
    },
    {
        'id': 'paper5',
        'doi': '10.1109/TCOM.2023.789',
        'title': 'Sub-6GHz Massive MIMO Backhaul',
        'authors': ['Garcia, Maria', 'Silva, Carlos'],
        'year': 2023,
        'venue': 'IEEE Transactions on Communications',
        'domain_pack_namespace': 'wireless'
    },
    {
        'id': 'paper6',
        'doi': '10.1109/JPHOT.2024.345',
        'title': 'Energy-Efficient Optical Circuit Switching',
        'authors': ['Johnson, David', 'Wang, Li'],
        'year': 2024,
        'venue': 'IEEE Photonics Journal',
        'domain_pack_namespace': 'optical'
    },
    {
        'id': 'paper7',
        'doi': '10.1364/OL.2023.567',
        'title': 'Burst Mode Receivers for PON Applications',
        'authors': ['Anderson, Emma', 'Martinez, Jose'],
        'year': 2023,
        'venue': 'Optics Letters',
        'domain_pack_namespace': 'optical'
    },
    {
        'id': 'paper8',
        'doi': '10.1109/JLT.2024.890',
        'title': 'Free-Space Optical Links with Adaptive Optics',
        'authors': ['Chen, Xiaoming', 'Yamamoto, Kenji'],
        'year': 2024,
        'venue': 'IEEE Journal of Lightwave Technology',
        'domain_pack_namespace': 'optical'
    },
    {
        'id': 'paper9',
        'doi': '10.1109/TWC.2023.234',
        'title': 'Terahertz Communications for 6G Networks',
        'authors': ['Nguyen, Thanh', 'Kim, Soo-Young'],
        'year': 2023,
        'venue': 'IEEE Transactions on Wireless Communications',
        'domain_pack_namespace': 'wireless'
    },
    {
        'id': 'paper10',
        'doi': '10.1109/MCOM.2024.456',
        'title': 'Reconfigurable Intelligent Surfaces for mmWave',
        'authors': ['Petrov, Viktor', 'Li, Jing'],
        'year': 2024,
        'venue': 'IEEE Communications Magazine',
        'domain_pack_namespace': 'wireless'
    },
    {
        'id': 'paper11',
        'doi': '10.1364/JOCN.2024.112',
        'title': 'Wavelength Selective Switching for Metro Networks',
        'authors': ["O'Brien, Patrick", 'Schmidt, Anna'],
        'year': 2024,
        'venue': 'Journal of Optical Communications and Networking',
        'domain_pack_namespace': 'optical'
    },
    {
        'id': 'paper12',
        'doi': '10.1109/LCOMM.2023.678',
        'title': 'Full-Duplex Wireless Backhaul Links',
        'authors': ['Rodriguez, Carlos', 'Hassan, Ahmed'],
        'year': 2023,
        'venue': 'IEEE Communications Letters',
        'domain_pack_namespace': 'wireless'
    },
    {
        'id': 'paper13',
        'doi': '10.1109/JLT.2023.901',
        'title': 'Coherent Detection in High-Speed Optical Networks',
        'authors': ['Tanaka, Hiroshi', 'Mueller, Stefan'],
        'year': 2023,
        'venue': 'IEEE Journal of Lightwave Technology',
        'domain_pack_namespace': 'optical'
    },
    {
        'id': 'paper14',
        'doi': '10.1109/TWC.2024.567',
        'title': 'Beamforming Techniques for mmWave Backhaul',
        'authors': ['Wilson, Robert', 'Taylor, Jessica'],
        'year': 2024,
        'venue': 'IEEE Transactions on Wireless Communications',
        'domain_pack_namespace': 'wireless'
    },
    {
        'id': 'paper15',
        'doi': '10.1109/JSAC.2024.789',
        'title': 'Network Slicing in 5G Backhaul Architecture',
        'authors': ['Gomez, Ricardo', 'Zhang, Yifei'],
        'year': 2024,
        'venue': 'IEEE Journal on Selected Areas in Communications',
        'domain_pack_namespace': 'wireless'
    },
    {
        'id': 'paper16',
        'doi': '10.1109/JLT.2025.101',
        'title': 'Programmable Optical Fabrics for Edge Aggregation',
        'authors': ['Singh, Arjun', 'Lopez, Elena'],
        'year': 2025,
        'venue': 'IEEE Journal of Lightwave Technology',
        'domain_pack_namespace': 'optical'
    },
    {
        'id': 'paper17',
        'doi': '10.1364/OE.2025.202',
        'title': 'Low-Loss Photonic Switching for Metro Access Rings',
        'authors': ['Keller, Nina', 'Xu, Minghao'],
        'year': 2025,
        'venue': 'Optics Express',
        'domain_pack_namespace': 'optical'
    },
    {
        'id': 'paper18',
        'doi': '10.1109/JPHOT.2025.303',
        'title': 'Adaptive Wavelength Scheduling in Elastic Optical Backhaul',
        'authors': ['Bianchi, Luca', 'Fernandez, Sofia'],
        'year': 2025,
        'venue': 'IEEE Photonics Journal',
        'domain_pack_namespace': 'optical'
    },
    {
        'id': 'paper19',
        'doi': '10.1364/JOCN.2025.404',
        'title': 'Resilient Optical Access Design Under Burst Traffic Loads',
        'authors': ['Hughes, Daniel', 'Ito, Haruka'],
        'year': 2025,
        'venue': 'Journal of Optical Communications and Networking',
        'domain_pack_namespace': 'optical'
    },
    {
        'id': 'paper20',
        'doi': '10.1109/JLT.2025.505',
        'title': 'Co-Packaged Optics for Energy-Aware Aggregation Networks',
        'authors': ['Rossi, Martina', 'Chen, Yubin'],
        'year': 2025,
        'venue': 'IEEE Journal of Lightwave Technology',
        'domain_pack_namespace': 'optical'
    },
    {
        'id': 'paper21',
        'doi': '10.1109/TWC.2025.111',
        'title': 'Integrated Access and Backhaul Optimization for Dense Small Cells',
        'authors': ['Ahmed, Samir', 'Novak, Petra'],
        'year': 2025,
        'venue': 'IEEE Transactions on Wireless Communications',
        'domain_pack_namespace': 'wireless'
    },
    {
        'id': 'paper22',
        'doi': '10.1109/TCOM.2025.222',
        'title': 'Joint Beam Steering and Power Control for Urban mmWave Relays',
        'authors': ['Park, Hyejin', 'Morales, Diego'],
        'year': 2025,
        'venue': 'IEEE Transactions on Communications',
        'domain_pack_namespace': 'wireless'
    },
    {
        'id': 'paper23',
        'doi': '10.1109/MCOM.2025.333',
        'title': 'AI-Assisted Topology Selection for Wireless Backhaul Meshes',
        'authors': ['Peterson, Claire', 'Raman, Vivek'],
        'year': 2025,
        'venue': 'IEEE Communications Magazine',
        'domain_pack_namespace': 'wireless'
    },
    {
        'id': 'paper24',
        'doi': '10.1109/LCOMM.2025.444',
        'title': 'Low-Latency Coordination in Cell-Free Backhaul Clusters',
        'authors': ['Silva, Beatriz', 'Meyer, Jonas'],
        'year': 2025,
        'venue': 'IEEE Communications Letters',
        'domain_pack_namespace': 'wireless'
    },
    {
        'id': 'paper25',
        'doi': '10.1109/JSAC.2025.555',
        'title': 'Sustainable Spectrum Reuse for 6G Wireless Transport',
        'authors': ['Khan, Amina', 'Dubois, Luc'],
        'year': 2025,
        'venue': 'IEEE Journal on Selected Areas in Communications',
        'domain_pack_namespace': 'wireless'
    }
]

# Mock metrics for each domain pack namespace
METRICS = {
    'optical': [
        {'name': 'reconfiguration_delay', 'unit': 'ms'},
        {'name': 'cross_talk', 'unit': 'dB'},
        {'name': 'latency', 'unit': 'ms'},
        {'name': 'power_consumption', 'unit': 'W'}
    ],
    'wireless': [
        {'name': 'latency', 'unit': 'ms'},
        {'name': 'throughput', 'unit': 'Gbps'},
        {'name': 'coverage_radius', 'unit': 'km'},
        {'name': 'energy_efficiency', 'unit': 'Mbps/W'}
    ]
}


# Deterministic mock context per domain pack: each mock paper is labelled with one
# method and one scenario so the coverage matrix has a realistic distribution.
# These are synthetic labels for the demo dataset, not extracted values.
CONTEXT_POOLS = {
    'optical': {
        'methods': ['wdm', 'optical_packet', 'burst_switching', 'circuit_switching', 'hybrid'],
        'scenarios': [
            'mesh',
            'ring',
            'star',
            'point_to_point',
            'free_space',
            'data_center',
            'metro_network',
            'long_haul',
            'access_network',
            'satellite',
        ],
    },
    'wireless': {
        'methods': ['beamforming', 'mimo', 'ofdm', 'full_duplex'],
        'scenarios': ['access_network', 'backhaul', 'data_center', 'satellite'],
    },
}


def mock_context_for(namespace: str, paper_index: int) -> dict:
    pools = CONTEXT_POOLS.get(namespace)
    if not pools:
        return {}
    return {
        'method': pools['methods'][paper_index % len(pools['methods'])],
        'scenario': pools['scenarios'][paper_index % len(pools['scenarios'])],
    }


def hash_code(s: str) -> int:
    """Simple hash function to generate deterministic 'random' numbers from a string."""
    hash_val = 0
    for i, char in enumerate(s):
        hash_val = ((hash_val << 5) - hash_val) + ord(char)
        hash_val = hash_val & 0xFFFFFFFF  # Convert to 32-bit integer
    return abs(hash_val)


def seeded_random(seed: int) -> float:
    """Seeded random number generator (0 to 1)."""
    x = math.sin(seed) * 10000
    return x - math.floor(x)


def generate_provenance_hash(paper_data: dict) -> str:
    """Generate a simple provenance hash from paper metadata."""
    content = f"{paper_data['doi']}_{paper_data['title']}_{paper_data['year']}"
    return hashlib.sha256(content.encode()).hexdigest()


def clear_database(db):
    """Clear all nodes and relationships from the database."""
    print("🗑️  Clearing existing data...")
    query = "MATCH (n) DETACH DELETE n"
    db.execute_write(query)
    print("✅ Database cleared")


def resolve_mock_owner_id():
    """Pick the account that should own the mock workspace.

    Prefers ``ONTOFORGE_MOCK_OWNER_ID``; otherwise looks up the seeded demo
    account so the data is visible after signing in to the desktop app.
    """
    configured = os.getenv("ONTOFORGE_MOCK_OWNER_ID", "").strip()
    if configured:
        return configured

    from backend.services.auth_service import find_user_by_username

    demo_user = find_user_by_username(os.getenv("ONTOFORGE_MOCK_OWNER", "demo"))
    return demo_user["user_id"] if demo_user else None


def create_workspace(node_repo: NodeRepository) -> str:
    """Create a workspace node for organizing data."""
    print(f"🏢 Creating workspace: {WORKSPACE_NAME}...")
    owner_id = resolve_mock_owner_id()
    if owner_id:
        print(f"  ✓ Workspace owner: {owner_id}")
    else:
        print("  ⚠️  No demo user found; workspace will be readable by any signed-in user")
    
    workspace = WorkspaceNode(
        id=WORKSPACE_ID,
        name=WORKSPACE_NAME,
        description="Demo workspace for testing OntoForge",
        root_path="file:///demo/workspace",
        created_at=datetime.now(timezone.utc),
        last_modified_at=datetime.now(timezone.utc),
        status="active",
        owner_id=owner_id,
        metadata={"type": "demo"}
    )
    
    try:
        # Create workspace node directly with execute_query
        db = get_db()
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
        workspace_data = workspace.model_dump()
        # Convert datetime to ISO string for Neo4j
        workspace_data['created_at'] = workspace_data['created_at'].isoformat()
        workspace_data['last_modified_at'] = workspace_data['last_modified_at'].isoformat()
        # Convert metadata dict to JSON string
        import json
        workspace_data['metadata'] = json.dumps(workspace_data['metadata'])
        
        db.execute_query(query, workspace_data)
        print(f"  ✓ Created workspace: {WORKSPACE_ID}")
        return WORKSPACE_ID
    except Exception as e:
        print(f"  ✗ Failed to create workspace: {e}")
        raise


def load_papers(node_repo: NodeRepository, workspace_id: str):
    """Load mock papers into the database."""
    print(f"📄 Loading {len(MOCK_PAPERS)} papers into Neo4j...")
    
    loaded_count = 0
    for paper_data in MOCK_PAPERS:
        # Create PaperNode with provenance hash and domain_pack_namespace
        paper_node = PaperNode(
            id=paper_data['id'],
            doi=paper_data['doi'],
            title=paper_data['title'],
            authors=paper_data['authors'],
            year=paper_data['year'],
            venue=paper_data['venue'],
            provenance_hash=generate_provenance_hash(paper_data),
            import_status='verified',
            domain_pack_namespace=paper_data['domain_pack_namespace'],
            workspace_id=workspace_id
        )
        
        try:
            node_repo.create_paper_node(paper_node)
            loaded_count += 1
            print(f"  ✓ {paper_node.id}: {paper_node.title[:50]}...")
        except Exception as e:
            print(f"  ✗ Failed to load {paper_data['id']}: {e}")
    
    print(f"✅ Loaded {loaded_count}/{len(MOCK_PAPERS)} papers")


def load_assertions(node_repo: NodeRepository, edge_repo: EdgeRepository, workspace_id: str):
    """Load mock assertions for each paper-metric combination."""
    print(f"\n📊 Generating assertions for paper-metric combinations...")
    
    assertion_count = 0
    edge_count = 0
    namespace_paper_index: dict[str, int] = {}

    for paper_data in MOCK_PAPERS:
        paper_id = paper_data['id']
        namespace = paper_data['domain_pack_namespace']

        paper_index = namespace_paper_index.get(namespace, 0)
        namespace_paper_index[namespace] = paper_index + 1
        mock_context = mock_context_for(namespace, paper_index)

        # Get metrics for this paper's domain pack
        metrics = METRICS.get(namespace, [])
        
        for metric in metrics:
            metric_full_name = f"{namespace}:{metric['name']}"
            key = f"{paper_id}:{metric_full_name}"
            
            # Use deterministic "random" based on paper+metric key
            seed = hash_code(key)
            rand1 = seeded_random(seed)
            rand2 = seeded_random(seed + 1)
            rand3 = seeded_random(seed + 2)
            rand4 = seeded_random(seed + 3)
            
            # 70% of cells have data
            if rand1 > 0.3:
                # Generate value based on metric name (deterministic)
                if 'delay' in metric['name'] or metric['name'] == 'latency':
                    value = f"{(rand3 * 50 + 10):.1f}"
                elif 'cross_talk' in metric['name'] or 'loss' in metric['name']:
                    value = f"{(-rand3 * 30 - 20):.1f}"
                elif metric['name'] == 'throughput':
                    value = f"{(rand3 * 50 + 10):.1f}"
                elif metric['name'] == 'coverage_radius':
                    value = f"{(rand3 * 5 + 1):.1f}"
                elif 'power' in metric['name'] or 'energy' in metric['name']:
                    value = f"{(rand3 * 100 + 50):.1f}"
                else:
                    value = f"{(rand3 * 100):.2f}"
                
                # Determine status
                statuses = ['resolved', 'pending', 'locked']
                status = statuses[int(rand2 * len(statuses))]
                
                # Create assertion
                assertion_id = f"assert_{paper_id}_{metric['name']}"
                assertion = AssertionNode(
                    id=assertion_id,
                    subject=metric_full_name,
                    predicate='equals',
                    object=value,
                    unit=metric['unit'],
                    domain_pack_namespace=namespace,
                    context_conditions={
                        'paper_id': paper_id,
                        'confidence': round(0.7 + rand4 * 0.3, 2),
                        **mock_context,
                    },
                    status=status,
                    workspace_id=workspace_id
                )
                
                try:
                    node_repo.create_assertion_node(assertion)
                    assertion_count += 1
                    
                    # Create CONTAINS edge from paper to assertion (simplified - normally through chunks)
                    contains_edge = ContainsEdge(
                        from_node_id=paper_id,
                        to_node_id=assertion_id,
                        extraction_method='mock_generator'
                    )
                    edge_repo.create_contains_edge(contains_edge)
                    edge_count += 1

                    # Attach one supporting chunk so the evidence viewer has content
                    chunk_id = f"chunk_{assertion_id}"
                    chunk = ChunkNode(
                        id=chunk_id,
                        raw_text=(
                            f"{paper_data['title']} reports {metric_full_name.replace(':', ' ')} "
                            f"of {value} {metric['unit']} for the tested configuration."
                        ),
                        bounding_box={
                            "page": 1 + seed % 8,
                            "x": 80,
                            "y": 120,
                            "width": 400,
                            "height": 60
                        },
                        verification_status="raw"
                    )
                    node_repo.create_chunk_node(chunk)
                    edge_repo.create_evidenced_by_edge(
                        EvidencedByEdge(
                            from_node_id=chunk_id,
                            to_node_id=assertion_id,
                            confidence_score=round(0.7 + rand4 * 0.3, 2)
                        )
                    )
                    
                except Exception as e:
                    print(f"  ✗ Failed to load assertion {assertion_id}: {e}")
    
    print(f"✅ Loaded {assertion_count} assertions with {edge_count} edges")


def main():
    """Main entry point."""
    # Get connection parameters from environment
    neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "password")
    
    print(f"🔌 Connecting to Neo4j at {neo4j_uri}...")
    
    try:
        # Initialize database connection
        db = init_db(neo4j_uri, neo4j_user, neo4j_password)
        
        if not db.verify_connectivity():
            print("❌ Failed to connect to Neo4j")
            print("   Make sure Neo4j is running: docker compose up -d neo4j")
            return 1
        
        print("✅ Connected to Neo4j")
        
        # Create repositories
        node_repo = NodeRepository(db)
        edge_repo = EdgeRepository(db)
        
        # Clear existing data
        clear_database(db)
        
        # Create workspace
        workspace_id = create_workspace(node_repo)
        
        # Load mock papers
        load_papers(node_repo, workspace_id)
        
        # Load mock assertions
        load_assertions(node_repo, edge_repo, workspace_id)
        
        print("\n🎉 Mock data loaded successfully!")
        
        # Close connection
        close_db()
        
        return 0
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
