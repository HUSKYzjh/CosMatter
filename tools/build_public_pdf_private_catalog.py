#!/usr/bin/env python3
"""Build a non-evidence catalogue from a public PDF allowlist and private parses.

The output intentionally contains metadata, hashes, and private relative paths
only.  It is a navigation catalogue, not an authorized evaluation cohort and
not a source of accepted material facts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class CatalogError(ValueError):
    pass


def load(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CatalogError(f"cannot load {path.name}") from error


def fingerprint(documents: list[dict[str, Any]]) -> str:
    raw = json.dumps(documents, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allowlist", type=Path, required=True)
    parser.add_argument("--download-receipt", type=Path, required=True)
    parser.add_argument("--markdown-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        allowlist = load(args.allowlist)
        receipt = load(args.download_receipt)
        markdown = load(args.markdown_manifest)
        if not isinstance(allowlist, dict) or allowlist.get("trust_status") != "human_curated_public_pdf_allowlist_not_evidence":
            raise CatalogError("allowlist trust boundary is invalid")
        if not isinstance(receipt, dict) or receipt.get("trust_status") != "private_public_pdf_download_receipt_not_corpus_not_evidence":
            raise CatalogError("download receipt trust boundary is invalid")
        if not isinstance(markdown, dict) or markdown.get("private_output_only") is not True:
            raise CatalogError("Markdown manifest must be private-output only")
        allow_docs = allowlist.get("documents")
        receipt_docs = receipt.get("documents")
        markdown_docs = markdown.get("entries")
        if not all(isinstance(value, list) for value in (allow_docs, receipt_docs, markdown_docs)):
            raise CatalogError("input document arrays are invalid")
        by_name = {item.get("filename"): item for item in allow_docs if isinstance(item, dict) and isinstance(item.get("filename"), str)}
        receipt_by_name = {item.get("filename"): item for item in receipt_docs if isinstance(item, dict) and item.get("status") in {"downloaded", "already_present"}}
        parsed_by_name = {item.get("source_relative_path"): item for item in markdown_docs if isinstance(item, dict) and item.get("status") == "downloaded"}
        if len(by_name) != len(allow_docs) or set(by_name) != set(receipt_by_name) or set(by_name) != set(parsed_by_name):
            raise CatalogError("allowlist, receipt, and completed private Markdown identities must match exactly")
        documents: list[dict[str, Any]] = []
        for filename in sorted(by_name):
            source, downloaded, parsed = by_name[filename], receipt_by_name[filename], parsed_by_name[filename]
            if not all(isinstance(source.get(key), str) and source[key].strip() for key in ("document_id", "title")):
                raise CatalogError("public source metadata is invalid")
            if not all(isinstance(item.get(key), str) and item[key] for item, key in ((downloaded, "sha256"), (parsed, "markdown_sha256"), (parsed, "markdown_relative_path"))):
                raise CatalogError("download or parse receipt is incomplete")
            documents.append({
                "document_id": source["document_id"],
                "provisional_title": source["title"],
                "source_group": "LiuTheoryLab_public_allowlist_20260820",
                "markdown_sha256": parsed["markdown_sha256"],
                "private_markdown_relative_path": parsed["markdown_relative_path"],
                "parse_state": "done",
                "classification": "unreviewed",
                "evidence_status": "not_evidence_requires_human_source_map_review",
            })
        if len({item["document_id"] for item in documents}) != len(documents):
            raise CatalogError("public catalogue document IDs are not unique")
        catalog = {
            "schema_version": "1.0",
            "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
            "trust_status": "private_parsed_library_catalog_not_corpus_not_evidence",
            "access_boundary": "publicly_hosted_pdf_private_internal_processing_only_redistribution_not_assessed",
            "catalog_fingerprint": fingerprint(documents),
            "document_count": len(documents),
            "duplicate_parse_receipts_merged": 0,
            "source_groups": {"LiuTheoryLab_public_allowlist_20260820": len(documents)},
            "input_integrity_summary": {
                "declared_files": len(allow_docs),
                "valid_pdf_files": len(receipt_by_name),
                "invalid_or_misnamed_count": 0,
            },
            "documents": documents,
        }
        output = args.output.resolve()
        if output.exists():
            raise CatalogError("refusing to overwrite an existing catalogue")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"document_count": len(documents), "catalog_fingerprint": catalog["catalog_fingerprint"], "output": str(output)}, ensure_ascii=False))
        return 0
    except CatalogError as error:
        parser.error(str(error))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
