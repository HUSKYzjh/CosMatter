import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cosmatter.cli import main
from cosmatter.evidence_maturity_registry import evidence_maturity_registry_sha256
from cosmatter.source_map import (
    AUTOMATED_TRIAL_SOURCE_MAP_TRUST_STATUS,
    source_map_from_review,
    write_source_map_for_document,
)


def _registry(document_id: str = "doc_1") -> dict[str, object]:
    return {
        "schema_version": "cosmatter.evidence-maturity-registry/v1",
        "registry_id": "multirun_registry_1",
        "question_id": "multirun_question_1",
        "trust_status": "delegated_automated_trial_evidence_maturity_registry_not_scientific_evidence",
        "claims": [{
            "claim_id": "claim_1",
            "claim_text": "A bounded literature statement.",
            "maturity_level": "literature_mentioned",
            "assessment_authority": "delegated_automated_trial",
            "support_records": [{
                "run_id": "run_1",
                "document_id": document_id,
                "document_version": "preprint",
                "independence_group": "not_human_verified",
                "source_map_status": "automated_trial_only",
                "data_status": "not_checked",
                "conditions_status": "not_checked",
                "stance": "supports",
            }],
            "reproducibility": {
                "protocol_status": "not_checked",
                "materials_status": "not_checked",
                "measurement_status": "not_checked",
                "raw_data_status": "not_checked",
                "assessment": "not_assessed",
            },
            "independent_reproduction": {
                "status": "not_attempted",
                "independent_run_id": None,
                "result_comparison": "not_available",
                "review_status": "not_reviewed",
            },
            "limitations": ["Not human reviewed."],
        }],
    }


class CliEvidenceMaturityRegistryTests(unittest.TestCase):
    def _write_run(self, runs: Path) -> None:
        run = runs / "run_1"
        run.mkdir(parents=True)
        (run / "mission.json").write_text(json.dumps({"mission_id": "mission_1"}), encoding="utf-8")
        (run / "retrieval_candidates.json").write_text(json.dumps({"candidates": [{"document_id": "doc_1"}]}), encoding="utf-8")
        source_map = source_map_from_review(
            mission_id="mission_1",
            document_id="doc_1",
            source_task={"document_id": "doc_1", "provider": "mineru", "state": "done", "task_id": "private-task-id"},
            selection={"document_id": "doc_1", "segments": [{"segment_id": "segment_1", "locator": "p. 1", "kind": "paragraph", "quote": "Private bounded excerpt."}]},
            trust_status=AUTOMATED_TRIAL_SOURCE_MAP_TRUST_STATUS,
        )
        write_source_map_for_document(run, source_map)

    def test_writes_v2_count_only_audit_without_printing_paths_or_source_text(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runs = root / "runs"
            self._write_run(runs)
            private = root / "private"
            private.mkdir()
            registry = _registry()
            input_path, output_path = private / "registry.json", private / "audit-v2.json"
            input_path.write_text(json.dumps(registry), encoding="utf-8")
            stdout = io.StringIO()
            with patch("cosmatter.cli._runs_dir", return_value=runs), contextlib.redirect_stdout(stdout):
                status = main(["audit-evidence-maturity-registry", "--input", str(input_path), "--output", str(output_path)])
            result = json.loads(stdout.getvalue())
            audit = json.loads(output_path.read_text(encoding="utf-8"))

            self.assertEqual(status, 0)
            self.assertTrue(result["passed"])
            self.assertEqual(audit["schema_version"], "cosmatter.evidence-maturity-registry-audit/v2")
            self.assertEqual(audit["registry_sha256"], evidence_maturity_registry_sha256(registry))
            self.assertEqual(audit["controlled_source_map_count"], 1)
            printed = stdout.getvalue()
            self.assertNotIn(str(input_path), printed)
            self.assertNotIn(str(output_path), printed)
            self.assertNotIn("Private bounded excerpt", printed)
            self.assertNotIn("private-task-id", printed)

            with patch("cosmatter.cli._runs_dir", return_value=runs), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["audit-evidence-maturity-registry", "--input", str(input_path), "--output", str(output_path)]), 2)

    def test_rejects_standalone_audit_output_inside_runs_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runs = root / "runs"
            self._write_run(runs)
            input_path = root / "registry.json"
            output_path = runs / "run_1" / "standalone-audit.json"
            input_path.write_text(json.dumps(_registry()), encoding="utf-8")
            with patch("cosmatter.cli._runs_dir", return_value=runs), contextlib.redirect_stdout(io.StringIO()):
                status = main(["audit-evidence-maturity-registry", "--input", str(input_path), "--output", str(output_path)])
            self.assertEqual(status, 2)
            self.assertFalse(output_path.exists())

    def test_link_failure_writes_diagnostic_receipt_and_returns_two(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runs = root / "runs"
            self._write_run(runs)
            input_path, output_path = root / "registry.json", root / "failed-audit.json"
            input_path.write_text(json.dumps(_registry("missing_doc")), encoding="utf-8")
            with patch("cosmatter.cli._runs_dir", return_value=runs), contextlib.redirect_stdout(io.StringIO()):
                status = main(["audit-evidence-maturity-registry", "--input", str(input_path), "--output", str(output_path)])
            audit = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(status, 2)
            self.assertFalse(audit["passed"])
            self.assertEqual(audit["link_error_count"], 1)


if __name__ == "__main__":
    unittest.main()
