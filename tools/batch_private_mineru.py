#!/usr/bin/env python3
"""Submit user-authorized local PDFs to CosMatter's private MinerU workflow.

The script intentionally delegates file storage, signed upload and result
handling to ``LocalMissionApi``.  It writes only a run/status manifest; PDFs
and full Markdown remain in CosMatter private storage and are never copied to
the submission package.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cosmatter.local_api import LocalApiError, LocalMissionApi


def now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, action="append", required=True, help="authorized PDF root; may repeat")
    parser.add_argument("--output", type=Path, required=True, help="private batch manifest directory")
    parser.add_argument("--max-files", type=int, default=0, help="0 means all discovered PDFs")
    parser.add_argument("--poll-interval", type=float, default=12.0)
    parser.add_argument("--max-poll-rounds", type=int, default=0, help="0 submits only; positive values poll completion")
    parser.add_argument("--resume", action="store_true", help="reuse an existing manifest and submit only missing files")
    return parser.parse_args()


def load_manifest(path: Path, *, resume: bool) -> dict[str, Any]:
    if not resume or not path.is_file():
        return {"schema_version": "1.0", "created_at": now(), "consent": True, "files": []}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not isinstance(value.get("files"), list):
        raise ValueError("existing manifest is invalid")
    return value


def save_manifest(path: Path, manifest: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def discover(roots: list[Path]) -> list[tuple[Path, Path]]:
    result: list[tuple[Path, Path]] = []
    for root in roots:
        resolved = root.resolve()
        if not resolved.is_dir():
            raise ValueError(f"input directory does not exist: {root}")
        result.extend((resolved, item) for item in sorted(resolved.rglob("*.pdf")) if item.is_file())
    return result


def public_entry(root: Path, pdf: Path, *, sequence: int, run_id: str, created: dict[str, object]) -> dict[str, object]:
    return {
        "sequence": sequence,
        "source_root": root.name,
        "source_relative_path": pdf.relative_to(root).as_posix(),
        "file_name": pdf.name,
        "byte_count": pdf.stat().st_size,
        "run_id": run_id,
        "document_id": created.get("document_id"),
        "submitted_at": now(),
        "state": created.get("state"),
        "doi_status": created.get("doi_status"),
        "markdown_ready": False,
        "error": None,
    }


def main() -> int:
    args = parse_args()
    if args.max_files < 0 or args.max_poll_rounds < 0 or args.poll_interval <= 0:
        raise SystemExit("limits must be non-negative and poll interval must be positive")
    inputs = [path.resolve() for path in args.input]
    discovered = discover(inputs)
    if args.max_files:
        discovered = discovered[: args.max_files]
    output = args.output.resolve()
    manifest_path = output / "mineru_batch_manifest.json"
    manifest = load_manifest(manifest_path, resume=args.resume)
    manifest["updated_at"] = now()
    manifest["input_roots"] = [path.name for path in inputs]
    manifest["requested_files"] = len(discovered)
    existing = {str(item.get("source_root")) + "/" + str(item.get("source_relative_path")): item for item in manifest["files"] if isinstance(item, dict)}

    api = LocalMissionApi.from_project()
    if not bool(api.status()["providers"]["mineru"]):
        raise RuntimeError("MinerU is not configured; no PDF was submitted")

    batch_label = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    for sequence, (root, pdf) in enumerate(discovered, start=1):
        key = root.name + "/" + pdf.relative_to(root).as_posix()
        if key in existing:
            continue
        try:
            created = api.create_pdf_run(
                {
                    "consent": True,
                    "run_id": f"mineru_batch_{batch_label}_{sequence:03d}",
                    "question": "Private user-authorized PDF parsing and bibliographic screening.",
                    "material": "user-authorized materials literature corpus",
                    "property": "source localization and bibliographic metadata",
                    "scope": "Private MinerU parsing only; no automatic EvidenceCard acceptance or scientific conclusion.",
                },
                pdf.name,
                pdf.read_bytes(),
            )
            entry = public_entry(root, pdf, sequence=sequence, run_id=str(created["run_id"]), created=created)
        except (LocalApiError, OSError, ValueError) as error:
            entry = {
                "sequence": sequence,
                "source_root": root.name,
                "source_relative_path": pdf.relative_to(root).as_posix(),
                "file_name": pdf.name,
                "byte_count": pdf.stat().st_size if pdf.exists() else 0,
                "run_id": None,
                "document_id": None,
                "submitted_at": now(),
                "state": "submission_failed",
                "doi_status": None,
                "markdown_ready": False,
                "error": str(error)[:300],
            }
        manifest["files"].append(entry)
        save_manifest(manifest_path, manifest)

    for _ in range(args.max_poll_rounds):
        pending = [item for item in manifest["files"] if isinstance(item, dict) and item.get("run_id") and item.get("state") not in {"done", "failed"}]
        if not pending:
            break
        time.sleep(args.poll_interval)
        for item in pending:
            try:
                status = api.pdf_status(str(item["run_id"]))
                item["state"] = status.get("state")
                item["doi_status"] = status.get("doi_status")
                item["markdown_ready"] = bool(status.get("markdown_ready"))
                item["error"] = status.get("error")
                item["polled_at"] = now()
            except LocalApiError as error:
                item["state"] = "poll_failed"
                item["error"] = str(error)[:300]
        manifest["updated_at"] = now()
        save_manifest(manifest_path, manifest)

    states: dict[str, int] = {}
    for item in manifest["files"]:
        if isinstance(item, dict):
            state = str(item.get("state") or "unknown")
            states[state] = states.get(state, 0) + 1
    summary = {"manifest": manifest_path.name, "requested_files": len(discovered), "records": len(manifest["files"]), "states": states}
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

