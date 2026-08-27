#!/usr/bin/env python3
"""Build a non-evidence audit report for the full Liu Theory Lab public intake."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def url_id(url: str) -> str:
    return "liutheory-public-" + hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-index", type=Path, required=True)
    parser.add_argument("--prior-allowlist", type=Path, required=True)
    parser.add_argument("--prior-receipt", type=Path, required=True)
    parser.add_argument("--batch-directory", type=Path, required=True)
    parser.add_argument("--markdown-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("refusing to overwrite an existing audit report")
    index, prior_allowlist, prior_receipt, markdown = (load(path.resolve()) for path in (args.source_index, args.prior_allowlist, args.prior_receipt, args.markdown_manifest))
    source_docs = index.get("documents") if isinstance(index, dict) else None
    prior_docs = prior_allowlist.get("documents") if isinstance(prior_allowlist, dict) else None
    prior_receipt_docs = prior_receipt.get("documents") if isinstance(prior_receipt, dict) else None
    markdown_entries = markdown.get("entries") if isinstance(markdown, dict) else None
    if not all(isinstance(value, list) for value in (source_docs, prior_docs, prior_receipt_docs, markdown_entries)):
        raise ValueError("audit inputs lack document lists")
    prior_ok_ids = {row.get("document_id") for row in prior_receipt_docs if isinstance(row, dict) and row.get("status") in {"downloaded", "already_present"}}
    prior_urls = {row.get("source_url") for row in prior_docs if isinstance(row, dict) and row.get("document_id") in prior_ok_ids and isinstance(row.get("source_url"), str)}
    batch_receipts: list[dict[str, Any]] = []
    batch_docs: list[dict[str, Any]] = []
    for allowlist_path in sorted(args.batch_directory.resolve().glob("batch-*.allowlist.json")):
        value = load(allowlist_path)
        rows = value.get("documents") if isinstance(value, dict) else None
        if not isinstance(rows, list):
            raise ValueError(f"invalid allowlist: {allowlist_path.name}")
        batch_docs.extend(row for row in rows if isinstance(row, dict))
        number = allowlist_path.name.removesuffix(".allowlist.json")
        receipt_path = args.batch_directory.parent / "batches" / number / "pdf" / "download_receipt.json"
        receipt = load(receipt_path)
        rows = receipt.get("documents") if isinstance(receipt, dict) else None
        if not isinstance(rows, list):
            raise ValueError(f"invalid receipt: {receipt_path}")
        batch_receipts.extend(row for row in rows if isinstance(row, dict))
    expected_current_urls = {row.get("source_url") for row in batch_docs if isinstance(row.get("source_url"), str)}
    receipt_by_id = {row.get("document_id"): row for row in batch_receipts if isinstance(row.get("document_id"), str)}
    if len(expected_current_urls) != len(batch_docs) or len(receipt_by_id) != len(batch_docs):
        raise ValueError("batch identity is not one-to-one")
    current_download_failures = [row for row in batch_receipts if row.get("status") not in {"downloaded", "already_present"}]
    completed_markdown = [row for row in markdown_entries if isinstance(row, dict) and row.get("status") == "downloaded"]
    parse_failures = [row for row in markdown_entries if not isinstance(row, dict) or row.get("status") != "downloaded"]
    if current_download_failures or len(completed_markdown) != len(batch_docs) or parse_failures:
        raise ValueError("cannot mark the intake complete while a download or parse is incomplete")
    records: list[dict[str, object]] = []
    for row in source_docs:
        if not isinstance(row, dict) or not isinstance(row.get("source_url"), str) or not isinstance(row.get("title"), str):
            raise ValueError("source index document is invalid")
        url = row["source_url"]
        records.append({
            "document_id": url_id(url),
            "title": row["title"],
            "doi": row.get("doi"),
            "source_url": url,
            "source_state": "public_link_declared_by_lab_source",
            "download_state": "completed_previous_batch" if url in prior_urls else "completed_current_batches",
            "parse_state": "done",
            "classification": "unreviewed",
            "evidence_status": "not_evidence_requires_human_source_map_review",
        })
    if len(records) != len(source_docs) or len({row["document_id"] for row in records}) != len(records):
        raise ValueError("final records are not unique")
    report = {
        "schema_version": "1.0",
        "generated_at": now(),
        "trust_status": "private_public_pdf_intake_audit_not_corpus_not_evidence",
        "access_boundary": "publicly_hosted_pdf_private_internal_processing_only_redistribution_not_assessed",
        "source_index_sha256": hashlib.sha256(args.source_index.read_bytes()).hexdigest(),
        "source_unique_pdf_count": len(source_docs),
        "previously_completed_count": len(prior_urls),
        "current_batch_downloaded_count": len(batch_docs),
        "current_batch_download_failures": current_download_failures,
        "current_batch_mineru_done_count": len(completed_markdown),
        "current_batch_parse_failures": parse_failures,
        "requires_human_source_map_review_count": len(records),
        "documents": records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"documents": len(records), "current_downloaded": len(batch_docs), "current_mineru_done": len(completed_markdown), "download_failures": 0, "parse_failures": 0, "requires_human_review": len(records)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
