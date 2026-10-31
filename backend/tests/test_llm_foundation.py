"""Tests for the Phase 1 LLM foundation layer."""

import json
from pathlib import Path
from typing import Any, Optional

import pytest
from pypdf import PdfWriter

from backend.schemas.protocol import (
    CommitParsedPdfParams,
    ParsePdfWithDomainPackParams,
    ParseUserIntentParams,
    ProcessChatMessageParams,
)
from backend.services.pdf_ingestion_service import (
    ExtractorArtifacts,
    MarkerPdfExtractor,
    ParseSource,
    commit_parsed_pdf,
    get_pdf_extractor,
    parse_pdf_with_domain_pack,
)
from backend.services.llm import (
    LLMProviderConfig,
    LLMProvider,
    MockLLMProvider,
    OpenAICompatibleProvider,
    OllamaProvider,
    StructuredOutputRequest,
    build_server_capability_registry,
    get_default_provider,
    parse_user_intent,
)


def _pdf_literal(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _build_single_page_text_pdf(lines: list[str], metadata: Optional[dict[str, str]] = None) -> bytes:
    content_lines = ["BT", "/F1 12 Tf", "72 720 Td"]
    for index, line in enumerate(lines):
        if index > 0:
            content_lines.append("0 -18 Td")
        content_lines.append(f"({_pdf_literal(line)}) Tj")
    content_lines.append("ET")
    stream = "\n".join(content_lines).encode("utf-8")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(stream)} >>\nstream\n".encode("utf-8") + stream + b"\nendstream",
    ]

    info_object_number: Optional[int] = None
    if metadata:
        metadata_pairs = " ".join(
            f"/{key} ({_pdf_literal(value)})" for key, value in metadata.items() if value
        )
        if metadata_pairs:
            info_object_number = len(objects) + 1
            objects.append(f"<< {metadata_pairs} >>".encode("utf-8"))

    header = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    body = bytearray(header)
    offsets = [0]

    for object_number, payload in enumerate(objects, start=1):
        offsets.append(len(body))
        body.extend(f"{object_number} 0 obj\n".encode("utf-8"))
        body.extend(payload)
        body.extend(b"\nendobj\n")

    xref_offset = len(body)
    body.extend(f"xref\n0 {len(objects) + 1}\n".encode("utf-8"))
    body.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        body.extend(f"{offset:010d} 00000 n \n".encode("utf-8"))

    trailer = f"<< /Size {len(objects) + 1} /Root 1 0 R"
    if info_object_number is not None:
        trailer += f" /Info {info_object_number} 0 R"
    trailer += " >>"
    body.extend(f"trailer\n{trailer}\nstartxref\n{xref_offset}\n%%EOF\n".encode("utf-8"))
    return bytes(body)


def _snapshot_parse_response(response) -> dict[str, Any]:
    return {
        "status": response.status,
        "paper_metadata": (
            None
            if response.paper_metadata is None
            else {
                "title": response.paper_metadata.title,
                "authors": response.paper_metadata.authors,
                "year": response.paper_metadata.year,
                "venue": response.paper_metadata.venue,
            }
        ),
        "markdown_text": response.markdown_text,
        "chunks": [chunk.raw_text for chunk in response.chunks],
        "formulas": [
            {
                "formula_id": formula.formula_id,
                "latex_string": formula.latex_string,
            }
            for formula in response.formulas
        ],
        "assertions": [
            {
                "subject": assertion.subject,
                "predicate": assertion.predicate,
                "object": assertion.object,
                "unit": assertion.unit,
                "evidence_sources": [link.source_id for link in assertion.evidence_links],
            }
            for assertion in response.assertions
        ],
        "warnings": response.warnings,
    }


def _load_pdf_parse_snapshot(snapshot_name: str) -> dict[str, Any]:
    snapshot_path = Path(__file__).parent / "fixtures" / snapshot_name
    return json.loads(snapshot_path.read_text(encoding="utf-8"))


