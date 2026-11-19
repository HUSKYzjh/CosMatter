"""Redacted, read-only bundle installation status for the local DSH profile."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, NamedTuple
from urllib.parse import parse_qs, urlsplit


DSH_PROFILE_STATUS_SCHEMA = "cosmatter.dsh-profile-status/v2"
DSH_PROFILE_STATUS_TRUST = "local_installation_snapshot_not_profile_boot_or_plugin_execution"
EXPECTED_DSH_PACKAGES = (
    "@cosmatter/dsh-mission-plugin",
    "@cosmatter/dsh-observability-plugin",
    "@cosmatter/dsh-policy-plugin",
    "@cosmatter/dsh-research-plugin",
    "@cosmatter/dsh-review-plugin",
    "@cosmatter/dsh-document-plugin",
    "@cosmatter/dsh-graph-plugin",
)
_PROFILE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")
_MAX_MANIFEST_BYTES = 128_000
_ENTRY = "lib/index.js"
_PATCH = "cordis.patch.yml"
_COMPOSITION_RECEIPT = ".cosmatter-composition-check.json"
_COMPOSITION_SCHEMA = "cosmatter.dsh-composition-check/v1"
_REGISTRY_RECEIPT = ".cosmatter-tool-registry-check.json"
_REGISTRY_SCHEMA = "cosmatter.dsh-tool-registry-check/v1"
_PORT_HISTORY_FILE = ".cosmatter-tool-registry-ports.json"
_PORT_HISTORY_SCHEMA = "cosmatter.dsh-tool-registry-ports/v1"
_MAX_LOOPBACK_RECEIPTS = 16
_MAX_CONFIG_BYTES = 1_000_000
_DIAGNOSTIC_CLEANUP_FAILED = "Diagnostic cleanup did not finish."
_DSH_VERSION = re.compile(r"[0-9]{1,4}\.[0-9]{1,4}\.[0-9]{1,4}(?:-[a-z0-9.]{1,24})?")
_DSH_UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\1bf39983-50d0-5fe0-9ef4-cece76f67c5e"
_REGISTRY_OUTPUT = "COSMATTER_TOOL_REGISTRY "
_RUN_STATUS_OUTPUT = "COSMATTER_DSH_RUN_STATUS "
_EVIDENCE_OUTPUT = "COSMATTER_DSH_EVIDENCE "
_RECENT_RUNS_OUTPUT = "COSMATTER_DSH_RECENT_RUNS "
_CATALOGUE_OUTPUT = "COSMATTER_DSH_CATALOGUE "
_ARTIFACTS_OUTPUT = "COSMATTER_DSH_RUN_ARTIFACTS "
_RUN_READ_OUTPUT = "COSMATTER_DSH_RUN_READ "
_OBSERVABILITY_BUNDLE = "@cosmatter/dsh-observability-plugin"
_GRAPH_BUNDLE = "@cosmatter/dsh-graph-plugin"
_POLICY_BUNDLE = "@cosmatter/dsh-policy-plugin"
_CATALOGUE_TOOL = "cosmatter_plugin_catalogue"
DSH_RUN_READ_TOOLS = {
    "cosmatter_workflow_status": _OBSERVABILITY_BUNDLE,
    "cosmatter_stage_contract": _OBSERVABILITY_BUNDLE,
    "cosmatter_operational_telemetry": _OBSERVABILITY_BUNDLE,
    "cosmatter_workflow_dag": _OBSERVABILITY_BUNDLE,
    "cosmatter_candidate_screening_template": "@cosmatter/dsh-review-plugin",
}
_LOCAL_RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,254}")
_BOOTSTRAP_ENV = {
    "path", "pathext", "comspec", "systemroot", "windir", "temp", "tmp",
    "systemdrive", "programdata", "programfiles", "programfiles(x86)", "lang",
}
_BUNDLE_TOOLS = dict(zip(EXPECTED_DSH_PACKAGES, (
    ("cosmatter_mission_create",),
    ("cosmatter_recent_runs", "cosmatter_workflow_status", "cosmatter_stage_contract", "cosmatter_operational_telemetry", "cosmatter_workflow_dag", "cosmatter_artifact_manifest"),
    ("cosmatter_plugin_catalogue", "cosmatter_plugin_authorization_plan"),
    ("cosmatter_research_plan_draft", "cosmatter_research_plan_approve", "cosmatter_research_query_execute"),
    ("cosmatter_candidate_screening_template", "cosmatter_candidate_screening_record"),
    ("cosmatter_mineru_source_submit", "cosmatter_mineru_task_poll"),
    ("cosmatter_graph_query", "cosmatter_accepted_evidence_search", "cosmatter_graph_plan", "cosmatter_graph_review_request"),
), strict=True))
_REGISTRY_PROBE = """
export const name = 'cosmatter-tool-registry-check'
export const inject = ['tools']
export async function apply(ctx, { expected, checkLoopback }) {
  const deadline = Date.now() + 6000
  let observed
  do {
    const registered = new Set(ctx.tools.definitions().map(({ name }) => name))
    observed = expected.filter(name => registered.has(name))
    if (observed.length === expected.length) break
    await new Promise(resolve => setTimeout(resolve, 50))
  } while (Date.now() < deadline)
  let output = observed
  if (checkLoopback) {
    const name = 'cosmatter_plugin_catalogue'
    let loopbackStatus = 'tool_not_registered'
    if (observed.includes(name)) {
      loopbackStatus = 'unavailable'
      try {
        const execution = await ctx.tools.execute({
          calls: [{type: 'tool-call', id: name, name, arguments: '{}'}],
          signal: AbortSignal.timeout(8000),
        })
        const result = execution.results.find(({callId}) => callId === name)?.result
        const catalogue = result?.value
        if (result && !result.isError && catalogue?.catalogue_api_version === '2.0' &&
            catalogue.trust_status === 'static_catalogue_not_plugin_execution_or_evidence_acceptance' &&
            Array.isArray(catalogue.plugins) && catalogue.plugins.length > 0) {
          loopbackStatus = 'verified'
        }
      } catch {
        // Record only the fixed outcome. Tool errors may include local details.
      }
    }
    output = { registered_tools: observed, loopback_status: loopbackStatus }
  }
  process.stdout.write('COSMATTER_TOOL_REGISTRY ' + JSON.stringify(output) + '\\n', () => process.exit(0))
}
"""
_RUN_STATUS_PROBE = """
export const name = 'cosmatter-run-status-reader'
export const inject = ['tools']
export async function apply(ctx, { runId }) {
  const send = value => process.stdout.write('COSMATTER_DSH_RUN_STATUS ' + JSON.stringify(value) + '\\n', () => process.exit(0))
  const names = ['cosmatter_workflow_status', 'cosmatter_stage_contract']
  try {
    const deadline = Date.now() + 5000
    while (!names.every(name => ctx.tools.definitions().some(tool => tool.name === name))) {
      if (Date.now() >= deadline) return send({error: 'not_registered'})
      await new Promise(resolve => setTimeout(resolve, 50))
    }
    const execution = await ctx.tools.execute({
      calls: names.map(name => ({type: 'tool-call', id: name, name, arguments: JSON.stringify({run_id: runId})})),
      signal: AbortSignal.timeout(8000),
    })
    const results = new Map(execution.results.map(({callId, result}) => [callId, result]))
    const [workflow, contract] = names.map(name => results.get(name))
    if (!workflow || !contract || workflow.isError || contract.isError) return send({error: 'run_unavailable'})
    const status = workflow.value
    const stages = contract.value
    if (status.run_id !== runId || stages.run_id !== runId || status.mission_id !== stages.mission_id || status.next_stage !== stages.next_stage) {
      return send({error: 'snapshot_changed'})
    }
    return send({
      ...status,
      checked_via: names,
      runtime_safety: stages.runtime_safety,
      next_stage_contract: stages.stages.find(({stage}) => stage === status.next_stage) ?? null,
    })
  } catch {
    return send({error: 'run_unavailable'})
  }
}
"""
_TOOL_READ_PROBE = """
export const name = 'cosmatter-tool-reader'
export const inject = ['tools']
export async function apply(ctx, { tool, args, prefix }) {
  const send = value => process.stdout.write(prefix + JSON.stringify(value) + '\\n', () => process.exit(0))
  try {
    const deadline = Date.now() + 5000
    while (!ctx.tools.definitions().some(({name}) => name === tool)) {
      if (Date.now() >= deadline) return send({error: 'not_registered'})
      await new Promise(resolve => setTimeout(resolve, 50))
    }
    const execution = await ctx.tools.execute({
      calls: [{type: 'tool-call', id: tool, name: tool, arguments: JSON.stringify(args)}],
      signal: AbortSignal.timeout(8000),
    })
    const result = execution.results.find(({callId}) => callId === tool)?.result
    return send(result && !result.isError ? result.value : {error: 'tool_unavailable'})
  } catch {
    return send({error: 'tool_unavailable'})
  }
}
"""


class DshCompositionCheckError(RuntimeError):
    """An explicit local check could not produce a trustworthy receipt."""


class DshBundleRepairError(RuntimeError):
    """The local CosMatter bundles could not be repaired."""


def dsh_profile_status(
    profile_name: str = "tui", *, dsh_home: Path | None = None, loopback_port: int | None = None,
) -> dict[str, Any]:
    """Check declared bundles and their fixed installation files without loading them."""
    if not isinstance(profile_name, str) or not _PROFILE_NAME.fullmatch(profile_name):
        raise ValueError("DSH profile name is invalid")
    if loopback_port is not None and (type(loopback_port) is not int or not 1 <= loopback_port <= 65535):
        raise ValueError("Port must be between 1 and 65535.")
    profile = (dsh_home or _default_dsh_home()) / "profiles" / profile_name
    dependencies: dict[str, object] = {}
    unavailable = False
    try:
        payload = _read_manifest(profile.resolve())
        raw_dependencies = payload.get("dependencies")
        if raw_dependencies is not None and not isinstance(raw_dependencies, dict):
            raise ValueError("DSH profile dependencies are invalid")
        dependencies = raw_dependencies or {}
    except FileNotFoundError:
        pass
    except (OSError, RuntimeError, ValueError):
        unavailable = True

    packages = []
    for package_name in EXPECTED_DSH_PACKAGES:
        raw_reference = dependencies.get(package_name)
        declared = isinstance(raw_reference, str) and 0 < len(raw_reference) <= 500 and bool(raw_reference.strip())
        packages.append({
            "package": package_name,
            "dependency_kind": _dependency_kind(raw_reference) if declared else "absent",
            "install_status": _bundle_status(profile / "node_modules" / package_name, package_name) if declared else "not_declared",
        })
    declared_count = sum(item["dependency_kind"] != "absent" for item in packages)
    installed_count = sum(item["install_status"] == "verified" for item in packages)
    snapshot_state = "unavailable" if unavailable else (
        "installed" if installed_count == len(packages) else "partial" if installed_count else "not_installed"
    )
    snapshot = {
        "schema_version": DSH_PROFILE_STATUS_SCHEMA,
        "profile_name": profile_name,
        "installation_state": snapshot_state,
        "expected_bundle_count": len(packages),
        "declared_bundle_count": declared_count,
        "installed_bundle_count": installed_count,
        "packages": packages,
        "composition_status": "not_checked_by_http_api",
        "trust_status": DSH_PROFILE_STATUS_TRUST,
    }
    if profile_name == "tui" and not unavailable and (check := _read_composition_check(profile)) is not None:
        snapshot["composition_check"] = check
    if profile_name == "tui" and not unavailable and (registry := _read_registry_check(profile, loopback_port)) is not None:
        snapshot["tool_registry_check"] = registry
    return snapshot


def repair_dsh_bundles(
    project_root: Path, *, executable: str = "dsh", dsh_home: Path | None = None,
) -> dict[str, Any]:
    """Link missing CosMatter bundles and enable the installed group in TUI."""
    home = (dsh_home or _default_dsh_home()).resolve()
    before = dsh_profile_status(dsh_home=home)
    if before["installation_state"] == "unavailable":
        raise DshBundleRepairError("The local tui manifest could not be read. Check its contents before repairing bundles.")
    missing = [item["package"] for item in before["packages"] if item["install_status"] != "verified"]
    profile = home / "profiles" / "tui"
    if not missing:
        enabled = _enable_dsh_bundles(profile)
        return {"profile_name": "tui", "status": "activated" if enabled else "already_installed", "repaired_bundles": [], "enabled_bundles": enabled}
    dsh = resolve_dsh_executable(executable)
    if not dsh:
        raise DshBundleRepairError("DSH executable not found. Set PATH or pass --dsh-executable.")
    root = project_root.resolve()
    plugin_root = root / "plugins"
    sources = []
    for package in missing:
        name = package.removeprefix("@cosmatter/dsh-").removesuffix("-plugin")
        source = plugin_root / f"dsh-cosmatter-{name}-plugin"
        if source.resolve() != source or _bundle_status(source, package) != "verified":
            raise DshBundleRepairError(f"Compiled checkout bundle unavailable for {package}. Run from the CosMatter repository root.")
        sources.append(f"link:{source.as_posix()}")
    if os.name == "nt" and Path(dsh).suffix.lower() in {".bat", ".cmd"} and re.search(r"[&|<>^()%!\r\n]", str(root)):
        raise DshBundleRepairError("The checkout path contains characters unsupported by the DSH Windows command launcher.")
    inherited = _BOOTSTRAP_ENV | {"home", "userprofile", "appdata", "localappdata"}
    environment = {key: value for key, value in os.environ.items() if key.casefold() in inherited}
    environment.update(DSH_HOME=str(home), CI="1")
    try:
        result = subprocess.run(
            [dsh, "plugin", "--profile", "tui", "add", "--offline", "--ignore-scripts", *sources],
            cwd=root, env=environment, stdin=subprocess.DEVNULL, capture_output=True, timeout=60, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise DshBundleRepairError("DSH could not finish linking the local bundles. Check the local DSH and pnpm installation.") from error
    if result.returncode:
        raise DshBundleRepairError("DSH could not link the bundles offline. Check pnpm and the local tui profile dependencies.")
    if dsh_profile_status(dsh_home=home)["installation_state"] != "installed":
        raise DshBundleRepairError("Some CosMatter bundle files are still missing or invalid. Refresh the installation checklist.")
    enabled = _enable_dsh_bundles(profile)
    return {"profile_name": "tui", "status": "installed", "repaired_bundles": missing, "enabled_bundles": enabled}


def _enable_dsh_bundles(profile: Path) -> list[str]:
    try:
        manifest = _read_manifest(profile.resolve())
        dsh = manifest.get("dsh")
        settings = dsh.get("profile") if isinstance(dsh, dict) else None
        if not isinstance(settings, dict) or "bundles" not in settings:
            return []
        bundles = settings["bundles"]
        if not isinstance(bundles, list) or any(not isinstance(bundle, str) for bundle in bundles):
            raise DshBundleRepairError("The tui enabled-bundle list is invalid. Check it before enabling CosMatter.")
        additions = [bundle for bundle in EXPECTED_DSH_PACKAGES if bundle not in bundles]
        if additions:
            updated = {**manifest, "dsh": {**dsh, "profile": {**settings, "bundles": bundles + additions}}}
            _write_profile_json(profile, "package.json", updated, indent=2, expected_manifest=manifest)
        return additions
    except DshBundleRepairError:
        raise
    except (OSError, RuntimeError, ValueError) as error:
        raise DshBundleRepairError("Bundle files are installed, but DSH could not persist the enabled-bundle list. Run the repair again.") from error


def open_dsh_workbench(
    port: int, *, executable: str = "dsh", dsh_home: Path | None = None,
    surface: str = "web", open_browser: bool = True, run_id: str | None = None,
) -> int:
    """Open a DSH interface with the installed TUI bundles on this workbench port."""
    if type(port) is not int or not 1 <= port <= 65535:
        raise DshCompositionCheckError("Port must be between 1 and 65535.")
    if surface not in {"web", "tui"}:
        raise DshCompositionCheckError("Select the web or tui surface.")
    if run_id is not None and not _LOCAL_RUN_ID.fullmatch(run_id):
        raise DshCompositionCheckError("Invalid local run ID.")
    dsh = resolve_dsh_executable(executable)
    if not dsh:
        raise DshCompositionCheckError("DSH executable not found. Set PATH or pass --dsh-executable.")
    home = (dsh_home or _default_dsh_home()).resolve()
    if dsh_profile_status(dsh_home=home)["installation_state"] != "installed":
        raise DshCompositionCheckError("The tui profile needs all seven CosMatter bundles. Run cosmatter repair-dsh-bundles first.")
    environment = {**os.environ, "DSH_HOME": str(home)}
    try:
        with tempfile.TemporaryDirectory(prefix="cosmatter-dsh-workbench-") as temporary:
            patch_path = Path(temporary) / "workbench.yml"
            if os.name == "nt" and Path(dsh).suffix.lower() in {".bat", ".cmd"} and re.search(r"[&|<>^()%!\r\n]", str(patch_path)):
                raise DshCompositionCheckError("The temporary directory contains characters unsupported by the DSH Windows command launcher.")
            composed = _run_dsh_diagnostic(dsh, ["--profile", "tui", "--dump-config"], temporary, environment)
            overlay = _dsh_workbench_patch(composed, port, run_id)
            args = [dsh, "--profile", surface, "--patch", str(patch_path)]
            if surface == "web":
                web_config = _run_dsh_diagnostic(dsh, ["--profile", "web", "--dump-config"], temporary, environment)
                overlay = _dsh_web_overlay(overlay, web_config, home)
                args.extend(["--host", "127.0.0.1", "--port", "0"])
                if not open_browser:
                    args.append("--no-open")
            patch_path.write_text(overlay, encoding="utf-8")
            return subprocess.run(args, env=environment, check=False).returncode
    except (OSError, UnicodeError, subprocess.TimeoutExpired) as error:
        raise DshCompositionCheckError("DSH could not open the local workbench session.") from error
    except KeyboardInterrupt:
        return 130


def _dsh_workbench_patch(composed: str, port: int, run_id: str | None = None) -> str:
    # DSH replaces the whole config mapping in a patch. Copy only the seven
    # verified rows' config nodes so timeouts, limits and YAML tags survive.
    try:
        import yaml
        from yaml.nodes import MappingNode, ScalarNode, SequenceNode
    except ImportError as error:
        raise DshCompositionCheckError("Update the CosMatter environment with python -m pip install -e . to open a DSH workbench session.") from error

    string_tag = "tag:yaml.org,2002:str"
    mapping_tag = "tag:yaml.org,2002:map"
    sequence_tag = "tag:yaml.org,2002:seq"
    expected = {
        "cosmatter-" + name.removeprefix("@cosmatter/dsh-").removesuffix("-plugin"): name
        for name in EXPECTED_DSH_PACKAGES
    }
    try:
        document = yaml.compose(composed, Loader=yaml.SafeLoader)
        if not isinstance(document, SequenceNode):
            raise DshCompositionCheckError("The tui configuration is not a supported DSH entry list.")
        entries = {}
        for row in document.value:
            if not isinstance(row, MappingNode):
                continue
            fields = {key.value: value for key, value in row.value if isinstance(key, ScalarNode) and key.tag == string_tag}
            identifier = fields.get("id")
            if not isinstance(identifier, ScalarNode) or identifier.tag != string_tag or identifier.value not in expected:
                continue
            name = fields.get("name")
            disabled = fields.get("disabled")
            if (identifier.value in entries or not isinstance(name, ScalarNode) or name.tag != string_tag
                or name.value != expected[identifier.value] or (disabled is not None and (
                    not isinstance(disabled, ScalarNode) or disabled.tag != "tag:yaml.org,2002:bool" or disabled.value != "false"
                ))):
                raise DshCompositionCheckError("A CosMatter entry was replaced, duplicated or disabled in tui. Check the profile and rerun verification.")
            configuration = fields.get("config", MappingNode(mapping_tag, []))
            if not isinstance(configuration, MappingNode) or configuration.tag != mapping_tag:
                raise DshCompositionCheckError("A CosMatter bundle has a non-mapping configuration. Check its tui configuration before setting a session port.")
            options = [(key, value) for key, value in configuration.value if not (isinstance(key, ScalarNode) and key.value == "baseUrl")]
            options.append((ScalarNode(string_tag, "baseUrl"), ScalarNode(string_tag, f"http://127.0.0.1:{port}")))
            if name.value == _OBSERVABILITY_BUNDLE:
                options = [(key, value) for key, value in options if key.value != "workbenchRunId"]
                if run_id is not None:
                    options.append((ScalarNode(string_tag, "workbenchRunId"), ScalarNode(string_tag, run_id)))
            entries[identifier.value] = MappingNode(mapping_tag, [
                (ScalarNode(string_tag, "id"), identifier),
                (ScalarNode(string_tag, "name"), name),
                (ScalarNode(string_tag, "config"), MappingNode(mapping_tag, options)),
            ])
        if len(entries) != len(expected):
            raise DshCompositionCheckError("The tui configuration must enable all seven CosMatter bundles. Check the profile and rerun verification.")
        return yaml.serialize(SequenceNode(sequence_tag, list(entries.values())), Dumper=yaml.SafeDumper, allow_unicode=True)
    except yaml.YAMLError as error:
        raise DshCompositionCheckError("The tui configuration could not be read as a DSH patch list.") from error


def _dsh_web_overlay(tui_overlay: str, web_config: str, home: Path) -> str:
    """Mount verified local entries in the browser profile without changing its manifest."""
    import yaml
    from yaml.nodes import MappingNode, ScalarNode, SequenceNode

    def fields(row):
        return {key.value: value for key, value in row.value if isinstance(key, ScalarNode)}

    try:
        patch = yaml.compose(tui_overlay, Loader=yaml.SafeLoader)
        web = yaml.compose(web_config, Loader=yaml.SafeLoader)
        if not isinstance(web, SequenceNode):
            raise DshCompositionCheckError("DSH did not return a web profile entry list.")
        additions = []
        overrides = []
        pending = [(row, True) for row in web.value]
        existing = {}
        names = set(EXPECTED_DSH_PACKAGES)
        while pending:
            row, parent_enabled = pending.pop()
            if not isinstance(row, MappingNode):
                continue
            entry = fields(row)
            disabled = entry.get("disabled")
            enabled = parent_enabled and (disabled is None or (
                isinstance(disabled, ScalarNode) and disabled.tag == "tag:yaml.org,2002:bool" and disabled.value == "false"
            ))
            group, children = entry.get("group"), entry.get("config")
            if isinstance(group, ScalarNode) and group.value == "true" and isinstance(children, SequenceNode):
                pending.extend((child, enabled) for child in children.value)
            identifier, name = entry.get("id"), entry.get("name")
            if isinstance(identifier, ScalarNode):
                existing.setdefault(identifier.value, []).append((entry, enabled))
            if isinstance(name, ScalarNode) and name.value in names:
                canonical = name.value.replace("@cosmatter/dsh-", "cosmatter-").removesuffix("-plugin")
                if not isinstance(identifier, ScalarNode) or identifier.value != canonical:
                    raise DshCompositionCheckError("A CosMatter bundle already has a different ID in the web profile. Resolve the conflicting entry before launch.")
        profiles = home / "profiles"
        for row in patch.value:
            entry = fields(row)
            identifier, name = entry["id"].value, entry["name"].value
            matches = existing.get(identifier, [])
            if not matches:
                entry["name"].value = (profiles / "tui" / "node_modules" / name / _ENTRY).resolve(strict=True).as_uri()
                additions.append(row)
                continue
            target, enabled = matches[0]
            target_name = target.get("name")
            if len(matches) != 1 or not enabled or not isinstance(target_name, ScalarNode) or target_name.value != name:
                raise DshCompositionCheckError(f"The web profile has a conflicting or disabled entry for {name}.")
            if (_bundle_status(profiles / "web" / "node_modules" / name, name) != "verified"
                or _bundle_runtime_stamp(profiles / "web", [name]) != _bundle_runtime_stamp(profiles / "tui", [name])):
                raise DshCompositionCheckError(f"The web and tui profiles have different compiled versions of {name}.")
            # Preserve web-specific limits when the bundle is already present.
            config = target.get("config", MappingNode("tag:yaml.org,2002:map", []))
            if not isinstance(config, MappingNode) or config.tag != "tag:yaml.org,2002:map":
                raise DshCompositionCheckError(f"The web configuration for {name} must be a mapping.")
            session_fields = {"baseUrl", "workbenchRunId"} if name == _OBSERVABILITY_BUNDLE else {"baseUrl"}
            session_options = [(key, value) for key, value in entry["config"].value if key.value in session_fields]
            entry["config"].value = [(key, value) for key, value in config.value if not isinstance(key, ScalarNode) or key.value not in session_fields] + session_options
            overrides.append(row)
        if additions:
            overrides.append(MappingNode("tag:yaml.org,2002:map", [(ScalarNode("tag:yaml.org,2002:str", "insert"), SequenceNode(patch.tag, additions))]))
        return yaml.serialize(SequenceNode(patch.tag, overrides), Dumper=yaml.SafeDumper, allow_unicode=True)
    except yaml.YAMLError as error:
        raise DshCompositionCheckError("DSH could not read the web profile configuration.") from error


def check_dsh_composition(
    *, executable: str = "dsh", dsh_home: Path | None = None, verify_tools: bool = False, loopback_port: int | None = None,
) -> dict[str, Any]:
    """Run the fixed TUI composition diagnostic and save only its redacted result."""
    if loopback_port is not None and (type(loopback_port) is not int or not 1 <= loopback_port <= 65535):
        raise DshCompositionCheckError("Port must be between 1 and 65535.")
    dsh = resolve_dsh_executable(executable)
    if not dsh:
        raise DshCompositionCheckError("DSH executable not found. Set PATH or pass --dsh-executable.")
    home = (dsh_home or _default_dsh_home()).resolve()
    profile = home / "profiles" / "tui"
    if not (profile / "package.json").is_file():
        raise DshCompositionCheckError("The local tui profile manifest is missing.")
    environment = {**os.environ, "DSH_HOME": str(home)}
    try:
        before = _configuration_state(profile)
        with tempfile.TemporaryDirectory(prefix="cosmatter-dsh-composition-") as temporary:
            version = _run_dsh_diagnostic(dsh, ["--version"], temporary, environment).strip()
            if not _DSH_VERSION.fullmatch(version):
                raise DshCompositionCheckError("DSH returned an unsupported version string.")
            arguments = ["--profile", "tui", "--dump-config"]
            config = _run_dsh_diagnostic(dsh, arguments, temporary, environment)
            after = _configuration_state(profile)
            if before != after and before.inputs == after.inputs:
                # DSH can generate or refresh cordis.yml on the first dump
                # after installing bundles. Require a stable second dump.
                before = after
                config = _run_dsh_diagnostic(dsh, arguments, temporary, environment)
                after = _configuration_state(profile)
        if before != after:
            raise DshCompositionCheckError("The local profile changed during the check. Run it again.")
        stamp = _stamp_configuration(after)
        composed = _composed_packages(config)
        check = {
            "schema_version": _COMPOSITION_SCHEMA,
            "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "dsh_version": version,
            "bundles": composed,
        }
        _write_profile_json(profile, _COMPOSITION_RECEIPT, {**check, "configuration_stamp": stamp})
        if verify_tools or loopback_port is not None:
            registry = _check_tool_registry(dsh, profile, composed, version, stamp, loopback_port)
            check["tool_registry_check"] = registry
    except (OSError, UnicodeError, subprocess.TimeoutExpired) as exc:
        raise DshCompositionCheckError("DSH composition check timed out or could not complete locally.") from exc
    return {**check, "matches_local_files": True}


def _check_tool_registry(dsh: str, profile: Path, composed: list[str], version: str, stamp: str, loopback_port: int | None) -> dict[str, Any]:
    bundles = [name for name in composed if _bundle_status(profile / "node_modules" / name, name) == "verified"]
    if not bundles:
        raise DshCompositionCheckError("No composed CosMatter bundle has a valid local entry to check.")
    runtime_stamp = _bundle_runtime_stamp(profile, bundles)
    expected = sorted(tool for bundle in bundles for tool in _BUNDLE_TOOLS[bundle])
    bundle_config: dict[str, dict[str, Any] | None] = dict.fromkeys(bundles)
    probe_config: dict[str, Any] = {"expected": expected}
    if loopback_port is not None:
        probe_config["checkLoopback"] = True
        if _POLICY_BUNDLE in bundle_config:
            bundle_config[_POLICY_BUNDLE] = {"baseUrl": f"http://127.0.0.1:{loopback_port}"}
    result = _run_isolated_dsh_probe(dsh, profile, bundle_config, _REGISTRY_PROBE, probe_config, _REGISTRY_OUTPUT)
    tools = result
    loopback_check = None
    if loopback_port is not None:
        if not isinstance(result, dict) or set(result) != {"registered_tools", "loopback_status"}:
            raise DshCompositionCheckError("DSH did not return a valid loopback check.")
        tools = result["registered_tools"]
        loopback_check = {"port": loopback_port, "status": result["loopback_status"]}
    if not isinstance(tools, list) or tools != [name for name in expected if name in tools]:
        raise DshCompositionCheckError("DSH did not return a valid isolated tool registry.")
    if loopback_check is not None and not _valid_loopback_check(loopback_check, tools):
        raise DshCompositionCheckError("DSH did not return a valid loopback check.")
    check = {
        "schema_version": _REGISTRY_SCHEMA,
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "dsh_version": version, "bundles": bundles, "registered_tools": tools,
    }
    if loopback_check is not None:
        check["loopback_check"] = loopback_check
    _save_registry_check(profile, {**check, "configuration_stamp": stamp, "runtime_stamp": runtime_stamp})
    return {**check, "matches_local_files": True}


def read_dsh_run_status(
    run_id: str, *, port: int = 8765, executable: str = "dsh", dsh_home: Path | None = None,
) -> dict[str, Any]:
    """Read one existing run through the installed DSH observability tools."""
    if not _LOCAL_RUN_ID.fullmatch(run_id):
        raise DshCompositionCheckError("Run ID must use letters, numbers, underscores, or hyphens.")
    result = _read_through_bundle(
        _OBSERVABILITY_BUNDLE, executable, dsh_home, port,
        _RUN_STATUS_PROBE, {"runId": run_id}, _RUN_STATUS_OUTPUT,
    )
    if isinstance(result, dict):
        error = result.get("error")
        if error == "not_registered":
            raise DshCompositionCheckError("DSH did not register the CosMatter status tools.")
        if error == "run_unavailable":
            raise DshCompositionCheckError("DSH could not read the run. Check the run ID and that CosMatter is serving the requested port.")
        if error == "snapshot_changed":
            raise DshCompositionCheckError("The workflow changed during the read. Run the command again.")
        if "error" not in result and result.get("run_id") == run_id:
            return result
    raise DshCompositionCheckError("DSH did not return a status for the requested run.")


def read_dsh_evidence_link(link: str, *, executable: str = "dsh", dsh_home: Path | None = None) -> dict[str, Any]:
    """Read the accepted card in a local workbench link through the installed DSH graph tool."""
    run_id, document_id, evidence_id, port = _parse_evidence_link(link)
    tool = "cosmatter_accepted_evidence_search"
    result = _read_through_bundle(
        _GRAPH_BUNDLE, executable, dsh_home, port,
        _TOOL_READ_PROBE, {"tool": tool, "args": {"run_id": run_id, "evidence_id": evidence_id, "limit": 1}, "prefix": _EVIDENCE_OUTPUT},
        _EVIDENCE_OUTPUT,
    )
    if isinstance(result, dict):
        if result.get("error") == "not_registered":
            raise DshCompositionCheckError("DSH did not register the CosMatter evidence search tool.")
        hits = result.get("results")
        if (result.get("run_id") == run_id and result.get("match_mode") == "exact_id"
                and result.get("trust_status") == "accepted_evidence_search_not_new_evidence_or_scientific_conclusion"
                and isinstance(hits, list) and len(hits) == 1 and isinstance(hits[0], dict)
                and hits[0].get("evidence_id") == evidence_id and hits[0].get("document_id") == document_id):
            return {**result, "checked_via": [tool]}
    raise DshCompositionCheckError("DSH could not find the accepted card for this link. Check the link and the local CosMatter service.")


def read_dsh_screening_link(link: str, *, executable: str = "dsh", dsh_home: Path | None = None) -> dict[str, Any]:
    """Read the screening snapshot identified by a local workbench link."""
    fields, port = _parse_local_workbench_link(link, ("run", "screening"), "screening")
    run_id, revision = fields["run"], fields["screening"]
    if not _LOCAL_RUN_ID.fullmatch(run_id) or not re.fullmatch(r"[a-f0-9]{64}", revision):
        raise DshCompositionCheckError("Screening link identifiers are invalid.")
    result = read_dsh_run_tool("cosmatter_candidate_screening_template", run_id, port=port, executable=executable, dsh_home=dsh_home)
    current = result.get("checklist_revision")
    if not isinstance(current, str) or not re.fullmatch(r"[a-f0-9]{64}", current):
        raise DshCompositionCheckError("DSH did not return a versioned screening checklist.")
    if current != revision:
        raise DshCompositionCheckError("Screening checklist changed. Refresh the workbench checklist and copy a new DSH command.")
    return result


def read_dsh_catalogue(*, port: int = 8765, executable: str = "dsh", dsh_home: Path | None = None) -> dict[str, Any]:
    """Read the workbench's static capability contracts through the installed policy tool."""
    config = {"tool": _CATALOGUE_TOOL, "args": {}, "prefix": _CATALOGUE_OUTPUT}
    result = _read_through_bundle(_POLICY_BUNDLE, executable, dsh_home, port, _TOOL_READ_PROBE, config, _CATALOGUE_OUTPUT)
    if isinstance(result, dict):
        if result.get("error") == "not_registered":
            raise DshCompositionCheckError("DSH did not register the catalogue tool. Check the installed policy bundle.")
        plugins = result.get("plugins")
        if (
            result.get("catalogue_api_version") == "2.0"
            and result.get("trust_status") == "static_catalogue_not_plugin_execution_or_evidence_acceptance"
            and isinstance(plugins, list)
            and 1 <= len(plugins) <= 64
            and all(isinstance(item, dict) and isinstance(item.get("plugin_id"), str) and item["plugin_id"] for item in plugins)
        ):
            return {
                "catalogue_api_version": result["catalogue_api_version"],
                "trust_status": result["trust_status"],
                "plugins": plugins,
                "checked_via": [_CATALOGUE_TOOL],
            }
    raise DshCompositionCheckError("DSH could not read the capability catalogue. Check the local workbench API and port.")


