"""Strict, dependency-free validation for the evidence-maturity registry."""

from __future__ import annotations

import json
import hashlib
import re
from pathlib import Path
from typing import Any

from .source_map import SourceMapError, load_source_map_for_document

SCHEMA_VERSION = "cosmatter.evidence-maturity-registry/v1"
_ROOT_FIELDS = {"schema_version", "registry_id", "question_id", "trust_status", "claims"}
_CLAIM_FIELDS = {"claim_id", "claim_text", "maturity_level", "assessment_authority", "support_records", "reproducibility", "independent_reproduction", "limitations"}
_SUPPORT_FIELDS = {"run_id", "document_id", "document_version", "independence_group", "source_map_status", "data_status", "conditions_status", "stance"}
_REPRO_FIELDS = {"protocol_status", "materials_status", "measurement_status", "raw_data_status", "assessment"}
_REPRODUCTION_FIELDS = {"status", "independent_run_id", "result_comparison", "review_status"}
_TRUST = {"blank_human_evidence_maturity_registry_template_not_evidence", "delegated_automated_trial_evidence_maturity_registry_not_scientific_evidence", "human_reviewed_evidence_maturity_registry_not_scientific_conclusion"}
_LEVELS = {"literature_mentioned", "data_supported", "reproducibility_ready", "independently_reproduced"}
_AUTHORITIES = {"unreviewed", "delegated_automated_trial", "human_source_review", "human_data_review", "human_reproducibility_review", "independent_reproduction_review"}
_RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,119}\Z")
_AUDIT_SCHEMA_VERSION = "cosmatter.evidence-maturity-registry-audit/v2"
_AUDIT_TRUST_STATUS = "evidence_maturity_registry_link_audit_not_scientific_evidence"
_AUDIT_FIELDS = {"schema_version", "trust_status", "registry_id", "question_id", "registry_sha256", "claim_count", "support_record_count", "controlled_source_map_count", "context_only_count", "link_error_count", "passed"}


class EvidenceMaturityRegistryError(ValueError):
    """Raised when a registry could overstate an evidence or reproduction claim."""


