from __future__ import annotations

import unittest

from cosmatter.harness_catalog import CosMatterHarnessCatalogue
from cosmatter.harness_policy import MissionAuthorization, evaluate_mission_authorization


class HarnessCatalogueAndPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalogue = CosMatterHarnessCatalogue()

    def test_catalogue_covers_existing_evidence_closure_without_executors(self) -> None:
        manifests = self.catalogue.manifests()
        ids = {item["plugin_id"] for item in manifests}
        self.assertTrue({"mission.define", "literature.metadata_retrieval", "document.mineru_private_parse", "evidence.verify", "run_package.continue", "potential_scope.plan_only"}.issubset(ids))
        self.assertTrue(all("scheduler submission" in item["execution_boundary"] for item in manifests))

    def test_external_plugin_needs_all_explicit_consents(self) -> None:
        decision = evaluate_mission_authorization(
            self.catalogue,
            MissionAuthorization("mission-001", "document.mineru_private_parse", ("mission_scoped_egress_consent",)),
        )
        self.assertFalse(decision["permitted"])
        self.assertIn("private_content_to_mineru", decision["missing_authorizations"])

    def test_human_evidence_gate_cannot_be_automatically_permitted(self) -> None:
        decision = evaluate_mission_authorization(
            self.catalogue,
            MissionAuthorization("mission-001", "evidence.verify", ()),
        )
        self.assertFalse(decision["permitted"])
        self.assertEqual(decision["reason"], "human_review_required")

    def test_local_derivation_is_permitted_but_not_executed(self) -> None:
        decision = evaluate_mission_authorization(
            self.catalogue,
            MissionAuthorization("mission-001", "planning.orchestrate", ()),
        )
        self.assertTrue(decision["permitted"])
        self.assertEqual(decision["reason"], "permitted_to_dispatch_not_yet_executed")


if __name__ == "__main__":
    unittest.main()
