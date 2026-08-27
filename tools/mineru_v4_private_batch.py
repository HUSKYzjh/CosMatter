#!/usr/bin/env python3
"""Private, auditable MinerU v4 batch upload for explicitly authorised PDFs.

The program uses the documented ``/api/v4/file-urls/batch`` endpoint (at most
200 files per request).  Signed URLs, bearer tokens, provider response bodies,
and parsed text are deliberately never written to its manifest or stdout.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from cosmatter.config import Settings


def now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


@dataclass
class FileRecord:
    data_id: str
    source_root: str
    source_relative_path: str
    upload_name: str
    byte_count: int
    sha256: str
    upload_state: str
    provider_state: str = "pending"
    error: str | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-files", type=int, default=0, help="0 means every discovered PDF; provider limit is 200")
    parser.add_argument("--poll-seconds", type=float, default=15.0)
    parser.add_argument("--poll-rounds", type=int, default=0, help="0 uploads only; otherwise polls safe aggregate states")
    return parser.parse_args()


def get_pdfs(roots: list[Path], max_files: int) -> list[tuple[Path, Path]]:
    found: list[tuple[Path, Path]] = []
    for root in roots:
        resolved = root.resolve()
        if not resolved.is_dir():
            raise ValueError(f"not a directory: {root}")
        found.extend((resolved, pdf) for pdf in sorted(resolved.rglob("*.pdf")) if pdf.is_file())
    if max_files:
        found = found[:max_files]
    if not found:
        raise ValueError("no PDFs discovered")
    if len(found) > 200:
        raise ValueError("MinerU v4 accepts at most 200 files per batch")
    return found


def upload_name(index: int, pdf: Path) -> str:
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", pdf.stem).strip("._") or "document"
    return f"{index:03d}_{stem[:180]}.pdf"


def api_json(settings: Settings, method: str, path: str, payload: dict[str, object] | None = None) -> dict[str, Any]:
    if not settings.mineru_api_token:
        raise RuntimeError("MinerU is not configured")
    request = Request(
        f"{settings.mineru_base_url}{path}",
        data=json.dumps(payload).encode("utf-8") if payload is not None else None,
        headers={"Authorization": f"Bearer {settings.mineru_api_token}", "Content-Type": "application/json", "Accept": "*/*"},
        method=method,
    )
    try:
        with urlopen(request, timeout=settings.http_timeout_seconds) as response:
            value = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        raise RuntimeError(f"MinerU API HTTP {error.code}") from error
    except (URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
        raise RuntimeError("MinerU API request failed before a valid response") from error
    if not isinstance(value, dict) or value.get("code") != 0 or not isinstance(value.get("data"), dict):
        raise RuntimeError("MinerU API reported an unsuccessful batch request")
    return value["data"]


def signed_put(settings: Settings, url: str, content: bytes) -> int:
    # The documented v4 endpoint says no Content-Type header is required.  Do
    # not log the opaque signed URL or response body.
    request = Request(url, data=content, headers={"Content-Length": str(len(content))}, method="PUT")
    try:
        with urlopen(request, timeout=settings.http_timeout_seconds) as response:
            return int(getattr(response, "status", 200))
    except HTTPError as error:
        return int(error.code)
    except (URLError, TimeoutError, OSError):
        return 0


def write_json(path: Path, value: object) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def main() -> int:
    args = parse_args()
    if args.max_files < 0 or args.max_files > 200 or args.poll_rounds < 0 or args.poll_seconds <= 0:
        raise SystemExit("invalid batch limits")
    files = get_pdfs([item.resolve() for item in args.input], args.max_files)
    settings = Settings.load()  # private configuration remains inside this process
    if not settings.mineru_api_token:
        raise SystemExit("MinerU is not configured")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    manifest_path = output / "mineru_v4_private_batch_manifest.json"

    records: list[FileRecord] = []
    request_files: list[dict[str, str]] = []
    contents: list[bytes] = []
    for index, (root, pdf) in enumerate(files, start=1):
        content = pdf.read_bytes()
        if not content.startswith(b"%PDF-") or len(content) > 200 * 1024 * 1024:
            raise SystemExit(f"invalid or oversized PDF: {pdf.name}")
        data_id = f"cosmatter-{index:03d}"
        name = upload_name(index, pdf)
        records.append(FileRecord(data_id, root.name, pdf.relative_to(root).as_posix(), name, len(content), hashlib.sha256(content).hexdigest(), "not_started"))
        request_files.append({"name": name, "data_id": data_id})
        contents.append(content)

    data = api_json(settings, "POST", "/api/v4/file-urls/batch", {"files": request_files, "model_version": settings.mineru_model_version})
    batch_id = data.get("batch_id")
    urls = data.get("file_urls")
    if not isinstance(batch_id, str) or not batch_id or not isinstance(urls, list) or len(urls) != len(records) or not all(isinstance(item, str) and item.startswith("https://") for item in urls):
        raise SystemExit("MinerU did not return a valid private upload batch")

    manifest: dict[str, object] = {"schema_version": "1.0", "created_at": now(), "batch_id": batch_id, "file_count": len(records), "files": [asdict(item) for item in records]}
    write_json(manifest_path, manifest)
    for record, url, content in zip(records, urls, contents, strict=True):
        status = signed_put(settings, url, content)
        if status in {200, 201, 204}:
            record.upload_state = "uploaded"
        elif status:
            record.upload_state = "upload_failed"
            record.error = f"signed_upload_http_{status}"
        else:
            record.upload_state = "upload_failed"
            record.error = "signed_upload_no_http_response"
        manifest["updated_at"] = now()
        manifest["files"] = [asdict(item) for item in records]
        write_json(manifest_path, manifest)

    for _ in range(args.poll_rounds):
        time.sleep(args.poll_seconds)
        data = api_json(settings, "GET", f"/api/v4/extract-results/batch/{batch_id}")
        results = data.get("extract_result")
        if isinstance(results, list):
            by_id = {str(item.get("data_id")): item for item in results if isinstance(item, dict) and isinstance(item.get("data_id"), str)}
            for record in records:
                result = by_id.get(record.data_id)
                if result is not None and isinstance(result.get("state"), str):
                    record.provider_state = str(result["state"])
        manifest["updated_at"] = now()
        manifest["files"] = [asdict(item) for item in records]
        write_json(manifest_path, manifest)

    summary = {
        "batch_id": "recorded_in_private_manifest",
        "files": len(records),
        "uploaded": sum(item.upload_state == "uploaded" for item in records),
        "upload_failed": sum(item.upload_state == "upload_failed" for item in records),
        "provider_states": {state: sum(item.provider_state == state for item in records) for state in sorted({item.provider_state for item in records})},
    }
    write_json(output / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

