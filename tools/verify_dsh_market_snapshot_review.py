"""Verify a redacted human review record for the checked-in market snapshot."""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cosmatter.market_snapshot_review import MarketSnapshotReviewError, verify_market_snapshot_review


def _load(name: str) -> dict[str, object]:
    try:
        value = json.loads((ROOT / "configs" / name).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise MarketSnapshotReviewError("market snapshot review configuration cannot be read") from error
    if not isinstance(value, dict):
        raise MarketSnapshotReviewError("market snapshot review configuration is invalid")
    return value


def main() -> int:
    try:
        result = verify_market_snapshot_review(
            baseline=_load("dsh_market_snapshot.baseline.json"),
            current=_load("dsh_market_snapshot.json"),
            review=_load("dsh_market_snapshot_review.json"),
        )
    except MarketSnapshotReviewError as error:
        print(json.dumps({"status": "blocked", "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({"status": "ok", **result}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
