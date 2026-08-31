import json
import tempfile
import unittest
from pathlib import Path

from cosmatter.external_dispatch import EXTERNAL_DISPATCH_OPERATIONS, begin_external_dispatch, complete_external_dispatch, mark_external_dispatch_unknown
from cosmatter.models import MissionBrief
from cosmatter.operational_telemetry import OperationalTelemetryError, operational_telemetry, validate_operational_telemetry
from cosmatter.provider_receipts import append_provider_receipt, sciverse_search_receipt


class OperationalTelemetryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.mission = MissionBrief("private telemetry question", "BiFeO3", "phase stability", "private scope", mission_id="mission_telemetry")

    def test_aggregates_receipts_and_dispatch_states_without_identifiers_or_queries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            receipt = sciverse_search_receipt(query="private query text", top_k=3, status_code=200, request_id="provider-request-1", candidate_count=2)
            append_provider_receipt(run, receipt)
            begin_external_dispatch(run, mission_id=self.mission.mission_id, dsh_call_id="telemetry-complete-0001", plugin_id="literature.metadata_retrieval", operation="metadata_query", request_shape={"query_index": 0})
            complete_external_dispatch(run, mission_id=self.mission.mission_id, dsh_call_id="telemetry-complete-0001", provider_receipt_ids=(receipt["receipt_id"],))
            begin_external_dispatch(run, mission_id=self.mission.mission_id, dsh_call_id="telemetry-unknown-0002", plugin_id="literature.metadata_retrieval", operation="metadata_query", request_shape={"query_index": 1})
            mark_external_dispatch_unknown(run, mission_id=self.mission.mission_id, dsh_call_id="telemetry-unknown-0002")
            telemetry = operational_telemetry(run, self.mission)

        self.assertEqual(telemetry["cost_latency_status"], "not_recorded")
        self.assertEqual(telemetry["provider_operations"], [{"provider": "sciverse", "operation": "agentic_search", "request_count": 1, "successful_response_count": 1, "client_error_count": 0, "server_error_count": 0, "other_status_count": 0}])
        self.assertEqual(telemetry["dispatch_operations"], [{"operation": "metadata_query", "dispatch_count": 2, "completed_count": 1, "incomplete_count": 0, "unknown_outcome_count": 1}])
        rendered = json.dumps(telemetry)
        self.assertNotIn("private query text", rendered)
        self.assertNotIn("provider-request-1", rendered)
        self.assertNotIn("telemetry-complete", rendered)
        self.assertNotIn("BiFeO3", rendered)

    def test_forwards_only_a_valid_human_reviewed_cost_latency_disclosure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            (run / "evaluation_api_cost_latency.json").write_text(json.dumps({
                "schema_version": "1.0", "mission_id": self.mission.mission_id, "corpus_id": "corpus_1",
                "trust_status": "human_reviewed_aggregate_evaluation_api_cost_latency", "measurement_scope": "local evaluation window",
                "providers": [{"provider_id": "sciverse", "request_count": 2, "successful_request_count": 2, "failed_request_count": 0, "currency": "USD", "total_cost": 0.25, "median_latency_seconds": 0.2, "p95_latency_seconds": 0.5}],
            }), encoding="utf-8")
            telemetry = operational_telemetry(run, self.mission)
            self.assertEqual(telemetry["cost_latency_status"], "recorded")
            self.assertEqual(telemetry["cost_latency"][0]["total_cost"], 0.25)
            (run / "evaluation_api_cost_latency.json").write_text("{}", encoding="utf-8")
            self.assertEqual(operational_telemetry(run, self.mission)["cost_latency_status"], "invalid")

    def test_includes_every_ledger_dispatch_operation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            for index, operation in enumerate(EXTERNAL_DISPATCH_OPERATIONS):
                call_id = f"telemetry-all-{index:04d}"
                begin_external_dispatch(run, mission_id=self.mission.mission_id, dsh_call_id=call_id, plugin_id="telemetry.external_probe", operation=operation, request_shape={"operation_index": index})
                mark_external_dispatch_unknown(run, mission_id=self.mission.mission_id, dsh_call_id=call_id)

            telemetry = operational_telemetry(run, self.mission)

        self.assertEqual(telemetry["dispatch_operations"], [
            {"operation": operation, "dispatch_count": 1, "completed_count": 0, "incomplete_count": 0, "unknown_outcome_count": 1}
            for operation in EXTERNAL_DISPATCH_OPERATIONS
        ])

    def test_schema_rejects_provider_identifier_or_counter_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            telemetry = operational_telemetry(Path(directory), self.mission)
        telemetry["provider_operations"] = [{"provider": "sciverse", "operation": "agentic_search", "request_count": 1, "successful_response_count": 0, "client_error_count": 0, "server_error_count": 0, "other_status_count": 0}]
        with self.assertRaises(OperationalTelemetryError):
            validate_operational_telemetry(telemetry, expected_mission_id=self.mission.mission_id)

    def test_schema_rejects_unknown_provider_operation_pair(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            telemetry = operational_telemetry(Path(directory), self.mission)
        telemetry["provider_operations"] = [{"provider": "sciverse", "operation": "unreviewed_operation", "request_count": 0, "successful_response_count": 0, "client_error_count": 0, "server_error_count": 0, "other_status_count": 0}]
        with self.assertRaises(OperationalTelemetryError):
            validate_operational_telemetry(telemetry, expected_mission_id=self.mission.mission_id)


if __name__ == "__main__":
    unittest.main()
