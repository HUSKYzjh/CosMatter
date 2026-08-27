from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from cosmatter.mineru_local_review import (
    prepare_mineru_markdown_review_pool,
    source_map_pool_review_template,
)
from cosmatter.potential_scope_review_registry import (
    PotentialScopeReviewRegistryError,
    build_reviewed_source_registry,
    load_reviewed_source,
    write_reviewed_source_registry,
)


class PotentialScopeReviewRegistryTests(unittest.TestCase):
    def _pool_and_review(self, root: Path) -> tuple[dict[str, object], Path, Path, dict[str, str]]:
        markdown = root / "private.md"
        private_quote = "Private reviewer excerpt for the frozen literature boundary."
        markdown.write_text(private_quote + "\n\nSecond local paragraph.", encoding="utf-8")
        task = {
            "document_id": "potential_scope_p0_0123456789abcdef",
            "provider": "mineru",
            "state": "done",
            "task_id": "private_manifest_test_task",
        }
        pool_path = root / "pool.json"
        pool = prepare_mineru_markdown_review_pool(
            mission_id="potential_scope_p0_review_20260820",
            document_id=task["document_id"],
            source_task=task,
            input_path=markdown,
            output_path=pool_path,
        )
        review = source_map_pool_review_template(pool)
        review["trust_status"] = "human_reviewed_source_map_pool_selection"
        review["segments"][0]["selected"] = True
        review["segments"][0]["reason"] = "Reviewer confirmed this locatable statement."
        review_path = root / "review.json"
        review_path.write_text(json.dumps(review, ensure_ascii=False), encoding="utf-8")
        return pool, pool_path, review_path, task

    def test_registry_stores_hashes_and_counts_but_not_private_excerpt_or_reason(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, pool_path, review_path, task = self._pool_and_review(root)
            entry = load_reviewed_source(
                mission_id="potential_scope_p0_review_20260820",
                document_id=task["document_id"],
                source_task=task,
                pool_path=pool_path,
                review_path=review_path,
            )
            registry = build_reviewed_source_registry(
                mission_id="potential_scope_p0_review_20260820", entries=[entry]
            )
            output = root / "registry.json"
            write_reviewed_source_registry(output, registry)
            written = output.read_text(encoding="utf-8")
            self.assertEqual(registry["trust_status"], "human_reviewed_private_source_registry_not_evidence")
            self.assertEqual(registry["sources"][0]["selected_segment_count"], 1)
            self.assertNotIn("Private reviewer excerpt", written)
            self.assertNotIn("Reviewer confirmed", written)
            self.assertNotIn(str(root), written)

    def test_blank_or_mismatched_review_cannot_enter_registry(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pool, pool_path, review_path, task = self._pool_and_review(root)
            blank = source_map_pool_review_template(pool)
            review_path.write_text(json.dumps(blank), encoding="utf-8")
            with self.assertRaises(PotentialScopeReviewRegistryError):
                load_reviewed_source(
                    mission_id="potential_scope_p0_review_20260820",
                    document_id=task["document_id"],
                    source_task=task,
                    pool_path=pool_path,
                    review_path=review_path,
                )


if __name__ == "__main__":
    unittest.main()
