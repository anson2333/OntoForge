"""Typed, explainable entity resolution for domain-pack mentions."""

from __future__ import annotations

import hashlib
import re
from difflib import SequenceMatcher

from backend.schemas.domain_pack import DomainPackConfig
from backend.schemas.ontology import (
    EntityCandidate,
    EntityMention,
    EntityResolutionDecision,
    EntityType,
    ResolutionKind,
)


def normalized_mention(value: str) -> str:
    """Normalize typography while preserving dataset-composition operators."""
    semantic = value.casefold().replace("++", " plus_plus ").replace("+", " plus ")
    return re.sub(r"[^a-z0-9]+", "", semantic)


def scoped_entity_id(workspace_id: str, domain_id: str, entity_type: str, local_id: str) -> str:
    scope = f"{workspace_id}\0{domain_id}\0{entity_type}\0{local_id}"
    return "entity_" + hashlib.sha256(scope.encode("utf-8")).hexdigest()


class EntityResolver:
    """Resolve exact typed aliases; fuzzy similarity is suggestion-only."""

    def __init__(self, config: DomainPackConfig):
        self.config = config

    def resolve_mention(self, mention: EntityMention) -> EntityResolutionDecision:
        definitions = [
            definition for definition in self.config.ontology.entities
            if definition.entity_type == mention.entity_type.value
        ]
        key = normalized_mention(mention.text)
        exact = []
        suggestions = []
        for definition in definitions:
            terms = [definition.name, *definition.aliases]
            matching = next((term for term in terms if normalized_mention(term) == key), None)
            entity_id = scoped_entity_id(
                mention.workspace_id,
                mention.domain_id,
                definition.entity_type,
                definition.id,
            )
            if matching is not None:
                exact.append(EntityCandidate(
                    entity_id=entity_id,
                    canonical_name=definition.name,
                    entity_type=mention.entity_type,
                    score=1.0,
                    matched_alias=matching,
                ))
                continue
            score = max(
                (SequenceMatcher(None, key, normalized_mention(term)).ratio() for term in terms),
                default=0.0,
            )
            if score >= 0.72:
                suggestions.append(EntityCandidate(
                    entity_id=entity_id,
                    canonical_name=definition.name,
                    entity_type=mention.entity_type,
                    score=round(score, 4),
                ))

        decision_id = "resolution_" + hashlib.sha256(
            f"{mention.workspace_id}\0{mention.id}\0{self.config.ontology.rule_version}".encode()
        ).hexdigest()
        if len(exact) == 1:
            proposed = mention.context.get("proposed_entity_id")
            if proposed and proposed != exact[0].entity_id:
                return EntityResolutionDecision(
                    id=decision_id, workspace_id=mention.workspace_id, domain_id=mention.domain_id,
                    mention=mention, candidates=exact, selected_entity_id=exact[0].entity_id,
                    decision=ResolutionKind.DISTINCT, rule_id="typed_exact_conflict_v1",
                    rule_version=self.config.ontology.rule_version,
                    reason="The typed exact alias resolves to a different canonical entity than the proposed merge",
                    evidence_ids=mention.evidence_ids,
                )
            decision = self._relation_to_canonical(mention, exact[0])
            return EntityResolutionDecision(
                id=decision_id,
                workspace_id=mention.workspace_id,
                domain_id=mention.domain_id,
                mention=mention,
                candidates=exact,
                selected_entity_id=exact[0].entity_id,
                decision=decision,
                rule_id="typed_exact_alias_v1",
                rule_version=self.config.ontology.rule_version,
                reason=(
                    f"Exact alias within entity type {mention.entity_type.value}; "
                    "punctuation and case are ignored"
                ),
                evidence_ids=mention.evidence_ids,
            )
        if len(exact) > 1:
            return EntityResolutionDecision(
                id=decision_id, workspace_id=mention.workspace_id, domain_id=mention.domain_id,
                mention=mention, candidates=exact, decision=ResolutionKind.UNRESOLVED,
                rule_id="ambiguous_typed_alias_v1", rule_version=self.config.ontology.rule_version,
                reason="More than one canonical entity has the same typed alias",
                evidence_ids=mention.evidence_ids,
            )

        suggestions.sort(key=lambda candidate: (-candidate.score, candidate.canonical_name))
        return EntityResolutionDecision(
            id=decision_id,
            workspace_id=mention.workspace_id,
            domain_id=mention.domain_id,
            mention=mention,
            candidates=suggestions[:5],
            decision=ResolutionKind.UNRESOLVED,
            rule_id="fuzzy_suggestion_only_v1" if suggestions else "no_typed_candidate_v1",
            rule_version=self.config.ontology.rule_version,
            reason=(
                "Similar names are suggestions only and require review"
                if suggestions else "No canonical entity of the requested type matched"
            ),
            evidence_ids=mention.evidence_ids,
        )

    def _relation_to_canonical(
        self, mention: EntityMention, candidate: EntityCandidate
    ) -> ResolutionKind:
        relation = str(mention.context.get("resolution_relation", "same_entity"))
        allowed = {
            item.value: item for item in (
                ResolutionKind.SAME_ENTITY,
                ResolutionKind.VARIANT_OF,
                ResolutionKind.COMPONENT_OF,
            )
        }
        requested = allowed.get(relation, ResolutionKind.SAME_ENTITY)
        if requested == ResolutionKind.VARIANT_OF and mention.entity_type != EntityType.MODEL_VARIANT:
            return ResolutionKind.SAME_ENTITY
        if requested == ResolutionKind.COMPONENT_OF and mention.entity_type != EntityType.COMPONENT:
            return ResolutionKind.SAME_ENTITY
        return requested
