from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

from cosmatter.dsh_profile_status import EXPECTED_DSH_PACKAGES, check_dsh_composition, dsh_profile_status


class DshProfileStatusTests(unittest.TestCase):
    def _write_bundle(self, profile: Path, package: str, *, manifest_name: str | None = None) -> None:
        bundle = profile / "node_modules" / package
        (bundle / "lib").mkdir(parents=True)
        (bundle / "package.json").write_text(json.dumps({
            "name": manifest_name or package,
            "main": "./lib/index.js",
            "dsh": {"bundle": {"patch": "./cordis.patch.yml"}},
        }), encoding="utf-8")
        (bundle / "lib" / "index.js").write_text("throw new Error('status must not load this')", encoding="utf-8")
        (bundle / "cordis.patch.yml").write_text("private-patch-content", encoding="utf-8")

    def test_reports_complete_local_links_without_disclosing_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            profile = home / "profiles" / "tui"
            profile.mkdir(parents=True)
            dependencies = {package: f"link:D:/private/{index}" for index, package in enumerate(EXPECTED_DSH_PACKAGES)}
            (profile / "package.json").write_text(json.dumps({"name": "dsh-profile-tui", "dependencies": dependencies}), encoding="utf-8")
            for package in EXPECTED_DSH_PACKAGES:
                self._write_bundle(profile, package)
            status = dsh_profile_status(dsh_home=home)
            self.assertEqual(status["installation_state"], "installed")
            self.assertEqual(status["declared_bundle_count"], 7)
            self.assertEqual(status["installed_bundle_count"], 7)
            self.assertTrue(all(item["dependency_kind"] == "local_link" for item in status["packages"]))
            self.assertTrue(all(item["install_status"] == "verified" for item in status["packages"]))
            self.assertNotIn("D:/private", json.dumps(status))
            self.assertNotIn("private-patch-content", json.dumps(status))
            self.assertEqual(status["composition_status"], "not_checked_by_http_api")

    def test_separates_declared_dependencies_from_missing_or_invalid_installations(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            profile = home / "profiles" / "tui"
            profile.mkdir(parents=True)
            present, missing, wrong_name, missing_patch, undeclared, *_ = EXPECTED_DSH_PACKAGES
            dependencies = dict.fromkeys((present, missing, wrong_name, missing_patch), "link:private")
            (profile / "package.json").write_text(json.dumps({"dependencies": dependencies}), encoding="utf-8")
            self._write_bundle(profile, present)
            self._write_bundle(profile, wrong_name, manifest_name="unrelated-package")
            self._write_bundle(profile, missing_patch)
            (profile / "node_modules" / missing_patch / "cordis.patch.yml").unlink()
            self._write_bundle(profile, undeclared)
            status = dsh_profile_status(dsh_home=home)
            self.assertEqual(status["installation_state"], "partial")
            self.assertEqual(status["declared_bundle_count"], 4)
            self.assertEqual(status["installed_bundle_count"], 1)
            self.assertEqual(
                [item["install_status"] for item in status["packages"][:5]],
                ["verified", "missing_bundle", "invalid_bundle", "missing_bundle", "not_declared"],
            )

    def test_fails_closed_for_partial_missing_and_malformed_profiles(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            self.assertEqual(dsh_profile_status(dsh_home=home)["installation_state"], "not_installed")
            profile = home / "profiles" / "tui"
            profile.mkdir(parents=True)
            (profile / "package.json").write_text(json.dumps({"dependencies": {EXPECTED_DSH_PACKAGES[0]: "1.0.0"}}), encoding="utf-8")
            self.assertEqual(dsh_profile_status(dsh_home=home)["installation_state"], "not_installed")
            (profile / "package.json").write_text("{", encoding="utf-8")
            malformed = dsh_profile_status(dsh_home=home)
            self.assertEqual(malformed["installation_state"], "unavailable")
            self.assertEqual(malformed["installed_bundle_count"], 0)
            (profile / "package.json").write_text("[]", encoding="utf-8")
            self.assertEqual(dsh_profile_status(dsh_home=home)["installation_state"], "unavailable")

    def test_rejects_an_unbounded_profile_name(self) -> None:
        with self.assertRaises(ValueError):
            dsh_profile_status("../private")

    def test_terminal_check_records_only_enabled_exact_package_pairs_and_detects_profile_edits(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            profile = home / "profiles" / "tui"
            profile.mkdir(parents=True)
            (profile / "package.json").write_text("{}", encoding="utf-8")
            generated_config = profile / "cordis.yml"
            generated_config.write_text("# generated profile\n", encoding="utf-8")
            config = """
- id: cosmatter-mission
  name: '@cosmatter/dsh-mission-plugin'
  config:
    private: raw-value-must-not-be-saved
- id: cosmatter-graph
  name: '@cosmatter/dsh-graph-plugin'
  disabled: true
- id: cosmatter-policy
  name: '@cosmatter/dsh-review-plugin'
- id: cosmatter-document
  name: '@cosmatter/dsh-document-plugin'
- id: cosmatter-document
  name: '@cosmatter/dsh-document-plugin'
"""
            with patch("cosmatter.dsh_profile_status.shutil.which", return_value="local-dsh"), patch(
                "cosmatter.dsh_profile_status.subprocess.run",
                side_effect=[
                    CompletedProcess([], 0, b"0.2.2-rc.3\n"),
                    CompletedProcess([], 0, config.encode("utf-8")),
                ],
            ) as run:
                receipt = check_dsh_composition(dsh_home=home)
                self.assertEqual([call.args[0] for call in run.call_args_list], [
                    ["local-dsh", "--version"], ["local-dsh", "--profile", "tui", "--dump-config"],
                ])
                self.assertTrue(all(call.kwargs["env"]["DSH_HOME"] == str(home.resolve()) for call in run.call_args_list))
            self.assertEqual(receipt["bundles"], [EXPECTED_DSH_PACKAGES[0]])
            receipt_text = (profile / ".cosmatter-composition-check.json").read_text(encoding="utf-8")
            self.assertNotIn("raw-value-must-not-be-saved", receipt_text)
            self.assertEqual(dsh_profile_status(dsh_home=home)["composition_check"], receipt)
            self.assertNotIn("configuration_stamp", receipt)
            generated_config.write_text("# generated profile\n", encoding="utf-8")
            self.assertTrue(dsh_profile_status(dsh_home=home)["composition_check"]["matches_local_files"])
            (profile / "cordis.patch.yml").write_text("# local edit\n", encoding="utf-8")
            self.assertFalse(dsh_profile_status(dsh_home=home)["composition_check"]["matches_local_files"])


if __name__ == "__main__":
    unittest.main()
