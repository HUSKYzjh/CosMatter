#!/usr/bin/env python3
"""Download a reviewer-curated allowlist of publicly hosted PDFs politely.

This is intentionally not a crawler.  Every URL must already be present in an
explicit JSON allowlist generated from a public landing page, repository, or
search result.  The downloader fetches one HTTPS PDF at a time, validates both
content type and magic bytes, waits between requests, and records a private
receipt.  It never redistributes the files or treats their availability as a
license to redistribute them.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen


MAX_BYTES = 100 * 1024 * 1024
CHUNK_BYTES = 1024 * 1024
ALLOWED_FIELDS = {"document_id", "filename", "title", "doi", "source_url", "source_note", "access_boundary"}


class DownloadError(ValueError):
    pass


def load_allowlist(path: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DownloadError("allowlist is not valid UTF-8 JSON") from error
    if not isinstance(payload, dict) or set(payload) != {"schema_version", "trust_status", "documents"}:
        raise DownloadError("allowlist has unsupported fields")
    if payload.get("schema_version") != "1.0" or payload.get("trust_status") != "human_curated_public_pdf_allowlist_not_evidence":
        raise DownloadError("allowlist identity is invalid")
    docs = payload.get("documents")
    if not isinstance(docs, list) or not 1 <= len(docs) <= 30:
        raise DownloadError("allowlist must contain 1 to 30 documents")
    seen_ids, seen_names = set(), set()
    result: list[dict[str, Any]] = []
    for row in docs:
        if not isinstance(row, dict) or set(row) != ALLOWED_FIELDS:
            raise DownloadError("allowlist document fields are invalid")
        document_id, filename, url = row.get("document_id"), row.get("filename"), row.get("source_url")
        if not all(isinstance(value, str) and value.strip() for value in (document_id, filename, url)):
            raise DownloadError("allowlist document identity is invalid")
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.netloc or parsed.hostname in {"localhost", "127.0.0.1", "::1"}:
            raise DownloadError("allowlist source URL must be a public HTTPS URL")
        if not filename.endswith(".pdf") or Path(filename).name != filename or filename in seen_names:
            raise DownloadError("allowlist filename is invalid or duplicated")
        if document_id in seen_ids or not isinstance(row.get("title"), str) or not row["title"].strip():
            raise DownloadError("allowlist document ID or title is invalid")
        if row.get("doi") is not None and (not isinstance(row["doi"], str) or not row["doi"].strip()):
            raise DownloadError("allowlist DOI must be a string or null")
        if not all(isinstance(row.get(key), str) and row[key].strip() for key in ("source_note", "access_boundary")):
            raise DownloadError("allowlist provenance fields are invalid")
        seen_ids.add(document_id)
        seen_names.add(filename)
        result.append(row)
    return result


def _is_pdf_existing(path: Path) -> bool:
    try:
        return path.is_file() and path.stat().st_size > 5 and path.open("rb").read(5) == b"%PDF-"
    except OSError:
        return False


def download_one(row: dict[str, Any], output: Path) -> dict[str, Any]:
    target = output / row["filename"]
    if _is_pdf_existing(target):
        payload = target.read_bytes()
        return {"document_id": row["document_id"], "filename": row["filename"], "status": "already_present", "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}
    request = Request(row["source_url"], headers={"User-Agent": "CosMatter/0.1 (academic private literature intake; Westlake University)"})
    try:
        with urlopen(request, timeout=60) as response:
            content_type = (response.headers.get("Content-Type") or "").casefold()
            length = response.headers.get("Content-Length")
            if "application/pdf" not in content_type:
                raise DownloadError("source response does not declare application/pdf")
            if length and int(length) > MAX_BYTES:
                raise DownloadError("source PDF exceeds the 100 MiB intake limit")
            chunks: list[bytes] = []
            total = 0
            while True:
                chunk = response.read(CHUNK_BYTES)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_BYTES:
                    raise DownloadError("source PDF exceeds the 100 MiB intake limit")
                chunks.append(chunk)
    except DownloadError:
        raise
    except Exception as error:
        raise DownloadError(f"download failed: {type(error).__name__}") from error
    content = b"".join(chunks)
    if not content.startswith(b"%PDF-"):
        raise DownloadError("source content does not have a PDF signature")
    if target.exists():
        raise DownloadError("refusing to overwrite an existing non-PDF target")
    target.write_bytes(content)
    return {"document_id": row["document_id"], "filename": row["filename"], "status": "downloaded", "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allowlist", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--delay-seconds", type=float, default=2.0)
    args = parser.parse_args()
    if not 1 <= args.delay_seconds <= 10:
        parser.error("delay-seconds must be between 1 and 10")
    try:
        records = load_allowlist(args.allowlist)
        output = args.output.resolve()
        output.mkdir(parents=True, exist_ok=True)
        receipts: list[dict[str, Any]] = []
        for number, row in enumerate(records, start=1):
            try:
                receipts.append(download_one(row, output))
            except DownloadError as error:
                receipts.append({"document_id": row["document_id"], "filename": row["filename"], "status": "failed", "reason": str(error)})
            if number < len(records):
                time.sleep(args.delay_seconds)
        summary = {
            "schema_version": "1.0",
            "trust_status": "private_public_pdf_download_receipt_not_corpus_not_evidence",
            "retrieved_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
            "allowlist_sha256": hashlib.sha256(args.allowlist.read_bytes()).hexdigest(),
            "documents": receipts,
            "downloaded_count": sum(item["status"] in {"downloaded", "already_present"} for item in receipts),
            "failed_count": sum(item["status"] == "failed" for item in receipts),
            "access_boundary": "publicly_hosted_pdf_private_internal_processing_only_redistribution_not_assessed",
        }
        receipt = output / "download_receipt.json"
        if receipt.exists():
            raise DownloadError("download receipt already exists; use a new output directory for another batch")
        receipt.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"downloaded_count": summary["downloaded_count"], "failed_count": summary["failed_count"], "receipt": str(receipt)}, ensure_ascii=False))
        return 0 if summary["failed_count"] == 0 else 1
    except DownloadError as error:
        parser.error(str(error))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
