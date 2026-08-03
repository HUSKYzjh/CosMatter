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

from .models import EvidenceCard, FlightPlan, MissionBrief, ReviewStatus
from .verification import VerificationDecision


GUIDE_SCHEMA_VERSION = "1.0"
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
}
_GUIDE_FIELDS = {"schema_version", "mission_id", "trust_status", "items", "caveats"}


class ReadingGuideError(ValueError):
    """Raised when a candidate history cannot form a bounded reading route."""


def build_reading_guide(
    mission: MissionBrief,
    plan: FlightPlan,
    candidate_payload: object,
    cards: tuple[EvidenceCard, ...] = (),
    decisions: tuple[VerificationDecision, ...] = (),
) -> dict[str, Any]:
    """Create a stable study route from approved retrieval provenance.

    Items with accepted, traceable evidence lead the route.  Remaining primary
    and counterevidence candidates retain their distinct provenance tracks.
    """
    if plan.mission_id != mission.mission_id:
        raise ReadingGuideError("approved plan does not belong to mission")
    candidates = _candidates_from_payload(candidate_payload)
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
        role = "verified_evidence" if evidence_ids else ("primary_candidate" if track == "primary" else "counterevidence_candidate")
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
                "_score": candidate["score"],
            }
        )
    if not normalized:
        raise ReadingGuideError("candidate history contains no usable candidates")
    role_rank = {"verified_evidence": 0, "primary_candidate": 1, "counterevidence_candidate": 2}
    normalized.sort(
        key=lambda item: (
            role_rank[item["role"]],
            0 if item["content_status"] == "authorized" else 1,
            -(item["_score"] if item["_score"] is not None else -1.0),
            item["document_id"],
        )
    )
    items = []
    for index, item in enumerate(normalized[:_MAX_GUIDE_ITEMS], start=1):
        item.pop("_score")
        items.append({"order": index, **item})
    return {
        "schema_version": GUIDE_SCHEMA_VERSION,
        "mission_id": mission.mission_id,
        "trust_status": "derived_from_approved_artifacts",
        "items": items,
        "caveats": [
            "The route orders bounded candidates; it is not a scientific conclusion.",
            "Metadata-only candidates must not be used for evidence extraction.",
            "Counterevidence items are deliberately retained and are not treated as disproved claims.",
        ],
    }


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
        if item["publication_year"] is not None and (not isinstance(item["publication_year"], int) or not 1000 <= item["publication_year"] <= 3000):
            raise ReadingGuideError("reading guide item year is invalid")
        if item["locator_hint"] is not None and not isinstance(item["locator_hint"], str):
            raise ReadingGuideError("reading guide locator hint is invalid")
        if not isinstance(item["evidence_ids"], list) or not all(isinstance(value, str) and value for value in item["evidence_ids"]):
            raise ReadingGuideError("reading guide evidence IDs are invalid")
    if not all(isinstance(caveat, str) and caveat.strip() for caveat in caveats):
        raise ReadingGuideError("reading guide caveats are invalid")
