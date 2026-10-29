"""
Intent Learning Engine
Analyzes HumanArbitratorNode history to extract patterns and build user intent profiles.
Implements pattern recognition and AI suggestion confidence computation (Section 2.6.3).
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict, Counter

from ..schemas.intent import (
    IntentPattern,
    UserIntentProfile,
    IntentGoal,
    AISuggestion
)
from ..schemas.nodes import HumanArbitratorNode
from ..database.node_repository import NodeRepository
from ..database.edge_repository import EdgeRepository


class IntentLearningEngine:
    """
    Learns from user's HITL action history to build intent profiles and suggest resolutions.
    Core component of the Intent Framework (Section 2.6).
    """
    
    def __init__(self, node_repo: NodeRepository, edge_repo: EdgeRepository):
        self.node_repo = node_repo
        self.edge_repo = edge_repo
    
    async def analyze_arbitrator_history(
        self,
        user_id: str,
        days: int = 90,
        min_frequency: int = 3
    ) -> List[IntentPattern]:
        """
        Extract intent patterns from HumanArbitratorNode history using Cypher queries.
        
        Implementation of pattern recognition queries from Section 2.6.3:
        - Groups arbitrator nodes by generalization_hint
        - Calculates frequency and confidence scores
        - Returns patterns meeting minimum frequency threshold
        
        Args:
            user_id: User identifier
            days: Lookback period for history analysis
            min_frequency: Minimum occurrences to qualify as a pattern
            
        Returns:
            List of learned IntentPattern objects
        """
        cutoff_date = datetime.now() - timedelta(days=days)
        
        # Cypher query from Section 2.6.3
        query = """
        MATCH (h:HumanArbitratorNode {user_id: $user_id})
        WHERE h.timestamp > datetime($cutoff_date)
          AND h.intent_type IN ['priority', 'preference', 'constraint']
          AND h.generalization_hint IS NOT NULL
        WITH h.generalization_hint as hint,
             h.intent_type as type,
             collect(h.id) as arbitrator_ids,
             count(*) as frequency,
             max(h.timestamp) as last_used
        WHERE frequency >= $min_frequency
        RETURN hint, type, arbitrator_ids, frequency, last_used
        ORDER BY frequency DESC, last_used DESC
        """
        
        results = self.node_repo.execute_query(
            query,
            {
                "user_id": user_id,
                "cutoff_date": cutoff_date.isoformat(),
                "min_frequency": min_frequency
            }
        )
        
        patterns = []
        for record in results:
            pattern_id = self._generate_pattern_id(record["hint"])
            confidence = min(1.0, record["frequency"] / 30.0)  # Confidence saturates at 30 applications
            
            patterns.append(IntentPattern(
                pattern_id=pattern_id,
                confidence=confidence,
                applications=record["frequency"],
                last_used=datetime.fromisoformat(record["last_used"]),
                intent_type=record["type"],
                description=record["hint"],
                matched_arbitrator_ids=record["arbitrator_ids"]
            ))
        
        return patterns
    
    async def build_user_intent_profile(
        self,
        user_id: str,
        active_goals: Optional[List[IntentGoal]] = None
    ) -> UserIntentProfile:
        return self.build_user_intent_profile_sync(user_id, active_goals)

    def build_user_intent_profile_sync(
        self,
        user_id: str,
        active_goals: Optional[List[IntentGoal]] = None
    ) -> UserIntentProfile:
        """
        Construct comprehensive UserIntentProfile from learned patterns.
        
        Aggregates:
        - Learned priorities (from priority intents)
        - Preferred units (from preference intents)
        - Evidence ranking (from conflict resolution history)
        - Subdomain focus (from paper/domain interactions)
        - Temporal preferences (from year filters in goals)
        
        Args:
            user_id: User identifier
            active_goals: List of active IntentGoal objects
            
        Returns:
            UserIntentProfile with all learned preferences
        """
        patterns = self._analyze_arbitrator_history_sync(user_id)
        explicit_declarations = self._get_explicit_declarations_sync(user_id)
        explicit_goals = self._build_explicit_goals(explicit_declarations)
        explicit_patterns = self._build_explicit_patterns(explicit_declarations)
        patterns = self._merge_patterns(patterns, explicit_patterns)
        
        # Extract priority mappings
        learned_priorities = {}
        for pattern in patterns:
            if pattern.intent_type == "priority":
                learned_priorities[pattern.pattern_id] = pattern.confidence
        
        # Extract preferred units (from preference patterns)
        preferred_units = self._extract_unit_preferences_sync(user_id)
        
        # Infer evidence ranking from conflict resolution history
        evidence_ranking = self._infer_evidence_ranking_sync(user_id)
        
        # Determine subdomain focus from classification actions
        subdomain_focus = self._get_subdomain_focus_sync(user_id)
        
        # Get total intent count
        total_intents = self._count_total_intents_sync(user_id)
        
        return UserIntentProfile(
            user_id=user_id,
            learned_priorities=learned_priorities,
            preferred_units=preferred_units,
            evidence_ranking=evidence_ranking,
            active_goals=self._merge_goals(active_goals or [], explicit_goals),
            subdomain_focus=subdomain_focus,
            temporal_preferences={},
            confidence_threshold=0.8,  # Default, user can override
            total_intents_captured=total_intents,
            learned_patterns=patterns
        )

    def _analyze_arbitrator_history_sync(
        self,
        user_id: str,
        days: int = 90,
        min_frequency: int = 3
    ) -> List[IntentPattern]:
        cutoff_date = datetime.now() - timedelta(days=days)

        query = """
        MATCH (h:HumanArbitratorNode {user_id: $user_id})
        WHERE h.timestamp > datetime($cutoff_date)
          AND h.intent_type IN ['priority', 'preference', 'constraint']
          AND h.generalization_hint IS NOT NULL
        WITH h.generalization_hint as hint,
             h.intent_type as type,
             collect(h.id) as arbitrator_ids,
             count(*) as frequency,
             max(h.timestamp) as last_used
        WHERE frequency >= $min_frequency
        RETURN hint, type, arbitrator_ids, frequency, last_used
        ORDER BY frequency DESC, last_used DESC
        """

        results = self.node_repo.execute_query(
            query,
            {
                "user_id": user_id,
                "cutoff_date": cutoff_date.isoformat(),
                "min_frequency": min_frequency
            }
        )

        patterns = []
        for record in results:
            pattern_id = self._generate_pattern_id(record["hint"])
            confidence = min(1.0, record["frequency"] / 30.0)
            patterns.append(IntentPattern(
                pattern_id=pattern_id,
                confidence=confidence,
                applications=record["frequency"],
                last_used=datetime.fromisoformat(record["last_used"]),
                intent_type=record["type"],
                description=record["hint"],
                matched_arbitrator_ids=record["arbitrator_ids"]
            ))

        return patterns
    
    async def compute_suggestion_confidence(
        self,
        conflict: Dict[str, Any],
        profile: UserIntentProfile
    ) -> Tuple[Optional[str], float, List[str]]:
        """
        Calculate confidence for AI-suggested resolution based on learned intent.
        
        Implements AI suggestion logic from Section 2.6.4:
        - Matches conflict context against learned patterns
        - Computes aggregate confidence from matching patterns
        - Returns suggested assertion ID if confidence exceeds threshold
        
        Args:
            conflict: Conflict data with nodes and context
            profile: User's intent profile
            
        Returns:
            Tuple of (suggested_assertion_id, confidence, matched_pattern_ids)
        """
        matched_patterns = []
        confidence_scores = []
        
        # Check for hardware preference patterns
        for node in conflict.get("nodes", []):
            implementation = node.get("implementation", "")
            
            for pattern in profile.learned_patterns:
                if pattern.intent_type == "priority":
                    # Check if pattern applies to this conflict
                    if self._pattern_matches_conflict(pattern, conflict, node):
                        matched_patterns.append(pattern.pattern_id)
                        confidence_scores.append(pattern.confidence)
        
        if not matched_patterns:
            return None, 0.0, []
        
        # Aggregate confidence (average of matching patterns)
        aggregate_confidence = sum(confidence_scores) / len(confidence_scores)
        
        # Determine which assertion to recommend based on matched patterns
        recommended_id = self._select_assertion_from_patterns(
            conflict, matched_patterns, profile
        )
        
        return recommended_id, aggregate_confidence, matched_patterns
    
    async def match_intent_patterns(
        self,
        arbitrator_node: HumanArbitratorNode
    ) -> List[Tuple[str, float]]:
        """
        Find similar intent patterns for MATCHES_PATTERN edges.
        
        Compares new arbitrator node against existing patterns:
        - Uses generalization_hint similarity
        - Checks intent_type matching
        - Computes similarity confidence score
        
        Args:
            arbitrator_node: Newly created HumanArbitratorNode
            
        Returns:
            List of (arbitrator_id, confidence) tuples for similar patterns
        """
        if not arbitrator_node.generalization_hint:
            return []
        
        query = """
        MATCH (h:HumanArbitratorNode {user_id: $user_id})
        WHERE h.id <> $current_id
          AND h.generalization_hint IS NOT NULL
          AND h.intent_type = $intent_type
        RETURN h.id as id, h.generalization_hint as hint
        """
        
        results = self.node_repo.execute_query(
            query,
            {
                "user_id": arbitrator_node.user_id,
                "current_id": arbitrator_node.id,
                "intent_type": arbitrator_node.intent_type
            }
        )
        
        matches = []
        for record in results:
            similarity = self._compute_text_similarity(
                arbitrator_node.generalization_hint,
                record["hint"]
            )
            if similarity > 0.7:  # Similarity threshold
                matches.append((record["id"], similarity))
        
        return sorted(matches, key=lambda x: x[1], reverse=True)
    
    def generate_ai_suggestion(
        self,
        conflict: Dict[str, Any],
        profile: UserIntentProfile
    ) -> Optional[AISuggestion]:
        """
        Generate AI suggestion for conflict resolution UI display.
        
        Implements Section 2.6.4 AI suggestion generation:
        - Computes suggestion confidence
        - Builds human-readable reasoning
        - Returns None if confidence below threshold
        
        Args:
            conflict: Conflict data
            profile: User's intent profile
            
        Returns:
            AISuggestion object or None
        """
        import asyncio
        
        # Run async method in sync context (for convenience)
        loop = asyncio.get_event_loop()
        recommended_id, confidence, matched_patterns = loop.run_until_complete(
            self.compute_suggestion_confidence(conflict, profile)
        )
        
        if not recommended_id or confidence < profile.confidence_threshold:
            return None
        
        # Build reasoning text
        pattern_count = len(matched_patterns)
        reasoning = (
            f"Based on your {pattern_count} previous conflict resolutions "
            f"({int(confidence * 100)}% preference), you consistently prefer "
            f"the selected assertion for this context."
        )
        
        return AISuggestion(
            recommended_assertion_id=recommended_id,
            confidence=confidence,
            reasoning=reasoning,
            matched_intent_patterns=matched_patterns,
            user_can_override=True
        )
    
    # ========================================================================
    # Private Helper Methods
    # ========================================================================
    
    def _generate_pattern_id(self, hint: str) -> str:
        """Generate pattern ID from generalization hint."""
        return hint.lower().replace(" ", "_").replace("-", "_")
    
    async def _extract_unit_preferences(self, user_id: str) -> Dict[str, str]:
        return self._extract_unit_preferences_sync(user_id)

    def _extract_unit_preferences_sync(self, user_id: str) -> Dict[str, str]:
        """Extract preferred units from preference-type intents."""
        query = """
        MATCH (h:HumanArbitratorNode {user_id: $user_id, intent_type: 'preference'})
        WHERE h.arbitration_notes CONTAINS 'unit' OR h.arbitration_notes CONTAINS 'ms' OR h.arbitration_notes CONTAINS 'dB'
        RETURN h.arbitration_notes as notes, h.tags as tags
        """
        
        results = self.node_repo.execute_query(query, {"user_id": user_id})
        
        # Simple parsing logic (can be enhanced with NLP)
        unit_prefs = {}
        for record in results:
            tags = record.get("tags", [])
            for tag in tags:
                if "unit_" in tag:
                    parts = tag.split("_")
                    if len(parts) >= 3:
                        metric = parts[1]
                        unit = parts[2]
                        unit_prefs[metric] = unit
        
        return unit_prefs
    
    async def _infer_evidence_ranking(self, user_id: str) -> List[str]:
        return self._infer_evidence_ranking_sync(user_id)

    def _infer_evidence_ranking_sync(self, user_id: str) -> List[str]:
        """Infer evidence type preferences from conflict resolution history."""
        query = """
        MATCH (h:HumanArbitratorNode {user_id: $user_id})-[:LOCKS]->(a:AssertionNode)
        MATCH (a)<-[:EVIDENCED_BY]-(e)
        WHERE e:ChunkNode OR e:FormulaNode
        WITH labels(e)[0] as evidence_type, count(*) as freq
        RETURN evidence_type, freq
        ORDER BY freq DESC
        """
        
        results = self.node_repo.execute_query(query, {"user_id": user_id})
        
        return [record["evidence_type"] for record in results]
    
    async def _get_subdomain_focus(self, user_id: str) -> List[str]:
        return self._get_subdomain_focus_sync(user_id)

    def _get_subdomain_focus_sync(self, user_id: str) -> List[str]:
        """Determine user's primary research subdomains."""
        query = """
        MATCH (h:HumanArbitratorNode {user_id: $user_id})-[:LOCKS]->(a:AssertionNode)
        MATCH (a)<-[:EVIDENCED_BY]-(chunk)-[:CONTAINS]-(p:PaperNode)
        MATCH (p)-[:BELONGS_TO]->(d:DomainNode)
        WITH d.id as subdomain_id, count(*) as freq
        RETURN subdomain_id, freq
        ORDER BY freq DESC
        LIMIT 5
        """
        
        results = self.node_repo.execute_query(query, {"user_id": user_id})
        
        return [record["subdomain_id"] for record in results]
    
    async def _count_total_intents(self, user_id: str) -> int:
        return self._count_total_intents_sync(user_id)

    def _count_total_intents_sync(self, user_id: str) -> int:
        """Count total HITL actions for this user."""
        query = """
        MATCH (h:HumanArbitratorNode {user_id: $user_id})
        RETURN count(h) as total
        """
        
        results = self.node_repo.execute_query(query, {"user_id": user_id})
        
        return results[0]["total"] if results else 0

    async def _get_explicit_declarations(self, user_id: str) -> List[Dict[str, Any]]:
        return self._get_explicit_declarations_sync(user_id)

    def _get_explicit_declarations_sync(self, user_id: str) -> List[Dict[str, Any]]:
        """Fetch explicit declarations that should survive page reloads."""
        query = """
        MATCH (h:HumanArbitratorNode {user_id: $user_id})
        WHERE 'explicit_declaration' IN coalesce(h.tags, [])
          AND h.intent_type IS NOT NULL
        RETURN h.id as id,
               h.timestamp as timestamp,
               h.arbitration_notes as description,
               h.intent_type as intent_type,
               h.intent_scope as intent_scope,
               h.generalization_hint as generalization_hint,
               h.confidence_override as confidence_override,
               h.declaration_constraints as declaration_constraints
        ORDER BY h.timestamp DESC
        """
        results = self.node_repo.execute_query(query, {"user_id": user_id})

        normalized: List[Dict[str, Any]] = []
        for record in results:
            constraints = record.get("declaration_constraints") or {}
            if isinstance(constraints, str):
                import json
                constraints = json.loads(constraints)
            normalized.append({**record, "declaration_constraints": constraints})
        return normalized

    def _build_explicit_goals(self, declarations: List[Dict[str, Any]]) -> List[IntentGoal]:
        goals: List[IntentGoal] = []
        for declaration in declarations:
            if declaration.get("intent_type") != "goal":
                continue
            goals.append(IntentGoal(
                goal_id=declaration["id"],
                description=declaration.get("description") or declaration.get("generalization_hint") or "Declared goal",
                constraints=declaration.get("declaration_constraints") or {},
                active_from=self._coerce_datetime(declaration.get("timestamp")),
                active_until=None,
                status="active",
            ))
        return goals

    def _build_explicit_patterns(self, declarations: List[Dict[str, Any]]) -> List[IntentPattern]:
        patterns: List[IntentPattern] = []
        for declaration in declarations:
            intent_type = declaration.get("intent_type")
            if intent_type not in {"correction", "preference", "priority", "constraint"}:
                continue
            patterns.append(IntentPattern(
                pattern_id=declaration["id"],
                confidence=declaration.get("confidence_override") or 1.0,
                applications=1,
                last_used=self._coerce_datetime(declaration.get("timestamp")),
                intent_type=intent_type,
                description=declaration.get("generalization_hint") or declaration.get("description") or declaration["id"],
                matched_arbitrator_ids=[declaration["id"]],
            ))
        return patterns

    def _merge_goals(self, learned_goals: List[IntentGoal], explicit_goals: List[IntentGoal]) -> List[IntentGoal]:
        seen_goal_ids = {goal.goal_id for goal in learned_goals}
        merged = list(learned_goals)
        for goal in explicit_goals:
            if goal.goal_id not in seen_goal_ids:
                merged.append(goal)
        return merged

    def _merge_patterns(self, learned_patterns: List[IntentPattern], explicit_patterns: List[IntentPattern]) -> List[IntentPattern]:
        seen_pattern_ids = {pattern.pattern_id for pattern in learned_patterns}
        merged = list(learned_patterns)
        for pattern in explicit_patterns:
            if pattern.pattern_id not in seen_pattern_ids:
                merged.append(pattern)
        merged.sort(key=lambda pattern: pattern.last_used, reverse=True)
        return merged

    def _coerce_datetime(self, value: Any) -> datetime:
        if isinstance(value, datetime):
            return value
        if value is None:
            return datetime.now()
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    
    def _pattern_matches_conflict(
        self,
        pattern: IntentPattern,
        conflict: Dict[str, Any],
        node: Dict[str, Any]
    ) -> bool:
        """Check if a pattern applies to a specific conflict node."""
        hint = pattern.description.lower()
        
        # Example: "prefer asic over fpga"
        if "asic" in hint and "fpga" in hint:
            implementation = node.get("implementation", "").lower()
            if "asic" in implementation:
                return True
        
        # Can be enhanced with more sophisticated matching
        return False
    
    def _select_assertion_from_patterns(
        self,
        conflict: Dict[str, Any],
        matched_patterns: List[str],
        profile: UserIntentProfile
    ) -> Optional[str]:
        """Select which assertion to recommend based on matched patterns."""
        nodes = conflict.get("nodes", [])
        
        for pattern_id in matched_patterns:
            if "asic_over_fpga" in pattern_id:
                # Find ASIC implementation
                for node in nodes:
                    if "asic" in node.get("implementation", "").lower():
                        return node.get("assertion_id")
        
        # Default: return first node if no specific match
        return nodes[0].get("assertion_id") if nodes else None
    
    def _compute_text_similarity(self, text1: str, text2: str) -> float:
        """Compute simple text similarity (can be enhanced with embeddings)."""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union) if union else 0.0
