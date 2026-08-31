"""Human-reviewed identity reconciliation between bounded relation sources."""

from __future__ import annotations

import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "1.1"
_LEGACY_SCHEMA_VERSION = "1.0"
_STATUSES = {"matched", "conflict", "unresolved"}


class RelationReconciliationError(ValueError):
    pass


def reconciliation_from_review(*, mission_id: str, openalex: dict[str, Any], crossref: dict[str, Any], selection: object) -> dict[str, Any]:
    """Record explicit reviewer mappings; never infer same identity from labels."""
    _validate_relation_artifact(openalex, mission_id, "public_relation_metadata_not_scientific_evidence")
    _validate_relation_artifact(crossref, mission_id, "public_bibliographic_reference_metadata_not_scientific_evidence")
    if openalex["source"]["evidence_id"] != crossref["source"]["evidence_id"] or openalex["source"]["document_id"] != crossref["source"]["document_id"]:
        raise RelationReconciliationError("relation sources must originate from the same accepted evidence")
    if not isinstance(selection, dict) or set(selection) != {"evidence_id", "document_id", "mappings"} or selection.get("evidence_id") != openalex["source"]["evidence_id"] or selection.get("document_id") != openalex["source"]["document_id"]:
        raise RelationReconciliationError("reconciliation selection identity is invalid")
    work_ids = {edge.get("target_openalex_id") for edge in openalex.get("edges", []) if isinstance(edge, dict)}
    dois = {edge.get("target_doi") for edge in crossref.get("edges", []) if isinstance(edge, dict)}
    mappings = _mappings(selection["mappings"], work_ids, dois)
    return {"schema_version": SCHEMA_VERSION, "mission_id": mission_id, "trust_status": "human_reviewed_cross_source_identity_not_scientific_evidence", "source": {"evidence_id": selection["evidence_id"], "document_id": selection["document_id"]}, "mappings": mappings, "revision_history": []}