def load_evidence_maturity_registry(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise EvidenceMaturityRegistryError("evidence maturity registry is unavailable") from error
    except json.JSONDecodeError as error:
        raise EvidenceMaturityRegistryError("evidence maturity registry is not valid JSON") from error
    validate_evidence_maturity_registry(value)
    return value


def write_evidence_maturity_registry(path: Path, value: object) -> Path:
    """Write one reviewed registry only after strict local validation."""
    validate_evidence_maturity_registry(value)
    if path.exists():
        raise EvidenceMaturityRegistryError("evidence maturity registry already exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def evidence_maturity_registry_sha256(value: object) -> str:
    validate_evidence_maturity_registry(value)
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def validate_evidence_maturity_registry(value: object) -> None:
    if not isinstance(value, dict) or set(value) != _ROOT_FIELDS or value.get("schema_version") != SCHEMA_VERSION or value.get("trust_status") not in _TRUST:
        raise EvidenceMaturityRegistryError("evidence maturity registry identity is invalid")
    if not _short_text(value.get("registry_id"), 120) or not _short_text(value.get("question_id"), 120):
        raise EvidenceMaturityRegistryError("evidence maturity registry identifiers are invalid")
    claims = value.get("claims")
    if not isinstance(claims, list) or not 1 <= len(claims) <= 500:
        raise EvidenceMaturityRegistryError("evidence maturity registry claims are invalid")
    seen: set[str] = set()
    for claim in claims:
        _validate_claim(claim)
        claim_id = claim["claim_id"]
        if claim_id in seen:
            raise EvidenceMaturityRegistryError("evidence maturity registry claim IDs must be unique")
        seen.add(claim_id)
    _validate_registry_trust_boundary(value["trust_status"], claims)


def audit_evidence_maturity_registry_against_runs(value: object, runs_root: Path) -> dict[str, Any]:
    """Check that registry references match candidates and source-map trust states.

    The result deliberately contains counts and stable identifiers only; it never
    returns excerpts, URLs, credentials, or private parser output.
    """
    validate_evidence_maturity_registry(value)
    if not isinstance(runs_root, Path) or not runs_root.is_dir():
        raise EvidenceMaturityRegistryError("evidence maturity audit runs root is unavailable")
    assert isinstance(value, dict)
    errors: list[str] = []
    support_count = controlled_count = context_only_count = 0
    for claim in value["claims"]:
        for support in claim["support_records"]:
            support_count += 1
            run = runs_root / support["run_id"]
            candidates = _load_json(run / "retrieval_candidates.json")
            items = candidates.get("candidates") if isinstance(candidates, dict) else None
            candidate_ids = {item.get("document_id") for item in items if isinstance(item, dict)} if isinstance(items, list) else set()
            if support["document_id"] not in candidate_ids:
                errors.append(f"candidate_missing:{support['run_id']}:{support['document_id']}")
                continue
            mission = _load_json(run / "mission.json")
            mission_id = mission.get("mission_id") if isinstance(mission, dict) else None
            if not _short_text(mission_id, 200):
                errors.append(f"mission_missing:{support['run_id']}")
                continue
            try:
                source_map = load_source_map_for_document(run, mission_id, support["document_id"])
            except SourceMapError:
                source_map = None
            observed = "none" if source_map is None else ("automated_trial_only" if source_map.get("trust_status") == "delegated_automated_trial_source_map_not_scientific_evidence" else "human_reviewed" if source_map.get("trust_status") == "human_reviewed_parser_selection" else "invalid")
            if observed != support["source_map_status"]:
                errors.append(f"source_map_mismatch:{support['run_id']}:{support['document_id']}")
            elif observed == "automated_trial_only":
                controlled_count += 1
            elif observed == "none":
                context_only_count += 1
    return {
        "schema_version": _AUDIT_SCHEMA_VERSION,
        "trust_status": _AUDIT_TRUST_STATUS,
        "registry_id": value["registry_id"],
        "question_id": value["question_id"],
        "registry_sha256": evidence_maturity_registry_sha256(value),
        "claim_count": len(value["claims"]),
        "support_record_count": support_count,
        "controlled_source_map_count": controlled_count,
        "context_only_count": context_only_count,
        "link_error_count": len(errors),
        "passed": not errors,
    }


def write_evidence_maturity_registry_audit(path: Path, audit: object) -> Path:
    _validate_evidence_maturity_registry_audit_shape(audit)
    if path.exists():
        raise EvidenceMaturityRegistryError("evidence maturity registry audit already exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def validate_evidence_maturity_registry_audit(audit: object, registry: object) -> None:
    """Require a count-only audit to bind exactly to its reviewed registry."""
    validate_evidence_maturity_registry(registry)
    _validate_evidence_maturity_registry_audit_shape(audit)
    assert isinstance(audit, dict) and isinstance(registry, dict)
    if audit["registry_id"] != registry["registry_id"] or audit["question_id"] != registry["question_id"] or audit["registry_sha256"] != evidence_maturity_registry_sha256(registry) or audit["claim_count"] != len(registry["claims"]) or audit["passed"] != (audit["link_error_count"] == 0):
        raise EvidenceMaturityRegistryError("evidence maturity registry audit does not bind the current registry")


def _validate_evidence_maturity_registry_audit_shape(audit: object) -> None:
    if not isinstance(audit, dict) or set(audit) != _AUDIT_FIELDS or audit.get("schema_version") != _AUDIT_SCHEMA_VERSION or audit.get("trust_status") != _AUDIT_TRUST_STATUS or not _short_text(audit.get("registry_id"), 120) or not _short_text(audit.get("question_id"), 120) or not _sha256(audit.get("registry_sha256")) or not all(isinstance(audit.get(key), int) and audit[key] >= 0 for key in ("claim_count", "support_record_count", "controlled_source_map_count", "context_only_count", "link_error_count")) or not isinstance(audit.get("passed"), bool):
        raise EvidenceMaturityRegistryError("evidence maturity registry audit is invalid")


def _validate_claim(value: object) -> None:
    if not isinstance(value, dict) or set(value) != _CLAIM_FIELDS or not _short_text(value.get("claim_id"), 120) or not _safe_public_text(value.get("claim_text"), 1000):
        raise EvidenceMaturityRegistryError("evidence maturity claim fields are invalid")
    level, authority = value.get("maturity_level"), value.get("assessment_authority")
    if level not in _LEVELS or authority not in _AUTHORITIES:
        raise EvidenceMaturityRegistryError("evidence maturity level or authority is invalid")
    if authority == "delegated_automated_trial" and level != "literature_mentioned":
        raise EvidenceMaturityRegistryError("automated trial claims cannot exceed literature-mentioned maturity")
    if authority == "unreviewed" and level != "literature_mentioned":
        raise EvidenceMaturityRegistryError("unreviewed claims cannot exceed literature-mentioned maturity")
    if level == "data_supported" and authority not in {"human_data_review", "human_reproducibility_review", "independent_reproduction_review"}:
        raise EvidenceMaturityRegistryError("data-supported maturity requires human data review")
    _validate_support(value.get("support_records"))
    support_records = value["support_records"]
    assert isinstance(support_records, list)
    if level in {"data_supported", "reproducibility_ready", "independently_reproduced"} and not _has_human_checked_data_support(support_records):
        raise EvidenceMaturityRegistryError("maturity above literature-mentioned requires human-reviewed data and complete conditions")
    _validate_reproducibility(value.get("reproducibility"), level, authority)
    _validate_reproduction(value.get("independent_reproduction"), level, authority, support_records)
    limitations = value.get("limitations")
    if not isinstance(limitations, list) or not limitations or len(limitations) > 30 or not all(_safe_public_text(item, 500) for item in limitations):
        raise EvidenceMaturityRegistryError("evidence maturity claim limitations are invalid")


def _validate_registry_trust_boundary(trust_status: str, claims: list[object]) -> None:
    """Prevent a registry-level trust label from laundering claim-level review states."""
    assert all(isinstance(claim, dict) for claim in claims)
    typed_claims = [claim for claim in claims if isinstance(claim, dict)]
    if trust_status == "delegated_automated_trial_evidence_maturity_registry_not_scientific_evidence":
        for claim in typed_claims:
            if claim["assessment_authority"] != "delegated_automated_trial" or claim["maturity_level"] != "literature_mentioned":
                raise EvidenceMaturityRegistryError("automated trial registry cannot contain human-reviewed or promoted claims")
            if any(
                support["source_map_status"] not in {"none", "automated_trial_only"}
                or support["data_status"] != "not_checked"
                or support["conditions_status"] not in {"not_checked", "partial"}
                for support in claim["support_records"]
            ):
                raise EvidenceMaturityRegistryError("automated trial registry cannot claim human-reviewed source or data states")
            reproducibility = claim["reproducibility"]
            reproduction = claim["independent_reproduction"]
            if any(reproducibility[key] == "complete_human_checked" for key in ("protocol_status", "materials_status", "measurement_status")) or reproducibility["assessment"] == "reproducibility_ready_human_reviewed" or reproduction["status"] not in {"not_attempted", "planned", "in_progress"} or reproduction["result_comparison"] != "not_available" or reproduction["review_status"] == "human_reviewed":
                raise EvidenceMaturityRegistryError("automated trial registry cannot contain human-reviewed reproducibility states")
    elif trust_status == "blank_human_evidence_maturity_registry_template_not_evidence":
        if any(
            claim["assessment_authority"] != "unreviewed"
            or claim["maturity_level"] != "literature_mentioned"
            or any(support["source_map_status"] != "none" or support["data_status"] != "not_checked" or support["conditions_status"] != "not_checked" for support in claim["support_records"])
            for claim in typed_claims
        ):
            raise EvidenceMaturityRegistryError("blank registry template cannot contain reviewed or promoted claims")
    elif any(
        claim["assessment_authority"] in {"unreviewed", "delegated_automated_trial"}
        or any(support["source_map_status"] == "automated_trial_only" for support in claim["support_records"])
        for claim in typed_claims
    ):
        raise EvidenceMaturityRegistryError("human-reviewed registry cannot contain unreviewed or automated-trial claims")


def _validate_support(value: object) -> None:
    if not isinstance(value, list) or not value or len(value) > 50:
        raise EvidenceMaturityRegistryError("evidence maturity support records are invalid")
    for item in value:
        if not isinstance(item, dict) or set(item) != _SUPPORT_FIELDS:
            raise EvidenceMaturityRegistryError("evidence maturity support record fields are invalid")
        if not _run_id(item.get("run_id")) or not all(_short_text(item.get(key), 200) for key in ("document_id", "independence_group")):
            raise EvidenceMaturityRegistryError("evidence maturity support record identity is invalid")
        if item.get("document_version") not in {"publisher_version", "accepted_manuscript", "preprint", "unknown", "publisher_open_access_mirror_version_not_human_verified"} or item.get("source_map_status") not in {"none", "automated_trial_only", "human_reviewed"} or item.get("data_status") not in {"not_checked", "narrative_only", "numeric_or_figure_data_human_checked"} or item.get("conditions_status") not in {"not_checked", "partial", "complete_human_checked"} or item.get("stance") not in {"supports", "contradicts", "mixed", "boundary_counterexample", "context_only"}:
            raise EvidenceMaturityRegistryError("evidence maturity support record status is invalid")


def _validate_reproducibility(value: object, level: str, authority: str) -> None:
    if not isinstance(value, dict) or set(value) != _REPRO_FIELDS:
        raise EvidenceMaturityRegistryError("evidence maturity reproducibility record is invalid")
    if any(value.get(key) not in {"not_checked", "partial", "complete_human_checked"} for key in ("protocol_status", "materials_status", "measurement_status")) or value.get("raw_data_status") not in {"not_checked", "available", "not_available", "not_required"} or value.get("assessment") not in {"not_assessed", "insufficient", "reproducibility_ready_human_reviewed"}:
        raise EvidenceMaturityRegistryError("evidence maturity reproducibility status is invalid")
    if level == "reproducibility_ready" and (authority not in {"human_reproducibility_review", "independent_reproduction_review"} or value["assessment"] != "reproducibility_ready_human_reviewed"):
        raise EvidenceMaturityRegistryError("reproducibility-ready maturity requires human reproducibility review")


def _validate_reproduction(value: object, level: str, authority: str, support_records: list[object]) -> None:
    if not isinstance(value, dict) or set(value) != _REPRODUCTION_FIELDS:
        raise EvidenceMaturityRegistryError("evidence maturity reproduction record is invalid")
    if value.get("status") not in {"not_attempted", "planned", "in_progress", "replicated", "not_replicated", "inconclusive"} or value.get("result_comparison") not in {"not_available", "within_predefined_tolerance", "outside_predefined_tolerance", "inconclusive"} or value.get("review_status") not in {"not_reviewed", "human_reviewed"} or (value.get("independent_run_id") is not None and not _short_text(value.get("independent_run_id"), 160)):
        raise EvidenceMaturityRegistryError("evidence maturity reproduction status is invalid")
    if level == "independently_reproduced" and (authority != "independent_reproduction_review" or value["status"] != "replicated" or value["result_comparison"] != "within_predefined_tolerance" or value["review_status"] != "human_reviewed" or not _short_text(value["independent_run_id"], 160) or value["independent_run_id"] in {item["run_id"] for item in support_records if isinstance(item, dict)}):
        raise EvidenceMaturityRegistryError("independently-reproduced maturity requires a human-reviewed independent run")


def _short_text(value: object, maximum: int) -> bool:
    return isinstance(value, str) and bool(value.strip()) and len(value) <= maximum


def _safe_public_text(value: object, maximum: int) -> bool:
    if not _short_text(value, maximum):
        return False
    assert isinstance(value, str)
    lowered = value.casefold()
    return not any(marker in lowered for marker in ("https://", "http://", "file://", "api_key", "authorization", "bearer ", "c:\\users\\", "/home/"))


def _run_id(value: object) -> bool:
    return isinstance(value, str) and bool(_RUN_ID.fullmatch(value))


def _sha256(value: object) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(r"[0-9a-f]{64}", value))


def _has_human_checked_data_support(records: list[object]) -> bool:
    return any(
        isinstance(record, dict)
        and record.get("source_map_status") == "human_reviewed"
        and record.get("data_status") == "numeric_or_figure_data_human_checked"
        and record.get("conditions_status") == "complete_human_checked"
        and record.get("stance") in {"supports", "contradicts", "mixed"}
        for record in records
    )


def _load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
