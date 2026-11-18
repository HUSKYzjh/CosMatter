import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cosmatter.cli import main
from cosmatter.candidate_screening import candidate_screening_from_review, write_candidate_screening
from cosmatter.config import Settings
from cosmatter.local_api import LocalApiError, LocalMissionApi
from cosmatter.mineru import MinerUCompletedMarkdown, MinerUTask
from cosmatter.models import MissionBrief
from cosmatter.source_parse import record_source_parse_task


class CliMinerUTests(unittest.TestCase):
    def test_submit_records_no_plain_source_url_in_output_or_audit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runs_dir = Path(directory)
            run_dir = runs_dir / "mineru_cli"
            run_dir.mkdir()
            (run_dir / "mission.json").write_text(json.dumps(MissionBrief(question="test question", material="BiFeO3", property_name="phase stability", scope="test scope", mission_id="mission_cli").to_dict()), encoding="utf-8")
            candidate_history = {"candidates": [{"document_id": "doc_1", "is_content_accessible": True}]}
            (run_dir / "retrieval_candidates.json").write_text(json.dumps(candidate_history), encoding="utf-8")
            screening = candidate_screening_from_review(
                "mission_cli", candidate_history,
                {"decisions": [{"document_id": "doc_1", "decision": "include_for_fulltext", "reason_codes": ["material_match"]}]},
            )
            write_candidate_screening(run_dir, screening)
            settings = Settings.load({"MINERU_API_TOKEN": "test-token", "API_MAX_RETRIES": "1"})
            output = io.StringIO()
            source_url = "https://publisher.example/paper.pdf?opaque=temporary"
            with (
                patch("cosmatter.cli._runs_dir", return_value=runs_dir),
                patch("cosmatter.cli.Settings.load", return_value=settings),
                patch("cosmatter.cli.MinerUAdapter.submit_remote_source", return_value=MinerUTask("task_1", "pending", "request_1")),
                contextlib.redirect_stdout(output),
            ):
                status = main(["mineru-submit-url", "--run-id", "mineru_cli", "--document-id", "doc_1", "--source-url", source_url])
            self.assertEqual(status, 0, output.getvalue())
            audit = (run_dir / "events.jsonl").read_text(encoding="utf-8")
            ledger = (run_dir / "source_parse_tasks.json").read_text(encoding="utf-8")


        self.assertNotIn(source_url, output.getvalue())
        self.assertNotIn(source_url, audit)
        self.assertNotIn(source_url, ledger)
        self.assertNotIn("task_1", output.getvalue())
    def test_poll_creates_hash_only_receipt_and_receipt_audit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runs_dir = Path(directory)
            run_dir = runs_dir / "mineru_poll_cli"
            run_dir.mkdir()
            mission = MissionBrief(question="test question", material="BiFeO3", property_name="phase stability", scope="test scope", mission_id="mission_poll")
            (run_dir / "mission.json").write_text(json.dumps(mission.to_dict()), encoding="utf-8")
            source_url = "https://publisher.example/paper.pdf?temporary=1"
            task_id = "task_private_1"
            record_source_parse_task(
                run_dir,
                mission_id=mission.mission_id,
                document_id="doc_1",
                source_url=source_url,
                task=MinerUTask(task_id, "pending", "request_submit"),
                model_version="vlm",
            )
            settings = Settings.load({"MINERU_API_TOKEN": "test-token", "API_MAX_RETRIES": "1", "MINERU_MODEL_VERSION": "vlm"})
            output = io.StringIO()
            with (
                patch("cosmatter.cli._runs_dir", return_value=runs_dir),
                patch("cosmatter.cli.Settings.load", return_value=settings),
                patch("cosmatter.cli.MinerUAdapter.get_task", return_value=MinerUTask(task_id, "done", "request_poll", 200)),
                contextlib.redirect_stdout(output),
            ):
                status = main(["mineru-poll", "--run-id", "mineru_poll_cli", "--document-id", "doc_1"])
            self.assertEqual(status, 0, output.getvalue())
            audit_output = io.StringIO()
            with patch("cosmatter.cli._runs_dir", return_value=runs_dir), contextlib.redirect_stdout(audit_output):
                self.assertEqual(main(["audit-source-parse-receipts", "--run-id", "mineru_poll_cli"]), 0)
            receipt_log = (run_dir / "provider_receipts.jsonl").read_text(encoding="utf-8")
            audit = json.loads((run_dir / "source_parse_receipt_audit.json").read_text(encoding="utf-8"))
            events = (run_dir / "events.jsonl").read_text(encoding="utf-8")
        self.assertNotIn(source_url, receipt_log)
        self.assertNotIn(task_id, receipt_log)
        self.assertNotIn(source_url, events)
        self.assertNotIn(task_id, events)
        self.assertEqual(audit["receipt_linked_task_count"], 1)
        self.assertEqual(audit["receipt_link_coverage"], 1.0)

    def test_fetched_markdown_stays_private_and_supports_candidate_review(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch(
            "cosmatter.source_parse.private_root", return_value=Path(directory) / "private-cache",
        ):
            root = Path(directory)
            runs_dir = root / "runs"
            run_dir = runs_dir / "mineru_fetch_cli"
            run_dir.mkdir(parents=True)
            mission = MissionBrief(question="test question", material="BiFeO3", property_name="phase stability", scope="test scope", mission_id="mission_fetch")
            (run_dir / "mission.json").write_text(json.dumps(mission.to_dict()), encoding="utf-8")
            run_id = run_dir.name
            api = LocalMissionApi(runs_dir=runs_dir)
            candidates = {"candidates": [{"document_id": "doc_1", "title": "Synthetic paper", "is_content_accessible": True}]}
            (run_dir / "retrieval_candidates.json").write_text(json.dumps(candidates), encoding="utf-8")
            api.record_candidate_screening(run_id, {
                "decisions": [{"document_id": "doc_1", "decision": "include_for_fulltext", "reason_codes": ["material_match"]}],
            })
            source_url = "https://publisher.example/paper.pdf?temporary=1"
            task_id = "task_private_fetch"
            record_source_parse_task(run_dir, mission_id=mission.mission_id, document_id="doc_1", source_url=source_url, task=MinerUTask(task_id, "done", "request_submit"), model_version="vlm")
            output_path = root / "private.md"
            markdown = ("# Private MinerU output\r\nA synthetic reviewed excerpt.\n条件\u2028"
                        + "x" * 1_601 + "\n" + "continuation\n" * 20).encode("utf-8")
            output = io.StringIO()
            settings = Settings.load({"MINERU_API_TOKEN": "test-token", "API_MAX_RETRIES": "1", "MINERU_MODEL_VERSION": "vlm"})
            with (
                patch("cosmatter.cli._runs_dir", return_value=runs_dir),
                patch("cosmatter.cli.Settings.load", return_value=settings),
                patch("cosmatter.cli.MinerUAdapter.download_completed_markdown", return_value=MinerUCompletedMarkdown(markdown, "done", 200, "archive_request")),
                contextlib.redirect_stdout(output),
            ):
                status = main(["mineru-fetch-markdown", "--run-id", "mineru_fetch_cli", "--document-id", "doc_1", "--output", str(output_path)])
            receipt_log = (run_dir / "provider_receipts.jsonl").read_text(encoding="utf-8")
            event_log = (run_dir / "events.jsonl").read_text(encoding="utf-8")
            private_markdown = output_path.read_bytes()
            self.assertEqual(status, 0, output.getvalue())
            self.assertEqual(private_markdown, markdown)
            self.assertNotIn(markdown.decode(), receipt_log + event_log + output.getvalue())
            self.assertNotIn(source_url, receipt_log + event_log + output.getvalue())
            self.assertNotIn(task_id, receipt_log + event_log + output.getvalue())
            self.assertIn("source_parse_output_fetch", receipt_log)
            cache_file = next((Path(directory) / "private-cache" / "mineru_fetched_markdown").glob("*.md"))
            cache_file.unlink()  # Simulate an output fetched before the workbench kept a private copy.
            self.assertTrue(api.source_parse_status(run_id)["tasks"][0]["can_link_markdown"])
            with self.assertRaises(LocalApiError) as mismatched_file:
                api.link_fetched_source_markdown(run_id, "doc_1", b"x" * len(private_markdown))
            self.assertEqual(mismatched_file.exception.status, 422)
            self.assertFalse(cache_file.exists())
            linked = api.link_fetched_source_markdown(run_id, "doc_1", output_path.read_bytes())
            self.assertEqual(linked, {"run_id": run_id, "document_id": "doc_1", "markdown_ready": True})
            self.assertEqual(api.link_fetched_source_markdown(run_id, "doc_1", private_markdown), linked)
            self.assertEqual((run_dir / "provider_receipts.jsonl").read_text(encoding="utf-8"), receipt_log)
            self.assertFalse(api.source_parse_status(run_id)["tasks"][0]["can_link_markdown"])
            output_path.unlink()
            self.assertEqual(api.fetched_source_markdown(run_id, "doc_1").data, markdown)
            self.assertTrue(api.source_parse_status(run_id)["tasks"][0]["markdown_ready"])
            window = api.private_markdown_lines(run_id, "doc_1", 1, fetched_source=True)
            self.assertEqual((window["start"], window["total_lines"], len(window["lines"])), (1, 24, 20))
            self.assertEqual(window["lines"][2], {"number": 3, "text": "条件", "truncated": False})
            self.assertEqual(window["lines"][3], {"number": 4, "text": "x" * 1_600, "truncated": True})
            tail = api.private_markdown_lines(run_id, "doc_1", 21, fetched_source=True)
            self.assertEqual([line["number"] for line in tail["lines"]], [21, 22, 23, 24])
            with self.assertRaises(LocalApiError) as outside:
                api.private_markdown_lines(run_id, "doc_1", 25, fetched_source=True)
            self.assertEqual(outside.exception.status, 416)
            with self.assertRaises(LocalApiError) as wrong_document:
                api.fetched_source_markdown(run_id, "different_candidate")
            self.assertEqual(wrong_document.exception.status, 403)

            selected = window["lines"][1:3]
            segments = [{"locator": "markdown_line:2-3", "kind": "paragraph", "quote": "\n".join(line["text"] for line in selected)}]
            review = {"document_id": "doc_1", "human_confirmed": True, "segments": segments}
            with self.assertRaisesRegex(LocalApiError, "line range"):
                api.record_fetched_source_map(run_id, review | {"segments": [segments[0] | {"locator": "markdown_line:1-1"}]})
            result = api.record_fetched_source_map(run_id, review)
            self.assertEqual(result["segments"], [{"segment_id": "private_md_001", "locator": "markdown_line:2-3", "kind": "paragraph", "markdown_range": {"start": 2, "end": 3}}])
            trace = api.private_markdown_lines(run_id, "doc_1", 2, fetched_source=True, segment_id="private_md_001")
            self.assertEqual(trace["recorded_range"], {"start": 2, "end": 3})
            with self.assertRaises(LocalApiError) as unknown_segment:
                api.private_markdown_lines(run_id, "doc_1", 2, fetched_source=True, segment_id="wrong")
            self.assertEqual(unknown_segment.exception.status, 409)
            self.assertEqual(api.record_fetched_source_map(run_id, review), result)
            self.assertEqual(api.fetched_source_map_context(run_id, "doc_1"), result)
            self.assertEqual(api.source_parse_status(run_id)["tasks"][0]["source_map_segment_count"], 1)
            facts = [{"fact_id": "phase_boundary", "segment_id": "private_md_001", "category": "property", "name": "phase boundary", "value": "synthetic", "unit": None, "normalized_value": "synthetic", "normalized_unit": None, "qualifiers": {}}]
            self.assertEqual(api.record_pdf_material_facts(run_id, {"document_id": "doc_1", "human_confirmed": True, "facts": facts}, fetched_source=True)["fact_count"], 1)
            conditions = {"sample_form": "film", "strain_percent": 0, "substrate": "synthetic", "thickness_nm": 10, "temperature_k": 300, "method": "xrd"}
            evidence = api.record_pdf_evidence_card(run_id, {
                "document_id": "doc_1", "human_confirmed": True, "segment_id": "private_md_001", "claim": "A synthetic claim",
                "stance": "support", "conditions": conditions, "reviewer_confidence": 0.8,
            }, fetched_source=True)
            self.assertEqual(evidence["review_status"], "accepted")
            provenance = json.loads((run_dir / "evidence_provenance_audit.json").read_text(encoding="utf-8"))
            self.assertEqual(provenance["exact_reviewed_source_map_match_count"], 1)
            self.assertFalse((run_dir / "pdf_intake.json").exists())

            cache_file.write_bytes(b"x" * len(markdown))
            with self.assertRaisesRegex(LocalApiError, "could not be verified"):
                api.fetched_source_markdown(run_id, "doc_1")
            cache_file.write_bytes(markdown)
            api.record_candidate_screening(run_id, {
                "decisions": [{"document_id": "doc_1", "decision": "exclude", "reason_codes": ["out_of_scope_material"]}],
            })
            with self.assertRaises(LocalApiError) as excluded_document:
                api.fetched_source_markdown(run_id, "doc_1")
            self.assertEqual(excluded_document.exception.status, 403)
            with self.assertRaises(LocalApiError) as excluded_link:
                api.link_fetched_source_markdown(run_id, "doc_1", markdown)
            self.assertEqual(excluded_link.exception.status, 403)
            with self.assertRaises(LocalApiError) as excluded_preview:
                api.private_markdown_lines(run_id, "doc_1", 1, fetched_source=True)
            self.assertEqual(excluded_preview.exception.status, 403)

    def test_source_map_requires_completed_task_and_keeps_quote_out_of_audit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runs_dir = Path(directory)
            run_dir = runs_dir / "source_map_cli"
            run_dir.mkdir()
            mission = MissionBrief(question="test question", material="BiFeO3", property_name="phase stability", scope="test scope", mission_id="mission_map")
            (run_dir / "mission.json").write_text(json.dumps(mission.to_dict()), encoding="utf-8")
            candidate_history = {"candidates": [{"document_id": "doc_1", "is_content_accessible": True}]}
            (run_dir / "retrieval_candidates.json").write_text(json.dumps(candidate_history), encoding="utf-8")
            write_candidate_screening(run_dir, candidate_screening_from_review(
                "mission_map", candidate_history,
                {"decisions": [{"document_id": "doc_1", "decision": "include_for_fulltext", "reason_codes": ["material_match"]}]},
            ))
            record_source_parse_task(
                run_dir,
                mission_id="mission_map",
                document_id="doc_1",
                source_url="https://publisher.example/paper.pdf",
                task=MinerUTask("task_1", "done", "request_1"),
                model_version="vlm",
            )
            quote = "Reviewer-selected short excerpt."
            selection_path = runs_dir / "selection.json"
            selection_path.write_text(
                json.dumps({"document_id": "doc_1", "segments": [{"segment_id": "p1", "locator": "p. 2", "kind": "paragraph", "quote": quote}]}),
                encoding="utf-8",
            )
            output = io.StringIO()
            with patch("cosmatter.cli._runs_dir", return_value=runs_dir), contextlib.redirect_stdout(output):
                status = main(["record-source-map", "--run-id", "source_map_cli", "--document-id", "doc_1", "--input", str(selection_path)])
            audit = (run_dir / "events.jsonl").read_text(encoding="utf-8")
            source_map = (run_dir / "source_map.json").read_text(encoding="utf-8")

        self.assertEqual(status, 0, output.getvalue())
        self.assertNotIn(quote, output.getvalue())
        self.assertNotIn(quote, audit)
        self.assertIn(quote, source_map)
