"""Measure real historical PDF parsing without making model calls or predictions."""
import json
from pathlib import Path
from unittest.mock import patch

from backend.schemas.protocol import ParsePdfWithDomainPackParams
from backend.services.llm.base import LLMProviderConfig, NullLLMProvider
from backend.services.pdf_ingestion_service import parse_pdf_with_domain_pack

ROOT = Path(__file__).resolve().parents[2]


def main():
    manifest = json.loads((ROOT / "docs/cv-validation/corpus.json").read_text(encoding="utf-8"))
    results = []
    for paper in manifest["papers"]:
        if paper["split"] != "historical":
            continue
        path = ROOT / f"data/cv-validation/historical/{paper['id']}.pdf"
        with patch("backend.services.pdf_ingestion_service.get_default_provider",
                   return_value=NullLLMProvider(LLMProviderConfig(provider="disabled"))):
            result = parse_pdf_with_domain_pack(ParsePdfWithDomainPackParams(
                workspace_id="cv_parser_smoke", domain_pack_namespace="cv_detection", paper_uri=str(path)))
        results.append({"id": paper["id"], "status": result.status, "assertion_source": result.assertion_extraction_method,
                        "assertions": len(result.assertions), "diagnostics": result.diagnostics, "warnings": result.warnings})
        print(f"{paper['id']}: {len(result.chunks)} chunks", flush=True)
    report = {"purpose": "Real PDF parser smoke and timing only; no LLM calls, gold annotations or gap prediction",
              "results": results}
    (ROOT / "docs/cv-validation/parser-smoke.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
