"""Inspect the normalized PDF parsing output for a real file."""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir.parent))


def _ensure_backend_runtime() -> None:
    if os.environ.get("ONTOFORGE_INSPECT_PDF_BOOTSTRAPPED") == "1":
        return

    try:
        import pydantic  # noqa: F401
    except ModuleNotFoundError:
        venv_python = backend_dir / ".venv" / "bin" / "python"
        if venv_python.exists() and Path(sys.executable).resolve() != venv_python.resolve():
            env = os.environ.copy()
            env["ONTOFORGE_INSPECT_PDF_BOOTSTRAPPED"] = "1"
            os.execve(str(venv_python), [str(venv_python), __file__, *sys.argv[1:]], env)

        raise SystemExit(
            "OntoForge backend dependencies are not installed for the current Python interpreter. "
            "Use backend/.venv/bin/python or install backend/requirements.txt."
        )


_ensure_backend_runtime()

from backend.schemas.protocol import ParsePdfWithDomainPackParams
from backend.services.pdf_ingestion_service import parse_pdf_with_domain_pack


def build_snapshot(response: Any) -> dict[str, Any]:
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
                "variables_map": formula.variables_map,
            }
            for formula in response.formulas
        ],
        "assertions": [
            {
                "subject": assertion.subject,
                "predicate": assertion.predicate,
                "object": assertion.object,
                "unit": assertion.unit,
                "context_conditions": assertion.context_conditions,
                "evidence_sources": [link.source_id for link in assertion.evidence_links],
            }
            for assertion in response.assertions
        ],
        "warnings": response.warnings,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect OntoForge PDF parsing output.")
    parser.add_argument("pdf_path", help="Path to the PDF file to inspect")
    parser.add_argument("--workspace-id", default="workspace_debug", help="Workspace id for the parse request")
    parser.add_argument("--domain-pack", default="optical", help="Domain-pack namespace")
    parser.add_argument(
        "--full",
        action="store_true",
        help="Print the full ParsePdfWithDomainPackResponse instead of the normalized snapshot view",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    pdf_path = Path(args.pdf_path).expanduser().resolve()
    if not pdf_path.exists() or not pdf_path.is_file():
        print(json.dumps({"error": f"PDF not found: {pdf_path}"}, indent=2), file=sys.stderr)
        return 1

    response = parse_pdf_with_domain_pack(
        ParsePdfWithDomainPackParams(
            workspace_id=args.workspace_id,
            domain_pack_namespace=args.domain_pack,
            paper_uri=str(pdf_path),
        )
    )

    payload = response.model_dump() if args.full else build_snapshot(response)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())