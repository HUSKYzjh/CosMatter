import json
import multiprocessing
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from unittest.mock import patch

from cosmatter.source_map import AUTOMATED_TRIAL_SOURCE_MAP_TRUST_STATUS, SourceMapAuditError, SourceMapConflictError, SourceMapError, iter_source_maps, load_source_map_for_document, record_confirmed_source_map, record_source_map_for_document, source_map_document_path, source_map_from_review, write_source_map, write_source_map_for_document


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


def _competing_writer(run_dir, review, barrier, results):
    barrier.wait(timeout=20)
    try:
        _, created = record_source_map_for_document(run_dir, review)
    except SourceMapConflictError:
        results.put(("conflict", review))
    else:
        results.put(("created" if created else "existing", review))


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

    def test_retries_and_conflicts_preserve_historical_review_and_identity(self) -> None:
        original = source_map_from_review(mission_id="mission_1", document_id="doc_1", source_task=completed_task(), selection=selection())
        different_review = source_map_from_review(mission_id="mission_1", document_id="doc_1", source_task=completed_task(), selection=selection("Another review"))
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            legacy = run / "source_map.json"
            original_bytes = json.dumps(original, indent=4).encode("utf-8")
            legacy.write_bytes(original_bytes)
            scoped = source_map_document_path(run, "doc_1")
            with self.assertRaises(SourceMapConflictError):
                write_source_map_for_document(run, different_review)
            self.assertFalse(scoped.exists())
            self.assertEqual(record_source_map_for_document(run, original), (scoped, False))
            original_scoped = scoped.stat().st_mtime_ns
            for writer in (write_source_map, write_source_map_for_document):
                writer(run, original)
                for replacement in (
                    different_review, original | {"mission_id": "another-mission"},
                    original | {"trust_status": AUTOMATED_TRIAL_SOURCE_MAP_TRUST_STATUS},
                    original | {"task_id_sha256": "b" * 64},
                    original | {"schema_version": "1.1", "source_markdown_sha256": "c" * 64},
                ):
                    with self.subTest(writer=writer.__name__, replacement=replacement), self.assertRaises(SourceMapConflictError):
                        writer(run, replacement)
            self.assertEqual(legacy.read_bytes(), original_bytes)
            self.assertEqual(scoped.stat().st_mtime_ns, original_scoped)
            self.assertEqual(json.loads(scoped.read_bytes()), original)

    def test_orphaned_confirmation_requires_original_request_and_one_audit_event(self) -> None:
        from cosmatter.source_map import _publish_json

        original = source_map_from_review(mission_id="mission_1", document_id="doc_1", source_task=completed_task(), selection=selection())
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)

            def confirm(review, **options):
                return record_confirmed_source_map(run, review, **options)

            def stop_before_first_map(path, payload):
                if path.name == "source_map.json":
                    raise OSError("simulated interruption before the first map")
                _publish_json(path, payload)

            with patch("cosmatter.source_map._publish_json", side_effect=stop_before_first_map), self.assertRaises(OSError):
                confirm(original)
            self.assertFalse((run / "source_map.json").exists())
            self.assertFalse(list((run / "source_maps").glob("*.json")))
            self.assertFalse((run / "events.jsonl").exists())
            with self.assertRaises(SourceMapConflictError):
                confirm(original | {"task_id_sha256": "c" * 64})
            with self.assertRaises(SourceMapConflictError):
                confirm(original, access_mode="human_authorized_private_pdf")
            with self.assertRaises(SourceMapConflictError):
                write_source_map_for_document(run, original)

            barrier = Barrier(2)

            def retry(_):
                barrier.wait(timeout=10)
                return confirm(original)

            with ThreadPoolExecutor(max_workers=2) as workers:
                paths = list(workers.map(retry, range(2)))
            self.assertEqual(paths[0], paths[1])
            self.assertEqual(paths[0].read_bytes(), (run / "source_map.json").read_bytes())
            self.assertFalse(list((run / "source_maps").glob("*.audit-pending")))
            audit = run / "events.jsonl"
            rows = [json.loads(line) for line in audit.read_bytes().splitlines()]
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["event_type"], "source_map_reviewed")
            damaged = audit.read_bytes() + b'{"incomplete"'
            audit.write_bytes(damaged)
            with self.assertRaisesRegex(SourceMapAuditError, "line 2"):
                confirm(original)
            self.assertEqual(audit.read_bytes(), damaged)

    def test_manual_and_historical_maps_do_not_acquire_new_review_events_on_retry(self) -> None:
        original = source_map_from_review(mission_id="mission_1", document_id="doc_1", source_task=completed_task(), selection=selection())
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            write_source_map(run, original)
            audit = run / "events.jsonl"
            record_confirmed_source_map(run, original)
            self.assertFalse(audit.exists())
            legacy_event = json.dumps({"event_type": "source_map_reviewed", "actor": "source_reviewer", "payload": {"document_id": "doc_1"}}).encode()
            audit.write_bytes(legacy_event)
            record_confirmed_source_map(run, original)
            self.assertEqual(audit.read_bytes(), legacy_event)

    def test_swapped_document_files_fail_closed_without_changing_legacy_reads(self) -> None:
        original = source_map_from_review(mission_id="mission_1", document_id="doc_1", source_task=completed_task(), selection=selection())
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            first = write_source_map_for_document(run, original)
            second = write_source_map_for_document(run, original | {"document_id": "doc_2"})
            first_bytes = first.read_bytes()
            first.write_bytes(second.read_bytes())
            second.write_bytes(first_bytes)
            for document in ("doc_1", "doc_2"):
                with self.assertRaisesRegex(SourceMapError, "document identity"):
                    load_source_map_for_document(run, "mission_1", document)
            with self.assertRaisesRegex(SourceMapError, "document identity"):
                iter_source_maps(run, "mission_1")
            self.assertEqual(load_source_map_for_document(run, "mission_1", None), original)

    def test_concurrent_first_record_has_one_winner_and_two_consistent_paths(self) -> None:
        context = multiprocessing.get_context("spawn")
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            reviews = [source_map_from_review(mission_id="mission_1", document_id="doc_1", source_task=completed_task(),
                       selection=selection(quote)) for quote in ("First specimen", "Second specimen")]
            barrier = context.Barrier(2)
            results = context.Queue()
            workers = [context.Process(target=_competing_writer, args=(run, review, barrier, results)) for review in reviews]
            try:
                for worker in workers:
                    worker.start()
                for worker in workers:
                    worker.join(30)
                    self.assertEqual(worker.exitcode, 0)
                outcomes = dict(results.get(timeout=5) for _ in workers)
                self.assertEqual(set(outcomes), {"created", "conflict"})
                scoped = source_map_document_path(run, "doc_1")
                self.assertEqual(json.loads(scoped.read_bytes()), outcomes["created"])
                self.assertEqual(json.loads((run / "source_map.json").read_bytes()), outcomes["created"])
                self.assertEqual(record_source_map_for_document(run, outcomes["created"]), (scoped, False))
            finally:
                for worker in workers:
                    if worker.is_alive():
                        worker.terminate()
                        worker.join(5)
                results.close()
