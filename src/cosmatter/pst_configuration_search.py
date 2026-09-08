"""Plan-only PST configuration encoding and synthetic MRMT ablation.

No function in this module runs molecular dynamics or predicts a material
property.  The synthetic evaluator exists only to test fixed-composition
search mechanics, budget accounting, replay, and the rule that response-field
descriptors may guide proposals but never rank unevaluated configurations.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from hashlib import sha256
import json
import math
from pathlib import Path
import random
from typing import Any, Callable


SUPERCELL = (8, 8, 8)
A_SITE_COUNT = 512
PLAN_SCHEMA_VERSION = "cosmatter.pst-configuration-search-plan/v1"
ABLATION_SCHEMA_VERSION = "cosmatter.pst-mrmt-synthetic-ablation/v1"
PLAN_TRUST_STATUS = "plan_only_no_md_execution_or_property_result"
ABLATION_TRUST_STATUS = "synthetic_search_regression_not_material_property_evidence"
METHODS = ("uniform_random", "fixed_cardinality_eda", "short_range_guided", "mrmt")


class PstConfigurationSearchError(ValueError):
    """Raised when a PST plan or configuration violates its frozen boundary."""


@dataclass(frozen=True)
class PstConfiguration:
    """A canonical fixed-size A-site occupation: 1=Pb and 0=Sr."""

    occupations: tuple[int, ...]

    def __post_init__(self) -> None:
        if len(self.occupations) != A_SITE_COUNT or any(not isinstance(value, int) or isinstance(value, bool) or value not in (0, 1) for value in self.occupations):
            raise PstConfigurationSearchError("PST configuration must contain exactly 512 binary A-site occupations")

    @property
    def n_pb(self) -> int:
        return sum(self.occupations)

    @property
    def n_sr(self) -> int:
        return A_SITE_COUNT - self.n_pb

    def swap(self, first: int, second: int) -> "PstConfiguration":
        if not 0 <= first < A_SITE_COUNT or not 0 <= second < A_SITE_COUNT or first == second:
            raise PstConfigurationSearchError("swap indexes must be distinct valid A-site indexes")
        if self.occupations[first] == self.occupations[second]:
            raise PstConfigurationSearchError("fixed-composition swap requires unlike occupants")
        changed = list(self.occupations)
        changed[first], changed[second] = changed[second], changed[first]
        result = PstConfiguration(tuple(changed))
        if result.n_pb != self.n_pb:
            raise AssertionError("fixed-composition swap changed Pb count")
        return result

    def canonical_translation(self) -> tuple[int, ...]:
        """Return the lexicographically minimal periodic translation.

        Translation canonicalisation removes 512 trivially equivalent origins.
        Point-group and chemistry-specific equivalences remain future work and
        are not silently claimed here.
        """
        return tuple(_canonical_translation_bytes(self.occupations))

    def configuration_hash(self) -> str:
        bits = _canonical_translation_bytes(self.occupations)
        packed = bytearray(A_SITE_COUNT // 8)
        for index, value in enumerate(bits):
            if value:
                packed[index // 8] |= 1 << (index % 8)
        return sha256(b"cosmatter:pst:8x8x8:a-site:v1\0" + bytes(packed)).hexdigest()


def realizable_composition(value: str | float | Decimal) -> tuple[int, int, str]:
    """Resolve a composition without silently rounding an unrealizable x."""
    try:
        requested = Decimal(str(value))
    except InvalidOperation as error:
        raise PstConfigurationSearchError("composition must be a finite decimal") from error
    if not requested.is_finite() or requested < 0 or requested > 1:
        raise PstConfigurationSearchError("composition must be between 0 and 1")
    exact_pb = requested * A_SITE_COUNT
    if exact_pb != exact_pb.to_integral_value():
        raise PstConfigurationSearchError("composition is not exactly realizable on 512 A sites; explicit reapproval is required")
    n_pb = int(exact_pb)
    realized = format(Decimal(n_pb) / Decimal(A_SITE_COUNT), "f")
    return n_pb, A_SITE_COUNT - n_pb, realized


def random_configuration(n_pb: int, rng: random.Random) -> PstConfiguration:
    if not isinstance(n_pb, int) or isinstance(n_pb, bool) or not 0 <= n_pb <= A_SITE_COUNT:
        raise PstConfigurationSearchError("n_pb must be an integer between 0 and 512")
    pb_sites = set(rng.sample(range(A_SITE_COUNT), n_pb))
    return PstConfiguration(tuple(1 if index in pb_sites else 0 for index in range(A_SITE_COUNT)))


def motif_descriptors(configuration: PstConfiguration) -> dict[str, Any]:
    """Compute proposal-only SRO, interface, and permitted composition waves."""
    unlike = 0
    pair_count = 0
    pb_to_sr = 0
    pb_neighbor_count = 0
    for x in range(8):
        for y in range(8):
            for z in range(8):
                origin = configuration.occupations[_index(x, y, z)]
                for nx, ny, nz in (((x + 1) % 8, y, z), (x, (y + 1) % 8, z), (x, y, (z + 1) % 8)):
                    neighbour = configuration.occupations[_index(nx, ny, nz)]
                    pair_count += 1
                    unlike += origin != neighbour
                if origin == 1:
                    for nx, ny, nz in (((x + 1) % 8, y, z), ((x - 1) % 8, y, z), (x, (y + 1) % 8, z), (x, (y - 1) % 8, z), (x, y, (z + 1) % 8), (x, y, (z - 1) % 8)):
                        pb_neighbor_count += 1
                        pb_to_sr += configuration.occupations[_index(nx, ny, nz)] == 0
    sr_fraction = configuration.n_sr / A_SITE_COUNT
    conditional_sr = pb_to_sr / pb_neighbor_count if pb_neighbor_count else 0.0
    alpha_1 = 0.0 if sr_fraction in (0.0, 1.0) else 1.0 - conditional_sr / sr_fraction
    waves = {
        axis: _composition_wave(configuration, vector)
        for axis, vector in (("100", (1, 0, 0)), ("010", (0, 1, 0)), ("001", (0, 0, 1)), ("200", (2, 0, 0)), ("020", (0, 2, 0)), ("002", (0, 0, 2)))
    }
    return {
        "nearest_neighbor_unlike_fraction": unlike / pair_count,
        "warren_cowley_alpha_1": alpha_1,
        "composition_wave_power": waves,
    }


def build_pst_configuration_search_plan(payload: object) -> dict[str, Any]:
    """Validate and normalize a reviewed plan without authorizing MD execution."""
    fields = {
        "composition_requested", "potential_id", "potential_hash", "objective_spec",
        "md_protocol_id", "md_protocol_hash", "chain_count", "random_baseline_count",
        "short_md_steps", "short_md_repeats", "promotion_rule", "long_md_steps",
        "long_md_independent_seeds", "max_evaluations", "aggregate_md_step_budget",
        "max_wallclock_hours", "max_accelerator_hours", "failure_policy", "stopping_rule",
    }
    if not isinstance(payload, dict) or set(payload) != fields:
        raise PstConfigurationSearchError("PST plan input has unsupported or missing fields")
    n_pb, n_sr, realized = realizable_composition(payload["composition_requested"])
    for field in ("potential_id", "md_protocol_id", "promotion_rule", "failure_policy", "stopping_rule"):
        if not isinstance(payload[field], str) or not payload[field].strip() or len(payload[field]) > 500:
            raise PstConfigurationSearchError(f"{field} must be bounded nonempty text")
    for field in ("potential_hash", "md_protocol_hash"):
        _require_sha256(payload[field], field)
    objective = payload["objective_spec"]
    if not isinstance(objective, dict) or set(objective) != {"mode", "components", "conditions_hash", "uncertainty_method"}:
        raise PstConfigurationSearchError("objective_spec has unsupported or missing fields")
    if objective["mode"] not in {"scalar", "pareto"} or not isinstance(objective["components"], list) or not objective["components"] or len(objective["components"]) > 8 or any(not isinstance(item, str) or not item.strip() for item in objective["components"]):
        raise PstConfigurationSearchError("objective_spec mode or components are invalid")
    _require_sha256(objective["conditions_hash"], "objective_spec.conditions_hash")
    if not isinstance(objective["uncertainty_method"], str) or not objective["uncertainty_method"].strip():
        raise PstConfigurationSearchError("objective_spec uncertainty_method is invalid")
    integer_fields = ("chain_count", "random_baseline_count", "short_md_steps", "short_md_repeats", "long_md_steps", "max_evaluations", "aggregate_md_step_budget")
    if any(not isinstance(payload[field], int) or isinstance(payload[field], bool) or payload[field] < 1 for field in integer_fields):
        raise PstConfigurationSearchError("PST plan integer budgets must be positive")
    seeds = payload["long_md_independent_seeds"]
    if not isinstance(seeds, list) or len(seeds) < 3 or len(set(seeds)) != len(seeds) or any(not isinstance(seed, int) or isinstance(seed, bool) or seed < 0 for seed in seeds):
        raise PstConfigurationSearchError("long MD validation requires at least three unique nonnegative seeds")
    for field in ("max_wallclock_hours", "max_accelerator_hours"):
        if not isinstance(payload[field], (int, float)) or isinstance(payload[field], bool) or not math.isfinite(payload[field]) or payload[field] <= 0:
            raise PstConfigurationSearchError(f"{field} must be a positive finite number")
    return {
        "schema_version": PLAN_SCHEMA_VERSION,
        "trust_status": PLAN_TRUST_STATUS,
        "material_system": "(Pb_xSr_1-x)TiO3",
        "potential": {"potential_id": payload["potential_id"].strip(), "sha256": payload["potential_hash"]},
        "supercell": list(SUPERCELL),
        "a_site_count": A_SITE_COUNT,
        "composition": {"requested": str(payload["composition_requested"]), "n_pb": n_pb, "n_sr": n_sr, "realized": realized},
        "objective_spec": {
            "mode": objective["mode"],
            "components": list(objective["components"]),
            "conditions_hash": objective["conditions_hash"],
            "uncertainty_method": objective["uncertainty_method"].strip(),
        },
        "md_protocol": {"protocol_id": payload["md_protocol_id"].strip(), "sha256": payload["md_protocol_hash"]},
        "proposal_method": "md_response_guided_motif_tempering",
        "chain_count": payload["chain_count"],
        "random_baseline_spec": {"configuration_count": payload["random_baseline_count"], "fixed_composition": True},
        "short_md_stage": {"steps": payload["short_md_steps"], "independent_repeats": payload["short_md_repeats"]},
        "promotion_rule": payload["promotion_rule"].strip(),
        "long_md_validation": {"steps": payload["long_md_steps"], "independent_seeds": seeds},
        "evaluation_budget": {
            "max_evaluations": payload["max_evaluations"],
            "aggregate_md_step_budget": payload["aggregate_md_step_budget"],
            "max_wallclock_hours": float(payload["max_wallclock_hours"]),
            "max_accelerator_hours": float(payload["max_accelerator_hours"]),
        },
        "failure_policy": payload["failure_policy"].strip(),
        "stopping_rule": payload["stopping_rule"].strip(),
        "configuration_hashes": [],
        "run_receipt_ids": [],
        "pareto_archive_or_best_found": [],
        "property_prediction_count": 0,
        "execution_authorized": False,
        "claim_boundary": "best_found_under_frozen_potential_protocol_and_budget_not_global_optimum",
    }


def validate_pst_configuration_search_plan(plan: object) -> None:
    if not isinstance(plan, dict) or plan.get("schema_version") != PLAN_SCHEMA_VERSION or plan.get("trust_status") != PLAN_TRUST_STATUS:
        raise PstConfigurationSearchError("PST configuration search plan is invalid")
    expected_fields = {
        "schema_version", "trust_status", "material_system", "potential", "supercell",
        "a_site_count", "composition", "objective_spec", "md_protocol", "proposal_method",
        "chain_count", "random_baseline_spec", "short_md_stage", "promotion_rule",
        "long_md_validation", "evaluation_budget", "failure_policy", "stopping_rule",
        "configuration_hashes", "run_receipt_ids", "pareto_archive_or_best_found",
        "property_prediction_count", "execution_authorized", "claim_boundary",
    }
    if set(plan) != expected_fields:
        raise PstConfigurationSearchError("PST configuration search plan has unsupported or missing fields")
    if plan.get("material_system") != "(Pb_xSr_1-x)TiO3" or plan.get("proposal_method") != "md_response_guided_motif_tempering" or plan.get("claim_boundary") != "best_found_under_frozen_potential_protocol_and_budget_not_global_optimum":
        raise PstConfigurationSearchError("PST configuration search plan scope boundary is invalid")
    if plan.get("supercell") != list(SUPERCELL) or plan.get("a_site_count") != A_SITE_COUNT or plan.get("execution_authorized") is not False or plan.get("property_prediction_count") != 0:
        raise PstConfigurationSearchError("PST configuration search plan violates its plan-only boundary")
    composition = plan.get("composition")
    if not isinstance(composition, dict) or set(composition) != {"requested", "n_pb", "n_sr", "realized"}:
        raise PstConfigurationSearchError("PST configuration search plan composition is invalid")
    stored_n_pb = composition.get("n_pb")
    stored_n_sr = composition.get("n_sr")
    if any(not isinstance(value, int) or isinstance(value, bool) for value in (stored_n_pb, stored_n_sr)) or stored_n_pb + stored_n_sr != A_SITE_COUNT:
        raise PstConfigurationSearchError("PST configuration search plan composition is invalid")
    n_pb, n_sr, realized = realizable_composition(composition["requested"])
    if (composition["n_pb"], composition["n_sr"], composition["realized"]) != (n_pb, n_sr, realized):
        raise PstConfigurationSearchError("PST configuration search plan realized composition is inconsistent")
    potential = plan.get("potential")
    protocol = plan.get("md_protocol")
    if not isinstance(potential, dict) or set(potential) != {"potential_id", "sha256"} or not isinstance(protocol, dict) or set(protocol) != {"protocol_id", "sha256"}:
        raise PstConfigurationSearchError("PST configuration search plan provenance is invalid")
    _require_sha256(potential["sha256"], "potential.sha256")
    _require_sha256(protocol["sha256"], "md_protocol.sha256")
    if plan.get("configuration_hashes") or plan.get("run_receipt_ids") or plan.get("pareto_archive_or_best_found"):
        raise PstConfigurationSearchError("plan-only PST artifact cannot contain execution results")


def write_pst_configuration_search_plan(path: Path, plan: dict[str, Any]) -> Path:
    validate_pst_configuration_search_plan(plan)
    return _write_immutable_json(path, plan, "PST configuration search plan")


@dataclass(frozen=True)
class SyntheticEvaluation:
    configuration_hash: str
    score: float
    response_field: tuple[int, ...]
    receipt_id: str


class EvaluationBudgetLedger:
    """Cache exact evaluation keys and reject use beyond a frozen budget."""

    def __init__(self, maximum: int) -> None:
        if not isinstance(maximum, int) or isinstance(maximum, bool) or maximum < 1:
            raise PstConfigurationSearchError("evaluation budget must be a positive integer")
        self.maximum = maximum
        self._records: dict[tuple[str, str, str, int], SyntheticEvaluation] = {}

    @property
    def used(self) -> int:
        return len(self._records)

    def evaluate(
        self,
        configuration: PstConfiguration,
        *,
        potential_hash: str,
        protocol_hash: str,
        seed: int,
        evaluator: Callable[[PstConfiguration, int], SyntheticEvaluation],
    ) -> tuple[SyntheticEvaluation, bool]:
        _require_sha256(potential_hash, "potential_hash")
        _require_sha256(protocol_hash, "protocol_hash")
        if not isinstance(seed, int) or isinstance(seed, bool) or seed < 0:
            raise PstConfigurationSearchError("evaluation seed must be a nonnegative integer")
        key = (configuration.configuration_hash(), potential_hash, protocol_hash, seed)
        cached = self._records.get(key)
        if cached is not None:
            return cached, True
        if self.used >= self.maximum:
            raise PstConfigurationSearchError("evaluation budget exhausted")
        result = evaluator(configuration, seed)
        if not isinstance(result, SyntheticEvaluation) or result.configuration_hash != key[0]:
            raise PstConfigurationSearchError("evaluation receipt is bound to another configuration")
        if not isinstance(result.score, (int, float)) or isinstance(result.score, bool) or not math.isfinite(result.score):
            raise PstConfigurationSearchError("evaluation receipt score must be finite")
        if len(result.response_field) != A_SITE_COUNT or any(not isinstance(value, int) or isinstance(value, bool) for value in result.response_field):
            raise PstConfigurationSearchError("evaluation response field must contain 512 integer proposal signals")
        _require_sha256(result.receipt_id, "evaluation receipt_id")
        self._records[key] = result
        return result, False


def run_synthetic_mrmt_ablation(*, n_pb: int = 256, evaluation_budget: int = 64, search_seeds: tuple[int, ...] = (11, 29, 47)) -> dict[str, Any]:
    """Run four same-budget synthetic searches with no property predictor."""
    if not 2 <= n_pb <= A_SITE_COUNT - 2:
        raise PstConfigurationSearchError("synthetic search requires at least two Pb and two Sr occupants")
    if evaluation_budget < 16:
        raise PstConfigurationSearchError("synthetic ablation budget must be at least 16 evaluations per method")
    if len(search_seeds) < 3 or len(set(search_seeds)) != len(search_seeds) or any(not isinstance(seed, int) or isinstance(seed, bool) or seed < 0 for seed in search_seeds):
        raise PstConfigurationSearchError("synthetic ablation requires at least three unique nonnegative search seeds")
    target = _synthetic_target(n_pb)
    runs: dict[str, list[dict[str, Any]]] = {method: [] for method in METHODS}
    for method in METHODS:
        for search_seed in search_seeds:
            runs[method].append(_run_synthetic_method(method, target, n_pb, evaluation_budget, search_seed))
    aggregates = {
        method: {
            "mean_best_score": sum(run["best_score"] for run in method_runs) / len(method_runs),
            "minimum_best_score": min(run["best_score"] for run in method_runs),
            "maximum_best_score": max(run["best_score"] for run in method_runs),
        }
        for method, method_runs in runs.items()
    }
    random_by_seed = {run["search_seed"]: run["best_score"] for run in runs["uniform_random"]}
    mrmt_outperforms = all(run["best_score"] > random_by_seed[run["search_seed"]] for run in runs["mrmt"])
    artifact = {
        "schema_version": ABLATION_SCHEMA_VERSION,
        "trust_status": ABLATION_TRUST_STATUS,
        "supercell": list(SUPERCELL),
        "n_pb": n_pb,
        "n_sr": A_SITE_COUNT - n_pb,
        "methods": list(METHODS),
        "evaluation_budget_per_method_per_seed": evaluation_budget,
        "search_seed_count": len(search_seeds),
        "runs": runs,
        "aggregates": aggregates,
        "ranking_source": "executed_synthetic_objective_receipts_only",
        "proposal_guidance": "configuration_descriptors_or_executed_synthetic_response_field_only",
        "property_prediction_count": 0,
        "mrmt_outperforms_uniform_random_every_seed": mrmt_outperforms,
        "claim_boundary": "algorithm_regression_only_not_pst_dielectric_or_piezoelectric_evidence",
    }
    validate_synthetic_ablation(artifact)
    return artifact


def write_synthetic_mrmt_ablation(path: Path, artifact: dict[str, Any]) -> Path:
    validate_synthetic_ablation(artifact)
    return _write_immutable_json(path, artifact, "synthetic MRMT ablation")


def validate_synthetic_ablation(artifact: object) -> None:
    if not isinstance(artifact, dict) or artifact.get("schema_version") != ABLATION_SCHEMA_VERSION or artifact.get("trust_status") != ABLATION_TRUST_STATUS:
        raise PstConfigurationSearchError("synthetic MRMT ablation artifact is invalid")
    expected_fields = {
        "schema_version", "trust_status", "supercell", "n_pb", "n_sr", "methods",
        "evaluation_budget_per_method_per_seed", "search_seed_count", "runs", "aggregates",
        "ranking_source", "proposal_guidance", "property_prediction_count",
        "mrmt_outperforms_uniform_random_every_seed", "claim_boundary",
    }
    n_pb = artifact.get("n_pb")
    n_sr = artifact.get("n_sr")
    if set(artifact) != expected_fields or artifact.get("supercell") != list(SUPERCELL) or any(not isinstance(value, int) or isinstance(value, bool) for value in (n_pb, n_sr)) or n_pb + n_sr != A_SITE_COUNT:
        raise PstConfigurationSearchError("synthetic MRMT ablation scope or fields are invalid")
    if artifact.get("claim_boundary") != "algorithm_regression_only_not_pst_dielectric_or_piezoelectric_evidence" or artifact.get("proposal_guidance") != "configuration_descriptors_or_executed_synthetic_response_field_only":
        raise PstConfigurationSearchError("synthetic MRMT ablation claim boundary is invalid")
    if artifact.get("property_prediction_count") != 0 or artifact.get("ranking_source") != "executed_synthetic_objective_receipts_only":
        raise PstConfigurationSearchError("synthetic MRMT ablation violates the no-surrogate ranking boundary")
    if artifact.get("methods") != list(METHODS) or artifact.get("search_seed_count", 0) < 3:
        raise PstConfigurationSearchError("synthetic MRMT ablation methods or repetitions are invalid")
    budget = artifact.get("evaluation_budget_per_method_per_seed")
    runs = artifact.get("runs")
    if not isinstance(budget, int) or not isinstance(runs, dict) or set(runs) != set(METHODS):
        raise PstConfigurationSearchError("synthetic MRMT ablation budget or runs are invalid")
    seed_sets: list[set[int]] = []
    for method in METHODS:
        method_runs = runs[method]
        if not isinstance(method_runs, list) or len(method_runs) != artifact["search_seed_count"]:
            raise PstConfigurationSearchError("synthetic MRMT ablation repetition count is invalid")
        if any(run.get("evaluation_count") != budget or run.get("property_prediction_count") != 0 for run in method_runs):
            raise PstConfigurationSearchError("synthetic MRMT ablation budget equality is invalid")
        for run in method_runs:
            if not isinstance(run, dict) or set(run) != {"search_seed", "evaluation_count", "unique_configuration_count", "best_score", "best_configuration_hash", "best_receipt_id", "property_prediction_count"}:
                raise PstConfigurationSearchError("synthetic MRMT ablation run fields are invalid")
            if not isinstance(run.get("search_seed"), int) or isinstance(run.get("search_seed"), bool) or run["search_seed"] < 0:
                raise PstConfigurationSearchError("synthetic MRMT ablation search seed is invalid")
            if not isinstance(run.get("best_score"), (int, float)) or isinstance(run.get("best_score"), bool) or not math.isfinite(run["best_score"]):
                raise PstConfigurationSearchError("synthetic MRMT ablation score is invalid")
            if run.get("unique_configuration_count") != budget:
                raise PstConfigurationSearchError("synthetic MRMT ablation contains duplicate evaluations")
            _require_sha256(run.get("best_configuration_hash"), "best_configuration_hash")
            _require_sha256(run.get("best_receipt_id"), "best_receipt_id")
        seed_sets.append({run["search_seed"] for run in method_runs})
    if any(seeds != seed_sets[0] for seeds in seed_sets[1:]) or len(seed_sets[0]) != artifact["search_seed_count"]:
        raise PstConfigurationSearchError("synthetic MRMT ablation methods do not share the same search seeds")
    aggregates = artifact.get("aggregates")
    if not isinstance(aggregates, dict) or set(aggregates) != set(METHODS):
        raise PstConfigurationSearchError("synthetic MRMT ablation aggregates are invalid")
    for method in METHODS:
        scores = [run["best_score"] for run in runs[method]]
        expected = {
            "mean_best_score": sum(scores) / len(scores),
            "minimum_best_score": min(scores),
            "maximum_best_score": max(scores),
        }
        if aggregates.get(method) != expected:
            raise PstConfigurationSearchError("synthetic MRMT ablation aggregates are inconsistent")
    random_by_seed = {run.get("search_seed"): run.get("best_score") for run in runs["uniform_random"]}
    mrmt_outperforms = all(
        isinstance(run.get("best_score"), (int, float))
        and run.get("search_seed") in random_by_seed
        and run["best_score"] > random_by_seed[run["search_seed"]]
        for run in runs["mrmt"]
    )
    if artifact.get("mrmt_outperforms_uniform_random_every_seed") is not mrmt_outperforms:
        raise PstConfigurationSearchError("synthetic MRMT ablation comparison flag is inconsistent")


def _run_synthetic_method(method: str, target: PstConfiguration, n_pb: int, budget: int, search_seed: int) -> dict[str, Any]:
    rng = random.Random(search_seed)
    ledger = EvaluationBudgetLedger(budget)
    synthetic_hash = sha256(b"synthetic-only").hexdigest()

    def evaluator(configuration: PstConfiguration, seed: int) -> SyntheticEvaluation:
        matches = tuple(1 if current == wanted else -1 for current, wanted in zip(configuration.occupations, target.occupations))
        score = sum(value == 1 for value in matches) / A_SITE_COUNT
        config_hash = configuration.configuration_hash()
        receipt = sha256(f"synthetic:{config_hash}:{seed}".encode()).hexdigest()
        return SyntheticEvaluation(config_hash, score, matches, receipt)

    evaluated: list[tuple[PstConfiguration, SyntheticEvaluation]] = []
    seen_hashes: set[str] = set()

    def consume(configuration: PstConfiguration) -> SyntheticEvaluation | None:
        config_hash = configuration.configuration_hash()
        if config_hash in seen_hashes:
            return None
        result, cached = ledger.evaluate(configuration, potential_hash=synthetic_hash, protocol_hash=synthetic_hash, seed=search_seed, evaluator=evaluator)
        if cached:
            return None
        seen_hashes.add(config_hash)
        evaluated.append((configuration, result))
        return result

    current = random_configuration(n_pb, rng)
    current_eval = consume(current)
    assert current_eval is not None
    chains: list[tuple[PstConfiguration, SyntheticEvaluation]] = [(current, current_eval)]
    duplicate_attempts = 0
    while ledger.used < budget:
        if duplicate_attempts >= 32:
            # Some proposal kernels converge onto already measured states. A
            # deterministic RNG-backed fallback preserves the fixed budget
            # without treating a cached result as a fresh evaluation.
            candidate = random_configuration(n_pb, rng)
        elif method == "uniform_random":
            candidate = random_configuration(n_pb, rng)
        elif method == "fixed_cardinality_eda":
            candidate = _eda_proposal(evaluated, n_pb, rng)
        elif method == "short_range_guided":
            candidate = _short_range_proposal(chains[0][0], rng)
        else:
            if len(chains) < 4:
                initial = random_configuration(n_pb, rng)
                result = consume(initial)
                if result is not None:
                    chains.append((initial, result))
                    duplicate_attempts = 0
                else:
                    duplicate_attempts += 1
                continue
            chain_index = ledger.used % len(chains)
            base, base_eval = chains[chain_index]
            candidate = _mrmt_response_proposal(base, base_eval.response_field, rng)
        result = consume(candidate)
        if result is None:
            duplicate_attempts += 1
            if duplicate_attempts > budget * 2048:
                raise PstConfigurationSearchError("unable to find enough unique configurations for the frozen budget")
            continue
        duplicate_attempts = 0
        if method in {"short_range_guided", "mrmt"}:
            chain_index = 0 if method == "short_range_guided" else (ledger.used - 1) % len(chains)
            base, base_eval = chains[chain_index]
            temperature = 0.015 + 0.04 * (chain_index / max(len(chains) - 1, 1))
            if result.score >= base_eval.score or rng.random() < math.exp((result.score - base_eval.score) / temperature):
                chains[chain_index] = (candidate, result)
            if method == "mrmt" and ledger.used % 12 == 0:
                chains.sort(key=lambda pair: pair[1].score, reverse=True)
    _, best_result = max(evaluated, key=lambda pair: pair[1].score)
    return {
        "search_seed": search_seed,
        "evaluation_count": ledger.used,
        "unique_configuration_count": len(seen_hashes),
        "best_score": best_result.score,
        "best_configuration_hash": best_result.configuration_hash,
        "best_receipt_id": best_result.receipt_id,
        "property_prediction_count": 0,
    }


def _eda_proposal(evaluated: list[tuple[PstConfiguration, SyntheticEvaluation]], n_pb: int, rng: random.Random) -> PstConfiguration:
    elite_count = max(2, min(8, len(evaluated) // 3))
    elite = sorted(evaluated, key=lambda pair: pair[1].score, reverse=True)[:elite_count]
    weights = [sum(configuration.occupations[index] for configuration, _ in elite) / len(elite) for index in range(A_SITE_COUNT)]
    ranked = sorted(range(A_SITE_COUNT), key=lambda index: weights[index] + rng.uniform(-0.18, 0.18), reverse=True)
    chosen = set(ranked[:n_pb])
    return PstConfiguration(tuple(1 if index in chosen else 0 for index in range(A_SITE_COUNT)))


def _short_range_proposal(configuration: PstConfiguration, rng: random.Random) -> PstConfiguration:
    pb = [index for index, value in enumerate(configuration.occupations) if value == 1]
    sr = [index for index, value in enumerate(configuration.occupations) if value == 0]
    candidates: list[tuple[int, int, int]] = []
    for _ in range(12):
        first, second = rng.choice(pb), rng.choice(sr)
        proposed = configuration.swap(first, second)
        unlike = _nearest_unlike_count(proposed)
        candidates.append((unlike, first, second))
    _, first, second = min(candidates)
    return configuration.swap(first, second)


def _mrmt_response_proposal(configuration: PstConfiguration, response_field: tuple[int, ...], rng: random.Random) -> PstConfiguration:
    wrong_pb = [index for index, (value, response) in enumerate(zip(configuration.occupations, response_field)) if value == 1 and response < 0]
    wrong_sr = [index for index, (value, response) in enumerate(zip(configuration.occupations, response_field)) if value == 0 and response < 0]
    if wrong_pb and wrong_sr:
        result = configuration
        exchange_count = 1 + (rng.random() < 0.28) + (rng.random() < 0.12)
        for first, second in zip(rng.sample(wrong_pb, min(exchange_count, len(wrong_pb))), rng.sample(wrong_sr, min(exchange_count, len(wrong_sr)))):
            result = result.swap(first, second)
        return result
    return _short_range_proposal(configuration, rng)


def _synthetic_target(n_pb: int) -> PstConfiguration:
    scored = []
    for x in range(8):
        for y in range(8):
            for z in range(8):
                score = 2.0 * math.cos(2 * math.pi * x / 8) + 1.3 * math.cos(4 * math.pi * y / 8) + 0.7 * math.cos(2 * math.pi * (x + z) / 8)
                scored.append((score, _index(x, y, z)))
    chosen = {index for _, index in sorted(scored, reverse=True)[:n_pb]}
    return PstConfiguration(tuple(1 if index in chosen else 0 for index in range(A_SITE_COUNT)))


def _nearest_unlike_count(configuration: PstConfiguration) -> int:
    count = 0
    for x in range(8):
        for y in range(8):
            for z in range(8):
                value = configuration.occupations[_index(x, y, z)]
                count += value != configuration.occupations[_index((x + 1) % 8, y, z)]
                count += value != configuration.occupations[_index(x, (y + 1) % 8, z)]
                count += value != configuration.occupations[_index(x, y, (z + 1) % 8)]
    return count


def _composition_wave(configuration: PstConfiguration, vector: tuple[int, int, int]) -> float:
    mean = configuration.n_pb / A_SITE_COUNT
    real = 0.0
    imaginary = 0.0
    for x in range(8):
        for y in range(8):
            for z in range(8):
                phase = 2 * math.pi * (vector[0] * x + vector[1] * y + vector[2] * z) / 8
                centered = configuration.occupations[_index(x, y, z)] - mean
                real += centered * math.cos(phase)
                imaginary -= centered * math.sin(phase)
    return (real * real + imaginary * imaginary) / (A_SITE_COUNT * A_SITE_COUNT)


def _index(x: int, y: int, z: int) -> int:
    return x * 64 + y * 8 + z


def _require_sha256(value: object, field: str) -> None:
    if not isinstance(value, str) or len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise PstConfigurationSearchError(f"{field} must be a lowercase SHA-256 digest")


def _write_immutable_json(path: Path, payload: dict[str, Any], label: str) -> Path:
    serialized = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if path.exists():
        try:
            existing = path.read_text(encoding="utf-8")
        except OSError as error:
            raise PstConfigurationSearchError(f"existing {label} cannot be read") from error
        if existing != serialized:
            raise PstConfigurationSearchError(f"existing {label} cannot be overwritten; use a new run")
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(serialized, encoding="utf-8")
    return path


@lru_cache(maxsize=4096)
def _canonical_translation_bytes(occupations: tuple[int, ...]) -> bytes:
    """Canonicalize periodic origins using byte slices for bounded replay cost."""
    data = bytes(occupations)
    best: bytes | None = None
    for dx in range(8):
        for dy in range(8):
            ordered_rows = [
                data[((x + dx) % 8) * 64 + ((y + dy) % 8) * 8:
                     ((x + dx) % 8) * 64 + ((y + dy) % 8) * 8 + 8]
                for x in range(8)
                for y in range(8)
            ]
            for dz in range(8):
                translated = b"".join(row[dz:] + row[:dz] for row in ordered_rows)
                if best is None or translated < best:
                    best = translated
    assert best is not None
    return best