def read_dsh_recent_runs(*, port: int = 8765, executable: str = "dsh", dsh_home: Path | None = None) -> dict[str, Any]:
    """Read a label-free local run index through the installed observability bundle."""
    tool = "cosmatter_recent_runs"
    result = _read_through_bundle(
        _OBSERVABILITY_BUNDLE, executable, dsh_home, port,
        _TOOL_READ_PROBE, {"tool": tool, "args": {}, "prefix": _RECENT_RUNS_OUTPUT}, _RECENT_RUNS_OUTPUT,
    )
    if isinstance(result, dict):
        if result.get("error") == "not_registered":
            raise DshCompositionCheckError("DSH did not register the CosMatter recent runs tool. Update the observability bundle.")
        if result.get("schema_version") == "cosmatter.recent-run-links/v1" and isinstance(result.get("runs"), list):
            return {**result, "checked_via": [tool]}
    raise DshCompositionCheckError("DSH could not read recent runs. Check that CosMatter is serving the local API on the requested port.")


def read_dsh_run_artifacts(
    run_id: str, *, port: int = 8765, executable: str = "dsh", dsh_home: Path | None = None,
) -> dict[str, Any]:
    """Read the same fixed artifact directory as the local workbench."""
    if not _LOCAL_RUN_ID.fullmatch(run_id):
        raise DshCompositionCheckError("Run ID must use letters, numbers, underscores, or hyphens.")
    tool = "cosmatter_artifact_manifest"
    config = {"tool": tool, "args": {"run_id": run_id}, "prefix": _ARTIFACTS_OUTPUT}
    result = _read_through_bundle(_OBSERVABILITY_BUNDLE, executable, dsh_home, port, _TOOL_READ_PROBE, config, _ARTIFACTS_OUTPUT)
    if isinstance(result, dict):
        if result.get("error") == "not_registered":
            raise DshCompositionCheckError("DSH did not register the CosMatter artifact manifest tool.")
        if (result.get("schema_version") == "cosmatter.artifact/v1" and result.get("run_id") == run_id
                and result.get("trust_status") == "allowlisted_artifact_index_not_scientific_evidence"):
            origin = "http://127.0.0.1" if port == 80 else f"http://127.0.0.1:{port}"
            return {**result, "workbench_url": f"{origin}/?api=local#run={run_id}&artifacts=1", "checked_via": [tool]}
    raise DshCompositionCheckError("DSH could not read the artifact list. Check the run ID and the local CosMatter service.")


