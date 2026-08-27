from __future__ import annotations

import unittest

from cosmatter.potential_scope_campaign_templates import build_post_system_spec_completion_pack, build_registry_completion_pack


class PotentialScopeCampaignTemplatesTests(unittest.TestCase):
    def test_stage_one_seeds_only_source_ids_and_stays_unfrozen(self) -> None:
        source_id = "ps_src_0123456789abcdef"
        registry = {"schema_version": "1.0", "mission_id": "mission_synthetic", "trust_status": "human_reviewed_private_source_registry_not_evidence", "sources": [{"source_id": source_id, "document_id": "synthetic_doc", "source_markdown_sha256": "a" * 64, "task_id_sha256": "b" * 64, "selection_sha256": "c" * 64, "selected_segment_count": 1}], "review_boundary": "Synthetic fixture."}
        pack = build_registry_completion_pack(reviewed_source_registry=registry)
        self.assertIn(source_id, pack["system_spec_template"]["literature_source_ids"])
        self.assertIn("not_frozen", pack["trust_status"])

    def test_stage_two_requires_a_frozen_spec_and_never_proposes_cards(self) -> None:
        source_id = "ps_src_0123456789abcdef"
        spec = {"schema_version": "1.0", "trust_status": "human_frozen_literature_bound_system_spec", "system_spec_id": "synthetic_scope", "material_systems": ["SyntheticMaterial"], "scope_description": "Synthetic planning scope.", "target_observables": ["relative_phase_energy"], "condition_axes": [{"axis_id": "strain_percent", "unit": "percent", "lower_bound": -1.0, "upper_bound": 1.0, "source_ids": [source_id]}], "potential_model_ids": ["model_a", "model_b"], "reference_method": "synthetic_reference", "pre_registered_metrics": ["energy_mae_ev_per_atom"], "literature_source_ids": [source_id], "approval": {"status": "human_frozen", "reviewer": "Synthetic Reviewer", "frozen_on": "2026-08-20"}, "execution_boundary": "Planning only."}
        pack = build_post_system_spec_completion_pack(system_spec=spec)
        self.assertEqual(pack["potential_model_ids_in_required_order"], ["model_a", "model_b"])
        self.assertNotIn("proposed_test_cards", str(pack))
        self.assertEqual(pack["autonomy_policy_template"]["budgets"], {"dft_tasks": 0, "gpu_tasks": 0, "external_calls": 0})


if __name__ == "__main__":
    unittest.main()
