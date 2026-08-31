from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from cosmatter.external_dispatch import (
    DISPATCH_LEDGER_FILENAME,
    ExternalDispatchError,
    begin_external_dispatch,
    complete_external_dispatch,
    mark_external_dispatch_unknown,
)


class ExternalDispatchTests(unittest.TestCase):
    def test_completed_call_is_reused_without_exposing_identity_or_request(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            first = begin_external_dispatch(
                run_dir,
                mission_id="mission_fixture",
                dsh_call_id="tool-call-0001",
                plugin_id="literature.metadata_retrieval",
                operation="metadata_query",
                request_shape={"query_index": 0, "sources": ["sciverse"], "private_query": "must-not-persist"},
            )
            self.assertFalse(first["duplicate"])
            complete_external_dispatch(
                run_dir, mission_id="mission_fixture", dsh_call_id="tool-call-0001", provider_receipt_ids=("receipt_fixture",)
            )
            repeated = begin_external_dispatch(
                run_dir,
                mission_id="mission_fixture",
                dsh_call_id="tool-call-0001",
                plugin_id="literature.metadata_retrieval",
                operation="metadata_query",
                request_shape={"query_index": 0, "sources": ["sciverse"], "private_query": "must-not-persist"},
            )
            self.assertTrue(repeated["duplicate"])
            ledger_text = (run_dir / DISPATCH_LEDGER_FILENAME).read_text(encoding="utf-8")
            self.assertNotIn("tool-call-0001", ledger_text)
            self.assertNotIn("must-not-persist", ledger_text)
            self.assertEqual(json.loads(ledger_text)["entries"][0]["state"], "completed")

    def test_unknown_outcome_fails_closed_until_a_new_explicit_call(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            begin_external_dispatch(
                run_dir,
                mission_id="mission_fixture",
                dsh_call_id="tool-call-0002",
                plugin_id="document.mineru_private_parse",
                operation="mineru_submit",
                request_shape={"document_id": "doc_1", "source_url_sha256": "0" * 64},
            )
            mark_external_dispatch_unknown(run_dir, mission_id="mission_fixture", dsh_call_id="tool-call-0002")
            with self.assertRaisesRegex(ExternalDispatchError, "outcome is unknown"):
                begin_external_dispatch(
                    run_dir,
                    mission_id="mission_fixture",
                    dsh_call_id="tool-call-0002",
                    plugin_id="document.mineru_private_parse",
                    operation="mineru_submit",
                    request_shape={"document_id": "doc_1", "source_url_sha256": "0" * 64},
                )
            replacement = begin_external_dispatch(
                run_dir,
                mission_id="mission_fixture",
                dsh_call_id="tool-call-0003",
                plugin_id="document.mineru_private_parse",
                operation="mineru_submit",
                request_shape={"document_id": "doc_1", "source_url_sha256": "0" * 64},
            )
            self.assertFalse(replacement["duplicate"])


if __name__ == "__main__":
    unittest.main()
