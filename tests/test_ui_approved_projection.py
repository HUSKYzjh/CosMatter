import unittest

from cosmatter.dispatch import MissionDispatcher
from cosmatter.models import AccessPolicy, EvidenceCard, MissionBrief, Provenance, ReviewStatus, Stance
from cosmatter.ui_export import UiExportError, approved_evidence_projection, build_ui_bundle
from cosmatter.verification import VerificationDecision


def card(evidence_id: str, quote: str = "short approved quote") -> EvidenceCard:
    return EvidenceCard("claim", Stance.SUPPORT, "BiFeO3", "phase", {"sample_form": "film"}, quote, Provenance("doc_" + evidence_id, "page:1", "fixture", access_policy=AccessPolicy.OA), evidence_id=evidence_id)


class UiApprovedProjectionTests(unittest.TestCase):
    def test_only_accepted_short_evidence_is_projected(self) -> None:
        accepted = card("accepted")
        rejected = card("rejected")
        decisions = (
            VerificationDecision("mission_1", "accepted", ReviewStatus.ACCEPTED, "complete"),
            VerificationDecision("mission_1", "rejected", ReviewStatus.REJECTED, "missing conditions", ("temperature_k",)),
        )
        evidence, summary = approved_evidence_projection("mission_1", (accepted, rejected), decisions)
        self.assertEqual([item["evidence_id"] for item in evidence], ["accepted"])
        self.assertEqual(summary["accepted_count"], 1)
        self.assertEqual(summary["rejected_count"], 1)
        self.assertNotIn("missing conditions", str(summary))

    def test_bundle_keeps_only_approved_evidence_and_summary(self) -> None:
        mission = MissionBrief("why", "BiFeO3", "phase", "films", mission_id="mission_1")
        assignment = MissionDispatcher.from_project().assign(mission)
        accepted = card("accepted")
        rejected = card("rejected")
        bundle = build_ui_bundle(
            mission,
            assignment,
            evidence_cards=(accepted, rejected),
            verification_decisions=(
                VerificationDecision("mission_1", "accepted", ReviewStatus.ACCEPTED, "complete"),
                VerificationDecision("mission_1", "rejected", ReviewStatus.REJECTED, "missing conditions"),
            ),
        )
        self.assertEqual([item["evidence_id"] for item in bundle["evidence_cards"]], ["accepted"])
        self.assertEqual(bundle["status"]["verification_summary"]["rejected_count"], 1)
        self.assertEqual(bundle["verification_decisions"], [])
    def test_gap_candidate_must_cite_only_accepted_evidence(self) -> None:
        mission = MissionBrief("why", "BiFeO3", "phase", "films", mission_id="mission_1")
        assignment = MissionDispatcher.from_project().assign(mission)
        accepted = card("accepted")
        rejected = card("rejected")
        candidate = {
            "schema_version": "1.0", "gap_id": "gap_001", "material": "BiFeO3", "property_name": "phase",
            "problem_description": "A bounded discrepancy", "evidence_ids": ["accepted", "rejected"],
            "conflict_or_missing_evidence": ["conflicting_condition:strain"],
            "novelty_status": "unverified_requires_bounded_literature_review",
            "actionability": "compare strain", "falsifiable_hypothesis": "strain explains the discrepancy",
            "suggested_validation": ["retrieve counterevidence"], "evidence_completeness": 1.0,
            "review_status": "candidate_requires_human_review",
        }
        with self.assertRaises(UiExportError):
            build_ui_bundle(
                mission, assignment, evidence_cards=(accepted, rejected),
                verification_decisions=(
                    VerificationDecision("mission_1", "accepted", ReviewStatus.ACCEPTED, "complete"),
                    VerificationDecision("mission_1", "rejected", ReviewStatus.REJECTED, "incomplete"),
                ), research_gap_candidates=[candidate],
            )

    def test_gap_candidate_must_match_scope_and_remain_pending_human_review(self) -> None:
        mission = MissionBrief("why", "BiFeO3", "phase", "films", mission_id="mission_1")
        assignment = MissionDispatcher.from_project().assign(mission)
        accepted = card("accepted")
        baseline = {
            "schema_version": "1.0", "gap_id": "gap_001", "material": "BiFeO3", "property_name": "phase",
            "problem_description": "A bounded discrepancy", "evidence_ids": ["accepted"],
            "conflict_or_missing_evidence": ["conflicting_condition:strain"],
            "novelty_status": "unverified_requires_bounded_literature_review",
            "actionability": "compare strain", "falsifiable_hypothesis": "strain explains the discrepancy",
            "suggested_validation": ["retrieve counterevidence"], "evidence_completeness": 1.0,
            "review_status": "candidate_requires_human_review",
        }
        for update in (
            {"material": "BaTiO3"},
            {"property_name": "polarization"},
            {"review_status": "draft"},
        ):
            with self.subTest(update=update):
                candidate = {**baseline, **update}
                with self.assertRaises(UiExportError):
                    build_ui_bundle(
                        mission, assignment, evidence_cards=(accepted,),
                        verification_decisions=(VerificationDecision("mission_1", "accepted", ReviewStatus.ACCEPTED, "complete"),),
                        research_gap_candidates=[candidate],
                    )

    def test_duplicate_decisions_are_rejected(self) -> None:
        accepted = card("accepted")
        decisions = (
            VerificationDecision("mission_1", "accepted", ReviewStatus.ACCEPTED, "complete"),
            VerificationDecision("mission_1", "accepted", ReviewStatus.REJECTED, "reversed"),
        )
        with self.assertRaises(UiExportError):
            approved_evidence_projection("mission_1", (accepted,), decisions)
    def test_long_quote_is_not_projected(self) -> None:
        long_card = card("long", "x" * 501)
        decision = VerificationDecision("mission_1", "long", ReviewStatus.ACCEPTED, "complete")
        evidence, summary = approved_evidence_projection("mission_1", (long_card,), (decision,))
        self.assertEqual(evidence, [])
        self.assertEqual(summary["withheld_count"], 1)

    def test_graph_keeps_document_scoped_entities_separate(self) -> None:
        mission = MissionBrief("why", "BiFeO3", "phase", "films", mission_id="mission_1")
        assignment = MissionDispatcher.from_project().assign(mission)
        structure_one = {
            "document_id": "doc_1",
            "trust_status": "human_reviewed_paper_structure_not_scientific_evidence",
            "entities": [
                {"entity_id": "e1", "label": "BiFeO3", "kind": "material", "segment_id": "s1"},
                {"entity_id": "e2", "label": "phase", "kind": "property", "segment_id": "s1"},
            ],
            "relations": [{"source_entity_id": "e1", "target_entity_id": "e2", "relation_type": "reports", "segment_id": "s1"}],
        }
        structure_two = {
            "document_id": "doc_2",
            "trust_status": "human_reviewed_paper_structure_not_scientific_evidence",
            "entities": [
                {"entity_id": "e1", "label": "BiFeO3", "kind": "material", "segment_id": "s2"},
                {"entity_id": "e2", "label": "phase", "kind": "property", "segment_id": "s2"},
            ],
            "relations": [{"source_entity_id": "e1", "target_entity_id": "e2", "relation_type": "reports", "segment_id": "s2"}],
        }
        bundle = build_ui_bundle(mission, assignment, paper_structures=(structure_one, structure_two))
        node_ids = {node["node_id"] for node in bundle["literature_graph"]["nodes"]}
        edge_pairs = {(edge["source_id"], edge["target_id"]) for edge in bundle["literature_graph"]["edges"]}
        self.assertIn("entity:doc_1:e1", node_ids)
        self.assertIn("entity:doc_2:e1", node_ids)
        self.assertIn(("entity:doc_1:e1", "entity:doc_1:e2"), edge_pairs)
        self.assertIn(("entity:doc_2:e1", "entity:doc_2:e2"), edge_pairs)

    def test_bundle_exposes_only_cross_document_review_counts(self) -> None:
        mission = MissionBrief("why", "BiFeO3", "phase", "films", mission_id="mission_1")
        assignment = MissionDispatcher.from_project().assign(mission)
        source_maps = (
            {"document_id": "doc_1", "segments": [{"segment_id": "s1"}, {"segment_id": "s2"}]},
            {"document_id": "doc_2", "segments": [{"segment_id": "s1"}]},
        )
        facts = (
            {"document_id": "doc_1", "facts": [{"fact_id": "f1"}]},
            {"document_id": "doc_2", "facts": [{"fact_id": "f2"}, {"fact_id": "f3"}]},
        )
        bundle = build_ui_bundle(
            mission,
            assignment,
            source_maps=source_maps,
            material_fact_artifacts=facts,
        )
        self.assertEqual(bundle["reviewed_source_map_summary"], {"document_count": 2, "segment_count": 3, "document_ids": ["doc_1", "doc_2"]})
        self.assertEqual(bundle["reviewed_material_fact_summary"], {"document_count": 2, "fact_count": 3})
        self.assertNotIn("s1", str(bundle["reviewed_source_map_summary"]))
        self.assertNotIn("f1", str(bundle["reviewed_material_fact_summary"]))


if __name__ == "__main__":
    unittest.main()
