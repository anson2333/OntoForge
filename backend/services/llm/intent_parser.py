"""Provider-backed parsing for freeform user intent."""

from __future__ import annotations

from pydantic import ValidationError

from backend.schemas.protocol import (
    ParseUserIntentParams,
    ParseUserIntentResponse,
    ParsedIntentResult,
)

from .base import LLMProvider, StructuredOutputRequest, get_default_provider


INTENT_RESULT_SCHEMA = {
    "type": "object",
    "properties": {
        "intent_type": {
            "type": "string",
            "enum": ["correction", "preference", "priority", "constraint", "goal"],
        },
        "intent_scope": {
            "type": "string",
            "enum": ["local", "pattern", "global"],
        },
        "description": {"type": "string"},
        "constraints": {"type": "object"},
        "generalization_hint": {"type": ["string", "null"]},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "requires_confirmation": {"type": "boolean"},
    },
    "required": [
        "intent_type",
        "intent_scope",
        "description",
        "constraints",
        "confidence",
        "requires_confirmation",
    ],
    "additionalProperties": False,
}


def _build_system_prompt() -> str:
    return (
        "You classify freeform OntoForge user intent for workspace actions. "
        "Return exactly one JSON object matching the requested schema. "
        "Choose intent_type from: correction, preference, priority, constraint, goal. "
        "Choose intent_scope from: local, pattern, global. "
        "Use constraints for concrete filters, entities, metrics, years, units, or thresholds. "
        "Set generalization_hint only when the message expresses a reusable preference or rule. "
        "Set requires_confirmation true when the intent could trigger data mutations or is ambiguous."
    )


def _build_user_prompt(params: ParseUserIntentParams) -> str:
    context = params.intent_context.strip() if params.intent_context else ""
    return (
        f"workspace_id: {params.workspace_id}\n"
        f"user_id: {params.user_id}\n"
        f"owner_id: {params.owner_id or 'unknown'}\n"
        f"intent_context: {context or 'none'}\n"
        f"message: {params.message.strip()}\n\n"
        "Interpret the user's message as an OntoForge intent declaration. "
        "Prefer concise descriptions. If the intent appears one-off, use scope 'local'."
    )


def _normalize_intent_payload(payload: dict, params: ParseUserIntentParams) -> dict:
    normalized = dict(payload)

    if isinstance(normalized.get("constraints"), list):
        normalized["constraints"] = {"conditions": normalized["constraints"]}
    elif normalized.get("constraints") is None:
        normalized["constraints"] = {}

    if not normalized.get("description"):
        normalized["description"] = (
            normalized.get("generalization_hint")
            or params.intent_context
            or params.message.strip()
        )

    if normalized.get("confidence") is None:
        normalized["confidence"] = 0.55 if normalized.get("requires_confirmation") else 0.8

    return normalized


async def parse_user_intent(
    params: ParseUserIntentParams,
    provider: LLMProvider | None = None,
) -> ParseUserIntentResponse:
    """Parse a freeform user message into a structured intent result."""
    llm_provider = provider or get_default_provider()
    result = await llm_provider.invoke_structured(
        StructuredOutputRequest(
            system_prompt=_build_system_prompt(),
            user_prompt=_build_user_prompt(params),
            response_schema_name="ParsedIntentResult",
            response_schema=INTENT_RESULT_SCHEMA,
            metadata={
                "workspace_id": params.workspace_id,
                "user_id": params.user_id,
                "owner_id": params.owner_id,
                "feature": "parse_user_intent",
            },
        )
    )

    try:
        parsed_intent = ParsedIntentResult.model_validate(
            _normalize_intent_payload(result.structured_output, params)
        )
    except ValidationError as exc:
        raise RuntimeError(f"LLM returned invalid parsed intent payload: {exc}") from exc

    return ParseUserIntentResponse(
        workspace_id=params.workspace_id,
        parsed_intent=parsed_intent,
    )