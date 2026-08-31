from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cosmatter.deepseek import DraftCompletion
from cosmatter.local_api import LocalApiError, LocalMissionApi
from cosmatter.models import AccessPolicy, EvidenceCard, Provenance, ReviewStatus, Stance
from cosmatter.verification import VerificationDecision


class LocalApiGraphTests(unittest.TestCase):
    def test_graph_projection_persists_only_minimized_accepted_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            api = LocalMissionApi(Path(directory) / "runs")
            created = api.create_mission({
                "question": "How does strain change phase stability?", "material": "BiFeO3",
                "property": "phase stability", "scope": "epitaxial films", "run_id": "bfo_graph",
            })
            run_dir = api.runs_dir / "bfo_graph"
            card = EvidenceCard(
                "Reviewed claim", Stance.SUPPORT, "BiFeO3", "phase stability", {"strain_percent": 1.2},
                "private quotation must remain local", Provenance("doc-1", "markdown_line:1-2", "fixture", access_policy=AccessPolicy.AUTHORIZED),
                evidence_id="evidence-1",
            )
            decision = VerificationDecision(str(created["mission_id"]), "evidence-1", ReviewStatus.ACCEPTED, "reviewed")
            (run_dir / "evidence_cards.json").write_text(json.dumps([card.to_dict()]), encoding="utf-8")
            (run_dir / "verification_decisions.json").write_text(json.dumps([decision.to_dict()]), encoding="utf-8")

            payload = api.project_accepted_evidence_graph("bfo_graph")
            read_back = api.graph_projection("bfo_graph")

            self.assertTrue((run_dir / "graph_snapshot.json").is_file())
            self.assertEqual(payload["trust_status"], "accepted_evidence_projection_not_scientific_conclusion")
            self.assertEqual(read_back["graph_id"], payload["graph_id"])
            self.assertNotIn("private quotation", (run_dir / "graph_snapshot.json").read_text(encoding="utf-8"))
            self.assertIn("plugin_execution_receipt", (run_dir / "events.jsonl").read_text(encoding="utf-8"))
            review = api.request_graph_review("bfo_graph", {"node_ids": [next(node["node_id"] for node in payload["nodes"] if node["node_type"] == "EvidenceCard")], "rationale": "Check the relation semantics."})
            self.assertEqual(review["status"], "pending_human_review_not_evidence_acceptance")
            draft = api.draft_graph_plan("bfo_graph", {"node_ids": [review["node_ids"][0]], "intent": "Inspect the accepted-evidence relation."})
            self.assertEqual(draft["trust_status"], "untrusted_graph_plan_draft_not_execution_or_evidence_acceptance")
            self.assertTrue((run_dir / "graph_plan_drafts.jsonl").is_file())
            approval = api.approve_graph_plan("bfo_graph", {"plan_id": draft["plan_id"], "reviewer": "researcher", "rationale": "Reviewed for a non-executing follow-up."})
            self.assertEqual(approval["status"], "human_approved_graph_plan_follow_up_not_execution_or_evidence_acceptance")
            self.assertTrue((run_dir / "graph_plan_approvals.jsonl").is_file())
            with self.assertRaises(LocalApiError):
                api.assist_authorized_graph_plan("bfo_graph", {"node_ids": [review["node_ids"][0]], "intent": "Inspect relation semantics.", "authorizations": []})
            response = json.dumps({"suggestions": [{"node_ids": [review["node_ids"][0]], "proposed_action": "request_human_to_review_or_project_graph", "uncertainty": "Human review is still required."}]})
            request = {"node_ids": [review["node_ids"][0]], "intent": "Inspect relation semantics.", "authorizations": ["mission_scoped_egress_consent", "deepseek_request_consent"], "dsh_call_id": "graph-model-plan-0001"}
            with patch("cosmatter.local_api.DeepSeekAdapter.draft", return_value=DraftCompletion(response, "deepseek-test", None)):
                model_draft = api.assist_authorized_graph_plan("bfo_graph", request)
                repeated = api.assist_authorized_graph_plan("bfo_graph", request)
            self.assertEqual(model_draft["trust_status"], "untrusted_graph_model_plan_not_execution_or_evidence_acceptance")
            self.assertEqual(repeated["idempotency_status"], "duplicate_completed")
            self.assertTrue((run_dir / "graph_model_plan_drafts.jsonl").is_file())
            ledger = json.loads((run_dir / "external_dispatch_ledger.json").read_text(encoding="utf-8"))
            self.assertEqual(ledger["entries"][-1]["operation"], "deepseek_graph_plan_draft")
            self.assertEqual(ledger["entries"][-1]["state"], "completed")

    def test_accepted_evidence_search_returns_reviewed_pointers_without_quotes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            api = LocalMissionApi(Path(directory) / "runs")
            created = api.create_mission({"run_id": "search_graph", "question": "How does strain affect phase stability?", "material": "BiFeO3", "property": "phase stability", "scope": "thin films"})
            run_dir = api.runs_dir / "search_graph"
            card = EvidenceCard("Strain shifts phase stability in a reviewed condition.", Stance.SUPPORT, "BiFeO3", "phase stability", {"strain_percent": 1.0}, "private source quote", Provenance("doc_search", "figure:2", "fixture", access_policy=AccessPolicy.AUTHORIZED), evidence_id="evidence_search")
            decision = VerificationDecision(str(created["mission_id"]), card.evidence_id, ReviewStatus.ACCEPTED, "human review")
            (run_dir / "evidence_cards.json").write_text(json.dumps([card.to_dict()]), encoding="utf-8")
            (run_dir / "verification_decisions.json").write_text(json.dumps([decision.to_dict()]), encoding="utf-8")
            result = api.search_accepted_evidence("search_graph", {"query": "strain phase stability", "limit": 4})
            self.assertEqual(result["result_count"], 1)
            self.assertEqual(result["results"][0]["evidence_id"], card.evidence_id)
            self.assertNotIn("private source quote", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
