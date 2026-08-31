from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


class DshReleaseGateTests(unittest.TestCase):
    def test_keyless_release_gate_matches_all_seven_bundle_manifests(self) -> None:
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [sys.executable, "tools/verify_dsh_plugin_release.py"], cwd=root,
            text=True, encoding="utf-8", capture_output=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"bundle_count": 7', result.stdout)
        self.assertIn('"profile_smoke": false', result.stdout)


if __name__ == "__main__":
    unittest.main()
