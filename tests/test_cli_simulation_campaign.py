import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cosmatter.cli import main
from cosmatter.simulation_campaign import SIMULATION_CAMPAIGN_BOUNDARY, SIMULATION_CAMPAIGN_SCHEMA_VERSION, SIMULATION_CAMPAIGN_TRUST_STATUS
from cosmatter.source_map import source_map_from_review, write_source_map_for_document


class SimulationCampaignCliTests(unittest.TestCase):
    def test_cli_records_only_an_approved_plan_and_never_an_execution_request(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = io.StringIO()
            with patch("cosmatter.cli._runs_dir", return_value=root / "runs"), contextlib.redirect_stdout(output):
                self.assertEqual(main([
                    "create-mission", "--run-id", "campaign_cli", "--mission-id", "mission_campaign_cli",
                    "--question", "Can the reviewed boundary support a DFT plan?", "--material", "BiFeO3",
                    "--property", "phase stability", "--scope", "epitaxial films",
                ]), 0, output.getvalue())
                self.assertEqual(main([
                    "assign-fleet", "--run-id", "campaign_cli", "--mission-id", "mission_campaign_cli",
                    "--question", "Can the reviewed boundary support a DFT plan?", "--material", "BiFeO3",
                    "--property", "phase stability", "--scope", "epitaxial films",
                ]), 0, output.getvalue())
                self.assertEqual(main(["create-simulation-campaign-template", "--run-id", "campaign_cli"]), 0, output.getvalue())
            run_dir = root / "runs" / "campaign_cli"
            self.assertTrue((run_dir / "simulation_campaign_template.json").is_file())
            (run_dir / "evidence_cards.json").write_text(json.dumps([{
                "evidence_id": "evidence_accepted", "claim": "bounded claim", "stance": "support",
                "material": "BiFeO3", "property_name": "phase stability", "conditions": {"form": "film"},
                "quote": "bounded quote", "provenance": {"document_id": "doc_1", "locator": "page:1", "source": "fixture", "access_policy": "oa"},
            }]), encoding="utf-8")
            (run_dir / "verification_decisions.json").write_text(json.dumps([{
                "mission_id": "mission_campaign_cli", "evidence_id": "evidence_accepted", "status": "accepted", "reason": "complete",
            }]), encoding="utf-8")
            write_source_map_for_document(run_dir, source_map_from_review(
                mission_id="mission_campaign_cli", document_id="doc_1",
                source_task={"provider": "mineru", "task_id": "task_fixture", "state": "done", "document_id": "doc_1"},
                selection={"document_id": "doc_1", "segments": [{"segment_id": "s1", "locator": "page:1", "kind": "paragraph", "quote": "bounded quote"}]},
            ))
            campaign = {
                "schema_version": "1.0", "trust_status": SIMULATION_CAMPAIGN_TRUST_STATUS,
                "campaign_id": "campaign_cli_001", "mission_id": "mission_campaign_cli", "simulation_kind": "md",
                "evidence_ids": ["evidence_accepted"],
                "hypothesis": {"statement": "bounded hypothesis", "variables": "temperature", "control": "composition", "observable": "aggregate summary", "falsifier": "no difference"},
                "protocol": {"engine": "external MD engine", "recipe_id": "recipe_001", "method_boundary": "reviewed method", "convergence_or_sampling_boundary": "reviewed sampling", "result_summary_boundary": "aggregate summary only"},
                "input_manifest": {"input_count": 1, "inputs": [{"input_id": "manifest_001", "sha256": "b" * 64, "source_kind": "reviewed manifest", "license_status": "reviewed license clearance"}]},
                "execution_profile": {"mode": "disabled", "adapter_kind": "none", "allowed_engines": [], "allowed_recipe_ids": [], "max_jobs": 0, "max_gpu_jobs": 0, "max_dft_jobs": 0, "scheduler_submission_enabled": False, "polling_enabled": False},
                "approval": {"status": "approved_plan_only", "reviewer": "human reviewer", "approved_on": "2026-09-02", "rationale": "bounded evidence"},
                "execution_permitted": False, "execution_boundary": SIMULATION_CAMPAIGN_BOUNDARY,
            }
            source = root / "campaign.json"
            source.write_text(json.dumps(campaign), encoding="utf-8")
            with patch("cosmatter.cli._runs_dir", return_value=root / "runs"), contextlib.redirect_stdout(output):
                status = main(["approve-simulation-campaign", "--run-id", "campaign_cli", "--input", str(source)])
                denial_status = main(["execute-simulation-campaign", "--run-id", "campaign_cli"])
                export_status = main(["export-ui", "--run-id", "campaign_cli"])
            saved = json.loads((run_dir / "simulation_campaign.json").read_text(encoding="utf-8"))
            self.assertEqual(export_status, 0, output.getvalue())
            bundle = json.loads((run_dir / "ui.json").read_text(encoding="utf-8"))
            events = (run_dir / "events.jsonl").read_text(encoding="utf-8")

        self.assertEqual(status, 0, output.getvalue())
        self.assertEqual(denial_status, 3, output.getvalue())
        self.assertFalse(saved["execution_permitted"])
        self.assertEqual(saved["execution_profile"]["mode"], "disabled")
        self.assertIn("simulation_campaign_approved_plan_only", events)
        self.assertNotIn("scheduler_submission", events)
        self.assertIn("simulation_campaign_execution_denied", events)
        self.assertEqual(bundle["simulation_campaign"]["chain"], {"evidence": "bound", "hypothesis": "approved", "protocol": "approved", "execution": "blocked"})
        self.assertNotIn("evidence_accepted", json.dumps(bundle["simulation_campaign"]))


if __name__ == "__main__":
    unittest.main()
