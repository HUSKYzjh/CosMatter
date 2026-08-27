import hashlib
"""One offline, synthetic integration path proving the review-gated agent workflow.

The fixture text is intentionally synthetic and is never a claim about BiFeO3.
It exercises production artifact gates without an API key, network request, or
LLM call.
"""

import json
import tempfile
import unittest
from pathlib import Path

from cosmatter.candidate_screening import candidate_screening_from_review, write_candidate_screening
from cosmatter.facilities import condition_differential, write_condition_matrix
from cosmatter.dispatch import MissionDispatcher
from cosmatter.gap_analysis import candidates_from_discrepancies, write_gap_candidates
from cosmatter.counterevidence import require_executed_counterevidence
from cosmatter.ingestion import ingest_evidence_draft
from cosmatter.knowledge_fusion import fuse_reviewed_material_facts, write_material_fact_fusion
from cosmatter.material_extraction import material_facts_from_review, write_material_facts_for_document
from cosmatter.mineru import MinerUTask
from cosmatter.models import MissionBrief, PaperCandidate
from cosmatter.planning import approved_flight_plan_from_payload, write_approved_flight_plan
from cosmatter.provenance_audit import audit_accepted_evidence_provenance, write_evidence_provenance_audit
from cosmatter.report_audit import audit_report_evidence, write_report_evidence_audit
from cosmatter.reporting import build_evidence_manifest, build_structured_research_report, write_mission_report, write_structured_research_report
from cosmatter.retrieval import write_candidate_artifact
from cosmatter.source_map import iter_source_maps, source_map_from_review, write_source_map_for_document
from cosmatter.source_parse import record_source_parse_task
from cosmatter.provider_receipts import append_provider_receipt, mineru_task_receipt
from cosmatter.ui_export import export_run_to_ui
from cosmatter.workflow_readiness import workflow_readiness, write_workflow_readiness


