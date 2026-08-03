import json
import tempfile
import unittest
from pathlib import Path

from cosmatter.ingestion import EvidenceIngestionError, ingest_evidence_draft


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
        (run_dir / "retrieval_candidates.json").write_text(
            json.dumps({"candidates": [{"document_id": "doc_1", "is_content_accessible": accessible}]}),
            encoding="utf-8",
        )
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


if __name__ == "__main__":
    unittest.main()
