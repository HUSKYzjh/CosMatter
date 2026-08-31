"""Versioned, allowlisted continuation packages for local CosMatter runs."""

from __future__ import annotations

import hashlib
import json
import math
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

from .workflow_readiness import WorkflowReadinessError, continuation_next_stage
from .evidence_maturity_registry import EvidenceMaturityRegistryError, validate_evidence_maturity_registry, validate_evidence_maturity_registry_audit
from .models import FacilityType, FleetAssignment, FleetType, StationType


SCHEMA_VERSION = "1.0"
PACKAGE_TYPE = "cosmatter_run"
_ARTIFACTS = (
    "mission.json", "fleet_assignment.json", "automatic_execution_plan.json",
    "workflow_readiness.json", "citation_expansion.json", "retrieval_candidates.json",
    "verification_decisions.json", "research_gap_candidates.json",
    "evidence_maturity_registry.json", "evidence_maturity_registry_audit.json",
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
    if "fleet_assignment.json" in artifacts:
        try:
            assignment = _fleet_assignment(artifacts["fleet_assignment.json"])
            if assignment.mission_id != mission["mission_id"]:
                raise ValueError("mission mismatch")
        except (KeyError, TypeError, ValueError) as error:
            raise RunPackageError("run package fleet assignment is invalid") from error
    registry_present = "evidence_maturity_registry.json" in artifacts
    maturity_audit_present = "evidence_maturity_registry_audit.json" in artifacts
    if registry_present != maturity_audit_present:
        raise RunPackageError("run package evidence maturity registry artifacts are incomplete")
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
    if registry_present:
        registry = artifacts["evidence_maturity_registry.json"]
        audit = artifacts["evidence_maturity_registry_audit.json"]
        try:
            validate_evidence_maturity_registry(registry)
            if registry["question_id"] != mission["mission_id"]:
                raise EvidenceMaturityRegistryError("evidence maturity registry question does not match mission")
            validate_evidence_maturity_registry_audit(audit, registry)
            if audit["passed"] is not True:
                raise EvidenceMaturityRegistryError("evidence maturity registry audit did not pass")
        except EvidenceMaturityRegistryError as error:
            raise RunPackageError("run package evidence maturity registry is invalid") from error
    return payload


def restore_run_package(runs_dir: Path, run_id: str, payload: object) -> Path:
    package = validate_run_package(payload)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", run_id):
        raise RunPackageError("restore run_id is invalid")
    destination = runs_dir / run_id
    if destination.exists():
        raise RunPackageError("restore run_id already exists")
    runs_dir.mkdir(parents=True, exist_ok=True)
    try:
        staging = Path(tempfile.mkdtemp(prefix=f".{run_id}.restore-", dir=runs_dir))
    except OSError as error:
        raise RunPackageError("could not prepare run package restore") from error
    try:
        for name, artifact in package["artifacts"].items():
            (staging / name).write_text(json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if "mission.json" not in package["artifacts"]:
            (staging / "mission.json").write_text(json.dumps(package["mission"], ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if destination.exists():
            raise RunPackageError("restore run_id already exists")
        staging.rename(destination)
    except (OSError, RunPackageError) as error:
        shutil.rmtree(staging, ignore_errors=True)
        if isinstance(error, RunPackageError):
            raise
        raise RunPackageError("could not restore run package") from error
    return destination


def _canonical_sha256(value: Any) -> str:
    canonical = (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _fleet_assignment(value: object) -> FleetAssignment:
    if not isinstance(value, dict):
        raise ValueError("fleet assignment is not an object")
    return FleetAssignment(
        mission_id=str(value["mission_id"]),
        fleet_type=FleetType(str(value["fleet_type"])),
        mission_type=str(value["mission_type"]),
        reason=str(value["reason"]),
        required_stations=tuple(StationType(str(item)) for item in value["required_stations"]),
        required_facilities=tuple(FacilityType(str(item)) for item in value["required_facilities"]),
        release_gate=StationType(str(value["release_gate"])),
        assignment_id=str(value.get("assignment_id", "assignment_restored")),
        created_at=str(value.get("created_at", "1970-01-01T00:00:00+00:00")),
    )

def _load(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RunPackageError(f"package artifact {path.name} is invalid") from error


def _assert_safe(value: Any) -> None:
    """Reject secrets, locators, and non-JSON values before a package is restored."""
    forbidden_markers = (
        "api_key", "authorization", "bearer ", "cookie:", "private_markdown", "full.md", "input.pdf", "request_headers",
        "https://", "http://", "file://", "ssh://", "c:\\users\\", "c:/users/", "/home/", "/users/",
    )
    forbidden_keys = {
        "apikey", "authorization", "authorizationheader", "bearertoken", "cookie", "cookies", "password",
        "accesstoken", "refreshtoken", "requestheaders", "privatemarkdown", "privatepath", "sourceurl",
        "downloadurl", "fulltext", "inputpdf", "inputpath",
    }

    def visit(item: Any) -> None:
        if item is None or isinstance(item, (bool, int)):
            return
        if isinstance(item, float):
            if math.isfinite(item):
                return
            raise RunPackageError("run package contains a non-JSON value")
        if isinstance(item, str):
            lowered = item.casefold()
            if any(marker in lowered for marker in forbidden_markers) or re.search(r"[a-z]:[\\/]", lowered):
                raise RunPackageError("run package contains a private or secret field")
            return
        if isinstance(item, list):
            for child in item:
                visit(child)
            return
        if isinstance(item, dict):
            for key, child in item.items():
                if not isinstance(key, str):
                    raise RunPackageError("run package contains a non-JSON value")
                normalized = re.sub(r"[^a-z0-9]", "", key.casefold())
                if normalized in forbidden_keys:
                    raise RunPackageError("run package contains a private or secret field")
                visit(key)
                visit(child)
            return
        raise RunPackageError("run package contains a non-JSON value")

    visit(value)
