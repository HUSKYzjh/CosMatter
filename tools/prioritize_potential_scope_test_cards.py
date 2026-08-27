"""Create a non-executing, literature-bound PotentialScope TestCard queue."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from cosmatter.potential_scope_task_priority import PotentialScopeTaskPriorityError, prioritize_proposed_test_cards


def _load(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PotentialScopeTaskPriorityError("supplied frozen JSON artifact cannot be read") from error


def main() -> int:
    parser = argparse.ArgumentParser(description="Prioritize proposed PotentialScope cards without executing them.")
    parser.add_argument("--frozen-plan", required=True, type=Path)
    parser.add_argument("--system-spec", required=True, type=Path)
    parser.add_argument("--passports", required=True, type=Path)
    parser.add_argument("--condition-matrix", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists() or args.output.suffix.casefold() != ".json":
        raise SystemExit("output must be a new .json file; refusing to overwrite queue history")
    try:
        queue = prioritize_proposed_test_cards(
            frozen_plan=_load(args.frozen_plan),
            system_spec=_load(args.system_spec),
            passports=_load(args.passports),
            condition_matrix=_load(args.condition_matrix),
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(queue, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, PotentialScopeTaskPriorityError) as error:
        raise SystemExit(f"cannot create non-executing PotentialScope priority queue: {error}") from error
    print(json.dumps({"status": "nonexecuting_priority_queue_created", "proposed_card_count": len(queue["proposed_queue"]), "execution_permitted": False, "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
