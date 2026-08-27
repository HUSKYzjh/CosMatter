from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

from cosmatter.corpus_preparation import corpus_manifest_from_selection_review


def _bridge_module():
    tool = Path(__file__).resolve().parents[1] / "tools" / "private_library_review_bridge.py"
    spec = importlib.util.spec_from_file_location("private_library_review_bridge", tool)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PrivateLibraryReviewBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.bridge = _bridge_module()

    def _catalog(self) -> dict[str, object]:
        record = {
            "document_id": "local-pdf-001",
            "provisional_title": "Reviewed local title candidate",
            "source_group": "private_group",
            "markdown_sha256": "a" * 64,
            "private_markdown_relative_path": "group/paper.md",
            "parse_state": "done",
            "classification": "unreviewed",
            "evidence_status": "not_evidence_requires_human_source_map_review",
        }
        return {
            "schema_version": "1.0",
            "trust_status": self.bridge.CATALOG_STATUS,
            "catalog_fingerprint": self.bridge._fingerprint([record]),
            "documents": [record],
        }

    def test_template_is_metadata_only_and_freeze_creates_compatible_private_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            catalog_path = root / "catalog.json"
            catalog_path.write_text(json.dumps(self._catalog()), encoding="utf-8")
            template_path = root / "review.json"
            common = {
                "catalog": catalog_path,
                "mission_id": "mission_1",
                "corpus_id": "bfo_90_v1",
                "material": "BiFeO3",
                "query": "BiFeO3 phase stability",
            }
            self.assertEqual(0, self.bridge.make_template(Namespace(**common, output=template_path)))
            template = json.loads(template_path.read_text(encoding="utf-8"))
            self.assertNotIn("private_markdown_relative_path", json.dumps(template))
            row = template["candidates"][0]
            template["trust_status"] = self.bridge.REVIEW_STATUS
            row.update({
                "include_for_corpus": True,
                "reviewed_title": "Human-reviewed BiFeO3 paper",
                "doi": "https://doi.org/10.1000/TEST",
                "material_scope_match": True,
                "access_authorized": True,
                "review_reason": "Matches the frozen material and scope; institutional access confirmed.",
            })
            review_path = root / "reviewed.json"
            review_path.write_text(json.dumps(template), encoding="utf-8")
            markdown_root = root / "markdown"
            paper = markdown_root / "group" / "paper.md"
            paper.parent.mkdir(parents=True)
            paper.write_text("private text never enters the run", encoding="utf-8")
            output = root / "frozen"
            self.assertEqual(0, self.bridge.freeze(Namespace(**common, review=review_path, markdown_root=markdown_root, output=output)))
            selection = json.loads((output / "corpus_selection_review.json").read_text(encoding="utf-8"))
            manifest = corpus_manifest_from_selection_review(mission_id="mission_1", material="BiFeO3", review=selection)
            self.assertEqual("human_reviewed_authorized_corpus_manifest_not_evaluation_result", manifest["trust_status"])
            local_index = json.loads((output / "local_source_index.json").read_text(encoding="utf-8"))
            self.assertEqual(str(paper.resolve()), local_index["documents"][0]["path"])

