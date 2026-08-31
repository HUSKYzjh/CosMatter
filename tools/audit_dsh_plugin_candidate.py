"""Emit a secret-safe static hygiene report for one locally staged plugin."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from cosmatter.plugin_hygiene import PluginHygieneError, audit_plugin_candidate, validate_plugin_hygiene_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-dir", type=Path, required=True, help="explicit locally staged candidate directory; it is never installed or executed")
    args = parser.parse_args(argv)
    try:
        report = audit_plugin_candidate(args.candidate_dir.resolve())
        validate_plugin_hygiene_report(report)
    except PluginHygieneError as error:
        print(json.dumps({"admission_recommendation": "blocked_invalid_candidate", "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 2 if report["admission_recommendation"] == "blocked_high_risk" else 0


if __name__ == "__main__":
    raise SystemExit(main())
