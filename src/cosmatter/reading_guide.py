"""Bounded, provenance-preserving reading routes for reviewed CosMatter runs.

This is deliberately not an LLM summary.  It only orders candidate metadata
already recovered through an approved FlightPlan and marks candidates linked to
accepted evidence.  Query strings, abstracts, full text, raw scores, review
reasons, and upstream API payloads never enter the guide artifact.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .candidate_screening import CandidateScreeningError, selected_document_ids, selected_document_reason_codes
from .metadata_enrichment import MetadataEnrichmentError, resolved_dois_for_candidates
from .models import EvidenceCard, FlightPlan, MissionBrief, ReviewStatus, normalized_doi_or_none
from .verification import VerificationDecision


GUIDE_SCHEMA_VERSION = "1.1"
_LEGACY_GUIDE_SCHEMA_VERSION = "1.0"
_MAX_GUIDE_ITEMS = 12
_ITEM_FIELDS = {
    "order",
    "document_id",
    "title",
    "publication_year",
    "source",
    "locator_hint",
    "track",
    "role",
    "content_status",
    "evidence_ids",
    "doi",
    "routing_signals",
}
_LEGACY_ITEM_FIELDS = _ITEM_FIELDS - {"doi", "routing_signals"}
_GUIDE_FIELDS = {"schema_version", "mission_id", "trust_status", "items", "caveats"}
_ROUTING_SIGNALS = {
    "accepted_evidence", "screened_for_fulltext", "material_match", "property_match", "scope_match",
    "method_match", "primary_evidence", "counterevidence", "counterevidence_track",
    "provider_advertised_content", "normalized_doi_resolved",
}


class ReadingGuideError(ValueError):
    """Raised when a candidate history cannot form a bounded reading route."""


def build_reading_guide(
    mission: MissionBrief,
    plan: FlightPlan,
    candidate_payload: object,
    cards: tuple[EvidenceCard, ...] = (),
    decisions: tuple[VerificationDecision, ...] = (),
    screening: object | None = None,
    metadata_enrichment: object | None = None,
) -> dict[str, Any]:
    """Create a stable study route from approved retrieval provenance.

    Items with accepted, traceable evidence lead the route.  Remaining primary
    and counterevidence candidates retain their distinct provenance tracks.
    """
    if plan.mission_id != mission.mission_id:
        raise ReadingGuideError("approved plan does not belong to mission")
    candidates = _candidates_from_payload(candidate_payload)
    try:
        selected_documents = selected_document_ids(screening, candidate_payload) if screening is not None else frozenset()
        screening_reasons = selected_document_reason_codes(screening, candidate_payload) if screening is not None else {}
    except CandidateScreeningError as error:
        raise ReadingGuideError(str(error)) from error
    try:
        enriched_dois = resolved_dois_for_candidates(metadata_enrichment, mission.mission_id, candidate_payload)
    except MetadataEnrichmentError as error:
        raise ReadingGuideError(str(error)) from error
    accepted_by_document = _accepted_evidence_by_document(mission.mission_id, cards, decisions)
    primary_queries = set(plan.queries)
    counter_queries = set(plan.counter_queries)
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for candidate in candidates:
        document_id = candidate["document_id"]
        if document_id in seen:
            continue
        seen.add(document_id)
        query = candidate["query"]
        if query in primary_queries:
            track = "primary"
        elif query in counter_queries:
            track = "counterevidence"
        else:
            raise ReadingGuideError("candidate history contains a query outside the approved FlightPlan")
        evidence_ids = accepted_by_document.get(document_id, [])
        accessible = candidate["is_content_accessible"]
        doi = candidate["doi"] or enriched_dois.get(document_id)
        role = "verified_evidence" if evidence_ids else ("primary_candidate" if track == "primary" else "counterevidence_candidate")
        routing_signals: list[str] = []
        if evidence_ids:
            routing_signals.append("accepted_evidence")
        if document_id in selected_documents:
            routing_signals.append("screened_for_fulltext")
            routing_signals.extend(screening_reasons.get(document_id, ()))
        if track == "counterevidence":
            routing_signals.append("counterevidence_track")
        if accessible:
            routing_signals.append("provider_advertised_content")
        if doi is not None:
            routing_signals.append("normalized_doi_resolved")
        normalized.append(
            {
                "document_id": document_id,
                "title": candidate["title"],
                "publication_year": candidate["publication_year"],
                "source": candidate["source"],
                "locator_hint": candidate["locator_hint"],
                "track": track,
                "role": role,
                "content_status": "authorized" if accessible else "metadata_only",
                "evidence_ids": evidence_ids,
                "doi": doi,
                "routing_signals": list(dict.fromkeys(routing_signals)),
                "_score": candidate["score"],
                "_selected": document_id in selected_documents,
            }
        )
    if not normalized:
        raise ReadingGuideError("candidate history contains no usable candidates")
    role_rank = {"verified_evidence": 0, "primary_candidate": 1, "counterevidence_candidate": 1}
    normalized.sort(
        key=lambda item: (
            role_rank[item["role"]],
            0 if item["_selected"] else 1,
            0 if item["content_status"] == "authorized" else 1,
            -(item["_score"] if item["_score"] is not None else -1.0),
            item["document_id"],
        )
    )
    routed = _bounded_balanced_route(normalized)
    items = []
    for index, item in enumerate(routed, start=1):
        item.pop("_score")
        item.pop("_selected")
        items.append({"order": index, **item})
    return {
        "schema_version": GUIDE_SCHEMA_VERSION,
        "mission_id": mission.mission_id,
        "trust_status": "derived_from_approved_artifacts",
        "items": items,
        "caveats": [
            "The route orders bounded candidates; it is not a scientific conclusion.",
            "Candidate-screening selections affect routing only and are not accepted scientific evidence.",
            "Metadata-only candidates must not be used for evidence extraction.",
            "Counterevidence items are deliberately retained and are not treated as disproved claims.",
        ],
    }


def _bounded_balanced_route(normalized: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep high-priority items while preventing one retrieval track from starvation."""
    routed = list(normalized[:_MAX_GUIDE_ITEMS])
    available_tracks = {item["track"] for item in normalized}
    for required_track in ("primary", "counterevidence"):
        if required_track not in available_tracks or any(item["track"] == required_track for item in routed):
            continue
        replacement = next(
            (
                item
                for item in reversed(routed)
                if item["role"] != "verified_evidence" and not item["_selected"]
            ),
            None,
        )
        if replacement is None:
            replacement = next((item for item in reversed(routed) if item["role"] != "verified_evidence"), None)
        if replacement is None:
            continue
        routed[routed.index(replacement)] = next(item for item in normalized if item["track"] == required_track)
    routed.sort(key=normalized.index)
    return routed


