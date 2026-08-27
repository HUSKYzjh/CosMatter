from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from cosmatter.deepseek import DraftCompletion
from cosmatter.mineru_local_review import prepare_mineru_markdown_review_pool
from cosmatter.potential_scope_auto_triage import untrusted_triage_from_completion
from cosmatter.potential_scope_batch_approval import (
    PotentialScopeBatchApprovalError,
    build_batch_approval_template,
    build_registry_from_batch_approval,
)


class PotentialScopeBatchApprovalTests(unittest.TestCase):
    def test_one_document_approval_projects_quote_free_registry(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            markdown = root / "private.md"
            markdown.write_text("Private potential scope observation.", encoding="utf-8")
            task = {"document_id": "ps_doc_01", "provider": "mineru", "state": "done", "task_id": "task-1"}
            pool = prepare_mineru_markdown_review_pool(mission_id="ps_mission", document_id="ps_doc_01", source_task=task, input_path=markdown, output_path=root / "pool.json")
            draft = untrusted_triage_from_completion(pool=pool, completion=DraftCompletion(content=json.dumps({"document_id": "ps_doc_01", "proposals": [{"segment_id": "mineru_md_001", "roles": ["potential_model_scope"], "reason": "Scope context.", "confidence": 0.8}]}), model="fake", request_id=None))
            approval = build_batch_approval_template(mission_id="ps_mission", drafts=[draft])
            approval.update({"trust_status": "human_approved_batch_potential_scope_triage_decision", "reviewer": "Reviewer", "reviewed_at": "2026-08-20"})
            approval["documents"][0]["decision"] = "approved"
            registry, audit = build_registry_from_batch_approval(mission_id="ps_mission", drafts=[draft], approval=approval, pools_by_document={"ps_doc_01": root / "pool.json"}, source_tasks_by_document={"ps_doc_01": task})
            rendered = json.dumps({"registry": registry, "audit": audit}, ensure_ascii=False)
            self.assertEqual(registry["sources"][0]["selected_segment_count"], 1)
            self.assertNotIn("Private potential scope observation", rendered)
            self.assertNotIn("markdown_line", rendered)

    def test_stale_approval_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            markdown = root / "private.md"
            markdown.write_text("Private scope observation.", encoding="utf-8")
            task = {"document_id": "ps_doc_01", "provider": "mineru", "state": "done", "task_id": "task-1"}
            pool = prepare_mineru_markdown_review_pool(mission_id="ps_mission", document_id="ps_doc_01", source_task=task, input_path=markdown, output_path=root / "pool.json")
            draft = untrusted_triage_from_completion(pool=pool, completion=DraftCompletion(content=json.dumps({"document_id": "ps_doc_01", "proposals": [{"segment_id": "mineru_md_001", "roles": ["known_limitation"], "reason": "Boundary.", "confidence": 0.8}]}), model="fake", request_id=None))
            approval = build_batch_approval_template(mission_id="ps_mission", drafts=[draft])
            approval.update({"trust_status": "human_approved_batch_potential_scope_triage_decision", "reviewer": "Reviewer", "reviewed_at": "2026-08-20"})
            approval["documents"][0].update({"decision": "approved", "triage_sha256": "0" * 64})
            with self.assertRaises(PotentialScopeBatchApprovalError):
                build_registry_from_batch_approval(mission_id="ps_mission", drafts=[draft], approval=approval, pools_by_document={"ps_doc_01": root / "pool.json"}, source_tasks_by_document={"ps_doc_01": task})


if __name__ == "__main__":
    unittest.main()
