#!/usr/bin/env python3
"""Create private, unreviewed review pools from a MinerU Markdown manifest.

The Markdown manifest and generated pools must remain outside this repository.
The command verifies every declared Markdown hash, creates one bounded pool and
one blank Source Map selection template per document, and never promotes a
candidate segment to evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from cosmatter.mineru_local_review import (
    MinerULocalReviewError,
    prepare_mineru_markdown_review_pool,
    source_map_pool_review_template,
    write_source_map_pool_review_template,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOCUMENT_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,199}")


class ManifestReviewError(ValueError):
    pass


def _outside_project(path: Path) -> Path:
    resolved = path.resolve()
    if resolved == PROJECT_ROOT or PROJECT_ROOT in resolved.parents:
        raise ManifestReviewError("private Markdown and review outputs must remain outside the repository")
    if "runs" in {part.casefold() for part in resolved.parts}:
        raise ManifestReviewError("private Markdown and review outputs must remain outside a runs directory")
    return resolved


def _safe_relative(value: object, *, suffix: str | None = None) -> Path:
    if not isinstance(value, str) or not value:
        raise ManifestReviewError("manifest contains an empty relative path")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ManifestReviewError("manifest contains an unsafe relative path")
    if suffix is not None and path.suffix.casefold() != suffix:
        raise ManifestReviewError(f"manifest path must end in {suffix}")
    return path


def _load_entries(manifest_path: Path, markdown_root: Path) -> list[dict[str, str]]:
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ManifestReviewError("private Markdown manifest is not valid UTF-8 JSON") from error
    if not isinstance(payload, dict) or payload.get("private_output_only") is not True:
        raise ManifestReviewError("manifest must declare private_output_only=true")
    rows = payload.get("entries")
    if not isinstance(rows, list) or not rows:
        raise ManifestReviewError("manifest has no Markdown entries")
    entries: list[dict[str, str]] = []
    document_ids: set[str] = set()
    markdown_hashes: set[str] = set()
    for row in rows:
        if not isinstance(row, dict) or row.get("status") != "downloaded":
            raise ManifestReviewError("every manifest entry must be downloaded before pool preparation")
        markdown_relative = _safe_relative(row.get("markdown_relative_path"), suffix=".md")
        source_relative = _safe_relative(row.get("source_relative_path"), suffix=".pdf")
        document_id = source_relative.stem
        if DOCUMENT_ID.fullmatch(document_id) is None or document_id in document_ids:
            raise ManifestReviewError("source PDF stem is not a unique safe document ID")
        expected_hash = row.get("markdown_sha256")
        if not isinstance(expected_hash, str) or len(expected_hash) != 64 or any(character not in "0123456789abcdef" for character in expected_hash):
            raise ManifestReviewError("manifest Markdown hash is invalid")
        markdown_path = (markdown_root / markdown_relative).resolve()
        if markdown_root != markdown_path and markdown_root not in markdown_path.parents:
            raise ManifestReviewError("manifest Markdown path escapes its private root")
        try:
            actual_hash = hashlib.sha256(markdown_path.read_bytes()).hexdigest()
        except OSError as error:
            raise ManifestReviewError("manifest Markdown file cannot be read") from error
        if actual_hash != expected_hash:
            raise ManifestReviewError("manifest Markdown hash does not match the private file")
        if expected_hash in markdown_hashes:
            raise ManifestReviewError("manifest contains duplicate Markdown content under different records")
        document_ids.add(document_id)
        markdown_hashes.add(expected_hash)
        entries.append(
            {
                "document_id": document_id,
                "markdown_relative_path": markdown_relative.as_posix(),
                "markdown_sha256": expected_hash,
            }
        )
    return sorted(entries, key=lambda item: item["document_id"])


def prepare(*, manifest_path: Path, markdown_root: Path, output: Path, mission_id: str) -> dict[str, Any]:
    if not isinstance(mission_id, str) or not mission_id.strip() or len(mission_id) > 200:
        raise ManifestReviewError("mission ID is invalid")
    private_markdown_root = _outside_project(markdown_root)
    private_output = _outside_project(output)
    if private_output.exists():
        raise ManifestReviewError("private review output already exists and will not be overwritten")
    private_manifest = _outside_project(manifest_path)
    entries = _load_entries(private_manifest, private_markdown_root)
    private_output.mkdir(parents=True, exist_ok=False)
    index: list[dict[str, str | int]] = []
    try:
        for sequence, entry in enumerate(entries, start=1):
            document_id = entry["document_id"]
            markdown_hash = entry["markdown_sha256"]
            task_id = "private_manifest_" + hashlib.sha256(f"{document_id}:{markdown_hash}".encode("utf-8")).hexdigest()
            task = {"document_id": document_id, "provider": "mineru", "state": "done", "task_id": task_id}
            pool_name = f"{sequence:02d}_{document_id}.review-pool.json"
            pool = prepare_mineru_markdown_review_pool(
                mission_id=mission_id.strip(),
                document_id=document_id,
                source_task=task,
                input_path=private_markdown_root / entry["markdown_relative_path"],
                output_path=private_output / pool_name,
            )
            template_name = f"{sequence:02d}_{document_id}.source-map-selection.template.json"
            write_source_map_pool_review_template(private_output / template_name, source_map_pool_review_template(pool))
            index.append(
                {
                    "review_slot": f"P0-{sequence:02d}",
                    "document_id": document_id,
                    "markdown_sha256": markdown_hash,
                    "candidate_segment_count": len(pool["candidate_segments"]),
                    "pool_filename": pool_name,
                    "selection_template_filename": template_name,
                    "trust_status": "private_unreviewed_mineru_markdown_candidate_pool_not_source_map",
                }
            )
    except (OSError, MinerULocalReviewError) as error:
        raise ManifestReviewError("private review pools could not be prepared") from error
    result = {
        "schema_version": "1.0",
        "mission_id": mission_id.strip(),
        "trust_status": "private_unreviewed_mineru_manifest_review_index_not_evidence",
        "pool_count": len(index),
        "entries": index,
        "review_boundary": "A human must select and justify 1-12 exact segments before a Source Map can be recorded; these pools are not evidence.",
    }
    (private_output / "review_pool_index.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--markdown-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--mission-id", required=True)
    args = parser.parse_args()
    try:
        result = prepare(
            manifest_path=args.manifest,
            markdown_root=args.markdown_root,
            output=args.output,
            mission_id=args.mission_id,
        )
    except ManifestReviewError as error:
        parser.error(str(error))
    print(json.dumps({"status": "private_review_pools_created", "pool_count": result["pool_count"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
