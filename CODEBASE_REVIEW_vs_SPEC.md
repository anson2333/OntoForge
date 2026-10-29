# OntoForge Codebase Review vs. Specification
**Review Date:** May 24, 2026  
**Spec Version:** v1.0 with Intent Framework (Section 2.6)  
**Review Scope:** Phases A-C Implementation Status

---

## Executive Summary

**Overall Status:** ~60% Complete (Phases A & B Complete, Phase C Partial)  
**Intent Framework Status:** ❌ **0% Implemented** - Critical gap requiring immediate attention

### Phase Completion Matrix

| Phase | Spec Requirement | Implementation Status | Gap Assessment |
|-------|-----------------|----------------------|----------------|
| **Phase A** | Data Contracts + Config Loader | ✅ **95% Complete** | Missing intent schemas |
| **Phase B** | SSP Server + Neo4j | ✅ **90% Complete** | Missing intent endpoints |
| **Phase C** | Matrix Frontend | 🔄 **40% Complete** | Missing intent UI, app not launching |

---

## Phase A: Data Contracts + Config Loader

### ✅ **Implemented Components**

#### Backend Schemas (`backend/schemas/`)
- ✅ `nodes.py`: DomainNode, PaperNode, ChunkNode, FormulaNode, AssertionNode, HumanArbitratorNode
- ✅ `edges.py`: HasBranchEdge, BelongsToEdge, CitesEdge, ContainsEdge, EvidencedByEdge, ContradictsEdge, LocksEdge, ApprovesEdge
- ✅ `protocol.py`: SSPInitialize, SSPIngest, SSPAuditConflicts, SSPResolveConflict
- ✅ `domain_pack.py`: TaxonomyDimension, DomainPackConfig with subdomain support

#### Config System (`backend/config/`)
- ✅ `loader.py`: YAML parser with validation
- ✅ `registries.py`: metric_registry, alias_registry, unit_registry
- ✅ `validator.py`: Domain-pack validation
- ✅ `watcher.py`: File watcher for hot-reload

#### Test Coverage
- ✅ `test_nodes.py`: Node schema validation
- ✅ `test_edges.py`: Edge schema validation
- ✅ `test_config_loader.py`: Config loading tests
- ✅ `test_registries.py`: Registry tests
- ✅ `test_validator.py`: Validation tests
- ✅ 94 tests passing, 74% coverage

### ❌ **Missing Components (Intent Framework)**

#### 1. **Intent Schemas** (`backend/schemas/intent.py`) - **NOT FOUND**
**Required:**
```python
class IntentMetadata(BaseModel):
    intent_type: Literal["correction", "preference", "priority", "constraint", "goal"]
    intent_scope: Literal["local", "pattern", "global"]
    generalization_hint: Optional[str]
    confidence_override: Optional[float]
    tags: List[str]

class UserIntentProfile(BaseModel):
    user_id: str
    learned_priorities: Dict[str, float]
    preferred_units: Dict[str, str]
    evidence_ranking: List[str]
    active_goals: List[IntentGoal]
    subdomain_focus: List[str]

class IntentPattern(BaseModel):
    pattern_id: str
    confidence: float
    applications: int
    last_used: datetime

class IntentGoal(BaseModel):
    goal_id: str
    description: str
    constraints: Dict[str, Any]
    active_from: datetime
    active_until: Optional[datetime]
```

#### 2. **IntentBranchNode** in `nodes.py` - **NOT FOUND**
**Current:** HumanArbitratorNode has NO intent fields
**Required:** Add to HumanArbitratorNode:
```python
intent_type: Optional[Literal["correction", "preference", "priority", "constraint", "goal"]]
intent_scope: Optional[Literal["local", "pattern", "global"]]
generalization_hint: Optional[str]
confidence_override: Optional[float]
intent_branch_id: Optional[str]
tags: List[str] = Field(default_factory=list)
```

**New Node Required:**
```python
class IntentBranchNode(BaseModel):
    id: str
    branch_name: str
    description: str
    user_id: str
    parent_branch_id: Optional[str]
    created_at: datetime
    active_until: Optional[datetime]
    status: Literal["active", "archived", "completed"]
    overrides: Dict[str, Any]
```

