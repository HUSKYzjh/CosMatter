import copy
import json
import tempfile
import unittest
from pathlib import Path

from cosmatter.evidence_maturity_registry import EvidenceMaturityRegistryError, audit_evidence_maturity_registry_against_runs, validate_evidence_maturity_registry, validate_evidence_maturity_registry_audit, write_evidence_maturity_registry_audit
from cosmatter.source_map import AUTOMATED_TRIAL_SOURCE_MAP_TRUST_STATUS, source_map_document_path, source_map_from_review, write_source_map_for_document


def registry() -> dict[str, object]:
    return {
        "schema_version": "cosmatter.evidence-maturity-registry/v1",
        "registry_id": "registry_1",
        "question_id": "question_1",
        "trust_status": "delegated_automated_trial_evidence_maturity_registry_not_scientific_evidence",
        "claims": [{
            "claim_id": "claim_1", "claim_text": "A bounded trial claim.", "maturity_level": "literature_mentioned", "assessment_authority": "delegated_automated_trial",
            "support_records": [{"run_id": "run_1", "document_id": "doc_1", "document_version": "preprint", "independence_group": "not_human_verified", "source_map_status": "automated_trial_only", "data_status": "not_checked", "conditions_status": "not_checked", "stance": "supports"}],
            "reproducibility": {"protocol_status": "not_checked", "materials_status": "not_checked", "measurement_status": "not_checked", "raw_data_status": "not_checked", "assessment": "not_assessed"},
            "independent_reproduction": {"status": "not_attempted", "independent_run_id": None, "result_comparison": "not_available", "review_status": "not_reviewed"},
            "limitations": ["Not human reviewed."],
        }],
    }


