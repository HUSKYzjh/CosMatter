import copy
import json
import tempfile
import unittest
from pathlib import Path

from cosmatter.run_package import RunPackageError, export_run_package, restore_run_package, validate_run_package
from cosmatter.workflow_readiness import WorkflowReadinessError, continuation_next_stage


class RunPackageTests(unittest.TestCase):
    def test_allowlisted_package_detects_tampering_and_omits_private_values(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory) / "run_a"; run.mkdir()
            mission = {"mission_id": "mission_a", "question": "Map material reports", "material": "BiFeO3", "property_name": "phase stability", "scope": "films"}
            (run / "mission.json").write_text(json.dumps(mission), encoding="utf-8")
            package = export_run_package(run)
            validate_run_package(package)
            altered = copy.deepcopy(package); altered["mission"]["question"] = "changed"
            with self.assertRaises(RunPackageError):
                validate_run_package(altered)
            restored = restore_run_package(Path(directory) / "runs", "resume_a", package)
            self.assertTrue((restored / "mission.json").is_file())

    def test_workflow_readiness_keeps_the_audited_continuation_stage(self):
        readiness = {
            "schema_version": "1.0",
            "mission_id": "mission_a",
            "trust_status": "derived_workflow_readiness_not_scientific_evidence",
            "stages": [
                {"stage": stage, "status": "completed" if index < 3 else ("waiting_human_review" if index == 3 else "blocked"), "counts": {}}
                for index, stage in enumerate(("intake", "plan", "retrieval", "screening", "parse", "extraction", "gap", "report", "evaluation"))
            ],
            "next_stage": "screening",
        }
        self.assertEqual(continuation_next_stage(readiness, "mission_a"), "screening")
        with self.assertRaises(WorkflowReadinessError):
            continuation_next_stage(readiness, "other_mission")
        inconsistent = copy.deepcopy(readiness)
        inconsistent["next_stage"] = "gap"
        with self.assertRaises(WorkflowReadinessError):
            continuation_next_stage(inconsistent, "mission_a")

