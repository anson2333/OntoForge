"""Regression cases for authorization, review fidelity and graph consistency."""
import base64
import copy
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from backend.schemas.protocol import CommitParsedPdfParams, ParsePdfWithDomainPackParams, UploadPdfParams
from backend.services import pdf_ingestion_service as pdf
from backend.services.auth_service import AuthError
from backend.services.llm.base import LLMProviderConfig, MockLLMProvider
from backend.services.llm.semantic_extractor import SemanticExtractor
from backend.tests.test_llm_foundation import _build_single_page_text_pdf


class MemoryGraph:
    """Transaction-aware repository double; real Neo4j is tested separately."""
    def __init__(self):
        self.nodes = {}
        self.edges = []
        self.db = self
        self.fail_edges = False

    @contextmanager
    def transaction(self):
        before = copy.deepcopy((self.nodes, self.edges))
        try:
            yield self
        except BaseException:
            self.nodes, self.edges = before
            raise

    def execute_query(self, query, params=None):
        return [{"id": (params or {}).get("id", "domain")}]

    def get_node_by_id(self, node_id, label):
        return self.nodes.get(node_id)

    def __getattr__(self, name):
        if name.startswith("create_") and name.endswith("_node"):
            def create(node):
                self.nodes[node.id] = node.model_dump()
                return self.nodes[node.id]
            return create
        if name.startswith("create_") and name.endswith("_edge"):
            def create(edge):
                if self.fail_edges:
                    return None
                self.edges.append(edge.model_dump())
                return {"created": True}
            return create
        raise AttributeError(name)


@pytest.fixture
def prepare(monkeypatch, tmp_path):
    monkeypatch.setenv("ONTOFORGE_UPLOAD_DIR", str(tmp_path))
    monkeypatch.setenv("ONTOFORGE_SOURCE_DIR", str(tmp_path / "sources"))
    monkeypatch.setenv("ONTOFORGE_LLM_PROVIDER", "disabled")
    monkeypatch.setattr(pdf, "get_default_provider", lambda: SimpleNamespace(is_configured=lambda: False))
    def build(workspace="workspace_a", owner="alice"):
        upload = pdf.store_pdf_upload(UploadPdfParams(
            file_name="paper.pdf", workspace_id=workspace, owner_id=owner,
            content_base64=base64.b64encode(_build_single_page_text_pdf([
                "Reconfiguration delay is 12.5 ms in this experiment."
            ])).decode(),
        ))
        preview = pdf.parse_pdf_with_domain_pack(ParsePdfWithDomainPackParams(
            workspace_id=workspace, owner_id=owner, domain_pack_namespace="optical", upload_id=upload.upload_id,
        ))
        return CommitParsedPdfParams(workspace_id=workspace, owner_id=owner,
            domain_pack_namespace="optical", upload_id=upload.upload_id, preview_id=preview.preview_id), preview
    return build


def test_commit_saves_reviewed_snapshot_without_model_call(prepare, monkeypatch):
    request, preview = prepare()
    monkeypatch.setattr(pdf, "parse_pdf_with_domain_pack", Mock(side_effect=AssertionError("must not reparse")))
    graph = MemoryGraph()
    result = pdf.commit_parsed_pdf(request, graph, graph)
    assert result.assertions_created == len(preview.assertions) > 0
    assert pdf.commit_parsed_pdf(request, graph, graph).assertions_created == 0
    assert len([n for n in graph.nodes.values() if "provenance_hash" in n]) == 1


def test_same_pdf_is_independent_in_two_workspaces(prepare):
    first, _ = prepare("workspace_a")
    second, _ = prepare("workspace_b")
    graph = MemoryGraph()
    a = pdf.commit_parsed_pdf(first, graph, graph)
    b = pdf.commit_parsed_pdf(second, graph, graph)
    assert a.paper_id != b.paper_id
    assert graph.nodes[b.paper_id]["workspace_id"] == "workspace_b"
    assert b.chunks_created > 0


@pytest.mark.parametrize("changes", [{"owner_id": "bob"}, {"workspace_id": "workspace_b"}])
def test_foreign_upload_cannot_be_committed(prepare, changes):
    request, _ = prepare()
    with pytest.raises(AuthError):
        pdf.commit_parsed_pdf(request.model_copy(update=changes), MemoryGraph(), MemoryGraph())


def test_missing_preview_cannot_trigger_extraction(prepare):
    request, _ = prepare()
    request.preview_id = "preview_" + "0" * 32
    with pytest.raises(ValueError, match="Preview expired"):
        pdf.commit_parsed_pdf(request, MemoryGraph(), MemoryGraph())


