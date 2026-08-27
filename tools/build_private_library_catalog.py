#!/usr/bin/env python3
"""Build a private, reviewer-controlled catalog for local MinerU Markdown.

The catalog intentionally contains no Markdown text, excerpts, external URLs,
or scientific claims.  It turns the download receipt into a deterministic list
that a researcher can classify before creating a mission-specific corpus.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "1.0"


def timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def title_from_relative_path(value: str) -> str:
    name = Path(value).stem
    # Many local exports use a directory and file with the same bibliographic
    # name.  Preserve the filename as the reviewer-visible provisional title.
    return re.sub(r"\s+", " ", name).strip() or "Untitled local document"


def require_object(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--private-markdown-manifest", type=Path, required=True)
    parser.add_argument("--input-integrity", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    markdown_manifest = require_object(json.loads(args.private_markdown_manifest.read_text(encoding="utf-8")), "private Markdown manifest")
    integrity = require_object(json.loads(args.input_integrity.read_text(encoding="utf-8")), "input integrity record")
    entries = markdown_manifest.get("entries")
    if not isinstance(entries, list):
        raise SystemExit("private Markdown manifest is missing entries")

    catalog_entries: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for item in entries:
        if not isinstance(item, dict) or item.get("status") != "downloaded":
            continue
        markdown_digest = item.get("markdown_sha256")
        source_digest = item.get("source_pdf_sha256")
        relative_path = item.get("source_relative_path")
        source_root = item.get("source_root")
        markdown_path = item.get("markdown_relative_path")
        if not all(isinstance(value, str) and value for value in (markdown_digest, relative_path, source_root, markdown_path)):
            raise SystemExit("private Markdown entry is incomplete")
        document_id = f"local-md-{markdown_digest[:24]}"
        if document_id in seen_ids:
            raise SystemExit("private Markdown entries are not unique")
        seen_ids.add(document_id)
        catalog_entries.append(
            {
                "document_id": document_id,
                "provisional_title": title_from_relative_path(relative_path),
                "source_group": source_root,
                "source_pdf_sha256": source_digest if isinstance(source_digest, str) else None,
                "markdown_sha256": markdown_digest,
                "private_markdown_relative_path": markdown_path,
                "parse_state": "done",
                "classification": "unreviewed",
                "evidence_status": "not_evidence_requires_human_source_map_review",
            }
        )

    if not catalog_entries:
        raise SystemExit("no downloaded private Markdown records are available")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    catalog = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": timestamp(),
        "trust_status": "private_parsed_library_catalog_not_corpus_not_evidence",
        "access_boundary": "institutional_access_local_review_only_no_fulltext_redistribution",
        "document_count": len(catalog_entries),
        "source_groups": {group: sum(item["source_group"] == group for item in catalog_entries) for group in sorted({item["source_group"] for item in catalog_entries})},
        "input_integrity_summary": {
            "declared_files": integrity.get("total_files"),
            "valid_pdf_files": integrity.get("pdf_signature_valid"),
            "invalid_or_misnamed_count": len(integrity.get("invalid_or_misnamed", [])) if isinstance(integrity.get("invalid_or_misnamed"), list) else None,
        },
        "documents": catalog_entries,
    }
    review_template = {
        "schema_version": SCHEMA_VERSION,
        "catalog_fingerprint": f"sha256:{__import__('hashlib').sha256(json.dumps(catalog_entries, ensure_ascii=False, separators=(',', ':'), sort_keys=True).encode('utf-8')).hexdigest()}",
        "trust_status": "blank_human_private_library_selection_template_not_corpus",
        "instructions": [
            "For each document, assign a classification and explain the inclusion or exclusion decision.",
            "Do not mark a document as evidence here. Evidence requires a separate human-reviewed Source Map.",
            "For the 90-paper BiFeO3 evaluation cohort, first select only papers that truly match the frozen research question and authorized scope.",
        ],
        "candidates": [
            {
                "document_id": item["document_id"],
                "provisional_title": item["provisional_title"],
                "source_group": item["source_group"],
                "include_for_named_cohort": "unreviewed",
                "material_system": "unreviewed",
                "review_reason": "",
            }
            for item in catalog_entries
        ],
    }
    (output / "private_library_catalog.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "private_library_selection_template.json").write_text(json.dumps(review_template, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"document_count": len(catalog_entries), "source_groups": catalog["source_groups"], "trust_status": catalog["trust_status"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
