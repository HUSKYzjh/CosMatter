import contextlib
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cosmatter.candidate_screening import candidate_screening_from_review, write_candidate_screening
from cosmatter.cli import main
from cosmatter.content_access import load_content_access, record_sciverse_content_access
from cosmatter.models import MissionBrief
from cosmatter.provider_receipts import append_provider_receipt, load_provider_receipts, sciverse_content_receipt
from cosmatter.sciverse_context_review import SciverseContextReviewError, prepare_sciverse_context_review_pool


class SciverseContextReviewTests(unittest.TestCase):
    def _confirmed(self, root: Path, content: str, *, offset: int = 20):
        run = root / "run"
        run.mkdir()
        candidates = {"candidates": [{"document_id": "doc_1", "title": "paper", "is_content_accessible": True}]}
        receipt = sciverse_content_receipt(
            document_id="doc_1", offset=offset, limit=4000, content=content,
            next_offset=None, more=False, status_code=200, request_id=None,
        )
        append_provider_receipt(run, receipt)
        record_sciverse_content_access(
            run, mission_id="mission_1", candidate_payload=candidates,
            document_id="doc_1", receipt=receipt,
        )
        access = load_content_access(run / "content_access_confirmations.json", "mission_1")
        return run, candidates, access, load_provider_receipts(run)

    def test_pool_is_bound_to_document_offset_receipt_and_exact_content(self) -> None:
        content = "First bounded result.\n\nSecond bounded result."
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, candidates, access, receipts = self._confirmed(root, content)
            context_path = root / "context.md"
            context_path.write_text(content, encoding="utf-8")
            pool = prepare_sciverse_context_review_pool(
                mission_id="mission_1", candidate_payload=candidates, content_access=access,
                provider_receipts=receipts, document_id="doc_1", offset=20,
                input_path=context_path, output_path=root / "pool.json",
            )
            with self.assertRaisesRegex(SciverseContextReviewError, "offset"):
                prepare_sciverse_context_review_pool(
                    mission_id="mission_1", candidate_payload=candidates, content_access=access,
                    provider_receipts=receipts, document_id="doc_1", offset=21,
                    input_path=context_path, output_path=root / "wrong-offset.json",
                )
            context_path.write_text(content + " tampered", encoding="utf-8")
            with self.assertRaisesRegex(SciverseContextReviewError, "hash"):
                prepare_sciverse_context_review_pool(
                    mission_id="mission_1", candidate_payload=candidates, content_access=access,
                    provider_receipts=receipts, document_id="doc_1", offset=20,
                    input_path=context_path, output_path=root / "tampered.json",
                )

        self.assertEqual(pool["receipt_id"], receipts[0]["receipt_id"])
        self.assertEqual(pool["content_sha256"], hashlib.sha256(content.encode()).hexdigest())
        self.assertEqual([item["locator"] for item in pool["candidate_segments"]], ["sciverse_char:20-41", "sciverse_char:43-65"])

    def test_stale_confirmation_is_rejected(self) -> None:
        content = "Bounded context."
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, candidates, access, receipts = self._confirmed(root, content)
            changed = {"candidates": [{"document_id": "doc_1", "title": "changed", "is_content_accessible": True}]}
            context_path = root / "context.txt"
            context_path.write_text(content, encoding="utf-8")
            with self.assertRaisesRegex(SciverseContextReviewError, "current confirmed"):
                prepare_sciverse_context_review_pool(
                    mission_id="mission_1", candidate_payload=changed, content_access=access,
                    provider_receipts=receipts, document_id="doc_1", offset=20,
                    input_path=context_path, output_path=root / "pool.json",
                )

    def test_cli_keeps_context_and_paths_outside_the_run(self) -> None:
        secret = "Private bounded Sciverse excerpt that must not enter the run."
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runs = root / "runs"
            run = runs / "context_pool"
            run.mkdir(parents=True)
            mission = MissionBrief("why", "BiFeO3", "phase", "films", mission_id="mission_1")
            candidates = {"candidates": [{"document_id": "doc_1", "title": "paper", "is_content_accessible": True}]}
            (run / "mission.json").write_text(json.dumps(mission.to_dict()), encoding="utf-8")
            (run / "retrieval_candidates.json").write_text(json.dumps(candidates), encoding="utf-8")
            screening = candidate_screening_from_review(
                mission.mission_id, candidates,
                {"decisions": [{"document_id": "doc_1", "decision": "include_for_fulltext", "reason_codes": ["material_match"]}]},
            )
            write_candidate_screening(run, screening)
            receipt = sciverse_content_receipt(
                document_id="doc_1", offset=0, limit=4000, content=secret,
                next_offset=None, more=False, status_code=200, request_id=None,
            )
            append_provider_receipt(run, receipt)
            record_sciverse_content_access(
                run, mission_id=mission.mission_id, candidate_payload=candidates,
                document_id="doc_1", receipt=receipt,
            )
            context_path = root / "private-context.md"
            pool_path = root / "private-pool.json"
            context_path.write_text(secret, encoding="utf-8")
            output = io.StringIO()
            with patch("cosmatter.cli._runs_dir", return_value=runs), contextlib.redirect_stdout(output):
                status = main([
                    "prepare-sciverse-context-review", "--run-id", "context_pool",
                    "--document-id", "doc_1", "--offset", "0",
                    "--input", str(context_path), "--output", str(pool_path),
                ])
            run_text = "\n".join(path.read_text(encoding="utf-8") for path in run.rglob("*") if path.is_file())
            pool_exists = pool_path.exists()

        self.assertEqual(status, 0, output.getvalue())
        self.assertTrue(pool_exists)
        self.assertNotIn(secret, output.getvalue())
        self.assertNotIn(secret, run_text)
        self.assertNotIn(str(context_path), run_text)
        self.assertNotIn(str(pool_path), run_text)


if __name__ == "__main__":
    unittest.main()