#### 3. **Intent Edges** in `edges.py` - **NOT FOUND**
**Required:**
```python
class ScopesEdge(BaseModel):
    """(:IntentBranchNode)-[:SCOPES]->(:HumanArbitratorNode)"""
    from_node_id: str
    to_node_id: str

class InheritsFromEdge(BaseModel):
    """(:IntentBranchNode)-[:INHERITS_FROM]->(:IntentBranchNode)"""
    from_node_id: str
    to_node_id: str

class MatchesPatternEdge(BaseModel):
    """(:HumanArbitratorNode)-[:MATCHES_PATTERN]->(:HumanArbitratorNode)"""
    from_node_id: str
    to_node_id: str
    pattern_id: str
    confidence: float
```

#### 4. **Intent Protocol Schemas** in `protocol.py` - **NOT FOUND**
**Required:** 7 new SSP method schemas:
- `SSPDeclareIntentParams` / `SSPDeclareIntentResponse`
- `SSPCreateIntentBranchParams` / `SSPCreateIntentBranchResponse`
- `SSPSwitchIntentContextParams` / `SSPSwitchIntentContextResponse`
- `SSPQueryByIntentParams` / `SSPQueryByIntentResponse`
- `SSPSuggestReviewQueueParams` / `SSPSuggestReviewQueueResponse`
- `SSPApplyIntentPatternParams` / `SSPApplyIntentPatternResponse`
- `SSPQueryIntentProfileParams` / `SSPQueryIntentProfileResponse`

#### 5. **ConflictResolution Enhancement** in `protocol.py` - **MISSING FIELDS**
**Current:**
```python
class ConflictResolution(BaseModel):
    accepted_assertion_id: str
    overridden_assertion_id: str
    arbitrator_notes: str
    lock_status: Literal["permanent_human_lock", "temporary_override"]
```

**Required:** Add `intent_metadata` field:
```python
intent_metadata: Optional[IntentMetadata]
```

**Gap Impact:** 🔴 **HIGH** - Phase A effort increases from 2-3 days to **2.5-3.5 days** (+0.5 days)

---

## Phase B: SSP Server + Neo4j Integration

### ✅ **Implemented Components**

#### FastAPI Server (`backend/server/`)
- ✅ `app.py`: FastAPI application with JSON-RPC 2.0 support
- ✅ `jsonrpc_methods.py`: SSP protocol handlers

#### Neo4j Integration (`backend/database/`)
- ✅ `connection.py`: Neo4j driver with testcontainers
- ✅ `node_repository.py`: CRUD for all node types
- ✅ `edge_repository.py`: Relationship management with edge properties

#### Services (`backend/services/`)
- ✅ `subdomain_classifier.py`: LLM + rule-based classification
- ✅ `ingestion_service.py`: Paper ingestion with auto-classification

#### Test Coverage
- ✅ `test_server.py`: Server endpoint tests
- ✅ `test_integration.py`: Neo4j integration tests (13 tests)
- ✅ `test_subdomain_classification.py`: Classification tests

### ❌ **Missing Components (Intent Framework)**

#### 1. **Intent Learning Engine** (`backend/services/intent_learning_engine.py`) - **NOT FOUND**
**Required:**
```python
class IntentLearningEngine:
    def __init__(self, node_repo, edge_repo):
        pass
    
    def analyze_arbitrator_history(self, user_id: str, days: int = 90) -> List[IntentPattern]:
        """Extract patterns from HumanArbitratorNode history using Cypher queries (Section 2.6.3)"""
        
    def build_user_intent_profile(self, user_id: str) -> UserIntentProfile:
        """Construct UserIntentProfile from learned patterns"""
        
    def compute_suggestion_confidence(self, conflict: Conflict, profile: UserIntentProfile) -> float:
        """Calculate confidence for AI-suggested resolution"""
        
    def match_intent_patterns(self, arbitrator_node: HumanArbitratorNode) -> List[str]:
        """Find similar intent patterns for MATCHES_PATTERN edges"""
```

#### 2. **IntentBranchNode Repository Operations** - **NOT IMPLEMENTED**
**Location:** `backend/database/node_repository.py`
**Required:** Add CRUD methods:
```python
def create_intent_branch(self, branch: IntentBranchNode) -> str
def get_intent_branch(self, branch_id: str) -> Optional[IntentBranchNode]
def update_intent_branch_status(self, branch_id: str, status: str)
def get_active_branches(self, user_id: str) -> List[IntentBranchNode]
```

