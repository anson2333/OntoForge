# HITL Implementation Gaps & Proposed Fixes

## Summary
The current Phase A implementation is **missing verification status fields** for 3 out of 4 tiers, which breaks the architectural principle that "each tier assumes the layer beneath it is 100% deterministic."

## Missing HITL Fields by Tier

### Tier 4: Source Assets (PaperNode) ❌
**Current State:**
```python
class PaperNode(BaseModel):
    id: str
    doi: str
    title: str
    authors: List[str]
    year: int
    venue: str
    provenance_hash: str
    # ❌ MISSING: No way to verify source integrity
```

**Required Addition:**
```python
import_status: Literal["pending", "verified", "rejected"] = Field(
    default="pending",
    description="Human verification of source artifact integrity"
)
```

**HITL Use Case:**
- Source PDF is corrupt or missing pages
- Provenance hash mismatch
- Visual inspection reveals artifacts/watermarks that would break parsing

**Human Workflow:** Visual inspection → Mark as verified/rejected → Block/allow downstream extraction

---

### Tier 3: Physical Evidence (FormulaNode) ❌
**Current State:**
```python
class FormulaNode(BaseModel):
    id: str
    latex_string: str
    variables_map: dict[str, str]
    constraints: dict[str, Any]
    # ❌ MISSING: No way to verify LaTeX correctness
```

**Required Addition:**
```python
verification_status: Literal["raw", "verified", "rejected"] = Field(
    default="raw",
    description="Human verification of LaTeX parsing accuracy"
)
```

**HITL Use Case:**
- LaTeX parsing produces malformed output
- Confidence score below safety threshold (e.g., <0.7)
- Complex equations with nested subscripts/superscripts fail

**Human Workflow:** Digital Microscope view → Correct LaTeX → Mark as verified

**Note:** ChunkNode already has this field ✅

---

### Tier 1: Macro Domain (DomainNode) ❌
**Current State:**
```python
class DomainNode(BaseModel):
    id: str
    name: str
    domain_pack_id: str
    domain_pack_version: str
    taxonomy_tree: dict[str, Any]
    core_metrics: List[str]
    # ❌ MISSING: No way to approve domain changes
```

**Required Additions:**

**Option A: Add verification field**
```python
approval_status: Literal["draft", "approved", "deprecated"] = Field(
    default="draft",
    description="Human approval of domain taxonomy structure"
)
```

**Option B: Extend HumanArbitratorNode capabilities**
Add new edge type:
```python
(:HumanArbitratorNode)-[:APPROVES {approval_type: STRING}]->(:DomainNode)
```

**HITL Use Case:**
- Domain taxonomy change would create temporal inversion (Paper A from 2020 references tech from 2022)
- Metric list change invalidates existing assertions
- Structural changes break baseline comparisons

**Human Workflow:** Git-like merge conflict interface → Review taxonomy diff → Approve/reject changes

---

## Recommended Implementation Priority

### Phase A Extension (Immediate)
These are **data contract** changes that should be in Phase A:

1. ✅ Add `verification_status` to `FormulaNode` (mirrors `ChunkNode` design)
2. ✅ Add `import_status` to `PaperNode` 
3. ✅ Add `approval_status` to `DomainNode`
4. ✅ Extend tests to cover new fields

**Estimated Time:** 1-2 hours

### Phase B Integration (Next)
These require **protocol** changes for the SSP service:

1. Update `sspIngest` response to include verification statuses
2. Add `sspVerifyEvidence` method for marking chunks/formulas as verified
3. Add `sspApproveDomain` method for domain structure approval
4. Update audit engine to respect verification boundaries

**Estimated Time:** 3-4 hours (part of Phase B)

---

## Impact on Tier Assumptions

### Current (Broken) Flow
```
Tier 1 (Domain) → assumes Tier 2 clean ❌ (no approval gate)
Tier 2 (Claims) → assumes Tier 3 clean ✅ (AssertionNode.status)
Tier 3 (Evidence) → assumes Tier 4 clean ❌ (FormulaNode missing)
Tier 4 (Source) → no assumption ❌ (no verification)
```

