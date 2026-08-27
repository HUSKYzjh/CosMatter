from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from cosmatter.pdf_task_registry import PdfTaskRegistryError, assert_pdf_task_slot, load_pdf_tasks, task_for_pdf_document, write_pdf_task


def task(document_id: str, candidate_document_id: str | None = None) -> dict[str, object]:
    return {
        "schema_version": "1.0", "mission_id": "mission-1", "document_id": document_id,
        "candidate_document_id": candidate_document_id, "file_name": f"{document_id}.pdf",
        "pdf_sha256": "a" * 64, "byte_count": 10, "consent": True, "batch_id": f"batch-{document_id}",
        "state": "pending", "markdown_sha256": None, "doi": None, "doi_status": "pending",
    }


class PdfTaskRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.run_dir = Path(self.directory.name)

    def tearDown(self) -> None:
        self.directory.cleanup()

    def test_keeps_two_document_tasks_without_overwrite(self) -> None:
        write_pdf_task(self.run_dir, "mission-1", task("pdf_a", "candidate-a"))
        write_pdf_task(self.run_dir, "mission-1", task("pdf_b", "candidate-b"))
        self.assertEqual(["pdf_a", "pdf_b"], [item["document_id"] for item in load_pdf_tasks(self.run_dir, "mission-1")])
        self.assertEqual("candidate-a", task_for_pdf_document(self.run_dir, "mission-1", "pdf_a")["candidate_document_id"])

    def test_rejects_two_private_tasks_for_one_screened_candidate(self) -> None:
        write_pdf_task(self.run_dir, "mission-1", task("pdf_a", "candidate-a"))
        with self.assertRaisesRegex(PdfTaskRegistryError, "already exists"):
            write_pdf_task(self.run_dir, "mission-1", task("pdf_b", "candidate-a"))

    def test_preflight_rejects_active_candidate_but_allows_failed_retry(self) -> None:
        active = task("pdf_active", "candidate-a")
        write_pdf_task(self.run_dir, "mission-1", active)
        with self.assertRaisesRegex(PdfTaskRegistryError, "non-failed"):
            assert_pdf_task_slot(self.run_dir, "mission-1", "candidate-a")
        active["state"] = "failed"
        write_pdf_task(self.run_dir, "mission-1", active)
        assert_pdf_task_slot(self.run_dir, "mission-1", "candidate-a")
    def test_projects_a_legacy_single_task_without_rewriting_it(self) -> None:
        (self.run_dir / "pdf_intake.json").write_text(json.dumps(task("pdf_legacy")), encoding="utf-8")
        self.assertEqual("pdf_legacy", task_for_pdf_document(self.run_dir, "mission-1")["document_id"])
        self.assertFalse((self.run_dir / "pdf_intake_tasks.json").exists())

    def test_allows_a_failed_candidate_task_to_be_replaced(self) -> None:
        first = task("pdf_first", candidate_document_id="candidate-1")
        first["state"] = "failed"
        replacement = task("pdf_retry", candidate_document_id="candidate-1")
        write_pdf_task(self.run_dir, "mission-1", first)
        write_pdf_task(self.run_dir, "mission-1", replacement)
        self.assertEqual(["pdf_retry"], [item["document_id"] for item in load_pdf_tasks(self.run_dir, "mission-1")])
    def test_requires_explicit_document_after_multiple_tasks_exist(self) -> None:
        write_pdf_task(self.run_dir, "mission-1", task("pdf_a"))
        write_pdf_task(self.run_dir, "mission-1", task("pdf_b"))
        with self.assertRaisesRegex(PdfTaskRegistryError, "document_id is required"):
            task_for_pdf_document(self.run_dir, "mission-1")


if __name__ == "__main__":
    unittest.main()