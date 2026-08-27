"""Parse an LLM material-extraction draft into review-only structured candidates."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


class MaterialDraftPreviewError(ValueError):
    pass


_CATEGORIES = {"composition", "structure", "property", "processing", "experimental_condition", "simulation_method"}
_FACT_FIELDS = {"fact_id", "segment_id", "category", "name", "value", "unit", "normalized_value", "normalized_unit", "qualifiers"}


def preview_untrusted_material_draft(run_dir: Path, mission_id: str, source_map: dict[str, Any], content: str) -> tuple[Path, int]:
    """Store a bounded, source-map-linked candidate preview without trusting it.

    Invalid model JSON deliberately produces no preview. The raw draft remains
    separate, and only a later human-review command can create material facts.
    """
    segments = _segments(source_map, mission_id)
    payload = _parse_json(content)
    if not isinstance(payload, dict) or set(payload) != {"document_id", "facts"} or payload.get("document_id") != source_map.get("document_id"):
        raise MaterialDraftPreviewError("LLM material draft must contain only its matching document_id and facts")
    raw_facts = payload.get("facts")
    if not isinstance(raw_facts, list) or not 1 <= len(raw_facts) <= 48:
        raise MaterialDraftPreviewError("LLM material draft requires 1 to 48 candidate facts")
    facts: list[dict[str, Any]] = []
    identifiers: set[str] = set()
    for raw in raw_facts:
        if not isinstance(raw, dict) or set(raw) != _FACT_FIELDS:
            raise MaterialDraftPreviewError("LLM candidate fact has unsupported or missing fields")
        fact_id, segment_id, category, name = raw.get("fact_id"), raw.get("segment_id"), raw.get("category"), raw.get("name")
        if (
            not all(isinstance(value, str) and value.strip() for value in (fact_id, segment_id, category, name))
            or fact_id in identifiers
            or len(fact_id) > 120
            or len(name) > 180
            or category not in _CATEGORIES
            or segment_id not in segments
        ):
            raise MaterialDraftPreviewError("LLM candidate fact identity or source segment is invalid")
        _scalar(raw.get("value"), "value")
        _scalar(raw.get("normalized_value"), "normalized_value")
        _unit(raw.get("unit"), "unit")
        _unit(raw.get("normalized_unit"), "normalized_unit")
        qualifiers = raw.get("qualifiers")
        if not isinstance(qualifiers, dict) or len(qualifiers) > 12 or any(not isinstance(key, str) or not key.strip() or len(key) > 100 for key in qualifiers):
            raise MaterialDraftPreviewError("LLM candidate fact qualifiers are invalid")
        for value in qualifiers.values():
            _scalar(value, "qualifier")
        identifiers.add(fact_id)
        segment = segments[segment_id]
        facts.append({**raw, "locator": segment["locator"], "source_quote_sha256": segment["quote_sha256"]})
    artifact = {
        "schema_version": "1.0",
        "mission_id": mission_id,
        "trust_status": "untrusted_llm_structured_material_fact_candidates_not_evidence",
        "document_id": source_map["document_id"],
        "facts": facts,
    }
    path = _preview_path(run_dir, source_map["document_id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path, len(facts)


def _preview_path(run_dir: Path, document_id: str) -> Path:
    digest = hashlib.sha256(document_id.encode("utf-8")).hexdigest()
    return run_dir / "material_extraction_candidates" / f"{digest}.json"


def _segments(source_map: object, mission_id: str) -> dict[str, dict[str, str]]:
    if not isinstance(source_map, dict) or source_map.get("mission_id") != mission_id or source_map.get("trust_status") != "human_reviewed_parser_selection" or not isinstance(source_map.get("document_id"), str) or not source_map["document_id"].strip() or not isinstance(source_map.get("segments"), list):
        raise MaterialDraftPreviewError("candidate preview requires a reviewed source map")
    result: dict[str, dict[str, str]] = {}
    for item in source_map["segments"]:
        if not isinstance(item, dict) or not all(isinstance(item.get(key), str) and item[key] for key in ("segment_id", "locator", "quote_sha256")) or item["segment_id"] in result or len(item["quote_sha256"]) != 64:
            raise MaterialDraftPreviewError("reviewed source-map segments are invalid")
        result[item["segment_id"]] = {"locator": item["locator"], "quote_sha256": item["quote_sha256"]}
    if not result:
        raise MaterialDraftPreviewError("reviewed source map has no usable segments")
    return result


def _parse_json(content: object) -> object:
    if not isinstance(content, str) or not content.strip() or len(content) > 40_000:
        raise MaterialDraftPreviewError("LLM material draft content is invalid")
    text = content.strip()
    if text.startswith("```json") and text.endswith("```"):
        text = text[7:-3].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        raise MaterialDraftPreviewError("LLM material draft is not valid JSON") from error


def _scalar(value: object, label: str) -> None:
    if value is not None and (isinstance(value, bool) or not isinstance(value, (str, int, float))):
        raise MaterialDraftPreviewError(f"LLM candidate {label} must be a scalar or null")
    if isinstance(value, str) and (not value.strip() or len(value) > 500):
        raise MaterialDraftPreviewError(f"LLM candidate {label} is invalid")


def _unit(value: object, label: str) -> None:
    if value is not None and (not isinstance(value, str) or not value.strip() or len(value) > 80):
        raise MaterialDraftPreviewError(f"LLM candidate {label} is invalid")
