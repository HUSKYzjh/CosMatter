"""Static, read-only hygiene signals for a candidate DSH plugin package."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any


class PluginHygieneError(ValueError):
    pass


_SCAN_EXTENSIONS = {".js", ".cjs", ".mjs", ".ts", ".cts", ".mts", ".json", ".yml", ".yaml"}
_SKIP_DIRS = {"node_modules", ".git", "dist", "lib", "coverage"}
_RULES = (
    ("install_lifecycle_script", "high", re.compile(r"\"(?:preinstall|install|postinstall|prepare)\"\s*:")),
    ("dynamic_code_execution", "high", re.compile(r"\b(?:eval|Function)\s*\(")),
    ("process_execution", "high", re.compile(r"\b(?:child_process|execSync|spawnSync|spawn|exec)\b")),
    ("environment_variable_access", "medium", re.compile(r"\b(?:process\.env|Deno\.env)\b")),
    ("network_egress", "medium", re.compile(r"\b(?:fetch|axios|https?\.request|WebSocket)\b")),
    ("credential_reference", "high", re.compile(r"\b(?:api[_-]?key|token|secret|authorization|password)\b", re.IGNORECASE)),
)


def audit_plugin_candidate(candidate_dir: Path) -> dict[str, Any]:
    """Scan bounded candidate sources without executing or disclosing source text."""
    package_path = candidate_dir / "package.json"
    try:
        package = json.loads(package_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PluginHygieneError("candidate package.json is invalid") from error
    name, version = package.get("name"), package.get("version")
    if not isinstance(name, str) or not name.strip() or len(name) > 180 or not isinstance(version, str) or not version.strip() or len(version) > 80:
        raise PluginHygieneError("candidate package identity is invalid")
    files = _candidate_files(candidate_dir)
    findings: list[dict[str, str]] = []
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            raise PluginHygieneError("candidate source cannot be read") from error
        relative = path.relative_to(candidate_dir).as_posix()
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        for category, severity, rule in _RULES:
            if rule.search(text):
                findings.append({"category": category, "severity": severity, "file_sha256": digest})
    deduplicated = sorted({(item["category"], item["severity"], item["file_sha256"]) for item in findings})
    safe_findings = [{"category": category, "severity": severity, "file_sha256": digest} for category, severity, digest in deduplicated]
    counts = {severity: sum(item["severity"] == severity for item in safe_findings) for severity in ("high", "medium")}
    return {
        "schema_version": "1.0",
        "trust_status": "static_plugin_hygiene_signal_not_security_certification_or_install_authorization",
        "candidate_name": name,
        "candidate_version": version,
        "scanned_file_count": len(files),
        "finding_counts": counts,
        "findings": safe_findings,
        "admission_recommendation": "blocked_high_risk" if counts["high"] else "manual_review_required",
    }


def validate_plugin_hygiene_report(payload: object) -> None:
    expected = {"schema_version", "trust_status", "candidate_name", "candidate_version", "scanned_file_count", "finding_counts", "findings", "admission_recommendation"}
    if not isinstance(payload, dict) or set(payload) != expected or payload.get("schema_version") != "1.0" or payload.get("trust_status") != "static_plugin_hygiene_signal_not_security_certification_or_install_authorization" or not isinstance(payload.get("candidate_name"), str) or not isinstance(payload.get("candidate_version"), str) or not isinstance(payload.get("scanned_file_count"), int) or payload["scanned_file_count"] < 1 or payload.get("admission_recommendation") not in {"blocked_high_risk", "manual_review_required"}:
        raise PluginHygieneError("plugin hygiene report is invalid")
    counts, findings = payload.get("finding_counts"), payload.get("findings")
    if not isinstance(counts, dict) or set(counts) != {"high", "medium"} or not all(isinstance(value, int) and value >= 0 for value in counts.values()) or not isinstance(findings, list):
        raise PluginHygieneError("plugin hygiene report is invalid")
    for item in findings:
        if not isinstance(item, dict) or set(item) != {"category", "severity", "file_sha256"} or item.get("severity") not in {"high", "medium"} or not isinstance(item.get("category"), str) or not isinstance(item.get("file_sha256"), str) or not re.fullmatch(r"[a-f0-9]{64}", item["file_sha256"]):
            raise PluginHygieneError("plugin hygiene report finding is invalid")
    if counts["high"] != sum(item["severity"] == "high" for item in findings) or counts["medium"] != sum(item["severity"] == "medium" for item in findings) or (counts["high"] > 0) != (payload["admission_recommendation"] == "blocked_high_risk"):
        raise PluginHygieneError("plugin hygiene report counts are invalid")


def _candidate_files(candidate_dir: Path) -> list[Path]:
    if not candidate_dir.is_dir() or candidate_dir.is_symlink():
        raise PluginHygieneError("candidate directory is invalid")
    files: list[Path] = []
    for path in candidate_dir.rglob("*"):
        if any(part in _SKIP_DIRS for part in path.relative_to(candidate_dir).parts):
            continue
        if path.is_symlink():
            raise PluginHygieneError("candidate package contains a symlink")
        if path.is_file() and path.suffix.lower() in _SCAN_EXTENSIONS:
            if path.stat().st_size > 1_000_000:
                raise PluginHygieneError("candidate source file exceeds scan limit")
            files.append(path)
            if len(files) > 500:
                raise PluginHygieneError("candidate source file count exceeds scan limit")
    if not files or package_path_missing(candidate_dir, files):
        raise PluginHygieneError("candidate source inventory is invalid")
    return sorted(files)


def package_path_missing(candidate_dir: Path, files: list[Path]) -> bool:
    return candidate_dir / "package.json" not in files
