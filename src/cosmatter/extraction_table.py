"""Read-only, run-scoped extraction table for included papers and checked evidence."""

from __future__ import annotations

import csv
import io
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

from .accepted_evidence_search import canonical_evidence_doi, safe_evidence_conditions
from .candidate_screening import load_candidate_screening, screening_matches_candidates, selected_document_ids
from .delegated_trial import has_delegated_test_review_boundary
from .material_extraction import iter_material_facts, validate_material_fact_source_links
from .models import MissionBrief, ReviewStatus, normalize_public_title
from .provenance_audit import matching_source_segments
from .run_control import load_run_control
from .source_map import HUMAN_SOURCE_MAP_TRUST_STATUS, iter_source_maps
from .stage_contract import stage_contract
from .ui_export import (
    _evidence_cards_from_payloads, _evidence_maturity_registry_projection, _load_array_if_present, _load_object,
    _verification_decisions_from_payloads, approved_evidence_projection, project_run_for_ui,
)


def _document_versions(run_dir: Path, mission_id: str) -> dict[str, str]:
    registry, _ = _evidence_maturity_registry_projection(run_dir, run_dir.parent, mission_id)
    versions: dict[str, set[str]] = defaultdict(set)
    if registry and registry["trust_status"] == "human_reviewed_evidence_maturity_registry_not_scientific_conclusion":
        for claim in registry["claims"]:
            for record in claim["support_records"]:
                if record["run_id"] == run_dir.name and record["source_map_status"] == "human_reviewed":
                    versions[record["document_id"]].add(record["document_version"])
    return {doc: next(iter(values)) for doc, values in versions.items() if len(values) == 1 and "unknown" not in values}


def _selected_papers(run_dir: Path, mission_id: str) -> tuple[dict[str, Any], frozenset[str], str]:
    path = run_dir / "retrieval_candidates.json"
    candidates = _load_object(path, "retrieval candidate artifact") if path.exists() else {"candidates": []}
    papers: dict[str, Any] = {}
    if not isinstance(candidates.get("candidates"), list):
        raise ValueError("invalid candidate list")
    for paper in candidates["candidates"]:
        if not isinstance(paper, dict) or not isinstance(paper.get("document_id"), str) or paper["document_id"] in papers:
            raise ValueError("invalid candidate identity")
        papers[paper["document_id"]] = paper
    screening = load_candidate_screening(run_dir / "candidate_screening.json", mission_id)
    if screening and screening_matches_candidates(screening, candidates):
        return papers, selected_document_ids(screening, candidates), "current"
    return papers, frozenset(), "outdated" if screening else "not_supplied"