#### 3. **Intent Edge Operations** - **NOT IMPLEMENTED**
**Location:** `backend/database/edge_repository.py`
**Required:** Add edge creation methods:
```python
def create_scopes_edge(self, branch_id: str, arbitrator_id: str)
def create_inherits_from_edge(self, child_branch_id: str, parent_branch_id: str)
def create_matches_pattern_edge(self, arbitrator_id1: str, arbitrator_id2: str, pattern_id: str, confidence: float)
```

#### 4. **Intent SSP Method Handlers** (`backend/server/`) - **NOT FOUND**
**Required:** 7 new handler files or methods in `jsonrpc_methods.py`:
- `handle_declare_intent(params: SSPDeclareIntentParams) -> SSPDeclareIntentResponse`
- `handle_create_intent_branch(params: SSPCreateIntentBranchParams) -> SSPCreateIntentBranchResponse`
- `handle_switch_intent_context(params: SSPSwitchIntentContextParams) -> SSPSwitchIntentContextResponse`
- `handle_query_by_intent(params: SSPQueryByIntentParams) -> SSPQueryByIntentResponse`
- `handle_suggest_review_queue(params: SSPSuggestReviewQueueParams) -> SSPSuggestReviewQueueResponse`
- `handle_apply_intent_pattern(params: SSPApplyIntentPatternParams) -> SSPApplyIntentPatternResponse`
- `handle_query_intent_profile(params: SSPQueryIntentProfileParams) -> SSPQueryIntentProfileResponse`

#### 5. **AI Suggestion in Conflict Detection** - **NOT IMPLEMENTED**
**Location:** Requires new service or enhancement to conflict detection
**Required:**
```python
class ConflictDetector:
    def detect_conflicts_with_suggestions(self, user_id: str) -> List[ConflictWithSuggestion]:
        """Add ai_suggestion field with confidence, reasoning, matched_intent_patterns"""
```

#### 6. **UserIntentProfile Storage** - **NOT IMPLEMENTED**
**Required:** Graph-based storage for intent profiles:
- Store in Neo4j as properties on user-specific node
- Implement retrieval and update methods
- Support pattern versioning and migration

**Gap Impact:** 🔴 **CRITICAL** - Phase B requires **+2-3 additional days** of work

---

## Phase C: Matrix Frontend (Electron)

### ✅ **Implemented Components**

#### Electron Shell
- ✅ `main.js`: Electron main process
- ✅ `preload.js`: IPC bridge
- ❌ **App not launching** (exit code 254)

#### React Components (`frontend/renderer/components/`)
- ✅ `MatrixGrid.tsx`: Papers × metrics grid
- ✅ `MatrixCell.tsx`: Cell with status indicators
- ✅ `DigitalMicroscope.tsx`: PDF crop + text viewer
- ✅ `EvidencePanel.tsx`: Evidence list
- ✅ `ConfidenceIndicator.tsx`: Confidence visualization

#### Services (`frontend/renderer/services/`)
- ✅ `ssp_client.ts`: JSON-RPC client
- ✅ `workspace.ts`: Workspace state (Zustand)

### ❌ **Missing Components (Intent Framework)**

#### 1. **Intent UI Components** (`frontend/renderer/components/intent/`) - **DIRECTORY NOT FOUND**
**Required:** 6 new components:

**a) `IntentDeclarationModal.tsx`**
```tsx
// Modal for explicit intent declaration (sspDeclareIntent)
interface Props {
  onDeclare: (intent: IntentDeclaration) => void;
}
// Form fields: intent_type, intent_scope, description, constraints, active_from, active_until
```

**b) `IntentBranchSelector.tsx`**
```tsx
// Dropdown in header/sidebar for switching active intent context
interface Props {
  activeBranch: IntentBranch | null;
  availableBranches: IntentBranch[];
  onSwitch: (branchId: string) => void;
}
```

**c) `IntentProfilePanel.tsx`**
```tsx
// Side panel showing learned patterns, active goals, confidence threshold slider
interface Props {
  userId: string;
  profile: UserIntentProfile;
  onDeletePattern: (patternId: string) => void;
  onUpdateThreshold: (threshold: number) => void;
}
```

