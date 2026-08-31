import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cosmatter.models import MissionBrief
from cosmatter.workflow_dag import WorkflowDagError, load_workflow_dag_definition, validate_workflow_dag_definition, validate_workflow_dag_projection, workflow_dag_projection


class WorkflowDagTests(unittest.TestCase):
    def setUp(self) -> None:
        self.mission = MissionBrief("private research question", "BiFeO3", "phase stability", "private scope", mission_id="mission_dag")

    def test_empty_run_projects_fixed_serial_dag_without_content_or_authority(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            projection = workflow_dag_projection("dag_001", Path(directory), self.mission)
        self.assertEqual(projection["schema_version"], "cosmatter.workflow-dag/v1")
        self.assertEqual(projection["max_concurrency"], 1)
        self.assertEqual(projection["scheduler_status"], "declarative_only_no_execution_authorization")
        self.assertEqual(projection["eligible_stages"], [])
        self.assertTrue(projection["human_review_required"])
        self.assertEqual([item["stage"] for item in projection["stages"]], ["intake", "plan", "retrieval", "screening", "parse", "extraction", "gap", "report", "evaluation"])
        self.assertEqual(projection["stages"][2]["depends_on"], ["plan"])
        rendered = json.dumps(projection)
        self.assertNotIn("private research question", rendered)
        self.assertNotIn("BiFeO3", rendered)
        self.assertNotIn("private scope", rendered)

    def test_definition_rejects_nonserial_concurrency_and_unknown_descriptor(self) -> None:
        definition = load_workflow_dag_definition()
        definition["max_concurrency"] = 2
        with self.assertRaises(WorkflowDagError):
            validate_workflow_dag_definition(definition)
        definition = load_workflow_dag_definition()
        definition["stages"][2]["depends_on"] = ["intake"]
        with self.assertRaises(WorkflowDagError):
            validate_workflow_dag_definition(definition)
        definition = load_workflow_dag_definition()
        definition["stages"][2]["allowed_descriptors"] = ["unknown.execute"]
        with self.assertRaises(WorkflowDagError):
            validate_workflow_dag_definition(definition)

    def test_projection_rejects_mutated_eligibility_and_dynamic_field(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            projection = workflow_dag_projection("dag_001", Path(directory), self.mission)
        projection["eligible_stages"] = ["retrieval"]
        with self.assertRaises(WorkflowDagError):
            validate_workflow_dag_projection(projection, expected_run_id="dag_001", expected_mission_id=self.mission.mission_id)
        with tempfile.TemporaryDirectory() as directory:
            projection = workflow_dag_projection("dag_001", Path(directory), self.mission)
        projection["command"] = "run anything"
        with self.assertRaises(WorkflowDagError):
            validate_workflow_dag_projection(projection, expected_run_id="dag_001", expected_mission_id=self.mission.mission_id)


if __name__ == "__main__":
    unittest.main()
