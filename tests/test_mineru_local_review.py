import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cosmatter.cli import main
from cosmatter.mineru import MinerUTask
from cosmatter.mineru_local_review import MinerULocalReviewError, prepare_mineru_markdown_review_pool, source_map_pool_review_template, source_map_selection_from_pool_review, write_source_map_pool_review_selection
from cosmatter.models import MissionBrief
from cosmatter.source_parse import record_source_parse_task
from cosmatter.source_map import AUTOMATED_TRIAL_SOURCE_MAP_TRUST_STATUS, source_map_from_pool_review


class MinerULocalReviewTests(unittest.TestCase):
    def test_pool_is_bounded_private_and_does_not_store_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_path = root / "mineru.md"
            output_path = root / "private_pool.json"
            input_path.write_text(
                "# Result\n\nA short reviewed candidate.\n\n"
                + "Long finding " * 120
                + "\n\n| a | b |\n| - | - |\n| 1 | 2 |\n",
                encoding="utf-8",
            )
            pool = prepare_mineru_markdown_review_pool(
                mission_id="mission_1",
                document_id="doc_1",
                source_task={"document_id": "doc_1", "provider": "mineru", "state": "done", "task_id": "task_1"},
                input_path=input_path,
                output_path=output_path,
            )
            raw = output_path.read_text(encoding="utf-8")
        self.assertEqual(pool["trust_status"], "private_unreviewed_mineru_markdown_candidate_pool_not_source_map")
        self.assertNotIn(str(input_path), raw)
        self.assertNotIn(str(output_path), raw)
        self.assertLessEqual(len(pool["candidate_segments"]), 48)
        self.assertTrue(all(len(item["quote"]) <= 500 for item in pool["candidate_segments"]))
        self.assertTrue(any(item["kind"] == "table" for item in pool["candidate_segments"]))

    def test_requires_done_task_and_never_overwrites(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_path = root / "mineru.md"
            output_path = root / "pool.json"
            input_path.write_text("One candidate.", encoding="utf-8")
            output_path.write_text("existing", encoding="utf-8")
            task = {"document_id": "doc_1", "provider": "mineru", "state": "done", "task_id": "task_1"}
            with self.assertRaises(MinerULocalReviewError):
                prepare_mineru_markdown_review_pool(mission_id="mission_1", document_id="doc_1", source_task={**task, "state": "pending"}, input_path=input_path, output_path=root / "new.json")
            with self.assertRaises(MinerULocalReviewError):
                prepare_mineru_markdown_review_pool(mission_id="mission_1", document_id="doc_1", source_task=task, input_path=input_path, output_path=output_path)


    def test_review_template_resolves_exact_pool_segments_into_hash_bound_source_map(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_path = root / "mineru.md"
            pool_path = root / "pool.json"
            input_path.write_text("First exact finding.\n\nSecond exact finding.", encoding="utf-8")
            task = {"document_id": "doc_1", "provider": "mineru", "state": "done", "task_id": "task_1"}
            pool = prepare_mineru_markdown_review_pool(mission_id="mission_1", document_id="doc_1", source_task=task, input_path=input_path, output_path=pool_path)
            review = source_map_pool_review_template(pool)
            review["trust_status"] = "human_reviewed_source_map_pool_selection"
            review["segments"][0]["selected"] = True
            review["segments"][0]["reason"] = "Supports the target phase-condition comparison."
            selection, markdown_sha256 = source_map_selection_from_pool_review(pool=pool, review=review)
            source_map = source_map_from_pool_review(mission_id="mission_1", document_id="doc_1", source_task=task, selection=selection, source_markdown_sha256=markdown_sha256)
        self.assertEqual(source_map["schema_version"], "1.1")
        self.assertEqual(source_map["source_markdown_sha256"], pool["source_markdown_sha256"])
        self.assertEqual(source_map["segments"][0]["quote"], "First exact finding.")

    def test_delegated_automated_trial_selection_stays_distinct_from_human_review(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_path = root / "mineru.md"
            pool_path = root / "pool.json"
            input_path.write_text("First exact finding.", encoding="utf-8")
            task = {"document_id": "doc_1", "provider": "mineru", "state": "done", "task_id": "task_1"}
            pool = prepare_mineru_markdown_review_pool(mission_id="mission_1", document_id="doc_1", source_task=task, input_path=input_path, output_path=pool_path)
            review = source_map_pool_review_template(pool, delegated_automated_trial=True)
            review["trust_status"] = "delegated_automated_trial_source_map_pool_selection"
            review["segments"][0]["selected"] = True
            review["segments"][0]["reason"] = "Direct support for authorized trial question."
            review["trust_status"] = "delegated_automated_trial_source_map_pool_selection"
            selection_path = root / "selection.json"
            write_source_map_pool_review_selection(selection_path, review, delegated_automated_trial=True)
            selection_exists = selection_path.exists()
            selection, digest = source_map_selection_from_pool_review(pool=pool, review=review, delegated_automated_trial=True)
            source_map = source_map_from_pool_review(
                mission_id="mission_1",
                document_id="doc_1",
                source_task=task,
                selection=selection,
                source_markdown_sha256=digest,
                trust_status=AUTOMATED_TRIAL_SOURCE_MAP_TRUST_STATUS,
            )
        self.assertEqual(source_map["trust_status"], AUTOMATED_TRIAL_SOURCE_MAP_TRUST_STATUS)
        self.assertTrue(selection_exists)

    def test_cli_writes_no_markdown_or_path_into_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runs_dir = root / "runs"
            run_dir = runs_dir / "mineru_local"
            run_dir.mkdir(parents=True)
            mission = MissionBrief(question="test question", material="BiFeO3", property_name="phase stability", scope="test scope", mission_id="mission_local")
            (run_dir / "mission.json").write_text(json.dumps(mission.to_dict()), encoding="utf-8")
            record_source_parse_task(
                run_dir,
                mission_id=mission.mission_id,
                document_id="doc_1",
                source_url="https://publisher.example/paper.pdf",
                task=MinerUTask("task_1", "done", "request_1"),
                model_version="vlm",
            )
            input_path = root / "private_mineru.md"
            output_path = root / "private_pool.json"
            secret_excerpt = "A locally parsed finding that must not enter the run."
            input_path.write_text(secret_excerpt, encoding="utf-8")
            output = io.StringIO()
            with patch("cosmatter.cli._runs_dir", return_value=runs_dir), contextlib.redirect_stdout(output):
                status = main([
                    "prepare-mineru-markdown-review",
                    "--run-id", "mineru_local",
                    "--document-id", "doc_1",
                    "--input", str(input_path),
                    "--output", str(output_path),
                ])
            audit = (run_dir / "events.jsonl").read_text(encoding="utf-8")
            run_text = "\n".join(item.read_text(encoding="utf-8") for item in run_dir.rglob("*") if item.is_file())
            output_exists = output_path.exists()
        self.assertEqual(status, 0, output.getvalue())
        self.assertTrue(output_exists)
        self.assertNotIn(secret_excerpt, output.getvalue())
        self.assertNotIn(secret_excerpt, audit)
        self.assertNotIn(secret_excerpt, run_text)
        self.assertNotIn(str(input_path), audit)
        self.assertNotIn(str(output_path), audit)