def read_dsh_run_tool(
    tool: str, run_id: str, *, port: int = 8765, executable: str = "dsh", dsh_home: Path | None = None,
) -> dict[str, Any]:
    """Dispatch one fixed, run-scoped read through an isolated DSH plugin."""
    bundle = DSH_RUN_READ_TOOLS.get(tool)
    if bundle is None:
        raise DshCompositionCheckError("Choose an allowed local DSH read tool.")
    if not _LOCAL_RUN_ID.fullmatch(run_id):
        raise DshCompositionCheckError("Run ID must use letters, numbers, underscores, or hyphens.")
    config = {"tool": tool, "args": {"run_id": run_id}, "prefix": _RUN_READ_OUTPUT}
    result = _read_through_bundle(bundle, executable, dsh_home, port, _TOOL_READ_PROBE, config, _RUN_READ_OUTPUT)
    if isinstance(result, dict):
        if result.get("error") == "not_registered":
            raise DshCompositionCheckError("The named tool was not registered by its installed CosMatter bundle.")
        if "error" not in result and result.get("run_id") == run_id:
            return {**result, "checked_via": [tool]}
    raise DshCompositionCheckError("The DSH tool could not read this run. Check the run ID, its saved artifacts, and the local CosMatter port.")


def _read_through_bundle(
    bundle: str, executable: str, dsh_home: Path | None, port: int,
    script: str, config: dict[str, Any], prefix: str,
) -> Any:
    if not 1 <= port <= 65535:
        raise DshCompositionCheckError("Port must be between 1 and 65535.")
    dsh = resolve_dsh_executable(executable)
    if not dsh:
        raise DshCompositionCheckError("DSH executable not found. Set PATH or pass --dsh-executable.")
    profile = (dsh_home or _default_dsh_home()).resolve() / "profiles" / "tui"
    if _bundle_status(profile / "node_modules" / bundle, bundle) != "verified":
        raise DshCompositionCheckError(f"The local tui profile has no valid {bundle} bundle.")
    return _run_isolated_dsh_probe(
        dsh, profile, {bundle: {"baseUrl": f"http://127.0.0.1:{port}"}}, script, config, prefix,
    )


