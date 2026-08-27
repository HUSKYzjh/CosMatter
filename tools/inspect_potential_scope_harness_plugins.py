"""List static PotentialScope harness plugins without starting a provider or executor."""

from __future__ import annotations

import json

from cosmatter.potential_scope_harness_plugins import PotentialScopeHarness


def main() -> int:
    print(json.dumps({"plugin_api_version": "1.0", "plugins": PotentialScopeHarness().manifests()}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
