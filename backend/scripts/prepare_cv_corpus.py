"""Download frozen primary-source PDFs, keeping evaluation holdouts separate."""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]


def validate_manifest(manifest):
    seen = set()
    for paper in manifest["papers"]:
        if paper["id"] in seen:
            raise ValueError("Duplicate corpus paper")
        seen.add(paper["id"])
        expected = "historical" if paper["first_public_date"] <= manifest["cutoff"] else "holdout"
        if paper["split"] != expected or not paper["pdf_url"].endswith("v1"):
            raise ValueError(f"Invalid temporal split/version: {paper['id']}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=["historical", "holdout"], default="historical")
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    manifest = json.loads((ROOT / "docs/cv-validation/corpus.json").read_text(encoding="utf-8"))
    validate_manifest(manifest)
    papers = [p for p in manifest["papers"] if p["split"] == args.split]
    if args.check_only:
        print(f"Temporal manifest valid: {len(papers)} {args.split} papers")
        return
    output = ROOT / "data/cv-validation" / args.split
    output.mkdir(parents=True, exist_ok=True)
    results = []
    with httpx.Client(follow_redirects=True, timeout=90, headers={"User-Agent": "OntoForge-course-validation/1.0"}) as client:
        for paper in papers:
            path = output / f"{paper['id']}.pdf"
            start = time.perf_counter()
            try:
                if not path.exists():
                    response = client.get(paper["pdf_url"])
                    response.raise_for_status()
                    if not response.content.startswith(b"%PDF-"):
                        raise ValueError("Remote response is not a PDF")
                    path.write_bytes(response.content)
                    time.sleep(3)  # avoid hammering the primary archive
                raw = path.read_bytes()
                from pypdf import PdfReader
                reader = PdfReader(path)
                row = {"id": paper["id"], "split": args.split, "url": paper["pdf_url"], "status": "downloaded",
                       "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw), "pages": len(reader.pages),
                       "seconds": round(time.perf_counter() - start, 4)}
            except Exception as exc:
                row = {"id": paper["id"], "split": args.split, "status": "failed", "error": str(exc)}
            results.append(row)
            print(f"{paper['id']}: {row['status']}", flush=True)
            (ROOT / f"docs/cv-validation/download-{args.split}.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    if any(row["status"] == "failed" for row in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
