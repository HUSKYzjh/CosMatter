import contextlib
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cosmatter.cli import main
from cosmatter.provider_receipts import ProviderReceiptError, append_provider_receipt, audit_candidate_receipt_links, audit_source_parse_receipt_links, mineru_task_receipt, sciverse_content_receipt, sciverse_search_receipt
from cosmatter.sciverse import SciverseResponse


class ProviderReceiptTests(unittest.TestCase):
    def test_receipt_retains_query_digest_without_query_text(self) -> None:
        query = "BiFeO3 strain phase stability private wording"
        receipt = sciverse_search_receipt(
            query=query, top_k=5, status_code=200, request_id="request_1", candidate_count=2,
        )
        self.assertEqual(receipt["query_sha256"], hashlib.sha256(query.encode("utf-8")).hexdigest())
        self.assertNotIn(query, json.dumps(receipt))
        with tempfile.TemporaryDirectory() as directory:
            path = append_provider_receipt(Path(directory), receipt)
            saved = path.read_text(encoding="utf-8")
        self.assertIn("request_1", saved)
        self.assertNotIn(query, saved)


    def test_content_receipt_retains_only_hashes_and_window_metadata(self) -> None:
        text = "bounded private content"
        receipt = sciverse_content_receipt(document_id="doc_1", offset=5, limit=200, content=text, next_offset=28, more=True, status_code=200, request_id="request_content")
        self.assertEqual(receipt["operation"], "content")
        self.assertNotIn(text, json.dumps(receipt))
        with tempfile.TemporaryDirectory() as directory:
            path = append_provider_receipt(Path(directory), receipt)
            self.assertNotIn(text, path.read_text(encoding="utf-8"))

    def test_mineru_receipt_and_task_audit_keep_source_identifiers_hashed(self) -> None:
        source_url = "https://publisher.example/paper.pdf?private=1"
        task_id = "task_private_1"
        source_hash = hashlib.sha256(source_url.encode("utf-8")).hexdigest()
        receipt = mineru_task_receipt(
            operation="source_parse_submit",
            document_id="doc_1",
            source_url_sha256=source_hash,
            task_id=task_id,
            task_state="pending",
            model_version="vlm",
            status_code=202,
            request_id="mineru_request_1",
        )
        self.assertNotIn(source_url, json.dumps(receipt))
        self.assertNotIn(task_id, json.dumps(receipt))
        ledger = {
            "tasks": [{
                "document_id": "doc_1",
                "source_url_sha256": source_hash,
                "task_id": task_id,
                "state": "pending",
                "model_version": "vlm",
            }],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = append_provider_receipt(Path(directory), receipt)
            audit = audit_source_parse_receipt_links(ledger, path)
        self.assertEqual(audit["receipt_linked_task_count"], 1)
        self.assertEqual(audit["stale_task_state_count"], 0)
        self.assertEqual(audit["receipt_link_coverage"], 1.0)

    def test_mineru_task_audit_identifies_stale_parser_state(self) -> None:
        source_hash = hashlib.sha256(b"https://publisher.example/paper.pdf").hexdigest()
        receipt = mineru_task_receipt(
            operation="source_parse_submit",
            document_id="doc_1",
            source_url_sha256=source_hash,
            task_id="task_1",
            task_state="pending",
            model_version="vlm",
            status_code=202,
            request_id=None,
        )
        ledger = {
            "tasks": [{
                "document_id": "doc_1",
                "source_url_sha256": source_hash,
                "task_id": "task_1",
                "state": "done",
                "model_version": "vlm",
            }],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = append_provider_receipt(Path(directory), receipt)
            audit = audit_source_parse_receipt_links(ledger, path)
        self.assertEqual(audit["receipt_linked_task_count"], 0)
        self.assertEqual(audit["stale_task_state_count"], 1)
        self.assertEqual(audit["unlinked_task_count"], 0)

    def test_sciverse_cli_writes_receipt_and_keeps_query_out_of_event_log(self) -> None:
        query = "BiFeO3 private approved phrase"
        response = SciverseResponse(
            {"hits": [{"doc_id": "doc_1", "title": "Candidate", "is_content_accessible": True}]},
            200, "request_cli_receipt",
        )
        with tempfile.TemporaryDirectory() as directory:
            runs_dir = Path(directory)
            with (
                patch("cosmatter.cli._runs_dir", return_value=runs_dir),
                patch("cosmatter.cli.SciverseAdapter") as adapter,
                contextlib.redirect_stdout(io.StringIO()),
            ):
                adapter.return_value.agentic_search.return_value = response
                self.assertEqual(main(["sciverse-search", "--query", query, "--top-k", "3", "--run-id", "receipt_cli"]), 0)
            receipt_log = (runs_dir / "receipt_cli" / "provider_receipts.jsonl").read_text(encoding="utf-8")
            event_log = (runs_dir / "receipt_cli" / "events.jsonl").read_text(encoding="utf-8")
            candidate_path = runs_dir / "receipt_cli" / "retrieval_candidates.json"
            candidate_payload = json.loads(candidate_path.read_text(encoding="utf-8"))
            audit = audit_candidate_receipt_links(candidate_payload, runs_dir / "receipt_cli" / "provider_receipts.jsonl")
            cli_audit_output = io.StringIO()
            with patch("cosmatter.cli._runs_dir", return_value=runs_dir), contextlib.redirect_stdout(cli_audit_output):
                self.assertEqual(main(["audit-candidate-receipts", "--run-id", "receipt_cli"]), 0)
            self.assertIn("candidate_receipt_audit.json", cli_audit_output.getvalue())
            candidate_payload["candidates"][0]["retrieval_origins"][0]["receipt_id"] = "receipt_missing"
            with self.assertRaises(ProviderReceiptError):
                audit_candidate_receipt_links(candidate_payload, runs_dir / "receipt_cli" / "provider_receipts.jsonl")
        self.assertEqual(audit["provider_linked_origin_count"], 1)
        self.assertIn(hashlib.sha256(query.encode("utf-8")).hexdigest(), receipt_log)
        self.assertNotIn(query, receipt_log)
        self.assertNotIn(query, event_log)
        self.assertIn("receipt_", event_log)


if __name__ == "__main__":
    unittest.main()
