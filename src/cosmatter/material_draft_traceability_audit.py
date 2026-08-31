"""Count-only traceability checks for untrusted material-fact draft candidates.

This audit deliberately cannot accept a scientific fact.  It helps a reviewer
identify whether a model candidate is mechanically linked to a selected source
map excerpt before they make the separate, required scientific judgment.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


class MaterialDraftTraceabilityAuditError(ValueError):
    """Raised when a candidate preview cannot be checked against its source map."""


_CATEGORIES = {"composition", "structure", "property", "processing", "experimental_condition", "simulation_method"}
_CANDIDATE_FIELDS = {"schema_version", "mission_id", "trust_status", "document_id", "facts"}
_FACT_FIELDS = {"fact_id", "segment_id", "category", "name", "value", "unit", "normalized_value", "normalized_unit", "qualifiers", "locator", "source_quote_sha256"}


def audit_untrusted_material_draft(*, mission_id: str, source_map: object, candidates: object) -> dict[str, Any]:
    """Return aggregate, non-scientific traceability results for one candidate draft."""
    segments, document_id = _source_segments(source_map, mission_id)
    if not isinstance(candidates, dict) or set(candidates) != _CANDIDATE_FIELDS:
        raise MaterialDraftTraceabilityAuditError("material candidate preview has unsupported or missing fields")
    if candidates.get("mission_id") != mission_id or candidates.get("document_id") != document_id:
        raise MaterialDraftTraceabilityAuditError("material candidate preview does not match the source map")
    if candidates.get("trust_status") != "untrusted_llm_structured_material_fact_candidates_not_evidence":
        raise MaterialDraftTraceabilityAuditError("material candidate preview is not explicitly untrusted")
    facts = candidates.get("facts")
    if not isinstance(facts, list) or not facts:
        raise MaterialDraftTraceabilityAuditError("material candidate preview has no facts to audit")

    source_linked = allowed_category = reported_value = normalized_value = 0
    for fact in facts:
        if not isinstance(fact, dict) or set(fact) != _FACT_FIELDS:
            raise MaterialDraftTraceabilityAuditError("material candidate fact has unsupported or missing fields")
        segment = segments.get(fact.get("segment_id"))
        linked = (
            segment is not None
            and fact.get("locator") == segment["locator"]
            and fact.get("source_quote_sha256") == segment["quote_sha256"]
        )
        if linked:
            source_linked += 1
        if fact.get("category") in _CATEGORIES:
            allowed_category += 1
        quote = segment["quote"] if linked else ""
        if _appears_in_quote(fact.get("value"), quote):
            reported_value += 1
        if fact.get("normalized_value") == fact.get("value") or _appears_in_quote(fact.get("normalized_value"), quote):
            normalized_value += 1

    return {
        "schema_version": "1.0",
        "mission_id": mission_id,
        "trust_status": "automated_non_scientific_material_draft_traceability_audit",
        "document_id": document_id,
        "candidate_preview_sha256": _digest(candidates),
        "source_map_sha256": _digest(source_map),
        "candidate_fact_count": len(facts),
        "source_linked_fact_count": source_linked,
        "allowed_category_fact_count": allowed_category,
        "reported_value_verbatim_fact_count": reported_value,
        "normalized_value_verbatim_or_unchanged_fact_count": normalized_value,
        "automatically_accepted_fact_count": 0,
        "review_gate": "requires_human_scientific_review",
    }


def write_material_draft_traceability_audit(run_dir: Path, audit: dict[str, Any]) -> Path:
    """Persist only aggregate audit fields in the run; no excerpts or candidate values."""
    required = {
        "schema_version", "mission_id", "trust_status", "document_id", "candidate_preview_sha256", "source_map_sha256",
        "candidate_fact_count", "source_linked_fact_count", "allowed_category_fact_count", "reported_value_verbatim_fact_count",
        "normalized_value_verbatim_or_unchanged_fact_count", "automatically_accepted_fact_count", "review_gate",
    }
    if not isinstance(audit, dict) or set(audit) != required or audit.get("trust_status") != "automated_non_scientific_material_draft_traceability_audit":
        raise MaterialDraftTraceabilityAuditError("material draft traceability audit is invalid")
    path = run_dir / "material_draft_traceability_audit.json"
    path.write_text(json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _source_segments(source_map: object, mission_id: str) -> tuple[dict[str, dict[str, str]], str]:
    if not isinstance(source_map, dict) or source_map.get("mission_id") != mission_id or not isinstance(source_map.get("document_id"), str) or not source_map["document_id"].strip() or not isinstance(source_map.get("segments"), list):
        raise MaterialDraftTraceabilityAuditError("reviewed source map is invalid")
    result: dict[str, dict[str, str]] = {}
    for item in source_map["segments"]:
        if not isinstance(item, dict) or not all(isinstance(item.get(key), str) and item[key] for key in ("segment_id", "locator", "quote", "quote_sha256")):
            raise MaterialDraftTraceabilityAuditError("reviewed source-map segment is invalid")
        if item["segment_id"] in result or hashlib.sha256(item["quote"].encode("utf-8")).hexdigest() != item["quote_sha256"]:
            raise MaterialDraftTraceabilityAuditError("reviewed source-map segment fingerprint is invalid")
        result[item["segment_id"]] = {key: item[key] for key in ("locator", "quote", "quote_sha256")}
    if not result:
        raise MaterialDraftTraceabilityAuditError("reviewed source map has no segments")
    return result, source_map["document_id"]


def _appears_in_quote(value: object, quote: str) -> bool:
    if value is None:
        return True
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        return False
    normalized = re.sub(r"\s+", " ", str(value)).strip().casefold()
    return bool(normalized) and normalized in re.sub(r"\s+", " ", quote).casefold()


def _digest(payload: object) -> str:
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
