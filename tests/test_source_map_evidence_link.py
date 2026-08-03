import json
import tempfile
import unittest
from pathlib import Path

from cosmatter.ingestion import EvidenceIngestionError, ingest_evidence_draft
from cosmatter.source_map import source_map_from_review, write_source_map
from tests.test_ingestion import draft


class SourceMapEvidenceLinkTests(unittest.TestCase):
    def _run(self, root: Path) -> Path:
        run_dir = root / "run_1"
        run_dir.mkdir()
        (run_dir / "mission.json").write_text(json.dumps({"mission_id": "mission_1"}), encoding="utf-8")
        (run_dir / "retrieval_candidates.json").write_text(
            json.dumps({"candidates": [{"document_id": "doc_1", "is_content_accessible": True}]}), encoding="utf-8"
        )
        source_map = source_map_from_review(
            mission_id="mission_1",
            document_id="doc_1",
            source_task={"document_id": "doc_1", "provider": "mineru", "task_id": "task_1", "state": "done"},
            selection={
                "document_id": "doc_1",
                "segments": [{"segment_id": "p1", "locator": "page:1", "kind": "paragraph", "quote": "Synthetic short quote only."}],
            },
        )
        write_source_map(run_dir, source_map)
        return run_dir

    def test_matching_source_map_quote_and_locator_can_be_ingested(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            decision = ingest_evidence_draft(self._run(Path(directory)), draft())
        self.assertEqual(decision.status.value, "accepted")

    def test_existing_source_map_rejects_paraphrase_or_wrong_locator(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run_dir = self._run(Path(directory))
            paraphrase = draft()
            paraphrase["quote"] = "Paraphrased but no longer exact."
            with self.assertRaises(EvidenceIngestionError):
                ingest_evidence_draft(run_dir, paraphrase)
            wrong_locator = draft()
            wrong_locator["provenance"] = dict(wrong_locator["provenance"], locator="page:2")
            with self.assertRaises(EvidenceIngestionError):
                ingest_evidence_draft(run_dir, wrong_locator)
