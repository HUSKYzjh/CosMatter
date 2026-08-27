from __future__ import annotations

import copy
import hashlib
import tempfile
import unittest
from pathlib import Path

from cosmatter.machine_config import machine_config_template
from cosmatter.potential_scope_frozen_plan import (
    PotentialScopeFrozenPlanError,
    build_frozen_plugin_plan,
    write_frozen_plugin_plan,
)
from cosmatter.potential_scope_intake import system_spec_sha256


class PotentialScopeFrozenPlanTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source_id = "ps_src_0123456789abcdef"
        self.registry = {
            "schema_version": "1.0",
            "mission_id": "fixture_review_mission",
            "trust_status": "human_reviewed_private_source_registry_not_evidence",
            "sources": [
                {
                    "source_id": self.source_id,
                    "document_id": "fixture_document",
                    "source_markdown_sha256": "a" * 64,
                    "task_id_sha256": "b" * 64,
                    "selection_sha256": "c" * 64,
                    "selected_segment_count": 1,
                }
            ],
            "review_boundary": "Synthetic fixture only; not a scientific conclusion.",
        }
        self.spec = {
            "schema_version": "1.0",
            "trust_status": "human_frozen_literature_bound_system_spec",
            "system_spec_id": "fixture_scope_v1",
            "material_systems": ["SyntheticMaterial"],
            "scope_description": "Synthetic fixture for non-executing plugin planning.",
            "target_observables": ["forces"],
            "condition_axes": [
                {"axis_id": "strain_percent", "unit": "percent", "lower_bound": -1.0, "upper_bound": 1.0, "source_ids": [self.source_id]},
                {"axis_id": "temperature_k", "unit": "K", "lower_bound": 300.0, "upper_bound": 600.0, "source_ids": [self.source_id]},
                {"axis_id": "defect_fraction", "unit": "fraction", "lower_bound": 0.0, "upper_bound": 0.1, "source_ids": [self.source_id]},
            ],
            "potential_model_ids": ["model_a", "model_b"],
            "reference_method": "synthetic human-approved reference",
            "pre_registered_metrics": ["energy_mae_ev_per_atom"],
            "literature_source_ids": [self.source_id],
            "approval": {"status": "human_frozen", "reviewer": "fixture", "frozen_on": "2026-08-20"},
            "execution_boundary": "Synthetic fixture has no execution authority.",
        }

    def _passport(self, model_id: str) -> dict:
        return {
            "schema_version": "1.0",
            "trust_status": "human_reviewed_literature_bound_potential_passport",
            "system_spec_sha256": system_spec_sha256(self.spec),
            "model_id": model_id,
            "implementation": "synthetic implementation",
            "version_or_commit": "fixture-v1",
            "artifact_sha256": hashlib.sha256(model_id.encode("utf-8")).hexdigest(),
            "license_or_terms": "synthetic terms reviewed by fixture",
            "training_envelope_status": "training_envelope_unknown",
            "declared_training_axes": [],
            "supports_observables": ["forces"],
            "known_limitations": ["Synthetic fixture only."],
            "literature_source_ids": [self.source_id],
            "review": {"status": "human_reviewed", "reviewer": "fixture", "reviewed_on": "2026-08-20"},
        }

    def _matrix(self) -> dict:
        return {
            "schema_version": "1.0",
            "trust_status": "human_reviewed_literature_condition_matrix",
            "system_spec_sha256": system_spec_sha256(self.spec),
            "cells": [
                {
                    "cell_id": "fixture_cell",
                    "condition_values": {"strain_percent": 0.0, "temperature_k": 300.0, "defect_fraction": 0.0},
                    "coverage_role": "reported",
                    "literature_source_ids": [self.source_id],
                }
            ],
            "review": {"status": "human_reviewed", "reviewer": "fixture", "reviewed_on": "2026-08-20"},
        }

    def test_binds_registered_sources_and_writes_only_proposed_cards(self) -> None:
        plan = build_frozen_plugin_plan(
            machine=machine_config_template(),
            system_spec=self.spec,
            passports=[self._passport("model_a"), self._passport("model_b")],
            condition_matrix=self._matrix(),
            reviewed_source_registry=self.registry,
        )
        self.assertEqual(plan["machine_execution_mode"], "plan_only")
        self.assertEqual(plan["literature_source_ids"], [self.source_id])
        self.assertTrue(all(card["approval_state"] == "proposed" for card in plan["proposal"]["proposed_test_cards"]))
        self.assertTrue(all(card["execution_permitted"] is False for card in plan["proposal"]["proposed_test_cards"]))
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "frozen_plan.json"
            write_frozen_plugin_plan(path, plan)
            self.assertNotIn("Synthetic fixture only.", path.read_text(encoding="utf-8"))

    def test_rejects_system_spec_source_absent_from_registry(self) -> None:
        invalid = copy.deepcopy(self.spec)
        invalid["literature_source_ids"] = ["ps_src_missing"]
        invalid["condition_axes"][0]["source_ids"] = ["ps_src_missing"]
        with self.assertRaises(PotentialScopeFrozenPlanError):
            build_frozen_plugin_plan(
                machine=machine_config_template(),
                system_spec=invalid,
                passports=[self._passport("model_a"), self._passport("model_b")],
                condition_matrix=self._matrix(),
                reviewed_source_registry=self.registry,
            )


if __name__ == "__main__":
    unittest.main()
