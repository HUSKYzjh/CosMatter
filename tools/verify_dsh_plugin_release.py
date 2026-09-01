"""Verify the versioned CosMatter DSH bundle release gate.

Default mode is deliberately local and keyless: it validates the compatibility
matrix, every package manifest and published-file allowlist.  ``--profile-smoke``
adds all packed local tarballs to a fresh temporary DSH home and checks the
composed configuration.  It never loads ``.env`` or starts a provider-backed
agent turn.
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
    if args.profile_smoke:
        _profile_smoke(compatibility, manifest, timeout_seconds=args.timeout_seconds)
    print(json.dumps({"status": "ok", "bundle_count": len(manifest["packages"]), "profile_smoke": args.profile_smoke}, ensure_ascii=False))
    return 0


def _validate(compatibility: dict[str, Any], manifest: dict[str, Any]) -> None:
    if set(compatibility) != {"schema_version", "dsh", "node", "npm", "bundles", "required_package_files", "invariants"} or compatibility.get("schema_version") != "1.0":
        raise ReleaseGateError("dsh compatibility matrix fields are invalid")
    if not all(isinstance(compatibility.get(key), str) and compatibility[key].strip() for key in ("dsh", "node", "npm")):
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
        for name in required_files:
            if not (package_dir / name).exists():
                raise ReleaseGateError(f"required published file is missing for {entry['package']}: {name}")
        if not (package_dir / "lib" / "index.js").is_file():
            raise ReleaseGateError(f"compiled entry is missing for {entry['package']}")
        patch = (package_dir / "cordis.patch.yml").read_text(encoding="utf-8")
        if f"id: {entry['plugin_id']}" not in patch or f"name: '{entry['package']}'" not in patch or "baseUrl: http://127.0.0.1:" not in patch or "https://" in patch or "http://localhost" in patch:
            raise ReleaseGateError(f"loopback patch contract is invalid for {entry['package']}")


def _profile_smoke(compatibility: dict[str, Any], manifest: dict[str, Any], *, timeout_seconds: int) -> None:
    dsh = shutil.which("dsh")
    npm = shutil.which("npm")
    node = shutil.which("node")
    if not dsh or not npm or not node:
        raise ReleaseGateError("dsh, node, and npm must be available on PATH for profile smoke")
    actual = _command_text([dsh, "--version"])
    if actual != compatibility["dsh"]:
        raise ReleaseGateError(f"DSH version mismatch: expected {compatibility['dsh']}, got {actual}")
    actual_node = _command_text([node, "--version"]).lstrip("v")
    if actual_node != compatibility["node"]:
        raise ReleaseGateError(f"Node version mismatch: expected {compatibility['node']}, got {actual_node}")
    actual_npm = _command_text([npm, "--version"])
    if actual_npm != compatibility["npm"]:
        raise ReleaseGateError(f"npm version mismatch: expected {compatibility['npm']}, got {actual_npm}")
    with tempfile.TemporaryDirectory(prefix="cosmatter-dsh-release-") as directory:
        temporary = Path(directory)
        tarballs: list[str] = []
        for entry in manifest["packages"]:
            package_dir = ROOT / "plugins" / str(entry["path"])
            completed = _run(
                [npm, "pack", "--pack-destination", str(temporary), "--json"], cwd=package_dir,
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
        install = _run([dsh, "plugin", "--profile", profile, "add", *tarballs], cwd=ROOT, env=environment, timeout=timeout_seconds)
        if install.returncode:
            raise ReleaseGateError(f"clean-profile bundle install failed: {install.stderr.strip() or install.stdout.strip()}")
        dump = _run([dsh, "--profile", profile, "--dump-config"], cwd=ROOT, env=environment, timeout=timeout_seconds)
        if dump.returncode:
            raise ReleaseGateError(f"clean-profile config dump failed: {dump.stderr.strip() or dump.stdout.strip()}")
        for entry in manifest["packages"]:
            if f"id: {entry['plugin_id']}" not in dump.stdout:
                raise ReleaseGateError(f"clean profile did not compose {entry['plugin_id']}")


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
