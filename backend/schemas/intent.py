"""
Intent Framework Schema Definitions
Pydantic models for intent-based interaction system as per Section 2.6 of the specification.
"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class IntentMetadata(BaseModel):
    """
    Metadata captured during HITL actions to classify user intent.
    Used to build learned preference patterns and enable AI suggestions.
    """
    intent_type: Literal["correction", "preference", "priority", "constraint", "goal"] = Field(
        ...,
        description="Classifies the intent level on the tactical-strategic spectrum (Section 2.6.1)"
    )
    intent_scope: Literal["local", "pattern", "global"] = Field(
        ...,
        description="Defines the generalization potential of this intent"
    )
    generalization_hint: Optional[str] = Field(
        None,
        description="Human-readable pattern description, e.g., 'Prefer ASIC over FPGA for baseline selection'"
    )
    confidence_override: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="User's confidence in this decision (0.0-1.0)"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Categorization tags, e.g., ['hardware_preference', 'baseline_selection']"
    )

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "intent_type": "priority",
            "intent_scope": "pattern",
            "generalization_hint": "Prefer ASIC over FPGA for reconfiguration_delay baselines",
            "confidence_override": 1.0,
            "tags": ["hardware_preference", "baseline_selection"]
        }
    })


class IntentPattern(BaseModel):
    """
    A learned preference pattern extracted from HumanArbitratorNode history.
    Represents recurring decision patterns that can be applied to future conflicts.
    """
    pattern_id: str = Field(..., description="Unique identifier for this pattern")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score based on frequency and recency")
    applications: int = Field(..., ge=0, description="Number of times this pattern has been applied")
    last_used: datetime = Field(..., description="Timestamp of most recent application")
    intent_type: Literal["correction", "preference", "priority", "constraint", "goal"] = Field(
        ...,
        description="Type of intent this pattern represents"
    )
    description: str = Field(..., description="Human-readable pattern description")
    matched_arbitrator_ids: List[str] = Field(
        default_factory=list,
        description="IDs of HumanArbitratorNodes that contributed to this pattern"
    )

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "pattern_id": "hardware_preference_asic_over_fpga",
            "confidence": 0.87,
            "applications": 23,
            "last_used": "2026-05-20T14:30:22Z",
            "intent_type": "priority",
            "description": "Prefer ASIC implementations over FPGA for reconfiguration_delay baselines",
            "matched_arbitrator_ids": ["arbitrator_alice_001", "arbitrator_alice_012"]
        }
    })


class IntentGoal(BaseModel):
    """
    Strategic research goal declared by the user.
    Shapes all subsequent operations (filtering, prioritization, suggestions).
    """
    goal_id: str = Field(..., description="Unique identifier, e.g., intent_wdm_survey_2026")
    description: str = Field(..., description="Human-readable goal description")
    constraints: Dict[str, Any] = Field(
        default_factory=dict,
        description="Goal-specific constraints (subdomain filters, temporal ranges, metric priorities)"
    )
    active_from: datetime = Field(..., description="When this goal becomes active")
    active_until: Optional[datetime] = Field(None, description="Optional expiration date for time-bound projects")
    status: Literal["active", "paused", "completed", "cancelled"] = Field(
        default="active",
        description="Current status of this goal"
    )

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "goal_id": "intent_wdm_survey_2026",
            "description": "Build comprehensive WDM performance comparison matrix for survey paper",
            "constraints": {
                "focus_subdomains": ["domain.networking.optical.wdm"],
                "time_range": {"min_year": 2020, "max_year": 2026},
                "required_metrics": ["reconfiguration_delay", "cross_talk", "spectral_efficiency"]
            },
            "active_from": "2026-05-24T00:00:00Z",
            "active_until": "2026-08-15T23:59:59Z",
            "status": "active"
        }
    })


class UserIntentProfile(BaseModel):
    """
    Aggregated intent profile for a user, learned from HITL action history.
    Used to compute AI suggestion confidence and prioritize review queues.
    """
    user_id: str = Field(..., description="User identifier")
    learned_priorities: Dict[str, float] = Field(
        default_factory=dict,
        description="Learned priority mappings, e.g., {'asic_over_fpga': 0.87}"
    )
    preferred_units: Dict[str, str] = Field(
        default_factory=dict,
        description="Preferred units by metric, e.g., {'reconfiguration_delay': 'ms'}"
    )
    evidence_ranking: List[str] = Field(
        default_factory=list,
        description="Ordered list of evidence types by preference, e.g., ['experimental', 'simulation', 'analytical']"
    )
    active_goals: List[IntentGoal] = Field(
        default_factory=list,
        description="Currently active strategic goals"
    )
    subdomain_focus: List[str] = Field(
        default_factory=list,
        description="User's primary research subdomains"
    )
    temporal_preferences: Dict[str, Any] = Field(
        default_factory=dict,
        description="Temporal constraints, e.g., preferred year ranges"
    )
    confidence_threshold: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Minimum confidence for auto-suggestions (user-configurable)"
    )
    total_intents_captured: int = Field(default=0, ge=0, description="Total number of HITL actions recorded")
    learned_patterns: List[IntentPattern] = Field(
        default_factory=list,
        description="All learned intent patterns for this user"
    )

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "user_id": "scholar_123",
            "learned_priorities": {
                "asic_over_fpga": 0.87,
                "peer_reviewed_over_arxiv": 0.92
            },
            "preferred_units": {
                "reconfiguration_delay": "ms",
                "cross_talk": "dB"
            },
            "evidence_ranking": ["experimental", "simulation", "analytical"],
            "active_goals": [],
            "subdomain_focus": ["domain.networking.optical.wdm"],
            "temporal_preferences": {"preferred_min_year": 2020},
            "confidence_threshold": 0.8,
            "total_intents_captured": 127,
            "learned_patterns": []
        }
    })


class AISuggestion(BaseModel):
    """
    AI-generated suggestion for conflict resolution based on learned intent patterns.
    Displayed in conflict resolution UI with reasoning and confidence.
    """
    recommended_assertion_id: str = Field(..., description="Suggested assertion to accept")
    confidence: float = Field(..., ge=0.0, le=1.0, description="AI confidence in this suggestion")
    reasoning: str = Field(..., description="Human-readable explanation for the suggestion")
    matched_intent_patterns: List[str] = Field(
        default_factory=list,
        description="Pattern IDs that contributed to this suggestion"
    )
    user_can_override: bool = Field(default=True, description="Whether user can reject this suggestion")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "recommended_assertion_id": "assert_201",
            "confidence": 0.87,
            "reasoning": "Based on your 23 previous conflict resolutions (87% preference), you consistently prefer ASIC implementations over FPGA for reconfiguration_delay baselines.",
            "matched_intent_patterns": [
                "hardware_preference_asic_over_fpga",
                "baseline_selection_production_ready"
            ],
            "user_can_override": True
        }
    })


class IntentBranchOverrides(BaseModel):
    """
    Context-specific preferences for an intent branch.
    Overrides global user preferences when this branch is active.
    """
    focus_subdomains: List[str] = Field(default_factory=list, description="Subdomain filters")
    temporal_filter: Dict[str, Any] = Field(default_factory=dict, description="Temporal constraints")
    priority_metrics: List[str] = Field(default_factory=list, description="Prioritized metrics")
    excluded_papers: List[str] = Field(default_factory=list, description="Papers to exclude from this context")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "focus_subdomains": ["domain.networking.optical.wdm"],
            "temporal_filter": {"min_year": 2020},
            "priority_metrics": ["reconfiguration_delay", "spectral_efficiency"],
            "excluded_papers": []
        }
    })


class ReviewItem(BaseModel):
    """
    Item in the smart review queue, prioritized by intent relevance.
    """
    item_type: Literal[
        "low_confidence_classification",
        "missing_context",
        "conflicting_assertions",
        "incomplete_extraction",
        "visual_fallback_alert"
    ] = Field(..., description="Type of review needed")
    item_id: str = Field(..., description="ID of the item requiring review (paper_id, assertion_id, etc.)")
    reason: str = Field(..., description="Human-readable explanation of why review is needed")
    estimated_time: str = Field(..., description="Estimated time to resolve, e.g., '30 seconds', '2 minutes'")
    intent_relevance: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Relevance to user's active goals and learned patterns"
    )
    priority: Literal["high", "medium", "low"] = Field(default="medium", description="Review priority")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "item_type": "low_confidence_classification",
            "item_id": "paper_ambiguous_2026",
            "reason": "Subdomain classification confidence 0.65 - your past reclassification patterns could help",
            "estimated_time": "30 seconds",
            "intent_relevance": 0.92,
            "priority": "high"
        }
    })