**d) `IntentPatternCard.tsx`**
```tsx
// Display individual intent pattern with actions
interface Props {
  pattern: IntentPattern;
  onDelete: () => void;
  onApply: () => void;
}
```

**e) `AISuggestionBadge.tsx`**
```tsx
// Visual indicator for AI suggestions with confidence score
interface Props {
  suggestion: AISuggestion;
  onAccept: () => void;
  onReject: () => void;
}
```

**f) `IntentMetadataForm.tsx`**
```tsx
// Capture intent metadata during HITL actions
interface Props {
  onSubmit: (metadata: IntentMetadata) => void;
}
// Fields: intent_type, intent_scope, generalization_hint, tags
```

#### 2. **ConflictResolutionPanel Enhancement** - **MISSING**
**Current:** No dedicated conflict resolution UI
**Required:**
- AI suggestion display with reasoning
- Matched pattern indicators
- Intent metadata capture form
- One-click accept/reject buttons
- Confidence score visualization

#### 3. **Intent Service** (`frontend/renderer/services/intent_service.ts`) - **NOT FOUND**
**Required:**
```typescript
class IntentService {
  async declareIntent(params: DeclareIntentParams): Promise<IntentResponse>
  async createIntentBranch(params: CreateBranchParams): Promise<BranchResponse>
  async switchIntentContext(branchId: string): Promise<void>
  async getIntentProfile(userId: string): Promise<UserIntentProfile>
  async applyIntentPattern(patternId: string, conflictIds: string[]): Promise<BatchResult>
  async queryByIntent(query: string, context?: string): Promise<QueryResult>
}
```

#### 4. **SSP Client Enhancement** - **MISSING INTENT METHODS**
**Location:** `frontend/renderer/services/ssp_client.ts`
**Required:** Add 7 intent method handlers:
```typescript
async sspDeclareIntent(params: SSPDeclareIntentParams): Promise<SSPDeclareIntentResponse>
async sspCreateIntentBranch(params: SSPCreateIntentBranchParams): Promise<SSPCreateIntentBranchResponse>
async sspSwitchIntentContext(params: SSPSwitchIntentContextParams): Promise<SSPSwitchIntentContextResponse>
async sspQueryByIntent(params: SSPQueryByIntentParams): Promise<SSPQueryByIntentResponse>
async sspSuggestReviewQueue(params: SSPSuggestReviewQueueParams): Promise<SSPSuggestReviewQueueResponse>
async sspApplyIntentPattern(params: SSPApplyIntentPatternParams): Promise<SSPApplyIntentPatternResponse>
async sspQueryIntentProfile(params: SSPQueryIntentProfileParams): Promise<SSPQueryIntentProfileResponse>
```

#### 5. **Workspace State Enhancement** - **MISSING INTENT CONTEXT**
**Location:** `frontend/renderer/services/workspace.ts`
**Required:** Add to Zustand store:
```typescript
interface WorkspaceState {
  // ... existing fields
  activeIntentBranch: IntentBranch | null;
  intentProfile: UserIntentProfile | null;
  confidenceThreshold: number;
  
  // Actions
  setActiveIntentBranch: (branch: IntentBranch) => void;
  loadIntentProfile: (userId: string) => Promise<void>;
  updateConfidenceThreshold: (threshold: number) => void;
}
```

#### 6. **MatrixCell Enhancement** - **MISSING AI SUGGESTION INDICATORS**
**Current:** Basic cell display
**Required:**
- AI suggestion badge overlay
- Confidence score indicator
- Visual differentiation for suggested vs manual resolutions

#### 7. **App Launch Issue** - **CRITICAL BUG**
**Status:** ❌ Electron app not launching (exit code 254)
**Impact:** Cannot test any frontend functionality
**Priority:** Must fix before implementing intent UI

**Gap Impact:** 🔴 **CRITICAL** - Phase C requires **+2-3 additional days** + fix launch issue

---

## Critical Path Analysis

### Immediate Blockers (Must Fix Now)

1. **🚨 Electron App Launch Failure** (exit code 254)
   - **Impact:** Cannot test or develop frontend features
   - **Action:** Debug main.js, check dependencies, verify Vite config
   - **Estimated Fix:** 0.5-1 day

2. **❌ No Intent Schemas** (`backend/schemas/intent.py`)
   - **Impact:** Cannot implement any intent functionality
   - **Action:** Create intent.py with all required schemas
   - **Estimated Effort:** 0.5 days