class TestLLMProtocolSchemas:
    """Validate Phase 1 protocol contracts."""

    def test_parse_pdf_with_domain_pack_params(self):
        params = ParsePdfWithDomainPackParams(
            workspace_id="workspace_test",
            domain_pack_namespace="optical",
            paper_uri="file:///tmp/test.pdf",
        )
        assert params.workspace_id == "workspace_test"
        assert params.domain_pack_namespace == "optical"
        assert params.parse_options.auto_classify is True

    def test_commit_parsed_pdf_params(self):
        params = CommitParsedPdfParams(
            workspace_id="workspace_test",
            domain_pack_namespace="optical",
            upload_id="upload_123",
            preview_id="preview_test",
        )
        assert params.upload_id == "upload_123"
        assert params.parse_options.auto_classify is True

    def test_parse_user_intent_params(self):
        params = ParseUserIntentParams(
            workspace_id="workspace_test",
            user_id="local-dev-user",
            message="Prefer ASIC baselines for reconfiguration delay",
        )
        assert params.user_id == "local-dev-user"
        assert "ASIC" in params.message

    def test_process_chat_message_params(self):
        params = ProcessChatMessageParams(
            workspace_id="workspace_test",
            message="Show me WDM papers after 2020",
            active_domain_packs=["optical"],
        )
        assert params.active_domain_packs == ["optical"]


class TestLLMProviderFoundation:
    """Validate the default provider abstraction behavior."""

    def test_default_provider_status_is_safe(self, monkeypatch):
        for key in [
            "ONTOFORGE_LLM_PROVIDER",
            "ONTOFORGE_LLM_MODEL",
            "ONTOFORGE_LLM_API_BASE_URL",
            "ONTOFORGE_LLM_API_KEY_ENV",
            "ONTOFORGE_LLM_API_KEY",
            "ONTOFORGE_LLM_TEMPERATURE",
            "ONTOFORGE_LLM_TIMEOUT_SECONDS",
            "ONTOFORGE_LLM_MAX_OUTPUT_TOKENS",
            "ONTOFORGE_LLM_ENABLED",
        ]:
            monkeypatch.delenv(key, raising=False)

        provider = get_default_provider()
        status = provider.get_status()
        assert status.provider == provider.name
        assert status.healthy is False
        assert status.enabled is False

    @pytest.mark.asyncio
    async def test_mock_provider_returns_deterministic_structured_output(self):
        provider = MockLLMProvider(
            LLMProviderConfig(provider="mock", enabled=True, model="mock-model")
        )
        result = await provider.invoke_structured(
            StructuredOutputRequest(
                system_prompt="You are a test system.",
                user_prompt="Echo this",
                response_schema_name="EchoResponse",
                metadata={"workspace_id": "workspace_test"},
            )
        )
        assert result.provider == "mock"
        assert result.structured_output["echo"] == "Echo this"

    def test_openai_compatible_health_check(self, monkeypatch):
        provider = OpenAICompatibleProvider(
            LLMProviderConfig(
                provider="openai_compatible",
                enabled=True,
                model="gpt-test",
                api_base_url="https://example.test/v1",
                api_key_env_var="TEST_LLM_API_KEY",
            )
        )
        monkeypatch.setenv("TEST_LLM_API_KEY", "secret")

        class FakeResponse:
            def raise_for_status(self):
                return None

        class FakeClient:
            def __init__(self, *args, **kwargs):
                pass

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def get(self, url, headers=None):
                assert url == "https://example.test/v1/models"
                assert headers["Authorization"] == "Bearer secret"
                return FakeResponse()

        monkeypatch.setattr("backend.services.llm.base.httpx.Client", FakeClient)

        status = provider.get_status()
        assert status.healthy is True
        assert "reachable" in status.message

    @pytest.mark.asyncio
    async def test_ollama_invoke_structured(self, monkeypatch):
        provider = OllamaProvider(
            LLMProviderConfig(
                provider="ollama",
                enabled=True,
                model="llama3",
                api_base_url="http://ollama.test",
            )
        )

        class FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "model": "llama3",
                    "message": {"content": json.dumps({"intent": "query"})},
                    "done_reason": "stop",
                    "prompt_eval_count": 10,
                    "eval_count": 5,
                }

        class FakeAsyncClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def post(self, url, json=None):
                assert url == "http://ollama.test/api/chat"
                assert json["model"] == "llama3"
                return FakeResponse()

        monkeypatch.setattr("backend.services.llm.base.httpx.AsyncClient", FakeAsyncClient)

        result = await provider.invoke_structured(
            StructuredOutputRequest(
                system_prompt="You are a classifier.",
                user_prompt="Classify this intent",
                response_schema_name="IntentResult",
            )
        )
        assert result.provider == "ollama"
        assert result.structured_output["intent"] == "query"


