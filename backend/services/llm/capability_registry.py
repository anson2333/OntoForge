"""Typed capability registry for agent-safe server function surfacing."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Literal, Optional

from pydantic import BaseModel, Field

from backend.schemas.protocol import (
    ParsePdfWithDomainPackParams,
    ParsePdfWithDomainPackResponse,
    ParseUserIntentParams,
    ParseUserIntentResponse,
    ProcessChatMessageParams,
    ProcessChatMessageResponse,
)


class CapabilityDefinition(BaseModel):
    """Internal representation of an assistant-usable capability."""

    name: str
    description: str
    execution_scope: Literal["server", "local", "hybrid"]
    mutability: Literal["read", "write", "side_effect"]
    confirmation_policy: Literal["auto", "confirm", "deny"]
    input_schema: Dict[str, Any] = Field(default_factory=dict)
    output_schema: Dict[str, Any] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)


class CapabilityRegistry:
    """Small registry for typed assistant-facing capabilities."""

    def __init__(self) -> None:
        self._capabilities: Dict[str, CapabilityDefinition] = {}

    def register(self, capability: CapabilityDefinition) -> None:
        self._capabilities[capability.name] = capability

    def get(self, name: str) -> Optional[CapabilityDefinition]:
        return self._capabilities.get(name)

    def list(
        self,
        scopes: Optional[Iterable[str]] = None,
        tags: Optional[Iterable[str]] = None,
    ) -> List[CapabilityDefinition]:
        scope_set = set(scopes or [])
        tag_set = set(tags or [])
        capabilities = list(self._capabilities.values())

        if scope_set:
            capabilities = [cap for cap in capabilities if cap.execution_scope in scope_set]
        if tag_set:
            capabilities = [cap for cap in capabilities if tag_set.intersection(cap.tags)]

        return sorted(capabilities, key=lambda capability: capability.name)


def _schema(model: Optional[type[BaseModel]]) -> Dict[str, Any]:
    if model is None:
        return {}
    try:
        return model.model_json_schema()
    except Exception:
        properties: Dict[str, Any] = {}
        required: List[str] = []
        for field_name, field_info in model.model_fields.items():
            properties[field_name] = {
                "title": field_info.title or field_name,
                "annotation": str(field_info.annotation),
            }
            if field_info.is_required():
                required.append(field_name)

        return {
            "title": model.__name__,
            "type": "object",
            "properties": properties,
            "required": required,
        }


def build_server_capability_registry() -> CapabilityRegistry:
    """Build the initial backend capability registry for Phase 1."""

    registry = CapabilityRegistry()

    registry.register(
        CapabilityDefinition(
            name="listWorkspaces",
            description="List workspaces visible to the current owner context.",
            execution_scope="server",
            mutability="read",
            confirmation_policy="auto",
            input_schema={
                "type": "object",
                "properties": {
                    "owner_id": {"type": ["string", "null"]},
                    "include_archived": {"type": "boolean"},
                },
            },
            output_schema={
                "type": "object",
                "properties": {"workspaces": {"type": "array"}},
            },
            tags=["workspace", "read"],
        )
    )
    registry.register(
        CapabilityDefinition(
            name="getWorkspace",
            description="Fetch the active metadata for a single workspace.",
            execution_scope="server",
            mutability="read",
            confirmation_policy="auto",
            input_schema={
                "type": "object",
                "required": ["workspace_id"],
                "properties": {
                    "workspace_id": {"type": "string"},
                    "owner_id": {"type": ["string", "null"]},
                },
            },
            output_schema={
                "type": "object",
                "properties": {"workspace": {"type": "object"}},
            },
            tags=["workspace", "read"],
        )
    )
    registry.register(
        CapabilityDefinition(
            name="createWorkspace",
            description="Create a new workspace in the backend graph store.",
            execution_scope="server",
            mutability="write",
            confirmation_policy="confirm",
            input_schema={
                "type": "object",
                "required": ["name"],
                "properties": {
                    "name": {"type": "string"},
                    "root": {"type": ["string", "null"]},
                    "description": {"type": ["string", "null"]},
                    "owner_id": {"type": ["string", "null"]},
                    "metadata": {"type": "object"},
                },
            },
            output_schema={
                "type": "object",
                "properties": {"workspace": {"type": "object"}},
            },
            tags=["workspace", "write"],
        )
    )
    registry.register(
        CapabilityDefinition(
            name="parseUserIntent",
            description="Parse freeform user text into structured intent metadata.",
            execution_scope="server",
            mutability="read",
            confirmation_policy="auto",
            input_schema=_schema(ParseUserIntentParams),
            output_schema=_schema(ParseUserIntentResponse),
            tags=["intent", "llm", "planning"],
        )
    )
    registry.register(
        CapabilityDefinition(
            name="processChatMessage",
            description="Route a chat message into a structured assistant response and suggested actions.",
            execution_scope="server",
            mutability="read",
            confirmation_policy="auto",
            input_schema=_schema(ProcessChatMessageParams),
            output_schema=_schema(ProcessChatMessageResponse),
            tags=["chat", "llm", "planning"],
        )
    )
    registry.register(
        CapabilityDefinition(
            name="parsePdfWithDomainPack",
            description="Parse a PDF with domain-pack context before ingestion persistence.",
            execution_scope="server",
            mutability="side_effect",
            confirmation_policy="confirm",
            input_schema=_schema(ParsePdfWithDomainPackParams),
            output_schema=_schema(ParsePdfWithDomainPackResponse),
            tags=["pdf", "ingestion", "llm"],
        )
    )

    return registry