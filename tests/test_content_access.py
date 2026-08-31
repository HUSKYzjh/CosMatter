import json
import tempfile
import unittest
from pathlib import Path

from cosmatter.content_access import ContentAccessError, has_sciverse_content_access, record_sciverse_content_access
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
        self.assertEqual(set(json.loads(stored)["confirmations"][0]), {"document_id", "provider", "receipt_id", "content_sha256"})

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


if __name__ == "__main__":
    unittest.main()
