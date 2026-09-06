#!/usr/bin/env python3
"""Create a bounded private BFO indicator shortlist from MinerU review pools."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from cosmatter.material_indicator_triage import MaterialIndicatorTriageError, build_private_indicator_shortlist
from cosmatter.mineru_local_review import MinerULocalReviewError, all_markdown_candidate_segments

try:
    from tools.prepare_private_mineru_review_pools import load_verified_markdown_entries
except ModuleNotFoundError as error:  # direct ``python tools/<script>.py`` execution
    if error.name != "tools":
        raise
    from prepare_private_mineru_review_pools import load_verified_markdown_entries


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SUPPORTED_MATRIX_PATHS = frozenset(
    PROJECT_ROOT / "configs" / name
    for name in (
        "bfo_p0_source_candidate_matrix.json",
        "bfo_expanded_source_candidate_matrix_v2.json",
        "bfo_magnetic_optical_process_source_candidate_matrix_v2.json",
        "bfo_magnetic_pv_process_source_candidate_matrix_v2.json",
    )
)


def _supported_matrix(path: Path) -> Path:
    resolved = path.resolve()
    if resolved not in SUPPORTED_MATRIX_PATHS:
        raise MaterialIndicatorTriageError("BFO shortlist requires a supported versioned repository source matrix")
    return resolved


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
    matrix_resolved = _supported_matrix(matrix_path)
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


def build_from_manifest(
    *, matrix_path: Path, manifest_path: Path, markdown_root: Path, output_path: Path,
) -> dict[str, Any]:
    """Rank indicator candidates across every verified Markdown segment."""
    matrix_resolved = _supported_matrix(matrix_path)
    manifest_resolved = _outside_project(manifest_path)
    markdown_resolved = _outside_project(markdown_root)
    output_resolved = _outside_project(output_path)
    if output_resolved.suffix.casefold() != ".json" or output_resolved.exists():
        raise MaterialIndicatorTriageError("private shortlist output must be a new .json file")
    try:
        entries = load_verified_markdown_entries(manifest_resolved, markdown_resolved)
    except (OSError, ValueError) as error:
        raise MaterialIndicatorTriageError("private Markdown manifest or content failed hash verification") from error
    pools: dict[str, object] = {}
    index_entries: list[dict[str, str]] = []
    for entry in entries:
        markdown_path = (markdown_resolved / entry["markdown_relative_path"]).resolve()
        try:
            content = markdown_path.read_text(encoding="utf-8")
            segments = all_markdown_candidate_segments(content)
        except (OSError, UnicodeDecodeError, MinerULocalReviewError) as error:
            raise MaterialIndicatorTriageError("verified private Markdown cannot be segmented safely") from error
        pools[entry["document_id"]] = {
            "document_id": entry["document_id"],
            "trust_status": "private_unreviewed_mineru_markdown_candidate_pool_not_source_map",
            "source_markdown_sha256": entry["markdown_sha256"],
            "candidate_segments": segments,
        }
        index_entries.append(
            {"document_id": entry["document_id"], "markdown_sha256": entry["markdown_sha256"]}
        )
    review_index = {
        "mission_id": "bfo_p0_full_markdown_indicator_triage",
        "trust_status": "private_unreviewed_mineru_manifest_review_index_not_evidence",
        "entries": index_entries,
    }
    result = build_private_indicator_shortlist(
        matrix=_read_json(matrix_resolved, "BFO source matrix"),
        review_index=review_index,
        pools_by_document=pools,
    )
    result["selection_method"] = "deterministic_full_markdown_indicator_numeric_condition_ranking_v2"
    try:
        output_resolved.parent.mkdir(parents=True, exist_ok=True)
        output_resolved.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except OSError as error:
        raise MaterialIndicatorTriageError("private shortlist output cannot be written") from error
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", type=Path, default=PROJECT_ROOT / "configs" / "bfo_p0_source_candidate_matrix.json")
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--review-index", type=Path)
    inputs.add_argument("--manifest", type=Path, help="verified private Markdown manifest for full-text ranking")
    parser.add_argument("--markdown-root", type=Path, help="private Markdown root; required with --manifest")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.manifest is not None:
            if args.markdown_root is None:
                raise MaterialIndicatorTriageError("--markdown-root is required with --manifest")
            result = build_from_manifest(
                matrix_path=args.matrix,
                manifest_path=args.manifest,
                markdown_root=args.markdown_root,
                output_path=args.output,
            )
        else:
            if args.markdown_root is not None:
                raise MaterialIndicatorTriageError("--markdown-root is only valid with --manifest")
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
