import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cosmatter.cli import main
from cosmatter.corpus_preparation import corpus_manifest_from_review, write_corpus_manifest
from cosmatter.local_corpus import candidates_from_local_source_index
from cosmatter.models import MissionBrief
from cosmatter.scibase_local import SciBaseLocalError, build_scibase_local_index


def manifest() -> dict[str, object]:
    return corpus_manifest_from_review(
        mission_id="mission_scibase",
        material="BiFeO3",
        selection={
            "corpus_id": "bfo_scibase_fixture",
            "material": "BiFeO3",
            "documents": [
                {
                    "document_id": "bfo_1",
                    "title": "BiFeO3 phase stability",
                    "doi": "10.1000/bfo.1",
                    "access_policy": "institutional_access_internal_review_only",
                },
                {
                    "document_id": "bfo_2",
                    "title": "BiFeO3 without DOI",
                    "doi": None,
                    "access_policy": "institutional_access_internal_review_only",
                },
            ],
        },
    )


def rows() -> list[dict[str, object]]:
    return [
        {
            "sha256": "a" * 64,
            "title": "Different metadata title is not trusted for the manifest",
            "doi": "10.1000/BFO.1",
            "is_oa": True,
            "abstract": "BiFeO3 phase overview.",
            "content_list": [{"text": "Epitaxial strain changes phase stability."}],
        },
        {
            "sha256": "b" * 64,
            "title": "Unrelated",
            "doi": "10.1000/unrelated",
            "is_oa": True,
            "content_list": [{"text": "not selected"}],
        },
    ]


class SciBaseLocalTests(unittest.TestCase):
    def test_builds_exact_doi_private_index_and_local_bm25_can_consume_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "private_scibase"
            result = build_scibase_local_index(
                manifest=manifest(), rows=rows(), output_dir=output,
                dataset_revision="fixture-revision", require_all_doi_matched=True,
            )
            index = json.loads(result.index_path.read_text(encoding="utf-8"))
            receipt = json.loads(result.receipt_path.read_text(encoding="utf-8"))
            candidates = candidates_from_local_source_index(
                manifest=manifest(), index_path=result.index_path,
                query="BiFeO3 epitaxial strain phase", top_k=10,
            )
            markdown = next((output / "scibase_markdown").glob("*.md")).read_text(encoding="utf-8")
            index_text = result.index_path.read_text(encoding="utf-8")
            self.assertEqual([item["document_id"] for item in index["documents"]], ["bfo_1"])
            self.assertEqual(index["documents"][0]["parser_provenance"], "scibase_parquet_oa_subset")
            self.assertEqual(receipt["match_policy"], "exact_normalized_doi_only")
            self.assertEqual(receipt["manifest_documents_without_doi"], 1)
            self.assertEqual([candidate.document_id for candidate in candidates], ["bfo_1"])
            self.assertIn("Epitaxial strain", markdown)
            self.assertNotIn("Epitaxial strain", index_text)

    def test_rejects_unmatched_non_oa_and_nonempty_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(SciBaseLocalError):
                build_scibase_local_index(
                    manifest=manifest(), rows=[{
                        "sha256": "a" * 64, "doi": "10.1000/bfo.1",
                        "is_oa": False, "content_list": [{"text": "restricted"}],
                    }], output_dir=root / "not_oa",
                )
            occupied = root / "occupied"
            occupied.mkdir()
            (occupied / "keep.txt").write_text("keep", encoding="utf-8")
            with self.assertRaises(SciBaseLocalError):
                build_scibase_local_index(
                    manifest=manifest(), rows=rows(), output_dir=occupied,
                )

    def test_cli_never_persists_private_output_path_or_text_in_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runs = root / "runs"
            run = runs / "scibase_cli"
            run.mkdir(parents=True)
            mission = MissionBrief(
                question="BiFeO3 phase", material="BiFeO3", property_name="phase",
                scope="films", mission_id="mission_scibase",
            )
            (run / "mission.json").write_text(json.dumps(mission.to_dict()), encoding="utf-8")
            write_corpus_manifest(run, manifest())
            private_output = root / "private_scibase"
            output = io.StringIO()
            with (
                patch("cosmatter.cli._runs_dir", return_value=runs),
                patch("cosmatter.cli.rows_from_scibase_parquet", return_value=iter(rows())),
                contextlib.redirect_stdout(output),
            ):
                status = main([
                    "prepare-scibase-local-index", "--run-id", "scibase_cli",
                    "--input", str(root / "subset.parquet"),
                    "--output-dir", str(private_output),
                    "--require-all-doi-matched",
                ])
            run_text = "\n".join(path.read_text(encoding="utf-8") for path in run.rglob("*") if path.is_file())
            self.assertEqual(status, 0, output.getvalue())
            self.assertTrue((private_output / "scibase_local_source_index.json").exists(), output.getvalue())
            self.assertNotIn(str(private_output), run_text)
            self.assertNotIn("Epitaxial strain", run_text)


if __name__ == "__main__":
    unittest.main()
