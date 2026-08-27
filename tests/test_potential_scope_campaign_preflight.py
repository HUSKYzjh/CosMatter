from __future__ import annotations

import copy
import hashlib
import unittest

from cosmatter.machine_config import machine_config_template
from cosmatter.potential_scope_campaign_preflight import inspect_campaign
from cosmatter.potential_scope_intake import build_system_spec, system_spec_sha256


class PotentialScopeCampaignPreflightTests(unittest.TestCase):
    def test_empty_campaign_is_blocked_and_never_execution_ready(self) -> None:
        report = inspect_campaign(machine=None, reviewed_source_registry=None, system_spec=None, passports=None, condition_matrix=None)
        self.assertFalse(report["ready_for_plan_only_proposal"])
        self.assertFalse(report["stages"]["plugin_plan"]["execution_permitted"])
        self.assertIn("human_reviewed_source_registry_missing_or_invalid", report["blocking_reasons"])

    def test_complete_synthetic_frozen_chain_is_ready_for_plan_only(self) -> None:
        source_id = "ps_src_0123456789abcdef"
        registry = {"schema_version": "1.0", "mission_id": "mission_01", "trust_status": "human_reviewed_private_source_registry_not_evidence", "sources": [{"source_id": source_id, "document_id": "document_01", "source_markdown_sha256": "a" * 64, "task_id_sha256": "b" * 64, "selection_sha256": "c" * 64, "selected_segment_count": 1}], "review_boundary": "Synthetic reviewed registry only."}
        spec = {"schema_version": "1.0", "trust_status": "human_frozen_literature_bound_system_spec", "system_spec_id": "synthetic_scope", "material_systems": ["SyntheticMaterial"], "scope_description": "Synthetic planning fixture.", "target_observables": ["relative_phase_energy"], "condition_axes": [{"axis_id": "strain_percent", "unit": "percent", "lower_bound": -1.0, "upper_bound": 1.0, "source_ids": [source_id]}], "potential_model_ids": ["model_a", "model_b"], "reference_method": "synthetic_reference", "pre_registered_metrics": ["energy_mae_ev_per_atom"], "literature_source_ids": [source_id], "approval": {"status": "human_frozen", "reviewer": "Synthetic Reviewer", "frozen_on": "2026-08-20"}, "execution_boundary": "Planning only."}
        frozen_spec = build_system_spec(spec)
        passports = []
        for model_id in ("model_a", "model_b"):
            passports.append({"schema_version": "1.0", "trust_status": "human_reviewed_literature_bound_potential_passport", "system_spec_sha256": system_spec_sha256(frozen_spec), "model_id": model_id, "implementation": "synthetic", "version_or_commit": "v1", "artifact_sha256": hashlib.sha256(model_id.encode()).hexdigest(), "license_or_terms": "synthetic terms", "training_envelope_status": "training_envelope_unknown", "declared_training_axes": [], "supports_observables": ["relative_phase_energy"], "known_limitations": ["synthetic fixture"], "literature_source_ids": [source_id], "review": {"status": "human_reviewed", "reviewer": "Synthetic Reviewer", "reviewed_on": "2026-08-20"}})
        matrix = {"schema_version": "1.0", "trust_status": "human_reviewed_literature_condition_matrix", "system_spec_sha256": system_spec_sha256(frozen_spec), "cells": [{"cell_id": "cell_01", "condition_values": {"strain_percent": 0.0}, "coverage_role": "reported", "literature_source_ids": [source_id]}], "review": {"status": "human_reviewed", "reviewer": "Synthetic Reviewer", "reviewed_on": "2026-08-20"}}
        report = inspect_campaign(machine=machine_config_template(), reviewed_source_registry=registry, system_spec=spec, passports=passports, condition_matrix=matrix)
        self.assertTrue(report["ready_for_plan_only_proposal"])
        self.assertEqual(report["stages"]["plugin_plan"]["proposed_test_card_count"], 3)
        self.assertFalse(report["stages"]["plugin_plan"]["execution_permitted"])


if __name__ == "__main__":
    unittest.main()
