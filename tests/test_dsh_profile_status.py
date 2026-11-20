from __future__ import annotations

import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from subprocess import CompletedProcess
from threading import Barrier
from unittest.mock import MagicMock, patch

from cosmatter.dsh_profile_status import (
    EXPECTED_DSH_PACKAGES, DshBundleRepairError, DshCompositionCheckError, _BUNDLE_TOOLS,
    check_dsh_composition, dsh_profile_status, open_dsh_workbench, read_dsh_evidence_link, read_dsh_recent_runs, read_dsh_run_artifacts, read_dsh_run_status, read_dsh_run_tool, read_dsh_screening_link,
    read_dsh_catalogue, repair_dsh_bundles, resolve_dsh_executable, _run_dsh_diagnostic, _run_isolated_dsh_probe,
)


class DshProfileStatusTests(unittest.TestCase):
    def test_cli_repair_prefers_the_checkout_for_the_invoked_executable(self) -> None:
        from cosmatter.cli import main

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, project, term = root / "editable source", root / "wheel project", root / "another checkout"
            manifest = Path("plugins") / "dsh-plugin-group.json"
            for checkout in (source, project, term):
                (checkout / manifest).parent.mkdir(parents=True)
                (checkout / manifest).write_text("{}", encoding="utf-8")
            with (
                patch("cosmatter.cli.AGENT_ROOT", source),
                patch("cosmatter.cli.sys.prefix", str(project / ".venv")),
                patch("cosmatter.cli.sys.base_prefix", str(root / "python")),
                patch("cosmatter.cli.Path.cwd", return_value=term),
                patch("cosmatter.cli._json_print"),
                patch("cosmatter.cli.repair_dsh_bundles") as repair,
            ):
                self.assertEqual(main(["repair-dsh-bundles"]), 0)
                repair.assert_called_once_with(source, executable="dsh")
                (source / manifest).unlink()
                self.assertEqual(main(["repair-dsh-bundles"]), 0)
                self.assertEqual(repair.call_args.args, (project,))
                (project / manifest).unlink()
                self.assertEqual(main(["repair-dsh-bundles"]), 0)
                self.assertEqual(repair.call_args.args, (term,))

    def test_cli_explicit_tool_checks_require_the_whole_group_and_keep_the_receipt(self) -> None:
        from cosmatter.cli import main

        all_tools = sorted(tool for tools in _BUNDLE_TOOLS.values() for tool in tools)
        missing = "cosmatter_mission_create"
        partial = [tool for tool in all_tools if tool != missing]
        port_args = ["--loopback-port", "8789"]
        for options, registered, loopback, expected_exit in (
            ([], None, None, 0),
            (["--verify-tools"], all_tools, None, 0),
            (["--verify-tools"], partial, None, 2),
            (port_args, all_tools, "verified", 0),
            (port_args, partial, "verified", 2),
            (["--verify-tools", *port_args], partial, "verified", 2),
            (port_args, all_tools, "unavailable", 2),
        ):
            with self.subTest(options=options, loopback=loopback, expected_exit=expected_exit):
                # A composition-only report may describe a partially composed profile.
                bundles = list(EXPECTED_DSH_PACKAGES) if registered is not None else [EXPECTED_DSH_PACKAGES[0]]
                receipt = {"bundles": bundles, "matches_local_files": True}
                if registered is not None:
                    registry = {"bundles": bundles, "registered_tools": registered, "matches_local_files": True}
                    if loopback is not None:
                        registry["loopback_check"] = {"port": 8789, "status": loopback}
                    receipt["tool_registry_check"] = registry
                with (
                    patch("cosmatter.cli.check_dsh_composition", return_value=receipt) as check,
                    patch("sys.stdout", new_callable=io.StringIO) as stdout,
                    patch("sys.stderr", new_callable=io.StringIO) as stderr,
                ):
                    self.assertEqual(main(["check-dsh-profile", *options]), expected_exit)
                check.assert_called_once_with(
                    executable="dsh", verify_tools="--verify-tools" in options, loopback_port=8789 if loopback else None,
                )
                self.assertEqual(json.loads(stdout.getvalue()), receipt)
                if registered == partial:
                    self.assertIn(missing, stderr.getvalue())
                    self.assertIn(f"{len(partial)}/{len(all_tools)}", stderr.getvalue())
                else:
                    self.assertEqual(stderr.getvalue(), "")

    def test_isolated_probe_timeout_survives_process_and_directory_cleanup(self) -> None:
        for shutdown_timeout in (False, True):
            for locked_directory in (False, True):
                with (
                    self.subTest(shutdown_timeout=shutdown_timeout, locked_directory=locked_directory),
                    patch("cosmatter.dsh_profile_status.tempfile.TemporaryDirectory") as directory,
                    patch.object(Path, "write_text"),
                    patch("cosmatter.dsh_profile_status.subprocess.Popen") as popen,
                    patch("cosmatter.dsh_profile_status.subprocess.run") as taskkill,
                    patch("cosmatter.dsh_profile_status.os.killpg", create=True),
                ):
                    temporary = directory.return_value
                    temporary.__enter__.return_value = "private-temp-dir"
                    if locked_directory:
                        temporary.__exit__.side_effect = PermissionError("private-locked-file")
                    process = popen.return_value.__enter__.return_value
                    timeout = subprocess.TimeoutExpired(["private-dsh", "private-arguments"], 60, output=b"private-output")
                    stop_timeout = subprocess.TimeoutExpired(["private-stop-command"], 10)
                    process.communicate.side_effect = [timeout, stop_timeout if shutdown_timeout else (b"", None)]
                    if shutdown_timeout:
                        taskkill.side_effect = stop_timeout
                    with self.assertRaises(DshCompositionCheckError) as caught:
                        _run_isolated_dsh_probe("private-dsh", Path("."), {}, "", {}, "RESULT ")
                    expected = "The isolated DSH diagnostic timed out."
                    if shutdown_timeout or locked_directory:
                        expected += " Diagnostic cleanup did not finish."
                    self.assertEqual(str(caught.exception), expected)
                    self.assertTrue(caught.exception.__suppress_context__)
                    temporary.__exit__.assert_called_once()
                    self.assertIs(temporary.__exit__.call_args.args[1], timeout)
                    if os.name == "nt":
                        process.kill.assert_called_once_with()

    def test_isolated_probe_preserves_interrupt_and_other_failures(self) -> None:
        for error in (KeyboardInterrupt(), PermissionError("private-input")):
            with (
                self.subTest(error=type(error).__name__),
                patch("cosmatter.dsh_profile_status.tempfile.TemporaryDirectory") as directory,
                patch.object(Path, "write_text"),
                patch("cosmatter.dsh_profile_status.subprocess.Popen") as popen,
                patch("cosmatter.dsh_profile_status.subprocess.run") as taskkill,
                patch("cosmatter.dsh_profile_status.os.killpg", create=True),
            ):
                temporary = directory.return_value
                temporary.__enter__.return_value = "private-temp-dir"
                stop_timeout = subprocess.TimeoutExpired(["private-stop-command"], 10)
                popen.return_value.__enter__.return_value.communicate.side_effect = [error, stop_timeout]
                taskkill.side_effect = stop_timeout
                if isinstance(error, KeyboardInterrupt):
                    temporary.__exit__.side_effect = PermissionError("private-locked-file")
                    with self.assertRaises(KeyboardInterrupt) as caught:
                        _run_isolated_dsh_probe("private-dsh", Path("."), {}, "", {}, "RESULT ")
                    self.assertIs(caught.exception, error)
                else:
                    with self.assertRaisesRegex(DshCompositionCheckError, "could not complete") as caught:
                        _run_isolated_dsh_probe("private-dsh", Path("."), {}, "", {}, "RESULT ")
                    self.assertIs(caught.exception.__cause__, error)
                temporary.__exit__.assert_called_once()

    def test_timed_out_diagnostic_releases_files_held_by_its_descendants(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "child.py").write_text(
                "import time\nwith open('held.node', 'w') as lock:\n"
                "    lock.write('started')\n    lock.flush()\n    time.sleep(20)\n",
                encoding="utf-8",
            )
            (root / "parent.py").write_text(
                "import subprocess, sys\nsubprocess.run([sys.executable, '-S', 'child.py'], check=True)\n", encoding="utf-8",
            )
            executable, arguments = sys.executable, ["-S", "parent.py"]
            if os.name == "nt":
                launcher = root / "diagnostic.cmd"
                launcher.write_text(f'@echo off\n"{sys.executable}" -S parent.py\n', encoding="utf-8")
                executable, arguments = str(launcher), []
            started = time.monotonic()
            with self.assertRaises(subprocess.TimeoutExpired):
                _run_dsh_diagnostic(executable, arguments, directory, dict(os.environ), timeout=4)
            self.assertLess(time.monotonic() - started, 15)
            held = root / "held.node"
            self.assertEqual(held.read_text(), "started")
            held.unlink()

    def test_dsh_uses_the_explicit_launcher_or_path_before_windows_discovery(self) -> None:
        registry = MagicMock()
        with (
            patch.dict("sys.modules", winreg=registry),
            patch("sys.platform", "win32"),
            patch("cosmatter.dsh_profile_status.shutil.which") as which,
        ):
            for executable in ("dsh", "custom-dsh", "tools/dsh.cmd"):
                which.return_value = "resolved-launcher"
                self.assertEqual(resolve_dsh_executable(executable), "resolved-launcher")
                which.assert_called_with(executable)
            which.return_value = None
            for executable in ("custom-dsh", "tools/dsh.cmd"):
                with self.assertRaisesRegex(DshCompositionCheckError, "DSH executable not found"):
                    check_dsh_composition(executable=executable)
            with patch("sys.platform", "linux"):
                self.assertIsNone(resolve_dsh_executable())
            registry.OpenKey.assert_not_called()

    def test_windows_dsh_requires_the_registered_product_and_its_bundled_launcher(self) -> None:
        registry = MagicMock(KEY_READ=1, KEY_WOW64_64KEY=256, KEY_WOW64_32KEY=512)
        uninstall_key = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\1bf39983-50d0-5fe0-9ef4-cece76f67c5e"
        with (
            tempfile.TemporaryDirectory() as temporary,
            patch.dict("sys.modules", winreg=registry),
            patch("sys.platform", "win32"),
            patch("cosmatter.dsh_profile_status.shutil.which", return_value=None),
        ):
            install = Path(temporary) / "DeepSeek Harness"
            values = {"DisplayName": "DeepSeek Harness", "InstallLocation": str(install)}
            registry.QueryValueEx.side_effect = lambda key, name: (values[name], 1)
            self.assertIsNone(resolve_dsh_executable())

            launcher = install / "resources/runtime/cli/bin/dsh.cmd"
            launcher.parent.mkdir(parents=True)
            launcher.touch()
            values["DisplayName"] = "Another application"
            self.assertIsNone(resolve_dsh_executable())
            values["DisplayName"] = "DeepSeek Harness"
            # Only the machine-wide 32-bit registry view contains this install.
            registry.OpenKey.side_effect = [FileNotFoundError(), PermissionError(), FileNotFoundError(), MagicMock()]
            self.assertEqual(resolve_dsh_executable(), str(launcher))
            registry.OpenKey.assert_called_with(registry.HKEY_LOCAL_MACHINE, uninstall_key, 0, 1 | 512)

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
                self.assertEqual(open_dsh_workbench(8789, dsh_home=home, surface="tui"), 23)
            self.assertEqual(dump.call_args.args[1], ["--profile", "tui", "--dump-config"])
            self.assertIsNotNone(overlay)
            self.assertFalse(overlay.exists())
            self.assertEqual(manifest.read_bytes(), original)

            web = home / "profiles" / "web"
            observability = "@cosmatter/dsh-observability-plugin"
            self._write_bundle(web, observability)
            web_rows = f"- id: cosmatter-observability\n  name: '{observability}'\n  config:\n    timeoutMs: 1234\n    workbenchRunId: stale_run\n"

            def launch_web(arguments, *, env, check):
                self.assertEqual(arguments[:4], ["dsh", "--profile", "web", "--patch"])
                self.assertEqual(arguments[5:], ["--host", "127.0.0.1", "--port", "0", "--no-open"])
                override, additions = yaml.safe_load(Path(arguments[4]).read_text(encoding="utf-8"))
                self.assertEqual(override["config"], {"timeoutMs": 1234, "workbenchRunId": "chosen_run", "baseUrl": "http://127.0.0.1:8789"})
                self.assertEqual([row["name"] for row in additions["insert"]], [
                    (profile / "node_modules" / name / "lib/index.js").as_uri() for name in EXPECTED_DSH_PACKAGES if name != observability
                ])
                return CompletedProcess(arguments, 0)

            with (
                patch("cosmatter.dsh_profile_status.shutil.which", return_value="dsh"),
                patch("cosmatter.dsh_profile_status._run_dsh_diagnostic", side_effect=["".join(rows), web_rows]),
                patch("cosmatter.dsh_profile_status.subprocess.run", side_effect=launch_web),
            ):
                self.assertEqual(open_dsh_workbench(8789, dsh_home=home, open_browser=False, run_id="chosen_run"), 0)

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
                "cosmatter.dsh_profile_status._run_dsh_diagnostic", side_effect=["0.2.2-rc.3\n", config],
            ) as run:
                receipt = check_dsh_composition(dsh_home=home)
                self.assertEqual([call.args[:2] for call in run.call_args_list], [
                    ("local-dsh", ["--version"]), ("local-dsh", ["--profile", "tui", "--dump-config"]),
                ])
                self.assertTrue(all(call.args[3]["DSH_HOME"] == str(home.resolve()) for call in run.call_args_list))
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

    def test_rebuilt_entry_keeps_new_receipts_only_for_the_same_contents_and_mount(self) -> None:
        from cosmatter.dsh_profile_status import _write_profile_json

        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            profile = home / "profiles" / "tui"
            bundle = "@cosmatter/dsh-policy-plugin"
            self._write_bundle(profile, bundle)
            (profile / "package.json").write_text(json.dumps({"dependencies": {bundle: "link:fixture"}}))
            root = profile / "node_modules" / bundle
            entry = root / "lib" / "index.js"
            original = entry.read_bytes()
            config = f"- id: cosmatter-policy\n  name: '{bundle}'\n"
            probe = {"registered_tools": ["cosmatter_plugin_catalogue"], "loopback_status": "verified"}
            with patch("cosmatter.dsh_profile_status.resolve_dsh_executable", return_value="test-dsh"), patch(
                "cosmatter.dsh_profile_status._run_dsh_diagnostic", side_effect=["0.2.2-rc.3", config],
            ), patch("cosmatter.dsh_profile_status._run_isolated_dsh_probe", return_value=probe):
                check_dsh_composition(dsh_home=home, loopback_port=8765)

            def freshness():
                status = dsh_profile_status(dsh_home=home, loopback_port=8765)
                return tuple(status[key]["matches_local_files"] for key in ("composition_check", "tool_registry_check"))

            # Reproduce the old per-port-v1 backend's private schema and digest without the new reader.
            composition = json.loads((profile / ".cosmatter-composition-check.json").read_bytes())
            registry = json.loads((profile / ".cosmatter-tool-registry-check.json").read_bytes())
            self.assertEqual(set(composition), {"schema_version", "checked_at", "dsh_version", "bundles", "configuration_stamp"})
            self.assertEqual(set(registry), {*composition, "registered_tools", "runtime_stamp", "loopback_check"})
            self.assertEqual(registry["loopback_check"], {"port": 8765, "status": "verified"})
            files = [profile / name for name in ("package.json", "cordis.patch.yml", "pnpm-lock.yaml", "pnpm-workspace.yaml")]
            files.append(home / "cordis.patch.yml")
            files.extend(profile / "node_modules" / name / file for name in EXPECTED_DSH_PACKAGES
                         for file in ("package.json", "lib/index.js", "cordis.patch.yml"))
            metadata = []
            for file in files:
                info = file.stat() if file.exists() else None
                metadata.append((info.st_size, info.st_mtime_ns, info.st_ino) if info else None)
            old_stamp = hashlib.sha256(json.dumps([None, metadata]).encode("ascii")).hexdigest()
            self.assertEqual((composition["configuration_stamp"], registry["configuration_stamp"]), (old_stamp, old_stamp))
            old_runtime = hashlib.sha256(f"{bundle}/lib/index.js\n".encode() + hashlib.sha256(original).digest()).hexdigest()
            self.assertEqual(registry["runtime_stamp"], old_runtime)
            receipts = {file: (file.read_bytes(), file.stat().st_mtime_ns) for file in profile.glob(".cosmatter-*.json")}
            with patch("cosmatter.dsh_profile_status._MAX_CONFIG_BYTES", len(original) - 1):
                self.assertEqual(freshness(), (False, False))
            info = entry.stat()
            os.utime(entry, ns=(info.st_atime_ns, info.st_mtime_ns + 2_000_000_000))
            self.assertEqual(freshness(), (True, True))
            replacement = entry.with_suffix(".new")
            replacement.write_bytes(original)
            replacement.replace(entry)
            self.assertEqual(freshness(), (True, True))
            self.assertEqual(receipts, {file: (file.read_bytes(), file.stat().st_mtime_ns) for file in receipts})

            for primary_name in (".cosmatter-composition-check.json", ".cosmatter-tool-registry-check.json"):
                primary = profile / primary_name
                committed = primary.read_bytes()

                def interrupt(directory, filename, payload):
                    if filename == primary_name:
                        raise OSError("simulated interruption before commit")
                    _write_profile_json(directory, filename, payload)

                with patch("cosmatter.dsh_profile_status.resolve_dsh_executable", return_value="test-dsh"), patch(
                    "cosmatter.dsh_profile_status._run_dsh_diagnostic", side_effect=["0.2.2-rc.3", config],
                ), patch("cosmatter.dsh_profile_status._run_isolated_dsh_probe", return_value=probe), patch(
                    "cosmatter.dsh_profile_status._write_profile_json", side_effect=interrupt,
                ):
                    with self.assertRaises(DshCompositionCheckError):
                        check_dsh_composition(dsh_home=home, loopback_port=8765)
                self.assertEqual(primary.read_bytes(), committed)
                self.assertEqual(freshness(), (True, True))

            info = entry.stat()
            entry.write_bytes(b"x" * len(original))
            os.utime(entry, ns=(info.st_atime_ns, info.st_mtime_ns))
            self.assertEqual(freshness(), (False, False))
            entry.write_bytes(original)
            self.assertEqual(freshness(), (True, True))

            # Preserve every file identity while replacing the linked package's directory.
            old_root = home / "old-bundle"
            root.rename(old_root)
            (root / "lib").mkdir(parents=True)
            for filename in ("package.json", "lib/index.js", "cordis.patch.yml"):
                os.link(old_root / filename, root / filename)
            self.assertEqual(freshness(), (False, False))

    def test_touch_during_composition_or_registry_probe_invalidates_the_attempt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            profile = home / "profiles" / "tui"
            bundle = EXPECTED_DSH_PACKAGES[0]
            self._write_bundle(profile, bundle)
            (profile / "package.json").write_text(json.dumps({"dependencies": {bundle: "link:fixture"}}))
            entry = profile / "node_modules" / bundle / "lib" / "index.js"

            def touch_entry(*_args):
                info = entry.stat()
                os.utime(entry, ns=(info.st_atime_ns, info.st_mtime_ns + 2_000_000_000))
                return ["cosmatter_mission_create"]

            config = f"- id: cosmatter-mission\n  name: '{bundle}'\n"

            def dump_while_rebuilding(_executable, arguments, _cwd, _environment):
                if arguments == ["--version"]:
                    return "0.2.2-rc.3"
                touch_entry()
                return config

            with patch("cosmatter.dsh_profile_status.resolve_dsh_executable", return_value="test-dsh"), patch(
                "cosmatter.dsh_profile_status._run_dsh_diagnostic", side_effect=dump_while_rebuilding,
            ):
                with self.assertRaisesRegex(DshCompositionCheckError, "profile changed during the check"):
                    check_dsh_composition(dsh_home=home)
            self.assertNotIn("composition_check", dsh_profile_status(dsh_home=home))

            with patch("cosmatter.dsh_profile_status.resolve_dsh_executable", return_value="test-dsh"), patch(
                "cosmatter.dsh_profile_status._run_dsh_diagnostic", side_effect=["0.2.2-rc.3", config],
            ), patch("cosmatter.dsh_profile_status._run_isolated_dsh_probe", side_effect=touch_entry):
                with self.assertRaisesRegex(DshCompositionCheckError, "changed during the registration check"):
                    check_dsh_composition(dsh_home=home, verify_tools=True)
            self.assertNotIn("tool_registry_check", dsh_profile_status(dsh_home=home))

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

    def test_loopback_history_preserves_other_workbenches_and_expires_on_change(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            profile = home / "profiles" / "tui"
            bundle = "@cosmatter/dsh-policy-plugin"
            self._write_bundle(profile, bundle)
            (profile / "package.json").write_text(json.dumps({"dependencies": {bundle: "0.2.0"}}), encoding="utf-8")
            tools = ["cosmatter_plugin_catalogue"]
            result = {"registered_tools": tools, "loopback_status": "verified"}
            composed = f"- id: cosmatter-policy\n  name: '{bundle}'\n"

            def check(port):
                return check_dsh_composition(dsh_home=home, verify_tools=True, loopback_port=port)["tool_registry_check"]

            def read(port=None):
                return dsh_profile_status(dsh_home=home, loopback_port=port)["tool_registry_check"]

            with (
                patch("cosmatter.dsh_profile_status.resolve_dsh_executable", return_value="local-dsh"),
                patch("cosmatter.dsh_profile_status._run_dsh_diagnostic", side_effect=lambda _, args, *_rest: "0.2.2" if args == ["--version"] else composed),
                patch("cosmatter.dsh_profile_status._run_isolated_dsh_probe", return_value=result) as probe,
                patch("cosmatter.dsh_profile_status._MAX_LOOPBACK_RECEIPTS", 3),
            ):
                first = check(8765)
                legacy = json.loads((profile / ".cosmatter-tool-registry-check.json").read_text())
                self.assertNotIn("port_history", legacy)
                self.assertEqual(read(8765), first)
                self.assertNotIn("loopback_check", read(8766))
                second = check(8766)
                result["loopback_status"] = "unavailable"
                failed = check(8765)
                self.assertEqual(read(8765), failed)
                self.assertEqual(read(8766), second)
                self.assertEqual(read(), failed)
                self.assertEqual(failed["loopback_check"]["status"], "unavailable")
                probe.return_value = tools
                generic = check(None)
                self.assertNotIn("loopback_check", generic)
                self.assertEqual(read(), generic)
                self.assertEqual(read(8765), failed)
                probe.return_value = result
                check(8767)
                check(8768)
                self.assertNotIn("loopback_check", read(8766))
                self.assertEqual(read(8765), failed)
                for changed in (profile / "cordis.patch.yml", profile / "node_modules" / bundle / "lib" / "client.js"):
                    changed.write_text("updated", encoding="utf-8")
                    self.assertFalse(read(8765)["matches_local_files"])
                    current = check(8766)
                    self.assertTrue(current["matches_local_files"])
                    self.assertNotIn("loopback_check", read(8765))
                    check(8765)

                barrier = Barrier(3)

                def concurrent_probe(*_args):
                    barrier.wait(timeout=5)
                    return result

                probe.side_effect = concurrent_probe
                with ThreadPoolExecutor(max_workers=3) as executor:
                    ports = (8780, 8781, 8782)
                    written = list(executor.map(check, ports))
                self.assertEqual([read(port) for port in ports], written)

    def test_single_receipt_remains_authoritative_during_a_rolling_upgrade(self) -> None:
        from cosmatter.dsh_profile_status import _bundle_runtime_stamp, _configuration_stamp, _save_registry_check

        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            profile = home / "profiles" / "tui"
            bundle = "@cosmatter/dsh-policy-plugin"
            self._write_bundle(profile, bundle)
            (profile / "package.json").write_text(json.dumps({"dependencies": {bundle: "0.2.0"}}), encoding="utf-8")
            primary = profile / ".cosmatter-tool-registry-check.json"
            legacy = {
                "schema_version": "cosmatter.dsh-tool-registry-check/v1", "checked_at": "2026-11-19T01:00:00Z",
                "dsh_version": "0.2.2", "bundles": [bundle], "registered_tools": ["cosmatter_plugin_catalogue"],
                "configuration_stamp": _configuration_stamp(profile), "runtime_stamp": _bundle_runtime_stamp(profile, [bundle]),
                "loopback_check": {"port": 8765, "status": "verified"},
            }
            primary.write_text(json.dumps(legacy), encoding="utf-8")

            def snapshot(port):
                return dsh_profile_status(dsh_home=home, loopback_port=port).get("tool_registry_check")

            latest = {**legacy, "loopback_check": {"port": 8766, "status": "verified"}}
            _save_registry_check(profile, latest)
            # The old reader bounds the primary at 4096 bytes and accepts only these fields.
            self.assertLessEqual(primary.stat().st_size, 4096)
            self.assertEqual(json.loads(primary.read_text(encoding="utf-8")), latest)
            self.assertEqual(snapshot(8765)["loopback_check"], legacy["loopback_check"])
            self.assertTrue(snapshot(8766)["matches_local_files"])

            failed = {**legacy, "loopback_check": {"port": 8765, "status": "unavailable"}}
            primary.write_text(json.dumps(failed), encoding="utf-8")
            self.assertEqual(snapshot(8765)["loopback_check"], failed["loopback_check"])
            self.assertEqual(snapshot(8766)["loopback_check"], latest["loopback_check"])
            _save_registry_check(profile, latest)
            self.assertEqual(snapshot(8765)["loopback_check"], failed["loopback_check"])
            primary.write_text(json.dumps({**latest, "dsh_version": "0.3.0"}), encoding="utf-8")
            self.assertNotIn("loopback_check", snapshot(8765))
            primary.write_text(json.dumps({**latest, "unexpected": True}), encoding="utf-8")
            self.assertIsNone(snapshot(8766))
            primary.unlink()
            self.assertIsNone(snapshot(8765))

            # An upgraded writer preserves an old port's proof only while its original stamp still matches.
            primary.write_text(json.dumps(legacy), encoding="utf-8")
            old_composition = {key: legacy[key] for key in ("checked_at", "dsh_version", "bundles", "configuration_stamp")}
            old_composition["schema_version"] = "cosmatter.dsh-composition-check/v1"
            composition_file = profile / ".cosmatter-composition-check.json"
            composition_file.write_text(json.dumps(old_composition))
            self.assertTrue(dsh_profile_status(dsh_home=home)["composition_check"]["matches_local_files"])
            self.assertEqual(json.loads(composition_file.read_bytes()), old_composition)
            config = f"- id: cosmatter-policy\n  name: '{bundle}'\n"
            with patch("cosmatter.dsh_profile_status.resolve_dsh_executable", return_value="test-dsh"), patch(
                "cosmatter.dsh_profile_status._run_dsh_diagnostic", side_effect=["0.2.2", config],
            ), patch("cosmatter.dsh_profile_status._run_isolated_dsh_probe", return_value={
                "registered_tools": ["cosmatter_plugin_catalogue"], "loopback_status": "verified",
            }):
                check_dsh_composition(dsh_home=home, loopback_port=8766)
            self.assertEqual(snapshot(8765)["loopback_check"], legacy["loopback_check"])
            self.assertEqual(json.loads(primary.read_bytes())["configuration_stamp"], legacy["configuration_stamp"])
            entry = profile / "node_modules" / bundle / "lib" / "index.js"
            info = entry.stat()
            os.utime(entry, ns=(info.st_atime_ns, info.st_mtime_ns + 2_000_000_000))
            self.assertNotIn("loopback_check", snapshot(8765))
            self.assertTrue(snapshot(8766)["matches_local_files"])
            composition_file.write_text(json.dumps(old_composition))
            self.assertFalse(dsh_profile_status(dsh_home=home)["composition_check"]["matches_local_files"])

    def test_registered_tool_changes_expire_other_ports_in_existing_and_new_history(self) -> None:
        from cosmatter.dsh_profile_status import _bundle_runtime_stamp, _configuration_stamp, _save_registry_check

        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            profile = home / "profiles" / "tui"
            bundles = list(EXPECTED_DSH_PACKAGES)
            for package in bundles:
                self._write_bundle(profile, package)
            (profile / "package.json").write_text(json.dumps({"dependencies": dict.fromkeys(bundles, "0.2.0")}), encoding="utf-8")
            tools = sorted(tool for group in _BUNDLE_TOOLS.values() for tool in group)
            partial = {
                "schema_version": "cosmatter.dsh-tool-registry-check/v1", "checked_at": "2026-11-19T01:00:00Z",
                "dsh_version": "0.2.2", "bundles": bundles, "registered_tools": [t for t in tools if t != "cosmatter_mission_create"],
                "configuration_stamp": _configuration_stamp(profile), "runtime_stamp": _bundle_runtime_stamp(profile, bundles),
                "loopback_check": {"port": 8765, "status": "verified"},
            }
            full = {**partial, "registered_tools": tools, "loopback_check": {"port": 8766, "status": "verified"}}
            _save_registry_check(profile, partial)
            _save_registry_check(profile, full)
            sidecar = profile / ".cosmatter-tool-registry-ports.json"
            history = json.loads(sidecar.read_text(encoding="utf-8"))
            self.assertEqual(history["receipts"], [full])

            # An older writer could persist ports from both tool inventories.
            history["receipts"].append(partial)
            sidecar.write_text(json.dumps(history), encoding="utf-8")
            old_port = dsh_profile_status(dsh_home=home, loopback_port=8765)["tool_registry_check"]
            self.assertEqual(old_port["registered_tools"], tools)
            self.assertNotIn("loopback_check", old_port)
            new_port = dsh_profile_status(dsh_home=home, loopback_port=8766)["tool_registry_check"]
            self.assertEqual(new_port["loopback_check"], full["loopback_check"])
            _save_registry_check(profile, {**full, "loopback_check": partial["loopback_check"]})
            self.assertEqual(
                [receipt["registered_tools"] for receipt in json.loads(sidecar.read_text(encoding="utf-8"))["receipts"]],
                [tools, tools],
            )

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

    def test_repair_uses_only_fresh_registration_gaps_in_checked_composed_bundles(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            home = base / "dsh-home"
            profile = home / "profiles" / "tui"
            for package in EXPECTED_DSH_PACKAGES:
                self._write_bundle(profile, package)
            (profile / "package.json").write_text(json.dumps({
                "dependencies": dict.fromkeys(EXPECTED_DSH_PACKAGES, "0.2.0"),
            }), encoding="utf-8")
            mission, observability = EXPECTED_DSH_PACKAGES[:2]
            config = f"- id: cosmatter-observability\n  name: '{observability}'\n"
            mission_entry = f"- id: cosmatter-mission\n  name: '{mission}'\n"
            version = "0.2.2"
            with (
                patch("cosmatter.dsh_profile_status.resolve_dsh_executable", return_value="local-dsh"),
                patch("cosmatter.dsh_profile_status._run_dsh_diagnostic", side_effect=lambda _, args, *_rest: version if args == ["--version"] else config),
                patch("cosmatter.dsh_profile_status._run_isolated_dsh_probe", return_value=sorted(_BUNDLE_TOOLS[observability])),
                patch("cosmatter.dsh_profile_status.subprocess.run") as link,
            ):
                def no_relink():
                    self.assertEqual(repair_dsh_bundles(base, dsh_home=home)["status"], "already_installed")
                    link.assert_not_called()

                no_relink()
                check_dsh_composition(dsh_home=home, verify_tools=True)
                config += mission_entry
                check_dsh_composition(dsh_home=home)  # Mission is composed but has never been checked.
                no_relink()
                check_dsh_composition(dsh_home=home, verify_tools=True)
                config = config.removesuffix(mission_entry)
                check_dsh_composition(dsh_home=home)  # The latest composition no longer includes mission.
                no_relink()
                config += mission_entry
                version = "0.3.0"
                check_dsh_composition(dsh_home=home)
                no_relink()
                version = "0.2.2"
                check_dsh_composition(dsh_home=home)
                registry_input = profile / "node_modules" / mission / "lib" / "client.js"
                registry_input.write_text("export const changed = true", encoding="utf-8")
                no_relink()
                registry_input.unlink()

                installed = profile / "node_modules" / mission
                source = base / "plugins" / "dsh-cosmatter-mission-plugin"
                self._write_bundle(base / "staging", mission)
                source.parent.mkdir()
                (base / "staging" / "node_modules" / mission).rename(source)
                link.return_value = CompletedProcess([], 0)
                with self.assertRaisesRegex(DshBundleRepairError, "did not link"):
                    repair_dsh_bundles(base, dsh_home=home)
                self.assertEqual(link.call_args.args[0][7:], [f"link:{source.as_posix()}"])

                def relink(arguments, **_options):
                    installed.rename(base / "previous-mission")
                    if os.name == "nt":
                        import _winapi
                        _winapi.CreateJunction(str(source), str(installed))
                    else:
                        installed.symlink_to(source, target_is_directory=True)
                    return CompletedProcess(arguments, 0)

                link.side_effect = relink
                repaired = repair_dsh_bundles(base, dsh_home=home)
                self.assertEqual(repaired["repaired_bundles"], [mission])
                self.assertEqual(repaired["status"], "installed")
                self.assertIs(repaired["tool_verification_required"], True)
                self.assertFalse(dsh_profile_status(dsh_home=home)["tool_registry_check"]["matches_local_files"])

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
                hit["reader_available"] = False
                with self.assertRaisesRegex(DshCompositionCheckError, "could not find the accepted card"):
                    read_dsh_evidence_link(link, dsh_home=home)
                del hit["reader_available"]
                hit["document_id"] = "another document"
                with self.assertRaisesRegex(DshCompositionCheckError, "could not find the accepted card"):
                    read_dsh_evidence_link(link, dsh_home=home)
                for malformed in (link.replace("127.0.0.1", "example.org"), link + "&evidence=other", link.replace("ev%27id", "ev%0Aid")):
                    with self.assertRaises(DshCompositionCheckError):
                        read_dsh_evidence_link(malformed, dsh_home=home)
                self.assertEqual(launch.call_count, 3)

    def test_catalogue_reads_through_policy_without_a_run_and_rejects_non_catalogue_results(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            profile = home / "profiles" / "tui"
            bundle = "@cosmatter/dsh-policy-plugin"
            self._write_bundle(profile, bundle)
            payload = {"catalogue_api_version": "2.0", "trust_status": "static_catalogue_not_plugin_execution_or_evidence_acceptance",
                       "plugins": [{"plugin_id": "mission.define", "title": "任务边界定义"}]}
            with (patch("cosmatter.dsh_profile_status.shutil.which", return_value="dsh"),
                  patch("cosmatter.dsh_profile_status._run_isolated_dsh_probe", return_value=payload) as probe):
                self.assertEqual(read_dsh_catalogue(port=8789, dsh_home=home), {**payload, "checked_via": ["cosmatter_plugin_catalogue"]})
                self.assertEqual(probe.call_args.args[1:3], (profile, {bundle: {"baseUrl": "http://127.0.0.1:8789"}}))
                self.assertEqual(probe.call_args.args[-2], {"tool": "cosmatter_plugin_catalogue", "args": {}, "prefix": "COSMATTER_DSH_CATALOGUE "})
                for update in ({"plugins": []}, {"plugins": [42]}, {"trust_status": "executed"}):
                    probe.return_value = {**payload, **update}
                    with self.assertRaisesRegex(DshCompositionCheckError, "capability catalogue"):
                        read_dsh_catalogue(port=8789, dsh_home=home)
                probe.return_value = {"error": "not_registered"}
                with self.assertRaisesRegex(DshCompositionCheckError, "policy bundle"):
                    read_dsh_catalogue(port=8789, dsh_home=home)

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
