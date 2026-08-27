"""Compose a frozen PotentialScope campaign without accessing private source content."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from cosmatter.potential_scope_campaign_runner import (
    PotentialScopeCampaignRunnerError,
    build_plan_only_campaign,
    write_plan_only_campaign,
)


def _read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build a safe, non-executing PotentialScope campaign package.")
    parser.add_argument("--machine", type=Path, required=True)
    parser.add_argument("--reviewed-source-registry", type=Path, required=True)
    parser.add_argument("--system-spec", type=Path, required=True)
    parser.add_argument("--passports", type=Path, required=True)
    parser.add_argument("--condition-matrix", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        campaign = build_plan_only_campaign(
            machine=_read_json(args.machine),
            reviewed_source_registry=_read_json(args.reviewed_source_registry),
            system_spec=_read_json(args.system_spec),
            passports=_read_json(args.passports),
            condition_matrix=_read_json(args.condition_matrix),
        )
        write_plan_only_campaign(args.output, campaign)
    except (OSError, json.JSONDecodeError, PotentialScopeCampaignRunnerError) as error:
        raise SystemExit(f"PotentialScope plan-only campaign was not created: {error}") from error
    print(json.dumps({"campaign_state": campaign["campaign_state"], "execution_permitted": False, "output": str(args.output)}, ensure_ascii=False))
