"""Versioned, allowlisted continuation packages for local CosMatter runs."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .workflow_readiness import WorkflowReadinessError, continuation_next_stage


SCHEMA_VERSION = "1.0"
PACKAGE_TYPE = "cosmatter_run"
_ARTIFACTS = (
    "mission.json", "fleet_assignment.json", "automatic_execution_plan.json",
    "workflow_readiness.json", "citation_expansion.json", "retrieval_candidates.json",
    "verification_decisions.json", "research_gap_candidates.json",
)


class RunPackageError(ValueError):
    pass


def export_run_package(run_dir: Path) -> dict[str, Any]:
    mission = _load(run_dir / "mission.json")
    artifacts: dict[str, Any] = {}
    digests: dict[str, str] = {}
    for name in _ARTIFACTS:
        path = run_dir / name
        if not path.is_file():
            continue
        payload = _load(path)
        _assert_safe(payload)
        artifacts[name] = payload
        digests[name] = _canonical_sha256(payload)
    package = {"package_type": PACKAGE_TYPE, "schema_version": SCHEMA_VERSION, "mission": mission, "artifacts": artifacts, "artifact_sha256": digests}
    validate_run_package(package)
    return package


def write_run_package(run_dir: Path) -> Path:
    payload = export_run_package(run_dir)
    path = run_dir / f"{run_dir.name}.cosmatter-run.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def validate_run_package(payload: object) -> dict[str, Any]:
    if not isinstance(payload, dict) or set(payload) != {"package_type", "schema_version", "mission", "artifacts", "artifact_sha256"}:
        raise RunPackageError("run package fields are invalid")
    if payload["package_type"] != PACKAGE_TYPE or payload["schema_version"] != SCHEMA_VERSION:
        raise RunPackageError("run package version is unsupported")
    mission = payload["mission"]
    if not isinstance(mission, dict) or not all(isinstance(mission.get(key), str) and mission[key].strip() for key in ("mission_id", "question", "material", "property_name", "scope")):
        raise RunPackageError("run package mission is invalid")
    artifacts, digests = payload["artifacts"], payload["artifact_sha256"]
    if not isinstance(artifacts, dict) or not isinstance(digests, dict) or set(artifacts) != set(digests):
        raise RunPackageError("run package artifact manifest is invalid")
    if "mission.json" in artifacts and artifacts["mission.json"] != mission:
        raise RunPackageError("run package mission does not match mission artifact")
    for name, artifact in artifacts.items():
        if name not in _ARTIFACTS or not isinstance(digests.get(name), str) or not re.fullmatch(r"[a-f0-9]{64}", digests[name]):
            raise RunPackageError("run package artifact is invalid")
        _assert_safe(artifact)
        if digests[name] != _canonical_sha256(artifact):
            raise RunPackageError("run package artifact digest does not match")
        if name == "workflow_readiness.json":
            try:
                continuation_next_stage(artifact, mission["mission_id"])
            except WorkflowReadinessError as error:
                raise RunPackageError("run package workflow readiness is invalid") from error
    return payload


def restore_run_package(runs_dir: Path, run_id: str, payload: object) -> Path:
    package = validate_run_package(payload)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", run_id):
        raise RunPackageError("restore run_id is invalid")
    destination = runs_dir / run_id
    if destination.exists():
        raise RunPackageError("restore run_id already exists")
    destination.mkdir(parents=True)
    for name, artifact in package["artifacts"].items():
        (destination / name).write_text(json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if "mission.json" not in package["artifacts"]:
        (destination / "mission.json").write_text(json.dumps(package["mission"], ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return destination


def _canonical_sha256(value: Any) -> str:
    canonical = (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()

def _load(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RunPackageError(f"package artifact {path.name} is invalid") from error


def _assert_safe(value: Any) -> None:
    raw = json.dumps(value, ensure_ascii=False).lower()
    forbidden = ("api_key", "authorization", "bearer ", "private_markdown", "full.md", "input.pdf", "request_headers")
    if any(item in raw for item in forbidden):
        raise RunPackageError("run package contains a private or secret field")
