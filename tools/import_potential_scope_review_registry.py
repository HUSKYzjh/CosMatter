"""Create a quote-free PotentialScope source registry from human selections.

Input pools and completed review templates remain in a private directory outside
``CosMatter/runs``.  The only output is a provenance registry with hashes,
identifiers and counts.  It does not create Source Maps or EvidenceCards and
never contacts an API, reads a PDF, runs a model, or launches a calculation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from cosmatter.potential_scope_review_registry import (
    PotentialScopeReviewRegistryError,
    build_reviewed_source_registry,
    load_reviewed_source,
    write_reviewed_source_registry,
)


def _is_in_runs(path: Path) -> bool:
    return "runs" in {part.casefold() for part in path.parts}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import completed private PotentialScope review templates into a quote-free source registry."
    )
    parser.add_argument("--review-index", required=True, type=Path, help="private review_pool_index.json")
    parser.add_argument("--output", required=True, type=Path, help="new quote-free registry JSON outside CosMatter/runs")
    args = parser.parse_args()
    if _is_in_runs(args.review_index) or _is_in_runs(args.output):
        raise SystemExit("private review index and registry output must remain outside CosMatter/runs")
    if args.output.exists():
        raise SystemExit("registry output already exists; refusing to overwrite human review history")
    try:
        index = json.loads(args.review_index.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"cannot read private review index: {error}") from error
    if not isinstance(index, dict) or index.get("trust_status") != "private_unreviewed_potential_scope_p0_review_index_not_evidence":
        raise SystemExit("private review index is not a PotentialScope P0 candidate index")
    mission_id = index.get("mission_id")
    entries = index.get("entries")
    if not isinstance(mission_id, str) or not mission_id or not isinstance(entries, list) or not entries:
        raise SystemExit("private review index identity is invalid")
    registry_entries = []
    root = args.review_index.parent
    try:
        for entry in entries:
            if not isinstance(entry, dict):
                raise PotentialScopeReviewRegistryError("review index entry is invalid")
            markdown_hash = entry.get("markdown_sha256")
            document_id = entry.get("document_id")
            pool_name = entry.get("pool_filename")
            review_name = entry.get("selection_template_filename")
            if not all(isinstance(item, str) and item for item in (markdown_hash, document_id, pool_name, review_name)):
                raise PotentialScopeReviewRegistryError("review index entry has missing filenames or identity")
            if len(markdown_hash) != 64 or any(char not in "0123456789abcdef" for char in markdown_hash):
                raise PotentialScopeReviewRegistryError("review index Markdown fingerprint is invalid")
            pool_path = root / pool_name
            review_path = root / review_name
            if any(path.is_absolute() or ".." in path.parts for path in (Path(pool_name), Path(review_name))):
                raise PotentialScopeReviewRegistryError("review index filenames must be local basenames")
            registry_entries.append(
                load_reviewed_source(
                    mission_id=mission_id,
                    document_id=document_id,
                    source_task={
                        "document_id": document_id,
                        "provider": "mineru",
                        "state": "done",
                        "task_id": "private_manifest_" + hashlib.sha256(markdown_hash.encode("utf-8")).hexdigest(),
                    },
                    pool_path=pool_path,
                    review_path=review_path,
                )
            )
        registry = build_reviewed_source_registry(mission_id=mission_id, entries=registry_entries)
        write_reviewed_source_registry(args.output, registry)
    except PotentialScopeReviewRegistryError as error:
        raise SystemExit(f"cannot import private reviewed sources: {error}") from error
    print(
        json.dumps(
            {
                "status": "private_reviewed_source_registry_created",
                "source_count": len(registry["sources"]),
                "trust_status": registry["trust_status"],
                "output": str(args.output),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
