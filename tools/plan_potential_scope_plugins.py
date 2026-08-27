"""Validate human-frozen PotentialScope JSON and write proposed TestCards only.

All inputs and the output must stay outside ``CosMatter/runs``.  This local
command has no provider adapter, scheduler adapter, subprocess invocation or
model loader; it is only the audited planning boundary.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from cosmatter.potential_scope_frozen_plan import (
    PotentialScopeFrozenPlanError,
    build_frozen_plugin_plan,
    write_frozen_plugin_plan,
)


def _load(path: Path, label: str) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PotentialScopeFrozenPlanError(f"cannot read {label} JSON") from error


def _outside_runs(path: Path) -> bool:
    return "runs" not in {part.casefold() for part in path.parts}


def main() -> int:
    parser = argparse.ArgumentParser(description="Create an audited, non-executable PotentialScope plugin plan.")
    parser.add_argument("--machine", required=True, type=Path)
    parser.add_argument("--system-spec", required=True, type=Path)
    parser.add_argument("--passport", required=True, action="append", type=Path, help="repeat exactly once for each model")
    parser.add_argument("--condition-matrix", required=True, type=Path)
    parser.add_argument("--reviewed-source-registry", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    paths = [args.machine, args.system_spec, *args.passport, args.condition_matrix, args.reviewed_source_registry, args.output]
    if not all(_outside_runs(path) for path in paths):
        raise SystemExit("PotentialScope frozen planning inputs and output must remain outside CosMatter/runs")
    if args.output.exists():
        raise SystemExit("output already exists; refusing to overwrite a frozen planning artifact")
    try:
        plan = build_frozen_plugin_plan(
            machine=_load(args.machine, "machine configuration"),
            system_spec=_load(args.system_spec, "SystemSpec"),
            passports=[_load(path, "PotentialPassport") for path in args.passport],
            condition_matrix=_load(args.condition_matrix, "ConditionMatrix"),
            reviewed_source_registry=_load(args.reviewed_source_registry, "reviewed source registry"),
        )
        write_frozen_plugin_plan(args.output, plan)
    except PotentialScopeFrozenPlanError as error:
        raise SystemExit(f"cannot create frozen PotentialScope plan: {error}") from error
    print(
        json.dumps(
            {
                "status": "frozen_plugin_plan_created",
                "test_card_count": len(plan["proposal"]["proposed_test_cards"]),
                "skipped_plugin_count": len(plan["proposal"]["skipped_plugins"]),
                "execution_mode": plan["machine_execution_mode"],
                "output": str(args.output),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
