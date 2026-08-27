import copy
import json
import tempfile
import unittest
from pathlib import Path

from cosmatter.machine_config import MachineConfigError, load_machine_config, machine_config_template, validate_machine_config, write_machine_config


class MachineConfigTests(unittest.TestCase):
    def test_template_is_strictly_planning_only(self) -> None:
        config = validate_machine_config(machine_config_template())
        self.assertEqual(config["execution_mode"], "plan_only")
        self.assertFalse(config["scheduler"]["submission_enabled"])
        self.assertTrue(all(not item["enabled"] for item in config["executors"].values()))
        self.assertTrue(all(item["requires_literature_source_ids"] for item in config["task_plugins"].values()))

    def test_rejects_scheduler_or_executor_activation(self) -> None:
        scheduler_config = copy.deepcopy(machine_config_template())
        scheduler_config["scheduler"]["submission_enabled"] = True
        with self.assertRaises(MachineConfigError):
            validate_machine_config(scheduler_config)
        executor_config = copy.deepcopy(machine_config_template())
        executor_config["executors"]["dft_reference"]["enabled"] = True
        with self.assertRaises(MachineConfigError):
            validate_machine_config(executor_config)

    def test_round_trip_writes_only_valid_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = write_machine_config(Path(directory) / "machine.json")
            self.assertEqual(load_machine_config(path), machine_config_template())
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["execution_mode"], "plan_only")


if __name__ == "__main__":
    unittest.main()
