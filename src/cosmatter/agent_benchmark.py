"""Frozen end-to-end benchmark for the evidence-bound literature-agent path."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .facilities import condition_differential, verification_decision
from .gap_analysis import candidates_from_discrepancies
from .local_library import candidates_from_zotero_items
from .material_extraction import material_facts_from_review
from .models import AccessPolicy, EvidenceCard, Provenance, Stance


class AgentBenchmarkError(ValueError):
    pass


@dataclass(frozen=True)
class AgentBenchmarkReport:
    fixture_id: str
    fixture_sha256: str
    retrieval_precision_at_k: float
    retrieval_recall_at_k: float
    retrieval_ndcg_at_k: float
    extraction_fact_id_recall: float
    extraction_locator_accuracy: float
    gap_evidence_boundary_precision: float
    gap_differing_field_recall: float

    def to_dict(self) -> dict[str, object]:
        return {"fixture_id": self.fixture_id, "fixture_sha256": self.fixture_sha256, "synthetic": True, "retrieval_precision_at_k": self.retrieval_precision_at_k, "retrieval_recall_at_k": self.retrieval_recall_at_k, "retrieval_ndcg_at_k": self.retrieval_ndcg_at_k, "extraction_fact_id_recall": self.extraction_fact_id_recall, "extraction_locator_accuracy": self.extraction_locator_accuracy, "gap_evidence_boundary_precision": self.gap_evidence_boundary_precision, "gap_differing_field_recall": self.gap_differing_field_recall}


def evaluate_frozen_agent_benchmark(path: Path, mission_id: str) -> AgentBenchmarkReport:
    try:
        fixture_bytes = path.read_bytes()
        fixture = json.loads(fixture_bytes.decode("utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AgentBenchmarkError("benchmark fixture is unreadable") from error
    if not isinstance(fixture, dict) or fixture.get("synthetic") is not True:
        raise AgentBenchmarkError("only explicitly synthetic benchmark fixtures are accepted")
    try:
        retrieval = fixture["retrieval"]
        ranked = candidates_from_zotero_items(retrieval["zotero_items"], str(retrieval["query"]), int(retrieval["top_k"]))
        expected_relevant = set(str(value) for value in retrieval["expected_relevant_document_ids"])
        ranked_ids = [item.document_id for item in ranked]
        retrieval_precision = _precision(set(ranked_ids), expected_relevant)
        retrieval_recall = _recall(set(ranked_ids), expected_relevant)
        retrieval_ndcg = _ndcg(ranked_ids, expected_relevant)

        extraction = fixture["extraction"]
        source_map = _source_map(mission_id, extraction)
        facts = material_facts_from_review(mission_id=mission_id, source_map=source_map, selection=extraction["reviewed_facts"])
        expected_facts = set(str(value) for value in extraction["expected_fact_ids"])
        observed_facts = {str(item["fact_id"]) for item in facts["facts"]}
        extraction_recall = _recall(observed_facts, expected_facts)
        locator_accuracy = sum(item["locator"] == next(segment["locator"] for segment in source_map["segments"] if segment["segment_id"] == item["segment_id"]) for item in facts["facts"]) / len(facts["facts"])

        gap = fixture["gap"]
        cards = tuple(_card(entry, str(gap["material"]), str(gap["property_name"])) for entry in gap["evidence_cards"])
        decisions = tuple(verification_decision(mission_id, card) for card in cards)
        matrix = condition_differential(cards, tuple(str(value) for value in gap["counterevidence_queries"]))
        candidates = candidates_from_discrepancies(mission_id, str(gap["material"]), str(gap["property_name"]), cards, decisions, matrix)
        observed_gap_evidence = set(candidates[0].evidence_ids)
        expected_gap_evidence = set(str(value) for value in gap["expected_evidence_ids"])
        observed_fields = set(matrix.rows[0].differing_fields)
        expected_fields = set(str(value) for value in gap["expected_differing_fields"])
    except (KeyError, TypeError, ValueError, StopIteration) as error:
        raise AgentBenchmarkError("benchmark fixture has an invalid shape") from error
    return AgentBenchmarkReport(
        fixture_id=f"{path.stem}_v{fixture.get('fixture_version', 'unknown')}", fixture_sha256=hashlib.sha256(fixture_bytes).hexdigest(), retrieval_precision_at_k=retrieval_precision,
        retrieval_recall_at_k=retrieval_recall, retrieval_ndcg_at_k=retrieval_ndcg,
        extraction_fact_id_recall=extraction_recall, extraction_locator_accuracy=locator_accuracy,
        gap_evidence_boundary_precision=_precision(observed_gap_evidence, expected_gap_evidence),
        gap_differing_field_recall=_recall(observed_fields, expected_fields),
    )


def write_agent_benchmark_record(run_dir: Path, report: AgentBenchmarkReport) -> Path:
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "agent_benchmark.json"
    path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _source_map(mission_id: str, extraction: Any) -> dict[str, Any]:
    segments = []
    for item in extraction["segments"]:
        quote = str(item["quote"])
        segments.append({"segment_id": str(item["segment_id"]), "locator": str(item["locator"]), "kind": str(item.get("kind", "paragraph")), "quote": quote, "quote_sha256": hashlib.sha256(quote.encode("utf-8")).hexdigest()})
    return {"schema_version": "1.0", "mission_id": mission_id, "trust_status": "human_reviewed_parser_selection", "document_id": str(extraction["document_id"]), "provider": "mineru", "task_id_sha256": "f" * 64, "segments": segments}


def _card(entry: dict[str, Any], material: str, property_name: str) -> EvidenceCard:
    return EvidenceCard(claim="Synthetic benchmark evidence; not a scientific claim.", stance=Stance(str(entry["stance"])), material=material, property_name=property_name, conditions=entry["conditions"], quote="Synthetic benchmark snippet.", provenance=Provenance(str(entry["evidence_id"]), "fixture", "CosMatter frozen benchmark", access_policy=AccessPolicy.LOCAL_ONLY), evidence_id=str(entry["evidence_id"]))


def _precision(predicted: set[str], expected: set[str]) -> float:
    return len(predicted & expected) / len(predicted) if predicted else 0.0


def _recall(predicted: set[str], expected: set[str]) -> float:
    return len(predicted & expected) / len(expected) if expected else 0.0


def _ndcg(ranked: list[str], relevant: set[str]) -> float:
    if not relevant:
        return 0.0
    dcg = sum((1.0 / __import__("math").log2(index + 2)) for index, item in enumerate(ranked) if item in relevant)
    ideal = sum(1.0 / __import__("math").log2(index + 2) for index in range(min(len(relevant), len(ranked))))
    return dcg / ideal if ideal else 0.0