class EvidenceMaturityRegistryTests(unittest.TestCase):
    def test_trial_claim_is_literature_mentioned_only(self) -> None:
        validate_evidence_maturity_registry(registry())
        invalid = copy.deepcopy(registry())
        invalid["claims"][0]["maturity_level"] = "data_supported"
        with self.assertRaises(EvidenceMaturityRegistryError):
            validate_evidence_maturity_registry(invalid)

    def test_reproduction_needs_human_review(self) -> None:
        invalid = copy.deepcopy(registry())
        invalid["claims"][0].update({"maturity_level": "independently_reproduced", "assessment_authority": "independent_reproduction_review"})
        invalid["claims"][0]["independent_reproduction"] = {"status": "replicated", "independent_run_id": "run_1", "result_comparison": "within_predefined_tolerance", "review_status": "not_reviewed"}
        with self.assertRaises(EvidenceMaturityRegistryError):
            validate_evidence_maturity_registry(invalid)

    def test_data_supported_needs_human_checked_data_and_complete_conditions(self) -> None:
        invalid = copy.deepcopy(registry())
        claim = invalid["claims"][0]
        claim.update({"maturity_level": "data_supported", "assessment_authority": "human_data_review"})
        with self.assertRaises(EvidenceMaturityRegistryError):
            validate_evidence_maturity_registry(invalid)
        claim["support_records"][0].update({"source_map_status": "human_reviewed", "data_status": "numeric_or_figure_data_human_checked", "conditions_status": "complete_human_checked"})
        validate_evidence_maturity_registry(invalid)

    def test_independent_reproduction_requires_a_distinct_confirmed_run(self) -> None:
        invalid = copy.deepcopy(registry())
        claim = invalid["claims"][0]
        claim.update({"maturity_level": "independently_reproduced", "assessment_authority": "independent_reproduction_review"})
        claim["support_records"][0].update({"source_map_status": "human_reviewed", "data_status": "numeric_or_figure_data_human_checked", "conditions_status": "complete_human_checked"})
        claim["independent_reproduction"] = {"status": "not_replicated", "independent_run_id": "lab_run_2", "result_comparison": "outside_predefined_tolerance", "review_status": "human_reviewed"}
        with self.assertRaises(EvidenceMaturityRegistryError):
            validate_evidence_maturity_registry(invalid)
        claim["independent_reproduction"] = {"status": "replicated", "independent_run_id": "run_1", "result_comparison": "within_predefined_tolerance", "review_status": "human_reviewed"}
        with self.assertRaises(EvidenceMaturityRegistryError):
            validate_evidence_maturity_registry(invalid)
        claim["independent_reproduction"]["independent_run_id"] = "lab_run_2"
        validate_evidence_maturity_registry(invalid)

    def test_run_identifier_cannot_escape_audit_root(self) -> None:
        invalid = copy.deepcopy(registry())
        invalid["claims"][0]["support_records"][0]["run_id"] = "../other-run"
        with self.assertRaises(EvidenceMaturityRegistryError):
            validate_evidence_maturity_registry(invalid)

    def test_public_registry_text_cannot_contain_urls_or_credentials(self) -> None:
        invalid = copy.deepcopy(registry())
        invalid["claims"][0]["claim_text"] = "See https://private.example.invalid for a claim."
        with self.assertRaises(EvidenceMaturityRegistryError):
            validate_evidence_maturity_registry(invalid)
        invalid = copy.deepcopy(registry())
        invalid["claims"][0]["limitations"] = ["authorization: secret-value"]
        with self.assertRaises(EvidenceMaturityRegistryError):
            validate_evidence_maturity_registry(invalid)

    def test_audit_requires_a_valid_source_map_for_the_run_mission(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run = root / "run_1"
            run.mkdir()
            (run / "mission.json").write_text(json.dumps({"mission_id": "mission_1"}), encoding="utf-8")
            (run / "retrieval_candidates.json").write_text(json.dumps({"candidates": [{"document_id": "doc_1"}]}), encoding="utf-8")
            source_map = source_map_from_review(mission_id="mission_1", document_id="doc_1", source_task={"document_id": "doc_1", "provider": "mineru", "state": "done", "task_id": "task_1"}, selection={"document_id": "doc_1", "segments": [{"segment_id": "segment_1", "locator": "p. 1", "kind": "paragraph", "quote": "Bounded test excerpt."}]}, trust_status=AUTOMATED_TRIAL_SOURCE_MAP_TRUST_STATUS)
            write_source_map_for_document(run, source_map)
            audit = audit_evidence_maturity_registry_against_runs(registry(), root)
            self.assertEqual(audit["link_error_count"], 0)
            self.assertTrue(audit["passed"])
            source_map["task_id_sha256"] = "not-a-fingerprint"
            source_map_document_path(run, "doc_1").write_text(json.dumps(source_map), encoding="utf-8")
            audit = audit_evidence_maturity_registry_against_runs(registry(), root)
            self.assertEqual(audit["link_error_count"], 1)
            self.assertFalse(audit["passed"])

    def test_writes_count_only_audit(self) -> None:
        value = registry()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run = root / "run_1"
            run.mkdir()
            (run / "mission.json").write_text(json.dumps({"mission_id": "mission_1"}), encoding="utf-8")
            (run / "retrieval_candidates.json").write_text(json.dumps({"candidates": [{"document_id": "doc_1"}]}), encoding="utf-8")
            source_map = source_map_from_review(mission_id="mission_1", document_id="doc_1", source_task={"document_id": "doc_1", "provider": "mineru", "state": "done", "task_id": "task_1"}, selection={"document_id": "doc_1", "segments": [{"segment_id": "segment_1", "locator": "p. 1", "kind": "paragraph", "quote": "Bounded test excerpt."}]}, trust_status=AUTOMATED_TRIAL_SOURCE_MAP_TRUST_STATUS)
            write_source_map_for_document(run, source_map)
            audit = audit_evidence_maturity_registry_against_runs(value, root)
            validate_evidence_maturity_registry_audit(audit, value)
            altered = copy.deepcopy(value)
            altered["claims"][0]["claim_text"] = "A different bounded trial claim."
            with self.assertRaises(EvidenceMaturityRegistryError):
                validate_evidence_maturity_registry_audit(audit, altered)
            path = write_evidence_maturity_registry_audit(root / "audit.json", audit)
            self.assertTrue(path.exists())


if __name__ == "__main__":
    unittest.main()