def write_relation_reconciliation(run_dir: Path, artifact: dict[str, Any]) -> Path:
    if artifact.get("schema_version") == SCHEMA_VERSION and artifact.get("revision_history") == []:
        _validate_artifact({**artifact, "revision_history": [_revision_entry(1, artifact["mappings"])]})
    else:
        _validate_artifact(artifact)
    path = run_dir / "relation_reconciliation.json"
    history: list[dict[str, Any]] = []
    if path.exists():
        existing = load_relation_reconciliation(path, artifact["mission_id"])
        assert existing is not None
        if existing["source"] != artifact["source"]:
            raise RelationReconciliationError("cannot replace reconciliation for a different reviewed source")
        history = list(existing.get("revision_history", []))
        if not history:
            history.append(_revision_entry(1, existing["mappings"]))
    revision = len(history) + 1
    upgraded = {**artifact, "schema_version": SCHEMA_VERSION, "revision_history": [*history, _revision_entry(revision, artifact["mappings"])]}
    _validate_artifact(upgraded)
    path.write_text(json.dumps(upgraded, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def load_relation_reconciliation(path: Path, mission_id: str) -> dict[str, Any] | None:
    if not path.exists(): return None
    try: payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error: raise RelationReconciliationError("relation_reconciliation.json is invalid JSON") from error
    _validate_artifact(payload)
    if payload["mission_id"] != mission_id: raise RelationReconciliationError("reconciliation does not belong to mission")
    return payload
def _mappings(raw: Any, work_ids: set[Any], dois: set[Any]) -> list[dict[str, str]]:
    if not isinstance(raw, list) or len(raw) > 12: raise RelationReconciliationError("mapping list is invalid")
    result: list[dict[str, str]] = []; seen: set[tuple[str, str]] = set()
    for item in raw:
        if not isinstance(item, dict) or set(item) != {"openalex_work_id", "crossref_doi", "status", "basis"}: raise RelationReconciliationError("mapping fields are invalid")
        work, doi, status, basis = (item[key] for key in ("openalex_work_id", "crossref_doi", "status", "basis"))
        if not all(isinstance(value, str) and value.strip() for value in (work, doi, status, basis)) or work not in work_ids or doi not in dois or status not in _STATUSES or len(basis) > 120 or (work, doi) in seen: raise RelationReconciliationError("mapping values are invalid")
        seen.add((work, doi)); result.append({"openalex_work_id": work, "crossref_doi": doi, "status": status, "basis": basis})
    return result


def _revision_entry(revision: int, mappings: list[dict[str, str]]) -> dict[str, Any]:
    canonical = json.dumps(mappings, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    counts = {status: sum(mapping["status"] == status for mapping in mappings) for status in sorted(_STATUSES)}
    return {
        "revision": revision,
        "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "mapping_count": len(mappings),
        "status_counts": counts,
        "mappings_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    }


def _validate_relation_artifact(payload: Any, mission_id: str, trust_status: str) -> None:
    if not isinstance(payload, dict) or payload.get("mission_id") != mission_id or payload.get("trust_status") != trust_status or not isinstance(payload.get("source"), dict) or not isinstance(payload.get("edges"), list): raise RelationReconciliationError("bounded relation artifact is invalid")


def _validate_artifact(payload: Any) -> None:
    if not isinstance(payload, dict) or payload.get("schema_version") not in {_LEGACY_SCHEMA_VERSION, SCHEMA_VERSION} or payload.get("trust_status") != "human_reviewed_cross_source_identity_not_scientific_evidence" or not isinstance(payload.get("mission_id"), str) or not isinstance(payload.get("source"), dict) or set(payload["source"]) != {"evidence_id", "document_id"}: raise RelationReconciliationError("reconciliation artifact is invalid")
    expected = {"schema_version", "mission_id", "trust_status", "source", "mappings"}
    if payload["schema_version"] == SCHEMA_VERSION:
        expected.add("revision_history")
    if set(payload) != expected: raise RelationReconciliationError("reconciliation artifact is invalid")
    _mappings(payload["mappings"], {mapping.get("openalex_work_id") for mapping in payload["mappings"] if isinstance(mapping, dict)}, {mapping.get("crossref_doi") for mapping in payload["mappings"] if isinstance(mapping, dict)})
    if payload["schema_version"] == SCHEMA_VERSION:
        _revision_history(payload["revision_history"], payload["mappings"])


def _revision_history(raw: Any, mappings: list[dict[str, str]]) -> None:
    if not isinstance(raw, list) or not raw or len(raw) > 48:
        raise RelationReconciliationError("reconciliation revision history is invalid")
    expected_fields = {"revision", "recorded_at", "mapping_count", "status_counts", "mappings_sha256"}
    for index, entry in enumerate(raw, start=1):
        if not isinstance(entry, dict) or set(entry) != expected_fields or entry.get("revision") != index or not isinstance(entry.get("recorded_at"), str) or not _timestamp(entry["recorded_at"]) or not isinstance(entry.get("mapping_count"), int) or entry["mapping_count"] < 0 or not isinstance(entry.get("status_counts"), dict) or set(entry["status_counts"]) != _STATUSES or any(not isinstance(entry["status_counts"][status], int) or entry["status_counts"][status] < 0 for status in _STATUSES) or sum(entry["status_counts"].values()) != entry["mapping_count"] or not _sha256(entry.get("mappings_sha256")):
            raise RelationReconciliationError("reconciliation revision history is invalid")
    latest = raw[-1]
    if latest["mapping_count"] != len(mappings) or latest["status_counts"] != {status: sum(mapping["status"] == status for mapping in mappings) for status in sorted(_STATUSES)} or latest["mappings_sha256"] != hashlib.sha256(json.dumps(mappings, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest():
        raise RelationReconciliationError("reconciliation revision history does not match current mappings")


def _timestamp(value: str) -> bool:
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return value.endswith("Z") and len(value) == 20


def _sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(character in "0123456789abcdef" for character in value)
