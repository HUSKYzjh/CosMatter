import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from cosmatter.final_submission import FinalSubmissionError, build_final_submission_package


class FinalSubmissionTests(unittest.TestCase):
    def test_packages_allowlisted_source_and_reviewed_report_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "CosMatter"
            (root / "configs").mkdir(parents=True)
            (root / "frontend" / "src").mkdir(parents=True)
            (root / "src" / "cosmatter").mkdir(parents=True)
            (root / "tests").mkdir()
            for name in ("pyproject.toml", "README.md", "REPRODUCIBILITY.md", "LICENSE", "CONTRIBUTING.md", "CITATION.cff", "requirements.lock"):
                (root / name).write_text("present\n", encoding="utf-8")
            (root / ".gitignore").write_text(".env\nruns/\n.private/\n", encoding="utf-8")
            (root / "frontend" / "package-lock.json").write_text("{}\n", encoding="utf-8")
            (root / "configs" / "reproducibility.example.json").write_text(json.dumps({
                "python": "3.12", "node": "24", "random_seed": 8,
                "key_parameters": {"question_candidate_minimum_characters": 12, "question_candidate_debounce_ms": 800, "potential_boundary_samples_per_regime_default": 3, "potential_boundary_samples_per_regime_allowed_range": [1, 32], "ising_default_seed": 8},
                "external_resources": [{"name": "OpenAlex", "purpose": "metadata", "version_or_access_date": "2026-08-14", "required": False}],
            }), encoding="utf-8")
            (root / "src" / "cosmatter" / "app.py").write_text("print('ok')\n", encoding="utf-8")
            (root / "tests" / "test_app.py").write_text("pass\n", encoding="utf-8")
            (root / "frontend" / "src" / "app.ts").write_text("export {}\n", encoding="utf-8")
            (root / "runs" / "demo" / "latex_submission").mkdir(parents=True)
            run = root / "runs" / "demo"
            disclosure = {
                "schema_version": "1.0",
                "trust_status": "human_completed_external_resource_disclosure_not_execution_evidence",
                "resources": [{
                    "name": "OpenAlex", "category": "database", "purpose": "metadata",
                    "access_method": "API", "version_or_access_date": "2026-08-13",
                    "license_or_terms": "provider terms", "redistribution_boundary": "metadata only",
                    "used_in_final_result": False,
                }],
                "reviewer": "reviewer", "review_date": "2026-08-13",
            }
            (run / "external_resource_disclosure.json").write_text(json.dumps(disclosure), encoding="utf-8")
            report = run / "latex_submission"
            for name in ("main.tex", "references.bib", "main.pdf"):
                (report / name).write_text("present\n", encoding="utf-8")
            (report / "citation_audit.json").write_text(json.dumps({"citation_bibliography_bijection": True}), encoding="utf-8")
            (report / "latex_report_manifest.json").write_text(json.dumps({"accepted_evidence_source_disclosure_coverage": 1.0}), encoding="utf-8")
            private = run / "private_full.md"
            private.write_text("must not package", encoding="utf-8")
            output = root / "submission" / "final.zip"
            result = build_final_submission_package(repository_root=root, run_dir=run, output_path=output)
            with zipfile.ZipFile(output) as archive:
                names = archive.namelist()
        self.assertTrue(result["package_sha256"])
        self.assertIn("source/src/cosmatter/app.py", names)
        self.assertIn("report/main.pdf", names)
        self.assertNotIn("runs/demo/private_full.md", names)

    def test_includes_aggregate_real_evaluation_only_after_completed_consistent_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "CosMatter"
            root.mkdir()
            run = root / "runs" / "completed"
            (run / "latex_submission").mkdir(parents=True)
            source = root / "source.py"
            source.write_text("print('ok')\n", encoding="utf-8")
            for name in ("main.tex", "references.bib", "main.pdf", "citation_audit.json", "latex_report_manifest.json"):
                (run / "latex_submission" / name).write_text("{}\n", encoding="utf-8")
            (run / "external_resource_disclosure.json").write_text("{}\n", encoding="utf-8")
            record = {"submission_truth_check": "completed"}
            (run / "real_corpus_evaluation_run_record.json").write_text(json.dumps(record), encoding="utf-8")
            evaluation_names = (
                "frozen_corpus_readiness.json", "human_annotation_coverage.json", "bibliographic_source_coverage.json",
                "evaluation_failure_case_log.json", "evaluation_api_cost_latency.json",
                "human_retrieval_evaluation.json", "human_material_fact_evaluation.json",
                "human_evidence_quality_evaluation.json", "human_gap_evaluation.json",
            )
            for name in evaluation_names:
                (run / name).write_text("{}\n", encoding="utf-8")
            readiness = {"ready": True, "checks": {"run_real_evaluation_record_consistent": True}, "required_human_checks": []}
            output = root / "submission" / "completed.zip"
            with patch("cosmatter.final_submission.submission_readiness", return_value=readiness), patch("cosmatter.final_submission._allowlisted_paths", return_value=[source]):
                result = build_final_submission_package(repository_root=root, run_dir=run, output_path=output)
            with zipfile.ZipFile(output) as archive:
                names = set(archive.namelist())
        self.assertEqual(len(result["real_evaluation_artifacts"]), 10)
        self.assertIn("evaluation/real_corpus_evaluation_run_record.json", names)
        self.assertIn("evaluation/human_gap_evaluation.json", names)
        self.assertIn("evaluation/bibliographic_source_coverage.json", names)
    def test_refuses_unready_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(FinalSubmissionError):
                build_final_submission_package(repository_root=root, run_dir=root / "runs" / "missing", output_path=root / "final.zip")


if __name__ == "__main__":
    unittest.main()
