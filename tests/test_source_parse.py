import json
import tempfile
import unittest
from pathlib import Path

from cosmatter.mineru import MinerUTask
from cosmatter.source_parse import load_source_parse_tasks, migrate_legacy_source_parse_task_ids, private_task_id_for_document, record_source_parse_task, task_for_document, update_source_parse_task


class SourceParseArtifactTests(unittest.TestCase):
    def test_task_ledger_stores_hash_and_status_but_not_source_or_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            source_url = "https://publisher.example/paper.pdf?temporary=opaque"
            path = record_source_parse_task(
                run_dir,
                mission_id="mission_test",
                document_id="doc_1",
                source_url=source_url,
                task=MinerUTask(task_id="task_1", state="pending", request_id="ignored"),
                model_version="vlm",
            )
            update_source_parse_task(
                run_dir,
                mission_id="mission_test",
                document_id="doc_1",
                task=MinerUTask(task_id="task_1", state="done", request_id="ignored"),
            )
            raw = path.read_text(encoding="utf-8")
            ledger = load_source_parse_tasks(path, "mission_test")
            self.assertNotIn(source_url, raw)
            self.assertNotIn("task_1", raw)
            self.assertNotIn("ignored", raw)
            self.assertEqual(task_for_document(run_dir, mission_id="mission_test", document_id="doc_1")["state"], "done")
            self.assertEqual(len(ledger["tasks"][0]["source_url_sha256"]), 64)
            self.assertEqual(len(ledger["tasks"][0]["task_id"]), 64)
            self.assertEqual(private_task_id_for_document(run_dir, mission_id="mission_test", document_id="doc_1"), "task_1")

    def test_migrates_legacy_raw_task_id_out_of_the_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            (run_dir / "source_parse_tasks.json").write_text(
                json.dumps(
                    {
                        "schema_version": "1.0",
                        "mission_id": "mission_migrate",
                        "tasks": [
                            {
                                "document_id": "doc_1",
                                "provider": "mineru",
                                "source_url_sha256": "a" * 64,
                                "task_id": "legacy_private_task",
                                "state": "done",
                                "model_version": "vlm",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(migrate_legacy_source_parse_task_ids(run_dir, mission_id="mission_migrate"), 1)
            raw = (run_dir / "source_parse_tasks.json").read_text(encoding="utf-8")
            task = task_for_document(run_dir, mission_id="mission_migrate", document_id="doc_1")

        self.assertNotIn("legacy_private_task", raw)
        self.assertEqual(len(task["task_id"]), 64)
