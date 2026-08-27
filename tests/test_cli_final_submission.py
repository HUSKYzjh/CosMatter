import contextlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from cosmatter.cli import main


class FinalSubmissionCliTests(unittest.TestCase):
    def test_cli_creates_complete_submission_zip_only_from_reviewed_allowlist(self) -> None:
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
            run = root / "runs" / "complete_cli"
            report = run / "latex_submission"
            report.mkdir(parents=True)
            for name in ("main.tex", "references.bib", "main.pdf"):
                (report / name).write_text("reviewed report\n", encoding="utf-8")
            (report / "citation_audit.json").write_text(json.dumps({"citation_bibliography_bijection": True}), encoding="utf-8")
            (report / "latex_report_manifest.json").write_text(json.dumps({"accepted_evidence_source_disclosure_coverage": 1.0}), encoding="utf-8")
            (run / "external_resource_disclosure.json").write_text(json.dumps({
                "schema_version": "1.0",
                "trust_status": "human_completed_external_resource_disclosure_not_execution_evidence",
                "resources": [{
                    "name": "OpenAlex", "category": "database", "purpose": "metadata",
                    "access_method": "API", "version_or_access_date": "2026-08-14",
                    "license_or_terms": "provider terms", "redistribution_boundary": "metadata only",
                    "used_in_final_result": False,
                }],
                "reviewer": "reviewer", "review_date": "2026-08-14",
            }), encoding="utf-8")
            (run / "private_fulltext.md").write_text("never packaged", encoding="utf-8")
            output = io.StringIO()
            with patch("cosmatter.cli.AGENT_ROOT", root), patch("cosmatter.cli._runs_dir", return_value=root / "runs"), contextlib.redirect_stdout(output):
                status = main(["build-final-submission-package", "--run-id", "complete_cli"])
            package = root / "submission" / "cosmatter_preliminary_complete_cli.zip"
            with zipfile.ZipFile(package) as archive:
                names = archive.namelist()
        self.assertEqual(status, 0, output.getvalue())
        self.assertIn("report/main.pdf", names)
        self.assertIn("source/src/cosmatter/app.py", names)
        self.assertFalse(any("private_fulltext" in name for name in names))


if __name__ == "__main__":
    unittest.main()
