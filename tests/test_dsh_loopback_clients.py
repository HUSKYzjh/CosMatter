from __future__ import annotations

import json
import os
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from cosmatter.config import Settings
from cosmatter.deepseek import DraftCompletion
from cosmatter.local_api import LocalMissionApi
from cosmatter.mineru import MinerUTask
from cosmatter.models import AccessPolicy, EvidenceCard, Provenance, ReviewStatus, Stance
from cosmatter.sciverse import SciverseResponse
from cosmatter.ui_preview import build_ui_preview_server
from cosmatter.verification import VerificationDecision


class _ResearchFakeDeepSeek:
    def __init__(self, _settings) -> None:
        pass

    def draft(self, **_) -> DraftCompletion:
        return DraftCompletion(content='{"queries":["bounded query"]}', model="test-deepseek", request_id="research-plan")


class _ResearchFakeSciverse:
    def __init__(self, _settings) -> None:
        pass

    def agentic_search(self, _query: str, *, top_k: int) -> SciverseResponse:
        return SciverseResponse(
            payload={"hits": [{"doc_id": "research-doc", "title": "Bounded candidate", "is_content_accessible": False, "score": 0.8}]},
            status_code=200,
            request_id="research-search",
        )


class _DocumentFakeSciverse:
    def __init__(self, _settings) -> None:
        pass

    def agentic_search(self, _query: str, *, top_k: int) -> SciverseResponse:
        return SciverseResponse(
            payload={"hits": [{"doc_id": "document-doc", "title": "Screened candidate", "is_content_accessible": True, "score": 0.8}]},
            status_code=200,
            request_id="document-search",
        )


class _DocumentFakeMinerU:
    def __init__(self, _settings) -> None:
        pass

    def submit_remote_source(self, _source_url: str) -> MinerUTask:
        return MinerUTask(task_id="document-task", state="pending", request_id="document-submit")

    def get_task(self, _task_id: str) -> MinerUTask:
        return MinerUTask(task_id="document-task", state="done", request_id="document-poll")


