import json
import tempfile
import unittest
from pathlib import Path

from cosmatter.content_access import ContentAccessError, content_access_states, has_sciverse_content_access, load_content_access, record_sciverse_content_access, record_sciverse_content_failure
from cosmatter.provider_receipts import sciverse_content_receipt


class ContentAccessTests(unittest.TestCase):
    def test_confirmation_is_hash_only_and_invalidated_when_candidate_history_changes(self) -> None:
        history = {"candidates": [{"document_id": "doc_1", "title": "candidate", "is_content_accessible": False}]}
        receipt = sciverse_content_receipt(
            document_id="doc_1", offset=0, limit=200, content="private bounded content",
            next_offset=None, more=False, status_code=200, request_id="request_1",
        )
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            path = record_sciverse_content_access(
                run, mission_id="mission_1", candidate_payload=history,
                document_id="doc_1", receipt=receipt,
            )
            stored = path.read_text(encoding="utf-8")
            self.assertTrue(has_sciverse_content_access(
                run, mission_id="mission_1", candidate_payload=history, document_id="doc_1",
            ))
            changed = {"candidates": [{"document_id": "doc_1", "title": "changed", "is_content_accessible": False}]}
            self.assertFalse(has_sciverse_content_access(
                run, mission_id="mission_1", candidate_payload=changed, document_id="doc_1",
            ))
        self.assertNotIn("private bounded content", stored)
        self.assertNotIn("request_1", stored)
        self.assertEqual(set(json.loads(stored)["confirmations"][0]), {"document_id", "provider", "receipt_id", "content_sha256", "confirmed_at"})
        self.assertTrue(json.loads(stored)["confirmations"][0]["confirmed_at"].endswith("Z"))
        self.assertEqual(json.loads(stored)["failures"], [])

    def test_confirmation_rejects_a_receipt_for_a_different_document(self) -> None:
        receipt = sciverse_content_receipt(
            document_id="doc_other", offset=0, limit=200, content="bounded",
            next_offset=None, more=False, status_code=200, request_id=None,
        )
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ContentAccessError):
                record_sciverse_content_access(
                    Path(directory), mission_id="mission_1",
                    candidate_payload={"candidates": [{"document_id": "doc_1"}]},
                    document_id="doc_1", receipt=receipt,
                )

    def test_failure_replaces_confirmation_and_success_replaces_failure(self) -> None:
        history = {"candidates": [{"document_id": "doc_1", "title": "candidate", "is_content_accessible": True}]}
        receipt = sciverse_content_receipt(
            document_id="doc_1", offset=0, limit=200, content="bounded",
            next_offset=None, more=False, status_code=200, request_id=None,
        )
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            record_sciverse_content_access(
                run, mission_id="mission_1", candidate_payload=history,
                document_id="doc_1", receipt=receipt,
            )
            record_sciverse_content_failure(
                run, mission_id="mission_1", candidate_payload=history,
                document_id="doc_1", reason_code="provider_request_failed",
            )
            failed = load_content_access(run / "content_access_confirmations.json", "mission_1")
            self.assertEqual(content_access_states(failed, "mission_1", history), {"doc_1": "failed_or_expired"})
            record_sciverse_content_access(
                run, mission_id="mission_1", candidate_payload=history,
                document_id="doc_1", receipt=receipt,
            )
            confirmed = load_content_access(run / "content_access_confirmations.json", "mission_1")
            self.assertEqual(content_access_states(confirmed, "mission_1", history), {"doc_1": "confirmed"})

    def test_stale_confirmation_projects_expired_not_confirmed(self) -> None:
        history = {"candidates": [{"document_id": "doc_1", "title": "candidate", "is_content_accessible": True}]}
        changed = {"candidates": [{"document_id": "doc_1", "title": "changed", "is_content_accessible": True}]}
        receipt = sciverse_content_receipt(
            document_id="doc_1", offset=0, limit=200, content="bounded",
            next_offset=None, more=False, status_code=200, request_id=None,
        )
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            record_sciverse_content_access(
                run, mission_id="mission_1", candidate_payload=history,
                document_id="doc_1", receipt=receipt,
            )
            artifact = load_content_access(run / "content_access_confirmations.json", "mission_1")
        self.assertEqual(content_access_states(artifact, "mission_1", changed), {"doc_1": "failed_or_expired"})

    def test_load_upgrades_v10_confirmation_without_inventing_failures(self) -> None:
        history = {"candidates": [{"document_id": "doc_1", "title": "candidate", "is_content_accessible": True}]}
        receipt = sciverse_content_receipt(
            document_id="doc_1", offset=0, limit=200, content="bounded",
            next_offset=None, more=False, status_code=200, request_id=None,
        )
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            path = record_sciverse_content_access(
                run, mission_id="mission_1", candidate_payload=history,
                document_id="doc_1", receipt=receipt,
            )
            legacy = json.loads(path.read_text(encoding="utf-8"))
            legacy["schema_version"] = "1.0"
            legacy.pop("failures")
            legacy["confirmations"][0].pop("confirmed_at")
            path.write_text(json.dumps(legacy), encoding="utf-8")
            loaded = load_content_access(path, "mission_1")

        self.assertEqual(loaded["schema_version"], "1.1")
        self.assertEqual(loaded["failures"], [])
        self.assertIsNone(loaded["confirmations"][0]["confirmed_at"])


if __name__ == "__main__":
    unittest.main()