def _parse_evidence_link(link: str) -> tuple[str, str, str, int]:
    fields, port = _parse_local_workbench_link(link, ("run", "document", "evidence"), "evidence")
    run_id, document_id, evidence_id = (fields[key] for key in ("run", "document", "evidence"))
    if not _LOCAL_RUN_ID.fullmatch(run_id) or any(
        not 1 <= len(value) <= limit or value.strip() != value or re.search(r"[\x00-\x1f\x7f]", value)
        for value, limit in ((document_id, 255), (evidence_id, 200))
    ):
        raise DshCompositionCheckError("Evidence link identifiers are invalid.")
    return run_id, document_id, evidence_id, port


def _parse_local_workbench_link(link: str, selectors: tuple[str, ...], label: str) -> tuple[dict[str, str], int]:
    message = f"Expected a local CosMatter {label} link."
    if not isinstance(link, str) or len(link) > 4_850 or re.search(r"[\x00-\x20\x7f]", link):
        raise DshCompositionCheckError(message)
    try:
        url = urlsplit(link)
        port = url.port if url.port is not None else 80
        fields = parse_qs(url.fragment, strict_parsing=True, keep_blank_values=True, errors="strict", max_num_fields=len(selectors))
    except ValueError as exc:
        raise DshCompositionCheckError(message) from exc
    if (url.scheme != "http" or url.hostname not in {"127.0.0.1", "localhost"} or url.username is not None
            or url.password is not None or url.path != "/" or url.query != "api=local" or not 1 <= port <= 65535
            or set(fields) != set(selectors) or any(len(values) != 1 for values in fields.values())):
        raise DshCompositionCheckError(message)
    return {key: values[0] for key, values in fields.items()}, port


