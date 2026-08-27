#!/usr/bin/env python3
"""Retrieve only ``full.md`` from completed private MinerU v4 result archives.

Result URLs, archive contents, and Markdown text never enter stdout or the
safe manifests.  The output root is intentionally outside the application run
and submission directories.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import json
import re
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


SOURCE = Path(__file__).with_name("mineru_v4_private_batch.py")
SPEC = importlib.util.spec_from_file_location("cosmatter_mineru_v4_downloader", SOURCE)
if SPEC is None or SPEC.loader is None:
    raise SystemExit("Cannot load private MinerU batch implementation")
batch = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = batch
SPEC.loader.exec_module(batch)


def timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def safe_component(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._") or "document"


def download_bytes(url: str, timeout: float) -> bytes:
    request = Request(url, headers={"Accept": "application/zip"}, method="GET")
    with urlopen(request, timeout=timeout) as response:
        return response.read()


def extract_full_markdown(archive: bytes) -> bytes:
    with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
        candidates = [info for info in zipped.infolist() if not info.is_dir() and (info.filename == "full.md" or info.filename.endswith("/full.md"))]
        if len(candidates) != 1:
            raise ValueError("result archive does not contain exactly one full.md")
        item = candidates[0]
        if item.file_size > 200 * 1024 * 1024:
            raise ValueError("full.md exceeds private safety limit")
        return zipped.read(item)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", action="append", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    settings = batch.Settings.load()
    summary: list[dict[str, object]] = []
    for manifest_argument in args.manifest:
        manifest_path = manifest_argument.resolve()
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        batch_id = manifest.get("batch_id")
        records = manifest.get("files")
        if not isinstance(batch_id, str) or not isinstance(records, list):
            raise SystemExit(f"invalid private manifest: {manifest_path.name}")
        data = batch.api_json(settings, "GET", f"/api/v4/extract-results/batch/{batch_id}")
        results = data.get("extract_result")
        by_id = {str(item.get("data_id")): item for item in results if isinstance(item, dict) and isinstance(item.get("data_id"), str)} if isinstance(results, list) else {}
        for record in records:
            if not isinstance(record, dict) or record.get("upload_state") != "uploaded":
                continue
            data_id = str(record.get("data_id"))
            result = by_id.get(data_id)
            entry: dict[str, object] = {"manifest": manifest_path.name, "data_id": data_id, "source_root": record.get("source_root"), "source_relative_path": record.get("source_relative_path"), "status": "not_done"}
            if not isinstance(result, dict) or result.get("state") != "done" or not isinstance(result.get("full_zip_url"), str):
                summary.append(entry)
                continue
            digest = str(record.get("sha256", ""))
            destination = output / safe_component(str(record.get("source_root", "corpus"))) / f"{safe_component(digest)[:16]}.md"
            destination.parent.mkdir(parents=True, exist_ok=True)
            try:
                markdown = extract_full_markdown(download_bytes(str(result["full_zip_url"]), settings.http_timeout_seconds))
                destination.write_bytes(markdown)
                entry.update({"status": "downloaded", "markdown_relative_path": destination.relative_to(output).as_posix(), "markdown_bytes": len(markdown), "markdown_sha256": hashlib.sha256(markdown).hexdigest()})
            except (HTTPError, URLError, TimeoutError, OSError, zipfile.BadZipFile, ValueError):
                entry["status"] = "download_or_extract_failed"
            summary.append(entry)
    status_counts: dict[str, int] = {}
    for item in summary:
        state = str(item["status"])
        status_counts[state] = status_counts.get(state, 0) + 1
    safe_manifest = {"schema_version": "1.0", "generated_at": timestamp(), "private_output_only": True, "entries": summary, "status_counts": dict(sorted(status_counts.items()))}
    (output / "private_markdown_manifest.json").write_text(json.dumps(safe_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"entries": len(summary), "status_counts": safe_manifest["status_counts"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
