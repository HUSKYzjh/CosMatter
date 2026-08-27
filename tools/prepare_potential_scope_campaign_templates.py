"""Prepare safe two-stage PotentialScope campaign completion templates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from cosmatter.potential_scope_campaign_templates import (
    PotentialScopeCampaignTemplateError,
    build_post_system_spec_completion_pack,
    build_registry_completion_pack,
    write_campaign_template_pack,
)


def _read(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create PotentialScope human-completion template packs.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--reviewed-source-registry", type=Path)
    group.add_argument("--system-spec", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        pack = build_registry_completion_pack(reviewed_source_registry=_read(args.reviewed_source_registry)) if args.reviewed_source_registry else build_post_system_spec_completion_pack(system_spec=_read(args.system_spec))
        write_campaign_template_pack(args.output, pack)
    except (OSError, json.JSONDecodeError, PotentialScopeCampaignTemplateError) as error:
        raise SystemExit(f"PotentialScope template pack was not created: {error}") from error
    print(json.dumps({"trust_status": pack["trust_status"], "execution_permitted": False, "output": str(args.output)}, ensure_ascii=False))