class TestPdfIngestionServices:
    def test_parse_pdf_with_domain_pack_matches_text_fixture_snapshot(self, tmp_path):
        pdf_path = tmp_path / "optical_preview.pdf"
        pdf_path.write_bytes(
            _build_single_page_text_pdf(
                lines=[
                    "Optical Systems 2025",
                    "Figure 1. Topology overview",
                    "The reconfiguration delay is 12.5 ms.",
                    "E = mc^2",
                ],
                metadata={
                    "Title": "Optical Systems 2025",
                    "Author": "Alice; Bob",
                    "Subject": "Photonics 2025",
                },
            )
        )

        response = parse_pdf_with_domain_pack(
            ParsePdfWithDomainPackParams(
                workspace_id="workspace_test",
                domain_pack_namespace="optical",
                paper_uri=str(pdf_path),
            )
        )

        assert _snapshot_parse_response(response) == _load_pdf_parse_snapshot(
            "parse_pdf_text_fixture_snapshot.json"
        )

    def test_parse_pdf_with_domain_pack_matches_blank_fixture_snapshot(self, tmp_path):
        pdf_path = tmp_path / "scanned_pages_only.pdf"
        writer = PdfWriter()
        writer.add_blank_page(width=300, height=300)
        writer.add_metadata(
            {
                "/Title": "Scanned Pages Only",
                "/Author": "Camera Capture",
                "/Subject": "Poster Session 2026",
            }
        )
        with pdf_path.open("wb") as output_file:
            writer.write(output_file)

        response = parse_pdf_with_domain_pack(
            ParsePdfWithDomainPackParams(
                workspace_id="workspace_test",
                domain_pack_namespace="optical",
                paper_uri=str(pdf_path),
            )
        )

        assert _snapshot_parse_response(response) == _load_pdf_parse_snapshot(
            "parse_pdf_blank_fixture_snapshot.json"
        )

    def test_parse_pdf_with_domain_pack_extracts_grounded_assertions_from_raw_text(self):
        response = parse_pdf_with_domain_pack(
            ParsePdfWithDomainPackParams(
                workspace_id="workspace_test",
                domain_pack_namespace="optical",
                raw_text="The reconfiguration delay is 12.5 ms under the experimental setup.",
            )
        )

        assert response.status in {"parsed", "needs_review"}
        assert response.paper_metadata is not None
        assert response.markdown_text
        assert any(assertion.subject == "optical:reconfiguration_delay" for assertion in response.assertions)

    def test_parse_pdf_with_domain_pack_avoids_false_positive_assertions_from_noisy_ocr_text(self):
        noisy_text = (
            "The objective function of minimizing the power consumption is discussed in Section 1 INTRODUCTION. "
            "We repeat an experiment 11 times and show error bars of 95% confidence intervals. "
            "Algorithm 1 builds the auxiliary graph and Figure 2 illustrates the design."
        )

        response = parse_pdf_with_domain_pack(
            ParsePdfWithDomainPackParams(
                workspace_id="workspace_test",
                domain_pack_namespace="optical",
                raw_text=noisy_text,
            )
        )

        assert response.assertions == []

    def test_parse_pdf_with_domain_pack_uses_configured_extractor_boundary(self, monkeypatch, tmp_path):
        class FakeExtractor:
            name = "fake_extractor"

            def extract(self, source, request):
                assert source.file_name == "boundary_test.pdf"
                assert request.domain_pack_namespace == "optical"
                return ExtractorArtifacts(
                    page_texts=["Synthetic extractor output"],
                    chunks=[],
                    formulas=[],
                    warnings=["Synthetic extractor warning."],
                    extraction_method="fake_extractor",
                    reader=None,
                )

        pdf_path = tmp_path / "boundary_test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 fake content")
        monkeypatch.setattr(
            "backend.services.pdf_ingestion_service.get_pdf_extractor",
            lambda: FakeExtractor(),
        )

        response = parse_pdf_with_domain_pack(
            ParsePdfWithDomainPackParams(
                workspace_id="workspace_test",
                domain_pack_namespace="optical",
                paper_uri=str(pdf_path),
            )
        )

        assert response.status == "needs_review"
        assert response.markdown_text == "## Page 1\n\nSynthetic extractor output"
        assert response.warnings[0] == "Synthetic extractor warning."
        assert response.warnings[-1] == "No domain-grounded assertions were extracted from the parsed chunks."

    def test_get_pdf_extractor_selects_marker_backend(self, monkeypatch):
        monkeypatch.setenv("ONTOFORGE_PDF_EXTRACTOR", "marker")
        extractor = get_pdf_extractor()
        assert isinstance(extractor, MarkerPdfExtractor)

    def test_marker_pdf_extractor_maps_marker_outputs(self, monkeypatch, tmp_path):
        extractor = MarkerPdfExtractor()
        source = ParseSource(
            raw_bytes=b"%PDF-1.4 fake content",
            file_name="marker_input.pdf",
            source_kind="paper_uri",
        )

        def fake_run_marker(pdf_path, output_dir, output_format, request):
            assert pdf_path.name == "marker_input.pdf"
            if output_format == "markdown":
                (output_dir / "marker_input.md").write_text(
                    "## Page 1\n\nMarker paragraph\n\n$$E=mc^2$$\n",
                    encoding="utf-8",
                )
            else:
                (output_dir / "marker_input.json").write_text(
                    json.dumps(
                        [
                            {
                                "id": "/page/1/Page/0",
                                "block_type": "Page",
                                "children": [
                                    {
                                        "id": "/page/1/Text/0",
                                        "block_type": "Text",
                                        "html": "<p>Marker paragraph</p>",
                                        "polygon": [[0, 0], [100, 0], [100, 20], [0, 20]],
                                        "children": None,
                                    },
                                    {
                                        "id": "/page/1/Equation/1",
                                        "block_type": "Equation",
                                        "html": "<math>E=mc^2</math>",
                                        "polygon": [[0, 30], [120, 30], [120, 60], [0, 60]],
                                        "children": None,
                                    },
                                ],
                            }
                        ]
                    ),
                    encoding="utf-8",
                )

        monkeypatch.setattr(extractor, "_run_marker", fake_run_marker)

        artifacts = extractor.extract(
            source,
            ParsePdfWithDomainPackParams(
                workspace_id="workspace_test",
                domain_pack_namespace="optical",
                paper_uri=str(tmp_path / "marker_input.pdf"),
            ),
        )

        assert artifacts.extraction_method == "marker"
        assert artifacts.page_texts == ["Marker paragraph"]
        assert [chunk.raw_text for chunk in artifacts.chunks] == ["Marker paragraph"]
        assert [formula.latex_string for formula in artifacts.formulas] == ["E=mc^2"]

    def test_commit_parsed_pdf_persists_parsed_artifacts(self):
        class FakeNodeRepo:
            def __init__(self):
                from contextlib import nullcontext
                from unittest.mock import Mock
                self.db = Mock()
                self.db.transaction.side_effect = nullcontext
                self.db.execute_query.return_value = [{"id": "workspace_test"}]
                self.papers = []
                self.chunks = []
                self.formulas = []
                self.assertions = []

            def get_node_by_id(self, node_id, node_label):
                return None

            def create_paper_node(self, node):
                self.papers.append(node)
                return node.model_dump()

            def create_chunk_node(self, node):
                self.chunks.append(node)
                return node.model_dump()

            def create_formula_node(self, node):
                self.formulas.append(node)
                return node.model_dump()

            def create_assertion_node(self, node):
                self.assertions.append(node)
                return node.model_dump()

        class FakeEdgeRepo:
            def __init__(self):
                self.contains_papers = []
                self.belongs_to = []
                self.contains = []
                self.evidenced_by = []

            def create_contains_paper_edge(self, edge):
                self.contains_papers.append(edge)
                return edge.model_dump()

            def create_belongs_to_edge(self, edge):
                self.belongs_to.append(edge)
                return edge.model_dump()

            def create_contains_edge(self, edge):
                self.contains.append(edge)
                return edge.model_dump()

            def create_evidenced_by_edge(self, edge):
                self.evidenced_by.append(edge)
                return edge.model_dump()

        from types import SimpleNamespace
        from unittest.mock import patch

        fake_upload = SimpleNamespace(
            upload_id="upload_test",
            file_name="demo.pdf",
            stored_path=None,
            expires_at=None,
        )

        parse_result = parse_pdf_with_domain_pack(
            ParsePdfWithDomainPackParams(
                workspace_id="workspace_test",
                domain_pack_namespace="optical",
                raw_text="Reconfiguration delay reaches 12.5 ms in this optical topology.",
            )
        )

        node_repo = FakeNodeRepo()
        edge_repo = FakeEdgeRepo()

        with patch("backend.services.pdf_ingestion_service.load_preview", return_value=parse_result), patch("backend.services.pdf_ingestion_service.preserve_pdf_source"):
            # This repository contract test isolates filesystem storage; real storage has separate regressions.
            response = commit_parsed_pdf(
                CommitParsedPdfParams(
                    workspace_id="workspace_test",
                    domain_pack_namespace="optical",
                    upload_id="upload_test",
                    preview_id="preview_test",
                ),
                node_repo=node_repo,
                edge_repo=edge_repo,
                workspace_exists=True,
            )

        assert response.status == "committed"
        assert response.paper_id.startswith("paper_")
        assert response.chunks_created == len(node_repo.chunks)
        assert response.assertions_created == len(node_repo.assertions)
        assert len(edge_repo.contains_papers) == 1
        assert len(edge_repo.contains) >= len(node_repo.chunks) + len(node_repo.assertions)


