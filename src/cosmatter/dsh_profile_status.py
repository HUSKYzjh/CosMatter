"""Redacted, read-only bundle installation status for the local DSH profile."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
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
_COMPOSITION_RECEIPT = ".cosmatter-composition-check.json"
_COMPOSITION_SCHEMA = "cosmatter.dsh-composition-check/v1"
_MAX_CONFIG_BYTES = 1_000_000
_DSH_VERSION = re.compile(r"[0-9]{1,4}\.[0-9]{1,4}\.[0-9]{1,4}(?:-[a-z0-9.]{1,24})?")


class DshCompositionCheckError(RuntimeError):
    """An explicit local check could not produce a trustworthy receipt."""


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
    return snapshot


def check_dsh_composition(*, executable: str = "dsh", dsh_home: Path | None = None) -> dict[str, Any]:
    """Run the fixed TUI composition diagnostic and save only its redacted result."""
    dsh = shutil.which(executable)
    if not dsh:
        raise DshCompositionCheckError("DSH executable not found. Set PATH or pass --dsh-executable.")
    home = (dsh_home or _default_dsh_home()).resolve()
    profile = home / "profiles" / "tui"
    if not (profile / "package.json").is_file():
        raise DshCompositionCheckError("The local tui profile manifest is missing.")
    environment = {**os.environ, "DSH_HOME": str(home)}
    try:
        stamp = _configuration_stamp(profile)
        with tempfile.TemporaryDirectory(prefix="cosmatter-dsh-composition-") as temporary:
            version = _run_dsh_diagnostic(dsh, ["--version"], temporary, environment).strip()
            if not _DSH_VERSION.fullmatch(version):
                raise DshCompositionCheckError("DSH returned an unsupported version string.")
            config = _run_dsh_diagnostic(dsh, ["--profile", "tui", "--dump-config"], temporary, environment)
        if stamp != _configuration_stamp(profile):
            raise DshCompositionCheckError("The local profile changed during the check. Run it again.")
        composed = _composed_packages(config)
        check = {
            "schema_version": _COMPOSITION_SCHEMA,
            "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "dsh_version": version,
            "bundles": composed,
        }
        _write_composition_receipt(profile, {**check, "configuration_stamp": stamp})
    except (OSError, UnicodeError, subprocess.TimeoutExpired) as exc:
        raise DshCompositionCheckError("DSH composition check timed out or could not complete locally.") from exc
    return {**check, "matches_local_files": True}


def _run_dsh_diagnostic(dsh: str, arguments: list[str], cwd: str, environment: dict[str, str]) -> str:
    result = subprocess.run(
        [dsh, *arguments], cwd=cwd, env=environment, stdin=subprocess.DEVNULL,
        capture_output=True, timeout=20, check=False,
    )
    if result.returncode or len(result.stdout) > _MAX_CONFIG_BYTES:
        raise DshCompositionCheckError("DSH could not produce a valid local configuration snapshot.")
    return result.stdout.decode("utf-8")


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
    # DSH rewrites cordis.yml with identical content during a dump. Compare its
    # bounded content digest, and track the other principal inputs by metadata.
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
    digest = _profile_config_digest(profile)
    return hashlib.sha256(json.dumps([digest, metadata]).encode("ascii")).hexdigest()


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


def _write_composition_receipt(profile: Path, payload: dict[str, Any]) -> None:
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=profile, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            json.dump(payload, stream)
            stream.close()
            temporary.replace(profile / _COMPOSITION_RECEIPT)
        finally:
            temporary.unlink(missing_ok=True)


def _read_composition_check(profile: Path) -> dict[str, Any] | None:
    try:
        root = profile.resolve()
        path = (root / _COMPOSITION_RECEIPT).resolve(strict=True)
        if not path.is_relative_to(root) or not path.is_file():
            return None
        with path.open("rb") as stream:
            data = stream.read(2049)
        if len(data) > 2048:
            return None
        payload = json.loads(data)
        if not isinstance(payload, dict) or set(payload) != {"schema_version", "checked_at", "dsh_version", "bundles", "configuration_stamp"}:
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
