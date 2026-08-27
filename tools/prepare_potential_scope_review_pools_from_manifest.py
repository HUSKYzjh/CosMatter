"""Create private PotentialScope P0 review pools from an existing Markdown manifest.

This is the reusable, deduplicating manifest entry point.  A local library may
hold multiple PDF records for one MinerU Markdown output, so it produces one
candidate pool per immutable Markdown digest.  It makes no network request and
does not create a Source Map, EvidenceCard, run artifact, or calculation task.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from cosmatter.mineru_local_review import (
    MinerULocalReviewError,
    prepare_mineru_markdown_review_pool,
    source_map_pool_review_template,
    write_source_map_pool_review_template,
)
from tools.prepare_potential_scope_review_pools import P0_MARKDOWN_SHA256


def main() -> int:
    parser = argparse.ArgumentParser(description="Create deduplicated private PotentialScope P0 review pools.")
    parser.add_argument("--manifest", required=True, type=Path, help="private Markdown manifest JSON")
    parser.add_argument("--markdown-root", required=True, type=Path, help="directory containing manifest-relative Markdown")
    parser.add_argument("--output", required=True, type=Path, help="new private output directory outside CosMatter/runs")
    parser.add_argument("--mission-id", default="potential_scope_p0_review_20260820")
    args = parser.parse_args()
    if "runs" in {part.casefold() for part in args.output.parts}:
        raise SystemExit("output must be private and outside a CosMatter/runs directory")
    if args.output.exists():
        raise SystemExit("output directory already exists; refusing to overwrite review material")
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"cannot read private manifest: {error}") from error
    entries = manifest.get("entries") if isinstance(manifest, dict) else None
    if not isinstance(entries, list):
        raise SystemExit("private manifest has no entries array")
    selected_by_hash: dict[str, dict[str, object]] = {}
    duplicate_record_count = 0
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        markdown_hash = entry.get("markdown_sha256")
        if not isinstance(markdown_hash, str) or markdown_hash not in P0_MARKDOWN_SHA256:
            continue
        if markdown_hash in selected_by_hash:
            duplicate_record_count += 1
            continue
        selected_by_hash[markdown_hash] = entry
    if set(selected_by_hash) != P0_MARKDOWN_SHA256:
        missing = len(P0_MARKDOWN_SHA256 - set(selected_by_hash))
        raise SystemExit(
            f"P0 manifest mismatch: expected {len(P0_MARKDOWN_SHA256)} unique digests, "
            f"found {len(selected_by_hash)}; missing {missing}"
        )
    args.output.mkdir(parents=True, exist_ok=False)
    index: list[dict[str, str | int]] = []
    try:
        for sequence, entry in enumerate(sorted(selected_by_hash.values(), key=lambda item: str(item["markdown_sha256"])), start=1):
            markdown_hash = str(entry["markdown_sha256"])
            relative_markdown = entry.get("markdown_relative_path")
            if not isinstance(relative_markdown, str) or not relative_markdown or Path(relative_markdown).is_absolute() or ".." in Path(relative_markdown).parts:
                raise MinerULocalReviewError("manifest Markdown reference is unsafe")
            markdown_path = args.markdown_root / relative_markdown
            document_id = f"potential_scope_p0_{markdown_hash[:16]}"
            task_id = "private_manifest_" + hashlib.sha256(markdown_hash.encode("utf-8")).hexdigest()
            pool_path = args.output / f"{sequence:02d}_{markdown_hash[:16]}.review-pool.json"
            pool = prepare_mineru_markdown_review_pool(
                mission_id=args.mission_id,
                document_id=document_id,
                source_task={"document_id": document_id, "provider": "mineru", "state": "done", "task_id": task_id},
                input_path=markdown_path,
                output_path=pool_path,
            )
            template_path = args.output / f"{sequence:02d}_{markdown_hash[:16]}.source-map-selection.template.json"
            write_source_map_pool_review_template(template_path, source_map_pool_review_template(pool))
            index.append(
                {
                    "review_slot": f"P0-{sequence:02d}",
                    "document_id": document_id,
                    "markdown_sha256": markdown_hash,
                    "candidate_segment_count": len(pool["candidate_segments"]),
                    "pool_filename": pool_path.name,
                    "selection_template_filename": template_path.name,
                    "trust_status": "private_unreviewed_mineru_markdown_candidate_pool_not_source_map",
                }
            )
    except (OSError, MinerULocalReviewError) as error:
        raise SystemExit(f"could not prepare private review pool: {error}") from error
    index_path = args.output / "review_pool_index.json"
    index_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "mission_id": args.mission_id,
                "trust_status": "private_unreviewed_potential_scope_p0_review_index_not_evidence",
                "pool_count": len(index),
                "duplicate_record_count": duplicate_record_count,
                "entries": index,
                "review_boundary": "A human must select 1-12 accurate segments and record a Source Map before any field can enter SystemSpec, PotentialPassport or ConditionMatrix.",
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": "private_review_pools_created",
                "pool_count": len(index),
                "duplicate_record_count": duplicate_record_count,
                "index_path": str(index_path),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
