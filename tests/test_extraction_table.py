from __future__ import annotations

import csv
import io
import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.request import urlopen

from cosmatter.candidate_screening import candidate_screening_from_review, write_candidate_screening
from cosmatter.evidence_maturity_registry import audit_evidence_maturity_registry_against_runs
from cosmatter.local_api import LocalApiError, LocalMissionApi
from cosmatter.material_extraction import material_facts_from_review, write_material_facts_for_document
from cosmatter.models import EvidenceCard, FlightPlan, PaperCandidate, Provenance, ReviewStatus, Stance
from cosmatter.retrieval import write_candidate_artifact
from cosmatter.source_map import source_map_from_review, write_source_map_for_document
from cosmatter.ui_preview import build_ui_preview_server
from cosmatter.verification import VerificationDecision


class ExtractionTableTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.api = LocalMissionApi(Path(temporary.name) / "runs")
        self.run = "compare"
        self.directory = self.api.runs_dir / self.run
        self.mission = str(self.api.create_mission({
            "question": "Which conditions accompanied the reported phase transition?", "material": "BiFeO3",
            "property": "temperature", "scope": "bulk measurements", "run_id": self.run,
        })["mission_id"])
        papers = tuple(PaperCandidate(document_id=doc, title=f"Paper {doc}", query="synthetic", source="fixture",
                                      doi="10.1234/" + doc) for doc in ("alpha", "beta", "gamma", "excluded"))
        path = write_candidate_artifact(self.directory, "synthetic", papers)
        decisions = [{"document_id": paper.document_id,
                      "decision": "exclude" if paper.document_id == "excluded" else "include_for_fulltext",
                      "reason_codes": ["out_of_scope_material" if paper.document_id == "excluded" else "material_match"]}
                     for paper in papers]
        review = candidate_screening_from_review(self.mission, json.loads(path.read_text(encoding="utf-8")), {"decisions": decisions})
        write_candidate_screening(self.directory, review)

    def _write(self, filename, value):
        (self.directory / filename).write_text(json.dumps(value), encoding="utf-8")

    def _enable_reader_stage(self):
        self._write("flight_plan.json", FlightPlan(self.mission, ("Which temperature?",), ("synthetic",), ()).to_dict())
        decisions = json.loads((self.directory / "verification_decisions.json").read_text(encoding="utf-8"))
        decisions.append(VerificationDecision(self.mission, "c1", ReviewStatus.REJECTED, "fixture review").to_dict())
        self._write("verification_decisions.json", decisions)

    def _cards(self, *, mismatch=False):
        snippet = "DO_NOT_EXPORT_ANY_PRIVATE_QUOTE"
        card = EvidenceCard("=reported value near ambient", Stance.SUPPORT, "BiFeO3", "temperature", {"field": "zero"},
                            snippet, Provenance("alpha", "Figure 5", "fixture", doi="10.1234/alpha"), evidence_id="a1")
        draft = {**card.to_dict(), "evidence_id": "c1", "claim": "UNREVIEWED_PRIVATE_CLAIM",
                 "provenance": {**card.to_dict()["provenance"], "document_id": "gamma"}, "review_status": "accepted"}
        self._write("evidence_cards.json", [card.to_dict(), {**card.to_dict(), "evidence_id": "a2"}, draft])
        self._write("verification_decisions.json", [
            VerificationDecision(self.mission, key, ReviewStatus.ACCEPTED, "NOT_FOR_EXPORT").to_dict() for key in ("a1", "a2")
        ])
        source_map = source_map_from_review(
            mission_id=self.mission, document_id="alpha",
            source_task={"document_id": "alpha", "provider": "mineru", "state": "done", "task_id": "job"},
            selection={"document_id": "alpha", "segments": [
                {"segment_id": "s1", "kind": "figure_caption", "locator": "Figure 5", "quote": "OTHER" if mismatch else snippet},
                {"segment_id": "s2", "kind": "figure_caption", "locator": "Figure 6", "quote": "other sample"},
            ]},
        )
        write_source_map_for_document(self.directory, source_map)
        values = [{"fact_id": f"f_{seg}", "segment_id": seg, "name": "temperature", "category": "property",
                   "value": value, "unit": "K", "normalized_value": value, "normalized_unit": "K", "qualifiers": {"sample": "A"}}
                  for seg, value in (("s1", 300), ("s2", 450))]
        facts = material_facts_from_review(mission_id=self.mission, source_map=source_map, selection={"document_id": "alpha", "facts": values})
        write_material_facts_for_document(self.directory, facts)

    def test_get_and_csv_use_source_links_and_do_not_write_the_run(self):
        self._cards()
        self._enable_reader_stage()
        before = {path.relative_to(self.directory): (path.read_bytes(), path.stat().st_mtime_ns) for path in self.directory.rglob("*") if path.is_file()}
        with build_ui_preview_server(port=0, api=self.api) as server:
            thread = threading.Thread(target=server.serve_forever)
            thread.start()
            try:
                url = f"http://127.0.0.1:{server.server_port}/api/runs/{self.run}/extraction-table"
                with urlopen(url, timeout=5) as response:
                    table = json.load(response)
                with urlopen(url + ".csv", timeout=5) as response:
                    self.assertIn("attachment", response.headers["Content-Disposition"])
                    exported = response.read().decode("utf-8-sig")
            finally:
                server.shutdown()
                thread.join(timeout=5)
        self.assertEqual(table["summary"], {"document_count": 3, "reviewed_count": 1, "gap_count": 2})
        reviewed, missing, draft = table["rows"]
        self.assertEqual((reviewed["evidence_id"], reviewed["reader_available"], reviewed["document_version"]), ("a1", True, None))
        self.assertEqual(reviewed["reported_facts"], [{"fact_id": "f_s1", "name": "temperature", "value": 300, "unit": "K", "qualifiers": {"sample": "A"}}])
        self.assertEqual([missing["status"], draft["status"]], ["awaiting_extraction", "awaiting_extraction"])
        self.assertIsNone(draft["claim"])
        self.assertEqual(list(csv.DictReader(io.StringIO(exported)))[0]["claim"], "'=reported value near ambient")
        for private in ("DO_NOT_EXPORT_ANY_PRIVATE_QUOTE", "UNREVIEWED_PRIVATE_CLAIM", "NOT_FOR_EXPORT", "Paper excluded"):
            self.assertNotIn(private, json.dumps(table) + exported)
        after = {path.relative_to(self.directory): (path.read_bytes(), path.stat().st_mtime_ns) for path in self.directory.rglob("*") if path.is_file()}
        self.assertEqual(after, before)

    def test_reader_links_require_navigable_stage_and_current_run(self):
        self._cards()
        early = self.api.extraction_table(self.run)["rows"]
        self.assertEqual((early[0]["status"], early[0]["reader_available"], early[2]["status"]),
                         ("reviewed", False, "awaiting_review"))
        self._enable_reader_stage()
        stage = self.api.stage_contract(self.run)
        self.assertEqual((stage["next_stage"], stage["runtime_safety"]), ("parse", "verified"))
        self.assertTrue(self.api.extraction_table(self.run)["rows"][0]["reader_available"])
        self.api.cancel(self.run)
        cancelled = self.api.extraction_table(self.run)["rows"][0]
        self.assertEqual((cancelled["status"], cancelled["reader_available"]), ("reviewed", False))

    def test_unmatched_source_and_delegated_human_looking_records_stay_out(self):
        self._cards(mismatch=True)
        table = self.api.extraction_table(self.run)
        row = table["rows"][0]
        self.assertEqual((row["status"], row["reader_available"], row["claim"], row["reported_facts"]),
                         ("unverified_source", False, None, []))
        (self.directory / "test_only_delegated_review.json").touch()
        table = self.api.extraction_table(self.run)
        self.assertEqual(table["summary"]["reviewed_count"], 0)
        self.assertNotIn("reported value", json.dumps(table))

    def test_stale_screening_and_missing_artifacts_do_not_report_old_selections(self):
        self._cards()
        path = self.directory / "retrieval_candidates.json"
        candidates = json.loads(path.read_text(encoding="utf-8"))
        candidates["candidates"].pop()
        self._write(path.name, candidates)
        table = self.api.extraction_table(self.run)
        self.assertEqual((table["screening_status"], [row["document_id"] for row in table["rows"]]), ("outdated", ["alpha"]))
        self._write("evidence_cards.json", [])
        with self.assertRaises(LocalApiError) as invalid:
            self.api.extraction_table(self.run)
        self.assertEqual(invalid.exception.status, 409)
        self._write("verification_decisions.json", [])
        self.assertEqual(self.api.extraction_table(self.run)["rows"], [])
        with self.assertRaises(LocalApiError) as unknown:
            self.api.extraction_table("unknown")
        self.assertEqual(unknown.exception.status, 404)

    def test_document_version_requires_a_current_human_audit(self):
        self._cards()
        registry = {
            "schema_version": "cosmatter.evidence-maturity-registry/v1", "registry_id": "reg", "question_id": self.mission,
            "trust_status": "human_reviewed_evidence_maturity_registry_not_scientific_conclusion",
            "claims": [{"claim_id": "claim", "claim_text": "version check", "maturity_level": "literature_mentioned",
                        "assessment_authority": "human_source_review", "support_records": [{
                            "run_id": self.run, "document_id": "alpha", "document_version": "preprint", "independence_group": "one",
                            "source_map_status": "human_reviewed", "data_status": "not_checked", "conditions_status": "not_checked", "stance": "supports",
                        }], "reproducibility": {"protocol_status": "not_checked", "materials_status": "not_checked",
                            "measurement_status": "not_checked", "raw_data_status": "not_checked", "assessment": "not_assessed"},
                        "independent_reproduction": {"status": "not_attempted", "independent_run_id": None,
                            "result_comparison": "not_available", "review_status": "not_reviewed"}, "limitations": ["One source."]}],
        }
        self._write("evidence_maturity_registry.json", registry)
        self.assertIsNone(self.api.extraction_table(self.run)["rows"][0]["document_version"])
        self._write("evidence_maturity_registry_audit.json", audit_evidence_maturity_registry_against_runs(registry, self.api.runs_dir))
        self.assertEqual(self.api.extraction_table(self.run)["rows"][0]["document_version"], "preprint")
        registry["claims"][0]["support_records"][0]["document_version"] = "publisher_version"
        self._write("evidence_maturity_registry.json", registry)
        self.assertIsNone(self.api.extraction_table(self.run)["rows"][0]["document_version"])
