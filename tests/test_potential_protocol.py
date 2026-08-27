import copy
import tempfile
import unittest
from pathlib import Path

from cosmatter.potential_benchmark import generate_potential_boundary_plan, write_potential_plan
from cosmatter.potential_protocol import (
    PotentialProtocolError,
    build_potential_execution_protocol,
    execution_protocol_template,
    write_potential_execution_protocol,
)


class PotentialProtocolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.plan = generate_potential_boundary_plan(
            system_label="BiFeO3 films", potential_models=("dp", "nequip"),
            reference_method="approved DFT single point", seed=8,
            controls={"strain_percent": (-2.0, 2.0)},
        )

    def _reviewed_protocol(self) -> dict:
        protocol = execution_protocol_template(plan=self.plan)
        protocol["reference_protocol"]["version_or_input_set"] = "VASP 6.4; PBEsol input set v1"
        protocol["reference_protocol"]["convergence_or_sampling_boundary"] = "Reviewed convergence protocol v1"
        for model in protocol["potential_models"]:
            model.update({
                "implementation": "approved external inference runner",
                "version_or_commit": "commit-123abc",
                "license_or_terms": "reviewed locally before use",
                "artifact_identifier": "model-registry-id-1",
            })
        protocol["structure_generation"].update({
            "generator": "approved structure generator",
            "generator_version_or_commit": "generator-v1",
        })
        protocol["measurement_environment"].update({
            "hardware_class": "single GPU worker",
            "accelerator_or_cpu": "approved accelerator class",
            "parallelism": "one GPU, one worker",
            "numerical_precision": "float64",
        })
        protocol["approval"].update({
            "reviewer": "reviewer", "allowed_external_runner": "approved cluster queue",
        })
        return protocol

    def test_reviewed_protocol_is_bound_to_tasks_and_can_be_written(self) -> None:
        protocol = self._reviewed_protocol()
        self.assertEqual(build_potential_execution_protocol(plan=self.plan, payload=protocol)["plan_sha256"], protocol["plan_sha256"])
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            write_potential_plan(run, self.plan)
            path = write_potential_execution_protocol(run, protocol)
            self.assertTrue(path.is_file())

    def test_approved_protocol_binds_result_import(self) -> None:
        from cosmatter.potential_benchmark import evaluate_potential_results

        protocol = self._reviewed_protocol()
        protocol["approval"].update({"status": "approved_for_external_execution", "approved_on": "2026-08-14"})
        results = [
            {"task_id": task["task_id"], "model_id": model, "atom_count": 20, "reference_energy_ev": -1.0,
             "predicted_energy_ev": -0.99, "force_rmse_ev_per_a": 0.01, "wall_time_seconds": 1.0}
            for task in self.plan["tasks"] for model in self.plan["potential_models"]
        ]
        report = evaluate_potential_results(plan=self.plan, results=results, execution_protocol=protocol)
        self.assertEqual(report["execution_protocol_status"], "approved_for_external_execution")
        protocol["approval"]["status"] = "pending_human_approval"
        protocol["approval"]["approved_on"] = ""
        from cosmatter.potential_benchmark import PotentialBenchmarkError
        with self.assertRaises(PotentialBenchmarkError):
            evaluate_potential_results(plan=self.plan, results=results, execution_protocol=protocol)


    def test_rejects_missing_measurement_environment_disclosure(self) -> None:
        malformed = self._reviewed_protocol()
        malformed["measurement_environment"].pop("timing_scope")
        with self.assertRaises(PotentialProtocolError):
            build_potential_execution_protocol(plan=self.plan, payload=malformed)


    def test_rejects_changed_task_coordinate_or_private_path(self) -> None:
        malformed = self._reviewed_protocol()
        malformed["task_packets"][0]["controls"]["strain_percent"] = 9.0
        with self.assertRaises(PotentialProtocolError):
            build_potential_execution_protocol(plan=self.plan, payload=malformed)
        malformed = self._reviewed_protocol()
        malformed["potential_models"][0]["artifact_identifier"] = "C:\\Users\\researcher\\model.pt"
        with self.assertRaises(PotentialProtocolError):
            build_potential_execution_protocol(plan=self.plan, payload=malformed)


if __name__ == "__main__":
    unittest.main()
