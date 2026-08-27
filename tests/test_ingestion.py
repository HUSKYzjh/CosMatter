import json
import tempfile
import unittest
from pathlib import Path

from cosmatter.candidate_screening import candidate_screening_from_review, write_candidate_screening
from cosmatter.ingestion import EvidenceIngestionError, ingest_evidence_draft
from cosmatter.source_map import source_map_from_review, write_source_map_for_document


def draft(document_id: str = "doc_1") -> dict[str, object]:
    return {
        "claim": "Synthetic extracted claim",
        "stance": "support",
        "material": "BiFeO3",
        "property_name": "phase stability",
        "conditions": {
            "sample_form": "film",
            "strain_percent": -2.0,
            "substrate": "synthetic",
            "thickness_nm": 30,
            "temperature_k": 300,
            "method": "synthetic method",
        },
        "quote": "Synthetic short quote only.",
        "provenance": {"document_id": document_id, "locator": "page:1", "source": "fixture", "access_policy": "authorized"},
        "extractor_confidence": 0.8,
        "evidence_id": "evidence_1",
    }


class EvidenceIngestionTests(unittest.TestCase):
    def _run(self, root: Path, accessible: bool = True) -> Path:
        run_dir = root / "run_1"
        run_dir.mkdir(parents=True)
        (run_dir / "mission.json").write_text(json.dumps({"mission_id": "mission_1"}), encoding="utf-8")
        candidates = {"candidates": [{"document_id": "doc_1", "is_content_accessible": accessible}]}
        (run_dir / "retrieval_candidates.json").write_text(json.dumps(candidates), encoding="utf-8")
        screening = candidate_screening_from_review(
            "mission_1", candidates,
            {"decisions": [{"document_id": "doc_1", "decision": "include_for_fulltext", "reason_codes": ["material_match"]}]},
        )
        write_candidate_screening(run_dir, screening)
        source_map = source_map_from_review(
            mission_id="mission_1", document_id="doc_1",
            source_task={"provider": "mineru", "task_id": "task_1", "state": "done", "document_id": "doc_1"},
            selection={"document_id": "doc_1", "segments": [{"segment_id": "s1", "locator": "page:1", "kind": "paragraph", "quote": "Synthetic short quote only."}]},
        )
        write_source_map_for_document(run_dir, source_map)
        return run_dir

    def test_ingestion_persists_a_card_and_accepted_decision(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run_dir = self._run(Path(directory))
            decision = ingest_evidence_draft(run_dir, draft())
            cards = json.loads((run_dir / "evidence_cards.json").read_text(encoding="utf-8"))

        self.assertEqual(decision.status.value, "accepted")
        self.assertEqual(cards[0]["provenance"]["document_id"], "doc_1")

    def test_ingestion_rejects_unavailable_candidate_and_raw_text_fields(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run_dir = self._run(Path(directory), accessible=False)
            with self.assertRaises(EvidenceIngestionError):
                ingest_evidence_draft(run_dir, draft())
            accessible_run = self._run(Path(directory) / "other")
            unsafe = draft()
            unsafe["full_text"] = "not allowed"
            with self.assertRaises(EvidenceIngestionError):
                ingest_evidence_draft(accessible_run, unsafe)

    def test_ingestion_rejects_missing_screening_or_source_map(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run_dir = self._run(Path(directory))
            (run_dir / "candidate_screening.json").unlink()
            with self.assertRaisesRegex(EvidenceIngestionError, "completed human candidate screening"):
                ingest_evidence_draft(run_dir, draft())
            self._run(Path(directory) / "other")
            other_run = Path(directory) / "other" / "run_1"
            for path in (other_run / "source_map.json", * (other_run / "source_maps").glob("*.json")):
                if path.exists():
                    path.unlink()
            with self.assertRaisesRegex(EvidenceIngestionError, "requires a reviewed source-map"):
                ingest_evidence_draft(other_run, draft())

    def test_ingestion_enforces_the_source_map_of_each_document(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run_dir = self._run(Path(directory))
            candidates = {"candidates": [
                {"document_id": "doc_1", "is_content_accessible": True},
                {"document_id": "doc_2", "is_content_accessible": True},
            ]}
            (run_dir / "retrieval_candidates.json").write_text(json.dumps(candidates), encoding="utf-8")
            screening = candidate_screening_from_review(
                "mission_1", candidates,
                {"decisions": [
                    {"document_id": "doc_1", "decision": "include_for_fulltext", "reason_codes": ["material_match"]},
                    {"document_id": "doc_2", "decision": "include_for_fulltext", "reason_codes": ["material_match"]},
                ]},
            )
            write_candidate_screening(run_dir, screening)
            task = {"provider": "mineru", "task_id": "task_2", "state": "done", "document_id": "doc_2"}
            selection = {"document_id": "doc_2", "segments": [{"segment_id": "s2", "locator": "page:2", "kind": "paragraph", "quote": "Reviewed second-document excerpt."}]}
            source_map = source_map_from_review(mission_id="mission_1", document_id="doc_2", source_task=task, selection=selection)
            write_source_map_for_document(run_dir, source_map)

            mismatched = draft("doc_2")
            with self.assertRaises(EvidenceIngestionError):
                ingest_evidence_draft(run_dir, mismatched)

            reviewed = draft("doc_2")
            reviewed["quote"] = "Reviewed second-document excerpt."
            reviewed["provenance"] = {"document_id": "doc_2", "locator": "page:2", "source": "fixture", "access_policy": "authorized"}
            reviewed["evidence_id"] = "evidence_2"
            decision = ingest_evidence_draft(run_dir, reviewed)
        self.assertEqual(decision.status.value, "accepted")


if __name__ == "__main__":
    unittest.main()
