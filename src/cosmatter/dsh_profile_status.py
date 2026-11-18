"""Redacted, read-only bundle installation status for the local DSH profile."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any


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


def dsh_profile_status(profile_name: str = "tui", *, dsh_home: Path | None = None) -> dict[str, Any]:
    """Check declared bundles and their fixed installation files without loading them."""
    if not isinstance(profile_name, str) or not _PROFILE_NAME.fullmatch(profile_name):
        raise ValueError("DSH profile name is invalid")
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
    return {
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
