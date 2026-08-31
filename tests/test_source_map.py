import tempfile
import unittest
from pathlib import Path

from cosmatter.source_map import AUTOMATED_TRIAL_SOURCE_MAP_TRUST_STATUS, SourceMapError, source_map_document_path, source_map_from_review, write_source_map, write_source_map_for_document


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

    def test_delegated_automated_trial_source_map_is_explicitly_labelled(self) -> None:
        result = source_map_from_review(
            mission_id="mission_1",
            document_id="doc_1",
            source_task=completed_task(),
            selection=selection(),
            trust_status=AUTOMATED_TRIAL_SOURCE_MAP_TRUST_STATUS,
        )
        self.assertEqual(result["trust_status"], AUTOMATED_TRIAL_SOURCE_MAP_TRUST_STATUS)


    def test_document_scoped_writes_do_not_replace_another_document(self) -> None:
        first = source_map_from_review(mission_id="mission_1", document_id="doc_1", source_task=completed_task(), selection=selection())
        second_task = completed_task() | {"document_id": "doc_2", "task_id": "task_2"}
        second_selection = selection("Second document excerpt.") | {"document_id": "doc_2"}
        second = source_map_from_review(mission_id="mission_1", document_id="doc_2", source_task=second_task, selection=second_selection)
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            first_path = write_source_map_for_document(run_dir, first)
            second_path = write_source_map_for_document(run_dir, second)
            legacy = (run_dir / "source_map.json").read_text(encoding="utf-8")
        self.assertNotEqual(first_path, second_path)
        self.assertEqual(first_path.name, source_map_document_path(Path(directory), "doc_1").name)
        self.assertIn('"document_id": "doc_1"', legacy)
