# Subdomain Classification System

## Overview

The **Taxonomy-Based Subdomain Classification** system automatically organizes papers into research subdomains during ingestion. This solves the problem of managing large paper collections (100+ papers) that span multiple specialized areas within a domain.

## Features

✅ **Multi-Subdomain Assignment** - Papers can belong to multiple subdomains simultaneously  
✅ **Confidence Scores** - Each assignment includes an AI-generated confidence score  
✅ **Primary/Secondary Classification** - Distinguish main focus from tangential topics  
✅ **LLM + Rule-Based** - Falls back to keyword matching if LLM unavailable  
✅ **Auto-Create Subdomains** - Subdomain nodes created automatically during ingestion  
✅ **Manual Override** - Human can reclassify papers via HITL workflows  

---

## Architecture

### Schema Extensions

#### 1. **BelongsToEdge** (Enhanced)
```python
class BelongsToEdge(BaseModel):
    from_node_id: str           # Paper ID
    to_node_id: str             # Domain/Subdomain ID
    confidence: float           # 0.0 - 1.0
    primary: bool               # Is this the main subdomain?
    classification_method: str  # manual|llm|rule_based|embedding
```

#### 2. **TaxonomyDimension** (New)
```python
class TaxonomyDimension(BaseModel):
    name: str                   # e.g., "switching_mechanism"
    values: List[str]           # e.g., ["wdm", "ops", "obs"]
    subdomain_map: dict         # Maps values to subdomain IDs
    description: str            # Human-readable description
```

#### 3. **DomainInfo** (Enhanced)
```python
class DomainInfo(BaseModel):
    id: str
    name: str
    taxonomy_tree: List[TaxonomyDimension]  # Structured dimensions
    parent_domain_id: str | None            # For subdomain hierarchy
```

---

## Usage

### 1. Define Taxonomy in Domain Pack YAML

```yaml
domain:
  id: domain.networking.optical
  taxonomy_tree:
    - name: switching_mechanism
      values: [wdm, optical_packet, burst_switching]
      subdomain_map:
        wdm: domain.networking.optical.wdm
        optical_packet: domain.networking.optical.ops
      description: Switching technologies
    
    - name: topology
      values: [mesh, ring, free_space]
      subdomain_map:
        free_space: domain.networking.optical.fso
        mesh: domain.networking.optical.access
      description: Network topologies
```

### 2. Initialize Classifier

```python
from config.loader import DomainPackLoader
from services.subdomain_classifier import SubdomainClassifier

# Load domain config
loader = DomainPackLoader()
domain_config = loader.load("configs/domain-pack-optical-networks.yaml")

# Create classifier
classifier = SubdomainClassifier(domain_config)

# Get subdomain hierarchy
hierarchy = classifier.get_subdomain_hierarchy()
print(hierarchy)
# {
#   "domain.networking.optical": [
#     "domain.networking.optical.wdm",
#     "domain.networking.optical.ops",
#     "domain.networking.optical.fso",
#     "domain.networking.optical.access"
#   ]
# }
```

### 3. Ingest Papers with Auto-Classification

```python
from services.ingestion_service import IngestionService
from database.node_repository import NodeRepository
from database.edge_repository import EdgeRepository

# Initialize services
node_repo = NodeRepository(db)
edge_repo = EdgeRepository(db)
ingestion_service = IngestionService(
    node_repo=node_repo,
    edge_repo=edge_repo,
    domain_config=domain_config,
    llm_client=your_llm_client  # Optional
)

# Ingest paper (automatically classified)
result = await ingestion_service.ingest_paper(
    paper=paper_node,
    chunks=extracted_chunks,
    formulas=extracted_formulas,
    auto_classify=True  # Enable auto-classification
)

print(result)
# {
#   "paper_id": "paper_wdm_2026",
#   "chunks_created": 45,
#   "formulas_created": 8,
#   "subdomain_assignments": [
#     {
#       "subdomain_id": "domain.networking.optical.wdm",
#       "confidence": 0.92,
#       "dimension": "switching_mechanism",
#       "primary": True
#     },
#     {
#       "subdomain_id": "domain.networking.optical.access",
#       "confidence": 0.78,
#       "dimension": "topology",
#       "primary": False
#     }
#   ],
#   "created_subdomains": ["domain.networking.optical.wdm"]
# }
```

### 4. Query Papers by Subdomain

```python
# Get all WDM papers
wdm_papers = ingestion_service.get_papers_by_subdomain(
    "domain.networking.optical.wdm"
)

# Get subdomain distribution
distribution = ingestion_service.get_subdomain_distribution()
print(distribution)
# {
#   "domain.networking.optical.wdm": {"name": "WDM", "count": 23},
#   "domain.networking.optical.ops": {"name": "OPS", "count": 15},
#   "domain.networking.optical.fso": {"name": "FSO", "count": 8}
# }
```

