import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cosmatter.candidate_duplicate_reconciliation import REVIEW_TRUST_STATUS
from cosmatter.cli import main
from cosmatter.models import MissionBrief, PaperCandidate
from cosmatter.retrieval import write_candidate_artifact


class CandidateDuplicateReconciliationCliTests(unittest.TestCase):
    def test_build_template_and_human_resolution_keep_titles_out_of_identity_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runs = root / "runs"
            run = runs / "duplicate_cli"
            run.mkdir(parents=True)
            mission = MissionBrief("Private duplicate question", "BiFeO3", "phase stability", "private scope", mission_id="mission_duplicate")
            (run / "mission.json").write_text(json.dumps(mission.to_dict()), encoding="utf-8")
            candidates = (
                PaperCandidate("doc_1", "Shared private candidate title", "query", "Sciverse"),
                PaperCandidate("doc_2", "Shared private candidate title.", "query", "Sciverse"),
            )
            write_candidate_artifact(run, "query", candidates)
            template_path = root / "review.json"
            stdout = io.StringIO()
            with patch("cosmatter.cli._runs_dir", return_value=runs), contextlib.redirect_stdout(stdout):
                self.assertEqual(main(["build-candidate-duplicate-queue", "--run-id", "duplicate_cli"]), 0)
                self.assertEqual(main(["create-candidate-duplicate-review-template", "--run-id", "duplicate_cli", "--output", str(template_path)]), 0)
            queue = json.loads((run / "candidate_duplicate_queue.json").read_text(encoding="utf-8"))
            review = json.loads(template_path.read_text(encoding="utf-8"))
            review["trust_status"] = REVIEW_TRUST_STATUS
            review["decisions"][0].update(
                decision="distinct_works", canonical_document_id=None, reason_code="distinct_study_same_title"
            )
            template_path.write_text(json.dumps(review), encoding="utf-8")
            with patch("cosmatter.cli._runs_dir", return_value=runs), contextlib.redirect_stdout(stdout):
                self.assertEqual(main(["record-candidate-duplicate-reconciliation", "--run-id", "duplicate_cli", "--input", str(template_path)]), 0)

            reconciliation = json.loads((run / "candidate_duplicate_reconciliation.json").read_text(encoding="utf-8"))
            self.assertEqual(queue["summary"]["title_only_review_required_count"], 1)
            self.assertEqual(reconciliation["summary"]["distinct_works_count"], 1)
            self.assertEqual(reconciliation["summary"]["same_work_count"], 0)
            identity_text = json.dumps({"queue": queue, "reconciliation": reconciliation, "events": (run / "events.jsonl").read_text(encoding="utf-8")})
            self.assertNotIn("Shared private candidate title", identity_text)
            self.assertNotIn("Private duplicate question", identity_text)


if __name__ == "__main__":
    unittest.main()