def _run_isolated_dsh_probe(
    dsh: str, profile: Path, bundles: dict[str, dict[str, Any] | None], script: str,
    probe_config: dict[str, Any], prefix: str,
) -> Any:
    # TemporaryDirectory cleanup can raise a second error while a child still holds a file.
    interruption: subprocess.TimeoutExpired | KeyboardInterrupt | None = None
    try:
        with tempfile.TemporaryDirectory(prefix="cosmatter-dsh-probe-") as temporary:
            directory = Path(temporary)
            environment = {key: value for key, value in os.environ.items() if key.casefold() in _BOOTSTRAP_ENV}
            environment.update({key: temporary for key in ("HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA")})
            environment.update(DSH_HOME=str(directory / "dsh-home"), CI="1")
            (directory / "probe.mjs").write_text(script, encoding="utf-8")
            overlay = directory / "probe.json"
            entries = [
                {"id": "probe-" + name.split("/")[1], "name": (profile / "node_modules" / name / _ENTRY).resolve(strict=True).as_uri(), "config": config or {}}
                for name, config in bundles.items()
            ]
            overlay.write_text(json.dumps([
                {"id": "headless-runner", "disabled": True},
                {"id": "llm-deepseek-account", "disabled": True},
                {"insert": [*entries, {"id": "cosmatter-isolated-probe", "name": "./probe.mjs", "config": probe_config}]},
            ]), encoding="utf-8")
            try:
                output = _run_dsh_diagnostic(dsh, [
                    "--profile", "cosmatter-isolated-probe", "--from-default-profile", "headless",
                    "--patch", str(overlay), "CosMatter local diagnostic",
                ], temporary, environment)
            except (subprocess.TimeoutExpired, KeyboardInterrupt) as exc:
                interruption = exc
                raise
        results = [line.removeprefix(prefix) for line in output.splitlines() if line.startswith(prefix)]
        if len(results) == 1:
            return json.loads(results[0])
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        if isinstance(interruption, KeyboardInterrupt):
            raise interruption from None
        if interruption is not None:
            message = "The isolated DSH diagnostic timed out."
            if exc is not interruption or _DIAGNOSTIC_CLEANUP_FAILED in getattr(interruption, "__notes__", ()):
                message += " " + _DIAGNOSTIC_CLEANUP_FAILED
            raise DshCompositionCheckError(message) from None
        raise DshCompositionCheckError("The isolated DSH diagnostic could not complete.") from exc
    raise DshCompositionCheckError("The isolated DSH diagnostic did not return a result.")


