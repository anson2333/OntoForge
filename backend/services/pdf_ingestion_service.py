"""PDF upload and parsing helpers for backend-managed preview ingestion."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from typing import Any, Optional, Protocol
from uuid import uuid4

from pypdf import PdfReader
from neo4j.exceptions import TransientError

from backend.schemas.protocol import (
    CommitParsedPdfParams,
    CommitParsedPdfResponse,
    EvidenceLink,
    ExtractedChunk,
    ExtractedAssertion,
    ExtractedFormula,
    PaperMetadata,
    ParsePdfWithDomainPackParams,
    ParsePdfWithDomainPackResponse,
    UploadPdfParams,
    UploadPdfResponse,
)
from backend.schemas.domain_pack import DomainPackConfig
from backend.schemas.edges import BelongsToEdge, ContainsEdge, ContainsPaperEdge, EvidencedByEdge
from backend.schemas.nodes import AssertionNode, ChunkNode, FormulaNode, PaperNode
from backend.database.ontology_repository import OntologyRepository
from backend.services.llm import get_default_provider
from backend.services.llm.semantic_extractor import create_semantic_extractor
from backend.services.ontology_projection import persist_preview_projection


UPLOAD_RETENTION_HOURS = int(os.getenv("ONTOFORGE_UPLOAD_RETENTION_HOURS", "24"))
MAX_UPLOAD_BYTES = int(os.getenv("ONTOFORGE_MAX_UPLOAD_BYTES", str(25 * 1024 * 1024)))


@dataclass
class StoredUpload:
    upload_id: str
    file_name: str
    content_type: Optional[str]
    size_bytes: int
    sha256: str
    stored_path: Path
    created_at: datetime
    expires_at: datetime
    workspace_id: Optional[str] = None
    owner_id: Optional[str] = None


@dataclass
class ParseSource:
    raw_bytes: bytes
    file_name: str
    upload: Optional[StoredUpload] = None
    warnings: list[str] = field(default_factory=list)
    source_kind: str = "pdf"


@dataclass
class ExtractorArtifacts:
    page_texts: list[str]
    chunks: list[ExtractedChunk]
    formulas: list[ExtractedFormula] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    extraction_method: str = "pypdf"
    reader: Optional[PdfReader] = None


class PdfExtractor(Protocol):
    name: str

    def extract(self, source: ParseSource, request: ParsePdfWithDomainPackParams) -> ExtractorArtifacts:
        ...


MARKER_SUPPORTED_TEXT_BLOCKS = {
    "Text",
    "SectionHeader",
    "TextInlineMath",
    "ListItem",
    "Caption",
    "Code",
    "Footnote",
}

MARKER_FORMULA_BLOCKS = {"Equation", "TextInlineMath"}


def _upload_root() -> Path:
    configured = os.getenv("ONTOFORGE_UPLOAD_DIR")
    if configured:
        root = Path(configured)
    else:
        root = Path(tempfile.gettempdir()) / "ontoforge_uploads"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _metadata_path(upload_id: str) -> Path:
    if not re.fullmatch(r"upload_[a-f0-9]{32}", upload_id):
        raise ValueError("Invalid upload identifier")
    return _upload_root() / upload_id / "metadata.json"


def _pdf_path(upload_id: str, file_name: str) -> Path:
    safe_name = Path(file_name).name or "upload.pdf"
    return _upload_root() / upload_id / safe_name


def _serialize_upload(upload: StoredUpload) -> dict[str, Any]:
    return {
        "upload_id": upload.upload_id,
        "file_name": upload.file_name,
        "content_type": upload.content_type,
        "size_bytes": upload.size_bytes,
        "sha256": upload.sha256,
        "stored_path": str(upload.stored_path),
        "created_at": upload.created_at.isoformat(),
        "expires_at": upload.expires_at.isoformat(),
        "workspace_id": upload.workspace_id,
        "owner_id": upload.owner_id,
    }


def _deserialize_upload(data: dict[str, Any]) -> StoredUpload:
    return StoredUpload(
        upload_id=data["upload_id"],
        file_name=data["file_name"],
        content_type=data.get("content_type"),
        size_bytes=int(data["size_bytes"]),
        sha256=data["sha256"],
        stored_path=Path(data["stored_path"]),
        created_at=datetime.fromisoformat(data["created_at"]),
        expires_at=datetime.fromisoformat(data["expires_at"]),
        workspace_id=data.get("workspace_id"),
        owner_id=data.get("owner_id"),
    )


def store_pdf_upload(request: UploadPdfParams) -> UploadPdfResponse:
    try:
        raw_bytes = base64.b64decode(request.content_base64, validate=True)
    except Exception as exc:  # pragma: no cover - exact decoder errors vary
        raise ValueError("Invalid base64 PDF upload payload") from exc

    if not raw_bytes:
        raise ValueError("Uploaded PDF payload is empty")
    if len(raw_bytes) > MAX_UPLOAD_BYTES:
        raise ValueError(f"Uploaded PDF exceeds the {MAX_UPLOAD_BYTES}-byte limit")
    if not raw_bytes.startswith(b"%PDF-"):
        raise ValueError("Uploaded content is not a PDF file")

    upload_id = f"upload_{uuid4().hex}"
    created_at = datetime.now(timezone.utc)
    expires_at = created_at + timedelta(hours=UPLOAD_RETENTION_HOURS)
    upload_dir = _upload_root() / upload_id
    upload_dir.mkdir(parents=True, exist_ok=True)

    stored_path = _pdf_path(upload_id, request.file_name)
    stored_path.write_bytes(raw_bytes)

    sha256 = hashlib.sha256(raw_bytes).hexdigest()
    upload = StoredUpload(
        upload_id=upload_id,
        file_name=Path(request.file_name).name,
        content_type=request.content_type,
        size_bytes=len(raw_bytes),
        sha256=sha256,
        stored_path=stored_path,
        created_at=created_at,
        expires_at=expires_at,
        workspace_id=request.workspace_id,
        owner_id=request.owner_id,
    )
    _metadata_path(upload_id).write_text(json.dumps(_serialize_upload(upload), indent=2), encoding="utf-8")

    return UploadPdfResponse(
        upload_id=upload.upload_id,
        file_name=upload.file_name,
        content_type=upload.content_type,
        size_bytes=upload.size_bytes,
        sha256=upload.sha256,
        expires_at=upload.expires_at.isoformat(),
    )


def load_pdf_upload(upload_id: str) -> StoredUpload:
    metadata_file = _metadata_path(upload_id)
    if not metadata_file.exists():
        raise FileNotFoundError(f"Upload {upload_id} was not found")

    data = json.loads(metadata_file.read_text(encoding="utf-8"))
    upload = _deserialize_upload(data)

    if upload.expires_at < datetime.now(timezone.utc):
        raise FileNotFoundError(f"Upload {upload_id} has expired")
    if not upload.stored_path.exists():
        raise FileNotFoundError(f"Uploaded PDF for {upload_id} is missing")
    return upload


def authorize_pdf_upload(upload_id: str, workspace_id: str, user_id: Optional[str]) -> StoredUpload:
    """Check upload ownership at every entry point, including graph commit."""
    from backend.services.auth_service import AuthError, CODE_FORBIDDEN
    upload = load_pdf_upload(upload_id)
    if upload.owner_id != user_id or upload.workspace_id != workspace_id:
        raise AuthError(CODE_FORBIDDEN, "Upload belongs to another user or workspace")
    return upload


def _config_hash(namespace: str) -> str:
    config = load_domain_pack_config(namespace)
    return hashlib.sha256((config.model_dump_json() if config else "null").encode()).hexdigest()


def paper_source_path(paper_id: str) -> Path:
    if not re.fullmatch(r"paper_[a-f0-9]{64}", paper_id):
        raise ValueError("Original PDF unavailable for this legacy or demo paper")
    root = Path(os.getenv("ONTOFORGE_SOURCE_DIR", str(Path(__file__).resolve().parents[1] / "data/sources")))
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{paper_id}.pdf"


def _preview_path(upload_id: str, preview_id: str) -> Path:
    if not re.fullmatch(r"preview_[a-f0-9]{32}", preview_id):
        raise ValueError("Invalid preview identifier")
    return _metadata_path(upload_id).parent / f"{preview_id}.json"


def load_preview(request: CommitParsedPdfParams) -> ParsePdfWithDomainPackResponse:
    upload = authorize_pdf_upload(request.upload_id, request.workspace_id, request.owner_id)
    path = _preview_path(request.upload_id, request.preview_id)
    if not path.exists():
        raise ValueError("Preview expired or missing; preview the PDF again before committing")
    data = json.loads(path.read_text(encoding="utf-8"))
    if (data["sha256"] != upload.sha256 or data["config_hash"] != _config_hash(request.domain_pack_namespace)):
        raise ValueError("Source or domain configuration changed; preview again")
    result = ParsePdfWithDomainPackResponse.model_validate(data["result"])
    if (result.workspace_id != request.workspace_id or result.domain_pack_namespace != request.domain_pack_namespace
            or result.upload_id != request.upload_id or result.preview_id != request.preview_id):
        raise ValueError("Preview does not belong to this import")
    if result.status != "parsed" or not result.chunks:
        raise ValueError("Preview needs review; resolve extraction failures and preview again")
    valid_ids = {chunk.chunk_id for chunk in result.chunks} | {formula.formula_id for formula in result.formulas}
    for assertion in result.assertions:
        if not assertion.evidence_links or any(link.source_id not in valid_ids for link in assertion.evidence_links):
            raise ValueError("Assertion references missing evidence")
    return result


def _first_non_empty_line(text: str) -> Optional[str]:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return None


def _extract_year(text: str) -> Optional[int]:
    match = re.search(r"\b(19|20)\d{2}\b", text)
    if not match:
        return None
    return int(match.group(0))


def _split_authors(value: Optional[str]) -> list[str]:
    if not value:
        return ["Unknown authors"]
    authors = [part.strip() for part in re.split(r",|;| and ", value) if part.strip()]
    return authors or [value.strip()]


def _normalize_text_to_markdown(page_texts: list[str]) -> str:
    sections: list[str] = []
    for index, text in enumerate(page_texts, start=1):
        cleaned_lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not cleaned_lines:
            continue
        body = "\n\n".join(cleaned_lines)
        sections.append(f"## Page {index}\n\n{body}")
    return "\n\n".join(sections).strip()


def _domain_pack_config_paths() -> list[Path]:
    base_dir = Path(__file__).resolve().parents[1]
    candidates = [base_dir / "config" / "domain-pack.yaml"]
    configs_dir = base_dir / "configs"
    if configs_dir.exists():
        candidates.extend(sorted(configs_dir.glob("*.yaml")))
        candidates.extend(sorted(configs_dir.glob("*.yml")))
    return [candidate for candidate in candidates if candidate.exists()]


def load_domain_pack_config(domain_pack_namespace: str) -> Optional[DomainPackConfig]:
    """Load the domain pack whose namespace matches ``domain_pack_namespace``."""
    from backend.config.loader import DomainPackLoader

    loader = DomainPackLoader()
    default_config: Optional[DomainPackConfig] = None
    for config_path in _domain_pack_config_paths():
        try:
            config = loader.load(config_path)
        except Exception:
            continue
        if config_path.name == "domain-pack.yaml":
            default_config = config
        if config.domain.id.split(".")[-1] == domain_pack_namespace:
            return config

    # The bundled default pack doubles as the optical pack.
    if domain_pack_namespace == "optical":
        return default_config
    return None


def _build_unit_alias_map(config: DomainPackConfig) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for canonical, variants in config.validation.unit_normalization.items():
        aliases[canonical.lower()] = canonical
        for variant in variants:
            aliases[(variant or "").lower()] = canonical
    return aliases


def _chunk_is_caption_like(text: str) -> bool:
    normalized = text.strip().lower()
    return bool(re.match(r"^(figure|fig\.?|table)\s+\d+[a-z]?(?:\s*[:.-]|\s)", normalized))


def _contains_metric_term(text: str, metric_terms: list[str]) -> bool:
    normalized_text = text.lower()
    for term in metric_terms:
        normalized_term = term.lower().replace("_", " ").strip()
        if not normalized_term:
            continue
        if len(normalized_term) <= 3 or re.fullmatch(r"[a-z0-9]+", normalized_term):
            pattern = rf"(?<![a-z0-9]){re.escape(normalized_term)}(?![a-z0-9])"
            if re.search(pattern, normalized_text):
                return True
            continue
        if normalized_term in normalized_text:
            return True
    return False


def _find_metric_term_spans(text: str, metric_terms: list[str]) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    for term in metric_terms:
        raw_term = term.replace("_", " ").strip()
        normalized_term = raw_term.lower()
        if not raw_term:
            continue
        if len(raw_term) <= 3 and raw_term.isalpha() and raw_term.upper() == raw_term:
            pattern = re.compile(rf"(?<![A-Za-z0-9]){re.escape(raw_term)}(?![A-Za-z0-9])")
            spans.extend(match.span() for match in pattern.finditer(text))
            continue
        if len(normalized_term) <= 3 or re.fullmatch(r"[a-z0-9]+", normalized_term):
            pattern = re.compile(rf"(?<![a-z0-9]){re.escape(normalized_term)}(?![a-z0-9])")
            spans.extend(match.span() for match in pattern.finditer(text.lower()))
        else:
            pattern = re.compile(re.escape(normalized_term))
            spans.extend(match.span() for match in pattern.finditer(text.lower()))
    return spans


def _select_metric_value_match(
    text: str,
    metric_terms: list[str],
    expected_unit: str,
    unit_alias_map: dict[str, str],
) -> Optional[re.Match[str]]:
    term_spans = _find_metric_term_spans(text, metric_terms)
    if not term_spans:
        return None

    numeric_pattern = re.compile(r"(-?\d+(?:\.\d+)?)\s*([a-zA-Z%]+)?")
    best_match: Optional[re.Match[str]] = None
    best_rank: Optional[tuple[int, int, int]] = None

    for match in numeric_pattern.finditer(text):
        unit_value = (match.group(2) or "").lower()
        canonical_unit = unit_alias_map.get(unit_value, unit_value)
        if unit_value and len(unit_value) == 1 and canonical_unit != expected_unit:
            continue

        distance = min(
            min(abs(match.start() - start), abs(match.start() - end))
            for start, end in term_spans
        )
        if distance > 96:
            continue

        has_expected_unit = canonical_unit == expected_unit
        if expected_unit == "unitless":
            has_expected_unit = canonical_unit in {"", "unitless"}

        if expected_unit != "unitless" and not has_expected_unit:
            continue
        if expected_unit == "unitless" and not has_expected_unit and unit_value:
            continue

        rank = (
            0 if has_expected_unit else 1,
            distance,
            match.start(),
        )
        if best_rank is None or rank < best_rank:
            best_rank = rank
            best_match = match

    return best_match


def _extract_assertions_heuristic(
    chunks: list[ExtractedChunk],
    config: Optional[DomainPackConfig],
    domain_pack_namespace: str,
) -> list[ExtractedAssertion]:
    """
    Heuristic-based assertion extraction using pattern matching.

    This is the fallback method when LLM extraction is unavailable.
    Uses regex patterns to find metric mentions and nearby numeric values.
    """
    if config is None:
        return []

    unit_alias_map = _build_unit_alias_map(config)
    assertions: list[ExtractedAssertion] = []
    seen_subjects: set[str] = set()

    for metric in config.core_metrics:
        metric_terms = [metric.name, *metric.aliases]
        for chunk in chunks:
            if _chunk_is_caption_like(chunk.raw_text):
                continue
            if not _contains_metric_term(chunk.raw_text, metric_terms):
                continue

            selected_match = _select_metric_value_match(
                chunk.raw_text,
                metric_terms,
                metric.expected_unit,
                unit_alias_map,
            )
            if selected_match is None:
                continue

            unit_value = (selected_match.group(2) or "").lower()
            canonical_unit = unit_alias_map.get(unit_value, metric.expected_unit if not unit_value else unit_value)
            subject = f"{domain_pack_namespace}:{metric.name}"
            if subject in seen_subjects:
                break

            assertion_id = f"assert_{slugify(metric.name)}_{chunk.chunk_id}"
            assertions.append(
                ExtractedAssertion(
                    assertion_id=assertion_id,
                    subject=subject,
                    predicate="equals",
                    object=selected_match.group(1),
                    unit=canonical_unit or metric.expected_unit,
                    context_conditions={
                        "page": chunk.bounding_box.get("page"),
                        "confidence": 0.72,
                        "source": "domain_pack_heuristic",
                    },
                    evidence_links=[EvidenceLink(source_id=chunk.chunk_id, confidence_score=0.72)],
                )
            )
            seen_subjects.add(subject)
            break

    return assertions


def _extract_assertions(
    chunks: list[ExtractedChunk],
    formulas: list[ExtractedFormula],
    config: Optional[DomainPackConfig],
    domain_pack_namespace: str,
) -> tuple[list[ExtractedAssertion], str, dict[str, Any]]:
    """
    Extract assertions using LLM semantic extraction with heuristic fallback.

    Strategy:
    1. Try LLM-based semantic extraction if available
    2. Fall back to heuristic pattern matching if LLM unavailable or fails
    3. Combine results, preferring LLM extractions for overlapping metrics

    Returns:
        (assertions, method) where method is "llm", "heuristic" or "none".
    """
    if config is None:
        return [], "none", {}

    diagnostics: dict[str, Any] = {"model_called": False, "model_seconds": 0.0, "usage": []}
    model_method = "llm"
    # Try LLM-based extraction first
    llm_assertions: list[ExtractedAssertion] = []
    try:
        llm_provider = get_default_provider()
        if llm_provider.is_configured():
            provider_name = llm_provider.config.provider
            model_method = "mock" if provider_name == "mock" else "llm"
            semantic_extractor = create_semantic_extractor(llm_provider)
            if semantic_extractor.is_available():
                llm_assertions = semantic_extractor.extract_assertions_sync(
                    chunks=chunks,
                    formulas=formulas,
                    config=config,
                    domain_pack_namespace=domain_pack_namespace,
                )
                diagnostics = semantic_extractor.diagnostics
                diagnostics.update({"model_called": True, "provider": provider_name, "model": llm_provider.config.model})
    except Exception as e:
        diagnostics = {"failed_batches": [0], "warnings": [f"Model extraction failed ({type(e).__name__}); retry extraction"], "retryable": True}
        # Log but don't crash - will fall back to heuristic
        import logging
        logging.warning(f"LLM semantic extraction failed, falling back to heuristic: {e}")

    # If LLM extraction succeeded, return those results
    if llm_assertions:
        return llm_assertions, model_method, diagnostics

    # Fall back to heuristic extraction
    heuristic = _extract_assertions_heuristic(chunks, config, domain_pack_namespace)
    for assertion in heuristic:
        assertion.context_conditions["extraction_method"] = "heuristic"
    return heuristic, "heuristic" if heuristic else "none", diagnostics


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_") or "item"


def _chunk_page_text(page_number: int, text: str) -> list[ExtractedChunk]:
    chunks: list[ExtractedChunk] = []
    paragraphs = [paragraph.strip() for paragraph in re.split(r"\n\s*\n", text) if paragraph.strip()]
    if not paragraphs and text.strip():
        paragraphs = [text.strip()]

    for index, paragraph in enumerate(paragraphs):
        normalized = re.sub(r"\s+", " ", paragraph).strip()
        if not normalized:
            continue
        chunks.append(
            ExtractedChunk(
                chunk_id=f"chunk_p{page_number}_{index}",
                raw_text=normalized,
                bounding_box={
                    "page": page_number,
                    "coordinate_precision": "page_only",
                },
            )
        )
    return chunks


def _build_metadata(file_name: str, raw_bytes: bytes, extracted_text: str, reader: Optional[PdfReader]) -> PaperMetadata:
    metadata = reader.metadata if reader is not None else None
    title = None
    if metadata:
        title = metadata.get("/Title") or metadata.get("Title")
    if not title:
        title = _first_non_empty_line(extracted_text)
    if not title:
        title = Path(file_name).stem.replace("_", " ").replace("-", " ").strip() or file_name

    authors = _split_authors(metadata.get("/Author") if metadata else None)
    # Benchmark years in an abstract are not publication years. Prefer the
    # explicit arXiv identifier in the supplied document (YYMM.number).
    arxiv = re.search(r'arXiv:\s*(\d{2})(?:0[1-9]|1[0-2])\.\d{4,5}', extracted_text[:12000], re.I)
    year = (1900 + int(arxiv[1]) if int(arxiv[1]) >= 91 else 2000 + int(arxiv[1])) if arxiv else _extract_year(extracted_text)
    if year is None and metadata:
        year = _extract_year(" ".join(str(value) for value in metadata.values() if value))
    if year is None:
        year = datetime.now(timezone.utc).year

    venue = metadata.get("/Subject") if metadata else None
    if not venue:
        venue = "Unknown venue"

    return PaperMetadata(
        title=title,
        authors=authors,
        year=year,
        venue=venue,
        doi=None,
        provenance_hash=hashlib.sha256(raw_bytes).hexdigest(),
    )


def _resolve_parse_source(request: ParsePdfWithDomainPackParams) -> ParseSource:
    warnings: list[str] = []

    if request.upload_id:
        upload = load_pdf_upload(request.upload_id)
        return ParseSource(
            raw_bytes=upload.stored_path.read_bytes(),
            file_name=upload.file_name,
            upload=upload,
            warnings=warnings,
            source_kind="upload",
        )

    if request.paper_uri:
        paper_path = Path(request.paper_uri)
        return ParseSource(
            raw_bytes=paper_path.read_bytes(),
            file_name=paper_path.name,
            warnings=warnings,
            source_kind="paper_uri",
        )

    if request.raw_text:
        warnings.append("Parsing used raw_text fallback instead of PDF bytes.")
        return ParseSource(
            raw_bytes=request.raw_text.encode("utf-8"),
            file_name="uploaded.pdf",
            warnings=warnings,
            source_kind="raw_text",
        )

    raise ValueError("One of upload_id, paper_uri, or raw_text is required")


class BasicPdfTextExtractor:
    name = "basic_pypdf"

    def extract(self, source: ParseSource, request: ParsePdfWithDomainPackParams) -> ExtractorArtifacts:
        page_texts: list[str] = []
        chunks: list[ExtractedChunk] = []
        warnings = list(source.warnings)
        reader: Optional[PdfReader] = None

        if source.source_kind == "raw_text" and request.raw_text and not request.upload_id and not request.paper_uri:
            normalized_text = request.raw_text.strip()
            page_texts = [normalized_text] if normalized_text else []
            chunks.extend(_chunk_page_text(1, normalized_text))
            return ExtractorArtifacts(
                page_texts=page_texts,
                chunks=chunks,
                warnings=warnings,
                extraction_method="raw_text",
                reader=None,
            )

        try:
            reader = PdfReader(BytesIO(source.raw_bytes))
            for page_number, page in enumerate(reader.pages, start=1):
                page_text = (page.extract_text() or "").strip()
                if not page_text:
                    warnings.append(f"Page {page_number} did not yield extractable text.")
                    continue
                page_texts.append(page_text)
                chunks.extend(_chunk_page_text(page_number, page_text))
        except Exception as exc:
            raise ValueError(f"Failed to parse uploaded PDF: {exc}") from exc

        return ExtractorArtifacts(
            page_texts=page_texts,
            chunks=chunks,
            warnings=warnings,
            extraction_method="pypdf",
            reader=reader,
        )


def _marker_output_file(output_dir: Path, extension: str) -> Path:
    """
    Find Marker output files. Handles both old and new Marker versions:
    - Old (<1.0): Files directly in output_dir (e.g., output_dir/doc.md)
    - New (>=1.0): Files in subdirectory (e.g., output_dir/doc/doc.md, doc_meta.json)
    """
    # For JSON files, try _meta.json pattern first (new Marker format)
    patterns = [f"*_meta.{extension}"] if extension == "json" else []
    patterns.append(f"*.{extension}")

    # First try direct files (old CLI)
    for pattern in patterns:
        matches = sorted(output_dir.glob(pattern))
        if matches:
            return matches[0]

    # Try subdirectories (new CLI creates a folder named after the PDF)
    subdirs = [d for d in output_dir.iterdir() if d.is_dir()]
    for subdir in subdirs:
        for pattern in patterns:
            matches = sorted(subdir.glob(pattern))
            if matches:
                return matches[0]

    raise RuntimeError(f"Marker did not produce a .{extension} output file in {output_dir} or subdirectories")


def _marker_block_text(block: dict[str, Any]) -> str:
    html = block.get("html") or ""
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _marker_block_bbox(block: dict[str, Any], page_number: int) -> dict[str, Any]:
    polygon = block.get("polygon") or []
    if polygon and isinstance(polygon, list):
        xs = [point[0] for point in polygon if isinstance(point, list) and len(point) >= 2]
        ys = [point[1] for point in polygon if isinstance(point, list) and len(point) >= 2]
        if xs and ys:
            return {
                "page": page_number,
                "x": min(xs),
                "y": min(ys),
                "width": max(xs) - min(xs),
                "height": max(ys) - min(ys),
            }
    return {"page": page_number, "x": 0, "y": 0, "width": 0, "height": 0}


def _collect_marker_blocks(node: Any) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    if isinstance(node, list):
        for item in node:
            blocks.extend(_collect_marker_blocks(item))
        return blocks
    if not isinstance(node, dict):
        return blocks

    blocks.append(node)
    children = node.get("children")
    if children:
        blocks.extend(_collect_marker_blocks(children))
    return blocks


class MarkerPdfExtractor:
    name = "marker"

    def _marker_command(self) -> list[str]:
        configured = os.getenv("ONTOFORGE_MARKER_COMMAND", "marker_single").strip()
        if not configured:
            configured = "marker_single"
        return configured.split()

    def _build_base_args(self, request: ParsePdfWithDomainPackParams) -> list[str]:
        args: list[str] = []
        if os.getenv("ONTOFORGE_MARKER_FORCE_OCR", "").strip().lower() in {"1", "true", "yes"}:
            args.append("--force_ocr")
        if os.getenv("ONTOFORGE_MARKER_USE_LLM", "").strip().lower() in {"1", "true", "yes"}:
            args.append("--use_llm")
        if os.getenv("ONTOFORGE_MARKER_REDO_INLINE_MATH", "").strip().lower() in {"1", "true", "yes"}:
            args.append("--redo_inline_math")
        page_range = os.getenv("ONTOFORGE_MARKER_PAGE_RANGE", "").strip()
        if page_range:
            args.extend(["--page_range", page_range])
        return args

    def _run_marker(self, pdf_path: Path, output_dir: Path, output_format: str, request: ParsePdfWithDomainPackParams) -> None:
        command = self._marker_command()
        executable = shutil.which(command[0])
        if executable is None:
            raise RuntimeError(
                f"Marker extractor selected but command '{command[0]}' is not available. "
                "Set ONTOFORGE_MARKER_COMMAND to a valid marker_single path."
            )

        # Check marker version by running --help to detect CLI format
        help_result = subprocess.run([executable, "--help"], capture_output=True, text=True)
        uses_old_cli = "--output_dir" not in help_result.stdout

        if uses_old_cli:
            # Old marker CLI (v0.2.6): marker_single filename output_folder
            # It outputs files directly to output_folder
            full_command = [
                executable,
                *command[1:],
                str(pdf_path),
                str(output_dir),
                *self._build_base_args(request),
            ]
        else:
            # New marker CLI: marker_single filename --output_dir dir --output_format format
            full_command = [
                executable,
                *command[1:],
                str(pdf_path),
                "--output_dir",
                str(output_dir),
                "--output_format",
                output_format,
                *self._build_base_args(request),
            ]

        result = subprocess.run(full_command, capture_output=True, text=True)
        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            stdout = (result.stdout or "").strip()
            message = stderr or stdout or f"Marker command exited with status {result.returncode}"
            raise RuntimeError(f"Marker extraction failed: {message}")

    def extract(self, source: ParseSource, request: ParsePdfWithDomainPackParams) -> ExtractorArtifacts:
        with tempfile.TemporaryDirectory(prefix="ontoforge_marker_") as temp_dir:
            temp_root = Path(temp_dir)
            pdf_path = temp_root / source.file_name
            pdf_path.write_bytes(source.raw_bytes)

            # Check if using old CLI
            command = self._marker_command()
            executable = shutil.which(command[0])
            if executable:
                help_result = subprocess.run([executable, "--help"], capture_output=True, text=True)
                uses_old_cli = "--output_dir" not in help_result.stdout
            else:
                uses_old_cli = False

            if uses_old_cli:
                # Old CLI generates both formats in one run
                output_dir = temp_root / "marker_output"
                output_dir.mkdir(parents=True, exist_ok=True)
                self._run_marker(pdf_path, output_dir, "both", request)

                markdown_text = _marker_output_file(output_dir, "md").read_text(encoding="utf-8")
                marker_json = json.loads(_marker_output_file(output_dir, "json").read_text(encoding="utf-8"))
            else:
                # New CLI (>=1.0): a markdown run normally also writes *_meta.json.
                output_dir = temp_root / "marker_output"
                output_dir.mkdir(parents=True, exist_ok=True)

                self._run_marker(pdf_path, output_dir, "markdown", request)

                markdown_text = _marker_output_file(output_dir, "md").read_text(encoding="utf-8")
                try:
                    metadata_file = _marker_output_file(output_dir, "json")
                except RuntimeError:
                    # Some Marker builds only emit the explicitly requested format.
                    # Ask for JSON as a second pass instead of failing the ingest.
                    self._run_marker(pdf_path, output_dir, "json", request)
                    metadata_file = _marker_output_file(output_dir, "json")
                marker_json = json.loads(metadata_file.read_text(encoding="utf-8"))

        # Detect Marker 1.10+ format (has 'table_of_contents' key instead of page blocks)
        is_new_marker_format = isinstance(marker_json, dict) and "table_of_contents" in marker_json

        if is_new_marker_format:
            # New Marker 1.10+ format: JSON only has metadata, all text is in markdown
            # Parse markdown directly into chunks
            page_texts: list[str] = []
            chunks: list[ExtractedChunk] = []
            formulas: list[ExtractedFormula] = []

            # Split markdown by paragraphs (double newline)
            paragraphs = [p.strip() for p in markdown_text.split("\n\n") if p.strip()]

            for idx, paragraph in enumerate(paragraphs):
                # Skip very short paragraphs (likely formatting artifacts)
                if len(paragraph) < 10:
                    continue

                chunks.append(
                    ExtractedChunk(
                        chunk_id=f"chunk_md_{idx}",
                        raw_text=paragraph,
                        # Marker markdown output has no coordinates; mark them
                        # explicitly instead of pretending a precise location.
                        bounding_box={
                            "page": None,
                            "x": None,
                            "y": None,
                            "width": None,
                            "height": None,
                            "coordinate_status": "unavailable",
                        },
                    )
                )

            # For new format, treat whole markdown as single page text
            page_texts = [markdown_text]

        else:
            # Old Marker format: JSON contains page blocks with text
            pages = marker_json if isinstance(marker_json, list) else [marker_json]
            page_texts: list[str] = []
            chunks: list[ExtractedChunk] = []
            formulas: list[ExtractedFormula] = []

            for page_index, page in enumerate(pages, start=1):
                page_blocks = _collect_marker_blocks(page)
                page_text_parts: list[str] = []
                text_block_index = 0
                formula_index = 0

                for block in page_blocks:
                    block_type = block.get("block_type")
                    if block_type in MARKER_SUPPORTED_TEXT_BLOCKS:
                        raw_text = _marker_block_text(block)
                        if not raw_text:
                            continue
                        page_text_parts.append(raw_text)
                        chunks.append(
                            ExtractedChunk(
                                chunk_id=f"chunk_p{page_index}_{text_block_index}",
                                raw_text=raw_text,
                                bounding_box=_marker_block_bbox(block, page_index),
                            )
                        )
                        text_block_index += 1

                    if block_type in MARKER_FORMULA_BLOCKS:
                        latex_string = _marker_block_text(block)
                        if not latex_string:
                            continue
                        formulas.append(
                            ExtractedFormula(
                                formula_id=f"formula_p{page_index}_{formula_index}",
                                latex_string=latex_string,
                                variables_map={},
                                bounding_box=_marker_block_bbox(block, page_index),
                            )
                        )
                        formula_index += 1

                page_text = "\n\n".join(page_text_parts).strip()
                if page_text:
                    page_texts.append(page_text)

        warnings = list(source.warnings)
        if not chunks:
            if is_new_marker_format:
                warnings.append("Marker 1.10+ did not extract text chunks from markdown.")
            else:
                warnings.append("Marker did not return any text-like blocks for this PDF.")

        return ExtractorArtifacts(
            page_texts=page_texts,
            chunks=chunks,
            formulas=formulas,
            warnings=warnings,
            extraction_method="marker",
            reader=None,
        )


def get_pdf_extractor() -> PdfExtractor:
    extractor_name = os.getenv("ONTOFORGE_PDF_EXTRACTOR", "basic_pypdf").strip().lower()
    if extractor_name in {"", "basic", "basic_pypdf", "pypdf"}:
        return BasicPdfTextExtractor()
    if extractor_name in {"marker", "marker_pdf"}:
        return MarkerPdfExtractor()
    raise ValueError(f"Unsupported PDF extractor '{extractor_name}'")


def parse_pdf_with_domain_pack(request: ParsePdfWithDomainPackParams) -> ParsePdfWithDomainPackResponse:
    started = time.perf_counter()
    if request.upload_id:
        authorize_pdf_upload(request.upload_id, request.workspace_id, request.owner_id)
    config = load_domain_pack_config(request.domain_pack_namespace)
    source = _resolve_parse_source(request)
    extractor = get_pdf_extractor()
    artifacts = extractor.extract(source, request)

    combined_text = "\n\n".join(artifacts.page_texts).strip()
    markdown_text = _normalize_text_to_markdown(artifacts.page_texts)
    paper_metadata = _build_metadata(source.file_name, source.raw_bytes, combined_text, artifacts.reader)
    parse_seconds = time.perf_counter() - started
    assertions, assertion_method, diagnostics = _extract_assertions(
        artifacts.chunks, artifacts.formulas, config, request.domain_pack_namespace
    )
    warnings = list(artifacts.warnings) + diagnostics.get("warnings", [])
    if artifacts.chunks and artifacts.extraction_method in {"pypdf", "raw_text"}:
        warnings.append("Page-only source locations; precise PDF bounding boxes are unavailable.")
    diagnostics.update({"parse_seconds": round(parse_seconds, 6), "total_seconds": round(time.perf_counter() - started, 6), "pages": len(artifacts.page_texts), "chunks": len(artifacts.chunks), "pdf_bytes": len(source.raw_bytes)})

    if not artifacts.chunks:
        warnings.append("No text chunks were extracted from the PDF.")
    if config is None:
        warnings.append("No backend domain-pack config was resolved for assertion grounding; preview includes metadata, markdown, and chunks only.")
    elif not assertions and not diagnostics.get("failed_batches"):
        warnings.append("No domain-grounded assertions were extracted from the parsed chunks.")
    if assertion_method == "heuristic":
        warnings.append(
            "LLM extraction was unavailable; assertions were produced by the rule-based heuristic extractor."
        )
    if assertion_method == "mock":
        warnings.append("Simulated mock-provider assertions; this is not a real LLM extraction.")

    result = ParsePdfWithDomainPackResponse(
        status="parsed" if artifacts.chunks and not diagnostics.get("failed_batches") else "needs_review",
        diagnostics=diagnostics,
        workspace_id=request.workspace_id,
        domain_pack_namespace=request.domain_pack_namespace,
        upload_id=source.upload.upload_id if source.upload else request.upload_id,
        markdown_text=markdown_text,
        paper_metadata=paper_metadata,
        chunks=artifacts.chunks,
        formulas=artifacts.formulas,
        assertions=assertions,
        warnings=warnings,
        extraction_method=artifacts.extraction_method,
        assertion_extraction_method=assertion_method,
    )
    if source.upload:
        result.preview_id = f"preview_{uuid4().hex}"
        path = _preview_path(source.upload.upload_id, result.preview_id)
        payload = {"sha256": source.upload.sha256, "config_hash": _config_hash(request.domain_pack_namespace), "result": result.model_dump()}
        pending = path.with_suffix(".tmp")
        pending.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        pending.replace(path)
    return result


def commit_parsed_pdf(
    request: CommitParsedPdfParams,
    node_repo: Any,
    edge_repo: Any,
    workspace_exists: bool = True,
) -> CommitParsedPdfResponse:
    parse_result = load_preview(request)
    for attempt in range(4):
        try:
            return _commit_atomic(request, parse_result, node_repo, edge_repo, workspace_exists)
        except TransientError:
            if attempt == 3:
                raise
            time.sleep(0.05 * 2 ** attempt)


def _commit_atomic(request, parse_result, node_repo, edge_repo, workspace_exists):
    with node_repo.db.transaction():
        # Updating the existing workspace acquires a write lock until commit.
        locked = node_repo.db.execute_query(
            "MATCH (w:WorkspaceNode {id: $id}) SET w.ingest_revision = coalesce(w.ingest_revision, 0) + 1 RETURN w.id AS id",
            {"id": request.workspace_id},
        )
        if not locked:
            raise ValueError("Workspace no longer exists")
        return _commit_preview(request, parse_result, node_repo, edge_repo, workspace_exists)


def preserve_pdf_source(request, paper_id: str, expected_hash: str) -> None:
    # Preserve the exact imported source beyond temporary upload expiry.
    source = authorize_pdf_upload(request.upload_id, request.workspace_id, request.owner_id)
    raw = source.stored_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_hash:
        raise ValueError("Uploaded source changed after preview")
    target = paper_source_path(paper_id)
    pending = target.with_suffix(f".{uuid4().hex}.tmp")
    pending.write_bytes(raw)
    pending.replace(target)


def _require_edge(create, edge):
    if create(edge) is None:
        raise ValueError("Graph relationship endpoint missing; transaction rolled back")


def _commit_preview(request, parse_result, node_repo, edge_repo, workspace_exists):
    metadata = parse_result.paper_metadata
    if metadata is None:
        raise ValueError("Parsed PDF is missing paper metadata")

    identity = f"{request.workspace_id}\0{request.domain_pack_namespace}\0{metadata.provenance_hash}"
    paper_id = "paper_" + hashlib.sha256(identity.encode()).hexdigest()

    # Local parser ids repeat across papers. The ontology run also reuses this
    # mapping so every EvidenceItem resolves to the immutable source node.
    id_map: dict[str, str] = {}

    def global_id(local_id: str) -> str:
        if local_id not in id_map:
            id_map[local_id] = f"{paper_id}::{local_id}"
        return id_map[local_id]

    config = load_domain_pack_config(request.domain_pack_namespace)

    def persist_ontology() -> dict[str, Any]:
        if config is None or not parse_result.preview_id:
            return {}
        return persist_preview_projection(
            repo=OntologyRepository(node_repo.db), workspace_id=request.workspace_id,
            paper_id=paper_id, provenance_hash=metadata.provenance_hash,
            preview_id=parse_result.preview_id, parse_result=parse_result, config=config,
            global_evidence_id=global_id,
        )

    # The source paper remains idempotent, while each immutable preview produces
    # a separate ExtractionRun. This preserves re-extractions instead of silently
    # discarding or overwriting them.
    existing_paper = node_repo.get_node_by_id(paper_id, "PaperNode")
    if existing_paper:
        projection = persist_ontology()
        return CommitParsedPdfResponse(
            status="committed",
            workspace_id=request.workspace_id,
            domain_pack_namespace=request.domain_pack_namespace,
            upload_id=request.upload_id,
            paper_id=paper_id,
            chunks_created=0,
            formulas_created=0,
            assertions_created=0,
            extraction_run_id=projection.get("run_id"),
            experiments_created=projection.get("experiments_created", 0),
            measurements_created=projection.get("measurements_created", 0),
            constraint_violations=projection.get("constraint_violations", []),
            warnings=[
                *parse_result.warnings,
                "Paper was already committed; duplicate write skipped (idempotent import).",
            ],
        )

    preserve_pdf_source(request, paper_id, metadata.provenance_hash)

    pdf_method = parse_result.extraction_method or "pypdf"
    assertion_method = parse_result.assertion_extraction_method or "heuristic"

    paper_node = PaperNode(
        id=paper_id,
        doi=metadata.doi or "",
        title=metadata.title,
        authors=metadata.authors,
        year=metadata.year,
        venue=metadata.venue or "Unknown",
        provenance_hash=metadata.provenance_hash,
        import_status="verified",
        domain_pack_namespace=request.domain_pack_namespace,
        workspace_id=request.workspace_id,
    )
    node_repo.create_paper_node(paper_node)

    if workspace_exists:
        _require_edge(edge_repo.create_contains_paper_edge,
            ContainsPaperEdge(from_node_id=request.workspace_id, to_node_id=paper_id)
        )

    if config is not None:
        node_repo.db.execute_query(
            "MERGE (d:DomainNode {id: $id}) SET d.name = $name, d.domain_pack_id = $id, "
            "d.domain_pack_version = $version, d.taxonomy_tree = $taxonomy, d.core_metrics = $metrics",
            {"id": config.domain.id, "name": config.domain.name, "version": config.schema_version,
             "taxonomy": json.dumps([d.model_dump() if hasattr(d, "model_dump") else d for d in config.domain.taxonomy_tree]),
             "metrics": json.dumps([m.model_dump() for m in config.core_metrics])},
        )
        _require_edge(edge_repo.create_belongs_to_edge,
            BelongsToEdge(
                from_node_id=paper_id,
                to_node_id=config.domain.id,
                confidence=1.0,
                primary=True,
                classification_method="manual",
            )
        )

    for chunk in parse_result.chunks:
        chunk_id = global_id(chunk.chunk_id)
        chunk_node = ChunkNode(
            id=chunk_id,
            raw_text=chunk.raw_text,
            bounding_box=chunk.bounding_box,
            verification_status="raw",
        )
        node_repo.create_chunk_node(chunk_node)
        _require_edge(edge_repo.create_contains_edge,
            ContainsEdge(from_node_id=paper_id, to_node_id=chunk_id, extraction_method=pdf_method)
        )

    for formula in parse_result.formulas:
        formula_id = global_id(formula.formula_id)
        formula_node = FormulaNode(
            id=formula_id,
            latex_string=formula.latex_string,
            variables_map=formula.variables_map,
            constraints={},
            verification_status="raw",
        )
        node_repo.create_formula_node(formula_node)
        _require_edge(edge_repo.create_contains_edge,
            ContainsEdge(from_node_id=paper_id, to_node_id=formula_id, extraction_method=pdf_method)
        )

    for assertion in parse_result.assertions:
        assertion_id = global_id(assertion.assertion_id)
        assertion_node = AssertionNode(
            id=assertion_id,
            subject=assertion.subject,
            predicate=assertion.predicate,
            object=assertion.object,
            unit=assertion.unit,
            domain_pack_namespace=request.domain_pack_namespace,
            context_conditions=assertion.context_conditions,
            status="pending",
            workspace_id=request.workspace_id,
        )
        node_repo.create_assertion_node(assertion_node)
        _require_edge(edge_repo.create_contains_edge,
            ContainsEdge(
                from_node_id=paper_id,
                to_node_id=assertion_id,
                extraction_method=f"domain_pack_{assertion_method}",
            )
        )
        for evidence in assertion.evidence_links:
            _require_edge(edge_repo.create_evidenced_by_edge,
                EvidencedByEdge(
                    from_node_id=global_id(evidence.source_id),
                    to_node_id=assertion_id,
                    confidence_score=evidence.confidence_score,
                )
            )

    projection = persist_ontology()
    return CommitParsedPdfResponse(
        status="committed" if parse_result.chunks else "needs_review",
        workspace_id=request.workspace_id,
        domain_pack_namespace=request.domain_pack_namespace,
        upload_id=request.upload_id,
        paper_id=paper_id,
        chunks_created=len(parse_result.chunks),
        formulas_created=len(parse_result.formulas),
        assertions_created=len(parse_result.assertions),
        extraction_run_id=projection.get("run_id"),
        experiments_created=projection.get("experiments_created", 0),
        measurements_created=projection.get("measurements_created", 0),
        constraint_violations=projection.get("constraint_violations", []),
        warnings=parse_result.warnings,
    )
