import hashlib
import json
import tempfile
import time
import threading
import unittest
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

from cosmatter.config import Settings
from cosmatter.corpus_preparation import corpus_manifest_from_review, write_corpus_manifest
from cosmatter.deepseek import DraftCompletion
from cosmatter.local_api import LocalApiError, LocalMissionApi, _candidate_payload
from cosmatter.pdf_task_registry import write_pdf_task
from cosmatter.source_map import write_source_map_for_document
from cosmatter.workflow_readiness import write_workflow_readiness
from cosmatter.mineru import MinerUBatch
from cosmatter.sciverse import SciverseResponse


class _FakeDeepSeek:
    def __init__(self, settings):
        self.settings = settings

    def draft(self, **_):
        return DraftCompletion(content='{"queries":["test"]}', model="deepseek-test", request_id="request-1")


class _FakeSciverse:
    def __init__(self, settings):
        self.settings = settings

    def agentic_search(self, query, *, top_k):
        return SciverseResponse(
            payload={
                "hits": [
                    {"doc_id": "doc-1", "title": "A bounded paper", "is_content_accessible": True, "score": 0.9}
                ]
            },
            status_code=200,
            request_id="search-1",
        )


class _FakeMinerU:
    def __init__(self, _settings):
        pass

    def submit_local_file(self, _file_name, _content):
        return MinerUBatch(batch_id="batch-test", upload_url="redacted", state="pending")

    def get_batch(self, _batch_id):
        return MinerUBatch(batch_id="batch-test", upload_url="redacted", state="pending")


class _FakeCrossref:
    def __init__(self, _settings):
        pass

    def work_references_by_doi(self, _doi):
        return SimpleNamespace(referenced_dois=())


class _FakeOpenAlex:
    def __init__(self, _settings):
        pass

    def citing_dois_by_doi(self, _doi, *, limit):
        return ()


class LocalMissionApiTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.runs = Path(self.directory.name) / "runs"
        self.api = LocalMissionApi(
            self.runs,
            settings_loader=lambda: Settings.load(
                {"LLM_PROVIDER": "deepseek", "LLM_MODEL": "deepseek-v4-flash", "DEEPSEEK_API_KEY": "test", "SCIVERSE_API_TOKEN": "test"}
            ),
        )

    def tearDown(self):
        self.directory.cleanup()

    def _mission(self):
        return self.api.create_mission(
            {
                "run_id": "live_001",
                "question": "How do conditions affect phase stability?",
                "material": "BiFeO3",
                "property": "phase stability",
                "scope": "epitaxial films",
            }
        )

    def test_status_and_mission_creation_do_not_return_a_secret(self):
        status = self.api.status()
        created = self._mission()
        self.assertEqual(status["api_mode"], "loopback_only")
        self.assertTrue(status["providers"]["deepseek"])
        self.assertEqual(created["run_id"], "live_001")
        self.assertTrue((self.runs / "live_001" / "mission.json").is_file())
        self.assertNotIn("test", json.dumps({"status": status, "created": created}))

    def test_imported_run_package_resumes_the_audited_stage(self):
        mission = self._mission()
        stages = ("intake", "plan", "retrieval", "screening", "parse", "extraction", "gap", "report", "evaluation")
        readiness = {
            "schema_version": "1.0",
            "mission_id": mission["mission_id"],
            "trust_status": "derived_workflow_readiness_not_scientific_evidence",
            "stages": [
                {"stage": stage, "status": "completed" if index < 3 else ("waiting_human_review" if index == 3 else "blocked"), "counts": {}}
                for index, stage in enumerate(stages)
            ],
            "next_stage": "screening",
        }
        write_workflow_readiness(self.runs / "live_001", readiness)
        package = json.loads(self.api.export_run_package("live_001").decode("utf-8"))
        restored = self.api.import_run_package({"run_id": "resume_001", "package": package})
        self.assertEqual(restored["next_stage"], "screening")

    def test_live_draft_requires_review_before_sciverse_query(self):
        self._mission()
        with patch("cosmatter.local_api.DeepSeekAdapter", _FakeDeepSeek):
            draft = self.api.draft_plan("live_001")
        self.assertEqual(draft["trust_status"], "untrusted_draft")
        self.assertTrue((self.runs / "live_001" / "research_plan_draft.json").is_file())
        approved = self.api.approve_plan(
            "live_001",
            {
                "subquestions": ["Which conditions differ?"],
                "queries": ["BiFeO3 phase stability epitaxial"],
                "counter_queries": ["BiFeO3 contradictory phase reports"],
            },
        )
        self.assertEqual(approved["queries"], ["BiFeO3 phase stability epitaxial"])
        with patch("cosmatter.local_api.SciverseAdapter", _FakeSciverse):
            result = self.api.execute_plan_query("live_001", {"query_index": 0, "counter": False})
        self.assertEqual(result["candidate_count"], 1)
        self.assertEqual(result["candidates"][0]["document_id"], "doc-1")
        artifact = json.loads((self.runs / "live_001" / "retrieval_candidates.json").read_text(encoding="utf-8"))
        self.assertEqual(artifact["candidates"][0]["retrieval_origins"][0]["provider"], "sciverse")
        self.assertNotIn("request-1", json.dumps(result))


    def test_condition_diagnostics_and_gap_candidates_require_cross_paper_accepted_evidence(self):
        mission = self._mission()
        self.api.approve_plan(
            "live_001",
            {
                "subquestions": ["Which conditions differ?"],
                "queries": ["BiFeO3 phase stability epitaxial"],
                "counter_queries": ["BiFeO3 contradictory phase reports"],
            },
        )
        with patch("cosmatter.local_api.SciverseAdapter", _FakeSciverse):
            self.api.execute_plan_query("live_001", {"query_index": 0, "counter": False})
            self.api.execute_plan_query("live_001", {"query_index": 0, "counter": True})

        run_dir = self.runs / "live_001"
        base_conditions = {
            "sample_form": "epitaxial film",
            "substrate": "SrTiO3",
            "thickness_nm": 40,
            "temperature_k": 300,
            "method": "xrd",
        }
        cards = [
            {
                "evidence_id": "ev_support", "claim": "phase is stable under compressive strain",
                "stance": "support", "material": "BiFeO3", "property_name": "phase stability",
                "conditions": base_conditions | {"strain_percent": -1.2}, "quote": "Reviewed support excerpt.",
                "review_status": "accepted",
                "provenance": {"document_id": "doi:10.1000/support", "locator": "markdown_line:10-11", "source": "private_markdown", "access_policy": "authorized"},
            },
            {
                "evidence_id": "ev_contradict", "claim": "phase is not stable under tensile strain",
                "stance": "contradict", "material": "BiFeO3", "property_name": "phase stability",
                "conditions": base_conditions | {"strain_percent": 1.1}, "quote": "Reviewed contradiction excerpt.",
                "review_status": "accepted",
                "provenance": {"document_id": "doi:10.1000/contradict", "locator": "markdown_line:21-22", "source": "private_markdown", "access_policy": "authorized"},
            },
        ]
        decisions = [
            {"mission_id": mission["mission_id"], "evidence_id": card["evidence_id"], "status": "accepted", "reason": "human-reviewed complete conditions", "missing_conditions": []}
            for card in cards
        ]
        (run_dir / "evidence_cards.json").write_text(json.dumps(cards), encoding="utf-8")
        (run_dir / "verification_decisions.json").write_text(json.dumps(decisions), encoding="utf-8")
        for index, card in enumerate(cards, start=1):
            write_source_map_for_document(run_dir, {
                "schema_version": "1.0", "mission_id": mission["mission_id"],
                "trust_status": "human_reviewed_parser_selection", "document_id": card["provenance"]["document_id"],
                "provider": "mineru", "task_id_sha256": f"{index:064x}",
                "segments": [{
                    "segment_id": f"source_{index}", "locator": card["provenance"]["locator"], "kind": "paragraph",
                    "quote": card["quote"], "quote_sha256": hashlib.sha256(card["quote"].encode("utf-8")).hexdigest(),
                }],
            })

        matrix = self.api.diagnose_conditions("live_001")
        self.assertEqual(matrix["matrix_row_count"], 1)
        stored_matrix = json.loads((run_dir / "condition_matrix.json").read_text(encoding="utf-8"))
        self.assertEqual(stored_matrix[0]["supporting_evidence_ids"], ["ev_support"])
        self.assertEqual(stored_matrix[0]["contradicting_evidence_ids"], ["ev_contradict"])
        self.assertIn("strain_percent", stored_matrix[0]["differing_fields"])
        self.assertNotIn("Reviewed support excerpt.", json.dumps(stored_matrix))

        gaps = self.api.generate_gap_candidates("live_001")
        self.assertEqual(gaps["candidate_count"], 1)
        candidate = json.loads((run_dir / "research_gap_candidates.json").read_text(encoding="utf-8"))[0]
        self.assertEqual(candidate["review_status"], "candidate_requires_human_review")
        self.assertEqual(set(candidate["evidence_ids"]), {"ev_support", "ev_contradict"})
        self.assertEqual(candidate["counterevidence_boundary"]["status"], "all_approved_counterevidence_queries_recorded")

        cards[1]["provenance"]["document_id"] = cards[0]["provenance"]["document_id"]
        (run_dir / "evidence_cards.json").write_text(json.dumps(cards), encoding="utf-8")
        # Keep the altered fixture exactly source-mapped so the next gate—not
        # provenance integrity—explains why one document cannot form a comparison.
        write_source_map_for_document(run_dir, {
            "schema_version": "1.0", "mission_id": mission["mission_id"],
            "trust_status": "human_reviewed_parser_selection", "document_id": cards[0]["provenance"]["document_id"],
            "provider": "mineru", "task_id_sha256": "f" * 64,
            "segments": [{
                "segment_id": f"same_doc_{index}", "locator": card["provenance"]["locator"], "kind": "paragraph",
                "quote": card["quote"], "quote_sha256": hashlib.sha256(card["quote"].encode("utf-8")).hexdigest(),
            } for index, card in enumerate(cards, start=1)],
        })
        with self.assertRaisesRegex(LocalApiError, "two distinct source documents"):
            self.api.diagnose_conditions("live_001")
    def test_approved_local_corpus_search_is_gated_and_keeps_private_paths_out_of_run(self):
        self._mission()
        self.api.approve_plan(
            "live_001",
            {
                "subquestions": ["Which conditions differ?"],
                "queries": ["BiFeO3 phase stability epitaxial"],
                "counter_queries": ["BiFeO3 contradictory phase reports"],
            },
        )
        run_dir = self.runs / "live_001"
        manifest = corpus_manifest_from_review(
            mission_id="mission_" + "placeholder",
            material="BiFeO3",
            selection={"corpus_id": "bfo_local", "material": "BiFeO3", "documents": [
                {"document_id": "doc_local", "title": "BiFeO3 phase stability epitaxial", "doi": None, "access_policy": "institutional_access_internal_review_only"},
            ]},
        )
        mission_id = json.loads((run_dir / "mission.json").read_text(encoding="utf-8"))["mission_id"]
        manifest["mission_id"] = mission_id
        write_corpus_manifest(run_dir, manifest)
        private_markdown = Path(self.directory.name) / "private_source.md"
        private_index = Path(self.directory.name) / "private_index.json"
        private_markdown.write_text("BiFeO3 phase stability in epitaxial films.", encoding="utf-8")
        private_index.write_text(json.dumps({"documents": [{
            "document_id": "doc_local",
            "title": "BiFeO3 phase stability epitaxial",
            "path": str(private_markdown),
            "parser_provenance": "mineru_reviewed_local_output",
        }]}), encoding="utf-8")
        result = self.api.execute_plan_local_corpus_query("live_001", {"query_index": 0, "index_path": str(private_index)})
        artifacts = "\n".join(item.read_text(encoding="utf-8") for item in run_dir.rglob("*") if item.is_file())
        self.assertEqual(result["candidate_count"], 1)
        self.assertEqual(result["candidates"][0]["document_id"], "doc_local")
        self.assertNotIn(str(private_index), json.dumps(result))
        self.assertNotIn(str(private_markdown), artifacts)
        self.assertNotIn(str(private_index), artifacts)


    def test_manual_doi_confirmation_requires_completed_private_parse_and_is_audited(self):
        mission = self._mission()
        run_dir = self.runs / "live_001"
        intake = {
            "schema_version": "1.0",
            "mission_id": mission["mission_id"],
            "document_id": "pdf_0123456789abcdef01234567",
            "file_name": "authorized.pdf",
            "pdf_sha256": "digest",
            "byte_count": 12,
            "consent": True,
            "batch_id": "batch-test",
            "state": "done",
            "markdown_sha256": "markdown-digest",
            "doi": None,
            "doi_status": "needs_human_doi",
        }
        (run_dir / "pdf_intake.json").write_text(json.dumps(intake), encoding="utf-8")
        with self.assertRaisesRegex(LocalApiError, "explicit human confirmation"):
            self.api.confirm_pdf_doi("live_001", {"doi": "10.1000/example"})
        result = self.api.confirm_pdf_doi("live_001", {"doi": "https://doi.org/10.1000/Example", "human_confirmed": True})
        self.assertEqual(result["doi"], "10.1000/example")
        self.assertEqual(result["doi_status"], "human_confirmed")
        with patch("cosmatter.local_api.CrossrefAdapter", _FakeCrossref), patch("cosmatter.local_api.OpenAlexAdapter", _FakeOpenAlex):
            expansion = self.api.expand_pdf_citations("live_001")
        self.assertEqual(expansion["node_count"], 1)
        events = (run_dir / "events.jsonl").read_text(encoding="utf-8")
        self.assertIn("pdf_doi_human_confirmed", events)
    def test_pdf_task_registry_requires_document_scope_and_preserves_other_tasks(self):
        mission = self._mission()
        run_dir = self.runs / "live_001"
        def task(document_id: str, batch_id: str) -> dict[str, object]:
            return {
                "schema_version": "1.0", "mission_id": mission["mission_id"], "document_id": document_id,
                "file_name": f"{document_id}.pdf", "pdf_sha256": "d" * 64, "byte_count": 12,
                "consent": True, "batch_id": batch_id, "state": "done", "markdown_sha256": "a" * 64,
                "doi": None, "doi_status": "needs_human_doi",
            }
        first = "pdf_0123456789abcdef01234567"
        second = "pdf_abcdef0123456789abcdef01"
        write_pdf_task(run_dir, mission["mission_id"], task(first, "batch-one"))
        write_pdf_task(run_dir, mission["mission_id"], task(second, "batch-two"))
        with self.assertRaisesRegex(LocalApiError, "document_id is required"):
            self.api.pdf_status("live_001")
        tasks = self.api.pdf_tasks("live_001")
        self.assertEqual({first, second}, {item["document_id"] for item in tasks["tasks"]})
        confirmed = self.api.confirm_pdf_doi("live_001", {"document_id": second, "doi": "10.1000/second", "human_confirmed": True})
        self.assertEqual(confirmed["document_id"], second)
        registry = self.api.pdf_tasks("live_001")
        by_id = {item["document_id"]: item for item in registry["tasks"]}
        self.assertEqual(by_id[second]["doi_status"], "human_confirmed")
        self.assertEqual(by_id[first]["doi_status"], "needs_human_doi")
    def test_private_pdf_source_map_requires_human_confirmation_and_matching_lines(self):
        mission = self._mission()
        run_dir = self.runs / "live_001"
        intake = {
            "schema_version": "1.0", "mission_id": mission["mission_id"],
            "document_id": "pdf_0123456789abcdef01234567", "file_name": "authorized.pdf",
            "pdf_sha256": "digest", "byte_count": 12, "consent": True,
            "batch_id": "batch-test", "state": "done", "markdown_sha256": "a" * 64,
            "doi": None, "doi_status": "needs_human_doi",
        }
        (run_dir / "pdf_intake.json").write_text(json.dumps(intake), encoding="utf-8")
        selection = {"segments": [{"locator": "markdown_line:2-2", "kind": "paragraph", "quote": "The phase boundary shifts with strain."}]}
        with patch("cosmatter.local_api.read_markdown", return_value=b"# Title\nThe phase boundary shifts with strain.\n"):
            with self.assertRaisesRegex(LocalApiError, "explicit human confirmation"):
                self.api.record_pdf_source_map("live_001", selection)
            with self.assertRaisesRegex(LocalApiError, "does not match"):
                self.api.record_pdf_source_map("live_001", {"human_confirmed": True, "segments": [{"locator": "markdown_line:2-2", "kind": "paragraph", "quote": "Invented claim"}]})
            result = self.api.record_pdf_source_map("live_001", {"human_confirmed": True, **selection})
        self.assertEqual(result["document_id"], intake["document_id"])
        self.assertEqual(result["segment_count"], 1)
        status = self.api.pdf_status("live_001")
        self.assertEqual(status["source_map_review_status"], "recorded")
        self.assertEqual(status["source_map_segment_count"], 1)
        self.assertNotIn("phase boundary shifts", json.dumps(status))
        restored = self.api.pdf_source_map_context("live_001")
        self.assertEqual(restored["segments"], [{"segment_id": "private_md_001", "locator": "markdown_line:2-2", "kind": "paragraph"}])
        self.assertNotIn("phase boundary shifts", json.dumps(restored))
        stored = next((run_dir / "source_maps").glob("*.json"))
        source_map = json.loads(stored.read_text(encoding="utf-8"))
        self.assertEqual(source_map["schema_version"], "1.1")
        self.assertEqual(source_map["source_markdown_sha256"], "a" * 64)
        self.assertNotIn("private", stored.read_text(encoding="utf-8").replace("private_md", ""))
        self.assertIn("source_map_reviewed", (run_dir / "events.jsonl").read_text(encoding="utf-8"))
        with self.assertRaisesRegex(LocalApiError, "explicit human confirmation"):
            self.api.record_pdf_material_facts("live_001", {"facts": []})
        facts = [{"fact_id": "phase_boundary", "segment_id": "private_md_001", "category": "property", "name": "phase boundary", "value": "shifts with strain", "unit": None, "normalized_value": "shifts with strain", "normalized_unit": None, "qualifiers": {}}]
        result = self.api.record_pdf_material_facts("live_001", {"human_confirmed": True, "facts": facts})
        self.assertEqual(result["document_id"], intake["document_id"])
        self.assertEqual(result["fact_count"], 1)
        stored_facts = next((run_dir / "material_facts").glob("*.json"))
        self.assertEqual(json.loads(stored_facts.read_text(encoding="utf-8"))["facts"][0]["locator"], "markdown_line:2-2")
        self.assertIn("material_facts_reviewed", (run_dir / "events.jsonl").read_text(encoding="utf-8"))
    def test_human_included_candidate_can_attach_authorized_pdf_to_same_run(self):
        self._mission()
        self.api.approve_plan(
            "live_001",
            {
                "subquestions": ["Which conditions differ?"],
                "queries": ["BiFeO3 phase stability epitaxial"],
                "counter_queries": ["BiFeO3 contradictory phase reports"],
            },
        )
        with patch("cosmatter.local_api.SciverseAdapter", _FakeSciverse):
            self.api.execute_plan_query("live_001", {"query_index": 0, "counter": False})
        self.api.record_candidate_screening(
            "live_001",
            {"decisions": [{"document_id": "doc-1", "decision": "include_for_fulltext", "reason_codes": ["material_match"]}]},
        )
        with patch("cosmatter.local_api.MinerUAdapter", _FakeMinerU), patch("cosmatter.local_api.write_pdf", return_value=(Path("private.pdf"), "digest")):
            result = self.api.create_pdf_run(
                {"run_id": "live_001", "candidate_document_id": "doc-1", "consent": True},
                "authorized.pdf",
                b"%PDF-1.7 test",
            )
        self.assertEqual(result["run_id"], "live_001")
        self.assertEqual(result["candidate_document_id"], "doc-1")
        intake = json.loads((self.runs / "live_001" / "pdf_intake.json").read_text(encoding="utf-8"))
        self.assertEqual(intake["candidate_document_id"], "doc-1")
        ledger = json.loads((self.runs / "live_001" / "source_parse_tasks.json").read_text(encoding="utf-8"))
        task = ledger["tasks"][0]
        self.assertEqual(task["document_id"], "doc-1")
        self.assertEqual(task["task_id"], "batch-test")
        self.assertEqual(task["state"], "pending")
        self.assertNotEqual(task["document_id"], intake["document_id"])
        status = self.api.pdf_status("live_001")
        self.assertEqual(status["candidate_document_id"], "doc-1")
        self.assertEqual(status["audit_document_id"], "doc-1")
        intake["state"] = "done"; intake["markdown_sha256"] = "b" * 64
        registry_path = self.runs / "live_001" / "pdf_intake_tasks.json"
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        registry["tasks"][0] = intake
        registry_path.write_text(json.dumps(registry), encoding="utf-8")
        with patch("cosmatter.local_api.read_markdown", return_value=b"# Title\nReviewed source excerpt.\n"):
            self.api.record_pdf_source_map("live_001", {"human_confirmed": True, "segments": [{"locator": "markdown_line:2-2", "kind": "paragraph", "quote": "Reviewed source excerpt."}]})
        with self.assertRaisesRegex(LocalApiError, "explicit human confirmation"):
            self.api.record_pdf_evidence_card("live_001", {"segment_id": "private_md_001", "claim": "A human-reviewed claim", "stance": "support", "conditions": {}, "reviewer_confidence": 0.8})
        evidence = self.api.record_pdf_evidence_card("live_001", {"human_confirmed": True, "segment_id": "private_md_001", "claim": "A human-reviewed claim", "stance": "support", "conditions": {"sample_form": "film", "strain_percent": 0, "substrate": "synthetic", "thickness_nm": 10, "temperature_k": 300, "method": "xrd"}, "reviewer_confidence": 0.8})
        self.assertEqual(evidence["document_id"], "doc-1")
        self.assertEqual(evidence["review_status"], "accepted")
        stored_evidence = json.loads((self.runs / "live_001" / "evidence_cards.json").read_text(encoding="utf-8"))
        self.assertEqual(stored_evidence[0]["quote"], "Reviewed source excerpt.")
        provenance_audit = json.loads((self.runs / "live_001" / "evidence_provenance_audit.json").read_text(encoding="utf-8"))
        self.assertEqual(provenance_audit["accepted_evidence_count"], 1)
        self.assertEqual(provenance_audit["exact_reviewed_source_map_match_count"], 1)
        self.assertEqual(provenance_audit["exact_source_map_match_rate"], 1.0)
        self.assertIn("human_evidence_card_accepted", (self.runs / "live_001" / "events.jsonl").read_text(encoding="utf-8"))
        with self.assertRaisesRegex(LocalApiError, "not approved"):
            self.api.create_pdf_run(
                {"run_id": "live_001", "candidate_document_id": "other-doc", "consent": True},
                "unauthorized.pdf",
                b"%PDF-1.7 test",
            )
    def test_question_candidates_require_distinct_reframed_focuses(self):
        original = "Why do thin-film studies disagree about phase stability?"
        valid = {
            "candidates": [
                {"question": "What evidence landscape defines reported thin-film phase outcomes?", "material": "thin films", "property": "reported phase outcomes", "scope": "studies and evidence boundaries", "kind": "survey"},
                {"question": "Which comparable preparation and measurement conditions explain divergent thin-film reports?", "material": "thin films", "property": "reporting differences", "scope": "conditions and comparability", "kind": "contrast"},
                {"question": "Which located observations distinguish competing explanations for the reported differences?", "material": "thin films", "property": "discriminating evidence", "scope": "source locations and review", "kind": "mechanism"},
            ]
        }
        result = _candidate_payload(valid, original_question=original)
        self.assertEqual({item["kind"] for item in result}, {"survey", "contrast", "mechanism"})
        repeated = {"candidates": [{**item, "question": original if index == 0 else item["question"]} for index, item in enumerate(valid["candidates"])]}
        with self.assertRaisesRegex(ValueError, "reframe"):
            _candidate_payload(repeated, original_question=original)
        missing_focus = {"candidates": [{**item, "kind": "survey"} for item in valid["candidates"]]}
        with self.assertRaisesRegex(ValueError, "cover survey"):
            _candidate_payload(missing_focus, original_question=original)
    def test_candidate_screening_is_complete_human_gate_before_fulltext(self):
        self._mission()
        self.api.approve_plan(
            "live_001",
            {
                "subquestions": ["Which conditions differ?"],
                "queries": ["BiFeO3 phase stability epitaxial"],
                "counter_queries": ["BiFeO3 contradictory phase reports"],
            },
        )
        with patch("cosmatter.local_api.SciverseAdapter", _FakeSciverse):
            self.api.execute_plan_query("live_001", {"query_index": 0, "counter": False})
        template = self.api.candidate_screening_template("live_001")
        self.assertEqual(template["candidate_count"], 1)
        self.assertEqual(template["candidates"][0]["document_id"], "doc-1")
        self.assertEqual(template["decisions"][0]["decision"], "unreviewed")
        with self.assertRaises(LocalApiError):
            self.api.record_candidate_screening("live_001", {"decisions": []})
        result = self.api.record_candidate_screening(
            "live_001",
            {"decisions": [{"document_id": "doc-1", "decision": "include_for_fulltext", "reason_codes": ["material_match"]}]},
        )
        self.assertEqual(result["decision_counts"], {"include_for_fulltext": 1})
        artifact = json.loads((self.runs / "live_001" / "candidate_screening.json").read_text(encoding="utf-8"))
        self.assertEqual(artifact["trust_status"], "human_reviewed_candidate_screening_not_scientific_evidence")
        persisted = self.api.candidate_screening_template("live_001")
        self.assertEqual(persisted["trust_status"], "human_reviewed_candidate_screening_not_scientific_evidence")
        self.assertEqual(persisted["decisions"][0]["decision"], "include_for_fulltext")
    def test_automatic_mission_reaches_success_terminal_with_metadata_only_candidates(self):
        payload = {
            "run_id": "auto_success_001",
            "question": "How do conditions affect phase stability in epitaxial BiFeO3 films?",
            "material": "BiFeO3",
            "property": "phase stability",
            "scope": "epitaxial films",
            "sources": ["sciverse"],
            "consent": True,
        }
        with patch("cosmatter.local_api.DeepSeekAdapter", _FakeDeepSeek), patch("cosmatter.local_api.SciverseAdapter", _FakeSciverse):
            created = self.api.auto_mission(payload)
            self.assertEqual(created["candidate_count"], 0)
            for _ in range(100):
                status = self.api.run_status("auto_success_001")
                if status["automatic_execution"]["state"] in {"succeeded", "failed", "cancelled"}:
                    break
                time.sleep(0.01)
            else:
                self.fail("automatic mission did not reach a terminal state")
        self.assertEqual(status["automatic_execution"]["state"], "succeeded")
        self.assertEqual(status["automatic_execution"]["candidate_count"], 1)
        artifact = json.loads((self.runs / "auto_success_001" / "retrieval_candidates.json").read_text(encoding="utf-8"))
        self.assertEqual(artifact["candidate_count"], 1)
        self.assertEqual(artifact["search_count"], 1)
        self.assertFalse((self.runs / "auto_success_001" / "evidence_cards.json").exists())
    def test_automatic_mission_keeps_successful_provider_candidates_when_another_source_fails(self):
        class FailingCrossrefMetadata:
            def __init__(self, _settings):
                pass

            def search_crossref(self, _query, *, top_k):
                raise RuntimeError("Crossref temporarily unavailable")

        payload = {
            "run_id": "auto_partial_001",
            "question": "How do conditions affect phase stability in epitaxial BiFeO3 films?",
            "material": "BiFeO3",
            "property": "phase stability",
            "scope": "epitaxial films",
            "sources": ["sciverse", "crossref"],
            "consent": True,
        }
        with patch("cosmatter.local_api.DeepSeekAdapter", _FakeDeepSeek), patch("cosmatter.local_api.SciverseAdapter", _FakeSciverse), patch("cosmatter.local_api.MetadataSearchAdapter", FailingCrossrefMetadata):
            self.api.auto_mission(payload)
            for _ in range(100):
                status = self.api.run_status("auto_partial_001")
                if status["automatic_execution"]["state"] in {"succeeded", "failed", "cancelled"}:
                    break
                time.sleep(0.01)
            else:
                self.fail("partial automatic mission did not reach a terminal state")
        automatic = status["automatic_execution"]
        self.assertEqual(automatic["state"], "succeeded")
        self.assertEqual(automatic["candidate_count"], 1)
        self.assertEqual(automatic["failure_count"], 1)
        self.assertEqual(automatic["failed_sources"], ["Crossref"])
        self.assertTrue((self.runs / "auto_partial_001" / "retrieval_candidates.json").exists())
        events = [json.loads(line) for line in (self.runs / "auto_partial_001" / "events.jsonl").read_text(encoding="utf-8").splitlines()]
        warnings = [event for event in events if event["event_type"] == "automatic_metadata_source_failed"]
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0]["payload"]["source"], "Crossref")

    def test_automatic_mission_fails_only_when_every_selected_source_fails(self):
        class FailingSciverse(_FakeSciverse):
            def agentic_search(self, _query, *, top_k):
                raise RuntimeError("Sciverse temporarily unavailable")

        payload = {
            "run_id": "auto_all_failed_001",
            "question": "How do conditions affect phase stability in epitaxial BiFeO3 films?",
            "material": "BiFeO3",
            "property": "phase stability",
            "scope": "epitaxial films",
            "sources": ["sciverse"],
            "consent": True,
        }
        with patch("cosmatter.local_api.DeepSeekAdapter", _FakeDeepSeek), patch("cosmatter.local_api.SciverseAdapter", FailingSciverse):
            self.api.auto_mission(payload)
            for _ in range(100):
                status = self.api.run_status("auto_all_failed_001")
                if status["automatic_execution"]["state"] in {"succeeded", "failed", "cancelled"}:
                    break
                time.sleep(0.01)
            else:
                self.fail("failed automatic mission did not reach a terminal state")
        automatic = status["automatic_execution"]
        self.assertEqual(automatic["state"], "failed")
        self.assertEqual(automatic["candidate_count"], 0)
        self.assertEqual(automatic["failure_count"], 1)
        self.assertEqual(automatic["failed_sources"], ["Sciverse"])
        self.assertFalse((self.runs / "auto_all_failed_001" / "retrieval_candidates.json").exists())

    def test_automatic_mission_returns_run_id_before_retrieval_and_cancellation_blocks_late_artifacts(self):
        started = threading.Event()
        released = threading.Event()

        class BlockingSciverse(_FakeSciverse):
            def agentic_search(self, query, *, top_k):
                started.set()
                if not released.wait(timeout=3):
                    raise AssertionError("test did not release the mocked provider")
                return super().agentic_search(query, top_k=top_k)

        payload = {
            "run_id": "auto_001",
            "question": "How do conditions affect phase stability in epitaxial BiFeO3 films?",
            "material": "BiFeO3",
            "property": "phase stability",
            "scope": "epitaxial films",
            "sources": ["sciverse"],
            "consent": True,
        }
        with patch("cosmatter.local_api.DeepSeekAdapter", _FakeDeepSeek), patch("cosmatter.local_api.SciverseAdapter", BlockingSciverse):
            created = self.api.auto_mission(payload)
            self.assertEqual(created["run_id"], "auto_001")
            self.assertEqual(created["candidate_count"], 0)
            self.assertTrue(started.wait(timeout=3))
            status = self.api.run_status("auto_001")
            automatic = status["automatic_execution"]
            self.assertIn(automatic["state"], {"queued", "running"})
            self.assertEqual(automatic["candidate_count"], 0)
            self.api.cancel("auto_001")
            released.set()
            worker = self.api._automatic_jobs.get("auto_001")
            if worker is not None:
                worker.join(timeout=3)
        final_status = self.api.run_status("auto_001")
        self.assertEqual(final_status["state"], "CANCELLED")
        self.assertEqual(final_status["automatic_execution"]["state"], "cancelled")
        self.assertFalse((self.runs / "auto_001" / "retrieval_candidates.json").exists())
if __name__ == "__main__":
    unittest.main()
