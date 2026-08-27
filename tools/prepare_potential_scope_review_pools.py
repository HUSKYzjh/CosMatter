"""Build private, unreviewed MinerU candidate pools for the PotentialScope P0 queue.

The source manifest and Markdown remain private.  This script makes no network
request and writes no result into ``CosMatter/runs``.  It only makes bounded
review pools plus blank human-selection templates under a caller-supplied
private output directory.  A generated pool is not a Source Map or evidence.
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


# Exact Markdown digests selected in 01_Plan/12.  They identify local files
# without putting a private filesystem path in the resulting review templates.
P0_MARKDOWN_SHA256 = {
    "9e53f51f4ad7c79e85a0ba947fb4b2937bb1b9331c07ed5924c9d1630a09ca81",
    "aa566fb16536fcb7cdfcc26ba441ffdefbc4c59be6c7e8ad4230562223ea4a34",
    "8bcdcbc56052ac776eb80bb2344441af73d3923a040f5286d02577695e67d758",
    "61fc93328f6ef6abb328bff5a3fcddcd5c2a9543c8a5da90b0d3adaea887484f",
    "1d46571f216512d8f0931698d09a5a9cf42a12133b3bbb4f24baf4d61330386f",
    "b3c6652845cba6de165d409e665f523b8213959b51ccddd75149a6eb4f8f0e8a",
    "feb99a75c43e9fc35d5c1d386021561a250a28429f5e4f80cef53c364f2124cf",
    "740dddc861310c87f077e7fd09fadb1fe4fcacbe122997ca5bf9205d77cbf225",
    "683af66084d5b154bc58cf0b9ed2a2f644f3f299057963d1a103c920c4334b35",
    "d6f37d574cbc473c11c730db147379cbdc951aeb31d333598d1d35b5e71c439f",
    "eb17f0f7fe2691fbebba561338d07af30f56bb4aa335c0bc7f6d7b775bac4ee2",
    "3c5275e5b5b58dea9b8611578ddbbe2ea75ba44d86f3cb9667c4431d24bd64ee",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Create private, unreviewed PotentialScope P0 review pools from an existing MinerU manifest.")
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
    chosen = [entry for entry in entries if isinstance(entry, dict) and entry.get("markdown_sha256") in P0_MARKDOWN_SHA256]
    if len(chosen) != len(P0_MARKDOWN_SHA256):
        found = {entry.get("markdown_sha256") for entry in chosen}
        raise SystemExit(f"P0 manifest mismatch: expected {len(P0_MARKDOWN_SHA256)}, found {len(found)}")
    args.output.mkdir(parents=True, exist_ok=False)
    index: list[dict[str, str | int]] = []
    try:
        for sequence, entry in enumerate(sorted(chosen, key=lambda item: str(item["markdown_sha256"])), start=1):
            markdown_hash = str(entry["markdown_sha256"])
            relative_markdown = entry.get("markdown_relative_path")
            if not isinstance(relative_markdown, str) or not relative_markdown or Path(relative_markdown).is_absolute() or ".." in Path(relative_markdown).parts:
                raise MinerULocalReviewError("manifest Markdown reference is unsafe")
            markdown_path = args.markdown_root / relative_markdown
            document_id = f"potential_scope_p0_{markdown_hash[:16]}"
            internal_task_id = "private_manifest_" + hashlib.sha256(markdown_hash.encode("utf-8")).hexdigest()
            source_task = {"document_id": document_id, "provider": "mineru", "state": "done", "task_id": internal_task_id}
            pool_path = args.output / f"{sequence:02d}_{markdown_hash[:16]}.review-pool.json"
            pool = prepare_mineru_markdown_review_pool(
                mission_id=args.mission_id,
                document_id=document_id,
                source_task=source_task,
                input_path=markdown_path,
                output_path=pool_path,
            )
            template_path = args.output / f"{sequence:02d}_{markdown_hash[:16]}.source-map-selection.template.json"
            write_source_map_pool_review_template(template_path, source_map_pool_review_template(pool))
            index.append({
                "review_slot": f"P0-{sequence:02d}",
                "document_id": document_id,
                "markdown_sha256": markdown_hash,
                "candidate_segment_count": len(pool["candidate_segments"]),
                "pool_filename": pool_path.name,
                "selection_template_filename": template_path.name,
                "trust_status": "private_unreviewed_mineru_markdown_candidate_pool_not_source_map",
            })
    except (OSError, MinerULocalReviewError) as error:
        raise SystemExit(f"could not prepare private review pool: {error}") from error
    index_path = args.output / "review_pool_index.json"
    index_path.write_text(json.dumps({
        "schema_version": "1.0",
        "mission_id": args.mission_id,
        "trust_status": "private_unreviewed_potential_scope_p0_review_index_not_evidence",
        "pool_count": len(index),
        "entries": index,
        "review_boundary": "A human must select 1-12 accurate segments and record a Source Map before any field can enter SystemSpec, PotentialPassport or ConditionMatrix.",
    }, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "private_review_pools_created", "pool_count": len(index), "index_path": str(index_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
