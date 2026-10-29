"""
Tests for Intent Framework (Section 2.6)
Tests schemas, nodes, edges, and basic intent operations.
"""

import pytest
from datetime import datetime, timezone
from backend.schemas.intent import (
    IntentMetadata,
    IntentPattern,
    IntentGoal,
    UserIntentProfile,
    AISuggestion,
    IntentBranchOverrides,
    ReviewItem,
)
from backend.schemas.nodes import HumanArbitratorNode, IntentBranchNode
from backend.schemas.edges import ScopesEdge, InheritsFromEdge, MatchesPatternEdge
from backend.schemas.protocol import (
    ConflictResolution,
    SSPDeclareIntentParams,
    SSPCreateIntentBranchParams,
    SSPSwitchIntentContextParams,
    SSPQueryByIntentParams,
    SSPSuggestReviewQueueParams,
    SSPApplyIntentPatternParams,
    SSPQueryIntentProfileParams,
)


class TestIntentSchemas:
    """Test intent schema definitions."""

    def test_intent_metadata_creation(self):
        """Test IntentMetadata schema."""
        metadata = IntentMetadata(
            intent_type="preference",
            intent_scope="pattern",
            generalization_hint="prefer_asic_over_fpga",
            confidence_override=0.9,
            tags=["hardware", "implementation"]
        )
        assert metadata.intent_type == "preference"
        assert metadata.intent_scope == "pattern"
        assert metadata.confidence_override == 0.9
        assert len(metadata.tags) == 2

    def test_intent_pattern_creation(self):
        """Test IntentPattern schema."""
        pattern = IntentPattern(
            pattern_id="hardware_preference_asic",
            confidence=0.85,
            applications=15,
            last_used=datetime.now(timezone.utc),
            intent_type="preference",
            description="User prefers ASIC implementations",
            matched_arbitrator_ids=["arb_1", "arb_2", "arb_3"]
        )
        assert pattern.confidence == 0.85
        assert pattern.applications == 15
        assert len(pattern.matched_arbitrator_ids) == 3

    def test_intent_goal_creation(self):
        """Test IntentGoal schema."""
        goal = IntentGoal(
            goal_id="goal_wdm_survey",
            description="Focus on WDM systems for survey paper",
            constraints={"subdomain": "optical.wdm", "year_range": [2020, 2026]},
            active_from=datetime.now(timezone.utc),
            active_until=None,
            status="active"
        )
        assert goal.status == "active"
        assert goal.constraints["subdomain"] == "optical.wdm"

    def test_user_intent_profile_creation(self):
        """Test UserIntentProfile schema."""
        profile = UserIntentProfile(
            user_id="alice",
            learned_priorities={"asic_preference": 0.9, "low_latency": 0.8},
            preferred_units={"latency": "ns", "bandwidth": "Gbps"},
            evidence_ranking=["experimental", "simulation"],
            active_goals=[],
            subdomain_focus=["optical.wdm", "optical.coherent"],
            temporal_preferences={},
            confidence_threshold=0.8,
            total_intents_captured=42,
            learned_patterns=[]
        )
        assert profile.user_id == "alice"
        assert profile.confidence_threshold == 0.8
        assert profile.total_intents_captured == 42

    def test_ai_suggestion_creation(self):
        """Test AISuggestion schema."""
        suggestion = AISuggestion(
            recommended_assertion_id="assert_123",
            confidence=0.87,
            reasoning="Based on 5 previous similar resolutions",
            matched_intent_patterns=["pattern_1", "pattern_2"],
            user_can_override=True
        )
        assert suggestion.confidence == 0.87
        assert len(suggestion.matched_intent_patterns) == 2
        assert suggestion.user_can_override is True

    def test_review_item_creation(self):
        """Test ReviewItem schema."""
        item = ReviewItem(
            item_id="conflict_42",
            item_type="conflicting_assertions",
            reason="WDM latency conflict between two papers",
            intent_relevance=0.95,
            estimated_time="5 minutes",
            priority="high"
        )
        assert item.intent_relevance == 0.95
        assert item.priority == "high"


