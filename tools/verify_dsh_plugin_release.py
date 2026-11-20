"""Verify the versioned CosMatter DSH bundle release gate.

Default mode is deliberately local and keyless: it validates the compatibility
matrix, every package manifest and published-file allowlist.  ``--profile-smoke``
installs the packed tarballs in a temporary DSH home, checks profile
composition and startup, and dispatches catalogue, mission creation, and
workflow status and the selected run's stage contract through an isolated CosMatter loopback API. It never loads
``.env`` or starts a provider-backed agent turn.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from threading import Thread
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


class ReleaseGateError(RuntimeError):
    pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile-smoke", action="store_true", help="install packed bundles into a fresh temporary DSH profile")
    parser.add_argument("--timeout-seconds", type=int, default=90, help="per external release-gate command timeout (default: 90)")
    args = parser.parse_args(argv)
    if not 5 <= args.timeout_seconds <= 300:
        raise ReleaseGateError("release-gate timeout must be between 5 and 300 seconds")
    compatibility = _load_json(ROOT / "configs" / "dsh_compatibility.json")
    manifest = _load_json(ROOT / "plugins" / "dsh-plugin-group.json")
    _validate(compatibility, manifest)
    report = {"status": "ok", "bundle_count": len(manifest["packages"]), "profile_smoke": args.profile_smoke}
    if args.profile_smoke:
        report["registered_tool_count"] = _profile_smoke(compatibility, manifest, timeout_seconds=args.timeout_seconds)
        report["loopback_catalogue_verified"] = True
        report["loopback_mission_roundtrip_verified"] = True
        report["mission_result_card_verified"] = True
        report["bound_stage_contract_verified"] = True
        report["document_receipt_card_verified"] = True
        report["browser_run_handoff_verified"] = True
    print(json.dumps(report, ensure_ascii=False))
    return 0


def _validate(compatibility: dict[str, Any], manifest: dict[str, Any]) -> None:
    if set(compatibility) != {"schema_version", "dsh", "node", "npm", "pnpm", "bundles", "required_package_files", "invariants"} or compatibility.get("schema_version") != "1.0":
        raise ReleaseGateError("dsh compatibility matrix fields are invalid")
    if not all(isinstance(compatibility.get(key), str) and compatibility[key].strip() for key in ("dsh", "node", "npm", "pnpm")):
        raise ReleaseGateError("dsh compatibility version pin is invalid")
    if not isinstance(manifest.get("packages"), list) or not isinstance(manifest.get("invariants"), list):
        raise ReleaseGateError("DSH group manifest is invalid")
    package_names = [entry.get("package") for entry in manifest["packages"]]
    if package_names != compatibility["bundles"] or manifest["invariants"] != compatibility["invariants"]:
        raise ReleaseGateError("DSH compatibility matrix does not match the group manifest")
    required_files = compatibility["required_package_files"]
    if required_files != ["lib", "cordis.patch.yml", "README.md"]:
        raise ReleaseGateError("published file allowlist is invalid")
    for entry in manifest["packages"]:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str) or not isinstance(entry.get("plugin_id"), str):
            raise ReleaseGateError("DSH bundle entry is invalid")
        package_dir = ROOT / "plugins" / entry["path"]
        package = _load_json(package_dir / "package.json")
        if package.get("name") != entry["package"] or package.get("files") != required_files:
            raise ReleaseGateError(f"package manifest is inconsistent for {entry['package']}")
        for dependencies in ("peerDependencies", "devDependencies"):
            if package.get(dependencies, {}).get("@deepseek-ai/dsh-tools") != compatibility["dsh"]:
                raise ReleaseGateError(f"DSH tools version does not match the runtime pin for {entry['package']}")
        for name in required_files:
            if not (package_dir / name).exists():
                raise ReleaseGateError(f"required published file is missing for {entry['package']}: {name}")
        if not (package_dir / "lib" / "index.js").is_file():
            raise ReleaseGateError(f"compiled entry is missing for {entry['package']}")
        patch = (package_dir / "cordis.patch.yml").read_text(encoding="utf-8")
        if f"id: {entry['plugin_id']}" not in patch or f"name: '{entry['package']}'" not in patch or "baseUrl: http://127.0.0.1:" not in patch or "https://" in patch or "http://localhost" in patch:
            raise ReleaseGateError(f"loopback patch contract is invalid for {entry['package']}")


def _profile_smoke(compatibility: dict[str, Any], manifest: dict[str, Any], *, timeout_seconds: int) -> int:
    sys.path.insert(0, str(ROOT / "src"))
    from cosmatter.dsh_profile_status import resolve_dsh_executable

    dsh = resolve_dsh_executable()
    if not dsh:
        raise ReleaseGateError("DSH executable not found for profile smoke")
    npm = shutil.which("npm")
    node = shutil.which("node")
    pnpm = shutil.which("pnpm")
    if not npm or not node or not pnpm:
        raise ReleaseGateError("node, npm, and pnpm must be available on PATH for profile smoke")
    actual = _command_text([dsh, "--version"])
    if actual != compatibility["dsh"]:
        raise ReleaseGateError(f"DSH version mismatch: expected {compatibility['dsh']}, got {actual}")
    actual_node = _command_text([node, "--version"]).lstrip("v")
    if actual_node != compatibility["node"]:
        raise ReleaseGateError(f"Node version mismatch: expected {compatibility['node']}, got {actual_node}")
    actual_npm = _command_text([npm, "--version"])
    if actual_npm != compatibility["npm"]:
        raise ReleaseGateError(f"npm version mismatch: expected {compatibility['npm']}, got {actual_npm}")
    actual_pnpm = _command_text([pnpm, "--version"])
    if actual_pnpm != compatibility["pnpm"]:
        raise ReleaseGateError(f"pnpm version mismatch: expected {compatibility['pnpm']}, got {actual_pnpm}")
    with tempfile.TemporaryDirectory(prefix="cosmatter-dsh-release-") as directory:
        temporary = Path(directory)
        tarballs: list[str] = []
        for entry in manifest["packages"]:
            package_dir = ROOT / "plugins" / str(entry["path"])
            completed = _run(
                # Bundles publish their checked-in `lib` output.  A release
                # smoke must exercise that exact artifact; running `prepare`
                # would instead require each plugin's devDependencies in CI.
                [npm, "pack", "--ignore-scripts", "--pack-destination", str(temporary), "--json"], cwd=package_dir,
                timeout=timeout_seconds,
            )
            if completed.returncode:
                raise ReleaseGateError(f"npm pack failed for {entry['package']}: {completed.stderr.strip()}")
            packed = json.loads(completed.stdout)
            if not isinstance(packed, list) or len(packed) != 1 or not isinstance(packed[0], dict) or not isinstance(packed[0].get("filename"), str):
                raise ReleaseGateError(f"npm pack output is invalid for {entry['package']}")
            tarballs.append(str(temporary / packed[0]["filename"]))
        # pnpm's non-TTY prompts can otherwise leave `dsh plugin add` waiting
        # forever in CI even though this is a fully local tarball install.
        environment = {**os.environ, "DSH_HOME": str(temporary / "dsh-home"), "PYTHONPATH": "", "CI": "1"}
        profile = "cosmatter-release-smoke"
        initialize = _run(
            [dsh, "--profile", profile, "--from-default-profile", "headless", "--dump-config"],
            cwd=temporary, env=environment, timeout=timeout_seconds,
        )
        if initialize.returncode:
            raise ReleaseGateError(f"clean headless profile initialization failed: {initialize.stderr.strip()}")
        install = _run([dsh, "plugin", "--profile", profile, "add", *tarballs], cwd=ROOT, env=environment, timeout=timeout_seconds)
        if install.returncode:
            raise ReleaseGateError(f"clean-profile bundle install failed: {install.stderr.strip() or install.stdout.strip()}")
        dump = _run([dsh, "--profile", profile, "--dump-config"], cwd=ROOT, env=environment, timeout=timeout_seconds)
        if dump.returncode:
            raise ReleaseGateError(f"clean-profile config dump failed: {dump.stderr.strip() or dump.stdout.strip()}")
        for entry in manifest["packages"]:
            if f"id: {entry['plugin_id']}" not in dump.stdout:
                raise ReleaseGateError(f"clean profile did not compose {entry['plugin_id']}")
        startup = _run([dsh, "--profile", profile, "--help"], cwd=temporary, env=environment, timeout=timeout_seconds)
        if startup.returncode or "Usage: dsh --profile headless" not in startup.stdout:
            raise ReleaseGateError(f"clean profile failed to reach the headless app: {startup.stderr.strip()}")
        return _verify_tool_registry(dsh, profile, manifest, temporary, environment, timeout_seconds, dump.stdout)


def _seed_saved_document(runs_dir: Path) -> dict[str, Any]:
    """Prepare a completed synthetic receipt that the native submit call can replay offline."""
    from unittest.mock import patch

    from cosmatter.config import Settings
    from cosmatter.local_api import LocalMissionApi
    from cosmatter.mineru import MinerUTask
    from cosmatter.sciverse import SciverseResponse

    api = LocalMissionApi(runs_dir, settings_loader=lambda: Settings.load({"SCIVERSE_API_TOKEN": "synthetic-fixture"}))
    run_id = "cosmatter_document_release_probe"
    api.create_mission({
        "run_id": run_id, "question": "How do synthetic diffraction patterns vary across oxide films?",
        "material": "oxide films", "property": "diffraction", "scope": "Synthetic receipt for the DSH document card",
    })
    api.approve_plan(run_id, {"subquestions": ["Which film was measured?"], "queries": ["oxide film diffraction"],
                              "counter_queries": ["oxide film diffraction counterexamples"]})
    document_id, source = "synthetic film & XRD", "https://example.invalid/synthetic.pdf"
    with patch("cosmatter.local_api.SciverseAdapter", autospec=True) as sciverse:
        sciverse.return_value.agentic_search.return_value = SciverseResponse(
            {"hits": [{"doc_id": document_id, "title": "Synthetic diffraction measurement", "is_content_accessible": True}]}, 200, None,
        )
        api.execute_plan_query(run_id, {"query_index": 0, "sources": ["sciverse"]})
        api.execute_plan_query(run_id, {"query_index": 0, "counter": True, "sources": ["sciverse"]})
    api.record_candidate_screening(run_id, {"decisions": [
        {"document_id": document_id, "decision": "include_for_fulltext", "reason_codes": ["material_match", "property_match"]},
    ]})
    args = {"document_id": document_id, "source_url": source,
            "authorizations": ["mission_scoped_egress_consent", "mineru_file_consent", "private_content_to_mineru"]}
    with patch("cosmatter.local_api.MinerUAdapter", autospec=True) as mineru:
        mineru.return_value.submit_remote_source.return_value = MinerUTask(task_id="synthetic-parse", state="done", request_id=None)
        api.submit_authorized_mineru_source(run_id, {**args, "dsh_call_id": "release-probe-cosmatter_mineru_source_submit"})
    return {"run_id": run_id, **args}


def _verify_tool_registry(
    dsh: str, profile: str, manifest: dict[str, Any], temporary: Path, environment: dict[str, str], timeout_seconds: int,
    composed: str,
) -> int:
    import yaml

    from cosmatter.dsh_profile_status import _dsh_workbench_patch
    from cosmatter.local_api import LocalMissionApi
    from cosmatter.ui_preview import build_ui_preview_server

    def provider_settings_disabled() -> Any:
        raise ReleaseGateError("provider settings are disabled for the DSH release probe")

    api = LocalMissionApi(temporary / "probe-runs", settings_loader=provider_settings_disabled)
    saved_document = _seed_saved_document(api.runs_dir)
    catalogue = api.plugin_catalogue()
    web_dir = temporary / "probe-web"
    web_dir.mkdir()
    (web_dir / "index.html").write_text("<title>CosMatter DSH release probe</title>", encoding="utf-8")

    expected_tools = [tool for entry in manifest["packages"] for tool in entry["tools"]]
    run_id = "cosmatter_release_probe"
    with build_ui_preview_server(0, web_dir, api=api) as server:
        patch = temporary / "registry-probe.json"
        shutil.copyfile(ROOT / "tools" / "verify_dsh_tool_registry.mjs", temporary / "registry-probe.mjs")
        patch.write_text(json.dumps([
            {"id": "headless-runner", "disabled": True},
            {"id": "llm-deepseek-account", "disabled": True},
            *yaml.safe_load(_dsh_workbench_patch(composed, server.server_port, run_id)),
            {"insert": [{
                "id": "cosmatter-release-registry-probe",
                "name": "./registry-probe.mjs",
                "config": {"expectedTools": expected_tools, "catalogue": catalogue, "webOrigin": f"http://127.0.0.1:{server.server_port}",
                           "runId": run_id, "savedDocument": saved_document},
            }]},
        ]), encoding="utf-8")
        worker = Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            probe = _run(
                [dsh, "--profile", profile, "--patch", str(patch), "CosMatter release registry probe"], cwd=temporary,
                env=environment, timeout=timeout_seconds,
            )
        finally:
            server.shutdown()
            worker.join()
    marker = f"CosMatter release probe: {len(expected_tools)} tools, loopback catalogue, mission result card, bound stage contract, document receipt card, and browser handoff verified"
    if probe.returncode or marker not in probe.stdout:
        raise ReleaseGateError(f"installed bundle tool registry failed: {probe.stderr.strip() or 'missing tool registry result'}")
    return len(expected_tools)


def _command_text(command: list[str]) -> str:
    completed = _run(command, cwd=ROOT, timeout=30)
    if completed.returncode:
        raise ReleaseGateError(f"command failed: {' '.join(command)}")
    return completed.stdout.strip()


def _run(command: list[str], *, cwd: Path, timeout: int, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(command, cwd=cwd, env=env, text=True, encoding="utf-8", capture_output=True, check=False, timeout=timeout)
    except subprocess.TimeoutExpired as error:
        raise ReleaseGateError(f"command timed out after {timeout}s: {Path(command[0]).name}") from error


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ReleaseGateError(f"cannot read {path.name}") from error
    if not isinstance(payload, dict):
        raise ReleaseGateError(f"{path.name} must be a JSON object")
    return payload


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ReleaseGateError as error:
        print(f"release gate failed: {error}", file=sys.stderr)
        raise SystemExit(2)