def _bundle_runtime_stamp(profile: Path, bundles: list[str]) -> str:
    digest = hashlib.sha256()
    for bundle in bundles:
        root = (profile / "node_modules" / bundle).resolve(strict=True)
        files = sorted((root / "lib").rglob("*.js"))
        if not files or len(files) > 64:
            raise OSError("Invalid compiled DSH bundle inventory")
        for file in files:
            resolved = file.resolve(strict=True)
            if not resolved.is_relative_to(root):
                raise OSError("Invalid compiled DSH bundle path")
            with resolved.open("rb") as stream:
                content = stream.read(_MAX_CONFIG_BYTES + 1)
            if len(content) > _MAX_CONFIG_BYTES:
                raise OSError("Compiled DSH bundle file exceeds the size limit")
            digest.update(f"{bundle}/{file.relative_to(root).as_posix()}\n".encode("utf-8"))
            digest.update(hashlib.sha256(content).digest())
    return digest.hexdigest()


def _run_dsh_diagnostic(
    dsh: str, arguments: list[str], cwd: str, environment: dict[str, str], *, timeout: float = 60,
) -> str:
    group_options = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
    with subprocess.Popen(
        [dsh, *arguments], cwd=cwd, env=environment, stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, **group_options,
    ) as process:
        try:
            stdout, _ = process.communicate(timeout=timeout)
        except (subprocess.TimeoutExpired, KeyboardInterrupt) as exc:
            try:
                # A Windows .cmd waits for the runtime. Terminate the tree while
                # its root still exists, before closing the pipe and temporary home.
                if os.name == "nt":
                    taskkill = Path(os.environ["SystemRoot"]) / "System32" / "taskkill.exe"
                    try:
                        subprocess.run(
                            [str(taskkill), "/PID", str(process.pid), "/T", "/F"], stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10, check=False,
                        )
                    finally:
                        process.kill()
                else:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                process.communicate(timeout=10)
            except (OSError, subprocess.TimeoutExpired):
                exc.add_note(_DIAGNOSTIC_CLEANUP_FAILED)
            raise
    if process.returncode or len(stdout) > _MAX_CONFIG_BYTES:
        raise DshCompositionCheckError("DSH could not produce a valid local diagnostic result.")
    return stdout.decode("utf-8")


