import json
import subprocess
import sys
import unittest
from pathlib import Path


class DshPluginAdmissionTests(unittest.TestCase):
    def test_production_group_is_independent_of_untrusted_market_snapshot(self) -> None:
        root = Path(__file__).resolve().parents[1]
        tool = root / "tools" / "verify_dsh_plugin_admission.py"
        result = subprocess.run([sys.executable, str(tool)], cwd=root, text=True, encoding="utf-8", capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["third_party_admission_count"], 0)
        self.assertEqual(payload["owned_bundle_count"], 7)
        self.assertEqual(payload["market_snapshot_change_count"], 0)
        self.assertNotIn("https://", result.stdout)


if __name__ == "__main__":
    unittest.main()
