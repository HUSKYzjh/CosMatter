#!/usr/bin/env python3
"""Build a versioned public-PDF intake index from Liu Theory Lab's source data.

The laboratory homepage renders its publication list client-side from
``data/publication.js``.  This tool reads only that public same-origin source,
extracts declared PDF paths, excludes previously recorded successful downloads,
and emits human-reviewable batches compatible with
``download_public_pdf_allowlist.py``.  It never downloads a PDF itself.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen


ORIGIN = "https://liutheory.westlake.edu.cn/"
SOURCE_URL = urljoin(ORIGIN, "data/publication.js")
USER_AGENT = "CosMatterResearchArchive/1.0 (public metadata inventory; local academic use)"
RECORD_RE = re.compile(r"\{\s*\"year\"\s*:\s*\d{4}.*?\n\s*\}", re.DOTALL)


def timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def fetch_source() -> bytes:
    request = Request(SOURCE_URL, headers={"User-Agent": USER_AGENT, "Accept": "application/javascript,text/plain;q=0.9,*/*;q=0.1"})
    with urlopen(request, timeout=60) as response:
        final = response.geturl()
        parsed = urlparse(final)
        if parsed.scheme != "https" or parsed.netloc.lower() != urlparse(ORIGIN).netloc.lower():
            raise ValueError("publication source redirected outside the permitted origin")
        return response.read()


def source_rows(source: bytes) -> list[dict[str, Any]]:
    text = source.decode("utf-8")
    records: list[dict[str, Any]] = []
    for match in RECORD_RE.finditer(text):
        try:
            value = json.loads(match.group(0))
        except json.JSONDecodeError as error:
            raise ValueError("publication source contains an invalid record") from error
        pdf = value.get("pdf")
        title = value.get("title")
        record_id = value.get("id")
        if not isinstance(pdf, str) or not pdf.lower().endswith(".pdf") or not isinstance(title, str) or not title.strip() or not isinstance(record_id, int):
            raise ValueError("publication record lacks required public PDF metadata")
        url = urljoin(ORIGIN, pdf)
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.netloc.lower() != urlparse(ORIGIN).netloc.lower():
            raise ValueError("publication PDF lies outside the permitted origin")
        records.append(
            {
                "document_id": f"liutheory-{record_id:03d}",
                "filename": Path(parsed.path).name,
                "title": re.sub(r"<[^>]+>", "", title).strip(),
                "doi": value.get("doi") if isinstance(value.get("doi"), str) and value["doi"].strip() else None,
                "source_url": url,
                "source_note": "Public PDF path declared by Liu Theory Lab's current data/publication.js source.",
                "access_boundary": "private internal reading and parsing only; redistribution license not assessed",
                "year": value.get("year"),
                "journal": value.get("journal"),
            }
        )
    unique = {row["source_url"]: row for row in records}
    if len(unique) != 160:
        raise ValueError(f"expected 160 unique public PDF paths, found {len(unique)}")
    return sorted(unique.values(), key=lambda item: item["source_url"])


def prior_success_urls(receipt: Path) -> set[str]:
    if not receipt.exists():
        return set()
    value = json.loads(receipt.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not isinstance(value.get("documents"), list):
        raise ValueError("prior receipt is not valid")
    urls: set[str] = set()
    for row in value["documents"]:
        if isinstance(row, dict) and row.get("status") in {"downloaded", "already_present"} and isinstance(row.get("document_id"), str):
            # Match on document id later only where old receipts lack source URLs.
            urls.add(str(row["document_id"]))
    return urls


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prior-receipt", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=30)
    args = parser.parse_args()
    if not 1 <= args.batch_size <= 30:
        parser.error("--batch-size must be between 1 and 30")
    output = args.output.resolve()
    if output.exists() and any(output.iterdir()):
        parser.error("output must be a new empty directory")
    output.mkdir(parents=True, exist_ok=False)
    source = fetch_source()
    (output / "publication_source.js").write_bytes(source)
    rows = source_rows(source)
    old_ids = prior_success_urls(args.prior_receipt.resolve())
    # The former eight entries used descriptive document IDs.  Their exact URLs
    # are authoritative and are mapped by filename here, avoiding redownloads.
    old_manifest = json.loads(args.prior_receipt.resolve().read_text(encoding="utf-8"))
    old_names = {str(row.get("filename")) for row in old_manifest.get("documents", []) if isinstance(row, dict) and row.get("status") in {"downloaded", "already_present"}}
    remaining = [row for row in rows if row["filename"] not in old_names]
    index = {
        "schema_version": "1.0",
        "trust_status": "public_website_metadata_not_corpus_not_evidence",
        "generated_at": timestamp(),
        "source_url": SOURCE_URL,
        "source_sha256": hashlib.sha256(source).hexdigest(),
        "public_pdf_count": len(rows),
        "previously_downloaded_count": len(rows) - len(remaining),
        "remaining_count": len(remaining),
        "documents": rows,
    }
    (output / "source_index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for number, start in enumerate(range(0, len(remaining), args.batch_size), start=1):
        batch = remaining[start : start + args.batch_size]
        allowlist = {
            "schema_version": "1.0",
            "trust_status": "human_curated_public_pdf_allowlist_not_evidence",
            "documents": [{key: row[key] for key in ("document_id", "filename", "title", "doi", "source_url", "source_note", "access_boundary")} for row in batch],
        }
        (output / f"batch-{number:02d}.allowlist.json").write_text(json.dumps(allowlist, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"public_pdf_count": len(rows), "previously_downloaded_count": len(rows) - len(remaining), "remaining_count": len(remaining), "batches": (len(remaining) + args.batch_size - 1) // args.batch_size}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