3. **❌ No Intent Protocol Definitions**
   - **Impact:** Cannot communicate intent operations between frontend/backend
   - **Action:** Add 7 intent method schemas to protocol.py
   - **Estimated Effort:** 0.5 days

### High Priority (Blocking Phase C Completion)

4. **❌ Missing HumanArbitratorNode Intent Fields**
   - **Impact:** Cannot capture intent metadata in HITL actions
   - **Action:** Add 6 intent fields to HumanArbitratorNode schema
   - **Estimated Effort:** 0.25 days

5. **❌ Missing IntentBranchNode Schema**
   - **Impact:** Cannot implement research context isolation
   - **Action:** Create IntentBranchNode in nodes.py
   - **Estimated Effort:** 0.25 days

6. **❌ Missing Intent Edges**
   - **Impact:** Cannot build intent graph relationships
   - **Action:** Add SCOPES, INHERITS_FROM, MATCHES_PATTERN edges
   - **Estimated Effort:** 0.25 days

### Medium Priority (Phase D Requirements)

7. **❌ Intent Learning Engine**
   - **Impact:** No AI suggestions, pattern recognition
   - **Action:** Implement intent_learning_engine.py service
   - **Estimated Effort:** 1.5-2 days

8. **❌ Intent SSP Handlers**
   - **Impact:** Backend cannot respond to intent requests
   - **Action:** Implement 7 intent method handlers
   - **Estimated Effort:** 1-1.5 days

9. **❌ Intent Repository Operations**
   - **Impact:** Cannot persist intent data to graph
   - **Action:** Add IntentBranchNode CRUD, intent edge creation
   - **Estimated Effort:** 0.5-1 day

### Low Priority (Post-MVP Features)

10. **❌ Intent UI Components**
    - **Impact:** No user-facing intent features
    - **Action:** Build 6 intent UI components
    - **Estimated Effort:** 2-3 days

11. **❌ Intent Service Layer**
    - **Impact:** No frontend intent state management
    - **Action:** Create intent_service.ts
    - **Estimated Effort:** 0.5-1 day

---

## Revised MVP Timeline

### Original Estimate
| Phase | Original | Actual | Remaining |
|-------|---------|--------|-----------|
| Phase A | 2-3 days | ✅ Done | +0.5 days (intent schemas) |
| Phase B | 3-4 days | ✅ Done | +2-3 days (intent backend) |
| Phase C | 5-7 days | 🔄 40% | +2-3 days (intent UI) + fix launch |
| **Total** | **10-14 days** | **~6 days** | **~6-8 days remaining** |

### With Intent Framework
| Phase | Base Work | Intent Work | Total | Status |
|-------|-----------|-------------|-------|--------|
| Phase A | ✅ Complete | +0.5 days | **2.5-3.5 days** | 95% done |
| Phase B | ✅ Complete | +2-3 days | **5-7 days** | 90% done |
| Phase C | 🔄 Partial | +2-3 days | **7-10 days** | 40% done |
| **Total** | **~10 days** | **+5-6.5 days** | **15-20 days** | **~60%** |

**Remaining Work:** ~6-8 days (assuming Electron launch issue resolved quickly)

---

## Recommendations

### Immediate Actions (This Sprint)

1. **Fix Electron App Launch** (Priority 1)
   - Debug exit code 254
   - Verify package.json scripts
   - Check Vite config and dependencies
   - Test basic rendering

2. **Complete Phase A Intent Schemas** (Priority 2)
   - Create `backend/schemas/intent.py`
   - Add intent fields to `HumanArbitratorNode`
   - Create `IntentBranchNode`
   - Add 3 intent edges to `edges.py`
   - Add 7 intent protocol schemas to `protocol.py`
   - Write unit tests for new schemas

3. **Implement Core Intent Backend** (Priority 3)
   - Create `IntentLearningEngine` service
   - Add IntentBranchNode CRUD operations
   - Implement intent edge creation methods
   - Add basic intent pattern recognition queries

### Next Sprint (After Frontend Launch)

4. **Add Intent SSP Handlers**
   - Implement 7 intent endpoint handlers
   - Test with Postman/curl before UI work
   - Document API endpoints