class DshLoopbackClientTests(unittest.TestCase):
    def test_compiled_dsh_clients_call_real_python_loopback_api(self) -> None:
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            sandbox = Path(directory)
            web = sandbox / "web"; web.mkdir(); (web / "index.html").write_text("<h1>preview</h1>", encoding="utf-8")
            api = LocalMissionApi(sandbox / "runs")
            created = api.create_mission({"run_id": "client_graph", "question": "How does strain change phase stability?", "material": "BiFeO3", "property": "phase stability", "scope": "synthetic thin films"})
            run_dir = sandbox / "runs" / "client_graph"
            card = EvidenceCard("Reviewed synthetic claim", Stance.SUPPORT, "BiFeO3", "phase stability", {"strain_percent": 1.0}, "private source quote", Provenance("synthetic-doc", "line:1", "fixture", access_policy=AccessPolicy.AUTHORIZED), evidence_id="evidence-client")
            decision = VerificationDecision(str(created["mission_id"]), "evidence-client", ReviewStatus.ACCEPTED, "synthetic review")
            (run_dir / "evidence_cards.json").write_text(json.dumps([card.to_dict()]), encoding="utf-8")
            (run_dir / "verification_decisions.json").write_text(json.dumps([decision.to_dict()]), encoding="utf-8")
            (run_dir / "ui.json").write_text(json.dumps({"schema_version": "1.0", "mission_id": created["mission_id"], "mission": {"mission_id": created["mission_id"]}}), encoding="utf-8")
            api.project_accepted_evidence_graph("client_graph")
            server = build_ui_preview_server(0, web, api=api)
            thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
            try:
                script = f'''
import {{ CosMatterMissionClient }} from {json.dumps((root / "plugins" / "dsh-cosmatter-mission-plugin" / "lib" / "client.js").as_uri())};
import {{ CosMatterLoopbackClient }} from {json.dumps((root / "plugins" / "dsh-cosmatter-graph-plugin" / "lib" / "client.js").as_uri())};
import {{ CosMatterObservabilityClient }} from {json.dumps((root / "plugins" / "dsh-cosmatter-observability-plugin" / "lib" / "client.js").as_uri())};
import {{ CosMatterPolicyClient }} from {json.dumps((root / "plugins" / "dsh-cosmatter-policy-plugin" / "lib" / "client.js").as_uri())};
const baseUrl = process.env.COSMATTER_TEST_BASE_URL;
const mission = await new CosMatterMissionClient({{ baseUrl }}).create({{ question: 'How does pressure change phase stability?', material: 'BiFeO3', property: 'phase stability', scope: 'synthetic scope', run_id: 'client_mission' }});
const graph = await new CosMatterLoopbackClient({{ baseUrl }}).graph('client_graph', {{ nodeType: 'EvidenceCard', limit: 25 }});
const workflow = await new CosMatterObservabilityClient({{ baseUrl }}).workflowStatus('client_graph');
const stageContract = await new CosMatterObservabilityClient({{ baseUrl }}).stageContract('client_graph');
const telemetry = await new CosMatterObservabilityClient({{ baseUrl }}).operationalTelemetry('client_graph');
const dag = await new CosMatterObservabilityClient({{ baseUrl }}).workflowDag('client_graph');
const artifacts = await new CosMatterObservabilityClient({{ baseUrl }}).artifactManifest('client_graph');
const catalogue = await new CosMatterPolicyClient({{ baseUrl }}).catalogue();
const authorization = await new CosMatterPolicyClient({{ baseUrl }}).authorizationPlan('client_graph', 'graph.plan_assist', ['mission_scoped_egress_consent']);
console.log(JSON.stringify({{ mission, graph, workflow, stageContract, telemetry, dag, artifacts, catalogue, authorization }}));
'''
                environment = {**os.environ, "COSMATTER_TEST_BASE_URL": f"http://127.0.0.1:{server.server_port}"}
                result = subprocess.run(["node", "--input-type=module", "-e", script], cwd=root, env=environment, text=True, encoding="utf-8", capture_output=True, timeout=15)
                if result.returncode:
                    self.fail(f"compiled DSH client failed: {result.stderr}\n{result.stdout}")
                payload = json.loads(result.stdout)
                self.assertEqual(payload["mission"]["run_id"], "client_mission")
                self.assertEqual(payload["graph"]["nodes"][0]["node_type"], "EvidenceCard")
                self.assertNotIn("private source quote", json.dumps(payload["graph"]))
                self.assertEqual(payload["workflow"]["run_id"], "client_graph")
                self.assertEqual(payload["workflow"]["trust_status"], "loopback_workflow_status_not_scientific_evidence")
                self.assertNotIn("How does strain", json.dumps(payload["workflow"]))
                self.assertEqual(payload["stageContract"]["schema_version"], "cosmatter.stage-contract/v1")
                self.assertEqual(payload["stageContract"]["stages"][1]["recovery_route"], "plan_review")
                self.assertNotIn("How does strain", json.dumps(payload["stageContract"]))
                self.assertNotIn("private source quote", json.dumps(payload["stageContract"]))
                self.assertEqual(payload["telemetry"]["schema_version"], "cosmatter.operational-telemetry/v1")
                self.assertEqual(payload["telemetry"]["cost_latency_status"], "not_recorded")
                self.assertNotIn("private source quote", json.dumps(payload["telemetry"]))
                self.assertEqual(payload["dag"]["schema_version"], "cosmatter.workflow-dag/v1")
                self.assertEqual(payload["dag"]["max_concurrency"], 1)
                self.assertEqual(payload["dag"]["scheduler_status"], "declarative_only_no_execution_authorization")
                self.assertNotIn("How does strain", json.dumps(payload["dag"]))
                self.assertEqual(payload["artifacts"]["schema_version"], "cosmatter.artifact/v1")
                self.assertEqual(payload["artifacts"]["artifacts"][0]["artifact_id"], "ui_bundle")
                self.assertNotIn("private source quote", json.dumps(payload["artifacts"]))
                self.assertEqual(payload["catalogue"]["trust_status"], "static_catalogue_not_plugin_execution_or_evidence_acceptance")
                workflow_descriptor = next(item for item in payload["catalogue"]["plugins"] if item["plugin_id"] == "workflow.status")
                self.assertEqual(workflow_descriptor["contract"]["execution_mode"], "read_only_projection")
                self.assertFalse(payload["authorization"]["permitted"])
                self.assertEqual(payload["authorization"]["trust_status"], "nonexecuting_authorization_plan_not_consent_or_execution")
            finally:
                server.shutdown(); server.server_close(); thread.join(timeout=2)

    def test_compiled_research_client_records_consent_before_loopback_dispatch(self) -> None:
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            sandbox = Path(directory)
            web = sandbox / "web"; web.mkdir(); (web / "index.html").write_text("<h1>preview</h1>", encoding="utf-8")
            api = LocalMissionApi(
                sandbox / "runs",
                settings_loader=lambda: Settings.load({"LLM_PROVIDER": "deepseek", "LLM_MODEL": "deepseek-v4-flash", "DEEPSEEK_API_KEY": "test", "SCIVERSE_API_TOKEN": "test"}),
            )
            api.create_mission({"run_id": "research_client", "question": "How does strain change phase stability?", "material": "BiFeO3", "property": "phase stability", "scope": "synthetic thin films"})
            with patch("cosmatter.local_api.DeepSeekAdapter", _ResearchFakeDeepSeek), patch("cosmatter.local_api.SciverseAdapter", _ResearchFakeSciverse):
                server = build_ui_preview_server(0, web, api=api)
                thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
                try:
                    script = f'''
import {{ CosMatterResearchClient }} from {json.dumps((root / "plugins" / "dsh-cosmatter-research-plugin" / "lib" / "client.js").as_uri())};
const client = new CosMatterResearchClient({{ baseUrl: process.env.COSMATTER_TEST_BASE_URL }});
const draft = await client.draftPlan('research_client', ['mission_scoped_egress_consent', 'deepseek_request_consent'], 'research-call-0001');
const plan = await client.approvePlan('research_client', {{ subquestions: ['Which conditions differ?'], queries: ['BiFeO3 phase stability'], counter_queries: ['BiFeO3 contradictory reports'] }});
const query = await client.executeQuery('research_client', {{ authorizations: ['mission_scoped_egress_consent', 'metadata_provider_consent'], query_index: 0, sources: ['sciverse'] }}, 'research-call-0002');
console.log(JSON.stringify({{ draft, plan, query }}));
'''
                    environment = {**os.environ, "COSMATTER_TEST_BASE_URL": f"http://127.0.0.1:{server.server_port}"}
                    result = subprocess.run(["node", "--input-type=module", "-e", script], cwd=root, env=environment, text=True, encoding="utf-8", capture_output=True, timeout=15)
                    if result.returncode:
                        self.fail(f"compiled DSH research client failed: {result.stderr}\n{result.stdout}")
                    payload = json.loads(result.stdout)
                    self.assertEqual(payload["draft"]["trust_status"], "untrusted_draft")
                    self.assertEqual(payload["plan"]["queries"], ["BiFeO3 phase stability"])
                    self.assertEqual(payload["query"]["candidate_count"], 1)
                    self.assertNotIn("test", json.dumps(payload))
                    events = (sandbox / "runs" / "research_client" / "events.jsonl").read_text(encoding="utf-8")
                    self.assertGreaterEqual(events.count('"event_type": "external_plugin_dispatch_authorized"'), 2)
                finally:
                    server.shutdown(); server.server_close(); thread.join(timeout=2)

    def test_compiled_document_client_only_dispatches_a_screened_candidate_and_returns_no_url(self) -> None:
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            sandbox = Path(directory)
            web = sandbox / "web"; web.mkdir(); (web / "index.html").write_text("<h1>preview</h1>", encoding="utf-8")
            api = LocalMissionApi(
                sandbox / "runs",
                settings_loader=lambda: Settings.load({"LLM_PROVIDER": "deepseek", "LLM_MODEL": "deepseek-v4-flash", "DEEPSEEK_API_KEY": "test", "SCIVERSE_API_TOKEN": "test", "MINERU_API_TOKEN": "test"}),
            )
            api.create_mission({"run_id": "document_client", "question": "How does strain change phase stability?", "material": "BiFeO3", "property": "phase stability", "scope": "synthetic thin films"})
            api.approve_plan("document_client", {"subquestions": ["Which conditions differ?"], "queries": ["BiFeO3 phase stability"], "counter_queries": ["BiFeO3 contradictory reports"]})
            with patch("cosmatter.local_api.SciverseAdapter", _DocumentFakeSciverse):
                api.execute_plan_query("document_client", {"query_index": 0, "sources": ["sciverse"]})
            with patch("cosmatter.local_api.MinerUAdapter", _DocumentFakeMinerU):
                server = build_ui_preview_server(0, web, api=api)
                thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
                try:
                    script = f'''
import {{ CosMatterDocumentClient }} from {json.dumps((root / "plugins" / "dsh-cosmatter-document-plugin" / "lib" / "client.js").as_uri())};
import {{ CosMatterReviewClient }} from {json.dumps((root / "plugins" / "dsh-cosmatter-review-plugin" / "lib" / "client.js").as_uri())};
const review = new CosMatterReviewClient({{ baseUrl: process.env.COSMATTER_TEST_BASE_URL }});
const template = await review.template('document_client');
const screening = await review.record('document_client', [{{ document_id: 'document-doc', decision: 'include_for_fulltext', reason_codes: ['material_match', 'property_match'] }}]);
const client = new CosMatterDocumentClient({{ baseUrl: process.env.COSMATTER_TEST_BASE_URL }});
const authorizations = ['mission_scoped_egress_consent', 'mineru_file_consent', 'private_content_to_mineru'];
const submitted = await client.submit('document_client', {{ authorizations, document_id: 'document-doc', source_url: 'https://example.org/paper.pdf' }}, 'document-call-0001');
const polled = await client.poll('document_client', {{ authorizations, document_id: 'document-doc' }}, 'document-call-0002');
console.log(JSON.stringify({{ template, screening, submitted, polled }}));
'''
                    environment = {**os.environ, "COSMATTER_TEST_BASE_URL": f"http://127.0.0.1:{server.server_port}"}
                    result = subprocess.run(["node", "--input-type=module", "-e", script], cwd=root, env=environment, text=True, encoding="utf-8", capture_output=True, timeout=15)
                    if result.returncode:
                        self.fail(f"compiled DSH document client failed: {result.stderr}\n{result.stdout}")
                    payload = json.loads(result.stdout)
                    self.assertEqual(payload["template"]["candidate_count"], 1)
                    self.assertEqual(payload["screening"]["candidate_count"], 1)
                    self.assertEqual(payload["submitted"]["task_state"], "pending")
                    self.assertEqual(payload["polled"]["task_state"], "done")
                    self.assertNotIn("example.org", json.dumps(payload))
                finally:
                    server.shutdown(); server.server_close(); thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