class TestIntentNodes:
    """Test intent-enhanced node schemas."""

    def test_human_arbitrator_node_with_intent(self):
        """Test HumanArbitratorNode with intent fields."""
        node = HumanArbitratorNode(
            id="arbitrator_alice_20260524_120000",
            user_id="alice",
            timestamp=datetime.now(timezone.utc),
            arbitration_notes="Prefer ASIC implementation for lower latency",
            lock_type="permanent_human_lock",
            intent_type="preference",
            intent_scope="pattern",
            generalization_hint="prefer_asic_over_fpga",
            confidence_override=0.9,
            intent_branch_id="intent_wdm_survey",
            tags=["hardware", "latency"]
        )
        assert node.intent_type == "preference"
        assert node.intent_scope == "pattern"
        assert node.intent_branch_id == "intent_wdm_survey"
        assert len(node.tags) == 2

    def test_intent_branch_node_creation(self):
        """Test IntentBranchNode schema."""
        node = IntentBranchNode(
            id="intent_wdm_survey_2026",
            branch_name="WDM Survey Paper 2026",
            description="Research context for WDM survey",
            user_id="alice",
            parent_branch_id=None,
            created_at=datetime.now(timezone.utc),
            active_until=None,
            status="active",
            overrides={
                "focus_subdomains": ["optical.wdm"],
                "temporal_filter": {"year_min": 2020}
            }
        )
        assert node.status == "active"
        assert node.overrides["focus_subdomains"] == ["optical.wdm"]


class TestIntentEdges:
    """Test intent edge schemas."""

    def test_scopes_edge_creation(self):
        """Test ScopesEdge schema."""
        edge = ScopesEdge(
            from_node_id="intent_wdm_survey",
            to_node_id="arbitrator_alice_20260524_120000"
        )
        assert edge.from_node_id == "intent_wdm_survey"
        assert edge.to_node_id == "arbitrator_alice_20260524_120000"

    def test_inherits_from_edge_creation(self):
        """Test InheritsFromEdge schema."""
        edge = InheritsFromEdge(
            from_node_id="intent_wdm_survey_v2",
            to_node_id="intent_wdm_survey_v1"
        )
        assert edge.from_node_id == "intent_wdm_survey_v2"
        assert edge.to_node_id == "intent_wdm_survey_v1"

    def test_matches_pattern_edge_creation(self):
        """Test MatchesPatternEdge schema."""
        edge = MatchesPatternEdge(
            from_node_id="arbitrator_1",
            to_node_id="arbitrator_2",
            pattern_id="hardware_preference_asic",
            confidence=0.87
        )
        assert edge.pattern_id == "hardware_preference_asic"
        assert edge.confidence == 0.87


class TestIntentProtocols:
    """Test intent protocol schemas."""

    def test_conflict_resolution_with_intent(self):
        """Test ConflictResolution with intent_metadata."""
        metadata = IntentMetadata(
            intent_type="priority",
            intent_scope="local",
            generalization_hint="prefer_newer_data",
            confidence_override=None,
            tags=["temporal"]
        )
        resolution = ConflictResolution(
            accepted_assertion_id="assert_new",
            overridden_assertion_id="assert_old",
            arbitrator_notes="Using newer data source",
            lock_status="permanent_human_lock",
            intent_metadata=metadata
        )
        assert resolution.intent_metadata is not None
        assert resolution.intent_metadata.intent_type == "priority"

    def test_ssp_declare_intent_params(self):
        """Test SSPDeclareIntentParams schema."""
        params = SSPDeclareIntentParams(
            intent_type="goal",
            intent_scope="global",
            description="Complete WDM survey by June 2026",
            constraints={"subdomain": "optical.wdm", "deadline": "2026-06-30"},
            active_from="2026-05-24T00:00:00Z",
            active_until="2026-06-30T23:59:59Z"
        )
        assert params.intent_type == "goal"
        assert params.intent_scope == "global"

    def test_ssp_create_intent_branch_params(self):
        """Test SSPCreateIntentBranchParams schema."""
        params = SSPCreateIntentBranchParams(
            branch_name="WDM Survey 2026",
            description="Research context for survey paper",
            inherit_from="intent_base_optical",
            overrides=IntentBranchOverrides(
                focus_subdomains=["optical.wdm"],
                temporal_filter={"year_min": 2020},
                priority_metrics=["latency", "bandwidth"]
            )
        )
        assert params.branch_name == "WDM Survey 2026"
        assert params.overrides.focus_subdomains == ["optical.wdm"]

    def test_ssp_switch_intent_context_params(self):
        """Test SSPSwitchIntentContextParams schema."""
        params = SSPSwitchIntentContextParams(
            branch_id="intent_wdm_survey_2026"
        )
        assert params.branch_id == "intent_wdm_survey_2026"

    def test_ssp_query_by_intent_params(self):
        """Test SSPQueryByIntentParams schema."""
        params = SSPQueryByIntentParams(
            query="WDM coherent detection latency",
            intent_context="intent_wdm_survey_2026"
        )
        assert params.query == "WDM coherent detection latency"
        assert params.intent_context == "intent_wdm_survey_2026"

    def test_ssp_suggest_review_queue_params(self):
        """Test SSPSuggestReviewQueueParams schema."""
        params = SSPSuggestReviewQueueParams(
            strategy="intent_aligned",
            limit=20
        )
        assert params.strategy == "intent_aligned"
        assert params.limit == 20

    def test_ssp_apply_intent_pattern_params(self):
        """Test SSPApplyIntentPatternParams schema."""
        params = SSPApplyIntentPatternParams(
            pattern_id="hardware_preference_asic",
            scope={"domain": "optical.wdm"},
            dry_run=True
        )
        assert params.pattern_id == "hardware_preference_asic"
        assert params.dry_run is True

    def test_ssp_query_intent_profile_params(self):
        """Test SSPQueryIntentProfileParams schema."""
        params = SSPQueryIntentProfileParams(
            user_id="alice",
            detail_level="full"
        )
        assert params.user_id == "alice"
        assert params.detail_level == "full"


