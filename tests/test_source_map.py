import tempfile
import unittest
from pathlib import Path

from cosmatter.source_map import SourceMapError, source_map_from_review, write_source_map


def completed_task() -> dict[str, str]:
    return {
        "document_id": "doc_1",
        "provider": "mineru",
        "source_url_sha256": "a" * 64,
        "task_id": "task_1",
        "state": "done",
        "model_version": "vlm",
    }


def selection(quote: str = "Short reviewer-selected source excerpt.") -> dict[str, object]:
    return {
        "document_id": "doc_1",
        "segments": [{"segment_id": "p1", "locator": "p. 2, para. 3", "kind": "paragraph", "quote": quote}],
    }


class SourceMapTests(unittest.TestCase):
    def test_completed_task_can_create_bounded_human_reviewed_map(self) -> None:
        source_map = source_map_from_review(
            mission_id="mission_1", document_id="doc_1", source_task=completed_task(), selection=selection()
        )
        with tempfile.TemporaryDirectory() as directory:
            path = write_source_map(Path(directory), source_map)
            raw = path.read_text(encoding="utf-8")

        self.assertEqual(source_map["trust_status"], "human_reviewed_parser_selection")
        self.assertNotIn("task_1", raw)
        self.assertEqual(len(source_map["segments"][0]["quote_sha256"]), 64)

    def test_map_rejects_incomplete_task_or_unbounded_quote(self) -> None:
        pending = completed_task() | {"state": "pending"}
        with self.assertRaises(SourceMapError):
            source_map_from_review(mission_id="mission_1", document_id="doc_1", source_task=pending, selection=selection())
        with self.assertRaises(SourceMapError):
            source_map_from_review(
                mission_id="mission_1", document_id="doc_1", source_task=completed_task(), selection=selection("x" * 501)
            )
