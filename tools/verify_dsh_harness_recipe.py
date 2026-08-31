"""Run the versioned, keyless CosMatter DSH Harness recipe."""

from __future__ import annotations

import json
import platform
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import Any
import argparse


ROOT = Path(__file__).resolve().parents[1]
_RECIPE_FIELDS = {"schema_version", "recipe_id", "trust_status", "compatibility_matrix", "fixture", "expected_workspace", "required_checks", "quality_boundary", "latency_boundary", "safety_boundary", "known_limitations"}


class HarnessRecipeError(ValueError):
    pass


def run_recipe(recipe_path: Path = ROOT / "configs" / "dsh_harness_recipe.json") -> dict[str, Any]:
    recipe = _load_recipe(recipe_path)
    checks: list[dict[str, object]] = []
    commands = {
        "release_matrix": [sys.executable, str(ROOT / "tools" / "verify_dsh_plugin_release.py")],
        "market_snapshot_review": [sys.executable, str(ROOT / "tools" / "verify_dsh_market_snapshot_review.py")],
        "third_party_admission": [sys.executable, str(ROOT / "tools" / "verify_dsh_plugin_admission.py")],
        "synthetic_replay": [sys.executable, str(ROOT / "tools" / "verify_dsh_synthetic_replay.py"), "--session", str(ROOT / recipe["fixture"]), "--expected", str(ROOT / recipe["expected_workspace"])],
    }
    for name in recipe["required_checks"]:
        start = time.monotonic()
        completed = subprocess.run(commands[name], cwd=ROOT, text=True, encoding="utf-8", capture_output=True, timeout=60, check=False, env={**__import__("os").environ, "PYTHONPATH": ""})
        checks.append({"name": name, "passed": completed.returncode == 0, "elapsed_ms": int((time.monotonic() - start) * 1000)})
        if completed.returncode:
            raise HarnessRecipeError(f"harness recipe check failed: {name}")
    report = {
        "schema_version": "1.0",
        "recipe_id": recipe["recipe_id"],
        "trust_status": "synthetic_harness_recipe_result_not_scientific_evidence_or_provider_benchmark",
        "passed": True,
        "environment": {
            "os": platform.system(),
            "python": platform.python_version(),
            "node": _version("node"),
            "dsh": _version("dsh"),
        },
        "checks": checks,
        "quality": "not_measured_synthetic_workflow_assertions_only",
        "latency_boundary": recipe["latency_boundary"],
        "safety_boundary": recipe["safety_boundary"],
        "known_limitations": recipe["known_limitations"],
    }
    _validate_report(report)
    return report


def _load_recipe(path: Path) -> dict[str, Any]:
    try:
        recipe = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise HarnessRecipeError("harness recipe cannot be read") from error
    if not isinstance(recipe, dict) or set(recipe) != _RECIPE_FIELDS or recipe.get("schema_version") != "1.0" or recipe.get("trust_status") != "synthetic_harness_recipe_not_scientific_evidence_or_provider_benchmark" or not isinstance(recipe.get("recipe_id"), str) or not recipe["recipe_id"].strip() or not isinstance(recipe.get("required_checks"), list) or recipe["required_checks"] != ["release_matrix", "market_snapshot_review", "third_party_admission", "synthetic_replay"] or not isinstance(recipe.get("known_limitations"), list) or not all(isinstance(item, str) and item.strip() for item in recipe["known_limitations"]):
        raise HarnessRecipeError("harness recipe fields are invalid")
    for key in ("compatibility_matrix", "fixture", "expected_workspace"):
        value = recipe.get(key)
        if not isinstance(value, str) or not value or Path(value).is_absolute() or ".." in Path(value).parts or not (ROOT / value).is_file():
            raise HarnessRecipeError("harness recipe path is invalid")
    for key in ("quality_boundary", "latency_boundary", "safety_boundary"):
        if not isinstance(recipe.get(key), str) or not recipe[key].strip():
            raise HarnessRecipeError("harness recipe boundary is invalid")
    return recipe


def _version(command: str) -> str:
    executable = shutil.which(command)
    if executable is None:
        raise HarnessRecipeError(f"required recipe executable is unavailable: {command}")
    completed = subprocess.run([executable, "--version"], cwd=ROOT, text=True, encoding="utf-8", capture_output=True, timeout=15, check=False)
    if completed.returncode or not completed.stdout.strip():
        raise HarnessRecipeError(f"cannot determine {command} version")
    return completed.stdout.strip().lstrip("v")


def _validate_report(report: object) -> None:
    expected = {"schema_version", "recipe_id", "trust_status", "passed", "environment", "checks", "quality", "latency_boundary", "safety_boundary", "known_limitations"}
    if not isinstance(report, dict) or set(report) != expected or report.get("schema_version") != "1.0" or report.get("trust_status") != "synthetic_harness_recipe_result_not_scientific_evidence_or_provider_benchmark" or report.get("passed") is not True or not isinstance(report.get("environment"), dict) or set(report["environment"]) != {"os", "python", "node", "dsh"} or not all(isinstance(value, str) and value for value in report["environment"].values()) or not isinstance(report.get("checks"), list) or not report["checks"]:
        raise HarnessRecipeError("harness recipe report is invalid")
    for check in report["checks"]:
        if not isinstance(check, dict) or set(check) != {"name", "passed", "elapsed_ms"} or check.get("name") not in {"release_matrix", "market_snapshot_review", "third_party_admission", "synthetic_replay"} or check.get("passed") is not True or not isinstance(check.get("elapsed_ms"), int) or check["elapsed_ms"] < 0:
            raise HarnessRecipeError("harness recipe report check is invalid")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recipe", type=Path, default=ROOT / "configs" / "dsh_harness_recipe.json")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(run_recipe(args.recipe), ensure_ascii=False, sort_keys=True))
    except (HarnessRecipeError, subprocess.TimeoutExpired) as error:
        print(json.dumps({"passed": False, "error": str(error)}, ensure_ascii=False))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
