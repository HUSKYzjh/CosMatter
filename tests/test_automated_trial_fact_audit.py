import hashlib
import tempfile
import unittest
from pathlib import Path

from cosmatter.automated_trial_fact_audit import AutomatedTrialFactAuditError, automated_trial_fact_audit_from_review, write_automated_trial_fact_audit
from cosmatter.material_extraction import MaterialExtractionError, material_fact_review_template
from cosmatter.source_map import AUTOMATED_TRIAL_SOURCE_MAP_TRUST_STATUS


def source_map() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "mission_id": "mission_trial",
        "trust_status": AUTOMATED_TRIAL_SOURCE_MAP_TRUST_STATUS,
        "document_id": "doc_trial",
        "provider": "mineru",
        "task_id_sha256": "a" * 64,
        "segments": [{"segment_id": "p1", "locator": "p. 1", "kind": "paragraph", "quote": "Reported result.", "quote_sha256": hashlib.sha256(b"Reported result.").hexdigest()}],
    }


def review() -> dict[str, object]:
    return {"document_id": "doc_trial", "claims": [{"claim_id": "claim_1", "segment_id": "p1", "claim": "The source reports the result.", "determination": "directly_supported", "rationale": "The selected segment states this result."}]}


class AutomatedTrialFactAuditTests(unittest.TestCase):
    def test_requires_agent_trial_map_and_exact_segment(self) -> None:
        artifact = automated_trial_fact_audit_from_review(mission_id="mission_trial", source_map=source_map(), review=review())
        self.assertEqual(artifact["trust_status"], "delegated_automated_trial_fact_audit_not_scientific_evidence")
        bad = review()
        bad["claims"][0]["segment_id"] = "missing"
        with self.assertRaises(AutomatedTrialFactAuditError):
            automated_trial_fact_audit_from_review(mission_id="mission_trial", source_map=source_map(), review=bad)
        with self.assertRaises(AutomatedTrialFactAuditError):
            automated_trial_fact_audit_from_review(mission_id="mission_trial", source_map={**source_map(), "trust_status": "human_reviewed_parser_selection"}, review=review())

    def test_writes_separate_non_fact_artifact(self) -> None:
        artifact = automated_trial_fact_audit_from_review(mission_id="mission_trial", source_map=source_map(), review=review())
        with tempfile.TemporaryDirectory() as directory:
            path = write_automated_trial_fact_audit(Path(directory), artifact)
            raw = path.read_text(encoding="utf-8")
        self.assertIn("delegated_automated_trial_fact_audit_not_scientific_evidence", raw)
        self.assertIn("claim_1", raw)

    def test_automated_trial_map_cannot_enter_formal_material_fact_workflow(self) -> None:
        with self.assertRaises(MaterialExtractionError):
            material_fact_review_template(mission_id="mission_trial", source_map=source_map())


if __name__ == "__main__":
    unittest.main()
