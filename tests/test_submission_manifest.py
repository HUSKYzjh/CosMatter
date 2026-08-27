import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cosmatter.cli import main
from cosmatter.models import MissionBrief
from cosmatter.submission_manifest import (
    SubmissionManifestError,
    build_submission_execution_manifest,
)


class SubmissionManifestTests(unittest.TestCase):
    def test_manifest_aggregates_execution_without_copying_sensitive_artifact_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory) / "run"
            run.mkdir()
            mission = MissionBrief(
                question="Private exact research question",
                material="BiFeO3", property_name="phase stability",
                scope="thin films", mission_id="mission_submission",
            )
            (run / "mission.json").write_text(json.dumps(mission.to_dict()), encoding="utf-8")
            (run / "retrieval_candidates.json").write_text(json.dumps({
                "candidates": [{
                    "document_id": "doc_1", "title": "Private paper",
                    "quote": "private source quote should not be projected",
                    "local_path": "D:/private/paper.md",
                }],
                "searches": [{"query": "private query should not be projected", "candidates": []}],
            }), encoding="utf-8")
            (run / "events.jsonl").write_text(json.dumps({
                "event_type": "approved_plan_query_executed",
                "payload": {"query": "private query should not be projected"},
            }) + "\n", encoding="utf-8")
            (run / "provider_receipts.jsonl").write_text(json.dumps({
                "provider": "sciverse", "operation": "agentic_search",
                "request_id": "private-request-id",
            }) + "\n", encoding="utf-8")
            (run / "external_resource_disclosure.json").write_text(json.dumps({"schema_version": "1.0"}), encoding="utf-8")
            (run / "potential_execution_protocol.json").write_text(json.dumps({"schema_version": "1.0"}), encoding="utf-8")
            manifest = build_submission_execution_manifest(run_dir=run, mission=mission)
            serialized = json.dumps(manifest)
            second = build_submission_execution_manifest(run_dir=run, mission=mission)
        self.assertEqual(manifest["event_summary"]["event_type_counts"], {"approved_plan_query_executed": 1})
        self.assertEqual(manifest["provider_receipt_summary"]["provider_operation_counts"], {"sciverse:agentic_search": 1})
        self.assertEqual(manifest["manifest_sha256_input"], second["manifest_sha256_input"])
        self.assertTrue(next(item for item in manifest["artifact_inventory"] if item["name"] == "external_resource_disclosure.json")["exists"])
        self.assertTrue(next(item for item in manifest["artifact_inventory"] if item["name"] == "potential_execution_protocol.json")["exists"])
        self.assertNotIn("private source quote", serialized)
        self.assertNotIn("D:/private", serialized)
        self.assertNotIn("private query", serialized)
        self.assertNotIn("private-request-id", serialized)

    def test_cli_writes_manifest_and_records_only_aggregate_event(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runs = root / "runs"
            run = runs / "submission_cli"
            run.mkdir(parents=True)
            mission = MissionBrief("question", "BiFeO3", "phase stability", "films", mission_id="mission_cli")
            (run / "mission.json").write_text(json.dumps(mission.to_dict()), encoding="utf-8")
            output = io.StringIO()
            with patch("cosmatter.cli._runs_dir", return_value=runs), contextlib.redirect_stdout(output):
                status = main(["build-submission-execution-manifest", "--run-id", "submission_cli"])
            manifest = (run / "submission_execution_manifest.json").read_text(encoding="utf-8")
            event_log = (run / "events.jsonl").read_text(encoding="utf-8")
        self.assertEqual(status, 0, output.getvalue())
        self.assertIn("derived_submission_execution_index", manifest)
        self.assertIn("submission_execution_manifest_built", event_log)
        self.assertNotIn("question", manifest)

    def test_rejects_malformed_event_log(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory) / "run"
            run.mkdir()
            mission = MissionBrief("q", "BiFeO3", "phase", "films", mission_id="mission_invalid")
            (run / "events.jsonl").write_text("{bad json}\n", encoding="utf-8")
            with self.assertRaises(SubmissionManifestError):
                build_submission_execution_manifest(run_dir=run, mission=mission)


if __name__ == "__main__":
    unittest.main()
