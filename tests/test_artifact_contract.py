import json
import tempfile
import unittest
from pathlib import Path

from cosmatter.artifact_contract import ArtifactContractError, approved_artifact_download, artifact_manifest, validate_artifact_manifest


class ArtifactContractTests(unittest.TestCase):
    def _ui(self, run: Path, mission_id: str, **extra) -> None:
        payload = {"schema_version": "1.0", "mission_id": mission_id, "mission": {"mission_id": mission_id}, **extra}
        (run / "ui.json").write_text(json.dumps(payload), encoding="utf-8")

    def test_manifest_uses_fixed_symbols_hashes_and_no_local_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            self._ui(run, "mission_safe")

            manifest = artifact_manifest(run_dir=run, run_id="safe_run", mission_id="mission_safe")
            download = approved_artifact_download(run_dir=run, run_id="safe_run", mission_id="mission_safe", artifact_id="ui_bundle")

            self.assertEqual(manifest["schema_version"], "cosmatter.artifact/v1")
            self.assertEqual(manifest["artifacts"][0]["download_path"], "/api/runs/safe_run/artifacts/ui_bundle")
            self.assertNotIn(str(run), json.dumps(manifest))
            self.assertEqual(download.media_type, "application/json; charset=utf-8")
            self.assertEqual(download.filename, "ui.json")

    def test_unsafe_or_unreviewed_files_are_not_downloadable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            self._ui(run, "mission_safe", source_url="https://private.example/paper.pdf")
            (run / "research_report.md").write_text("# report", encoding="utf-8")
            manifest = artifact_manifest(run_dir=run, run_id="safe_run", mission_id="mission_safe")
            self.assertEqual(manifest["artifact_count"], 0)
            with self.assertRaises(ArtifactContractError):
                approved_artifact_download(run_dir=run, run_id="safe_run", mission_id="mission_safe", artifact_id="ui_bundle")
            with self.assertRaises(ArtifactContractError):
                approved_artifact_download(run_dir=run, run_id="safe_run", mission_id="mission_safe", artifact_id="research_report")

    def test_report_requires_the_matching_report_audit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            (run / "mission_report.json").write_text(json.dumps({
                "mission_id": "mission_safe", "summary": "safe", "evidence_ids": ["evidence_1"], "limitations": ["limited"],
                "next_steps": ["review"], "research_gap_candidate_ids": [], "report_id": "report_1", "created_at": "fixture",
            }), encoding="utf-8")
            (run / "research_report.md").write_text("# Reviewed report\nNo raw URL.", encoding="utf-8")
            manifest = artifact_manifest(run_dir=run, run_id="safe_run", mission_id="mission_safe")
            self.assertEqual(manifest["artifact_count"], 0)
            (run / "report_evidence_audit.json").write_text(json.dumps({
                "schema_version": "1.3", "mission_id": "mission_safe",
                "trust_status": "artifact_level_identifier_audit_not_scientific_validity_assessment",
            }), encoding="utf-8")
            manifest = artifact_manifest(run_dir=run, run_id="safe_run", mission_id="mission_safe")
            self.assertEqual({item["artifact_id"] for item in manifest["artifacts"]}, {"mission_report", "research_report"})

    def test_manifest_schema_rejects_unknown_download_surface(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            self._ui(run, "mission_safe")
            manifest = artifact_manifest(run_dir=run, run_id="safe_run", mission_id="mission_safe")
            manifest["artifacts"][0]["download_path"] = "/api/runs/safe_run/pdf/private"
            with self.assertRaises(ArtifactContractError):
                validate_artifact_manifest(manifest, expected_run_id="safe_run", expected_mission_id="mission_safe")


if __name__ == "__main__":
    unittest.main()
