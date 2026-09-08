from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from cosmatter.dsh_profile_status import EXPECTED_DSH_PACKAGES, dsh_profile_status


class DshProfileStatusTests(unittest.TestCase):
    def test_reports_complete_local_links_without_disclosing_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            profile = home / "profiles" / "tui"
            profile.mkdir(parents=True)
            dependencies = {package: f"link:D:/private/{index}" for index, package in enumerate(EXPECTED_DSH_PACKAGES)}
            (profile / "package.json").write_text(json.dumps({"name": "dsh-profile-tui", "dependencies": dependencies}), encoding="utf-8")
            status = dsh_profile_status(dsh_home=home)
            self.assertEqual(status["installation_state"], "installed")
            self.assertEqual(status["installed_bundle_count"], 7)
            self.assertTrue(all(item["dependency_kind"] == "local_link" for item in status["packages"]))
            self.assertNotIn("D:/private", json.dumps(status))
            self.assertEqual(status["composition_status"], "not_checked_by_http_api")

    def test_fails_closed_for_partial_missing_and_malformed_profiles(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            self.assertEqual(dsh_profile_status(dsh_home=home)["installation_state"], "not_installed")
            profile = home / "profiles" / "tui"
            profile.mkdir(parents=True)
            (profile / "package.json").write_text(json.dumps({"dependencies": {EXPECTED_DSH_PACKAGES[0]: "1.0.0"}}), encoding="utf-8")
            self.assertEqual(dsh_profile_status(dsh_home=home)["installation_state"], "partial")
            (profile / "package.json").write_text("{", encoding="utf-8")
            malformed = dsh_profile_status(dsh_home=home)
            self.assertEqual(malformed["installation_state"], "unavailable")
            self.assertEqual(malformed["installed_bundle_count"], 0)
            (profile / "package.json").write_text("[]", encoding="utf-8")
            self.assertEqual(dsh_profile_status(dsh_home=home)["installation_state"], "unavailable")

    def test_rejects_an_unbounded_profile_name(self) -> None:
        with self.assertRaises(ValueError):
            dsh_profile_status("../private")


if __name__ == "__main__":
    unittest.main()