def _composed_packages(config: str) -> list[str]:
    # The bundled patches insert top-level entries. Treat quoted values as
    # text and reject ambiguous IDs or conditional disabling without evaluating YAML.
    entries: dict[str, list[dict[str, list[str]]]] = {}
    for block in re.split(r"(?m)(?=^- )", config):
        lines = block.splitlines()
        if not lines or not (header := re.fullmatch(r"- id: ([a-z0-9-]+)", lines[0])):
            continue
        fields: dict[str, list[str]] = {}
        for line in lines[1:]:
            if match := re.fullmatch(r"  (name|disabled): (.+)", line):
                fields.setdefault(match[1], []).append(match[2].strip())
        entries.setdefault(header[1], []).append(fields)
    if not entries:
        raise DshCompositionCheckError("DSH did not return a supported composed entry list.")
    composed = []
    for package in EXPECTED_DSH_PACKAGES:
        plugin_id = package.removeprefix("@cosmatter/dsh-").removesuffix("-plugin")
        matches = entries.get(f"cosmatter-{plugin_id}", [])
        if len(matches) != 1:
            continue
        names = matches[0].get("name", [])
        disabled = matches[0].get("disabled", [])
        if len(names) == 1 and names[0] in {package, f"'{package}'", f'"{package}"'} and disabled in ([], ["false"]):
            composed.append(package)
    return composed


def _configuration_stamp(profile: Path) -> str:
    return _stamp_configuration(_configuration_state(profile))


class _DshConfigurationState(NamedTuple):
    generated_config_digest: str | None
    inputs: list[tuple[int, int, int] | None]


def _stamp_configuration(state: _DshConfigurationState) -> str:
    return hashlib.sha256(json.dumps(state).encode("ascii")).hexdigest()


def _configuration_state(profile: Path) -> _DshConfigurationState:
    files = [profile / name for name in ("package.json", _PATCH, "pnpm-lock.yaml", "pnpm-workspace.yaml")]
    files.append(profile.parent.parent / _PATCH)
    for package in EXPECTED_DSH_PACKAGES:
        directory = profile / "node_modules" / package
        files.extend(directory / name for name in ("package.json", _ENTRY, _PATCH))
    metadata = []
    for file in files:
        try:
            stat = file.stat()
            metadata.append((stat.st_size, stat.st_mtime_ns, stat.st_ino))
        except FileNotFoundError:
            metadata.append(None)
    return _DshConfigurationState(_profile_config_digest(profile), metadata)


def _profile_config_digest(profile: Path) -> str | None:
    root = profile.resolve()
    try:
        config = (root / "cordis.yml").resolve(strict=True)
    except FileNotFoundError:
        return None
    if not config.is_relative_to(root) or not config.is_file():
        raise OSError("DSH profile config is not a file within the profile")
    with config.open("rb") as stream:
        contents = stream.read(_MAX_CONFIG_BYTES + 1)
    if len(contents) > _MAX_CONFIG_BYTES:
        raise OSError("DSH profile config exceeds the check size limit")
    return hashlib.sha256(contents).hexdigest()


def _write_profile_json(
    profile: Path, filename: str, payload: dict[str, Any], *, indent: int | None = None, expected_manifest: dict[str, Any] | None = None,
) -> None:
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=profile, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            json.dump(payload, stream, ensure_ascii=indent is None, indent=indent)
            if indent is not None:
                stream.write("\n")
            stream.close()
            if expected_manifest is not None and expected_manifest != _read_manifest(profile.resolve()):
                raise DshBundleRepairError("The tui manifest changed while enabling bundles. Run the repair again.")
            # Windows briefly denies atomic replacement while another check or
            # an HTTP reader has the destination receipt open.
            for attempt in range(6):
                try:
                    temporary.replace(profile / filename)
                    break
                except PermissionError as error:
                    if expected_manifest is not None or getattr(error, "winerror", None) not in (5, 32, 33) or attempt == 5:
                        raise
                    time.sleep(0.01 * 2**attempt)
        finally:
            temporary.unlink(missing_ok=True)


def _read_profile_receipt(profile: Path, filename: str, *, max_bytes: int = 4096) -> dict[str, Any] | None:
    try:
        root = profile.resolve()
        path = (root / filename).resolve(strict=True)
        if not path.is_relative_to(root) or not path.is_file():
            return None
        with path.open("rb") as stream:
            data = stream.read(max_bytes + 1)
        payload = json.loads(data)
        return payload if len(data) <= max_bytes and isinstance(payload, dict) else None
    except (OSError, RuntimeError, ValueError):
        return None