### Fixed Flow
```
Tier 1 (Domain) → assumes Tier 2 clean ✅ (approval_status)
Tier 2 (Claims) → assumes Tier 3 clean ✅ (AssertionNode.status)
Tier 3 (Evidence) → assumes Tier 4 clean ✅ (verification_status on both nodes)
Tier 4 (Source) → no assumption ✅ (import_status verifies integrity)
```

---

## Additional Edge Types Needed

### For Domain Approval (Tier 1)
```python
class ApprovesEdge(BaseModel):
    """
    (:HumanArbitratorNode)-[:APPROVES]->(:DomainNode)
    Represents human approval of domain structure changes.
    """
    from_node_id: str
    to_node_id: str
    approval_type: Literal["initial_approval", "taxonomy_change", "metric_addition"]
    approved_version: str  # domain_pack_version that was approved
```

### For Evidence Verification (Optional Enhancement)
```python
class VerifiesEdge(BaseModel):
    """
    (:HumanArbitratorNode)-[:VERIFIES]->(:ChunkNode|:FormulaNode)
    Tracks who verified extracted evidence.
    """
    from_node_id: str
    to_node_id: str
    verification_timestamp: datetime
    corrections_made: Optional[str]  # Description of what was fixed
```

**Note:** This edge is **optional** because verification status is already tracked on the nodes themselves. Only add if you need detailed audit trails of *who* verified *what* and *when*.

---

## Questions for Decision

1. **FormulaNode verification_status**: Should we add `"rejected"` as a third option (like PaperNode), or keep it binary like ChunkNode currently is?
   - **Recommendation**: Add `"rejected"` for consistency across all tiers

2. **DomainNode approval**: Should approval be a node property or an edge to HumanArbitratorNode?
   - **Recommendation**: Start with node property for MVP, add edge later if detailed audit trails are needed

3. **Verification cascade**: When a FormulaNode is marked "rejected", should all dependent AssertionNodes be automatically marked "pending"?
   - **Recommendation**: Yes, add cascade logic in Phase B audit engine

4. **Status values**: Should we standardize on a common set of status values across tiers?
   - Current inconsistency: 
     - ChunkNode: `"raw" | "verified"`
     - AssertionNode: `"pending" | "resolved" | "locked"`
     - Proposed PaperNode: `"pending" | "verified" | "rejected"`
   - **Recommendation**: Accept this diversity since each tier has different semantics; document in OntoForge.md

---

## Testing Impact

New tests needed:
- `test_formula_node_verification_status` - Default "raw", accepts "verified"/"rejected"
- `test_paper_node_import_status` - Default "pending", accepts "verified"/"rejected"
- `test_domain_node_approval_status` - Default "draft", accepts "approved"/"deprecated"
- `test_verification_status_consistency` - All Tier 3 nodes have verification_status
- `test_approves_edge` - If we add the edge type

---

## Documentation Updates Needed

1. **OntoForge.md Section 3.1** - Add new fields to node schemas
2. **OntoForge.md Section 3.2** - Add `[:APPROVES]` edge if implemented
3. **backend/README.md** - Update Phase A success criteria
4. **PHASE_A_SUMMARY.md** - Note HITL implementation status

---

## Decision: Implement Now or Defer?

**Recommendation: Implement core fields NOW in Phase A**

**Rationale:**
- These are **data contract** definitions - the foundation for all downstream work
- Fixing this in Phase B or C would require:
  - Schema migration
  - Rewriting tests
  - Updating protocol definitions
  - Potentially breaking client code
- Phase A is specifically about "Data Contracts" - this is the right time
- Implementation time: 1-2 hours (low risk, high value)

**What to defer to Phase B:**
- Protocol methods for verification workflows (sspVerifyEvidence, sspApproveDomain)
- UI components (Digital Microscope, Git-like merge interface)
- Cascade logic and audit engine behavior

---

## Proposed Phase A Extension Scope

**Add to current Phase A:**
1. Update `FormulaNode` with `verification_status`
2. Update `PaperNode` with `import_status`  
3. Update `DomainNode` with `approval_status`
4. Add `ApprovesEdge` for Tier 1 HITL tracking
5. Update all schema tests
6. Update OntoForge.md specification

**Keep Phase A success criteria the same:**
- Still focused on "Data Contracts + Config Loader"
- No protocol implementation required
- No UI work required
- Clean separation for Phase B

**Estimated time to complete extension: 1-2 hours**
