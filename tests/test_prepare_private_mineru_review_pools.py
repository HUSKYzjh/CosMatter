from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tools.prepare_private_mineru_review_pools import PROJECT_ROOT, ManifestReviewError, prepare


class PreparePrivateMinerUReviewPoolsTests(unittest.TestCase):
    def _fixture(self, root: Path) -> tuple[Path, Path, str]:
        markdown_root = root / "markdown"
        markdown_path = markdown_root / "batch" / "paper.md"
        markdown_path.parent.mkdir(parents=True)
        markdown_path.write_text("# Result\n\nA measured value is 42 units.\n\nThe boundary condition differs.", encoding="utf-8")
        digest = hashlib.sha256(markdown_path.read_bytes()).hexdigest()
        manifest = root / "private_markdown_manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "private_output_only": True,
                    "entries": [
                        {
                            "status": "downloaded",
                            "source_relative_path": "bfo_source_01.pdf",
                            "markdown_relative_path": "batch/paper.md",
                            "markdown_sha256": digest,
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        return manifest, markdown_root, digest

    def test_creates_hash_bound_private_pools_and_blank_templates(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest, markdown_root, digest = self._fixture(root)
            output = root / "review"

            result = prepare(
                manifest_path=manifest,
                markdown_root=markdown_root,
                output=output,
                mission_id="bfo_p0_test",
            )

            self.assertEqual(result["pool_count"], 1)
            self.assertEqual(result["entries"][0]["document_id"], "bfo_source_01")
            self.assertEqual(result["entries"][0]["markdown_sha256"], digest)
            pool = json.loads((output / "01_bfo_source_01.review-pool.json").read_text(encoding="utf-8"))
            template = json.loads((output / "01_bfo_source_01.source-map-selection.template.json").read_text(encoding="utf-8"))
            self.assertEqual(pool["trust_status"], "private_unreviewed_mineru_markdown_candidate_pool_not_source_map")
            self.assertTrue(pool["candidate_segments"])
            self.assertEqual(template["trust_status"], "blank_human_source_map_pool_selection_template")
            self.assertTrue(all(not item["selected"] and not item["reason"] for item in template["segments"]))

    def test_rejects_a_manifest_hash_that_does_not_match_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest, markdown_root, _ = self._fixture(root)
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            payload["entries"][0]["markdown_sha256"] = "0" * 64
            manifest.write_text(json.dumps(payload), encoding="utf-8")

            with self.assertRaisesRegex(ManifestReviewError, "does not match"):
                prepare(
                    manifest_path=manifest,
                    markdown_root=markdown_root,
                    output=root / "review",
                    mission_id="bfo_p0_test",
                )

    def test_requires_every_entry_to_be_complete(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest, markdown_root, _ = self._fixture(root)
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            payload["entries"][0]["status"] = "not_done"
            manifest.write_text(json.dumps(payload), encoding="utf-8")

            with self.assertRaisesRegex(ManifestReviewError, "every manifest entry"):
                prepare(
                    manifest_path=manifest,
                    markdown_root=markdown_root,
                    output=root / "review",
                    mission_id="bfo_p0_test",
                )

    def test_rejects_private_outputs_inside_the_repository(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest, markdown_root, _ = self._fixture(root)
            with self.assertRaisesRegex(ManifestReviewError, "outside the repository"):
                prepare(
                    manifest_path=manifest,
                    markdown_root=markdown_root,
                    output=PROJECT_ROOT / "private-review-must-not-exist",
                    mission_id="bfo_p0_test",
                )


if __name__ == "__main__":
    unittest.main()
