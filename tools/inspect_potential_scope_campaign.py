"""Inspect PotentialScope campaign readiness without exposing artifact contents."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from cosmatter.potential_scope_campaign_preflight import inspect_campaign


def _load(path: Path | None) -> object | None:
    if path is None:
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"cannot read supplied JSON artifact: {error}") from error


def main() -> int:
    parser = argparse.ArgumentParser(description="Print a quote-free PotentialScope plan-only campaign preflight.")
    parser.add_argument("--machine", type=Path)
    parser.add_argument("--reviewed-source-registry", type=Path)
    parser.add_argument("--system-spec", type=Path)
    parser.add_argument("--passports", type=Path, help="JSON array of reviewed PotentialPassports")
    parser.add_argument("--condition-matrix", type=Path)
    args = parser.parse_args()
    report = inspect_campaign(
        machine=_load(args.machine),
        reviewed_source_registry=_load(args.reviewed_source_registry),
        system_spec=_load(args.system_spec),
        passports=_load(args.passports),
        condition_matrix=_load(args.condition_matrix),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["ready_for_plan_only_proposal"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
