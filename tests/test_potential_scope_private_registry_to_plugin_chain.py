from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from cosmatter.machine_config import machine_config_template
from cosmatter.mineru_local_review import (
    prepare_mineru_markdown_review_pool,
    source_map_pool_review_template,
)
from cosmatter.potential_scope_intake import (
    build_condition_matrix,
    build_plugin_request,
    build_potential_passport,
    build_system_spec,
    system_spec_sha256,
)
from cosmatter.potential_scope_review_registry import (
    build_reviewed_source_registry,
    load_reviewed_source,
    write_reviewed_source_registry,
)
from cosmatter.potential_task_plugins import default_task_plugin_registry


class PotentialScopePrivateRegistryToPluginChainTests(unittest.TestCase):
    def test_reviewed_private_source_id_can_seed_only_zero_execution_proposals(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            markdown = root / "private.md"
            markdown.write_text("Synthetic private excerpt used only to exercise the reviewer boundary.", encoding="utf-8")
            task = {"document_id": "potential_scope_p0_fixture", "provider": "mineru", "state": "done", "task_id": "private_fixture_task"}
            pool_path = root / "pool.json"
            pool = prepare_mineru_markdown_review_pool(
                mission_id="potential_scope_fixture",
                document_id=task["document_id"],
                source_task=task,
                input_path=markdown,
                output_path=pool_path,
            )
            review = source_map_pool_review_template(pool)
            review["trust_status"] = "human_reviewed_source_map_pool_selection"
            review["segments"][0]["selected"] = True
            review["segments"][0]["reason"] = "Synthetic reviewer confirmation for a test fixture."
            review_path = root / "review.json"
            review_path.write_text(json.dumps(review), encoding="utf-8")
            source = load_reviewed_source(
                mission_id="potential_scope_fixture",
                document_id=task["document_id"],
                source_task=task,
                pool_path=pool_path,
                review_path=review_path,
            )
            registry_path = root / "registry.json"
            write_reviewed_source_registry(
                registry_path,
                build_reviewed_source_registry(mission_id="potential_scope_fixture", entries=[source]),
            )
            source_id = source["source_id"]
            spec = build_system_spec(
                {
                    "schema_version": "1.0",
                    "trust_status": "human_frozen_literature_bound_system_spec",
                    "system_spec_id": "synthetic_scope_v1",
                    "material_systems": ["SyntheticMaterial"],
                    "scope_description": "Synthetic fixture proving a literature-bound planning chain.",
                    "target_observables": ["forces", "relative_phase_energy"],
                    "condition_axes": [
                        {"axis_id": "strain_percent", "unit": "percent", "lower_bound": -1.0, "upper_bound": 1.0, "source_ids": [source_id]},
                        {"axis_id": "temperature_k", "unit": "K", "lower_bound": 300.0, "upper_bound": 600.0, "source_ids": [source_id]},
                        {"axis_id": "defect_fraction", "unit": "fraction", "lower_bound": 0.0, "upper_bound": 0.1, "source_ids": [source_id]},
                    ],
                    "potential_model_ids": ["synthetic_model_a", "synthetic_model_b"],
                    "reference_method": "human-approved synthetic reference fixture",
                    "pre_registered_metrics": ["energy_mae_ev_per_atom"],
                    "literature_source_ids": [source_id],
                    "approval": {"status": "human_frozen", "reviewer": "fixture_reviewer", "frozen_on": "2026-08-20"},
                    "execution_boundary": "Synthetic planning fixture; no calculation or external call is authorized.",
                }
            )
            passports = [
                build_potential_passport(
                    system_spec=spec,
                    payload={
                        "schema_version": "1.0",
                        "trust_status": "human_reviewed_literature_bound_potential_passport",
                        "system_spec_sha256": system_spec_sha256(spec),
                        "model_id": model_id,
                        "implementation": "synthetic implementation",
                        "version_or_commit": "fixture-v1",
                        "artifact_sha256": hashlib.sha256(model_id.encode("utf-8")).hexdigest(),
                        "license_or_terms": "synthetic reviewed terms",
                        "training_envelope_status": "training_envelope_unknown",
                        "declared_training_axes": [],
                        "supports_observables": ["forces"],
                        "known_limitations": ["Synthetic fixture has no scientific applicability."],
                        "literature_source_ids": [source_id],
                        "review": {"status": "human_reviewed", "reviewer": "fixture_reviewer", "reviewed_on": "2026-08-20"},
                    },
                )
                for model_id in spec["potential_model_ids"]
            ]
            matrix = build_condition_matrix(
                system_spec=spec,
                payload={
                    "schema_version": "1.0",
                    "trust_status": "human_reviewed_literature_condition_matrix",
                    "system_spec_sha256": system_spec_sha256(spec),
                    "cells": [
                        {
                            "cell_id": "fixture_cell_1",
                            "condition_values": {"strain_percent": 0.0, "temperature_k": 300.0, "defect_fraction": 0.0},
                            "coverage_role": "reported",
                            "literature_source_ids": [source_id],
                        }
                    ],
                    "review": {"status": "human_reviewed", "reviewer": "fixture_reviewer", "reviewed_on": "2026-08-20"},
                },
            )
            request = build_plugin_request(system_spec=spec, passports=passports, condition_matrix=matrix)
            proposal = default_task_plugin_registry().plan(machine=machine_config_template(), request=request)
            written_registry = registry_path.read_text(encoding="utf-8")
            self.assertEqual(proposal["selected_plugin_ids"], ["defect_boundary", "finite_temperature", "reference_label", "static_property", "strain_path"])
            self.assertTrue(all(card["approval_state"] == "proposed" for card in proposal["proposed_test_cards"]))
            self.assertTrue(all(card["execution_permitted"] is False for card in proposal["proposed_test_cards"]))
            self.assertEqual(proposal["machine_execution_mode"], "plan_only")
            self.assertNotIn("Synthetic private excerpt", written_registry)
            self.assertNotIn("fixture_reviewer", written_registry)


if __name__ == "__main__":
    unittest.main()
