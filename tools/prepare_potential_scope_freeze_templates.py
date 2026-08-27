"""Create a non-frozen PotentialScope template pack from an approved source registry."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from cosmatter.potential_scope_freeze_templates import (
    PotentialScopeFreezeTemplateError,
    build_freeze_template_pack,
    write_freeze_template_pack,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare a human-only PotentialScope freeze template pack.")
    parser.add_argument("--reviewed-source-registry", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        registry = json.loads(args.reviewed_source_registry.read_text(encoding="utf-8"))
        pack = build_freeze_template_pack(reviewed_source_registry=registry)
        output = write_freeze_template_pack(args.output, pack)
    except (OSError, json.JSONDecodeError, PotentialScopeFreezeTemplateError) as error:
        raise SystemExit(f"cannot prepare PotentialScope freeze templates: {error}") from error
    print(json.dumps({"status": "human_freeze_template_pack_created", "reviewed_source_count": pack["reviewed_source_count"], "output": str(output), "trust_status": pack["trust_status"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
