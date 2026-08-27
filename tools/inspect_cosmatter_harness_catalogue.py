"""Print the static CosMatter plugin catalogue without reading configuration."""

from __future__ import annotations

import json

from cosmatter.harness_catalog import CosMatterHarnessCatalogue


if __name__ == "__main__":
    print(json.dumps({"plugins": CosMatterHarnessCatalogue().manifests()}, ensure_ascii=False, indent=2, sort_keys=True))
