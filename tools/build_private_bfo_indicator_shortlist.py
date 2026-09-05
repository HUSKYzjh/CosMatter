#!/usr/bin/env python3
"""Create a bounded private BFO indicator shortlist from MinerU review pools."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from cosmatter.material_indicator_triage import MaterialIndicatorTriageError, build_private_indicator_shortlist


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _outside_project(path: Path) -> Path:
    resolved = path.resolve()
    if resolved == PROJECT_ROOT or PROJECT_ROOT in resolved.parents:
        raise MaterialIndicatorTriageError("private shortlist inputs and output must remain outside the repository")
    if "runs" in {part.casefold() for part in resolved.parts}:
        raise MaterialIndicatorTriageError("private shortlist inputs and output must remain outside a runs directory")
    return resolved


def _read_json(path: Path, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise MaterialIndicatorTriageError(f"{label} is not valid UTF-8 JSON") from error


def build(*, matrix_path: Path, review_index_path: Path, output_path: Path) -> dict[str, Any]:
    matrix_resolved = matrix_path.resolve()
    if matrix_resolved != PROJECT_ROOT / "configs" / "bfo_p0_source_candidate_matrix.json":
        raise MaterialIndicatorTriageError("BFO shortlist requires the versioned repository source matrix")
    index_resolved = _outside_project(review_index_path)
    output_resolved = _outside_project(output_path)
    if output_resolved.suffix.casefold() != ".json":
        raise MaterialIndicatorTriageError("private shortlist output must use a .json filename")
    if output_resolved.exists():
        raise MaterialIndicatorTriageError("private shortlist output already exists and will not be overwritten")
    index = _read_json(index_resolved, "private review index")
    pool_root = index_resolved.parent
    pools: dict[str, object] = {}
    for entry in index.get("entries", []) if isinstance(index, dict) else []:
        if not isinstance(entry, dict) or not isinstance(entry.get("pool_filename"), str):
            raise MaterialIndicatorTriageError("private review index pool filename is invalid")
        relative = Path(entry["pool_filename"])
        if relative.is_absolute() or ".." in relative.parts or relative.suffix.casefold() != ".json":
            raise MaterialIndicatorTriageError("private review index contains an unsafe pool filename")
        pool_path = (pool_root / relative).resolve()
        if pool_path.parent != pool_root:
            raise MaterialIndicatorTriageError("private review pool escapes its indexed directory")
        document_id = entry.get("document_id")
        if not isinstance(document_id, str) or document_id in pools:
            raise MaterialIndicatorTriageError("private review index document IDs are invalid or duplicated")
        pools[document_id] = _read_json(pool_path, "private review pool")
    result = build_private_indicator_shortlist(
        matrix=_read_json(matrix_resolved, "BFO source matrix"),
        review_index=index,
        pools_by_document=pools,
    )
    try:
        output_resolved.parent.mkdir(parents=True, exist_ok=True)
        output_resolved.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except OSError as error:
        raise MaterialIndicatorTriageError("private shortlist output cannot be written") from error
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", type=Path, default=PROJECT_ROOT / "configs" / "bfo_p0_source_candidate_matrix.json")
    parser.add_argument("--review-index", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = build(matrix_path=args.matrix, review_index_path=args.review_index, output_path=args.output)
    except MaterialIndicatorTriageError as error:
        parser.error(str(error))
    print(
        json.dumps(
            {
                "status": "private_unreviewed_indicator_shortlist_created",
                "document_count": result["document_count"],
                "segment_count": result["segment_count"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