class TestCapabilityRegistry:
    """Validate capability discovery for agent-safe server actions."""

    def test_server_capability_registry_contains_phase1_entries(self):
        registry = build_server_capability_registry()
        parse_intent = registry.get("parseUserIntent")
        chat = registry.get("processChatMessage")
        assert parse_intent is not None
        assert chat is not None
        assert parse_intent.execution_scope == "server"
        assert chat.mutability == "read"

    def test_capability_registry_filtering(self):
        registry = build_server_capability_registry()
        llm_capabilities = registry.list(tags=["llm"])
        names = {capability.name for capability in llm_capabilities}
        assert "parseUserIntent" in names
        assert "processChatMessage" in names


class TestIntentParser:
    """Validate provider-backed freeform intent parsing."""

    @pytest.mark.asyncio
    async def test_parse_user_intent_uses_provider_output(self):
        class FakeIntentProvider(LLMProvider):
            async def invoke_structured(self, request: StructuredOutputRequest):
                assert request.response_schema_name == "ParsedIntentResult"
                return type("Result", (), {
                    "structured_output": {
                        "intent_type": "preference",
                        "intent_scope": "pattern",
                        "description": "Prefer ASIC baselines for delay comparisons",
                        "constraints": {"metric": "reconfiguration_delay"},
                        "generalization_hint": "Prefer ASIC baselines when comparing delay papers",
                        "confidence": 0.91,
                        "requires_confirmation": False,
                    }
                })()

        response = await parse_user_intent(
            ParseUserIntentParams(
                workspace_id="workspace_test",
                user_id="local-dev-user",
                message="Prefer ASIC baselines for reconfiguration delay comparisons.",
            ),
            provider=FakeIntentProvider(
                LLMProviderConfig(provider="mock", enabled=True, model="fake")
            ),
        )

        assert response.workspace_id == "workspace_test"
        assert response.parsed_intent.intent_type == "preference"
        assert response.parsed_intent.intent_scope == "pattern"

    @pytest.mark.asyncio
    async def test_parse_user_intent_normalizes_common_provider_drift(self):
        class DriftedIntentProvider(LLMProvider):
            async def invoke_structured(self, request: StructuredOutputRequest):
                return type("Result", (), {
                    "structured_output": {
                        "intent_type": "constraint",
                        "intent_scope": "local",
                        "constraints": [{"field": "year", "operator": ">=", "value": 2020}],
                        "generalization_hint": "Limit papers to recent studies",
                        "requires_confirmation": False,
                    }
                })()

        response = await parse_user_intent(
            ParseUserIntentParams(
                workspace_id="workspace_test",
                user_id="local-dev-user",
                message="Only show papers after 2020.",
            ),
            provider=DriftedIntentProvider(
                LLMProviderConfig(provider="mock", enabled=True, model="fake")
            ),
        )

        assert response.parsed_intent.description == "Limit papers to recent studies"
        assert response.parsed_intent.constraints == {
            "conditions": [{"field": "year", "operator": ">=", "value": 2020}]
        }
        assert response.parsed_intent.confidence == 0.8