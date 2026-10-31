"""Model format compatibility must not bypass scientific validation."""
import json

import httpx
import pytest

from backend.services.llm.output_adapter import adapt_assertions
from backend.services.llm.base import LLMProviderConfig, StructuredOutputRequest, provider_from_config, StructuredOutputResult, MockLLMProvider
from backend.services.llm.semantic_extractor import SemanticExtractor
from backend.tests.test_semantic_extractor import sample_domain_pack_config, sample_chunks


ROW = {"metric_name": "reconfiguration_delay", "value": "12.5", "unit": "ms", "source_chunk_ids": ["chunk_0"]}


@pytest.mark.parametrize("text", [
    json.dumps({"assertions": [ROW]}),
    "Here are the results:\n```json\n" + json.dumps([ROW]) + "\n```\nPlease review.",
    "| 指标 | 数值 | 单位 | 来源 | 条件 |\n|---|---|---|---|---|\n| reconfiguration_delay | 12.5 | ms | chunk_0 | high load |",
    "metric_name: reconfiguration_delay\nvalue: 12.5\nunit: ms\nsource_chunk_ids: chunk_0",
    "The reconfiguration delay is 12.5 ms under high load (source: chunk_0).",
    "指标: reconfiguration_delay\n数值: 12.5\n单位: ms\n原文引用: The reconfiguration delay is 12.5 ms under high network load.",
])
@pytest.mark.asyncio
async def test_formats_produce_evidence_backed_assertion(text, sample_domain_pack_config, sample_chunks):
    class Provider(MockLLMProvider):
        async def invoke_structured(self, request):
            assert request.metadata["flexible_output"]
            return StructuredOutputResult(provider="mock", raw_text=text)
    extractor = SemanticExtractor(Provider(LLMProviderConfig(provider="mock", enabled=True)))
    result = await extractor.extract_assertions(sample_chunks, [], sample_domain_pack_config, "optical")
    assert len(result) == 1 and result[0].object == "12.5"
    assert result[0].evidence_links[0].source_id == "chunk_0"


@pytest.mark.parametrize("text", [
    "metric_name: reconfiguration_delay\nvalue: 999\nunit: ms\nsource_chunk_ids: chunk_0",
    "metric_name: reconfiguration_delay\nvalue: 12.5\nunit: ms",
    "metric_name: reconfiguration_delay\nvalue: 12.5\nunit: seconds\nsource_chunk_ids: chunk_0",
    "metric_name: reconfiguration_delay\nvalue: 12.5\nunit: ms\nsource_chunk_ids: invented",
])
@pytest.mark.asyncio
async def test_text_cannot_bypass_evidence_or_units(text, sample_domain_pack_config, sample_chunks):
    class Provider(MockLLMProvider):
        async def invoke_structured(self, request):
            return StructuredOutputResult(provider="mock", raw_text=text)
    extractor = SemanticExtractor(Provider(LLMProviderConfig(provider="mock", enabled=True)))
    assert not await extractor.extract_assertions(sample_chunks, [], sample_domain_pack_config, "optical")
    assert extractor.diagnostics["warnings"]


@pytest.mark.asyncio
async def test_malformed_row_does_not_discard_good_rows(sample_domain_pack_config, sample_chunks):
    class Provider(MockLLMProvider):
        async def invoke_structured(self, request):
            return StructuredOutputResult(provider="mock", structured_output={"assertions": [ROW, {"metric_name": "bad"}, {**ROW, "source_chunk_ids": ["invented"]}]})
    extractor = SemanticExtractor(Provider(LLMProviderConfig(provider="mock", enabled=True)))
    result = await extractor.extract_assertions(sample_chunks, [], sample_domain_pack_config, "optical")
    assert len(result) == 1
    assert len(extractor.diagnostics["warnings"]) == 2


def test_ambiguous_prose_is_not_fabricated_into_data():
    with pytest.raises(ValueError, match="未识别"):
        adapt_assertions({}, "The method looks promising and could improve performance.")
    assert adapt_assertions({}, '{"assertions": []}')[0] == []


@pytest.mark.parametrize("protocol", ["openai_compatible", "anthropic", "ollama"])
@pytest.mark.asyncio
async def test_paper_request_does_not_require_server_json_mode(monkeypatch, protocol):
    original = httpx.AsyncClient
    text = "metric_name: reconfiguration_delay\nvalue: 12.5\nunit: ms\nsource_chunk_ids: chunk_0"
    def respond(request):
        payload = json.loads(request.content)
        assert "response_format" not in payload and "format" not in payload
        assert "matching this schema" not in payload.get("system", "")
        if protocol == "anthropic":
            body = {"content": [{"type": "text", "text": text}], "stop_reason": "end_turn"}
        elif protocol == "ollama":
            body = {"message": {"content": text}}
        else:
            body = {"choices": [{"message": {"content": text}, "finish_reason": "stop"}]}
        return httpx.Response(200, json=body)
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: original(transport=httpx.MockTransport(respond), **kw))
    monkeypatch.setenv("FIXTURE_KEY", "fixture")
    provider = provider_from_config(LLMProviderConfig(provider=protocol, enabled=True, model="fixture", api_base_url="http://fixture.invalid", api_key_env_var="FIXTURE_KEY"))
    result = await provider.invoke_structured(StructuredOutputRequest(system_prompt="Extract assertions", user_prompt="Evidence", response_schema_name="AssertionExtractionResult", metadata={"flexible_output": True}))
    assert result.raw_text == text and result.structured_output == {}
