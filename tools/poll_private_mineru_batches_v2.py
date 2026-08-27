#!/usr/bin/env python3
"""Poll MinerU batch states without retrieving PDF or Markdown data."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import UTC, datetime
from pathlib import Path


SOURCE = Path(__file__).with_name("mineru_v4_private_batch.py")
SPEC = importlib.util.spec_from_file_location("cosmatter_mineru_v4_batch_poll_v2", SOURCE)
if SPEC is None or SPEC.loader is None:
    raise SystemExit("Cannot load private MinerU batch implementation")
batch = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = batch
SPEC.loader.exec_module(batch)


def timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", action="append", type=Path, required=True)
    args = parser.parse_args()
    settings = batch.Settings.load()
    totals: dict[str, int] = {}
    for argument_path in args.manifest:
        manifest_path = argument_path.resolve()
        value = json.loads(manifest_path.read_text(encoding="utf-8"))
        batch_id = value.get("batch_id")
        records = value.get("files")
        if not isinstance(batch_id, str) or not isinstance(records, list):
            raise SystemExit(f"invalid private manifest: {manifest_path.name}")
        data = batch.api_json(settings, "GET", f"/api/v4/extract-results/batch/{batch_id}")
        results = data.get("extract_result")
        by_id = {str(item.get("data_id")): item for item in results if isinstance(item, dict) and isinstance(item.get("data_id"), str)} if isinstance(results, list) else {}
        for record in records:
            if not isinstance(record, dict):
                continue
            result = by_id.get(str(record.get("data_id")))
            if isinstance(result, dict) and isinstance(result.get("state"), str):
                record["provider_state"] = result["state"]
            state = str(record.get("provider_state", "unknown"))
            totals[state] = totals.get(state, 0) + 1
        value["updated_at"] = timestamp()
        batch.write_json(manifest_path, value)
    print(json.dumps({"batches_polled": len(args.manifest), "provider_states": dict(sorted(totals.items()))}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