class OfflineEndToEndWorkflowTests(unittest.TestCase):
    def test_two_literature_routes_reach_evidence_gap_report_and_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runs_dir = Path(directory) / "runs"
            run_dir = runs_dir / "offline_bfo"
            run_dir.mkdir(parents=True)
            mission = MissionBrief(
                question="Which recorded conditions can explain an offline fixture discrepancy?",
                material="BiFeO3",
                property_name="phase stability",
                scope="epitaxial films",
                mission_id="mission_offline_bfo",
            )
            (run_dir / "mission.json").write_text(json.dumps(mission.to_dict()), encoding="utf-8")
            assignment = MissionDispatcher.from_project().assign(mission)
            (run_dir / "fleet_assignment.json").write_text(json.dumps(assignment.to_dict()), encoding="utf-8")
            plan = approved_flight_plan_from_payload(
                mission,
                {
                    "subquestions": ["Which recorded conditions differ across the two fixture routes?"],
                    "queries": ["BiFeO3 fixture phase stability"],
                    "counter_queries": ["BiFeO3 fixture contradictory phase stability"],
                    "max_papers": 2,
                },
            )
            write_approved_flight_plan(run_dir, plan)
            main = PaperCandidate("doc_support", "Offline fixture supporting record", plan.queries[0], "offline_fixture", is_content_accessible=True)
            counter = PaperCandidate("doc_contradict", "Offline fixture counter record", plan.counter_queries[0], "offline_fixture", is_content_accessible=True)
            write_candidate_artifact(run_dir, plan.queries[0], (main,))
            write_candidate_artifact(run_dir, plan.counter_queries[0], (counter,))
            candidate_history = json.loads((run_dir / "retrieval_candidates.json").read_text(encoding="utf-8"))
            screening = candidate_screening_from_review(
                mission.mission_id,
                candidate_history,
                {"decisions": [
                    {"document_id": "doc_support", "decision": "include_for_fulltext", "reason_codes": ["material_match", "property_match"]},
                    {"document_id": "doc_contradict", "decision": "include_for_fulltext", "reason_codes": ["material_match", "property_match", "counterevidence"]},
                ]},
            )
            write_candidate_screening(run_dir, screening)

            cards = []
            decisions = []
            facts = []
            fixture_rows = (
                (
                    "doc_support",
                    "support",
                    "page:1 paragraph:1",
                    "Offline fixture states that a strained film was measured at 300 K.",
                    1.0,
                    "support",
                ),
                (
                    "doc_contradict",
                    "contradict",
                    "page:2 paragraph:1",
                    "Offline fixture states that a second strained film was measured at 300 K.",
                    -1.0,
                    "contradict",
                ),
            )
            for document_id, label, locator, quote, strain, stance in fixture_rows:
                record_source_parse_task(
                    run_dir,
                    mission_id=mission.mission_id,
                    document_id=document_id,
                    source_url=f"https://fixture.example/{document_id}.pdf",
                    task=MinerUTask(f"task_{label}", "done", f"request_{label}"),
                    model_version="fixture",
                )
                append_provider_receipt(
                    run_dir,
                    mineru_task_receipt(
                        operation="source_parse_poll", document_id=document_id,
                        source_url_sha256=hashlib.sha256(f"https://fixture.example/{document_id}.pdf".encode("utf-8")).hexdigest(),
                        task_id=f"task_{label}", task_state="done", model_version="fixture",
                        status_code=200, request_id=f"request_{label}",
                    ),
                )
                source_map = source_map_from_review(
                    mission_id=mission.mission_id,
                    document_id=document_id,
                    source_task={"document_id": document_id, "provider": "mineru", "state": "done", "task_id": f"task_{label}"},
                    selection={"document_id": document_id, "segments": [{"segment_id": f"seg_{label}", "locator": locator, "kind": "paragraph", "quote": quote}]},
                )
                write_source_map_for_document(run_dir, source_map)
                decision = ingest_evidence_draft(
                    run_dir,
                    {
                        "claim": f"Offline fixture {label} route records a phase-stability observation.",
                        "stance": stance,
                        "material": "BiFeO3",
                        "property_name": "phase stability",
                        "conditions": {
                            "sample_form": "film",
                            "strain_percent": strain,
                            "substrate": "STO",
                            "thickness_nm": 20,
                            "temperature_k": 300,
                            "method": "XRD",
                        },
                        "quote": quote,
                        "provenance": {
                            "document_id": document_id,
                            "locator": locator,
                            "source": "offline_fixture",
                            "access_policy": "authorized",
                        },
                        "extractor_confidence": 0.8,
                        "evidence_id": f"evidence_{label}",
                    },
                )
                decisions.append(decision)
                facts.append(
                    material_facts_from_review(
                        mission_id=mission.mission_id,
                        source_map=source_map,
                        selection={
                            "document_id": document_id,
                            "facts": [
                                {
                                    "fact_id": f"fact_{label}",
                                    "segment_id": f"seg_{label}",
                                    "category": "property",
                                    "name": "reported_phase",
                                    "value": "fixture_phase_a" if label == "support" else "fixture_phase_b",
                                    "unit": None,
                                    "normalized_value": "fixture_phase_a" if label == "support" else "fixture_phase_b",
                                    "normalized_unit": None,
                                    "qualifiers": {"strain_percent": strain, "temperature_k": 300},
                                }
                            ],
                        },
                    )
                )
            from cosmatter.ui_export import _evidence_cards_from_payloads
            cards = _evidence_cards_from_payloads(json.loads((run_dir / "evidence_cards.json").read_text(encoding="utf-8")))
            for artifact in facts:
                write_material_facts_for_document(run_dir, artifact)
            fusion = fuse_reviewed_material_facts(mission.mission_id, tuple(facts))
            write_material_fact_fusion(run_dir, fusion)
            matrix = condition_differential(cards, plan.counter_queries)
            write_condition_matrix(run_dir, matrix)
            counterevidence = require_executed_counterevidence(plan, candidate_history)
            gaps = candidates_from_discrepancies(
                mission.mission_id, mission.material, mission.property_name, cards, tuple(decisions), matrix,
                counterevidence,
            )
            write_gap_candidates(run_dir, gaps)
            provenance = audit_accepted_evidence_provenance(
                mission=mission, cards=cards, decisions=tuple(decisions), source_maps=iter_source_maps(run_dir, mission.mission_id)
            )
            write_evidence_provenance_audit(run_dir, provenance)
            report = build_evidence_manifest(mission, cards, tuple(decisions), gaps)
            write_mission_report(run_dir, report)
            structured = build_structured_research_report(mission, cards, tuple(decisions), gaps, tuple(facts), fusion)
            write_structured_research_report(run_dir, structured)
            audit = audit_report_evidence(
                mission=mission,
                cards=cards,
                decisions=tuple(decisions),
                research_gap_candidates=gaps,
                report_payload=report.to_dict(),
                structured_report=structured,
                material_fact_artifacts=tuple(facts),
                material_fact_fusion=fusion,
            )
            write_report_evidence_audit(run_dir, audit)
            readiness = workflow_readiness(run_dir, mission)
            write_workflow_readiness(run_dir, readiness)
            ui_path = export_run_to_ui(runs_dir, "offline_bfo")
            bundle = json.loads(ui_path.read_text(encoding="utf-8"))
            stages = {stage["stage"]: stage for stage in readiness["stages"]}

        self.assertEqual(stages["retrieval"]["status"], "completed")
        self.assertEqual(stages["screening"]["status"], "completed")
        self.assertEqual(stages["parse"]["status"], "completed")
        self.assertEqual(stages["extraction"]["status"], "completed")
        self.assertEqual(stages["gap"]["status"], "completed")
        self.assertEqual(stages["report"]["status"], "completed")
        self.assertEqual(bundle["research_gap_candidates"][0]["review_status"], "candidate_requires_human_review")
        self.assertEqual(bundle["audit_summary"]["report_evidence"]["accepted_evidence_locator_rendered_coverage"], 1.0)
        self.assertNotIn("https://fixture.example/", json.dumps(bundle))
        self.assertNotIn("task_support", json.dumps(bundle))


if __name__ == "__main__":
    unittest.main()

