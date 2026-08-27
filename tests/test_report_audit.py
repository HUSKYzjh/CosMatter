import json
import tempfile
import unittest
from pathlib import Path

from cosmatter.gap_analysis import CounterevidenceBoundary, ResearchGapCandidate
from cosmatter.models import AccessPolicy, EvidenceCard, MissionBrief, Provenance, ReviewStatus, Stance
from cosmatter.report_audit import ReportAuditError, audit_report_evidence, write_report_evidence_audit
from cosmatter.reporting import build_evidence_manifest, build_structured_research_report
from cosmatter.verification import VerificationDecision


def _card(evidence_id: str, stance: Stance = Stance.SUPPORT) -> EvidenceCard:
    return EvidenceCard(
        "bounded synthetic claim", stance, "BiFeO3", "phase stability",
        {"sample_form": "film"}, "short fixture quote",
        Provenance(f"doc_{evidence_id}", "page:1", "fixture", access_policy=AccessPolicy.OA),
        evidence_id=evidence_id,
    )


class ReportAuditTests(unittest.TestCase):
    def test_audit_requires_complete_accepted_evidence_gap_coverage_and_rendered_counterevidence(self) -> None:
        mission = MissionBrief("why", "BiFeO3", "phase stability", "films", mission_id="mission_report_audit")
        cards = (_card("support"), _card("contradict", Stance.CONTRADICT))
        decisions = tuple(VerificationDecision(mission.mission_id, item.evidence_id, ReviewStatus.ACCEPTED, "complete") for item in cards)
        gap = ResearchGapCandidate(
            "gap_001", "BiFeO3", "phase stability", "bounded discrepancy",
            ("support", "contradict"), ("conflicting_condition:strain",),
            "unverified_requires_bounded_literature_review", "test strain",
            "strain explains the disagreement", ("retrieve counterevidence",), 1.0,
            counterevidence_boundary=CounterevidenceBoundary(
                "all_approved_counterevidence_queries_recorded", 1, 1, ("a" * 64,), "b" * 64,
            ),
        )
        report = build_evidence_manifest(mission, cards, decisions, (gap,))
        facts = (
            {"document_id": "doc_support", "facts": [{"fact_id": "fact_support", "segment_id": "seg_support", "category": "property", "name": "polarization", "value": 50, "unit": "uC/cm2", "normalized_value": 50, "normalized_unit": "uC/cm2", "qualifiers": {"strain": "0%"}, "locator": "page:2", "source_quote_sha256": "0" * 64}]},
            {"document_id": "doc_contradict", "facts": [{"fact_id": "fact_contradict", "segment_id": "seg_contradict", "category": "property", "name": "polarization", "value": 60, "unit": "uC/cm2", "normalized_value": 60, "normalized_unit": "uC/cm2", "qualifiers": {"strain": "1%"}, "locator": "page:3", "source_quote_sha256": "1" * 64}]},
        )
        fusion = {"comparisons": [{"comparison_id": "comparison_001", "observations": [{"document_id": "doc_support", "fact_id": "fact_support", "locator": "page:2", "value": 50, "qualifiers": {"strain": "0%"}}, {"document_id": "doc_contradict", "fact_id": "fact_contradict", "locator": "page:3", "value": 60, "qualifiers": {"strain": "1%"}}]}]}
        structured = build_structured_research_report(mission, cards, decisions, (gap,), facts, fusion)

        result = audit_report_evidence(
            mission=mission, cards=cards, decisions=decisions,
            research_gap_candidates=(gap,), report_payload=report.to_dict(), structured_report=structured,
            material_fact_artifacts=facts, material_fact_fusion=fusion,
        )

        self.assertEqual(result["accepted_evidence_count"], 2)
        self.assertEqual(result["gap_evidence_reference_count"], 2)
        self.assertEqual(result["structured_report_identifier_coverage"], 1.0)
        self.assertEqual(result["accepted_evidence_locator_rendered_coverage"], 1.0)
        self.assertEqual(result["reviewed_material_fact_count"], 2)
        self.assertEqual(result["cross_document_comparison_count"], 1)
        self.assertEqual(result["comparison_observation_reference_count"], 2)
        self.assertEqual(result["executed_gap_counterevidence_boundary_count"], 1)
        self.assertEqual(result["gap_counterevidence_boundary_rendered_coverage"], 1.0)
        self.assertTrue(result["human_source_locator_review_required"])
        with self.assertRaisesRegex(ReportAuditError, "counterevidence boundaries"):
            audit_report_evidence(
                mission=mission, cards=cards, decisions=decisions,
                research_gap_candidates=(gap,), report_payload=report.to_dict(),
                structured_report=structured.replace("b" * 64, "hidden-history"),
                material_fact_artifacts=facts, material_fact_fusion=fusion,
            )
        with tempfile.TemporaryDirectory() as directory:
            path = write_report_evidence_audit(Path(directory), result)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["trust_status"], result["trust_status"])

    def test_audit_rejects_evidence_identifier_without_its_document_locator(self) -> None:
        mission = MissionBrief("why", "BiFeO3", "phase stability", "films", mission_id="mission_report_locator")
        card = _card("accepted")
        decisions = (VerificationDecision(mission.mission_id, card.evidence_id, ReviewStatus.ACCEPTED, "complete"),)
        report = build_evidence_manifest(mission, (card,), decisions)
        structured = build_structured_research_report(mission, (card,), decisions).replace("page:1", "hidden-locator")
        with self.assertRaisesRegex(ReportAuditError, "document IDs or locators"):
            audit_report_evidence(
                mission=mission, cards=(card,), decisions=decisions, research_gap_candidates=(),
                report_payload=report.to_dict(), structured_report=structured,
            )

    def test_audit_rejects_missing_rendered_identifier_or_unaccepted_manifest_id(self) -> None:
        mission = MissionBrief("why", "BiFeO3", "phase stability", "films", mission_id="mission_report_audit")
        card = _card("accepted")
        decisions = (VerificationDecision(mission.mission_id, card.evidence_id, ReviewStatus.ACCEPTED, "complete"),)
        report = build_evidence_manifest(mission, (card,), decisions)
        with self.assertRaisesRegex(ReportAuditError, "missing identifiers"):
            audit_report_evidence(
                mission=mission, cards=(card,), decisions=decisions, research_gap_candidates=(),
                report_payload=report.to_dict(), structured_report="## Evidence register\n\n## Review boundary\n",
            )
        invalid = report.to_dict()
        invalid["evidence_ids"] = ["not_accepted"]
        with self.assertRaisesRegex(ReportAuditError, "without an accepted decision"):
            audit_report_evidence(
                mission=mission, cards=(card,), decisions=decisions, research_gap_candidates=(),
                report_payload=invalid, structured_report="not used",
            )


if __name__ == "__main__":
    unittest.main()