def test_graph_failure_rolls_back_all_nodes(prepare):
    request, _ = prepare()
    graph = MemoryGraph()
    graph.fail_edges = True
    with pytest.raises(ValueError, match="endpoint missing"):
        pdf.commit_parsed_pdf(request, graph, graph)
    assert graph.nodes == {} and graph.edges == []


def test_invalid_evidence_is_rejected_at_commit(prepare):
    request, _ = prepare()
    path = pdf._preview_path(request.upload_id, request.preview_id)
    import json
    data = json.loads(path.read_text(encoding="utf-8"))
    data["result"]["assertions"][0]["evidence_links"][0]["source_id"] = "missing"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="missing evidence"):
        pdf.commit_parsed_pdf(request, MemoryGraph(), MemoryGraph())


def test_domain_changes_require_new_preview(prepare, monkeypatch):
    request, _ = prepare()
    monkeypatch.setattr(pdf, "_config_hash", lambda _: "changed")
    with pytest.raises(ValueError, match="configuration changed"):
        pdf.commit_parsed_pdf(request, MemoryGraph(), MemoryGraph())


@pytest.mark.parametrize("bad_id", ["../metadata", "upload_../x", "C:\\secret"])
def test_upload_path_traversal_is_rejected(bad_id):
    with pytest.raises(ValueError, match="identifier"):
        pdf.load_pdf_upload(bad_id)


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", [
    {"source_chunk_ids": ["nonexistent"]}, {"source_chunk_ids": []},
    {"unit": "bananas"}, {"value": "nan"}, {"predicate": "invented"},
])
async def test_invalid_model_assertions_are_rejected(bad):
    class Provider(MockLLMProvider):
        async def invoke_structured(self, request):
            candidate = {"metric_name": "reconfiguration_delay", "value": "12.5", "unit": "ms",
                         "confidence": 0.9, "source_chunk_ids": ["c"]}
            return SimpleNamespace(structured_output={"assertions": [{**candidate, **bad}]}, usage={})
    from backend.schemas.protocol import ExtractedChunk
    extractor = SemanticExtractor(Provider(LLMProviderConfig(provider="mock", enabled=True)))
    result = await extractor.extract_assertions([ExtractedChunk(chunk_id="c", raw_text="text", bounding_box={})], [],
        pdf.load_domain_pack_config("optical"), "optical")
    assert result == []
    assert extractor.diagnostics["warnings"]


@pytest.mark.asyncio
async def test_failed_batch_is_visible_and_retryable(monkeypatch):
    monkeypatch.setenv("ONTOFORGE_LLM_CHUNK_BATCH_SIZE", "1")
    class Provider(MockLLMProvider):
        async def invoke_structured(self, request):
            if request.metadata["batch_index"] == 1:
                raise TimeoutError("simulated model timeout")
            return SimpleNamespace(structured_output={"assertions": []}, usage={"input_tokens": 10})
    from backend.schemas.protocol import ExtractedChunk
    extractor = SemanticExtractor(Provider(LLMProviderConfig(provider="mock", enabled=True)))
    await extractor.extract_assertions([ExtractedChunk(chunk_id=str(i), raw_text="text", bounding_box={}) for i in range(2)], [],
        pdf.load_domain_pack_config("optical"), "optical")
    assert extractor.diagnostics["failed_batches"] == [1]
    assert extractor.diagnostics["retryable"]
    assert extractor.diagnostics["usage"] == [{"input_tokens": 10}]


def test_neo4j_transaction_rolls_back_and_restores_context():
    from backend.database.connection import Neo4jConnection
    connection = Neo4jConnection("bolt://unused", "neo4j", "unused")
    tx = Mock()
    tx.run.return_value = []
    session = Mock()
    session.begin_transaction.return_value = tx
    connection._driver = Mock()
    connection._driver.session.return_value = session
    with pytest.raises(RuntimeError, match="injected"):
        with connection.transaction():
            connection.execute_query("CREATE (n)")
            raise RuntimeError("injected failure")
    tx.rollback.assert_called_once()
    tx.commit.assert_not_called()
    assert connection._transaction.get() is None


def test_long_single_chunk_is_fully_batched(monkeypatch):
    from backend.schemas.protocol import ExtractedChunk
    monkeypatch.setenv("ONTOFORGE_LLM_BATCH_CHARACTERS", "1000")
    extractor = SemanticExtractor()
    source = "abcdef" * 700
    batches = extractor._chunk_batches([ExtractedChunk(chunk_id="long", raw_text=source, bounding_box={})])
    assert "".join(c.raw_text for batch in batches for c in batch) == source
    assert all(sum(len(c.raw_text) for c in batch) <= 1000 for batch in batches)
