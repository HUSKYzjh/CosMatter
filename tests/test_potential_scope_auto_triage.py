from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from cosmatter.deepseek import DraftCompletion
from cosmatter.mineru_local_review import prepare_mineru_markdown_review_pool
from cosmatter.potential_scope_auto_triage import (
    PotentialScopeAutoTriageError,
    potential_scope_triage_prompts,
    untrusted_triage_from_completion,
    write_untrusted_triage_draft,
)


class PotentialScopeAutoTriageTests(unittest.TestCase):
    def _pool(self, root: Path) -> dict[str, object]:
        markdown = root / "private.md"
        markdown.write_text("Potential-model scope note.\n\nReference calculation boundary.", encoding="utf-8")
        return prepare_mineru_markdown_review_pool(
            mission_id="potential_scope_p0_review_20260820",
            document_id="potential_scope_p0_0123456789abcdef",
            source_task={
                "document_id": "potential_scope_p0_0123456789abcdef",
                "provider": "mineru",
                "state": "done",
                "task_id": "private_manifest_test_task",
            },
            input_path=markdown,
            output_path=root / "pool.json",
        )

    def test_prompt_is_bounded_and_triage_output_is_quote_free(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pool = self._pool(root)
            system, user = potential_scope_triage_prompts(pool)
            self.assertLessEqual(len(system), 8_000)
            self.assertLessEqual(len(user), 20_000)
            completion = DraftCompletion(
                content=json.dumps({"document_id": pool["document_id"], "proposals": [{"segment_id": "mineru_md_001", "roles": ["potential_model_scope"], "reason": "Contains a scope boundary.", "confidence": 0.8}]}),
                model="fake-deepseek",
                request_id="request-test",
            )
            draft = untrusted_triage_from_completion(pool=pool, completion=completion)
            output = root / "triage.json"
            write_untrusted_triage_draft(output, draft)
            written = output.read_text(encoding="utf-8")
            self.assertEqual(draft["trust_status"], "untrusted_llm_private_potential_scope_source_triage_not_evidence")
            self.assertNotIn("Potential-model scope note", written)
            self.assertNotIn("locator", written)

    def test_unknown_segment_or_extra_text_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            pool = self._pool(Path(temporary))
            completion = DraftCompletion(
                content=json.dumps({"document_id": pool["document_id"], "proposals": [{"segment_id": "invented", "roles": ["known_limitation"], "reason": "Bad identifier.", "confidence": 0.5}]}),
                model="fake-deepseek",
                request_id=None,
            )
            with self.assertRaises(PotentialScopeAutoTriageError):
                untrusted_triage_from_completion(pool=pool, completion=completion)


if __name__ == "__main__":
    unittest.main()