5. **Build Basic Intent UI**
   - Start with `IntentBranchSelector` (simple dropdown)
   - Add `IntentMetadataForm` to conflict resolution
   - Implement `AISuggestionBadge` for conflict cells
   - Defer complex components (IntentProfilePanel, IntentDeclarationModal) to Phase D

6. **Integration Testing**
   - Test end-to-end intent capture flow
   - Verify pattern recognition queries
   - Test branch switching functionality

### Post-MVP (Phase D & E)

7. **Advanced Intent Features**
   - Natural language intent queries
   - Smart review queue prioritization
   - Batch intent pattern application
   - Intent profile management UI

8. **Production Hardening**
   - Intent versioning and migration
   - Multi-user intent reconciliation
   - Performance optimization for pattern matching
   - Comprehensive intent framework documentation

---

## Test Coverage Gaps

### Current: 94 tests, 74% coverage
**Missing Test Suites:**

1. **Intent Schema Tests** (`tests/test_intent_schemas.py`) - **NOT FOUND**
   - IntentMetadata validation
   - UserIntentProfile construction
   - IntentPattern matching
   - IntentGoal constraints

2. **Intent Learning Engine Tests** (`tests/test_intent_learning.py`) - **NOT FOUND**
   - Pattern recognition from arbitrator history
   - Confidence score calculation
   - Intent profile building
   - Pattern matching algorithms

3. **Intent Integration Tests** (`tests/test_intent_integration.py`) - **NOT FOUND**
   - Intent branch creation and switching
   - Intent metadata capture in HITL workflows
   - AI suggestion generation
   - Batch pattern application

**Target:** 120+ tests, 80% coverage (including intent framework)

---

## Documentation Gaps

### Completed Documentation
- ✅ `OntoForge.md`: Complete spec including Section 2.6 Intent Framework
- ✅ `backend/docs/SUBDOMAIN_CLASSIFICATION.md`: Classification system guide
- ✅ `PHASE_A_SUMMARY.md`: Phase A completion notes
- ✅ `PHASE_B_COMPLETE.md`: Phase B delivery summary
- ✅ `PHASE_C_COMPLETE.md`: Phase C structure (outdated - app not launching)

### Missing Documentation
- ❌ `backend/docs/INTENT_FRAMEWORK.md`: Intent system implementation guide
- ❌ `backend/docs/INTENT_API.md`: SSP intent method reference
- ❌ `backend/docs/INTENT_PATTERNS.md`: Pattern recognition algorithm details
- ❌ `frontend/docs/INTENT_UI_GUIDE.md`: Intent component usage guide
- ❌ `docs/MIGRATION_GUIDE.md`: Upgrading existing workspaces for intent support

---

## Risk Assessment

### High Risk Items

1. **Electron Launch Failure** - Blocking all frontend work
   - **Mitigation:** Prioritize debugging, consider Vite/Electron version compatibility

2. **Intent Framework Scope Creep** - +5-6.5 days of additional work
   - **Mitigation:** Implement minimal viable intent features first, defer advanced features to Phase D

3. **No LLM Client Integration** - AI suggestions require LLM
   - **Mitigation:** Mock LLM responses for development, add real integration in Phase D

### Medium Risk Items

4. **Pattern Recognition Performance** - Cypher queries may be slow with large datasets
   - **Mitigation:** Index intent fields, cache intent profiles, optimize queries

5. **Intent UI Complexity** - 6 new components + state management
   - **Mitigation:** Start with simplest components (branch selector, metadata form), defer complex UI

### Low Risk Items

6. **Intent Schema Evolution** - May need to update schemas as requirements evolve
   - **Mitigation:** Version intent schemas, implement migration system in Phase E

---

## Conclusion

**Current State:** OntoForge has a solid foundation (Phases A & B complete) but **Intent Framework is 0% implemented**, creating a significant gap between specification and codebase.

**Critical Path:**
1. Fix Electron app launch (0.5-1 day)
2. Complete intent schemas (0.5 days)
3. Implement basic intent backend (2-3 days)
4. Build minimal intent UI (2-3 days)

**Total Remaining:** ~6-8 days to complete MVP with basic intent support

**Recommendation:** Prioritize intent schema work immediately, even before fixing Electron launch, since backend schemas don't depend on frontend. This parallelizes the work and reduces overall timeline.
