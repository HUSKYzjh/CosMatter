import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cosmatter.cli import main
from cosmatter.citation_expansion import build_citation_expansion, write_citation_expansion
from cosmatter.external_dispatch import begin_external_dispatch, complete_external_dispatch, mark_external_dispatch_unknown
from cosmatter.provider_receipts import append_provider_receipt, sciverse_search_receipt
from cosmatter.runtime_invariants import audit_runtime_invariants, write_runtime_invariant_audit


class RuntimeInvariantTests(unittest.TestCase):
    def _mission(self, run: Path) -> None:
        run.mkdir(parents=True, exist_ok=True)
        (run / "mission.json").write_text(json.dumps({
            "mission_id": "mission_invariant", "question": "Synthetic invariant fixture",
            "material": "BiFeO3", "property_name": "phase stability",
            "scope": "synthetic test", "source_policy": "authorized",
            "output_request": "evidence-backed research report", "created_at": "2026-01-01T00:00:00+00:00",
        }), encoding="utf-8")

    def _event(self, run: Path, event_type: str, state: str, payload: dict) -> None:
        with (run / "events.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"event_type": event_type, "state": state, "payload": payload}) + "\n")

    def test_completed_metadata_dispatch_requires_authorization_receipt_and_result(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory) / "run"
            self._mission(run)
            call_id = "invariant-query-0001"
            begin_external_dispatch(
                run, mission_id="mission_invariant", dsh_call_id=call_id,
                plugin_id="literature.metadata_retrieval", operation="metadata_query",
                request_shape={"query_index": 0, "sources": ["sciverse"]},
            )
            receipt = sciverse_search_receipt(query="private synthetic query", top_k=3, status_code=200, request_id="fixture", candidate_count=0)
            append_provider_receipt(run, receipt)
            complete_external_dispatch(run, mission_id="mission_invariant", dsh_call_id=call_id, provider_receipt_ids=(receipt["receipt_id"],))
            (run / "retrieval_candidates.json").write_text(json.dumps({"candidates": []}), encoding="utf-8")
            self._event(run, "external_plugin_dispatch_authorized", "PLAN", {
                "plugin_id": "literature.metadata_retrieval",
                "dsh_call_id_sha256": __import__("hashlib").sha256(call_id.encode("utf-8")).hexdigest(),
            })

            audit = audit_runtime_invariants(run, "mission_invariant")
            path = write_runtime_invariant_audit(run, audit)

            self.assertTrue(audit["passed"])
            self.assertEqual(audit["checks"]["provider_results"]["missing_receipt_link_count"], 0)
            self.assertTrue(path.is_file())
            rendered = path.read_text(encoding="utf-8")
            self.assertNotIn(call_id, rendered)
            self.assertNotIn("private synthetic query", rendered)

    def test_unknown_dispatch_and_invalid_state_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory) / "run"
            self._mission(run)
            begin_external_dispatch(
                run, mission_id="mission_invariant", dsh_call_id="invariant-unknown-0001",
                plugin_id="document.mineru_private_parse", operation="mineru_submit",
                request_shape={"document_id": "doc_1", "source_url_sha256": "0" * 64},
            )
            mark_external_dispatch_unknown(run, mission_id="mission_invariant", dsh_call_id="invariant-unknown-0001")
            self._event(run, "state_transition", "PLAN", {})
            self._event(run, "state_transition", "EXTRACT", {})

            audit = audit_runtime_invariants(run, "mission_invariant")

            self.assertFalse(audit["passed"])
            self.assertEqual(audit["checks"]["state_transitions"]["invalid_transition_count"], 1)
            self.assertEqual(audit["checks"]["authorization_dispatch"]["unknown_outcome_count"], 1)
            self.assertEqual(audit["checks"]["authorization_dispatch"]["unpaired_dispatch_count"], 1)

    def test_completed_citation_expansion_requires_a_valid_run_bound_result(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory) / "run"
            self._mission(run)
            call_id = "invariant-citation-0001"
            begin_external_dispatch(
                run, mission_id="mission_invariant", dsh_call_id=call_id,
                plugin_id="bibliography.two_hop_expand", operation="citation_expansion",
                request_shape={"document_id": "doc_1"},
            )
            complete_external_dispatch(run, mission_id="mission_invariant", dsh_call_id=call_id)
            self._event(run, "external_plugin_dispatch_authorized", "RETRIEVE", {
                "plugin_id": "bibliography.two_hop_expand",
                "dsh_call_id_sha256": __import__("hashlib").sha256(call_id.encode("utf-8")).hexdigest(),
            })

            missing = audit_runtime_invariants(run, "mission_invariant")
            self.assertFalse(missing["passed"])
            self.assertEqual(missing["checks"]["provider_results"]["missing_result_artifact_count"], 1)

            write_citation_expansion(run, build_citation_expansion("mission_invariant", "10.1000/root", lambda _doi: {"references": [], "cited_by": []}))
            complete = audit_runtime_invariants(run, "mission_invariant")

            self.assertTrue(complete["passed"])
            self.assertEqual(complete["checks"]["provider_results"]["missing_result_artifact_count"], 0)
            self.assertIn("citation_expansion.json", [item["name"] for item in complete["artifact_hashes"]])

    def test_evidence_requires_exactly_one_decision_and_cli_writes_count_only_audit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runs = Path(directory)
            run = runs / "invariant_cli"
            self._mission(run)
            (run / "evidence_cards.json").write_text(json.dumps([{"evidence_id": "evidence_a"}]), encoding="utf-8")
            (run / "verification_decisions.json").write_text(json.dumps([
                {"decision_id": "decision_a", "mission_id": "mission_invariant", "evidence_id": "evidence_a", "status": "accepted", "reason": "human review", "missing_conditions": [], "created_at": "fixture"},
                {"decision_id": "decision_b", "mission_id": "mission_invariant", "evidence_id": "evidence_a", "status": "accepted", "reason": "duplicate", "missing_conditions": [], "created_at": "fixture"},
            ]), encoding="utf-8")
            audit = audit_runtime_invariants(run, "mission_invariant")
            self.assertFalse(audit["passed"])
            self.assertEqual(audit["checks"]["evidence_decisions"]["duplicate_verification_decision_count"], 1)

            (run / "verification_decisions.json").write_text(json.dumps([
                {"decision_id": "decision_a", "mission_id": "mission_invariant", "evidence_id": "evidence_a", "status": "accepted", "reason": "human review", "missing_conditions": [], "created_at": "fixture"},
            ]), encoding="utf-8")
            output = io.StringIO()
            with patch("cosmatter.cli._runs_dir", return_value=runs), contextlib.redirect_stdout(output):
                code = main(["audit-runtime-invariants", "--run-id", "invariant_cli"])
            result = json.loads(output.getvalue())
            self.assertEqual(code, 0)
            self.assertTrue(result["passed"])
            self.assertNotIn("evidence_a", output.getvalue())


if __name__ == "__main__":
    unittest.main()
