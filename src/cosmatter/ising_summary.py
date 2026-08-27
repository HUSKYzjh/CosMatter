"""Safe, report-ready summary for one executed finite Ising benchmark.

The summary is deliberately smaller than the raw local result: it retains only
aggregate metrics, plan binding and a measurement boundary.  It never accepts
or exposes trajectories, spin configurations, private paths or host identity.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from .ising_benchmark import IsingBenchmarkError, _sha256, build_ising_benchmark_plan


SCHEMA_VERSION = "1.0"


class IsingSummaryError(ValueError):
    """Raised when an executed finite-Ising result is not safe to summarize."""


def ising_benchmark_summary(*, plan: object, result: object, followups: object | None = None) -> dict[str, Any]:
    _validate_plan(plan)
    assert isinstance(plan, dict)
    _validate_result(result, plan)
    assert isinstance(result, dict)
    normalized_followups = _validate_followups(followups, plan) if followups is not None else None
    return {
        "schema_version": SCHEMA_VERSION,
        "trust_status": "aggregate_executed_finite_classical_ising_benchmark_scope_limited",
        "plan_sha256": _sha256(plan),
        "model": result["model"],
        "lattice_size": result["lattice_size"],
        "temperatures": list(result["temperatures"]),
        "seed": result["seed"],
        "repetitions": result["repetitions"],
        "algorithms": list(plan["algorithms"]),
        "metrics": [
            {
                "temperature": row["temperature"],
                "algorithm": row["algorithm"],
                "replicate_count": row["replicate_count"],
                "integrated_autocorrelation_time_sweeps": row["integrated_autocorrelation_time_sweeps"],
                "autocorrelation_time_standard_deviation": row["autocorrelation_time_standard_deviation"],
                "effective_samples_per_second": row["effective_samples_per_second"],
                "wall_time_seconds": row["wall_time_seconds"],
                "wall_time_standard_deviation_seconds": row["wall_time_standard_deviation_seconds"],
                "relative_to_metropolis": dict(row["relative_to_metropolis"]),
            }
            for row in result["algorithm_metrics"]
        ],
        "measurement_environment": dict(result["measurement_environment"]),
        "followup_proposal": normalized_followups,
        "interpretation_boundary": result["interpretation_boundary"],
    }


def write_ising_benchmark_summary(run_dir: Path, payload: dict[str, Any]) -> Path:
    if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
        raise IsingSummaryError("Ising benchmark summary schema is invalid")
    path = run_dir / "ising_benchmark_summary.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _validate_plan(plan: object) -> None:
    if not isinstance(plan, dict):
        raise IsingSummaryError("Ising benchmark plan must be an object")
    try:
        rebuilt = build_ising_benchmark_plan(
            lattice_size=plan.get("lattice_size"),
            temperatures=tuple(plan.get("temperatures", ())),
            burn_in_sweeps=plan.get("burn_in_sweeps"),
            measurement_sweeps=plan.get("measurement_sweeps"),
            seed=plan.get("seed"), repetitions=plan.get("repetitions", 1),
            algorithms=tuple(plan.get("algorithms", ())),
        )
    except IsingBenchmarkError as error:
        raise IsingSummaryError(str(error)) from error
    if plan != rebuilt:
        raise IsingSummaryError("Ising benchmark plan is not canonical")


def _validate_result(result: object, plan: dict[str, Any]) -> None:
    if not isinstance(result, dict) or result.get("schema_version") != SCHEMA_VERSION:
        raise IsingSummaryError("Ising benchmark result schema is invalid")
    required = {
        "schema_version", "trust_status", "plan_sha256", "model", "lattice_size", "temperatures", "seed", "repetitions",
        "algorithm_metrics", "replicate_metrics", "measurement_environment", "interpretation_boundary",
    }
    if set(result) != required or result.get("trust_status") != "executed_seeded_classical_ising_benchmark_requires_scope_limited_interpretation":
        raise IsingSummaryError("Ising benchmark result fields or trust status are invalid")
    if result.get("plan_sha256") != _sha256(plan):
        raise IsingSummaryError("Ising benchmark result does not match its plan")
    if result.get("model") != "two_dimensional_zero_field_nearest_neighbor_ising" or any(
        result.get(key) != plan[key] for key in ("lattice_size", "temperatures", "seed", "repetitions")
    ):
        raise IsingSummaryError("Ising benchmark result identity does not match its plan")
    rows = result.get("algorithm_metrics")
    if not isinstance(rows, list) or len(rows) != len(plan["temperatures"]) * len(plan["algorithms"]):
        raise IsingSummaryError("Ising benchmark aggregate metrics are incomplete")
    expected_pairs = {(float(temp), algorithm) for temp in plan["temperatures"] for algorithm in plan["algorithms"]}
    seen: set[tuple[float, str]] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise IsingSummaryError("Ising aggregate metric row is invalid")
        pair = (row.get("temperature"), row.get("algorithm"))
        if pair not in expected_pairs or pair in seen or row.get("replicate_count") != plan["repetitions"]:
            raise IsingSummaryError("Ising aggregate metric identity is invalid")
        seen.add(pair)
        for key in ("integrated_autocorrelation_time_sweeps", "autocorrelation_time_standard_deviation", "effective_samples_per_second", "wall_time_seconds", "wall_time_standard_deviation_seconds"):
            value = row.get(key)
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(float(value)) or float(value) < 0:
                raise IsingSummaryError("Ising aggregate metric numeric value is invalid")
        baseline = row.get("relative_to_metropolis")
        if not isinstance(baseline, dict) or set(baseline) != {"autocorrelation_time_ratio", "effective_samples_per_second_ratio"}:
            raise IsingSummaryError("Ising aggregate metric baseline comparison is invalid")
        if not all(isinstance(value, (int, float)) and math.isfinite(float(value)) and float(value) > 0 for value in baseline.values()):
            raise IsingSummaryError("Ising aggregate metric baseline values are invalid")
    if seen != expected_pairs:
        raise IsingSummaryError("Ising aggregate metric pairs are incomplete")
    environment = result.get("measurement_environment")
    expected_environment = {"runtime", "operating_system", "machine_architecture", "logical_cpu_count", "parallelism", "numerical_precision", "timing_scope"}
    if not isinstance(environment, dict) or set(environment) != expected_environment or not isinstance(environment.get("logical_cpu_count"), int):
        raise IsingSummaryError("Ising measurement environment is invalid")
    if not all(isinstance(environment.get(key), str) and environment[key].strip() for key in expected_environment - {"logical_cpu_count"}):
        raise IsingSummaryError("Ising measurement environment text is invalid")


def _validate_followups(followups: object, plan: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(followups, dict) or followups.get("schema_version") != SCHEMA_VERSION:
        raise IsingSummaryError("Ising followup proposal schema is invalid")
    required = {"schema_version", "trust_status", "plan_sha256", "trigger", "proposed_refinement", "interpretation_boundary"}
    if set(followups) != required or followups.get("trust_status") != "classical_mc_followup_suggestion_requires_human_approval_not_run" or followups.get("plan_sha256") != _sha256(plan):
        raise IsingSummaryError("Ising followup proposal is invalid")
    refinement = followups.get("proposed_refinement")
    if not isinstance(refinement, dict) or refinement.get("approval_required") is not True:
        raise IsingSummaryError("Ising followup proposal must remain approval required")
    return {
        "trigger": dict(followups["trigger"]),
        "proposed_refinement": {
            "temperatures": list(refinement.get("temperatures", [])),
            "lattice_sizes": list(refinement.get("lattice_sizes", [])),
            "measurement_sweeps": refinement.get("measurement_sweeps"),
            "approval_required": True,
        },
        "interpretation_boundary": followups["interpretation_boundary"],
    }