### 5. Manual Reclassification

```python
# Reclassify a paper manually
ingestion_service.reclassify_paper(
    paper_id="paper_123",
    new_subdomain_id="domain.networking.optical.ops",
    confidence=1.0,
    classification_method="manual"
)
```

---

## Classification Methods

### LLM-Based Classification (Recommended)

When `llm_client` is provided, the system uses structured prompting:

```python
classifier = SubdomainClassifier(domain_config)
assignments = await classifier.classify_paper(
    paper=paper,
    extracted_chunks=chunks,
    llm_client=openai_client  # or anthropic_client
)
```

**LLM Prompt Structure:**
- Paper metadata (title, authors, venue, year)
- Sample text chunks (first 1000 chars)
- Taxonomy dimensions with available values
- Request JSON output with confidence scores

**Example LLM Response:**
```json
{
  "switching_mechanism": {
    "value": "wdm",
    "confidence": 0.92,
    "reasoning": "Paper focuses on wavelength division multiplexing systems"
  },
  "topology": {
    "value": "mesh",
    "confidence": 0.78,
    "reasoning": "Describes mesh network architecture for metro applications"
  }
}
```

### Rule-Based Classification (Fallback)

When no LLM is available, uses keyword matching:

```python
assignments = await classifier.classify_paper(
    paper=paper,
    extracted_chunks=chunks,
    llm_client=None  # Falls back to rule-based
)
```

**Keyword Matching Logic:**
1. Extract keywords from taxonomy values (e.g., "wdm" → ["wdm", "wavelength", "division"])
2. Search in paper title + chunk text
3. Score = (matched_keywords / total_keywords)
4. Assign to subdomain if score > 0.3
5. Confidence capped at 0.85 for rule-based

---

## Cypher Query Examples

### Find papers in specific subdomain
```cypher
MATCH (p:PaperNode)-[:BELONGS_TO]->(d:DomainNode {id: "domain.networking.optical.wdm"})
RETURN p.title, p.year
ORDER BY p.year DESC
```

### Find papers in multiple subdomains
```cypher
MATCH (p:PaperNode)-[b:BELONGS_TO]->(d:DomainNode)
WHERE d.id STARTS WITH "domain.networking.optical."
WITH p, count(d) as subdomain_count, collect({
    subdomain: d.name,
    confidence: b.confidence,
    primary: b.primary
}) as subdomains
WHERE subdomain_count > 1
RETURN p.title, subdomain_count, subdomains
```

### Get primary subdomain only
```cypher
MATCH (p:PaperNode)-[b:BELONGS_TO {primary: true}]->(d:DomainNode)
RETURN p.title, d.name, b.confidence
```

### Low-confidence classifications (for HITL review)
```cypher
MATCH (p:PaperNode)-[b:BELONGS_TO]->(d:DomainNode)
WHERE b.confidence < 0.7 AND b.classification_method = "llm"
RETURN p.title, d.name, b.confidence, b.classification_method
ORDER BY b.confidence ASC
```

### Subdomain statistics
```cypher
MATCH (p:PaperNode)-[:BELONGS_TO]->(d:DomainNode)
WHERE d.id STARTS WITH "domain.networking.optical."
WITH d.name as subdomain, 
     count(p) as total_papers,
     avg(properties([:BELONGS_TO]).confidence) as avg_confidence
RETURN subdomain, total_papers, avg_confidence
ORDER BY total_papers DESC
```

---

## Frontend Integration

### Matrix View with Subdomain Filter

```typescript
// frontend/renderer/services/workspace.ts

interface SubdomainFilter {
  subdomainId: string;
  name: string;
  paperCount: number;
}

class WorkspaceStore {
  subdomains: SubdomainFilter[] = [];
  selectedSubdomain: string | null = null;
  
  async loadSubdomains() {
    const result = await sspClient.request('textDocument/getSubdomains', {
      domainId: this.domainId
    });
    
    this.subdomains = result.subdomains;
  }
  
  filterBySubdomain(subdomainId: string) {
    this.selectedSubdomain = subdomainId;
    // Reload papers filtered by subdomain
    this.refreshData();
  }
}
```

### Subdomain Badge Component

