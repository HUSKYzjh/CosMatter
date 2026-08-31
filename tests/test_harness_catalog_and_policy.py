from __future__ import annotations

import unittest

from cosmatter.harness_catalog import CosMatterHarnessCatalogue
from cosmatter.harness_policy import MissionAuthorization, evaluate_mission_authorization
from cosmatter.harness_receipts import PluginExecutionReceipt, PluginReceiptError


class HarnessCatalogueAndPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalogue = CosMatterHarnessCatalogue()

    def test_catalogue_covers_existing_evidence_closure_without_executors(self) -> None:
        manifests = self.catalogue.manifests()
        ids = {item["plugin_id"] for item in manifests}
        self.assertTrue({"mission.define", "literature.plan_draft", "literature.metadata_retrieval", "document.mineru_private_parse", "evidence.verify", "run_package.continue", "potential_scope.plan_only"}.issubset(ids))
        self.assertTrue(all("scheduler submission" in item["execution_boundary"] for item in manifests))

    def test_external_plugin_needs_all_explicit_consents(self) -> None:
        decision = evaluate_mission_authorization(
            self.catalogue,
            MissionAuthorization("mission-001", "document.mineru_private_parse", ("mission_scoped_egress_consent",)),
        )
        self.assertFalse(decision["permitted"])
        self.assertIn("private_content_to_mineru", decision["missing_authorizations"])

    def test_research_plan_draft_needs_the_deepseek_consent_pair(self) -> None:
        decision = evaluate_mission_authorization(
            self.catalogue,
            MissionAuthorization("mission-001", "literature.plan_draft", ("mission_scoped_egress_consent",)),
        )
        self.assertFalse(decision["permitted"])
        self.assertIn("deepseek_request_consent", decision["missing_authorizations"])

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

    def test_graph_export_has_a_versioned_read_only_contract(self) -> None:
        graph_export = self.catalogue.describe("graph.export_projection")
        self.assertEqual(graph_export["api_version"], "2.0")
        self.assertEqual(graph_export["contract"]["input_schema"], "cosmatter.graph-snapshot/v1")
        self.assertEqual(graph_export["contract"]["execution_mode"], "read_only_projection")

    def test_graph_plan_is_declared_as_plan_only_and_review_required(self) -> None:
        graph_plan = self.catalogue.describe("graph.plan")
        self.assertEqual(graph_plan["contract"]["execution_mode"], "plan_only")
        self.assertTrue(graph_plan["requires_human_review"])

    def test_graph_model_plan_needs_explicit_deepseek_consent(self) -> None:
        decision = evaluate_mission_authorization(
            self.catalogue,
            MissionAuthorization("mission-001", "graph.plan_assist", ("mission_scoped_egress_consent",)),
        )
        self.assertFalse(decision["permitted"])
        self.assertIn("deepseek_request_consent", decision["missing_authorizations"])

    def test_graph_review_request_cannot_be_misdescribed_as_a_release(self) -> None:
        review = self.catalogue.describe("graph.review_request")
        self.assertEqual(review["contract"]["execution_mode"], "pending_human_review_only")

    def test_execution_receipt_never_claims_evidence_acceptance(self) -> None:
        receipt = PluginExecutionReceipt("mission-001", "graph.export_projection", "authorization-001", "completed", ("a" * 64,))
        self.assertEqual(receipt.as_audit_payload()["trust_status"], "adapter_execution_receipt_not_evidence_acceptance")
        with self.assertRaises(PluginReceiptError):
            PluginExecutionReceipt("mission-001", "graph.export_projection", "authorization-001", "completed")


if __name__ == "__main__":
    unittest.main()