def write_reading_guide(run_dir: Path, guide: dict[str, Any]) -> Path:
    """Persist a validated route next to its approved run artifacts."""
    _validate_reading_guide(guide)
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "reading_guide.json"
    path.write_text(json.dumps(guide, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def load_reading_guide(path: Path, mission_id: str) -> dict[str, Any] | None:
    """Load an optional guide and return only its browser-safe field contract."""
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ReadingGuideError("reading_guide.json is invalid JSON") from error
    if isinstance(payload, dict) and payload.get("schema_version") == _LEGACY_GUIDE_SCHEMA_VERSION:
        payload = _upgrade_legacy_guide(payload)
    _validate_reading_guide(payload)
    if payload["mission_id"] != mission_id:
        raise ReadingGuideError("reading guide does not belong to mission")
    return payload


def _candidates_from_payload(payload: object) -> list[dict[str, Any]]:
    if not isinstance(payload, dict) or not isinstance(payload.get("candidates"), list):
        raise ReadingGuideError("candidate history must contain a candidates array")
    candidates: list[dict[str, Any]] = []
    for raw in payload["candidates"]:
        if not isinstance(raw, dict):
            raise ReadingGuideError("candidate history contains a non-object candidate")
        document_id, title, query, source = (raw.get(key) for key in ("document_id", "title", "query", "source"))
        if not all(isinstance(value, str) and value.strip() for value in (document_id, title, query, source)):
            raise ReadingGuideError("candidate history contains an invalid candidate identity")
        year = raw.get("publication_year")
        if year is not None and (not isinstance(year, int) or not 1000 <= year <= 3000):
            raise ReadingGuideError("candidate history contains an invalid publication year")
        locator_hint = raw.get("locator_hint")
        if locator_hint is not None and not isinstance(locator_hint, str):
            raise ReadingGuideError("candidate history contains an invalid locator hint")
        score = raw.get("score")
        if score is not None and not isinstance(score, (int, float)):
            raise ReadingGuideError("candidate history contains an invalid score")
        candidates.append(
            {
                "document_id": document_id.strip(),
                "title": title.strip(),
                "query": query.strip(),
                "source": source.strip(),
                "publication_year": year,
                "locator_hint": locator_hint,
                "score": float(score) if score is not None else None,
                "is_content_accessible": raw.get("is_content_accessible") is True,
                "doi": normalized_doi_or_none(raw.get("doi")),
            }
        )
    return candidates


def _accepted_evidence_by_document(
    mission_id: str,
    cards: tuple[EvidenceCard, ...],
    decisions: tuple[VerificationDecision, ...],
) -> dict[str, list[str]]:
    accepted = {
        decision.evidence_id
        for decision in decisions
        if decision.mission_id == mission_id and decision.status is ReviewStatus.ACCEPTED
    }
    result: dict[str, list[str]] = {}
    for card in cards:
        if card.evidence_id in accepted:
            result.setdefault(card.provenance.document_id, []).append(card.evidence_id)
    return result


def _validate_reading_guide(payload: object) -> None:
    if not isinstance(payload, dict) or set(payload) != _GUIDE_FIELDS:
        raise ReadingGuideError("reading guide has unsupported or missing fields")
    if payload.get("schema_version") != GUIDE_SCHEMA_VERSION:
        raise ReadingGuideError("reading guide has an unsupported schema version")
    if payload.get("trust_status") != "derived_from_approved_artifacts":
        raise ReadingGuideError("reading guide trust status is invalid")
    if not isinstance(payload.get("mission_id"), str) or not payload["mission_id"].strip():
        raise ReadingGuideError("reading guide mission_id is invalid")
    items = payload.get("items")
    caveats = payload.get("caveats")
    if not isinstance(items, list) or not 1 <= len(items) <= _MAX_GUIDE_ITEMS or not isinstance(caveats, list):
        raise ReadingGuideError("reading guide items or caveats are invalid")
    document_ids: set[str] = set()
    for expected_order, item in enumerate(items, start=1):
        if not isinstance(item, dict) or set(item) != _ITEM_FIELDS or item.get("order") != expected_order:
            raise ReadingGuideError("reading guide item fields or order are invalid")
        if not all(isinstance(item[key], str) and item[key].strip() for key in ("document_id", "title", "source", "track", "role", "content_status")):
            raise ReadingGuideError("reading guide item string fields are invalid")
        if item["document_id"] in document_ids:
            raise ReadingGuideError("reading guide document IDs must be unique")
        document_ids.add(item["document_id"])
        if item["track"] not in {"primary", "counterevidence"} or item["role"] not in {"verified_evidence", "primary_candidate", "counterevidence_candidate"}:
            raise ReadingGuideError("reading guide item roles are invalid")
        if item["content_status"] not in {"authorized", "metadata_only"}:
            raise ReadingGuideError("reading guide item content status is invalid")
        if item["doi"] is not None and normalized_doi_or_none(item["doi"]) != item["doi"]:
            raise ReadingGuideError("reading guide item DOI is invalid")
        signals = item["routing_signals"]
        if not isinstance(signals, list) or len(signals) != len(set(signals)) or any(signal not in _ROUTING_SIGNALS for signal in signals):
            raise ReadingGuideError("reading guide routing signals are invalid")
        if item["publication_year"] is not None and (not isinstance(item["publication_year"], int) or not 1000 <= item["publication_year"] <= 3000):
            raise ReadingGuideError("reading guide item year is invalid")
        if item["locator_hint"] is not None and not isinstance(item["locator_hint"], str):
            raise ReadingGuideError("reading guide locator hint is invalid")
        if not isinstance(item["evidence_ids"], list) or not all(isinstance(value, str) and value for value in item["evidence_ids"]):
            raise ReadingGuideError("reading guide evidence IDs are invalid")
    if not all(isinstance(caveat, str) and caveat.strip() for caveat in caveats):
        raise ReadingGuideError("reading guide caveats are invalid")


def _upgrade_legacy_guide(payload: dict[str, Any]) -> dict[str, Any]:
    """Project a previously written v1.0 route into the v1.1 safe contract."""
    if set(payload) != _GUIDE_FIELDS or not isinstance(payload.get("items"), list):
        raise ReadingGuideError("legacy reading guide fields are invalid")
    upgraded_items = []
    for item in payload["items"]:
        if not isinstance(item, dict) or set(item) != _LEGACY_ITEM_FIELDS:
            raise ReadingGuideError("legacy reading guide item fields are invalid")
        signals = []
        if item.get("role") == "verified_evidence":
            signals.append("accepted_evidence")
        if item.get("track") == "counterevidence":
            signals.append("counterevidence_track")
        if item.get("content_status") == "authorized":
            signals.append("provider_advertised_content")
        upgraded_items.append({**item, "doi": None, "routing_signals": signals})
    return {**payload, "schema_version": GUIDE_SCHEMA_VERSION, "items": upgraded_items}
