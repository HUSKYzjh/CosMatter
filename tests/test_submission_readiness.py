import json
import tempfile
import unittest
from pathlib import Path

from cosmatter.submission_readiness import submission_readiness


class SubmissionReadinessTests(unittest.TestCase):
    def test_accepts_source_requirements_and_run_scoped_latex_package(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "configs").mkdir()
            (root / "frontend" / "src").mkdir(parents=True)
            (root / "src" / "cosmatter").mkdir(parents=True)
            (root / "tests").mkdir()
            (root / "src" / "cosmatter" / "app.py").write_text("pass\n", encoding="utf-8")
            (root / "tests" / "test_app.py").write_text("pass\n", encoding="utf-8")
            (root / "frontend" / "src" / "app.ts").write_text("export {}\n", encoding="utf-8")
            for name in ("pyproject.toml", "README.md", "REPRODUCIBILITY.md", "LICENSE", "CONTRIBUTING.md", "CITATION.cff", "requirements.lock"):
                (root / name).write_text("present\n", encoding="utf-8")
            (root / ".gitignore").write_text(".env\nruns/\n.private/\n", encoding="utf-8")
            (root / "frontend" / "package-lock.json").write_text("{}\n", encoding="utf-8")
            (root / "configs" / "reproducibility.example.json").write_text(json.dumps({
                "python": "3.12", "node": "24", "random_seed": 8,
                "key_parameters": {"question_candidate_minimum_characters": 12, "question_candidate_debounce_ms": 800, "potential_boundary_samples_per_regime_default": 3, "potential_boundary_samples_per_regime_allowed_range": [1, 32], "ising_default_seed": 8},
                "external_resources": [{"name": "OpenAlex", "purpose": "metadata", "version_or_access_date": "2026-08-14", "required": False}],
            }), encoding="utf-8")
            run = root / "runs" / "demo"
            run.mkdir(parents=True)
            (run / "external_resource_disclosure.json").write_text(json.dumps({
                "schema_version": "1.0",
                "trust_status": "human_completed_external_resource_disclosure_not_execution_evidence",
                "resources": [{
                    "name": "OpenAlex", "category": "database", "purpose": "metadata",
                    "access_method": "API", "version_or_access_date": "2026-08-13",
                    "license_or_terms": "provider terms",
                    "redistribution_boundary": "metadata only", "used_in_final_result": False,
                }],
                "reviewer": "reviewer", "review_date": "2026-08-13",
            }), encoding="utf-8")
            package = run / "latex_submission"
            package.mkdir()
            (package / "latex_report_manifest.json").write_text(json.dumps({
                "accepted_evidence_source_disclosure_coverage": 1.0,
            }), encoding="utf-8")
            for name in ("main.tex", "references.bib", "main.pdf"):
                (package / name).write_text("present\n", encoding="utf-8")
            (package / "citation_audit.json").write_text(json.dumps({"citation_bibliography_bijection": True}), encoding="utf-8")
            report = submission_readiness(repository_root=root, run_dir=run)
            (run / "test_only_delegated_review.json").write_text(json.dumps({
                "trust_status": "user_authorized_delegated_test_review_not_scientific_evidence",
                "scientific_use_prohibited": True,
            }), encoding="utf-8")
            delegated_report = submission_readiness(repository_root=root, run_dir=run)
        self.assertTrue(report["ready"])
        self.assertTrue(report["checks"]["latex_main.pdf"])
        self.assertTrue(report["checks"]["run_external_resource_disclosure"])
        self.assertTrue(report["checks"]["key_parameters_declared"])
        self.assertTrue(report["checks"]["python_source_present"])
        self.assertFalse(delegated_report["ready"])
        self.assertFalse(delegated_report["checks"]["run_not_delegated_test_review"])

    def test_rejects_inconsistent_existing_real_evaluation_record(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "configs").mkdir()
            (root / "frontend" / "src").mkdir(parents=True)
            (root / "src" / "cosmatter").mkdir(parents=True)
            (root / "tests").mkdir()
            (root / "src" / "cosmatter" / "app.py").write_text("pass\n", encoding="utf-8")
            (root / "tests" / "test_app.py").write_text("pass\n", encoding="utf-8")
            (root / "frontend" / "src" / "app.ts").write_text("export {}\n", encoding="utf-8")
            for name in ("pyproject.toml", "README.md", "REPRODUCIBILITY.md", "LICENSE", "CONTRIBUTING.md", "CITATION.cff", "requirements.lock"):
                (root / name).write_text("present\n", encoding="utf-8")
            (root / ".gitignore").write_text(".env\nruns/\n.private/\n", encoding="utf-8")
            (root / "frontend" / "package-lock.json").write_text("{}\n", encoding="utf-8")
            (root / "configs" / "reproducibility.example.json").write_text(json.dumps({
                "python": "3.12", "node": "24", "random_seed": 8,
                "key_parameters": {"question_candidate_minimum_characters": 12, "question_candidate_debounce_ms": 800, "potential_boundary_samples_per_regime_default": 3, "potential_boundary_samples_per_regime_allowed_range": [1, 32], "ising_default_seed": 8},
                "external_resources": [{"name": "OpenAlex", "purpose": "metadata", "version_or_access_date": "2026-08-14", "required": False}],
            }), encoding="utf-8")
            run = root / "runs" / "demo"
            run.mkdir(parents=True)
            (run / "external_resource_disclosure.json").write_text(json.dumps({
                "schema_version": "1.0", "trust_status": "human_completed_external_resource_disclosure_not_execution_evidence",
                "resources": [{"name": "OpenAlex", "category": "database", "purpose": "metadata", "access_method": "API", "version_or_access_date": "2026-08-14", "license_or_terms": "provider terms", "redistribution_boundary": "metadata only", "used_in_final_result": False}], "reviewer": "reviewer", "review_date": "2026-08-14",
            }), encoding="utf-8")
            package = run / "latex_submission"
            package.mkdir()
            for name in ("main.tex", "references.bib", "main.pdf"):
                (package / name).write_text("present\n", encoding="utf-8")
            (package / "citation_audit.json").write_text(json.dumps({"citation_bibliography_bijection": True}), encoding="utf-8")
            (package / "latex_report_manifest.json").write_text(json.dumps({"accepted_evidence_source_disclosure_coverage": 1.0}), encoding="utf-8")
            mission = {"question": "q", "material": "BiFeO3", "property_name": "phase", "scope": "scope", "mission_id": "mission_1"}
            (run / "mission.json").write_text(json.dumps(mission), encoding="utf-8")
            corpus = {"mission_id": "mission_1", "corpus_id": "bfo_90_v1", "documents": [{"document_id": "d1"}]}
            (run / "corpus_manifest.json").write_text(json.dumps(corpus), encoding="utf-8")
            record = {"schema_version": "1.0", "mission_id": "mission_1", "corpus_id": "bfo_90_v1", "trust_status": "human_reviewed_real_corpus_evaluation_run_record", "frozen_corpus_document_count": 1, "execution_completed_on": "2026-08-14", "code_revision": "snapshot", "service_and_model_disclosure": {key: "not_used" for key in ("llm", "embedding", "reranker", "sciverse", "mineru", "local_corpus")}, "human_review_disclosure": {key: "complete" for key in ("relevance_gold", "material_fact_gold", "evidence_quality", "gap_expert_review")}, "metric_artifacts": {key: "generated" for key in ("human_retrieval_evaluation", "human_material_fact_evaluation", "human_evidence_quality_evaluation", "human_gap_evaluation")}, "failure_case_log_status": "recorded", "api_cost_and_latency_status": "recorded", "submission_truth_check": "completed"}
            (run / "real_corpus_evaluation_run_record.json").write_text(json.dumps(record), encoding="utf-8")
            for name in ("human_retrieval_evaluation.json", "human_material_fact_evaluation.json", "human_evidence_quality_evaluation.json", "human_gap_evaluation.json"):
                (run / name).write_text("{}", encoding="utf-8")
            report = submission_readiness(repository_root=root, run_dir=run)
        self.assertFalse(report["ready"])
        self.assertFalse(report["checks"]["run_frozen_question_set_consistent"])
        self.assertFalse(report["checks"]["run_real_evaluation_record_consistent"])
    def test_reports_missing_license_without_claiming_ready(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report = submission_readiness(repository_root=Path(directory))
        self.assertFalse(report["ready"])
        self.assertFalse(report["checks"]["license"])


if __name__ == "__main__":
    unittest.main()
