import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cosmatter.cli import main
from cosmatter.corpus_preparation import (
    CorpusPreparationError,
    candidates_from_authorized_corpus_manifest,
    corpus_manifest_from_review,
    corpus_manifest_from_selection_review,
    corpus_selection_template_from_zotero_candidates,
    gold_standard_template_from_manifest,
)
from cosmatter.models import PaperCandidate
from cosmatter.models import MissionBrief


def selection() -> dict[str, object]:
    return {
        "corpus_id": "bfo_90_v1",
        "material": "BiFeO3",
        "documents": [
            {
                "document_id": "bfo_001",
                "title": "Synthetic bibliographic title one",
                "doi": None,
                "access_policy": "institutional_access_internal_review_only",
            },
            {
                "document_id": "bfo_002",
                "title": "Synthetic bibliographic title two",
                "doi": "10.0000/synthetic.2",
                "access_policy": "institutional_access_internal_review_only",
            },
        ],
    }


class CorpusPreparationTests(unittest.TestCase):
    def test_manifest_is_path_free_and_gold_template_starts_blank(self) -> None:
        manifest = corpus_manifest_from_review(
            mission_id="mission_1", material="BiFeO3", selection=selection()
        )
        template = gold_standard_template_from_manifest(manifest)
        candidates = candidates_from_authorized_corpus_manifest(manifest, "BiFeO3 phase review")

        self.assertEqual(manifest["access_boundary"], "institutional_access_local_review_only_no_fulltext_redistribution")
        self.assertEqual([item["document_id"] for item in template["documents"]], ["bfo_001", "bfo_002"])
        self.assertTrue(all(item["retrieval_relevance"] == "unreviewed" for item in template["documents"]))
        self.assertTrue(all(item.is_content_accessible and item.score is None for item in candidates))
        self.assertEqual(candidates[0].source, "Authorized local corpus manifest")

    def test_manifest_rejects_local_paths_and_material_mismatch(self) -> None:
        unsafe = selection()
        unsafe["documents"][0]["local_path"] = "D:/private/paper.pdf"
        with self.assertRaises(CorpusPreparationError):
            corpus_manifest_from_review(mission_id="mission_1", material="BiFeO3", selection=unsafe)
        with self.assertRaises(CorpusPreparationError):
            corpus_manifest_from_review(mission_id="mission_1", material="Other", selection=selection())


    def test_manifest_normalizes_dois_and_rejects_duplicate_doi_aliases(self) -> None:
        reviewed = selection()
        reviewed["documents"][1]["doi"] = "https://doi.org/10.0000/SYNTHETIC.2"
        manifest = corpus_manifest_from_review(mission_id="mission_1", material="BiFeO3", selection=reviewed)
        self.assertEqual(manifest["documents"][1]["doi"], "10.0000/synthetic.2")
        duplicate = selection()
        duplicate["documents"][0]["doi"] = "doi:10.0000/SYNTHETIC.2"
        with self.assertRaisesRegex(CorpusPreparationError, "duplicate normalized DOIs"):
            corpus_manifest_from_review(mission_id="mission_1", material="BiFeO3", selection=duplicate)


    def test_cli_records_manifest_then_creates_blank_template(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runs = Path(directory)
            run = runs / "corpus_cli"
            run.mkdir()
            mission = MissionBrief(
                question="q",
                material="BiFeO3",
                property_name="phase",
                scope="scope",
                mission_id="mission_1",
            )
            (run / "mission.json").write_text(json.dumps(mission.to_dict()), encoding="utf-8")
            input_path = run / "selection.json"
            input_path.write_text(json.dumps(selection()), encoding="utf-8")
            output = io.StringIO()
            with patch("cosmatter.cli._runs_dir", return_value=runs), contextlib.redirect_stdout(output):
                status_manifest = main(["record-corpus-manifest", "--run-id", "corpus_cli", "--input", str(input_path)])
                status_template = main(["create-gold-standard-template", "--run-id", "corpus_cli"])
                status_candidates = main(["seed-authorized-corpus-candidates", "--run-id", "corpus_cli"])
            manifest = json.loads((run / "corpus_manifest.json").read_text(encoding="utf-8"))
            template = json.loads((run / "human_gold_standard_template.json").read_text(encoding="utf-8"))
            candidates = json.loads((run / "retrieval_candidates.json").read_text(encoding="utf-8"))
        self.assertEqual(status_manifest, 0, output.getvalue())
        self.assertEqual(status_template, 0, output.getvalue())
        self.assertEqual(status_candidates, 0, output.getvalue())
        self.assertEqual(manifest["documents"][0]["document_id"], "bfo_001")
        self.assertEqual(template["trust_status"], "blank_human_annotation_template_not_evaluation_result")
        self.assertEqual(candidates["candidates"][0]["source"], "Authorized local corpus manifest")
        self.assertIsNone(candidates["candidates"][0]["score"])


    def test_zotero_selection_template_requires_explicit_review_and_preserves_metadata_only_boundary(self) -> None:
        candidates = (
            PaperCandidate(
                document_id="zotero:BFO1", title="BiFeO3 thin films", query="BiFeO3",
                source="Local Zotero metadata", publication_year=2023,
                locator_hint="metadata:title,tags", doi="10.1000/bfo.1",
            ),
            PaperCandidate(
                document_id="zotero:BFO2", title="BiFeO3 phase studies", query="BiFeO3",
                source="Local Zotero metadata", publication_year=2022,
                locator_hint="metadata:title,tags", doi=None,
            ),
        )
        template = corpus_selection_template_from_zotero_candidates(
            mission_id="mission_1", material="BiFeO3", corpus_id="bfo_90_v1",
            query="BiFeO3", candidates=candidates,
        )
        self.assertEqual(template["trust_status"], "blank_human_corpus_selection_template_not_manifest")
        self.assertNotIn("attachment", json.dumps(template))
        with self.assertRaises(CorpusPreparationError):
            corpus_manifest_from_selection_review(
                mission_id="mission_1", material="BiFeO3", review=template
            )
        tampered = json.loads(json.dumps(template))
        tampered["trust_status"] = "human_reviewed_corpus_selection_for_manifest"
        tampered["candidates"][0]["include_for_corpus"] = True
        tampered["candidates"][0]["review_reason"] = "In scope."
        tampered["candidates"][1]["include_for_corpus"] = False
        tampered["candidates"][1]["review_reason"] = "Out of scope."
        tampered["candidates"][0]["title"] = "Replacement candidate"
        with self.assertRaises(CorpusPreparationError):
            corpus_manifest_from_selection_review(
                mission_id="mission_1", material="BiFeO3", review=tampered
            )
        template["trust_status"] = "human_reviewed_corpus_selection_for_manifest"
        template["candidates"][0]["include_for_corpus"] = True
        template["candidates"][0]["review_reason"] = "BiFeO3 thin-film primary study."
        template["candidates"][1]["include_for_corpus"] = False
        template["candidates"][1]["review_reason"] = "Outside the chosen thin-film scope."
        manifest = corpus_manifest_from_selection_review(
            mission_id="mission_1", material="BiFeO3", review=template
        )
        self.assertEqual([item["document_id"] for item in manifest["documents"]], ["zotero:BFO1"])
        self.assertEqual(manifest["documents"][0]["access_policy"], "institutional_access_internal_review_only")

    def test_cli_zotero_template_then_human_review_freezes_only_selected_papers(self) -> None:
        export = [
            {
                "key": "BFO1", "title": "BiFeO3 thin films", "date": "2023",
                "DOI": "10.1000/bfo.1", "tags": ["ferroelectric"],
                "attachments": [{"path": "C:/private/paper.pdf"}],
                "abstractNote": "private abstract",
            },
            {"key": "BFO2", "title": "BiFeO3 phase studies", "date": "2022"},
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runs = root / "runs"
            run = runs / "zotero_selection"
            run.mkdir(parents=True)
            mission = MissionBrief(
                question="Compare BiFeO3 phase stability in thin films.",
                material="BiFeO3", property_name="phase stability",
                scope="epitaxial thin films", mission_id="mission_zotero",
            )
            (run / "mission.json").write_text(json.dumps(mission.to_dict()), encoding="utf-8")
            export_path = root / "zotero.json"
            export_path.write_text(json.dumps(export), encoding="utf-8")
            output = io.StringIO()
            with patch("cosmatter.cli._runs_dir", return_value=runs), contextlib.redirect_stdout(output):
                status_template = main([
                    "create-corpus-selection-template-from-zotero",
                    "--run-id", "zotero_selection", "--input", str(export_path),
                    "--query", "BiFeO3", "--corpus-id", "bfo_90_v1", "--top-k", "90",
                ])
            template_path = run / "corpus_selection_template.json"
            template = json.loads(template_path.read_text(encoding="utf-8"))
            self.assertEqual(status_template, 0, output.getvalue())
            self.assertNotIn("private abstract", json.dumps(template))
            self.assertNotIn("private/paper.pdf", json.dumps(template))
            template["trust_status"] = "human_reviewed_corpus_selection_for_manifest"
            template["candidates"][0]["include_for_corpus"] = True
            template["candidates"][0]["review_reason"] = "In scope."
            template["candidates"][1]["include_for_corpus"] = False
            template["candidates"][1]["review_reason"] = "Excluded after scope review."
            reviewed_path = root / "reviewed_selection.json"
            reviewed_path.write_text(json.dumps(template), encoding="utf-8")
            with patch("cosmatter.cli._runs_dir", return_value=runs), contextlib.redirect_stdout(output):
                status_manifest = main([
                    "record-corpus-manifest-from-selection-review",
                    "--run-id", "zotero_selection", "--input", str(reviewed_path),
                ])
            manifest = json.loads((run / "corpus_manifest.json").read_text(encoding="utf-8"))
            events = (run / "events.jsonl").read_text(encoding="utf-8")
        self.assertEqual(status_manifest, 0, output.getvalue())
        self.assertEqual([item["document_id"] for item in manifest["documents"]], ["zotero:BFO1"])
        self.assertNotIn(str(export_path), events)
        self.assertIn("authorized_corpus_manifest_recorded_from_human_selection", events)


if __name__ == "__main__":
    unittest.main()
