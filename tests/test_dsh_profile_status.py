from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

from cosmatter.dsh_profile_status import (
    EXPECTED_DSH_PACKAGES, DshBundleRepairError, DshCompositionCheckError, _BUNDLE_TOOLS,
    check_dsh_composition, dsh_profile_status, open_dsh_workbench, read_dsh_evidence_link, read_dsh_recent_runs, read_dsh_run_artifacts, read_dsh_run_status, read_dsh_run_tool, read_dsh_screening_link,
    repair_dsh_bundles,
)


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

    def test_workbench_launch_rebinds_existing_tui_only_for_the_session(self) -> None:
        import yaml

        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            profile = home / "profiles" / "tui"
            profile.mkdir(parents=True)
            manifest = profile / "package.json"
            manifest.write_text(json.dumps({"dependencies": dict.fromkeys(EXPECTED_DSH_PACKAGES, "0.2.0")}), encoding="utf-8")
            rows = []
            for index, package in enumerate(EXPECTED_DSH_PACKAGES):
                self._write_bundle(profile, package)
                bundle_id = package.removeprefix("@cosmatter/dsh-").removesuffix("-plugin")
                rows.append(f"- id: cosmatter-{bundle_id}\n  name: '{package}'\n  config:\n    baseUrl: http://127.0.0.1:8765\n    timeoutMs: {7000 + index}\n")
            rows.append("- id: unrelated-account\n  config:\n    credential: never-copy-this\n")
            original = manifest.read_bytes()
            overlay = None

            def launch(arguments, *, env, check):
                nonlocal overlay
                self.assertEqual(arguments[:4], ["dsh", "--profile", "tui", "--patch"])
                self.assertEqual(env["DSH_HOME"], str(home))
                self.assertFalse(check)
                overlay = Path(arguments[-1])
                patch = overlay.read_text(encoding="utf-8")
                self.assertNotIn("never-copy-this", patch)
                self.assertEqual(yaml.safe_load(patch), [
                    {
                        "id": f"cosmatter-{package.removeprefix('@cosmatter/dsh-').removesuffix('-plugin')}",
                        "name": package,
                        "config": {"timeoutMs": 7000 + index, "baseUrl": "http://127.0.0.1:8789"},
                    }
                    for index, package in enumerate(EXPECTED_DSH_PACKAGES)
                ])
                return CompletedProcess(arguments, 23)

            with (
                patch("cosmatter.dsh_profile_status.shutil.which", return_value="dsh"),
                patch("cosmatter.dsh_profile_status._run_dsh_diagnostic", return_value="".join(rows)) as dump,
                patch("cosmatter.dsh_profile_status.subprocess.run", side_effect=launch),
            ):
                self.assertEqual(open_dsh_workbench(8789, dsh_home=home), 23)
            self.assertEqual(dump.call_args.args[1], ["--profile", "tui", "--dump-config"])
            self.assertIsNotNone(overlay)
            self.assertFalse(overlay.exists())
            self.assertEqual(manifest.read_bytes(), original)

            with (
                patch("cosmatter.dsh_profile_status.shutil.which", return_value="dsh"),
                patch("cosmatter.dsh_profile_status._run_dsh_diagnostic", return_value=rows[0].replace("  name:", "  disabled: true\n  name:")),
                patch("cosmatter.dsh_profile_status.subprocess.run") as launch,
            ):
                with self.assertRaisesRegex(DshCompositionCheckError, "disabled in tui"):
                    open_dsh_workbench(8789, dsh_home=home)
                launch.assert_not_called()

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

    def test_composition_rechecks_generated_config_but_rejects_a_change_to_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            profile = home / "profiles" / "tui"
            bundle = EXPECTED_DSH_PACKAGES[0]
            self._write_bundle(profile, bundle)
            (profile / "package.json").write_text(json.dumps({"dependencies": {bundle: "link:checkout"}}), encoding="utf-8")
            dump_count = 0
            edit_profile = False

            def diagnostic(_executable, arguments, _cwd, _environment):
                nonlocal dump_count
                if arguments == ["--version"]:
                    return "0.2.2-rc.3"
                dump_count += 1
                (profile / "cordis.yml").write_text("generated config", encoding="utf-8")
                if edit_profile:
                    (profile / "cordis.patch.yml").write_text("changed locally", encoding="utf-8")
                return f"- id: cosmatter-mission\n  name: '{bundle}'\n"

            with patch("cosmatter.dsh_profile_status.shutil.which", return_value="local-dsh"), patch(
                "cosmatter.dsh_profile_status._run_dsh_diagnostic", side_effect=diagnostic,
            ):
                check = check_dsh_composition(dsh_home=home)
                self.assertEqual(dump_count, 2)
                self.assertEqual(dsh_profile_status(dsh_home=home)["composition_check"], check)
                edit_profile = True
                with self.assertRaisesRegex(DshCompositionCheckError, "profile changed"):
                    check_dsh_composition(dsh_home=home)
                self.assertEqual(dump_count, 3)

    def test_registry_records_only_observed_tools_and_expires_when_imported_js_changes(self) -> None:
        manifest = Path(__file__).resolve().parents[1] / "plugins" / "dsh-plugin-group.json"
        declared = json.loads(manifest.read_text(encoding="utf-8"))["packages"]
        self.assertEqual(_BUNDLE_TOOLS, {entry["package"]: tuple(entry["tools"]) for entry in declared})
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            profile = home / "profiles" / "tui"
            profile.mkdir(parents=True)
            bundle = EXPECTED_DSH_PACKAGES[1]
            (profile / "package.json").write_text(json.dumps({"dependencies": {bundle: "link:private"}}), encoding="utf-8")
            self._write_bundle(profile, bundle)
            client = profile / "node_modules" / bundle / "lib" / "client.js"
            client.write_text("export const revision = 1", encoding="utf-8")
            config = f"- id: cosmatter-observability\n  name: '{bundle}'\n"

            def diagnostic(executable, arguments, cwd, environment):
                if arguments == ["--version"]:
                    return "0.2.2-rc.3"
                if arguments[-1] == "--dump-config":
                    return config
                self.assertNotEqual(environment["DSH_HOME"], str(home))
                self.assertNotIn("DEEPSEEK_API_KEY", environment)
                overlay = json.loads(Path(arguments[arguments.index("--patch") + 1]).read_text(encoding="utf-8"))
                self.assertIn({"id": "headless-runner", "disabled": True}, overlay)
                self.assertIn({"id": "llm-deepseek-account", "disabled": True}, overlay)
                self.assertEqual(overlay[-1]["insert"][0]["name"], client.with_name("index.js").resolve().as_uri())
                return 'COSMATTER_TOOL_REGISTRY ["cosmatter_workflow_status"]\n'

            with patch("cosmatter.dsh_profile_status.shutil.which", return_value="local-dsh"), patch(
                "cosmatter.dsh_profile_status._run_dsh_diagnostic", side_effect=diagnostic,
            ), patch.dict("os.environ", {"DEEPSEEK_API_KEY": "private-test-key"}):
                observed = check_dsh_composition(dsh_home=home, verify_tools=True)["tool_registry_check"]
                check_dsh_composition(dsh_home=home)
            self.assertEqual(observed["registered_tools"], ["cosmatter_workflow_status"])
            self.assertEqual(dsh_profile_status(dsh_home=home)["tool_registry_check"], observed)
            client.write_text("export const revision = 2", encoding="utf-8")
            updated = dsh_profile_status(dsh_home=home)
            self.assertTrue(updated["composition_check"]["matches_local_files"])
            self.assertFalse(updated["tool_registry_check"]["matches_local_files"])
            self.assertNotIn("runtime_stamp", json.dumps(updated))

    def test_loopback_check_binds_the_policy_probe_and_receipt_to_the_requested_port(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            profile = home / "profiles" / "tui"
            bundle = "@cosmatter/dsh-policy-plugin"
            self._write_bundle(profile, bundle)
            (profile / "package.json").write_text(json.dumps({"dependencies": {bundle: "link:private"}}), encoding="utf-8")
            output = {"registered_tools": ["cosmatter_plugin_catalogue"], "loopback_status": "verified"}

            def diagnostic(_executable, arguments, _cwd, environment):
                if arguments == ["--version"]:
                    return "0.2.2-rc.3"
                if arguments[-1] == "--dump-config":
                    return f"- id: cosmatter-policy\n  name: '{bundle}'\n"
                self.assertNotIn("DEEPSEEK_API_KEY", environment)
                overlay = json.loads(Path(arguments[arguments.index("--patch") + 1]).read_text(encoding="utf-8"))
                entries = overlay[-1]["insert"]
                self.assertEqual(entries[0]["config"], {"baseUrl": "http://127.0.0.1:8789"})
                self.assertEqual(entries[1]["config"], {"expected": sorted(_BUNDLE_TOOLS[bundle]), "checkLoopback": True})
                return "COSMATTER_TOOL_REGISTRY " + json.dumps(output)

            with patch("cosmatter.dsh_profile_status.shutil.which", return_value="local-dsh"), patch(
                "cosmatter.dsh_profile_status._run_dsh_diagnostic", side_effect=diagnostic,
            ), patch.dict("os.environ", {"DEEPSEEK_API_KEY": "credential-not-needed"}):
                check = check_dsh_composition(dsh_home=home, loopback_port=8789)["tool_registry_check"]
                self.assertEqual(check["loopback_check"], {"port": 8789, "status": "verified"})
                self.assertEqual(dsh_profile_status(dsh_home=home)["tool_registry_check"], check)
                output["loopback_status"] = "unavailable"
                failed = check_dsh_composition(dsh_home=home, loopback_port=8789)["tool_registry_check"]
                self.assertEqual(dsh_profile_status(dsh_home=home)["tool_registry_check"], failed)
                self.assertEqual(failed["loopback_check"]["status"], "unavailable")
                output.update(registered_tools=[], loopback_status="verified")
                with self.assertRaisesRegex(DshCompositionCheckError, "valid loopback check"):
                    check_dsh_composition(dsh_home=home, loopback_port=8789)
                with self.assertRaisesRegex(DshCompositionCheckError, "Port"):
                    check_dsh_composition(dsh_home=home, loopback_port=65536)
            receipt = profile / ".cosmatter-tool-registry-check.json"
            payload = json.loads(receipt.read_text(encoding="utf-8"))
            payload["loopback_check"]["private_path"] = "must be rejected"
            receipt.write_text(json.dumps(payload), encoding="utf-8")
            self.assertNotIn("tool_registry_check", dsh_profile_status(dsh_home=home))

    def test_repair_links_only_unverified_bundles_and_is_repeatable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            project = base / "checkout with spaces"
            home = base / "dsh-home"
            profile = home / "profiles" / "tui"
            installed = EXPECTED_DSH_PACKAGES[0]
            missing = list(EXPECTED_DSH_PACKAGES[1:])
            self._write_bundle(profile, installed)
            dependencies = {installed: "link:existing", "user-fixture": "link:retained"}
            profile_manifest = profile / "package.json"
            profile_manifest.write_text(json.dumps({"dependencies": dependencies}), encoding="utf-8")

            def link_bundles(arguments, **options):
                self.assertEqual(arguments[:7], ["local-dsh", "plugin", "--profile", "tui", "add", "--offline", "--ignore-scripts"])
                self.assertEqual(arguments[7:], [f"link:{sources[name].as_posix()}" for name in missing])
                self.assertEqual(options["cwd"], project)
                self.assertEqual(options["env"]["DSH_HOME"], str(home))
                self.assertNotIn("DEEPSEEK_API_KEY", options["env"])
                dependencies.update({name: f"link:{sources[name]}" for name in missing})
                for name in missing:
                    self._write_bundle(profile, name)
                profile_manifest.write_text(json.dumps({"dependencies": dependencies}), encoding="utf-8")
                return CompletedProcess(arguments, 0)

            sources = {}
            for package in missing:
                name = package.split("/")[1].replace("dsh-", "dsh-cosmatter-", 1)
                source = project / "plugins" / name
                self._write_bundle(base / "staging", package)
                source.parent.mkdir(parents=True, exist_ok=True)
                (base / "staging" / "node_modules" / package).rename(source)
                sources[package] = source
            with patch("cosmatter.dsh_profile_status.shutil.which", return_value="local-dsh"), patch(
                "cosmatter.dsh_profile_status.subprocess.run", side_effect=link_bundles,
            ) as launch, patch.dict("os.environ", {"DEEPSEEK_API_KEY": "unused-fixture"}):
                self.assertEqual(repair_dsh_bundles(project, dsh_home=home)["repaired_bundles"], missing)
                self.assertEqual(repair_dsh_bundles(project, dsh_home=home)["status"], "already_installed")
                launch.assert_called_once()
            retained = json.loads(profile_manifest.read_text(encoding="utf-8"))["dependencies"]
            self.assertEqual(retained[installed], "link:existing")
            self.assertEqual(retained["user-fixture"], "link:retained")

    def test_repair_requires_checkout_sources_before_running_dsh(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            with patch("cosmatter.dsh_profile_status.shutil.which", return_value="local-dsh"), patch(
                "cosmatter.dsh_profile_status.subprocess.run",
            ) as launch:
                with self.assertRaisesRegex(DshBundleRepairError, "repository root"):
                    repair_dsh_bundles(base, dsh_home=base / "dsh-home")
                launch.assert_not_called()

    def test_repair_enables_existing_bundles_without_reinstalling_or_replacing_other_entries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            profile = home / "profiles" / "tui"
            dependencies = {package: "link:existing" for package in EXPECTED_DSH_PACKAGES}
            for name in dependencies:
                self._write_bundle(profile, name)
            profile_manifest = profile / "package.json"
            prior = ["base-bundle", "operator-bundle", EXPECTED_DSH_PACKAGES[0]]
            profile_manifest.write_text(json.dumps({
                "dependencies": dependencies, "dsh": {"profile": {"bundles": prior, "unknown_setting": True}},
            }), encoding="utf-8")
            with patch("cosmatter.dsh_profile_status.subprocess.run") as launch:
                changed = repair_dsh_bundles(home, dsh_home=home)
                self.assertEqual(changed["status"], "activated")
                self.assertEqual(changed["repaired_bundles"], [])
                self.assertEqual(changed["enabled_bundles"], list(EXPECTED_DSH_PACKAGES[1:]))
                self.assertEqual(repair_dsh_bundles(home, dsh_home=home)["status"], "already_installed")
                launch.assert_not_called()
            manifest = json.loads(profile_manifest.read_text(encoding="utf-8"))
            self.assertEqual(manifest["dsh"]["profile"], {"bundles": prior + list(EXPECTED_DSH_PACKAGES[1:]), "unknown_setting": True})
            self.assertEqual(manifest["dependencies"], dependencies)

    def test_run_status_uses_installed_observability_bundle_and_requires_the_requested_id(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            profile = home / "profiles" / "tui"
            bundle = EXPECTED_DSH_PACKAGES[1]
            self._write_bundle(profile, bundle)
            payload = {"run_id": "run_001", "next_stage": "plan"}

            def diagnostic(executable, arguments, cwd, environment):
                overlay = json.loads(Path(arguments[arguments.index("--patch") + 1]).read_text(encoding="utf-8"))
                entries = overlay[-1]["insert"]
                self.assertEqual(len(entries), 2)
                self.assertEqual(entries[0]["name"], (profile / "node_modules" / bundle / "lib" / "index.js").resolve().as_uri())
                self.assertEqual(entries[0]["config"], {"baseUrl": "http://127.0.0.1:8769"})
                self.assertEqual(entries[1]["config"], {"runId": "run_001"})
                return "COSMATTER_DSH_RUN_STATUS " + json.dumps(payload)

            with patch("cosmatter.dsh_profile_status.shutil.which", return_value="local-dsh"), patch(
                "cosmatter.dsh_profile_status._run_dsh_diagnostic", side_effect=diagnostic,
            ) as launch:
                self.assertEqual(read_dsh_run_status("run_001", port=8769, dsh_home=home), payload)
                payload["run_id"] = "different_run"
                with self.assertRaisesRegex(DshCompositionCheckError, "requested run"):
                    read_dsh_run_status("run_001", port=8769, dsh_home=home)
                with self.assertRaisesRegex(DshCompositionCheckError, "Run ID"):
                    read_dsh_run_status("run_001; bad", port=8769, dsh_home=home)
                with self.assertRaisesRegex(DshCompositionCheckError, "Port"):
                    read_dsh_run_status("run_001", port=65536, dsh_home=home)
                self.assertEqual(launch.call_count, 2)

    def test_evidence_link_uses_the_graph_bundle_and_requires_the_exact_card_and_document(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            bundle = "@cosmatter/dsh-graph-plugin"
            profile = home / "profiles" / "tui"
            self._write_bundle(profile, bundle)
            link = "http://127.0.0.1:8789/?api=local#run=run_001&document=paper+%26+x%3D1&evidence=ev%27id"
            hit = {"evidence_id": "ev'id", "document_id": "paper & x=1"}
            result = {"run_id": "run_001", "match_mode": "exact_id", "results": [hit],
                      "trust_status": "accepted_evidence_search_not_new_evidence_or_scientific_conclusion"}

            def diagnostic(executable, arguments, cwd, environment):
                overlay = json.loads(Path(arguments[arguments.index("--patch") + 1]).read_text(encoding="utf-8"))
                entries = overlay[-1]["insert"]
                self.assertEqual(len(entries), 2)
                self.assertEqual(entries[0]["name"], (profile / "node_modules" / bundle / "lib/index.js").resolve().as_uri())
                self.assertEqual(entries[0]["config"], {"baseUrl": "http://127.0.0.1:8789"})
                self.assertEqual(entries[1]["config"], {
                    "tool": "cosmatter_accepted_evidence_search",
                    "args": {"run_id": "run_001", "evidence_id": "ev'id", "limit": 1},
                    "prefix": "COSMATTER_DSH_EVIDENCE ",
                })
                return "COSMATTER_DSH_EVIDENCE " + json.dumps(result)

            with patch("cosmatter.dsh_profile_status.shutil.which", return_value="local-dsh"), patch(
                "cosmatter.dsh_profile_status._run_dsh_diagnostic", side_effect=diagnostic,
            ) as launch:
                self.assertEqual(read_dsh_evidence_link(link, dsh_home=home)["checked_via"], ["cosmatter_accepted_evidence_search"])
                hit["document_id"] = "another document"
                with self.assertRaisesRegex(DshCompositionCheckError, "could not find the accepted card"):
                    read_dsh_evidence_link(link, dsh_home=home)
                for malformed in (link.replace("127.0.0.1", "example.org"), link + "&evidence=other", link.replace("ev%27id", "ev%0Aid")):
                    with self.assertRaises(DshCompositionCheckError):
                        read_dsh_evidence_link(malformed, dsh_home=home)
                self.assertEqual(launch.call_count, 2)

    def test_recent_runs_calls_only_the_installed_observability_tool_without_a_run_id(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            profile = home / "profiles" / "tui"
            bundle = "@cosmatter/dsh-observability-plugin"
            self._write_bundle(profile, bundle)

            payload = {"schema_version": "cosmatter.recent-run-links/v1", "runs": []}
            with patch("cosmatter.dsh_profile_status.shutil.which", return_value="local-dsh"), patch(
                "cosmatter.dsh_profile_status._run_isolated_dsh_probe", return_value=payload,
            ) as launch:
                self.assertEqual(read_dsh_recent_runs(port=8789, dsh_home=home), {**payload, "checked_via": ["cosmatter_recent_runs"]})
                self.assertEqual(launch.call_args.args[1:3], (profile, {bundle: {"baseUrl": "http://127.0.0.1:8789"}}))
                self.assertEqual(launch.call_args.args[-2], {
                    "tool": "cosmatter_recent_runs", "args": {}, "prefix": "COSMATTER_DSH_RECENT_RUNS ",
                })
                launch.return_value = {"error": "not_registered"}
                with self.assertRaisesRegex(DshCompositionCheckError, "Update the observability bundle"):
                    read_dsh_recent_runs(port=8789, dsh_home=home)
                with self.assertRaisesRegex(DshCompositionCheckError, "Port"):
                    read_dsh_recent_runs(port=0, dsh_home=home)
                self.assertEqual(launch.call_count, 2)

    def test_screening_link_requires_the_same_run_and_exact_revision(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            profile = home / "profiles" / "tui"
            bundle = "@cosmatter/dsh-review-plugin"
            self._write_bundle(profile, bundle)
            revision = "a" * 64
            link = f"http://127.0.0.1:8789/?api=local#run=run_001&screening={revision}"
            result = {"run_id": "run_001", "checklist_revision": revision, "decisions": []}
            with patch("cosmatter.dsh_profile_status.shutil.which", return_value="local-dsh"), patch(
                "cosmatter.dsh_profile_status._run_isolated_dsh_probe", return_value=result,
            ) as launch:
                self.assertEqual(read_dsh_screening_link(link, dsh_home=home)["checked_via"], ["cosmatter_candidate_screening_template"])
                self.assertEqual(launch.call_args.args[1:3], (profile, {bundle: {"baseUrl": "http://127.0.0.1:8789"}}))
                self.assertEqual(launch.call_args.args[-2]["args"], {"run_id": "run_001"})
                result["checklist_revision"] = "b" * 64
                with self.assertRaisesRegex(DshCompositionCheckError, "Screening checklist changed"):
                    read_dsh_screening_link(link, dsh_home=home)
                result.pop("checklist_revision")
                with self.assertRaisesRegex(DshCompositionCheckError, "versioned screening checklist"):
                    read_dsh_screening_link(link, dsh_home=home)
                for invalid in (link.replace("127.0.0.1", "example.org"), link + "&screening=" + revision, link.replace(revision, "bad"),
                                link + "&document=paper_1", link.replace("run_001", "..%2Fother")):
                    with self.assertRaises(DshCompositionCheckError):
                        read_dsh_screening_link(invalid, dsh_home=home)
                self.assertEqual(launch.call_count, 3)


    def test_run_artifacts_uses_the_installed_manifest_tool_and_rejects_the_wrong_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            profile = home / "profiles" / "tui"
            bundle = "@cosmatter/dsh-observability-plugin"
            self._write_bundle(profile, bundle)
            payload = {
                "schema_version": "cosmatter.artifact/v1", "run_id": "archived_1",
                "trust_status": "allowlisted_artifact_index_not_scientific_evidence", "artifact_count": 0, "artifacts": [],
            }
            with patch("cosmatter.dsh_profile_status.shutil.which", return_value="local-dsh"), patch(
                "cosmatter.dsh_profile_status._run_isolated_dsh_probe", return_value=payload,
            ) as launch:
                self.assertEqual(read_dsh_run_artifacts("archived_1", port=8789, dsh_home=home), {
                    **payload, "checked_via": ["cosmatter_artifact_manifest"], "workbench_url": "http://127.0.0.1:8789/?api=local#run=archived_1&artifacts=1",
                })
                self.assertEqual(launch.call_args.args[1:3], (profile, {bundle: {"baseUrl": "http://127.0.0.1:8789"}}))
                self.assertEqual(launch.call_args.args[-2], {
                    "tool": "cosmatter_artifact_manifest", "args": {"run_id": "archived_1"}, "prefix": "COSMATTER_DSH_RUN_ARTIFACTS ",
                })
                with self.assertRaisesRegex(DshCompositionCheckError, "could not read the artifact list"):
                    read_dsh_run_artifacts("archived_2", port=8789, dsh_home=home)
                with self.assertRaisesRegex(DshCompositionCheckError, "Run ID"):
                    read_dsh_run_artifacts("../private", port=8789, dsh_home=home)
                self.assertEqual(launch.call_count, 2)


    def test_only_fixed_run_reads_can_be_dispatched_by_name(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            profile = home / "profiles" / "tui"
            bundle = "@cosmatter/dsh-review-plugin"
            tool = "cosmatter_candidate_screening_template"
            self._write_bundle(profile, bundle)
            payload = {"run_id": "saved_1", "candidates": [], "decisions": []}
            with patch("cosmatter.dsh_profile_status.shutil.which", return_value="local-dsh"), patch(
                "cosmatter.dsh_profile_status._run_isolated_dsh_probe", return_value=payload,
            ) as launch:
                self.assertEqual(read_dsh_run_tool(tool, "saved_1", port=8789, dsh_home=home), {**payload, "checked_via": [tool]})
                self.assertEqual(launch.call_args.args[1:3], (profile, {bundle: {"baseUrl": "http://127.0.0.1:8789"}}))
                self.assertEqual(launch.call_args.args[-2], {"tool": tool, "args": {"run_id": "saved_1"}, "prefix": "COSMATTER_DSH_RUN_READ "})
                for rejected in ("cosmatter_mineru_task_poll", "cosmatter_candidate_screening_record", "other_tool"):
                    with self.assertRaisesRegex(DshCompositionCheckError, "allowed local DSH read"):
                        read_dsh_run_tool(rejected, "saved_1", dsh_home=home)
                with self.assertRaisesRegex(DshCompositionCheckError, "Run ID"):
                    read_dsh_run_tool(tool, "../other", dsh_home=home)
                with self.assertRaisesRegex(DshCompositionCheckError, "could not read this run"):
                    read_dsh_run_tool(tool, "other_run", port=8789, dsh_home=home)
                self.assertEqual(launch.call_count, 2)


if __name__ == "__main__":
    unittest.main()
