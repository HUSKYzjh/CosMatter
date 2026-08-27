import json
import tempfile
import unittest
from pathlib import Path

from cosmatter.gap_analysis import ResearchGapCandidate
from cosmatter.models import AccessPolicy, EvidenceCard, MissionBrief, Provenance, ReviewStatus, Stance
from cosmatter.reporting import ReportGateError, build_evidence_manifest, build_structured_research_report, write_mission_report, write_structured_research_report
from cosmatter.verification import VerificationDecision


def card(evidence_id: str) -> EvidenceCard:
    return EvidenceCard(
        "synthetic claim",
        Stance.SUPPORT,
        "BiFeO3",
        "phase stability",
        {"sample_form": "film"},
        "synthetic short quote",
        Provenance("doc_1", "page:1", "fixture", access_policy=AccessPolicy.OA),
        evidence_id=evidence_id,
    )


class ReportingTests(unittest.TestCase):
    def test_report_contains_only_accepted_evidence_identifiers(self) -> None:
        mission = MissionBrief("why", "BiFeO3", "phase stability", "films", mission_id="mission_1")
        accepted = card("accepted")
        rejected = card("rejected")
        report = build_evidence_manifest(
            mission,
            (accepted, rejected),
            (
                VerificationDecision("mission_1", "accepted", ReviewStatus.ACCEPTED, "complete"),
                VerificationDecision("mission_1", "rejected", ReviewStatus.REJECTED, "missing conditions"),
            ),
        )

        self.assertEqual(report.evidence_ids, ("accepted",))
        self.assertIn("does not by itself establish", report.summary)

    def test_structured_report_links_evidence_facts_and_comparison_boundaries(self) -> None:
        mission = MissionBrief("why", "BiFeO3", "phase stability", "films", mission_id="mission_1")
        accepted = card("accepted")
        decisions = (VerificationDecision("mission_1", "accepted", ReviewStatus.ACCEPTED, "complete"),)
        fact_artifact = {"document_id": "doc_1", "facts": [{"fact_id": "fact_1", "category": "property", "name": "polarization", "value": 50, "unit": "uC/cm2", "normalized_value": 50, "normalized_unit": "uC/cm2", "locator": "page:2"}]}
        fusion = {"comparisons": [{"comparison_id": "comparison_001", "category": "property", "name": "polarization", "normalized_unit": "uC/cm2", "comparison_status": "aligned_under_matching_qualifiers", "differing_qualifier_fields": [], "observations": [{"document_id": "doc_1", "fact_id": "fact_1", "locator": "page:2", "value": 50, "qualifiers": {"sample_form": "film"}}]}]}
        content = build_structured_research_report(mission, (accepted,), decisions, material_fact_artifacts=(fact_artifact,), material_fact_fusion=fusion)
        with tempfile.TemporaryDirectory() as directory:
            path = write_structured_research_report(Path(directory), content)
            saved = path.read_text(encoding="utf-8")
        self.assertIn("| accepted | doc_1 | page:1", saved)
        self.assertIn("fact_1", saved)
        self.assertIn("comparison_001", saved)
        self.assertIn("doc_1 / fact_1 / page:2", saved)
        self.assertIn("condition-aware grouping", saved)
        self.assertIn("not an autonomous scientific conclusion", saved)

    def test_report_rejects_gap_candidate_outside_the_mission_scope(self) -> None:
        mission = MissionBrief("why", "BiFeO3", "phase stability", "films", mission_id="mission_1")
        accepted = (card("accepted_1"), card("accepted_2"))
        decisions = (
            VerificationDecision("mission_1", "accepted_1", ReviewStatus.ACCEPTED, "complete"),
            VerificationDecision("mission_1", "accepted_2", ReviewStatus.ACCEPTED, "complete"),
        )
        candidate = ResearchGapCandidate(
            "gap_scope", "BaTiO3", "phase stability", "bounded conflict",
            ("accepted_1", "accepted_2"), ("conflicting_condition:strain_percent",),
            "unverified_requires_bounded_literature_review", "compare strain",
            "strain explains the discrepancy", ("retrieve counterevidence",), 1.0,
        )
        with self.assertRaises(ReportGateError):
            build_evidence_manifest(mission, accepted, decisions, (candidate,))

    def test_report_requires_accepted_evidence_and_excludes_quotes_on_disk(self) -> None:
        mission = MissionBrief("why", "BiFeO3", "phase stability", "films", mission_id="mission_1")
        rejected = card("rejected")
        with self.assertRaises(ReportGateError):
            build_evidence_manifest(
                mission,
                (rejected,),
                (VerificationDecision("mission_1", "rejected", ReviewStatus.REJECTED, "missing conditions"),),
            )
        report = build_evidence_manifest(
            mission,
            (card("accepted"),),
            (VerificationDecision("mission_1", "accepted", ReviewStatus.ACCEPTED, "complete"),),
        )
        with tempfile.TemporaryDirectory() as directory:
            path = write_mission_report(Path(directory), report)
            payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(payload["evidence_ids"], ["accepted"])
        self.assertNotIn("synthetic short quote", json.dumps(payload))


if __name__ == "__main__":
    unittest.main()
