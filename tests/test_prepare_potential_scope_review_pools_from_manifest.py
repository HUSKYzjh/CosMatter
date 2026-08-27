from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import prepare_potential_scope_review_pools_from_manifest as command


class PreparePotentialScopeReviewPoolsFromManifestTests(unittest.TestCase):
    def test_deduplicates_manifest_records_by_markdown_digest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            markdown = root / "paper.md"
            markdown.write_text("A private local paragraph for human review.", encoding="utf-8")
            digest = hashlib.sha256(markdown.read_text(encoding="utf-8").encode("utf-8")).hexdigest()
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "entries": [
                            {"markdown_sha256": digest, "markdown_relative_path": "paper.md"},
                            {"markdown_sha256": digest, "markdown_relative_path": "paper.md"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            output = root / "review_output"
            argv = [
                "prepare_potential_scope_review_pools_from_manifest.py",
                "--manifest", str(manifest),
                "--markdown-root", str(root),
                "--output", str(output),
                "--mission-id", "test_mission",
            ]
            with patch.object(command, "P0_MARKDOWN_SHA256", {digest}), patch.object(sys, "argv", argv):
                self.assertEqual(command.main(), 0)
            index = json.loads((output / "review_pool_index.json").read_text(encoding="utf-8"))
            self.assertEqual(index["pool_count"], 1)
            self.assertEqual(index["duplicate_record_count"], 1)
            self.assertEqual(len(list(output.glob("*.review-pool.json"))), 1)
            self.assertEqual(len(list(output.glob("*.source-map-selection.template.json"))), 1)


if __name__ == "__main__":
    unittest.main()
