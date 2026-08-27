import json
import tempfile
import unittest
from pathlib import Path

from cosmatter.latex_report import LatexReportError, audit_latex_citations, export_latex_report
from cosmatter.models import AccessPolicy, EvidenceCard, MissionBrief, Provenance, ReviewStatus, Stance
from cosmatter.verification import VerificationDecision


def evidence(evidence_id: str = "evidence_1", document_id: str = "doi:10.1000/example") -> EvidenceCard:
    return EvidenceCard(
        claim="A reviewed synthetic claim.", stance=Stance.SUPPORT,
        material="BiFeO3", property_name="phase stability", conditions={"form": "film"},
        quote="reviewed short quote", provenance=Provenance(document_id, "page:2", "fixture", access_policy=AccessPolicy.LOCAL_ONLY),
        evidence_id=evidence_id,
    )


class LatexReportTests(unittest.TestCase):
    def test_export_has_bijective_citations_without_quotes_or_private_paths(self) -> None:
        mission = MissionBrief("question", "BiFeO3", "phase stability", "films", mission_id="latex_mission")
        card = evidence()
        with tempfile.TemporaryDirectory() as directory:
            export = export_latex_report(
                output_dir=Path(directory) / "submission", mission=mission, cards=(card,),
                decisions=(VerificationDecision("latex_mission", card.evidence_id, ReviewStatus.ACCEPTED, "reviewed"),),
                document_metadata=({"document_id": card.provenance.document_id, "title": "A bibliographic record", "doi": "10.1000/example", "source": "OpenAlex", "publication_year": 2025},),
            )
            tex, bib = export.tex_path.read_text(encoding="utf-8"), export.bib_path.read_text(encoding="utf-8")
            audit = json.loads(export.citation_audit_path.read_text(encoding="utf-8"))
            manifest = json.loads(export.manifest_path.read_text(encoding="utf-8"))
        self.assertIn("evidence\\_1", tex)
        self.assertIn("书目数据库/来源", tex)
        self.assertIn("OpenAlex", tex)
        self.assertIn("\\cite{cm_doi:10_1000_example_", tex)
        self.assertNotIn("reviewed short quote", tex)
        self.assertNotIn("D:/", tex + bib)
        self.assertTrue(audit["citation_bibliography_bijection"])
        self.assertEqual(audit["accepted_evidence_citation_coverage"], 1.0)
        self.assertEqual(manifest["bibliographic_sources"], ["OpenAlex"])
        self.assertEqual(manifest["bibliographic_source_count"], 1)
        self.assertTrue(manifest["every_accepted_evidence_row_discloses_bibliographic_source"])

    def test_export_rejects_metadata_without_a_disclosed_source(self) -> None:
        mission = MissionBrief("question", "BiFeO3", "phase stability", "films", mission_id="latex_mission")
        card = evidence()
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(LatexReportError):
                export_latex_report(
                    output_dir=Path(directory), mission=mission, cards=(card,),
                    decisions=(VerificationDecision("latex_mission", card.evidence_id, ReviewStatus.ACCEPTED, "reviewed"),),
                    document_metadata=({"document_id": card.provenance.document_id, "title": "A bibliographic record"},),
                )


    def test_export_rejects_accepted_card_without_metadata(self) -> None:
        mission = MissionBrief("question", "BiFeO3", "phase stability", "films", mission_id="latex_mission")
        card = evidence()
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(LatexReportError):
                export_latex_report(
                    output_dir=Path(directory), mission=mission, cards=(card,),
                    decisions=(VerificationDecision("latex_mission", card.evidence_id, ReviewStatus.ACCEPTED, "reviewed"),),
                    document_metadata=(),
                )

    def test_citation_audit_rejects_uncited_bibliography_entry(self) -> None:
        card = evidence()
        with self.assertRaises(LatexReportError):
            audit_latex_citations(
                tex="No citation.", bibliography="@misc{key, title={x}}", accepted_cards=(card,),
                cite_keys={card.provenance.document_id: "key"},
            )


if __name__ == "__main__":
    unittest.main()
