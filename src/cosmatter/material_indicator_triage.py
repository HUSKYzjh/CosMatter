"""Deterministically shortlist private MinerU segments for indicator review.

The result is a private, unreviewed navigation aid.  It deliberately retains
exact source excerpts so a reviewer can inspect values and conditions, but it
is neither a Source Map nor evidence and must stay outside the repository.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any


SHORTLIST_SCHEMA_VERSION = "cosmatter.private-material-indicator-shortlist/v1"
SHORTLIST_TRUST_STATUS = "private_unreviewed_local_indicator_shortlist_not_source_map_or_evidence"
POOL_TRUST_STATUS = "private_unreviewed_mineru_markdown_candidate_pool_not_source_map"
_MAX_SEGMENTS_PER_DOCUMENT = 2
_MAX_TOTAL_SEGMENTS = 12


class MaterialIndicatorTriageError(ValueError):
    """Raised when an indicator shortlist input or result is unsafe or invalid."""


_INDICATOR_TERMS: dict[str, tuple[str, ...]] = {
    "spontaneous_polarization_ps": (
        "spontaneous polarization", "remanent polarization", "polarisation", "polarization",
        "hysteresis loop", "p-e loop", "p(e)",
    ),
    "hysteresis_saturation": (
        "saturat", "unsaturat", "hysteresis loop", "coercive field", "cycling field",
    ),
    "epitaxial_strain": (
        "epitaxial strain", "compressive strain", "tensile strain", "lattice mismatch", "misfit strain",
    ),
    "tetragonality_c_over_a": (
        "c/a", "tetragonality", "tetragonal-like", "t-like", "t phase",
    ),
    "space_group": (
        "space group", "r3c", "pbnm", "pnma", "rhombohedral", "orthorhombic", "monoclinic",
        "tetragonal", "m_a", "m_c", "ma phase", "mc phase",
    ),
    "ferroelectric_transition_temperature": (
        "ferroelectric transition", "curie temperature", "curie point", "alpha-beta transition",
        "beta-to-alpha", "beta to alpha",
    ),
    "insulator_metal_transition_temperature": (
        "metal-insulator", "insulator-metal", "metallic", "semiconducting", "gamma phase",
    ),
    "domain_wall_conductivity": (
        "domain-wall conduction", "domain wall conduction", "domain-wall conductivity",
        "domain wall conductivity", "conductive wall", "conducting wall", "c-afm",
    ),
    "resistance_switching_ratio": (
        "switching ratio", "on/off", "on-off", "resistance ratio", "orders of magnitude",
    ),
}

_NUMERIC_RE = re.compile(
    r"(?<![A-Za-z])(?:[<>~≈]?\s*[+-]?(?:\d+(?:\.\d+)?|\.\d+)"
    r"(?:\s*(?:±|\+/-|to|[-–—])\s*[+-]?(?:\d+(?:\.\d+)?|\.\d+))?"
    r"(?:\s*[×x]\s*10\s*\^?\s*[+-]?\d+|\s*[eE][+-]?\d+)?)"
)
_UNIT_RE = re.compile(
    r"(?:μ|µ|u)c\s*/\s*cm(?:\^?2|²)|kv\s*/\s*cm|mv\s*/\s*cm|v\s*/\s*(?:cm|m)|"
    r"(?:°\s*c|deg\s*c|kelvin|\bk\b)|%|nm|μm|µm|angstrom|å|pa|na|μa|µa|ma|"
    r"a\s*/\s*cm(?:\^?2|²)|s\s*/\s*cm|ev|mev|hz|khz|mhz|pm\s*/\s*v",
    re.IGNORECASE,
)
_CONDITION_TERMS = (
    "temperature", "room temperature", "liquid nitrogen", "frequency", "field", "bias",
    "thickness", "substrate", "electrode", "orientation", "oriented", "direction", "along",
    "single crystal", "thin film", "ceramic", "polycrystalline", "powder", "anneal", "quench",
    "cooling", "heating", "oxygen", "atmosphere", "cycle", "sample",
)
_METHOD_TERMS = (
    "measured", "measurement", "determined", "observed", "x-ray", "diffraction", "neutron",
    "raman", "conductive afm", "c-afm", "pfm", "microscopy", "spectroscopy", "hysteresis",
    "current-voltage", "i-v", "reciprocal space map",
)
_BOUNDARY_TERMS = (
    "however", "although", "cannot", "could not", "limited", "limitation", "decomposition",
    "unsaturated", "degradation", "uncertainty", "not observed", "no evidence", "depends on",
    "rather than", "in contrast", "only", "approximately",
)
_REFERENCE_RE = re.compile(
    r"(?:^|\n)\s*(?:#{1,4}\s*)?(?:references|bibliography)\b|"
    r"(?:^|\n)\s*\[?\d{1,3}\]?\s+[A-Z][A-Za-z-]+(?:\s+et\s+al\.)?.{0,100}\b(?:19|20)\d{2}\b",
    re.IGNORECASE,
)


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def _score_segment(segment: dict[str, str], focus_indicator_ids: list[str]) -> dict[str, Any] | None:
    quote = segment["quote"]
    text = quote.casefold()
    matched = [
        indicator_id
        for indicator_id in focus_indicator_ids
        if _contains_any(text, _INDICATOR_TERMS.get(indicator_id, (indicator_id.replace("_", " "),)))
    ]
    has_number = _NUMERIC_RE.search(quote) is not None
    has_unit = _UNIT_RE.search(quote) is not None
    condition_hits = sum(term in text for term in _CONDITION_TERMS)
    method_hits = sum(term in text for term in _METHOD_TERMS)
    boundary_hits = sum(term in text for term in _BOUNDARY_TERMS)
    reference_like = _REFERENCE_RE.search(quote) is not None

    # A generic number alone is too weak.  Keep an excerpt only when it names a
    # target indicator, or when a measured value/unit is tied to method/context.
    if not matched and not (has_number and (has_unit or condition_hits or method_hits)):
        return None

    score = 8 * len(matched)
    score += 5 if has_number else 0
    score += 4 if has_unit else 0
    score += min(condition_hits, 4) * 2
    score += min(method_hits, 3) * 2
    score += min(boundary_hits, 2)
    if reference_like:
        score -= 18
    if score <= 0:
        return None

    candidate_roles: list[str] = []
    reason_codes: list[str] = []
    if has_number or has_unit:
        candidate_roles.append("reported_value_candidate")
        reason_codes.append("numeric_or_unit_expression")
    if condition_hits:
        candidate_roles.append("measurement_condition_candidate")
        reason_codes.append("measurement_context_term")
    if method_hits:
        candidate_roles.append("measurement_method_candidate")
        reason_codes.append("measurement_method_term")
    if boundary_hits:
        candidate_roles.append("boundary_or_limitation_candidate")
        reason_codes.append("boundary_term")
    if matched:
        reason_codes.append("focus_indicator_term")
    if reference_like:
        reason_codes.append("reference_like_penalty")

    return {
        "segment_id": segment["segment_id"],
        "locator": segment["locator"],
        "kind": segment["kind"],
        "quote": quote,
        "quote_sha256": hashlib.sha256(quote.encode("utf-8")).hexdigest(),
        "matched_indicator_ids": matched,
        "candidate_roles": candidate_roles,
        "reason_codes": reason_codes,
        "score": score,
    }


def _validate_pool(pool: object, *, document_id: str, expected_markdown_hash: str) -> dict[str, Any]:
    if not isinstance(pool, dict):
        raise MaterialIndicatorTriageError("private review pool must be an object")
    if pool.get("trust_status") != POOL_TRUST_STATUS or pool.get("document_id") != document_id:
        raise MaterialIndicatorTriageError("private review pool identity or trust status does not match")
    if pool.get("source_markdown_sha256") != expected_markdown_hash:
        raise MaterialIndicatorTriageError("private review pool Markdown hash does not match its index")
    segments = pool.get("candidate_segments")
    if not isinstance(segments, list) or not segments:
        raise MaterialIndicatorTriageError("private review pool has no candidate segments")
    seen: set[str] = set()
    for item in segments:
        if not isinstance(item, dict) or set(item) != {"segment_id", "locator", "kind", "quote"}:
            raise MaterialIndicatorTriageError("private review pool segment fields are invalid")
        if not all(isinstance(item[key], str) and item[key].strip() for key in item):
            raise MaterialIndicatorTriageError("private review pool segment values are invalid")
        if item["segment_id"] in seen or len(item["quote"]) > 500:
            raise MaterialIndicatorTriageError("private review pool segment boundary is invalid")
        seen.add(item["segment_id"])
    return pool


def _source_scopes(matrix: object) -> dict[str, dict[str, Any]]:
    if not isinstance(matrix, dict) or matrix.get("schema_version") != "cosmatter.material-source-candidate-matrix/v1":
        raise MaterialIndicatorTriageError("material source matrix schema is unsupported")
    result: dict[str, dict[str, Any]] = {}
    for question in matrix.get("questions", []):
        if not isinstance(question, dict):
            raise MaterialIndicatorTriageError("material source matrix question is invalid")
        focus_ids = question.get("focus_indicator_ids")
        if not isinstance(focus_ids, list) or not focus_ids or not all(isinstance(value, str) and value for value in focus_ids):
            raise MaterialIndicatorTriageError("material source matrix focus indicators are invalid")
        for source in question.get("source_candidates", []):
            if not isinstance(source, dict) or not isinstance(source.get("source_id"), str):
                raise MaterialIndicatorTriageError("material source candidate is invalid")
            if source["source_id"] in result:
                raise MaterialIndicatorTriageError("material source candidate IDs must be unique")
            result[source["source_id"]] = {
                "question_id": question.get("question_id"),
                "focus_indicator_ids": focus_ids,
                "source_role": source.get("role"),
                "access_status": source.get("access_status"),
            }
    return result


def build_private_indicator_shortlist(
    *,
    matrix: object,
    review_index: object,
    pools_by_document: dict[str, object],
    max_total_segments: int = _MAX_TOTAL_SEGMENTS,
    max_segments_per_document: int = _MAX_SEGMENTS_PER_DOCUMENT,
) -> dict[str, Any]:
    """Build a bounded, hash-bound shortlist without making factual claims."""
    if not 1 <= max_total_segments <= _MAX_TOTAL_SEGMENTS:
        raise MaterialIndicatorTriageError("shortlist total limit must be between 1 and 12")
    if not 1 <= max_segments_per_document <= _MAX_SEGMENTS_PER_DOCUMENT:
        raise MaterialIndicatorTriageError("per-document shortlist limit must be between 1 and 2")
    if not isinstance(review_index, dict) or review_index.get("trust_status") != "private_unreviewed_mineru_manifest_review_index_not_evidence":
        raise MaterialIndicatorTriageError("private review index identity or trust status is invalid")
    entries = review_index.get("entries")
    if not isinstance(entries, list) or not entries:
        raise MaterialIndicatorTriageError("private review index has no entries")
    scopes = _source_scopes(matrix)

    per_document: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise MaterialIndicatorTriageError("private review index entry is invalid")
        document_id = entry.get("document_id")
        markdown_hash = entry.get("markdown_sha256")
        if not isinstance(document_id, str) or not isinstance(markdown_hash, str):
            raise MaterialIndicatorTriageError("private review index entry identity is invalid")
        scope = scopes.get(document_id)
        if scope is None or scope["access_status"] != "private_mineru_review_pool_ready":
            raise MaterialIndicatorTriageError("private review document is not a ready source-matrix candidate")
        if document_id not in pools_by_document:
            raise MaterialIndicatorTriageError("private review pool is missing for an indexed document")
        pool = _validate_pool(pools_by_document[document_id], document_id=document_id, expected_markdown_hash=markdown_hash)
        ranked = []
        for order, segment in enumerate(pool["candidate_segments"]):
            scored = _score_segment(segment, scope["focus_indicator_ids"])
            if scored is not None:
                ranked.append((scored, order))
        ranked.sort(key=lambda item: (-item[0]["score"], item[1], item[0]["segment_id"]))
        selected = [item[0] for item in ranked[:max_segments_per_document]]
        if selected:
            per_document.append(
                {
                    "document_id": document_id,
                    "source_markdown_sha256": pool["source_markdown_sha256"],
                    "question_id": scope["question_id"],
                    "source_role": scope["source_role"],
                    "focus_indicator_ids": list(scope["focus_indicator_ids"]),
                    "segments": selected,
                }
            )

    # Preserve document coverage first.  First-ranked segments from all sources
    # precede second-ranked segments when a caller requests a smaller total cap.
    chosen: dict[str, list[dict[str, Any]]] = {item["document_id"]: [] for item in per_document}
    remaining = max_total_segments
    for rank in range(max_segments_per_document):
        for item in per_document:
            if remaining == 0:
                break
            if rank < len(item["segments"]):
                chosen[item["document_id"]].append(item["segments"][rank])
                remaining -= 1
        if remaining == 0:
            break
    documents = [
        {**{key: value for key, value in item.items() if key != "segments"}, "segments": chosen[item["document_id"]]}
        for item in per_document
        if chosen[item["document_id"]]
    ]
    segment_count = sum(len(item["segments"]) for item in documents)
    if not segment_count:
        raise MaterialIndicatorTriageError("no indicator-relevant private segments met the deterministic threshold")
    return {
        "schema_version": SHORTLIST_SCHEMA_VERSION,
        "mission_id": review_index.get("mission_id"),
        "material_scope": matrix.get("material_scope"),
        "catalog_id": matrix.get("catalog_id"),
        "trust_status": SHORTLIST_TRUST_STATUS,
        "selection_method": "deterministic_indicator_numeric_condition_ranking_v1",
        "document_count": len(documents),
        "segment_count": segment_count,
        "limits": {
            "max_total_segments": max_total_segments,
            "max_segments_per_document": max_segments_per_document,
            "max_quote_chars": 500,
        },
        "documents": documents,
        "review_boundary": (
            "These exact excerpts are private navigation candidates only. Validate each value, unit, qualifier, "
            "table or figure context, and source location before creating a Source Map or material fact."
        ),
    }
