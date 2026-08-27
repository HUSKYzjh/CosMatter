"""Reviewer-approved paper-scoped material entities and internal relations."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "1.0"
_ENTITY_KINDS = {"material", "property", "method", "experimental_setting", "computational_setting", "metric", "finding"}
_RELATION_TYPES = {"uses", "measures", "reports", "compares", "conditions", "describes"}


class PaperStructureError(ValueError):
    pass


def paper_structure_from_review(*, mission_id: str, source_map: dict[str, Any], selection: object) -> dict[str, Any]:
    """Keep a small reviewer-selected structure tied to source-map segments."""
    if not isinstance(source_map, dict) or source_map.get("mission_id") != mission_id or source_map.get("trust_status") != "human_reviewed_parser_selection":
        raise PaperStructureError("paper structure requires a reviewed source map from this mission")
    document_id = source_map.get("document_id")
    segment_ids = {segment.get("segment_id") for segment in source_map.get("segments", []) if isinstance(segment, dict)}
    if not isinstance(document_id, str) or not segment_ids or not isinstance(selection, dict) or set(selection) != {"document_id", "entities", "relations"} or selection.get("document_id") != document_id:
        raise PaperStructureError("paper structure selection identity is invalid")
    entities = _entities(selection["entities"], document_id, segment_ids)
    relations = _relations(selection["relations"], {entity["entity_id"] for entity in entities}, segment_ids)
    return {"schema_version": SCHEMA_VERSION, "mission_id": mission_id, "trust_status": "human_reviewed_paper_structure_not_scientific_evidence", "document_id": document_id, "entities": entities, "relations": relations}


def paper_structure_document_path(run_dir: Path, document_id: str) -> Path:
    if not isinstance(document_id, str) or not document_id.strip():
        raise PaperStructureError("document_id must be nonempty")
    digest = hashlib.sha256(document_id.encode("utf-8")).hexdigest()
    return run_dir / "paper_structures" / f"{digest}.json"


def write_paper_structure_for_document(run_dir: Path, structure: dict[str, Any]) -> Path:
    """Persist one reviewed paper structure without replacing other papers."""
    _validate(structure)
    path = paper_structure_document_path(run_dir, structure["document_id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(structure, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    legacy = run_dir / "paper_structure.json"
    if not legacy.exists():
        legacy.write_text(json.dumps(structure, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def load_paper_structure_for_document(
    run_dir: Path, mission_id: str, document_id: str | None
) -> dict[str, Any] | None:
    if document_id is None:
        return load_paper_structure(run_dir / "paper_structure.json", mission_id)
    path = paper_structure_document_path(run_dir, document_id)
    if path.exists():
        return load_paper_structure(path, mission_id)
    legacy = load_paper_structure(run_dir / "paper_structure.json", mission_id)
    if legacy is not None and legacy["document_id"] == document_id:
        return legacy
    return None


def iter_paper_structures(run_dir: Path, mission_id: str) -> tuple[dict[str, Any], ...]:
    """Return every reviewed structure, deduplicated with the legacy artifact."""
    structures: dict[str, dict[str, Any]] = {}
    legacy = load_paper_structure(run_dir / "paper_structure.json", mission_id)
    if legacy is not None:
        structures[legacy["document_id"]] = legacy
    directory = run_dir / "paper_structures"
    if directory.exists():
        for path in sorted(directory.glob("*.json")):
            item = load_paper_structure(path, mission_id)
            if item is not None:
                structures[item["document_id"]] = item
    return tuple(structures[key] for key in sorted(structures))


def write_paper_structure(run_dir: Path, structure: dict[str, Any]) -> Path:
    """Backward-compatible singleton writer for older callers and fixtures."""
    _validate(structure)
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "paper_structure.json"
    path.write_text(json.dumps(structure, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def load_paper_structure(path: Path, mission_id: str) -> dict[str, Any] | None:
    if not path.exists(): return None
    try: payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error: raise PaperStructureError("paper_structure.json is invalid JSON") from error
    _validate(payload)
    if payload["mission_id"] != mission_id: raise PaperStructureError("paper structure does not belong to mission")
    return payload


def _entities(raw: Any, document_id: str, segment_ids: set[Any]) -> list[dict[str, str]]:
    if not isinstance(raw, list) or not 1 <= len(raw) <= 24: raise PaperStructureError("paper structure requires 1 to 24 entities")
    result: list[dict[str, str]] = []; seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict) or set(item) != {"entity_id", "label", "kind", "segment_id"}: raise PaperStructureError("entity fields are invalid")
        entity_id, label, kind, segment_id = (item[key] for key in ("entity_id", "label", "kind", "segment_id"))
        if not all(isinstance(value, str) and value.strip() for value in (entity_id, label, kind, segment_id)) or entity_id in seen or len(entity_id) > 80 or len(label) > 160 or kind not in _ENTITY_KINDS or segment_id not in segment_ids: raise PaperStructureError("entity values are invalid")
        seen.add(entity_id); result.append({"entity_id": entity_id, "label": label, "kind": kind, "segment_id": segment_id})
    return result


def _relations(raw: Any, entity_ids: set[str], segment_ids: set[Any]) -> list[dict[str, str]]:
    if not isinstance(raw, list) or len(raw) > 36: raise PaperStructureError("relation list is invalid")
    result: list[dict[str, str]] = []; seen: set[tuple[str, str, str]] = set()
    for item in raw:
        if not isinstance(item, dict) or set(item) != {"source_entity_id", "target_entity_id", "relation_type", "segment_id"}: raise PaperStructureError("relation fields are invalid")
        source, target, relation_type, segment_id = (item[key] for key in ("source_entity_id", "target_entity_id", "relation_type", "segment_id"))
        identity = (source, target, relation_type)
        if not all(isinstance(value, str) and value.strip() for value in (source, target, relation_type, segment_id)) or source == target or source not in entity_ids or target not in entity_ids or relation_type not in _RELATION_TYPES or segment_id not in segment_ids or identity in seen: raise PaperStructureError("relation values are invalid")
        seen.add(identity); result.append({"source_entity_id": source, "target_entity_id": target, "relation_type": relation_type, "segment_id": segment_id})
    return result


def _validate(payload: Any) -> None:
    if not isinstance(payload, dict) or set(payload) != {"schema_version", "mission_id", "trust_status", "document_id", "entities", "relations"} or payload.get("schema_version") != SCHEMA_VERSION or payload.get("trust_status") != "human_reviewed_paper_structure_not_scientific_evidence" or not isinstance(payload.get("mission_id"), str) or not isinstance(payload.get("document_id"), str): raise PaperStructureError("paper structure artifact is invalid")
    entities = _entities(payload["entities"], payload["document_id"], {entity.get("segment_id") for entity in payload["entities"] if isinstance(entity, dict)})
    _relations(payload["relations"], {entity["entity_id"] for entity in entities}, {entity["segment_id"] for entity in entities})
