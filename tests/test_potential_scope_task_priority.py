from __future__ import annotations

import hashlib
import unittest

from cosmatter.machine_config import machine_config_template
from cosmatter.potential_scope_frozen_plan import build_frozen_plugin_plan
from cosmatter.potential_scope_intake import build_system_spec, system_spec_sha256
from cosmatter.potential_scope_task_priority import prioritize_proposed_test_cards


class PotentialScopeTaskPriorityTests(unittest.TestCase):
    def _fixtures(self):
        source_id = "ps_src_0123456789abcdef"
        registry = {"schema_version": "1.0", "mission_id": "mission_01", "trust_status": "human_reviewed_private_source_registry_not_evidence", "sources": [{"source_id": source_id, "document_id": "doc_01", "source_markdown_sha256": "a" * 64, "task_id_sha256": "b" * 64, "selection_sha256": "c" * 64, "selected_segment_count": 1}], "review_boundary": "Synthetic registry."}
        spec = {"schema_version": "1.0", "trust_status": "human_frozen_literature_bound_system_spec", "system_spec_id": "synthetic_scope", "material_systems": ["SyntheticMaterial"], "scope_description": "Synthetic scope.", "target_observables": ["relative_phase_energy"], "condition_axes": [{"axis_id": "strain_percent", "unit": "percent", "lower_bound": -1.0, "upper_bound": 1.0, "source_ids": [source_id]}], "potential_model_ids": ["model_a", "model_b"], "reference_method": "synthetic_reference", "pre_registered_metrics": ["energy_mae_ev_per_atom"], "literature_source_ids": [source_id], "approval": {"status": "human_frozen", "reviewer": "Reviewer", "frozen_on": "2026-08-20"}, "execution_boundary": "Planning only."}
        frozen_spec = build_system_spec(spec)
        passports = [{"schema_version": "1.0", "trust_status": "human_reviewed_literature_bound_potential_passport", "system_spec_sha256": system_spec_sha256(frozen_spec), "model_id": model, "implementation": "synthetic", "version_or_commit": "v1", "artifact_sha256": hashlib.sha256(model.encode()).hexdigest(), "license_or_terms": "synthetic terms", "training_envelope_status": "training_envelope_unknown", "declared_training_axes": [], "supports_observables": ["relative_phase_energy"], "known_limitations": ["synthetic limitation"], "literature_source_ids": [source_id], "review": {"status": "human_reviewed", "reviewer": "Reviewer", "reviewed_on": "2026-08-20"}} for model in ("model_a", "model_b")]
        matrix = {"schema_version": "1.0", "trust_status": "human_reviewed_literature_condition_matrix", "system_spec_sha256": system_spec_sha256(frozen_spec), "cells": [{"cell_id": "cell_01", "condition_values": {"strain_percent": 0.0}, "coverage_role": "conflict_candidate", "literature_source_ids": [source_id]}], "review": {"status": "human_reviewed", "reviewer": "Reviewer", "reviewed_on": "2026-08-20"}}
        plan = build_frozen_plugin_plan(machine=machine_config_template(), system_spec=spec, passports=passports, condition_matrix=matrix, reviewed_source_registry=registry)
        return plan, spec, passports, matrix

    def test_conflict_candidate_is_ranked_without_execution_permission(self) -> None:
        plan, spec, passports, matrix = self._fixtures()
        queue = prioritize_proposed_test_cards(frozen_plan=plan, system_spec=spec, passports=passports, condition_matrix=matrix)
        self.assertEqual(queue["proposed_queue"][0]["plugin_id"], "reference_label")
        self.assertTrue(any(item["priority_band"] == "high" for item in queue["proposed_queue"]))
        self.assertTrue(all(item["approval_state"] == "proposed" and item["execution_permitted"] is False for item in queue["proposed_queue"]))
        self.assertIn("literature_condition_conflict_candidate", queue["proposed_queue"][0]["priority_reasons"])


if __name__ == "__main__":
    unittest.main()