class TestIntentIntegration:
    """Integration tests for intent components."""

    def test_complete_intent_workflow(self):
        """Test a complete intent capture workflow."""
        # 1. Create intent metadata
        metadata = IntentMetadata(
            intent_type="preference",
            intent_scope="pattern",
            generalization_hint="prefer_asic_implementations",
            confidence_override=0.9,
            tags=["hardware", "performance"]
        )

        # 2. Create arbitrator node with intent
        arbitrator = HumanArbitratorNode(
            id="arbitrator_test_001",
            user_id="alice",
            timestamp=datetime.now(timezone.utc),
            arbitration_notes="Choosing ASIC for better performance",
            lock_type="permanent_human_lock",
            intent_type=metadata.intent_type,
            intent_scope=metadata.intent_scope,
            generalization_hint=metadata.generalization_hint,
            confidence_override=metadata.confidence_override,
            intent_branch_id="intent_wdm_survey",
            tags=metadata.tags
        )

        # 3. Create intent branch
        branch = IntentBranchNode(
            id="intent_wdm_survey",
            branch_name="WDM Survey",
            description="Survey paper on WDM systems",
            user_id="alice",
            parent_branch_id=None,
            created_at=datetime.now(timezone.utc),
            active_until=None,
            status="active",
            overrides={"focus_subdomains": ["optical.wdm"]}
        )

        # 4. Create SCOPES edge
        scopes_edge = ScopesEdge(
            from_node_id=branch.id,
            to_node_id=arbitrator.id
        )

        # Verify complete workflow
        assert arbitrator.intent_branch_id == branch.id
        assert scopes_edge.from_node_id == branch.id
        assert scopes_edge.to_node_id == arbitrator.id

    def test_intent_pattern_learning(self):
        """Test intent pattern representation."""
        pattern = IntentPattern(
            pattern_id="prefer_asic_over_fpga",
            confidence=0.85,
            applications=12,
            last_used=datetime.now(timezone.utc),
            intent_type="preference",
            description="User consistently prefers ASIC over FPGA implementations",
            matched_arbitrator_ids=[f"arb_{i}" for i in range(12)]
        )

        # Verify pattern can generate AI suggestions
        suggestion = AISuggestion(
            recommended_assertion_id="assert_asic_123",
            confidence=pattern.confidence,
            reasoning=f"Based on {pattern.applications} previous decisions matching pattern '{pattern.pattern_id}'",
            matched_intent_patterns=[pattern.pattern_id],
            user_can_override=True
        )

        assert suggestion.confidence == pattern.confidence
        assert pattern.pattern_id in suggestion.matched_intent_patterns
