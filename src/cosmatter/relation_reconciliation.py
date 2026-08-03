"""Human-reviewed identity reconciliation between bounded relation sources."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "1.0"
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
    return {"schema_version": SCHEMA_VERSION, "mission_id": mission_id, "trust_status": "human_reviewed_cross_source_identity_not_scientific_evidence", "source": {"evidence_id": selection["evidence_id"], "document_id": selection["document_id"]}, "mappings": mappings}


def write_relation_reconciliation(run_dir: Path, artifact: dict[str, Any]) -> Path:
    _validate_artifact(artifact)
    path = run_dir / "relation_reconciliation.json"
    path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
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


def _validate_relation_artifact(payload: Any, mission_id: str, trust_status: str) -> None:
    if not isinstance(payload, dict) or payload.get("mission_id") != mission_id or payload.get("trust_status") != trust_status or not isinstance(payload.get("source"), dict) or not isinstance(payload.get("edges"), list): raise RelationReconciliationError("bounded relation artifact is invalid")


def _validate_artifact(payload: Any) -> None:
    if not isinstance(payload, dict) or set(payload) != {"schema_version", "mission_id", "trust_status", "source", "mappings"} or payload.get("schema_version") != SCHEMA_VERSION or payload.get("trust_status") != "human_reviewed_cross_source_identity_not_scientific_evidence" or not isinstance(payload.get("mission_id"), str) or not isinstance(payload.get("source"), dict) or set(payload["source"]) != {"evidence_id", "document_id"}: raise RelationReconciliationError("reconciliation artifact is invalid")
    _mappings(payload["mappings"], {mapping.get("openalex_work_id") for mapping in payload["mappings"] if isinstance(mapping, dict)}, {mapping.get("crossref_doi") for mapping in payload["mappings"] if isinstance(mapping, dict)})
