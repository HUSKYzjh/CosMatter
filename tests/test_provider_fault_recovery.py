"""Fault-injection matrix for the externally dispatching loopback boundary.

All adapters below are synthetic.  The tests must never need a provider token,
real task ID, source URL, paper, or network connection.
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cosmatter.config import Settings
from cosmatter.deepseek import DeepSeekRequestError
from cosmatter.local_api import LocalApiError, LocalMissionApi
from cosmatter.mineru import MinerURequestError, MinerUTask
from cosmatter.sciverse import SciverseRequestError, SciverseResponse


class _SciverseSuccess:
    def __init__(self, _settings):
        pass

    def agentic_search(self, _query, *, top_k):
        return SciverseResponse(
            payload={"hits": [{"doc_id": "fixture-doc", "title": "Synthetic bounded metadata", "is_content_accessible": True, "score": 0.5}]},
            status_code=200,
            request_id="synthetic-request",
        )


class ProviderFaultRecoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.runs = Path(self.directory.name) / "runs"
        self.api = LocalMissionApi(self.runs, settings_loader=lambda: Settings.load({
            "LLM_PROVIDER": "deepseek", "LLM_MODEL": "deepseek-v4-flash",
            "DEEPSEEK_API_KEY": "synthetic", "SCIVERSE_API_TOKEN": "synthetic", "MINERU_API_TOKEN": "synthetic",
        }))
        self.api.create_mission({"run_id": "fault_matrix", "question": "Synthetic fault matrix", "material": "BiFeO3", "property": "phase stability", "scope": "test only"})
        self.api.approve_plan("fault_matrix", {"subquestions": ["Synthetic?"], "queries": ["synthetic query"], "counter_queries": ["synthetic counter query"]})

    def tearDown(self) -> None:
        self.directory.cleanup()

    @property
    def _metadata_auth(self):
        return ["mission_scoped_egress_consent", "metadata_provider_consent"]

    @property
    def _mineru_auth(self):
        return ["mission_scoped_egress_consent", "mineru_file_consent", "private_content_to_mineru"]

    def _prepare_screened_candidate(self) -> None:
        with patch("cosmatter.local_api.SciverseAdapter", _SciverseSuccess):
            self.api.execute_plan_query("fault_matrix", {"query_index": 0, "sources": ["sciverse"]})
        self.api.record_candidate_screening("fault_matrix", {"decisions": [{"document_id": "fixture-doc", "decision": "include_for_fulltext", "reason_codes": ["material_match", "property_match"]}]})

    def _state(self, call_id: str) -> str:
        payload = json.loads((self.runs / "fault_matrix" / "external_dispatch_ledger.json").read_text(encoding="utf-8"))
        digest = __import__("hashlib").sha256(call_id.encode("utf-8")).hexdigest()
        return next(item["state"] for item in payload["entries"] if item["call_id_sha256"] == digest)

    def test_sciverse_timeout_401_and_429_become_unknown_without_automatic_replay(self) -> None:
        for label in ("timeout", "401", "429"):
            with self.subTest(label=label):
                call_id = f"sciverse-{label}-0001"

                class FailingSciverse:
                    def __init__(self, _settings):
                        pass

                    def agentic_search(self, _query, *, top_k):
                        raise SciverseRequestError(f"synthetic Sciverse {label}")

                payload = {"authorizations": self._metadata_auth, "query_index": 0, "sources": ["sciverse"], "dsh_call_id": call_id}
                with patch("cosmatter.local_api.SciverseAdapter", FailingSciverse):
                    with self.assertRaises(LocalApiError):
                        self.api.execute_authorized_plan_query("fault_matrix", payload)
                    with self.assertRaisesRegex(LocalApiError, "outcome is unknown"):
                        self.api.execute_authorized_plan_query("fault_matrix", payload)
                self.assertEqual(self._state(call_id), "unknown")

    def test_deepseek_malformed_or_timeout_result_becomes_unknown(self) -> None:
        for label in ("timeout", "malformed_response"):
            with self.subTest(label=label):
                call_id = f"deepseek-{label}-0001"

                class FailingDeepSeek:
                    def __init__(self, _settings):
                        pass

                    def draft(self, **_kwargs):
                        raise DeepSeekRequestError(f"synthetic DeepSeek {label}")

                payload = {"authorizations": ["mission_scoped_egress_consent", "deepseek_request_consent"], "dsh_call_id": call_id}
                with patch("cosmatter.local_api.DeepSeekAdapter", FailingDeepSeek):
                    with self.assertRaises(LocalApiError):
                        self.api.draft_authorized_plan("fault_matrix", payload)
                    with self.assertRaisesRegex(LocalApiError, "outcome is unknown"):
                        self.api.draft_authorized_plan("fault_matrix", payload)
                self.assertEqual(self._state(call_id), "unknown")

    def test_mineru_half_success_malformed_task_and_duplicate_poll_are_all_safe(self) -> None:
        self._prepare_screened_candidate()

        class MalformedMinerU:
            def __init__(self, _settings):
                pass

            def submit_remote_source(self, _url):
                # Simulates an upstream half-success whose returned task metadata is unusable.
                return MinerUTask(task_id="synthetic-task", state="unexpected", request_id="synthetic")

        submit_payload = {"authorizations": self._mineru_auth, "document_id": "fixture-doc", "source_url": "https://example.org/synthetic.pdf", "dsh_call_id": "mineru-half-success-0001"}
        with patch("cosmatter.local_api.MinerUAdapter", MalformedMinerU):
            with self.assertRaises(LocalApiError):
                self.api.submit_authorized_mineru_source("fault_matrix", submit_payload)
            with self.assertRaisesRegex(LocalApiError, "outcome is unknown"):
                self.api.submit_authorized_mineru_source("fault_matrix", submit_payload)
        self.assertEqual(self._state("mineru-half-success-0001"), "unknown")

        poll_calls: list[str] = []

        class CountingMinerU:
            def __init__(self, _settings):
                pass

            def submit_remote_source(self, _url):
                return MinerUTask(task_id="stable-task", state="pending", request_id="submit")

            def get_task(self, task_id):
                poll_calls.append(task_id)
                return MinerUTask(task_id="stable-task", state="done", request_id="poll")

        success_payload = {**submit_payload, "dsh_call_id": "mineru-submit-stable-0001"}
        poll_payload = {"authorizations": self._mineru_auth, "document_id": "fixture-doc", "dsh_call_id": "mineru-poll-stable-0001"}
        with patch("cosmatter.local_api.MinerUAdapter", CountingMinerU):
            self.api.submit_authorized_mineru_source("fault_matrix", success_payload)
            first = self.api.poll_authorized_mineru_source("fault_matrix", poll_payload)
            repeated = self.api.poll_authorized_mineru_source("fault_matrix", poll_payload)
        self.assertEqual(first["task_state"], "done")
        self.assertEqual(repeated["idempotency_status"], "duplicate_completed")
        self.assertEqual(poll_calls, ["stable-task"])

    def test_structural_invariant_failure_blocks_a_new_sensitive_dispatch(self) -> None:
        # An orphan decision is a local relationship corruption, not an
        # uncertain provider outcome.  It must block before adapter creation.
        (self.runs / "fault_matrix" / "verification_decisions.json").write_text(json.dumps([{
            "decision_id": "orphan", "mission_id": self.api._active_mission("fault_matrix")[1].mission_id,
            "evidence_id": "missing-card", "status": "accepted", "reason": "synthetic", "missing_conditions": [], "created_at": "fixture",
        }]), encoding="utf-8")
        calls: list[str] = []

        class MustNotRunSciverse:
            def __init__(self, _settings):
                calls.append("constructed")

            def agentic_search(self, _query, *, top_k):
                raise AssertionError("provider must be blocked before dispatch")

        payload = {"authorizations": self._metadata_auth, "query_index": 0, "sources": ["sciverse"], "dsh_call_id": "blocked-structural-0001"}
        with patch("cosmatter.local_api.SciverseAdapter", MustNotRunSciverse):
            with self.assertRaisesRegex(LocalApiError, "runtime invariant audit blocks"):
                self.api.execute_authorized_plan_query("fault_matrix", payload)
        self.assertEqual(calls, [])
        self.assertFalse((self.runs / "fault_matrix" / "external_dispatch_ledger.json").exists())


if __name__ == "__main__":
    unittest.main()