def _read_composition_check(profile: Path) -> dict[str, Any] | None:
    try:
        payload = _read_profile_receipt(profile, _COMPOSITION_RECEIPT)
        if payload is None or set(payload) != {"schema_version", "checked_at", "dsh_version", "bundles", "configuration_stamp"}:
            return None
        version, checked_at, bundles = payload["dsh_version"], payload["checked_at"], payload["bundles"]
        stamp = payload["configuration_stamp"]
        if (
            payload["schema_version"] != _COMPOSITION_SCHEMA
            or not isinstance(version, str) or not _DSH_VERSION.fullmatch(version)
            or not isinstance(checked_at, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", checked_at)
            or not isinstance(bundles, list) or bundles != [package for package in EXPECTED_DSH_PACKAGES if package in bundles]
            or not isinstance(stamp, str) or not re.fullmatch(r"[a-f0-9]{64}", stamp)
        ):
            return None
        datetime.fromisoformat(checked_at)
        return {
            "schema_version": _COMPOSITION_SCHEMA, "checked_at": checked_at, "dsh_version": version, "bundles": bundles,
            "matches_local_files": stamp == _configuration_stamp(profile),
        }
    except (OSError, RuntimeError, ValueError):
        return None


@contextmanager
def _registry_write_lock(profile: Path) -> Iterator[None]:
    # Atomic replacement protects readers. Lock a separate, stable file so
    # independent CLI processes cannot overwrite one another's port history.
    with (profile / ".cosmatter-tool-registry.lock").open("a+b") as stream:
        if os.name == "nt":
            import msvcrt
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        yield


def _save_registry_check(profile: Path, check: dict[str, Any]) -> None:
    with _registry_write_lock(profile):
        if (check["configuration_stamp"] != _configuration_stamp(profile)
                or check["runtime_stamp"] != _bundle_runtime_stamp(profile, check["bundles"])):
            raise DshCompositionCheckError("The local profile or bundle files changed during the registration check. Run it again.")
        port = check.get("loopback_check", {}).get("port")
        history = [check] if port is not None else []
        seen = {port}
        for previous in _load_registry_receipts(profile):
            old_port = previous.get("loopback_check", {}).get("port")
            if old_port is None or old_port in seen:
                continue
            if not _same_registry_generation(previous, check):
                continue
            seen.add(old_port)
            history.append(previous)
        _write_profile_json(profile, _PORT_HISTORY_FILE, {
            "schema_version": _PORT_HISTORY_SCHEMA, "receipts": history[:_MAX_LOOPBACK_RECEIPTS],
        })
        # Older workbenches read this exact, single-check schema. Commit it last.
        _write_profile_json(profile, _REGISTRY_RECEIPT, check)


def _same_registry_generation(first: dict[str, Any], second: dict[str, Any]) -> bool:
    return all(first[key] == second[key] for key in ("configuration_stamp", "runtime_stamp", "dsh_version", "bundles"))


def _load_registry_receipts(profile: Path, *, include_history: bool = True) -> list[dict[str, Any]]:
    latest = _read_profile_receipt(profile, _REGISTRY_RECEIPT)
    if latest is None or not _valid_registry_receipt(latest):
        return []
    if not include_history:
        return [latest]
    sidecar = _read_profile_receipt(profile, _PORT_HISTORY_FILE, max_bytes=4096 * (1 + _MAX_LOOPBACK_RECEIPTS))
    if sidecar is None or set(sidecar) != {"schema_version", "receipts"} or sidecar["schema_version"] != _PORT_HISTORY_SCHEMA:
        return [latest]
    history = sidecar["receipts"]
    if not isinstance(history, list) or len(history) > _MAX_LOOPBACK_RECEIPTS:
        return [latest]
    return [latest] + [
        item for item in history
        if _valid_registry_receipt(item) and "loopback_check" in item and _same_registry_generation(item, latest)
    ]


def _valid_registry_receipt(payload: object) -> bool:
    if not isinstance(payload, dict) or set(payload) - {"loopback_check"} != {"schema_version", "checked_at", "dsh_version", "bundles", "registered_tools", "configuration_stamp", "runtime_stamp"}:
        return False
    version, checked_at, bundles = payload["dsh_version"], payload["checked_at"], payload["bundles"]
    tools, stamp, runtime_stamp = payload["registered_tools"], payload["configuration_stamp"], payload["runtime_stamp"]
    if (
        payload["schema_version"] != _REGISTRY_SCHEMA
        or not isinstance(version, str) or not _DSH_VERSION.fullmatch(version)
        or not isinstance(checked_at, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", checked_at)
        or not isinstance(bundles, list) or not bundles or bundles != [name for name in EXPECTED_DSH_PACKAGES if name in bundles]
        or not all(isinstance(value, str) and re.fullmatch(r"[a-f0-9]{64}", value) for value in (stamp, runtime_stamp))
    ):
        return False
    expected = sorted(tool for bundle in bundles for tool in _BUNDLE_TOOLS[bundle])
    if not isinstance(tools, list) or tools != [name for name in expected if name in tools]:
        return False
    if "loopback_check" in payload and not _valid_loopback_check(payload["loopback_check"], tools):
        return False
    try:
        datetime.fromisoformat(checked_at)
    except ValueError:
        return False
    return True


def _read_registry_check(profile: Path, loopback_port: int | None) -> dict[str, Any] | None:
    receipts = _load_registry_receipts(profile, include_history=loopback_port is not None)
    if not receipts:
        return None
    payload = receipts[0]
    if loopback_port is not None:
        for item in receipts:
            if item.get("loopback_check", {}).get("port") == loopback_port:
                payload = item
                break
        else:
            payload = {key: value for key, value in payload.items() if key != "loopback_check"}
    try:
        matches = (
            payload["configuration_stamp"] == _configuration_stamp(profile)
            and payload["runtime_stamp"] == _bundle_runtime_stamp(profile, payload["bundles"])
        )
    except (OSError, RuntimeError, ValueError):
        matches = False
    return {key: value for key, value in payload.items() if key not in {"configuration_stamp", "runtime_stamp"}} | {"matches_local_files": matches}


def _valid_loopback_check(value: object, tools: list[str]) -> bool:
    if not isinstance(value, dict) or set(value) != {"port", "status"}:
        return False
    port = value["port"]
    statuses = ("verified", "unavailable") if _CATALOGUE_TOOL in tools else ("tool_not_registered",)
    return type(port) is int and 1 <= port <= 65535 and value["status"] in statuses


def _bundle_status(directory: Path, package_name: str) -> str:
    try:
        root = directory.resolve(strict=True)
        manifest = _read_manifest(root)
        dsh = manifest.get("dsh")
        bundle = dsh.get("bundle") if isinstance(dsh, dict) else None
        if (
            manifest.get("name") != package_name
            or manifest.get("main") != f"./{_ENTRY}"
            or not isinstance(bundle, dict)
            or bundle.get("patch") != f"./{_PATCH}"
        ):
            return "invalid_bundle"
        for filename in (_ENTRY, _PATCH):
            entry = (root / filename).resolve(strict=True)
            if not entry.is_relative_to(root) or not entry.is_file():
                return "invalid_bundle"
    except FileNotFoundError:
        return "missing_bundle"
    except (OSError, RuntimeError, ValueError):
        return "invalid_bundle"
    return "verified"


def _read_manifest(root: Path) -> dict[str, Any]:
    manifest = (root / "package.json").resolve(strict=True)
    if not manifest.is_relative_to(root) or not manifest.is_file():
        raise ValueError("DSH package manifest is outside its package or is not a file")
    with manifest.open("rb") as stream:
        data = stream.read(_MAX_MANIFEST_BYTES + 1)
    if len(data) > _MAX_MANIFEST_BYTES:
        raise ValueError("DSH package manifest is too large")
    payload = json.loads(data.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("DSH package manifest is invalid")
    return payload


def resolve_dsh_executable(executable: str = "dsh") -> str | None:
    """Find the requested launcher or the registered DeepSeek Harness desktop CLI."""
    found = shutil.which(executable)
    if found or executable != "dsh" or sys.platform != "win32":
        return found

    import winreg

    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
            try:
                with winreg.OpenKey(hive, _DSH_UNINSTALL_KEY, 0, winreg.KEY_READ | view) as key:
                    name, _ = winreg.QueryValueEx(key, "DisplayName")
                    if name != "DeepSeek Harness":
                        continue
                    location, _ = winreg.QueryValueEx(key, "InstallLocation")
                if isinstance(location, str):
                    launcher = Path(location) / "resources/runtime/cli/bin/dsh.cmd"
                    if launcher.is_absolute() and launcher.is_file():
                        return str(launcher)
            except (OSError, ValueError):
                continue
    return None


def _default_dsh_home() -> Path:
    configured = os.environ.get("DSH_HOME")
    return Path(configured).expanduser() if configured else Path.home() / ".dsh"


def _dependency_kind(reference: object) -> str:
    if not isinstance(reference, str):
        return "absent"
    lowered = reference.casefold()
    if lowered.startswith(("link:", "file:")):
        return "local_link"
    if lowered.startswith(("http:", "https:", "git:", "git+", "ssh:")):
        return "remote_reference"
    return "registry_reference"
