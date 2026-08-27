import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cosmatter.cli import main


class PotentialProtocolCliTests(unittest.TestCase):
    def test_cli_writes_and_records_a_plan_bound_nonexecuting_protocol(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            controls = root / "controls.json"
            controls.write_text(json.dumps({"strain_percent": [-2.0, 2.0]}), encoding="utf-8")
            output = io.StringIO()
            with patch("cosmatter.cli._runs_dir", return_value=root / "runs"), contextlib.redirect_stdout(output):
                self.assertEqual(main([
                    "create-potential-benchmark-plan", "--run-id", "protocol_cli", "--system", "BiFeO3",
                    "--model", "baseline", "--model", "candidate", "--reference-method", "DFT protocol",
                    "--controls", str(controls), "--seed", "8",
                ]), 0, output.getvalue())
                self.assertEqual(main(["create-potential-execution-protocol-template", "--run-id", "protocol_cli"]), 0, output.getvalue())
            template = root / "runs" / "protocol_cli" / "potential_execution_protocol_template.json"
            payload = json.loads(template.read_text(encoding="utf-8"))
            payload["reference_protocol"]["version_or_input_set"] = "VASP 6.4"
            payload["reference_protocol"]["convergence_or_sampling_boundary"] = "reviewed settings"
            for model in payload["potential_models"]:
                model.update({"implementation": "runner", "version_or_commit": "commit-1", "license_or_terms": "terms", "artifact_identifier": "registry-id"})
            payload["structure_generation"].update({"generator": "generator", "generator_version_or_commit": "v1"})
            payload["measurement_environment"].update({"hardware_class": "GPU node", "accelerator_or_cpu": "test accelerator", "parallelism": "one GPU", "numerical_precision": "float64"})
            payload["approval"].update({"reviewer": "reviewer", "allowed_external_runner": "cluster"})
            reviewed = root / "reviewed_protocol.json"
            reviewed.write_text(json.dumps(payload), encoding="utf-8")
            with patch("cosmatter.cli._runs_dir", return_value=root / "runs"), contextlib.redirect_stdout(output):
                status = main(["record-potential-execution-protocol", "--run-id", "protocol_cli", "--input", str(reviewed)])
                saved = root / "runs" / "protocol_cli" / "potential_execution_protocol.json"
            self.assertTrue((root / "runs" / "protocol_cli" / "potential_execution_protocol.json").is_file())

        self.assertEqual(status, 0, output.getvalue())

if __name__ == "__main__":
    unittest.main()