```tsx
// frontend/renderer/components/SubdomainBadge.tsx

interface SubdomainBadgeProps {
  subdomain: string;
  confidence: number;
  primary: boolean;
}

export function SubdomainBadge({ subdomain, confidence, primary }: SubdomainBadgeProps) {
  const shortName = subdomain.split('.').pop()?.toUpperCase();
  const bgColor = primary ? 'bg-blue-600' : 'bg-gray-600';
  
  return (
    <span className={`${bgColor} text-white px-2 py-1 rounded text-xs`}>
      {shortName}
      {confidence < 0.8 && <span className="ml-1">⚠️</span>}
    </span>
  );
}
```

---

## Testing

Run subdomain classification tests:

```bash
cd backend
python -m pytest tests/test_subdomain_classification.py -v
```

Run the example demonstration:

```bash
python tests/test_subdomain_classification.py
```

Expected output:
```
============================================================
Subdomain Classification Example
============================================================

📊 Taxonomy Dimensions:

  switching_mechanism:
    Values: ['wdm', 'optical_packet', 'burst_switching']
    Subdomain Mappings:
      - wdm → domain.networking.optical.wdm
      - optical_packet → domain.networking.optical.ops

  topology:
    Values: ['mesh', 'ring', 'star', 'free_space']
    Subdomain Mappings:
      - free_space → domain.networking.optical.fso
      - mesh → domain.networking.optical.access

🏗️  Subdomain Hierarchy:

  domain.networking.optical:
    └─ domain.networking.optical.wdm
    └─ domain.networking.optical.ops
    └─ domain.networking.optical.fso
    └─ domain.networking.optical.access

============================================================
✅ Subdomain classification system ready!
============================================================
```

---

## Migration Guide

### For Existing Installations

1. **Update Schema:**
   ```bash
   # Backup existing database
   neo4j-admin dump --database=neo4j --to=backup.dump
   
   # Update edge properties
   python scripts/migrate_belongs_to_edges.py
   ```

2. **Update Domain Pack YAML:**
   ```yaml
   # Old format
   taxonomy_tree:
     - topology
     - switching_mechanism
   
   # New format
   taxonomy_tree:
     - name: topology
       values: [mesh, ring, star]
       subdomain_map:
         mesh: domain.networking.optical.access
   ```

3. **Reclassify Existing Papers:**
   ```python
   from services.ingestion_service import IngestionService
   
   # Load all papers
   papers = node_repo.get_all_papers()
   
   # Reclassify each paper
   for paper in papers:
       chunks = node_repo.get_paper_chunks(paper.id)
       assignments = await classifier.classify_paper(paper, chunks)
       
       # Update BELONGS_TO edges
       for subdomain_id, confidence, dim in assignments:
           edge_repo.create_belongs_to_edge(BelongsToEdge(
               from_node_id=paper.id,
               to_node_id=subdomain_id,
               confidence=confidence,
               primary=True,
               classification_method="migration"
           ))
   ```

---

## Best Practices

### 1. Design Taxonomy Dimensions Carefully
- Use **orthogonal dimensions** (e.g., topology vs. switching mechanism)
- Keep **5-10 values per dimension** (not too granular)
- Map only **high-confidence subdomains** (leave ambiguous values unmapped)

### 2. Review Low-Confidence Classifications
- Set up HITL review for confidence < 0.7
- Show subdomain badges with warning icons
- Allow easy drag-and-drop reclassification in UI

### 3. Monitor Subdomain Balance
- Check distribution regularly
- Create new subdomains if one becomes too large (>50 papers)
- Merge subdomains if too small (<5 papers)

### 4. Iterate on Keywords (Rule-Based Mode)
- Add domain-specific keywords to improve matching
- Test on sample papers before bulk ingestion
- Use LLM mode for better accuracy when available

---

## Troubleshooting

**Q: Papers not classified into subdomains?**
- Check that taxonomy_tree has TaxonomyDimension objects with subdomain_map
- Verify subdomain IDs in subdomain_map are correct
- Check classification confidence threshold (may be too low)

**Q: All papers going to parent domain?**
- LLM may not recognize keywords → add classification_hints in YAML
- Rule-based matching too strict → lower confidence threshold
- Chunks may be empty → verify extraction pipeline

**Q: Too many subdomain assignments per paper?**
- Papers can belong to multiple subdomains (by design)
- Filter by `primary=true` to get main subdomain only
- Adjust confidence thresholds to reduce false positives

---

## API Reference

See:
- `services/subdomain_classifier.py` - Core classification logic
- `services/ingestion_service.py` - Integration with ingestion pipeline
- `schemas/edges.py` - BelongsToEdge schema
- `schemas/domain_pack.py` - TaxonomyDimension schema

---

**Status:** ✅ Production Ready  
**Version:** 1.0  
**Last Updated:** May 24, 2026
