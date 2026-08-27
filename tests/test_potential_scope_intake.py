import copy
import unittest

from cosmatter.machine_config import machine_config_template
from cosmatter.potential_scope_intake import (
    PotentialScopeIntakeError,
    autonomy_policy_template,
    build_condition_matrix,
    build_plugin_request,
    build_potential_passport,
    build_system_spec,
    system_spec_sha256,
)
from cosmatter.potential_task_plugins import default_task_plugin_registry


class PotentialScopeIntakeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.spec = {
            "schema_version": "1.0",
            "trust_status": "human_frozen_literature_bound_system_spec",
            "system_spec_id": "bfo_scope_v1",
            "material_systems": ["BiFeO3"],
            "scope_description": "Compare declared potential applicability for literature-mapped conditions.",
            "target_observables": ["forces", "relative_phase_energy"],
            "condition_axes": [
                {"axis_id": "strain_percent", "unit": "percent", "lower_bound": -2.0, "upper_bound": 2.0, "source_ids": ["source_map_001"]},
                {"axis_id": "temperature_k", "unit": "K", "lower_bound": 300.0, "upper_bound": 900.0, "source_ids": ["source_map_002"]},
            ],
            "potential_model_ids": ["potential_a", "potential_b"],
            "reference_method": "approved external reference protocol",
            "pre_registered_metrics": ["energy_mae_ev_per_atom", "force_rmse_ev_per_angstrom"],
            "literature_source_ids": ["source_map_001", "source_map_002"],
            "approval": {"status": "human_frozen", "reviewer": "reviewer", "frozen_on": "2026-08-20"},
            "execution_boundary": "Literature-bound planning only; no external execution is authorized.",
        }

    def _passport(self, model_id: str) -> dict:
        return {
            "schema_version": "1.0",
            "trust_status": "human_reviewed_literature_bound_potential_passport",
            "system_spec_sha256": system_spec_sha256(self.spec),
            "model_id": model_id,
            "implementation": "reviewed external implementation",
            "version_or_commit": "reviewed-version",
            "artifact_sha256": "b" * 64,
            "license_or_terms": "reviewed terms",
            "training_envelope_status": "declared_only",
            "declared_training_axes": [{"axis_id": "strain_percent", "description": "literature-declared strain coverage", "source_ids": ["source_map_001"]}],
            "supports_observables": ["forces"],
            "known_limitations": ["Boundary remains to be tested."],
            "literature_source_ids": ["source_map_001"],
            "review": {"status": "human_reviewed", "reviewer": "reviewer", "reviewed_on": "2026-08-20"},
        }

    def _matrix(self) -> dict:
        return {
            "schema_version": "1.0",
            "trust_status": "human_reviewed_literature_condition_matrix",
            "system_spec_sha256": system_spec_sha256(self.spec),
            "cells": [
                {"cell_id": "cell_001", "condition_values": {"strain_percent": 0.0, "temperature_k": 300.0}, "coverage_role": "reported", "literature_source_ids": ["source_map_001"]},
                {"cell_id": "cell_002", "condition_values": {"strain_percent": 2.0, "temperature_k": 900.0}, "coverage_role": "coverage_gap", "literature_source_ids": ["source_map_002"]},
            ],
            "review": {"status": "human_reviewed", "reviewer": "reviewer", "reviewed_on": "2026-08-20"},
        }

    def test_frozen_artifacts_make_a_plugin_request_without_execution(self) -> None:
        spec = build_system_spec(self.spec)
        passports = [build_potential_passport(system_spec=spec, payload=self._passport(model)) for model in spec["potential_model_ids"]]
        matrix = build_condition_matrix(system_spec=spec, payload=self._matrix())
        request = build_plugin_request(system_spec=spec, passports=passports, condition_matrix=matrix)
        self.assertEqual(request["literature_source_ids"], ["source_map_001", "source_map_002"])
        result = default_task_plugin_registry().plan(machine=machine_config_template(), request=request)
        self.assertEqual({card["approval_state"] for card in result["proposed_test_cards"]}, {"proposed"})
        self.assertTrue(all(not card["execution_permitted"] for card in result["proposed_test_cards"]))

    def test_rejects_unfrozen_source_or_out_of_range_matrix_value(self) -> None:
        invalid_spec = copy.deepcopy(self.spec)
        invalid_spec["condition_axes"][0]["source_ids"] = ["unreviewed_source"]
        with self.assertRaises(PotentialScopeIntakeError):
            build_system_spec(invalid_spec)
        invalid_matrix = self._matrix()
        invalid_matrix["cells"][0]["condition_values"]["temperature_k"] = 9000.0
        with self.assertRaises(PotentialScopeIntakeError):
            build_condition_matrix(system_spec=self.spec, payload=invalid_matrix)

    def test_passport_requires_known_envelope_to_cite_axes(self) -> None:
        unknown = self._passport("potential_a")
        unknown["training_envelope_status"] = "training_envelope_unknown"
        with self.assertRaises(PotentialScopeIntakeError):
            build_potential_passport(system_spec=self.spec, payload=unknown)
        unknown["declared_training_axes"] = []
        self.assertEqual(
            build_potential_passport(system_spec=self.spec, payload=unknown)["training_envelope_status"],
            "training_envelope_unknown",
        )

    def test_autonomy_template_forbids_all_execution(self) -> None:
        policy = autonomy_policy_template(self.spec)
        self.assertEqual(policy["budgets"], {"dft_tasks": 0, "gpu_tasks": 0, "external_calls": 0})
        self.assertIn("dft_submission", policy["forbidden_actions"])


if __name__ == "__main__":
    unittest.main()
