import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cosmatter.cli import main
from cosmatter.corpus_preparation import corpus_manifest_from_review, write_corpus_manifest
from cosmatter.local_corpus import LocalCorpusSearchError, candidates_from_local_source_index
from cosmatter.models import MissionBrief


def selection() -> dict[str, object]:
    return {
        "corpus_id": "bfo_test",
        "material": "BiFeO3",
        "documents": [
            {
                "document_id": "doc_1",
                "title": "BiFeO3 phase stability",
                "doi": None,
                "access_policy": "institutional_access_internal_review_only",
            },
            {
                "document_id": "doc_2",
                "title": "Unrelated title",
                "doi": None,
                "access_policy": "institutional_access_internal_review_only",
            },
        ],
    }


class LocalCorpusSearchTests(unittest.TestCase):
    def test_local_markdown_search_ranks_without_returning_path_or_text(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first.md"
            second = root / "second.md"
            first.write_text("# BiFeO3 phase stability\nstrain controls phase transitions", encoding="utf-8")
            second.write_text("# unrelated\nno matching subject", encoding="utf-8")
            manifest = corpus_manifest_from_review(mission_id="m_1", material="BiFeO3", selection=selection())
            index = root / "index.json"
            index.write_text(json.dumps({"documents": [
                {"document_id": "doc_1", "title": "BiFeO3 phase stability", "path": str(first), "parser_provenance": "mineru_reviewed_local_output"},
                {"document_id": "doc_2", "title": "Unrelated title", "path": str(second), "parser_provenance": "mineru_reviewed_local_output"},
            ]}), encoding="utf-8")
            candidates = candidates_from_local_source_index(manifest=manifest, index_path=index, query="BiFeO3 phase", top_k=10)
        self.assertEqual([item.document_id for item in candidates], ["doc_1"])
        self.assertGreater(candidates[0].score or 0, 0)
        self.assertNotIn("first.md", json.dumps(candidates[0].to_dict()))

    def test_rejects_unapproved_parser_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "paper.md"
            source.write_text("BiFeO3 phase", encoding="utf-8")
            manifest = corpus_manifest_from_review(mission_id="m_1", material="BiFeO3", selection=selection())
            index = root / "index.json"
            index.write_text(json.dumps({"documents": [
                {"document_id": "doc_1", "title": "BiFeO3 phase stability", "path": str(source), "parser_provenance": "unknown"},
            ]}), encoding="utf-8")
            with self.assertRaises(LocalCorpusSearchError):
                candidates_from_local_source_index(manifest=manifest, index_path=index, query="BiFeO3", top_k=10)

    def test_cli_keeps_private_index_path_out_of_run_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runs = root / "runs"
            run = runs / "local_search"
            run.mkdir(parents=True)
            mission = MissionBrief("BiFeO3 phase", "BiFeO3", "phase", "films", mission_id="m_1")
            (run / "mission.json").write_text(json.dumps(mission.to_dict()), encoding="utf-8")
            manifest = corpus_manifest_from_review(mission_id="m_1", material="BiFeO3", selection=selection())
            write_corpus_manifest(run, manifest)
            source = root / "private.md"
            source.write_text("BiFeO3 phase stability", encoding="utf-8")
            index = root / "private-index.json"
            index.write_text(json.dumps({"documents": [
                {"document_id": "doc_1", "title": "BiFeO3 phase stability", "path": str(source), "parser_provenance": "mineru_reviewed_local_output"},
            ]}), encoding="utf-8")
            output = io.StringIO()
            with patch("cosmatter.cli._runs_dir", return_value=runs), contextlib.redirect_stdout(output):
                status = main(["local-parsed-corpus-search", "--run-id", "local_search", "--index", str(index), "--query", "BiFeO3 phase", "--top-k", "10"])
            artifact = (run / "retrieval_candidates.json").read_text(encoding="utf-8")
        self.assertEqual(status, 0, output.getvalue())
        self.assertIn("doc_1", artifact)
        self.assertNotIn(str(source), artifact)
        self.assertNotIn(str(index), artifact)


if __name__ == "__main__":
    unittest.main()
