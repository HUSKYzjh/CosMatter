#!/usr/bin/env python3
"""Build a source-identity-deduplicated catalog of private MinerU outputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def provisional_title(relative_path: str) -> str:
    return re.sub(r"\s+", " ", Path(relative_path).stem).strip() or "Untitled local document"


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--private-markdown-manifest", type=Path, required=True)
    parser.add_argument("--input-integrity", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    parsed: Any = json.loads(args.private_markdown_manifest.read_text(encoding="utf-8"))
    integrity: Any = json.loads(args.input_integrity.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict) or not isinstance(parsed.get("entries"), list) or not isinstance(integrity, dict):
        raise SystemExit("private input manifests are invalid")

    documents: list[dict[str, Any]] = []
    seen_sources: set[tuple[str, str]] = set()
    duplicate_receipts = 0
    for item in parsed["entries"]:
        if not isinstance(item, dict) or item.get("status") != "downloaded":
            continue
        markdown_sha, source_root, relative, markdown_path = (item.get("markdown_sha256"), item.get("source_root"), item.get("source_relative_path"), item.get("markdown_relative_path"))
        if not all(isinstance(value, str) and value for value in (markdown_sha, source_root, relative, markdown_path)):
            raise SystemExit("a downloaded private Markdown receipt is incomplete")
        source_key = (source_root, relative)
        if source_key in seen_sources:
            duplicate_receipts += 1
            continue
        seen_sources.add(source_key)
        document_id = f"local-pdf-{digest(source_root + chr(0) + relative)[:24]}"
        documents.append(
            {
                "document_id": document_id,
                "provisional_title": provisional_title(relative),
                "source_group": source_root,
                "markdown_sha256": markdown_sha,
                "private_markdown_relative_path": markdown_path,
                "parse_state": "done",
                "classification": "unreviewed",
                "evidence_status": "not_evidence_requires_human_source_map_review",
            }
        )
    if not documents:
        raise SystemExit("no downloaded private Markdown records are available")

    fingerprint = "sha256:" + hashlib.sha256(json.dumps(documents, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")).hexdigest()
    groups = {group: sum(item["source_group"] == group for item in documents) for group in sorted({item["source_group"] for item in documents})}
    catalog = {
        "schema_version": "1.0",
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "trust_status": "private_parsed_library_catalog_not_corpus_not_evidence",
        "access_boundary": "institutional_access_local_review_only_no_fulltext_redistribution",
        "catalog_fingerprint": fingerprint,
        "document_count": len(documents),
        "duplicate_parse_receipts_merged": duplicate_receipts,
        "source_groups": groups,
        "input_integrity_summary": {
            "declared_files": integrity.get("total_files"),
            "valid_pdf_files": integrity.get("pdf_signature_valid"),
            "invalid_or_misnamed_count": len(integrity.get("invalid_or_misnamed", [])) if isinstance(integrity.get("invalid_or_misnamed"), list) else None,
        },
        "documents": documents,
    }
    template = {
        "schema_version": "1.0",
        "catalog_fingerprint": fingerprint,
        "trust_status": "blank_human_private_library_selection_template_not_corpus",
        "instructions": [
            "Classify every candidate before defining a named evaluation cohort.",
            "Parsed full text is not evidence: acceptance still requires a human-reviewed Source Map.",
            "For the planned 90-paper BiFeO3 cohort, select only papers matching the frozen question and allowed scope.",
        ],
        "candidates": [
            {"document_id": item["document_id"], "provisional_title": item["provisional_title"], "source_group": item["source_group"], "include_for_named_cohort": "unreviewed", "material_system": "unreviewed", "review_reason": ""}
            for item in documents
        ],
    }
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    (output / "private_library_catalog.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "private_library_selection_template.json").write_text(json.dumps(template, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"document_count": len(documents), "duplicate_parse_receipts_merged": duplicate_receipts, "source_groups": groups, "catalog_fingerprint": fingerprint}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
