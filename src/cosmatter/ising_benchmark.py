"""Small, reproducible classical Monte Carlo benchmark for route-B diagnostics.

The revised competition manual explicitly names classical Ising Monte Carlo as
an eligible Route-B direction and asks for quantitative comparison with
classical methods.  This module therefore implements a deliberately bounded
2-D zero-field Ising diagnostic, rather than presenting a planning fixture as
an experiment.  It is not a materials simulator and its measurements must not
be generalized to a potential model, a QMC method, or a physical material.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import random
import sys
import time
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "1.0"
SUPPORTED_ALGORITHMS = ("metropolis", "wolff", "swendsen_wang")


class IsingBenchmarkError(ValueError):
    """Raised when an Ising benchmark plan or result is invalid."""


def build_ising_benchmark_plan(
    *,
    lattice_size: int,
    temperatures: tuple[float, ...],
    burn_in_sweeps: int,
    measurement_sweeps: int,
    seed: int,
    repetitions: int = 3,
    algorithms: tuple[str, ...] = SUPPORTED_ALGORITHMS,
) -> dict[str, Any]:
    """Create a finite, seeded 2-D Ising benchmark plan.

    The plan pins the observable, update definition and compute boundary before
    a run.  It has no numerical metrics and is safe to include in a source-only
    preliminary submission.
    """
    if not isinstance(lattice_size, int) or not 8 <= lattice_size <= 128:
        raise IsingBenchmarkError("lattice size must be an integer between 8 and 128")
    if not isinstance(burn_in_sweeps, int) or not 0 <= burn_in_sweeps <= 2_000:
        raise IsingBenchmarkError("burn-in sweeps must be an integer between 0 and 2000")
    if not isinstance(measurement_sweeps, int) or not 16 <= measurement_sweeps <= 10_000:
        raise IsingBenchmarkError("measurement sweeps must be an integer between 16 and 10000")
    if not isinstance(seed, int) or not 0 <= seed <= 2**32 - 1:
        raise IsingBenchmarkError("seed must be an unsigned 32-bit integer")
    if not isinstance(repetitions, int) or not 1 <= repetitions <= 20:
        raise IsingBenchmarkError("repetitions must be an integer between 1 and 20")
    if not isinstance(temperatures, tuple) or not 1 <= len(temperatures) <= 12:
        raise IsingBenchmarkError("one to twelve temperatures are required")
    normalized_temperatures = tuple(float(item) for item in temperatures)
    if any(not math.isfinite(item) or not 0.1 <= item <= 10.0 for item in normalized_temperatures):
        raise IsingBenchmarkError("temperatures must be finite values between 0.1 and 10.0")
    if len(set(normalized_temperatures)) != len(normalized_temperatures):
        raise IsingBenchmarkError("temperatures must be unique")
    if not isinstance(algorithms, tuple) or set(algorithms) != set(SUPPORTED_ALGORITHMS):
        raise IsingBenchmarkError("algorithms must contain Metropolis, Wolff, and Swendsen-Wang exactly once")
    return {
        "schema_version": SCHEMA_VERSION,
        "trust_status": "seeded_classical_ising_benchmark_plan_not_run",
        "model": "two_dimensional_zero_field_nearest_neighbor_ising",
        "lattice_size": lattice_size,
        "temperatures": list(normalized_temperatures),
        "burn_in_sweeps": burn_in_sweeps,
        "measurement_sweeps": measurement_sweeps,
        "seed": seed,
        "repetitions": repetitions,
        "algorithms": list(SUPPORTED_ALGORITHMS),
        "observable": "energy_per_spin",
        "comparison_boundary": (
            "Each algorithm starts from an independently seeded random spin lattice at the same temperature. "
            "Wall time is local Python process time for the declared sweep convention, not a hardware-independent claim."
        ),
    }


def run_ising_benchmark(*, plan: dict[str, Any]) -> dict[str, Any]:
    """Execute the bounded, seeded classical-MC plan and return aggregate metrics."""
    _validate_plan(plan)
    replicate_rows: list[dict[str, Any]] = []
    for temperature_index, temperature in enumerate(plan["temperatures"]):
        for algorithm_index, algorithm in enumerate(plan["algorithms"]):
            for repetition_index in range(plan["repetitions"]):
                task_seed = _derived_seed(plan["seed"], temperature_index, algorithm_index, repetition_index)
                spins = _random_lattice(plan["lattice_size"], random.Random(task_seed))
                rng = random.Random(task_seed ^ 0x9E3779B9)
                beta = 1.0 / temperature
                for _ in range(plan["burn_in_sweeps"]):
                    _sweep(spins, beta, algorithm, rng)
                started = time.perf_counter_ns()
                observations = []
                for _ in range(plan["measurement_sweeps"]):
                    _sweep(spins, beta, algorithm, rng)
                    observations.append(_energy_per_spin(spins))
                elapsed_seconds = max((time.perf_counter_ns() - started) / 1_000_000_000, 1e-12)
                tau = _integrated_autocorrelation_time(observations)
                effective_samples = len(observations) / (2.0 * tau)
                replicate_rows.append({
                    "temperature": temperature,
                    "algorithm": algorithm,
                    "repetition_index": repetition_index,
                    "sample_count": len(observations),
                    "mean_energy_per_spin": _mean(observations),
                    "integrated_autocorrelation_time_sweeps": tau,
                    "effective_sample_count": effective_samples,
                    "wall_time_seconds": elapsed_seconds,
                    "effective_samples_per_second": effective_samples / elapsed_seconds,
                })
    rows = _aggregate_algorithm_metrics(replicate_rows, repetitions=plan["repetitions"])
    return {
        "schema_version": SCHEMA_VERSION,
        "trust_status": "executed_seeded_classical_ising_benchmark_requires_scope_limited_interpretation",
        "plan_sha256": _sha256(plan),
        "model": plan["model"],
        "lattice_size": plan["lattice_size"],
        "temperatures": plan["temperatures"],
        "seed": plan["seed"],
        "repetitions": plan["repetitions"],
        "algorithm_metrics": rows,
        "replicate_metrics": replicate_rows,
        "measurement_environment": _local_measurement_environment(),
        "interpretation_boundary": (
            "These are local measurements for this finite 2-D Ising implementation and declared sweep convention. "
            "They do not establish a universal algorithm ranking, QMC performance, or materials-model performance."
        ),
    }


def propose_ising_followups(*, plan: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    """Propose a bounded refinement near the slowest observed local point."""
    _validate_plan(plan)
    if not isinstance(result, dict) or result.get("plan_sha256") != _sha256(plan):
        raise IsingBenchmarkError("Ising result is not bound to the supplied benchmark plan")
    rows = result.get("algorithm_metrics")
    if not isinstance(rows, list) or not rows:
        raise IsingBenchmarkError("Ising result has no algorithm metrics")
    slowest = max(rows, key=lambda row: float(row.get("integrated_autocorrelation_time_sweeps", -1)))
    temperature = float(slowest["temperature"])
    delta = max(0.02, temperature * 0.03)
    proposed_temperatures = sorted({round(max(0.1, temperature - delta), 6), round(temperature, 6), round(min(10.0, temperature + delta), 6)})
    return {
        "schema_version": SCHEMA_VERSION,
        "trust_status": "classical_mc_followup_suggestion_requires_human_approval_not_run",
        "plan_sha256": _sha256(plan),
        "trigger": {
            "algorithm": slowest["algorithm"],
            "temperature": temperature,
            "integrated_autocorrelation_time_sweeps": slowest["integrated_autocorrelation_time_sweeps"],
        },
        "proposed_refinement": {
            "temperatures": proposed_temperatures,
            "lattice_sizes": [plan["lattice_size"], min(128, plan["lattice_size"] * 2)],
            "measurement_sweeps": min(10_000, plan["measurement_sweeps"] * 2),
            "approval_required": True,
        },
        "interpretation_boundary": "The proposal targets a locally observed autocorrelation signal; it is not an automatic computation or a conclusion about a thermodynamic critical point.",
    }


def write_ising_plan(run_dir: Path, payload: dict[str, Any]) -> Path:
    return _write(run_dir / "ising_benchmark_plan.json", payload)


def write_ising_result(run_dir: Path, payload: dict[str, Any]) -> Path:
    return _write(run_dir / "ising_benchmark_result.json", payload)


def write_ising_followups(run_dir: Path, payload: dict[str, Any]) -> Path:
    return _write(run_dir / "ising_benchmark_followups.json", payload)


def _sweep(spins: list[list[int]], beta: float, algorithm: str, rng: random.Random) -> None:
    if algorithm == "metropolis":
        _metropolis_sweep(spins, beta, rng)
    elif algorithm == "wolff":
        _wolff_sweep(spins, beta, rng)
    elif algorithm == "swendsen_wang":
        _swendsen_wang_sweep(spins, beta, rng)
    else:  # pragma: no cover - plan validation prevents this branch.
        raise IsingBenchmarkError("unsupported classical MC algorithm")


def _metropolis_sweep(spins: list[list[int]], beta: float, rng: random.Random) -> None:
    size = len(spins)
    for _ in range(size * size):
        i, j = rng.randrange(size), rng.randrange(size)
        spin = spins[i][j]
        neighbors = spins[(i - 1) % size][j] + spins[(i + 1) % size][j] + spins[i][(j - 1) % size] + spins[i][(j + 1) % size]
        delta_energy = 2 * spin * neighbors
        if delta_energy <= 0 or rng.random() < math.exp(-beta * delta_energy):
            spins[i][j] = -spin


def _wolff_sweep(spins: list[list[int]], beta: float, rng: random.Random) -> None:
    size = len(spins)
    visited_sites = 0
    probability = 1.0 - math.exp(-2.0 * beta)
    while visited_sites < size * size:
        start = (rng.randrange(size), rng.randrange(size))
        target = spins[start[0]][start[1]]
        cluster = {start}
        frontier = [start]
        while frontier:
            i, j = frontier.pop()
            for neighbor in (((i - 1) % size, j), ((i + 1) % size, j), (i, (j - 1) % size), (i, (j + 1) % size)):
                if neighbor not in cluster and spins[neighbor[0]][neighbor[1]] == target and rng.random() < probability:
                    cluster.add(neighbor)
                    frontier.append(neighbor)
        for i, j in cluster:
            spins[i][j] = -spins[i][j]
        visited_sites += len(cluster)


def _swendsen_wang_sweep(spins: list[list[int]], beta: float, rng: random.Random) -> None:
    size, count = len(spins), len(spins) * len(spins)
    parent = list(range(count))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        left, right = find(left), find(right)
        if left != right:
            parent[right] = left

    probability = 1.0 - math.exp(-2.0 * beta)
    for i in range(size):
        for j in range(size):
            index = i * size + j
            for ni, nj in (((i + 1) % size, j), (i, (j + 1) % size)):
                if spins[i][j] == spins[ni][nj] and rng.random() < probability:
                    union(index, ni * size + nj)
    flip_by_root = {find(index): rng.random() < 0.5 for index in range(count)}
    for i in range(size):
        for j in range(size):
            if flip_by_root[find(i * size + j)]:
                spins[i][j] = -spins[i][j]


def _random_lattice(size: int, rng: random.Random) -> list[list[int]]:
    return [[1 if rng.random() < 0.5 else -1 for _ in range(size)] for _ in range(size)]


def _energy_per_spin(spins: list[list[int]]) -> float:
    size = len(spins)
    energy = 0
    for i in range(size):
        for j in range(size):
            energy -= spins[i][j] * (spins[(i + 1) % size][j] + spins[i][(j + 1) % size])
    return energy / (size * size)


def _integrated_autocorrelation_time(values: list[float]) -> float:
    mean = _mean(values)
    variance = _mean([(value - mean) ** 2 for value in values])
    if variance <= 1e-14:
        return 0.5
    total = 0.5
    maximum_lag = min(len(values) // 2, 200)
    for lag in range(1, maximum_lag + 1):
        covariance = _mean([(values[index] - mean) * (values[index + lag] - mean) for index in range(len(values) - lag)])
        correlation = covariance / variance
        if correlation <= 0:
            break
        total += correlation
    return max(0.5, total)


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def _validate_plan(payload: object) -> None:
    if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
        raise IsingBenchmarkError("Ising benchmark plan schema is invalid")
    if payload.get("trust_status") != "seeded_classical_ising_benchmark_plan_not_run":
        raise IsingBenchmarkError("Ising benchmark plan trust status is invalid")
    rebuilt = build_ising_benchmark_plan(
        lattice_size=payload.get("lattice_size"),
        temperatures=tuple(payload.get("temperatures", ())),
        burn_in_sweeps=payload.get("burn_in_sweeps"),
        measurement_sweeps=payload.get("measurement_sweeps"),
        seed=payload.get("seed"),
        repetitions=payload.get("repetitions", 1),
        algorithms=tuple(payload.get("algorithms", ())),
    )
    if rebuilt["lattice_size"] != payload["lattice_size"] or rebuilt["temperatures"] != payload["temperatures"]:
        raise IsingBenchmarkError("Ising benchmark plan is invalid")


def _write(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _derived_seed(seed: int, temperature_index: int, algorithm_index: int, repetition_index: int) -> int:
    return int(hashlib.sha256(f"{seed}:{temperature_index}:{algorithm_index}:{repetition_index}".encode()).hexdigest()[:8], 16)


def _aggregate_algorithm_metrics(replicates: list[dict[str, Any]], *, repetitions: int) -> list[dict[str, Any]]:
    """Aggregate repeated local measurements and expose a fixed Metropolis baseline.

    Timing remains machine-specific; ratios are therefore descriptive only and
    must always travel with the recorded plan and its sweep convention.
    """
    grouped: dict[tuple[float, str], list[dict[str, Any]]] = {}
    for row in replicates:
        grouped.setdefault((row["temperature"], row["algorithm"]), []).append(row)
    result: list[dict[str, Any]] = []
    baseline_by_temperature: dict[float, dict[str, Any]] = {}
    for (temperature, algorithm), rows in sorted(grouped.items()):
        if len(rows) != repetitions:
            raise IsingBenchmarkError("Ising replicate aggregation is incomplete")
        aggregate = {
            "temperature": temperature,
            "algorithm": algorithm,
            "replicate_count": repetitions,
            "sample_count_per_replicate": rows[0]["sample_count"],
            "mean_energy_per_spin": _mean([row["mean_energy_per_spin"] for row in rows]),
            "energy_per_spin_standard_deviation": _population_std([row["mean_energy_per_spin"] for row in rows]),
            "integrated_autocorrelation_time_sweeps": _mean([row["integrated_autocorrelation_time_sweeps"] for row in rows]),
            "autocorrelation_time_standard_deviation": _population_std([row["integrated_autocorrelation_time_sweeps"] for row in rows]),
            "effective_sample_count": _mean([row["effective_sample_count"] for row in rows]),
            "wall_time_seconds": _mean([row["wall_time_seconds"] for row in rows]),
            "wall_time_standard_deviation_seconds": _population_std([row["wall_time_seconds"] for row in rows]),
            "effective_samples_per_second": _mean([row["effective_samples_per_second"] for row in rows]),
        }
        if algorithm == "metropolis":
            baseline_by_temperature[temperature] = aggregate
        result.append(aggregate)
    for row in result:
        baseline = baseline_by_temperature.get(row["temperature"])
        if baseline is None:
            raise IsingBenchmarkError("Ising result requires a Metropolis baseline at every temperature")
        row["relative_to_metropolis"] = {
            "autocorrelation_time_ratio": row["integrated_autocorrelation_time_sweeps"] / baseline["integrated_autocorrelation_time_sweeps"],
            "effective_samples_per_second_ratio": row["effective_samples_per_second"] / baseline["effective_samples_per_second"],
        }
    return result


def _population_std(values: list[float]) -> float:
    mean = _mean(values)
    return math.sqrt(_mean([(value - mean) ** 2 for value in values]))


def _local_measurement_environment() -> dict[str, str | int]:
    """Record only submission-safe context for a local timing comparison.

    No host name, user name, filesystem location, job identifier or external
    service information is recorded.  This makes the timing boundary explicit
    while keeping the run artifact safe to index or share as an aggregate.
    """
    return {
        "runtime": f"CPython {platform.python_version()}",
        "operating_system": platform.system() or "unknown",
        "machine_architecture": platform.machine() or "unknown",
        "logical_cpu_count": os.cpu_count() or 0,
        "parallelism": "single Python process; no GPU or MPI",
        "numerical_precision": "Python float (IEEE-754 binary64 on supported CPython builds)",
        "timing_scope": "perf_counter_ns around measurement sweeps only; excludes plan creation, lattice initialization, burn-in, serialization and queueing",
    }


def _sha256(payload: object) -> str:
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
