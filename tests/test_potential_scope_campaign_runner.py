from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from cosmatter.machine_config import machine_config_template
from cosmatter.potential_scope_campaign_runner import build_plan_only_campaign, campaign_sha256, write_plan_only_campaign
from cosmatter.potential_scope_intake import build_system_spec, system_spec_sha256


def _fixture() -> dict[str, object]:
    source_id = "ps_src_0123456789abcdef"
    registry = {"schema_version": "1.0", "mission_id": "mission_synthetic", "trust_status": "human_reviewed_private_source_registry_not_evidence", "sources": [{"source_id": source_id, "document_id": "synthetic_doc", "source_markdown_sha256": "a" * 64, "task_id_sha256": "b" * 64, "selection_sha256": "c" * 64, "selected_segment_count": 1}], "review_boundary": "Synthetic fixture."}
    spec = {"schema_version": "1.0", "trust_status": "human_frozen_literature_bound_system_spec", "system_spec_id": "synthetic_scope", "material_systems": ["SyntheticMaterial"], "scope_description": "Synthetic plan-only scope.", "target_observables": ["relative_phase_energy"], "condition_axes": [{"axis_id": "strain_percent", "unit": "percent", "lower_bound": -1.0, "upper_bound": 1.0, "source_ids": [source_id]}], "potential_model_ids": ["model_a", "model_b"], "reference_method": "synthetic_reference", "pre_registered_metrics": ["energy_mae_ev_per_atom"], "literature_source_ids": [source_id], "approval": {"status": "human_frozen", "reviewer": "Synthetic Reviewer", "frozen_on": "2026-08-20"}, "execution_boundary": "Planning only."}
    frozen = build_system_spec(spec)
    passports = [{"schema_version": "1.0", "trust_status": "human_reviewed_literature_bound_potential_passport", "system_spec_sha256": system_spec_sha256(frozen), "model_id": model, "implementation": "synthetic", "version_or_commit": "v1", "artifact_sha256": hashlib.sha256(model.encode("utf-8")).hexdigest(), "license_or_terms": "synthetic terms", "training_envelope_status": "training_envelope_unknown", "declared_training_axes": [], "supports_observables": ["relative_phase_energy"], "known_limitations": ["synthetic limitation"], "literature_source_ids": [source_id], "review": {"status": "human_reviewed", "reviewer": "Synthetic Reviewer", "reviewed_on": "2026-08-20"}} for model in ("model_a", "model_b")]
    matrix = {"schema_version": "1.0", "trust_status": "human_reviewed_literature_condition_matrix", "system_spec_sha256": system_spec_sha256(frozen), "cells": [{"cell_id": "cell_01", "condition_values": {"strain_percent": 0.0}, "coverage_role": "conflict_candidate", "literature_source_ids": [source_id]}], "review": {"status": "human_reviewed", "reviewer": "Synthetic Reviewer", "reviewed_on": "2026-08-20"}}
    return {"machine": machine_config_template(), "reviewed_source_registry": registry, "system_spec": spec, "passports": passports, "condition_matrix": matrix}


class PotentialScopeCampaignRunnerTests(unittest.TestCase):
    def test_complete_frozen_artifacts_automatically_make_only_a_nonexecuting_campaign(self) -> None:
        campaign = build_plan_only_campaign(**_fixture())
        self.assertEqual(campaign["campaign_state"], "planned")
        self.assertEqual([item["plugin_id"] for item in campaign["plugin_trace"]], ["potential_scope.campaign_preflight", "potential_scope.plan_only_test_cards", "potential_scope.prioritize_test_cards"])
        self.assertTrue(all(item["execution_permitted"] is False and item["approval_state"] == "proposed" for item in campaign["prioritized_queue"]["proposed_queue"]))
        self.assertEqual(len(campaign_sha256(campaign)), 64)

    def test_incomplete_artifacts_terminate_at_the_preflight_gate(self) -> None:
        campaign = build_plan_only_campaign(machine=None, reviewed_source_registry=None, system_spec=None, passports=None, condition_matrix=None)
        self.assertEqual(campaign["campaign_state"], "blocked")
        self.assertIsNone(campaign["frozen_plan"])
        self.assertEqual(len(campaign["plugin_trace"]), 1)

    def test_safe_campaign_can_be_written_once_outside_private_and_run_locations(self) -> None:
        campaign = build_plan_only_campaign(**_fixture())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "potential_scope_campaign.json"
            self.assertEqual(write_plan_only_campaign(path, campaign), path)
            self.assertTrue(path.is_file())


if __name__ == "__main__":
    unittest.main()
