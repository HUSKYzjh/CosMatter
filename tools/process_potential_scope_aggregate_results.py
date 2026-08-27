"""Validate external aggregate summaries and derive a review-gated applicability map.

The tool never contacts a runner or provider.  Inputs must already be safe JSON
artifacts; it rejects private-looking output locations and never overwrites.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from cosmatter.potential_scope_result_analysis import (
    PotentialScopeResultAnalysisError,
    build_applicability_map,
    build_applicability_policy,
    draft_boundary_claim_candidates,
    import_aggregate_result_rows,
)


def _read(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, payload: object) -> None:
    if path.exists() or path.suffix.casefold() != ".json" or any(part.casefold() in {"runs", "private", "03_paper"} for part in path.parts):
        raise PotentialScopeResultAnalysisError("outputs must be new JSON files outside run and private directories")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Derive review-gated PotentialScope applicability artifacts from external aggregate rows.")
    parser.add_argument("--campaign", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--rows", type=Path, required=True)
    parser.add_argument("--applicability-policy", type=Path, required=True)
    parser.add_argument("--import-output", type=Path, required=True)
    parser.add_argument("--map-output", type=Path, required=True)
    parser.add_argument("--candidates-output", type=Path, required=True)
    args = parser.parse_args()
    try:
        campaign = _read(args.campaign)
        receipt = _read(args.receipt)
        rows = _read(args.rows)
        imported = import_aggregate_result_rows(campaign=campaign, receipt=receipt, rows=rows)
        policy = build_applicability_policy(imported_results=imported, payload=_read(args.applicability_policy))
        app_map = build_applicability_map(campaign=campaign, imported_results=imported, applicability_policy=policy)
        candidates = draft_boundary_claim_candidates(applicability_map=app_map)
        for path, payload in ((args.import_output, imported), (args.map_output, app_map), (args.candidates_output, candidates)):
            _write(path, payload)
    except (OSError, json.JSONDecodeError, PotentialScopeResultAnalysisError) as error:
        raise SystemExit(f"PotentialScope aggregate result processing was not completed: {error}") from error
    print(json.dumps({"execution_permitted": False, "boundary_claims_accepted": False, "candidate_count": len(candidates["candidates"])}, ensure_ascii=False))