def _reported_fact(fact: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(fact["name"], str) or not fact["name"].strip():
        raise ValueError("invalid fact name")
    for value in (fact["value"], *fact["qualifiers"].values()):
        if value is not None and (type(value) not in {str, int, float} or isinstance(value, float) and not math.isfinite(value)):
            raise ValueError("invalid fact value")
    return {field: fact[field] for field in ("fact_id", "name", "value", "unit", "qualifiers")}


def _reader_edges(run_dir: Path, mission: MissionBrief) -> set[tuple[str, str]]:
    """Identify exact evidence deep links reachable through the current workbench gates."""
    try:
        if load_run_control(run_dir / "run_control.json", mission.mission_id) is not None:
            return set()
        contract = stage_contract(run_dir, mission)
        if contract["runtime_safety"] != "verified" or contract["next_stage"] in {"intake", "plan", "retrieval"}:
            return set()
        # Use the exporter's actual bounded graph and run-wide source audit. Querying the table
        # must not write ui.json or log a UI export, including for a large or incomplete run.
        bundle = project_run_for_ui(run_dir.parent, run_dir.name)
        if bundle["status"]["mission_state"] == "CANCELLED":
            return set()
        return {(edge["source_id"], edge["target_id"]) for edge in bundle["literature_graph"]["edges"]
                if edge["edge_type"] == "source_provenance" and edge["trust_status"] == "accepted_evidence"}
    except (ValueError, OSError, TypeError, KeyError):
        # A rejected bundle or stage may still contain individually verified, exportable rows.
        return set()


def extraction_table(run_dir: Path, mission: MissionBrief) -> dict[str, Any]:
    mission_id = mission.mission_id
    papers, selected, screening_status = _selected_papers(run_dir, mission_id)
    delegated = has_delegated_test_review_boundary(run_dir)
    # Historical delegated trials can contain human-looking records. The marker always wins.
    cards = () if delegated else _evidence_cards_from_payloads(_load_array_if_present(run_dir / "evidence_cards.json", "evidence"))
    decisions = () if delegated else _verification_decisions_from_payloads(_load_array_if_present(run_dir / "verification_decisions.json", "decisions"))
    card_ids = {card.evidence_id for card in cards}
    if len(card_ids) != len(cards):
        raise ValueError("duplicate evidence ID")
    visible, _ = approved_evidence_projection(mission_id, cards, decisions)
    visible_ids = {card["evidence_id"] for card in visible}
    statuses = {d.evidence_id: d.status for d in decisions if d.mission_id == mission_id}
    if any(status is ReviewStatus.ACCEPTED and key not in card_ids for key, status in statuses.items()):
        raise ValueError("missing accepted card")
    maps = {} if delegated else {m["document_id"]: m for m in iter_source_maps(run_dir, mission_id) if m["trust_status"] == HUMAN_SOURCE_MAP_TRUST_STATUS}
    facts = () if delegated else iter_material_facts(run_dir, mission_id)
    validate_material_fact_source_links(mission_id=mission_id, artifacts=facts, source_maps=tuple(maps.values()))
    by_segment: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for artifact in facts:
        for fact in artifact["facts"]:
            by_segment[artifact["document_id"], fact["segment_id"]].append(_reported_fact(fact))
    versions = {} if delegated else _document_versions(run_dir, mission_id)

    reader_edges = _reader_edges(run_dir, mission) if visible_ids else set()

    rows = []
    cards_by_doc = defaultdict(list)
    for card in sorted(cards, key=lambda item: item.evidence_id):
        cards_by_doc[card.provenance.document_id].append(card)
    accepted_docs = {c.provenance.document_id for c in cards if statuses.get(c.evidence_id) is ReviewStatus.ACCEPTED}
    documents = sorted(selected | accepted_docs)
    gap_count = 0
    for document_id in documents:
        paper = papers.get(document_id, {})
        base = {
            "document_id": document_id, "title": normalize_public_title(paper["title"]) if paper else document_id,
            "doi": canonical_evidence_doi(paper.get("doi")), "document_version": versions.get(document_id),
            "source": paper.get("source") if isinstance(paper.get("source"), str) else None,
            "evidence_id": None, "claim": None, "material": None, "property_name": None, "stance": None,
            "conditions": {}, "locator": None, "reported_facts": [], "reader_available": False,
        }
        found = False
        pending = False
        unverified = False
        seen_observations: set[tuple[str, ...]] = set()
        for card in cards_by_doc[document_id]:
            status = statuses.get(card.evidence_id)
            if status is not ReviewStatus.ACCEPTED:
                pending |= status is not ReviewStatus.REJECTED
                continue
            source_map = maps.get(document_id)
            segments = matching_source_segments(card, source_map) if source_map else []
            if card.evidence_id not in visible_ids or not segments:
                unverified = True
                continue
            doi = canonical_evidence_doi(card.provenance.doi)
            if doi and base["doi"] and doi != base["doi"]:
                raise ValueError("conflicting paper and evidence DOI")
            conditions = safe_evidence_conditions(card.conditions)
            # A second review of the same observation at the same source is one table row.
            # Keep distinct qualifiers, claims, stances, and quotations at that location.
            key = (card.claim, card.material, card.property_name, card.stance.value, card.provenance.locator,
                   card.provenance.source, doi or base["doi"] or "", segments[0]["quote_sha256"],
                   json.dumps(conditions, ensure_ascii=False, sort_keys=True))
            if key in seen_observations:
                continue
            seen_observations.add(key)
            rows.append({
                **base, "status": "reviewed", "evidence_id": card.evidence_id, "claim": card.claim, "stance": card.stance.value,
                "material": card.material, "property_name": card.property_name, "conditions": conditions,
                "locator": card.provenance.locator, "source": card.provenance.source,
                "doi": doi or base["doi"],
                "reported_facts": [fact for seg in segments for fact in by_segment[document_id, seg["segment_id"]]],
                "reader_available": (f"paper:{document_id}", f"evidence:{card.evidence_id}") in reader_edges,
            })
            found = True
        if not found or unverified or pending:
            gap_count += 1
            gap = "unverified_source" if unverified else "awaiting_review" if pending or document_id in maps else "awaiting_extraction"
            rows.append({**base, "status": gap})
    return {
        "schema_version": "cosmatter.extraction-table/v1", "run_id": run_dir.name, "screening_status": screening_status,
        "summary": {"document_count": len(documents), "reviewed_count": len(rows) - gap_count, "gap_count": gap_count}, "rows": rows,
    }


def extraction_table_csv(table: dict[str, Any]) -> bytes:
    fields = ("run_id", "document_id", "title", "doi", "status", "evidence_id", "material", "property_name", "claim",
              "stance", "conditions", "reported_facts", "locator", "document_version", "source", "reader_available")
    output = io.StringIO(newline="")
    writer = csv.writer(output, quoting=csv.QUOTE_ALL)
    writer.writerow(fields)
    for row in table["rows"]:
        cells = []
        for key in fields:
            value = table["run_id"] if key == "run_id" else row[key]
            if isinstance(value, (dict, list, bool)):
                value = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
            if isinstance(value, str) and (value.startswith(("\t", "\r", "\n"))
                                          or value.lstrip().lstrip("\ufeff").lstrip().startswith(("=", "+", "-", "@"))):
                value = "'" + value
            cells.append(value)
        writer.writerow(cells)
    return output.getvalue().encode("utf-8-sig")
