"""Redacted, read-only dependency status for the fixed local DSH profile."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any


DSH_PROFILE_STATUS_SCHEMA = "cosmatter.dsh-profile-status/v1"
DSH_PROFILE_STATUS_TRUST = "local_dependency_snapshot_not_profile_boot_or_plugin_execution"
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


def dsh_profile_status(profile_name: str = "tui", *, dsh_home: Path | None = None) -> dict[str, Any]:
    """Return package-name presence only; never expose dependency values or paths.

    A dependency snapshot proves that the profile references the expected local
    bundles.  It deliberately does not invoke ``dsh``, compose the profile, read
    plugin configuration, inspect environment values, or claim tool execution.
    """
    if not isinstance(profile_name, str) or not _PROFILE_NAME.fullmatch(profile_name):
        raise ValueError("DSH profile name is invalid")
    home = (dsh_home or _default_dsh_home()).resolve()
    package_file = home / "profiles" / profile_name / "package.json"
    dependencies: dict[str, object] = {}
    snapshot_state = "not_installed"
    if package_file.is_file():
        try:
            if package_file.stat().st_size > 128_000:
                raise ValueError("DSH profile package manifest is too large")
            payload = json.loads(package_file.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("DSH profile package manifest is invalid")
            raw_dependencies = payload.get("dependencies")
            if raw_dependencies is not None and not isinstance(raw_dependencies, dict):
                raise ValueError("DSH profile dependencies are invalid")
            dependencies = raw_dependencies or {}
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
            snapshot_state = "unavailable"
            dependencies = {}

    packages = []
    for package_name in EXPECTED_DSH_PACKAGES:
        raw_reference = dependencies.get(package_name)
        installed = isinstance(raw_reference, str) and 0 < len(raw_reference) <= 500
        packages.append({
            "package": package_name,
            "installed": installed,
            "dependency_kind": _dependency_kind(raw_reference) if installed else "absent",
        })
    installed_count = sum(1 for item in packages if item["installed"])
    if snapshot_state != "unavailable":
        snapshot_state = "installed" if installed_count == len(packages) else "partial" if installed_count else "not_installed"
    return {
        "schema_version": DSH_PROFILE_STATUS_SCHEMA,
        "profile_name": profile_name,
        "installation_state": snapshot_state,
        "expected_bundle_count": len(packages),
        "installed_bundle_count": installed_count,
        "packages": packages,
        "composition_status": "not_checked_by_http_api",
        "trust_status": DSH_PROFILE_STATUS_TRUST,
    }


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
