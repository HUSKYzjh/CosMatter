#!/usr/bin/env python3
"""Build download batches from the public Liu Theory Lab publication source.

The site renders publication metadata from ``data/publication.js``.  This
utility reads that single public source, snapshots it, and writes batches of at
most 30 public same-origin PDF links.  It excludes exact URLs already recorded
as downloaded in the prior allowlist/receipt pair.  No PDFs are fetched here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen


ORIGIN = "https://liutheory.westlake.edu.cn/"
SOURCE_URL = urljoin(ORIGIN, "data/publication.js")
USER_AGENT = "CosMatterResearchArchive/1.0 (public metadata inventory; local academic use)"
OBJECT = re.compile(r"\{\s*\"year\"\s*:\s*\d{4}.*?\n\s*\}", re.DOTALL)


def now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def source_bytes() -> bytes:
    request = Request(SOURCE_URL, headers={"User-Agent": USER_AGENT, "Accept": "application/javascript,text/plain;q=0.9,*/*;q=0.1"})
    with urlopen(request, timeout=60) as response:
        final_url = response.geturl()
        parsed = urlparse(final_url)
        if parsed.scheme != "https" or parsed.netloc.lower() != urlparse(ORIGIN).netloc.lower():
            raise ValueError("publication source redirected outside permitted origin")
        return response.read()


def rows_from_source(payload: bytes) -> tuple[list[dict[str, object]], int]:
    records: list[dict[str, object]] = []
    for match in OBJECT.finditer(payload.decode("utf-8")):
        value = json.loads(match.group(0))
        pdf, title, numeric_id = value.get("pdf"), value.get("title"), value.get("id")
        if not isinstance(pdf, str) or not pdf.endswith(".pdf") or not isinstance(title, str) or not title.strip() or not isinstance(numeric_id, int):
            raise ValueError("publication record lacks required PDF metadata")
        source_url = urljoin(ORIGIN, pdf)
        parsed = urlparse(source_url)
        if parsed.scheme != "https" or parsed.netloc.lower() != urlparse(ORIGIN).netloc.lower():
            raise ValueError("publication PDF is outside permitted origin")
        doi = value.get("doi")
        records.append({
            "document_id": f"liutheory-{numeric_id:03d}",
            "filename": Path(parsed.path).name,
            "title": re.sub(r"<[^>]+>", "", title).strip(),
            "doi": doi if isinstance(doi, str) and doi.strip() else None,
            "source_url": source_url,
            "source_note": "Public PDF path declared by Liu Theory Lab's current data/publication.js source.",
            "access_boundary": "private internal reading and parsing only; redistribution license not assessed",
            "year": value.get("year"),
            "journal": value.get("journal"),
        })
    unique = {str(row["source_url"]): row for row in records}
    if not unique:
        raise ValueError("publication source contains no public PDF paths")
    return sorted(unique.values(), key=lambda row: str(row["source_url"])), len(records)


def existing_urls(receipt_path: Path, allowlist_path: Path) -> set[str]:
    receipt, allowlist = read_json(receipt_path), read_json(allowlist_path)
    if not isinstance(receipt, dict) or not isinstance(allowlist, dict):
        raise ValueError("prior receipt or allowlist has an invalid top-level shape")
    receipt_documents, allowlist_documents = receipt.get("documents"), allowlist.get("documents")
    if not isinstance(receipt_documents, list) or not isinstance(allowlist_documents, list):
        raise ValueError("prior receipt or allowlist lacks documents")
    ids = {row.get("document_id") for row in receipt_documents if isinstance(row, dict) and row.get("status") in {"downloaded", "already_present"}}
    return {str(row["source_url"]) for row in allowlist_documents if isinstance(row, dict) and row.get("document_id") in ids and isinstance(row.get("source_url"), str)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prior-receipt", type=Path, required=True)
    parser.add_argument("--prior-allowlist", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=30)
    args = parser.parse_args()
    if not 1 <= args.batch_size <= 30:
        parser.error("--batch-size must be between 1 and 30")
    output = args.output.resolve()
    if output.exists():
        parser.error("output must not already exist")
    output.mkdir(parents=True)
    snapshot = source_bytes()
    rows, source_record_count = rows_from_source(snapshot)
    prior_urls = existing_urls(args.prior_receipt.resolve(), args.prior_allowlist.resolve())
    remaining = [row for row in rows if str(row["source_url"]) not in prior_urls]
    (output / "publication_source.js").write_bytes(snapshot)
    index = {
        "schema_version": "1.0",
        "trust_status": "public_website_metadata_not_corpus_not_evidence",
        "generated_at": now(),
        "source_url": SOURCE_URL,
        "source_sha256": hashlib.sha256(snapshot).hexdigest(),
        "source_record_count": source_record_count,
        "unique_public_pdf_count": len(rows),
        "previously_downloaded_count": len(rows) - len(remaining),
        "remaining_count": len(remaining),
        "documents": rows,
    }
    (output / "source_index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    public_fields = ("document_id", "filename", "title", "doi", "source_url", "source_note", "access_boundary")
    for batch_number, start in enumerate(range(0, len(remaining), args.batch_size), start=1):
        docs = [{field: row[field] for field in public_fields} for row in remaining[start : start + args.batch_size]]
        allowlist = {"schema_version": "1.0", "trust_status": "human_curated_public_pdf_allowlist_not_evidence", "documents": docs}
        (output / f"batch-{batch_number:02d}.allowlist.json").write_text(json.dumps(allowlist, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"source_record_count": source_record_count, "unique_public_pdf_count": len(rows), "previously_downloaded_count": len(rows) - len(remaining), "remaining_count": len(remaining), "batches": (len(remaining) + args.batch_size - 1) // args.batch_size}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
