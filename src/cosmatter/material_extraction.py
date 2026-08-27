"""Review-gated structured material facts grounded in source-map segments."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .deepseek import DraftCompletion
from .models import MissionBrief
from .unit_normalization import UnitNormalizationError, validate_reported_normalization

MATERIAL_FACTS_SCHEMA_VERSION = "1.0"
MATERIAL_FACT_REVIEW_TEMPLATE_SCHEMA_VERSION = "1.0"
_FACT_CATEGORIES = {"composition", "structure", "property", "processing", "experimental_condition", "simulation_method"}
_REVIEW_FIELDS = {"document_id", "facts"}
_REVIEW_TEMPLATE_FIELDS = {"schema_version", "mission_id", "trust_status", "document_id", "source_map_fingerprint", "allowed_categories", "segments", "facts"}
_REVIEW_TEMPLATE_SEGMENT_FIELDS = {"segment_id", "locator", "quote_sha256"}
_REVIEW_FACT_FIELDS = {"fact_id", "segment_id", "category", "name", "value", "unit", "normalized_value", "normalized_unit", "qualifiers"}
_ARTIFACT_FIELDS = {"schema_version", "mission_id", "trust_status", "document_id", "facts"}
_STORED_FACT_FIELDS = _REVIEW_FACT_FIELDS | {"locator", "source_quote_sha256"}


class MaterialExtractionError(ValueError):
    """Raised when a material-fact draft lacks a bounded evidence basis."""


def material_extraction_prompts(mission: MissionBrief, source_map: dict[str, Any]) -> tuple[str, str]:
    """Build an explicitly opt-in prompt from reviewer-selected short excerpts."""
    _validate_source_map(source_map, mission.mission_id)
    system = (
        "You are the CosMatter material-fact extraction station. Return an untrusted JSON draft only. "
        "Extract only statements explicitly present in supplied locatable excerpts. Each proposed fact must cite one "
        "segment_id and use one category from composition, structure, property, processing, experimental_condition, "
        "simulation_method. Preserve uncertainty; do not infer, merge papers, invent units, claim novelty, or write a conclusion."
    )
    user = json.dumps({
        "mission": {"material": mission.material, "property_name": mission.property_name, "scope": mission.scope},
        "document_id": source_map["document_id"],
        "output_schema": {"document_id": source_map["document_id"], "facts": [{"fact_id": "unique id", "segment_id": "given segment id", "category": "one allowed category", "name": "field name", "value": "reported value", "unit": "reported unit or null", "normalized_value": "same value or explicit conversion", "normalized_unit": "unit or null", "qualifiers": {"condition": "reported context"}}]},
        "segments": [{"segment_id": item["segment_id"], "locator": item["locator"], "kind": item["kind"], "quote": item["quote"]} for item in source_map["segments"]],
    }, ensure_ascii=False)
    return system, user


def write_untrusted_material_extraction_draft(run_dir: Path, completion: DraftCompletion, source_map: dict[str, Any]) -> Path:
    """Persist model output locally; it is never evidence or a browser projection."""
    _validate_source_map(source_map, source_map["mission_id"])
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "material_extraction_draft.json"
    path.write_text(json.dumps({"schema_version": MATERIAL_FACTS_SCHEMA_VERSION, "trust_status": "untrusted_llm_material_extraction_draft", "model": completion.model, "document_id": source_map["document_id"], "content": completion.content}, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def material_fact_review_template(*, mission_id: str, source_map: dict[str, Any]) -> dict[str, Any]:
    """Create a blank fact-review form without copying source-map quote text."""
    _validate_source_map(source_map, mission_id)
    segments = _review_segments(source_map)
    return {
        "schema_version": MATERIAL_FACT_REVIEW_TEMPLATE_SCHEMA_VERSION,
        "mission_id": mission_id,
        "trust_status": "blank_human_material_fact_review_template_not_facts",
        "document_id": source_map["document_id"],
        "source_map_fingerprint": _source_map_fingerprint(segments),
        "allowed_categories": sorted(_FACT_CATEGORIES),
        "segments": segments,
        "facts": [],
    }


def write_material_fact_review_template(run_dir: Path, template: dict[str, Any]) -> Path:
    _validate_review_template(template, reviewed=False)
    document_id = template["document_id"]
    path = run_dir / "material_fact_review_templates" / f"{hashlib.sha256(document_id.encode('utf-8')).hexdigest()}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(template, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _selection_from_review_template(*, mission_id: str, source_map: dict[str, Any], template: object) -> dict[str, Any]:
    _validate_review_template(template, reviewed=True)
    assert isinstance(template, dict)
    if template["mission_id"] != mission_id or template["document_id"] != source_map["document_id"]:
        raise MaterialExtractionError("material fact review template does not match the source-map mission or document")
    expected_segments = _review_segments(source_map)
    if template["segments"] != expected_segments or template["source_map_fingerprint"] != _source_map_fingerprint(expected_segments):
        raise MaterialExtractionError("material fact review template does not match the current reviewed source map")
    return {"document_id": template["document_id"], "facts": template["facts"]}


def _review_segments(source_map: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {
            "segment_id": item["segment_id"],
            "locator": item["locator"],
            "quote_sha256": item["quote_sha256"],
        }
        for item in source_map["segments"]
    ]


def _source_map_fingerprint(segments: list[dict[str, str]]) -> str:
    stable = json.dumps(segments, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(stable).hexdigest()


def _validate_review_template(template: object, *, reviewed: bool) -> None:
    if not isinstance(template, dict) or set(template) != _REVIEW_TEMPLATE_FIELDS:
        raise MaterialExtractionError("material fact review template has unsupported or missing fields")
    expected_status = (
        "human_reviewed_material_facts_for_recording"
        if reviewed else "blank_human_material_fact_review_template_not_facts"
    )
    if template.get("schema_version") != MATERIAL_FACT_REVIEW_TEMPLATE_SCHEMA_VERSION or template.get("trust_status") != expected_status:
        raise MaterialExtractionError("material fact review template schema or trust status is invalid")
    if not all(isinstance(template.get(key), str) and template[key].strip() for key in ("mission_id", "document_id", "source_map_fingerprint")):
        raise MaterialExtractionError("material fact review template identity is invalid")
    if template.get("allowed_categories") != sorted(_FACT_CATEGORIES):
        raise MaterialExtractionError("material fact review template categories are invalid")
    segments = template.get("segments")
    if not isinstance(segments, list) or not segments:
        raise MaterialExtractionError("material fact review template segments are invalid")
    seen: set[str] = set()
    for item in segments:
        if not isinstance(item, dict) or set(item) != _REVIEW_TEMPLATE_SEGMENT_FIELDS:
            raise MaterialExtractionError("material fact review template segment fields are invalid")
        if not all(isinstance(item.get(key), str) and item[key].strip() for key in _REVIEW_TEMPLATE_SEGMENT_FIELDS):
            raise MaterialExtractionError("material fact review template segment values are invalid")
        if item["segment_id"] in seen or len(item["quote_sha256"]) != 64:
            raise MaterialExtractionError("material fact review template segment identity is invalid")
        seen.add(item["segment_id"])
    if template["source_map_fingerprint"] != _source_map_fingerprint(segments):
        raise MaterialExtractionError("material fact review template source-map fingerprint is invalid")
    facts = template.get("facts")
    if not isinstance(facts, list):
        raise MaterialExtractionError("material fact review template facts are invalid")
    if not reviewed and facts:
        raise MaterialExtractionError("blank material fact review template must start with no facts")


def material_facts_from_review(*, mission_id: str, source_map: dict[str, Any], selection: object) -> dict[str, Any]:
    """Validate reviewed facts and attach exact source-map locators and hashes."""
    _validate_source_map(source_map, mission_id)
    if isinstance(selection, dict) and set(selection) == _REVIEW_TEMPLATE_FIELDS:
        selection = _selection_from_review_template(mission_id=mission_id, source_map=source_map, template=selection)
    if not isinstance(selection, dict) or set(selection) != _REVIEW_FIELDS or selection.get("document_id") != source_map["document_id"]:
        raise MaterialExtractionError("material fact review must match the source-map document")
    raw_facts = selection.get("facts")
    if not isinstance(raw_facts, list) or not 1 <= len(raw_facts) <= 48:
        raise MaterialExtractionError("material fact review requires 1 to 48 facts")
    segments = {item["segment_id"]: item for item in source_map["segments"]}
    facts: list[dict[str, Any]] = []
    identifiers: set[str] = set()
    for raw in raw_facts:
        if not isinstance(raw, dict) or set(raw) != _REVIEW_FACT_FIELDS:
            raise MaterialExtractionError("material fact has unsupported or missing fields")
        fact_id, segment_id, category, name = raw.get("fact_id"), raw.get("segment_id"), raw.get("category"), raw.get("name")
        if not all(isinstance(value, str) and value.strip() for value in (fact_id, segment_id, category, name)):
            raise MaterialExtractionError("material fact identity fields must be nonempty strings")
        if fact_id in identifiers or len(fact_id) > 120 or len(name) > 180 or category not in _FACT_CATEGORIES or segment_id not in segments:
            raise MaterialExtractionError("material fact identity, category, or source segment is invalid")
        _validate_value(raw.get("value"), "value")
        _validate_value(raw.get("normalized_value"), "normalized_value")
        _validate_unit(raw.get("unit"), "unit")
        _validate_unit(raw.get("normalized_unit"), "normalized_unit")
        _validate_normalized_pair(raw)
        qualifiers = raw.get("qualifiers")
        if not isinstance(qualifiers, dict) or len(qualifiers) > 12 or not all(isinstance(key, str) and key.strip() and len(key) <= 100 for key in qualifiers):
            raise MaterialExtractionError("material fact qualifiers are invalid")
        for value in qualifiers.values():
            _validate_value(value, "qualifier")
        identifiers.add(fact_id)
        segment = segments[segment_id]
        facts.append({**raw, "locator": segment["locator"], "source_quote_sha256": segment["quote_sha256"]})
    artifact = {"schema_version": MATERIAL_FACTS_SCHEMA_VERSION, "mission_id": mission_id, "trust_status": "human_reviewed_structured_material_facts_not_scientific_conclusion", "document_id": source_map["document_id"], "facts": facts}
    _validate_artifact(artifact, mission_id)
    return artifact



def validate_material_fact_source_links(
    *,
    mission_id: str,
    artifacts: tuple[dict[str, Any], ...],
    source_maps: tuple[dict[str, Any], ...],
) -> None:
    """Prove every persisted material fact still matches a reviewed source-map segment.

    This guard is intentionally repeated before fusion, report delivery, and UI
    export. It catches an orphaned or locally altered fact artifact even when
    its standalone schema remains syntactically valid.
    """
    if not isinstance(mission_id, str) or not mission_id.strip():
        raise MaterialExtractionError("material fact source-link validation requires a mission identifier")
    maps: dict[str, dict[str, dict[str, str]]] = {}
    for source_map in source_maps:
        _validate_source_map(source_map, mission_id)
        document_id = source_map["document_id"]
        if document_id in maps:
            raise MaterialExtractionError("source-link validation found duplicate source maps for one document")
        segments: dict[str, dict[str, str]] = {}
        for segment in source_map["segments"]:
            quote = segment.get("quote")
            if not isinstance(quote, str) or hashlib.sha256(quote.encode("utf-8")).hexdigest() != segment["quote_sha256"]:
                raise MaterialExtractionError("source-link validation found a source-map quote fingerprint mismatch")
            segments[segment["segment_id"]] = {
                "locator": segment["locator"],
                "source_quote_sha256": segment["quote_sha256"],
            }
        maps[document_id] = segments
    for artifact in artifacts:
        _validate_artifact(artifact, mission_id)
        segments = maps.get(artifact["document_id"])
        if segments is None:
            raise MaterialExtractionError("reviewed material facts require a current reviewed source map for the same document")
        for fact in artifact["facts"]:
            segment = segments.get(fact["segment_id"])
            if segment is None or fact["locator"] != segment["locator"] or fact["source_quote_sha256"] != segment["source_quote_sha256"]:
                raise MaterialExtractionError("material fact is not linked to its current reviewed source-map segment")


def material_facts_document_path(run_dir: Path, document_id: str) -> Path:
    if not isinstance(document_id, str) or not document_id.strip():
        raise MaterialExtractionError("document_id must be nonempty")
    import hashlib
    return run_dir / "material_facts" / f"{hashlib.sha256(document_id.encode('utf-8')).hexdigest()}.json"


def write_material_facts_for_document(run_dir: Path, artifact: dict[str, Any]) -> Path:
    """Persist facts for one document without replacing other reviewed documents."""
    _validate_artifact(artifact, artifact["mission_id"])
    path = material_facts_document_path(run_dir, artifact["document_id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    legacy = run_dir / "material_facts.json"
    if not legacy.exists():
        legacy.write_text(json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def load_material_facts_for_document(run_dir: Path, mission_id: str, document_id: str | None) -> dict[str, Any] | None:
    if document_id is None:
        return load_material_facts(run_dir / "material_facts.json", mission_id)
    path = material_facts_document_path(run_dir, document_id)
    if path.exists():
        return load_material_facts(path, mission_id)
    legacy = load_material_facts(run_dir / "material_facts.json", mission_id)
    if legacy is not None and legacy["document_id"] == document_id:
        return legacy
    return None


def iter_material_facts(run_dir: Path, mission_id: str) -> tuple[dict[str, Any], ...]:
    artifacts: dict[str, dict[str, Any]] = {}
    legacy = load_material_facts(run_dir / "material_facts.json", mission_id)
    if legacy is not None:
        artifacts[legacy["document_id"]] = legacy
    directory = run_dir / "material_facts"
    if directory.exists():
        for path in sorted(directory.glob("*.json")):
            item = load_material_facts(path, mission_id)
            if item is not None:
                artifacts[item["document_id"]] = item
    return tuple(artifacts[key] for key in sorted(artifacts))

def write_material_facts(run_dir: Path, artifact: dict[str, Any]) -> Path:
    _validate_artifact(artifact, artifact["mission_id"])
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "material_facts.json"
    path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def load_material_facts(path: Path, mission_id: str) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        artifact = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise MaterialExtractionError("material_facts.json is invalid JSON") from error
    _validate_artifact(artifact, mission_id)
    return artifact


def _validate_value(value: object, label: str) -> None:
    if value is not None and (isinstance(value, bool) or not isinstance(value, (str, int, float))):
        raise MaterialExtractionError(f"material fact {label} must be a scalar or null")
    if isinstance(value, str) and (not value.strip() or len(value) > 500):
        raise MaterialExtractionError(f"material fact {label} is invalid")


def _validate_unit(value: object, label: str) -> None:
    if value is not None and (not isinstance(value, str) or not value.strip() or len(value) > 80):
        raise MaterialExtractionError(f"material fact {label} is invalid")


def _validate_normalized_pair(fact: dict[str, Any]) -> None:
    try:
        validate_reported_normalization(
            fact.get("value"), fact.get("unit"),
            fact.get("normalized_value"), fact.get("normalized_unit"),
        )
    except UnitNormalizationError as error:
        raise MaterialExtractionError(f"material fact unit normalization is inconsistent: {error}") from error


def _validate_source_map(source_map: object, mission_id: str) -> None:
    if not isinstance(source_map, dict) or source_map.get("mission_id") != mission_id or source_map.get("trust_status") != "human_reviewed_parser_selection":
        raise MaterialExtractionError("material extraction requires a reviewed source map for this mission")
    segments = source_map.get("segments")
    if not isinstance(source_map.get("document_id"), str) or not isinstance(segments, list) or not segments:
        raise MaterialExtractionError("source map identity or segments are invalid")
    for segment in segments:
        if not isinstance(segment, dict) or not all(isinstance(segment.get(key), str) and segment[key] for key in ("segment_id", "locator", "quote_sha256")):
            raise MaterialExtractionError("source map segment is invalid")


def _validate_artifact(artifact: object, mission_id: str) -> None:
    if not isinstance(artifact, dict) or set(artifact) != _ARTIFACT_FIELDS or artifact.get("schema_version") != MATERIAL_FACTS_SCHEMA_VERSION or artifact.get("mission_id") != mission_id or artifact.get("trust_status") != "human_reviewed_structured_material_facts_not_scientific_conclusion":
        raise MaterialExtractionError("material facts artifact is invalid")
    if not isinstance(artifact.get("document_id"), str) or not artifact["document_id"].strip() or not isinstance(artifact.get("facts"), list) or not 1 <= len(artifact["facts"]) <= 48:
        raise MaterialExtractionError("material facts artifact identity is invalid")
    identifiers: set[str] = set()
    for fact in artifact["facts"]:
        if not isinstance(fact, dict) or set(fact) != _STORED_FACT_FIELDS:
            raise MaterialExtractionError("material fact artifact fields are invalid")
        if not isinstance(fact.get("fact_id"), str) or not fact["fact_id"].strip() or fact["fact_id"] in identifiers or fact.get("category") not in _FACT_CATEGORIES or not isinstance(fact.get("segment_id"), str) or not isinstance(fact.get("locator"), str) or len(fact.get("source_quote_sha256", "")) != 64:
            raise MaterialExtractionError("material fact artifact identity is invalid")
        _validate_value(fact.get("value"), "value")
        _validate_value(fact.get("normalized_value"), "normalized_value")
        _validate_unit(fact.get("unit"), "unit")
        _validate_unit(fact.get("normalized_unit"), "normalized_unit")
        _validate_normalized_pair(fact)
        if not isinstance(fact.get("qualifiers"), dict):
            raise MaterialExtractionError("material fact artifact qualifiers are invalid")
        identifiers.add(fact["fact_id"])
