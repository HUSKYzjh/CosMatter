"""Framework-only, reproducible potential comparison and boundary exploration.

This module deliberately prepares test tasks and evaluates result files already
produced by an approved external calculator.  It does not train a potential,
launch DFT/MD jobs, or manufacture physical measurements.  It supports the
revised track's advanced-route requirement for quantitative comparison against
declared baselines while keeping all scientific claims result-bound.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any


POTENTIAL_BENCHMARK_SCHEMA_VERSION = "1.1"


class PotentialBenchmarkError(ValueError):
    """Raised when a benchmark plan or external result is invalid."""


@dataclass(frozen=True)
class PotentialTestTask:
    task_id: str
    regime: str
    purpose: str
    controls: dict[str, float]
    expected_boundary: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "regime": self.regime,
            "purpose": self.purpose,
            "controls": self.controls,
            "expected_boundary": self.expected_boundary,
        }


def generate_potential_boundary_plan(
    *,
    system_label: str,
    potential_models: tuple[str, ...],
    reference_method: str,
    baseline_model_id: str | None = None,
    seed: int,
    controls: dict[str, tuple[float, float]],
    samples_per_regime: int = 3,
) -> dict[str, Any]:
    """Generate deterministic in-domain, boundary, and OOD task packets.

    ``controls`` may contain any declared scalar coordinates, e.g. temperature,
    strain_percent, pressure_gpa, or defect_fraction.  The function creates no
    structures; an external adapter must translate task controls into approved
    input files.
    """
    if not system_label.strip() or not reference_method.strip() or len(set(potential_models)) < 2:
        raise PotentialBenchmarkError("system, reference method, and at least two unique potential models are required")
    if not isinstance(seed, int) or not 0 <= seed <= 2**32 - 1:
        raise PotentialBenchmarkError("seed must be an unsigned 32-bit integer")
    if not isinstance(samples_per_regime, int) or not 1 <= samples_per_regime <= 32:
        raise PotentialBenchmarkError("samples per regime must be an integer from 1 through 32")
    baseline_model_id = baseline_model_id or potential_models[0]
    if baseline_model_id not in potential_models:
        raise PotentialBenchmarkError("baseline potential model must be one of the declared potential models")
    normalized_controls = _controls(controls)
    task_rows: list[PotentialTestTask] = []
    for regime in ("in_domain", "near_boundary", "out_of_domain"):
        for sample_index in range(1, samples_per_regime + 1):
            values = {
                name: _select_coordinate(lower, upper, regime, seed, sample_index, name)
                for name, (lower, upper) in normalized_controls.items()
            }
            task_rows.append(PotentialTestTask(
                task_id=f"potential_{regime}_{sample_index:02d}", regime=regime,
                purpose={
                    "in_domain": "Measure interpolation fidelity inside the declared training envelope.",
                    "near_boundary": "Probe extrapolation close to the declared envelope boundary.",
                    "out_of_domain": "Expose failure modes beyond the declared training envelope; not a production prediction.",
                }[regime],
                controls=values,
                expected_boundary={
                    "in_domain": "within_declared_training_envelope",
                    "near_boundary": "adjacent_to_declared_training_envelope",
                    "out_of_domain": "outside_declared_training_envelope",
                }[regime],
            ))
    return {
        "schema_version": POTENTIAL_BENCHMARK_SCHEMA_VERSION,
        "trust_status": "framework_test_plan_not_executed_calculation",
        "system_label": system_label.strip(),
        "reference_method": reference_method.strip(),
        "potential_models": list(potential_models),
        "baseline_model_id": baseline_model_id,
        "seed": seed,
        "samples_per_regime": samples_per_regime,
        "declared_controls": {name: {"train_min": lower, "train_max": upper} for name, (lower, upper) in normalized_controls.items()},
        "tasks": [task.to_dict() for task in task_rows],
        "required_result_fields": ["task_id", "model_id", "atom_count", "reference_energy_ev", "predicted_energy_ev", "force_rmse_ev_per_a", "wall_time_seconds"],
        "execution_boundary": "External calculators must be manually approved and run outside CosMatter before their result summary is imported.",
    }


def evaluate_potential_results(*, plan: dict[str, Any], results: list[dict[str, Any]], execution_protocol: dict[str, Any] | None = None) -> dict[str, Any]:
    """Compare imported numeric summaries, never execute a calculator itself."""
    _validate_plan(plan)
    protocol_summary = _execution_protocol_summary(plan, execution_protocol)
    models = set(plan["potential_models"])
    tasks = {task["task_id"]: task for task in plan["tasks"]}
    required_pairs = {(task_id, model_id) for task_id in tasks for model_id in models}
    observed: dict[tuple[str, str], dict[str, Any]] = {}
    for row in results:
        if not isinstance(row, dict):
            raise PotentialBenchmarkError("benchmark result entries must be objects")
        task_id, model_id = row.get("task_id"), row.get("model_id")
        if task_id not in tasks or model_id not in models:
            raise PotentialBenchmarkError("benchmark result references an unknown task or model")
        key = (task_id, model_id)
        if key in observed:
            raise PotentialBenchmarkError("benchmark result contains duplicate task/model rows")
        values = {field: row.get(field) for field in ("reference_energy_ev", "predicted_energy_ev", "force_rmse_ev_per_a", "wall_time_seconds")}
        if not all(isinstance(value, (int, float)) and math.isfinite(float(value)) for value in values.values()):
            raise PotentialBenchmarkError("benchmark result has missing or non-finite numeric fields")
        atom_count = row.get("atom_count")
        if not isinstance(atom_count, int) or isinstance(atom_count, bool) or atom_count < 1:
            raise PotentialBenchmarkError("benchmark result requires a positive integer atom_count")
        if float(values["wall_time_seconds"]) <= 0 or float(values["force_rmse_ev_per_a"]) < 0:
            raise PotentialBenchmarkError("benchmark elapsed time and force RMSE must be nonnegative with positive time")
        observed[key] = {**{name: float(value) for name, value in values.items()}, "atom_count": atom_count}
    if set(observed) != required_pairs:
        missing = sorted(f"{task_id}/{model_id}" for task_id, model_id in required_pairs - set(observed))
        raise PotentialBenchmarkError("benchmark result is incomplete: " + ", ".join(missing))
    references_by_task: dict[str, tuple[float, int]] = {}
    for (task_id, _model_id), row in observed.items():
        reference, atom_count = row["reference_energy_ev"], int(row["atom_count"])
        previous = references_by_task.get(task_id)
        if previous is not None and (
            previous[1] != atom_count
            or not math.isclose(previous[0], reference, rel_tol=0.0, abs_tol=1e-10)
        ):
            raise PotentialBenchmarkError(
                "benchmark rows for one task must share exactly one atom count and reference energy; "
                "re-run or correct the imported external summary before comparing models"
            )
        references_by_task[task_id] = (reference, atom_count)
    task_diagnostics: list[dict[str, Any]] = []
    for task_id, task in sorted(tasks.items()):
        baseline_row = observed[(task_id, plan["baseline_model_id"])]
        atom_count = int(baseline_row["atom_count"])
        baseline_error = abs(baseline_row["predicted_energy_ev"] - baseline_row["reference_energy_ev"])
        baseline_per_atom_error = baseline_error / atom_count
        for model_id in sorted(models):
            row = observed[(task_id, model_id)]
            error = abs(row["predicted_energy_ev"] - row["reference_energy_ev"])
            per_atom_error = error / atom_count
            task_diagnostics.append({
                "task_id": task_id,
                "model_id": model_id,
                "regime": task["regime"],
                "controls": dict(task["controls"]),
                "atom_count": atom_count,
                "absolute_energy_error_ev": error,
                "absolute_energy_error_ev_per_atom": per_atom_error,
                "force_rmse_ev_per_a": row["force_rmse_ev_per_a"],
                "wall_time_seconds": row["wall_time_seconds"],
                "relative_to_task_baseline": {
                    "baseline_model_id": plan["baseline_model_id"],
                    "wall_time_speedup_ratio": baseline_row["wall_time_seconds"] / row["wall_time_seconds"],
                    "energy_error_reduction_fraction_per_atom": None if baseline_per_atom_error == 0 else (baseline_per_atom_error - per_atom_error) / baseline_per_atom_error,
                },
            })
    summaries: list[dict[str, Any]] = []
    for model_id in sorted(models):
        rows = [(tasks[task_id], observed[(task_id, model_id)]) for task_id in tasks]
        energies = [abs(row["predicted_energy_ev"] - row["reference_energy_ev"]) for _, row in rows]
        energies_per_atom = [error / int(row["atom_count"]) for error, (_, row) in zip(energies, rows)]
        forces = [row["force_rmse_ev_per_a"] for _, row in rows]
        times = [row["wall_time_seconds"] for _, row in rows]
        by_regime = {
            regime: _regime_summary([(task, row) for task, row in rows if task["regime"] == regime])
            for regime in ("in_domain", "near_boundary", "out_of_domain")
        }
        summaries.append({
            "model_id": model_id,
            "mean_absolute_energy_error_ev": _mean(energies),
            "mean_absolute_energy_error_ev_per_atom": _mean(energies_per_atom),
            "mean_force_rmse_ev_per_a": _mean(forces),
            "mean_wall_time_seconds": _mean(times),
            "regime_metrics": by_regime,
            "boundary_warning": by_regime["out_of_domain"]["mean_absolute_energy_error_ev_per_atom"] > by_regime["in_domain"]["mean_absolute_energy_error_ev_per_atom"],
        })
    baseline_summary = next(item for item in summaries if item["model_id"] == plan["baseline_model_id"])
    baseline_time = baseline_summary["mean_wall_time_seconds"]
    baseline_energy_error = baseline_summary["mean_absolute_energy_error_ev_per_atom"]
    for summary in summaries:
        error = summary["mean_absolute_energy_error_ev_per_atom"]
        summary["relative_to_baseline"] = {
            "baseline_model_id": plan["baseline_model_id"],
            "wall_time_speedup_ratio": baseline_time / summary["mean_wall_time_seconds"],
            "energy_error_reduction_fraction_per_atom": None if baseline_energy_error == 0 else (baseline_energy_error - error) / baseline_energy_error,
        }
    return {
        "schema_version": POTENTIAL_BENCHMARK_SCHEMA_VERSION,
        "trust_status": "imported_external_result_comparison_requires_human_scientific_review",
        "plan_sha256": _canonical_sha256(plan),
        "system_label": plan["system_label"],
        "reference_method": plan["reference_method"],
        "baseline_model_id": plan["baseline_model_id"],
        "seed": plan["seed"],
        "model_summaries": summaries,
        "task_diagnostics": task_diagnostics,
        "shared_reference_value_and_atom_count_per_task": True,
        "comparability_boundary": "All rows use the imported plan's declared task coordinates, one shared atom count and reference energy per task, and the declared reference method. Model ranking uses energy error in eV/atom, force RMSE and same-task wall time. Numerical agreement does not prove transferability outside those coordinates.",
        **protocol_summary,
        "external_execution_confirmed_by_import_only": True,
    }


def _execution_protocol_summary(plan: dict[str, Any], protocol: dict[str, Any] | None) -> dict[str, Any]:
    """Bind imported external outcomes to an explicitly approved protocol when supplied."""
    if protocol is None:
        return {
            "execution_protocol_status": "not_recorded",
            "execution_protocol_sha256": None,
            "result_interpretation_boundary": "No execution protocol was supplied. This import is a numeric fixture or an unbound draft and cannot support a reproducibility claim.",
        }
    from .potential_protocol import build_potential_execution_protocol, potential_execution_protocol_sha256

    reviewed = build_potential_execution_protocol(plan=plan, payload=protocol)
    if reviewed["approval"]["status"] != "approved_for_external_execution":
        raise PotentialBenchmarkError("external benchmark results require an execution protocol approved for external execution")
    return {
        "execution_protocol_status": "approved_for_external_execution",
        "execution_protocol_sha256": potential_execution_protocol_sha256(reviewed),
        "result_interpretation_boundary": "Imported rows are bound to a reviewed protocol, but still require human scientific review before any transferability claim.",
    }


def write_potential_plan(run_dir: Path, plan: dict[str, Any]) -> Path:
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "potential_benchmark_plan.json"
    path.write_text(json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def write_potential_evaluation(run_dir: Path, report: dict[str, Any]) -> Path:
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "potential_benchmark_evaluation.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def propose_potential_followups(*, plan: dict[str, Any], evaluation: dict[str, Any]) -> dict[str, Any]:
    """Propose local, approval-required probes around a concrete observed weak point.

    The selector is deliberately lexicographic rather than an opaque mixed-unit
    score: highest absolute energy error per atom, then highest force RMSE, then largest
    local wall time.  All resulting tasks remain suggestions only.
    """
    _validate_plan(plan)
    if not isinstance(evaluation, dict) or evaluation.get("plan_sha256") != _canonical_sha256(plan):
        raise PotentialBenchmarkError("potential evaluation is not bound to the supplied benchmark plan")
    diagnostics = evaluation.get("task_diagnostics")
    if not isinstance(diagnostics, list) or not diagnostics:
        raise PotentialBenchmarkError("potential evaluation lacks task-level diagnostics")
    expected_pairs = {(task["task_id"], model_id) for task in plan["tasks"] for model_id in plan["potential_models"]}
    observed_pairs: set[tuple[str, str]] = set()
    for item in diagnostics:
        if not isinstance(item, dict):
            raise PotentialBenchmarkError("potential task diagnostic is invalid")
        task_id, model_id = item.get("task_id"), item.get("model_id")
        if (task_id, model_id) not in expected_pairs or (task_id, model_id) in observed_pairs:
            raise PotentialBenchmarkError("potential task diagnostics do not match the benchmark plan")
        observed_pairs.add((task_id, model_id))
        for key in ("absolute_energy_error_ev", "absolute_energy_error_ev_per_atom", "force_rmse_ev_per_a", "wall_time_seconds"):
            value = item.get(key)
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(float(value)) or float(value) < 0:
                raise PotentialBenchmarkError("potential task diagnostic numeric fields are invalid")
    if observed_pairs != expected_pairs:
        raise PotentialBenchmarkError("potential task diagnostics are incomplete")
    anchor = max(
        diagnostics,
        key=lambda item: (
            float(item["absolute_energy_error_ev_per_atom"]),
            float(item["force_rmse_ev_per_a"]),
            float(item["wall_time_seconds"]),
            str(item["task_id"]),
            str(item["model_id"]),
        ),
    )
    task_by_id = {task["task_id"]: task for task in plan["tasks"]}
    source_task = task_by_id[anchor["task_id"]]
    if anchor.get("regime") != source_task["regime"] or anchor.get("controls") != source_task["controls"]:
        raise PotentialBenchmarkError("potential task diagnostic coordinates do not match the benchmark plan")
    controls = plan["declared_controls"]
    followups = []
    for name, bounds in sorted(controls.items()):
        lower, upper = float(bounds["train_min"]), float(bounds["train_max"])
        anchor_value = float(source_task["controls"][name])
        probes = _local_probe_values(lower, upper, anchor_value, source_task["regime"])
        followups.append({
            "task_id": f"followup_{source_task['task_id']}_{name}",
            "target_model_id": anchor["model_id"],
            "anchor_task_id": source_task["task_id"],
            "trigger_regime": source_task["regime"],
            "anchor_controls": dict(source_task["controls"]),
            "trigger_absolute_energy_error_ev": float(anchor["absolute_energy_error_ev"]),
            "trigger_absolute_energy_error_ev_per_atom": float(anchor["absolute_energy_error_ev_per_atom"]),
            "trigger_force_rmse_ev_per_a": float(anchor["force_rmse_ev_per_a"]),
            "trigger_wall_time_seconds": float(anchor["wall_time_seconds"]),
            "selection_policy": "lexicographic_max_energy_error_per_atom_then_force_rmse_then_wall_time",
            "varied_control": name,
            "proposed_values": probes,
            "fixed_controls": {other: float(source_task["controls"][other]) for other in controls if other != name},
            "approval_required": True,
            "purpose": "Densify the locally observed weak coordinate before any claim about the potential applicability boundary.",
        })
    return {
        "schema_version": POTENTIAL_BENCHMARK_SCHEMA_VERSION,
        "trust_status": "followup_test_suggestions_require_human_approval_not_executed_calculations",
        "plan_sha256": _canonical_sha256(plan),
        "trigger": {
            "model_id": anchor["model_id"], "task_id": source_task["task_id"], "regime": source_task["regime"],
            "absolute_energy_error_ev": float(anchor["absolute_energy_error_ev"]),
            "absolute_energy_error_ev_per_atom": float(anchor["absolute_energy_error_ev_per_atom"]),
            "force_rmse_ev_per_a": float(anchor["force_rmse_ev_per_a"]),
            "wall_time_seconds": float(anchor["wall_time_seconds"]),
            "selection_policy": "lexicographic_max_energy_error_per_atom_then_force_rmse_then_wall_time",
        },
        "followup_tasks": followups,
        "execution_boundary": "Every proposed task requires an approved structure-generation and external-calculation protocol before execution.",
    }


def _local_probe_values(lower: float, upper: float, anchor: float, regime: str) -> list[float]:
    span = upper - lower
    step = 0.04 * span
    if regime == "in_domain":
        return sorted({round(min(max(value, lower + 0.01 * span), upper - 0.01 * span), 8) for value in (anchor - step, anchor, anchor + step)})
    if regime == "near_boundary":
        return sorted({round(value, 8) for value in (anchor - step, anchor, anchor + step)})
    if anchor < lower:
        return sorted({round(min(value, lower - 0.01 * span), 8) for value in (anchor - step, anchor, anchor + step)})
    return sorted({round(max(value, upper + 0.01 * span), 8) for value in (anchor - step, anchor, anchor + step)})

def write_potential_followups(run_dir: Path, payload: dict[str, Any]) -> Path:
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "potential_benchmark_followups.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path

def _controls(controls: dict[str, tuple[float, float]]) -> dict[str, tuple[float, float]]:
    if not isinstance(controls, dict) or not controls:
        raise PotentialBenchmarkError("at least one declared control range is required")
    result: dict[str, tuple[float, float]] = {}
    for name, values in controls.items():
        if not isinstance(name, str) or not name.strip() or not isinstance(values, tuple) or len(values) != 2:
            raise PotentialBenchmarkError("control ranges must be named numeric (min, max) tuples")
        lower, upper = values
        if not all(isinstance(value, (int, float)) and math.isfinite(float(value)) for value in values) or float(lower) >= float(upper):
            raise PotentialBenchmarkError("each control range must have finite min < max")
        result[name.strip()] = (float(lower), float(upper))
    return result


def _select_coordinate(lower: float, upper: float, regime: str, seed: int, index: int, name: str) -> float:
    span = upper - lower
    digest = int(hashlib.sha256(f"{seed}:{index}:{name}".encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
    if regime == "in_domain":
        return round(lower + span * (0.2 + 0.6 * digest), 8)
    if regime == "near_boundary":
        return round(lower + span * (0.02 if digest < 0.5 else 0.98), 8)
    direction = -1 if digest < 0.5 else 1
    return round((lower if direction < 0 else upper) + direction * span * (0.15 + 0.1 * digest), 8)


def _validate_plan(plan: object) -> None:
    if not isinstance(plan, dict) or plan.get("schema_version") != POTENTIAL_BENCHMARK_SCHEMA_VERSION:
        raise PotentialBenchmarkError("potential benchmark plan schema is invalid")
    if plan.get("trust_status") != "framework_test_plan_not_executed_calculation":
        raise PotentialBenchmarkError("potential benchmark plan trust status is invalid")
    samples = plan.get("samples_per_regime")
    if not isinstance(samples, int) or not 1 <= samples <= 32:
        raise PotentialBenchmarkError("potential benchmark plan samples per regime are invalid")
    tasks = plan.get("tasks")
    if not isinstance(plan.get("potential_models"), list) or len(plan["potential_models"]) < 2 or not isinstance(tasks, list) or len(tasks) != 3 * samples:
        raise PotentialBenchmarkError("potential benchmark plan is incomplete")
    for regime in ("in_domain", "near_boundary", "out_of_domain"):
        if sum(task.get("regime") == regime for task in tasks if isinstance(task, dict)) != samples:
            raise PotentialBenchmarkError("potential benchmark plan regime balance is invalid")
    if not isinstance(plan.get("baseline_model_id"), str) or plan["baseline_model_id"] not in plan["potential_models"]:
        raise PotentialBenchmarkError("potential benchmark plan baseline model is invalid")


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def _regime_summary(rows: list[tuple[dict[str, Any], dict[str, float]]]) -> dict[str, float]:
    if not rows:
        raise PotentialBenchmarkError("benchmark plan is missing a required regime")
    return {
        "mean_absolute_energy_error_ev": _mean([abs(row["predicted_energy_ev"] - row["reference_energy_ev"]) for _, row in rows]),
        "mean_absolute_energy_error_ev_per_atom": _mean([abs(row["predicted_energy_ev"] - row["reference_energy_ev"]) / int(row["atom_count"]) for _, row in rows]),
        "mean_force_rmse_ev_per_a": _mean([row["force_rmse_ev_per_a"] for _, row in rows]),
        "mean_wall_time_seconds": _mean([row["wall_time_seconds"] for _, row in rows]),
    }


def _canonical_sha256(payload: object) -> str:
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
