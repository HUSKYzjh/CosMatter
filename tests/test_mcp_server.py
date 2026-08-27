from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path

from cosmatter.local_api import LocalMissionApi
from cosmatter.mcp_server import CosMatterMcpServer, MCP_PROTOCOL_VERSION, serve_stdio


class _Api:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    def create_mission(self, payload: object) -> dict[str, object]:
        self.calls.append(("create", payload))
        return {"run_id": "bfo_001", "mission_id": "mission_bfo_001"}

    def draft_plan(self, run_id: str) -> dict[str, object]:
        self.calls.append(("draft", run_id))
        return {"run_id": run_id, "trust_status": "untrusted_draft"}

    def approve_plan(self, run_id: str, payload: object) -> dict[str, object]:
        self.calls.append(("approve", (run_id, payload)))
        return {"run_id": run_id, "plan_id": "plan_001"}

    def execute_plan_query(self, run_id: str, payload: object) -> dict[str, object]:
        self.calls.append(("search", (run_id, payload)))
        return {"run_id": run_id, "candidate_count": 2}

    def execute_plan_local_corpus_query(self, run_id: str, payload: object) -> dict[str, object]:
        self.calls.append(("local_search", (run_id, payload)))
        return {"run_id": run_id, "candidate_count": 1, "source": "authorized_local_parsed_corpus"}


class McpServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.api = _Api()
        self.server = CosMatterMcpServer(self.api)  # type: ignore[arg-type]

    def test_initialize_and_list_tools(self) -> None:
        initialized = self.server.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
        self.assertEqual(initialized["result"]["protocolVersion"], MCP_PROTOCOL_VERSION)  # type: ignore[index]
        listed = self.server.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        tools = listed["result"]["tools"]  # type: ignore[index]
        self.assertEqual([tool["name"] for tool in tools], ["cosmatter_create_mission", "cosmatter_draft_plan", "cosmatter_approve_plan", "cosmatter_execute_approved_search", "cosmatter_execute_approved_local_corpus_search"])

    def test_create_and_approved_search_dispatch(self) -> None:
        created = self.server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "cosmatter_create_mission", "arguments": {"question": "q", "material": "BiFeO3", "property": "phase stability", "scope": "thin films"}}})
        self.assertFalse(created["result"]["isError"])  # type: ignore[index]
        search = self.server.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "cosmatter_execute_approved_search", "arguments": {"run_id": "bfo_001", "query_index": 0, "counter": True, "sources": ["sciverse"]}}})
        self.assertFalse(search["result"]["isError"])  # type: ignore[index]
        self.assertEqual(self.api.calls[1], ("search", ("bfo_001", {"query_index": 0, "counter": True, "sources": ["sciverse"]})))
        local_search = self.server.handle({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "cosmatter_execute_approved_local_corpus_search", "arguments": {"run_id": "bfo_001", "query_index": 0, "index_path": "D:/private/index.json"}}})
        self.assertFalse(local_search["result"]["isError"])  # type: ignore[index]
        self.assertEqual(self.api.calls[2], ("local_search", ("bfo_001", {"query_index": 0, "index_path": "D:/private/index.json"})))

    def test_errors_are_safe_tool_results(self) -> None:
        response = self.server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "cosmatter_execute_approved_search", "arguments": {"query_index": 0}}})
        self.assertTrue(response["result"]["isError"])  # type: ignore[index]
        self.assertIn("run_id", response["result"]["structuredContent"]["error"])  # type: ignore[index]
        self.assertEqual(self.server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}), None)

    def test_strict_contract_rejects_unknown_and_invalid_arguments(self) -> None:
        unknown = self.server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "cosmatter_create_mission", "arguments": {"question": "q", "material": "BiFeO3", "property": "p", "scope": "s", "free_query": "not allowed"}}})
        self.assertTrue(unknown["result"]["isError"])  # type: ignore[index]
        self.assertIn("unsupported arguments", unknown["result"]["structuredContent"]["error"])  # type: ignore[index]
        invalid = self.server.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "cosmatter_execute_approved_search", "arguments": {"run_id": "bfo_001", "query_index": True}}})
        self.assertTrue(invalid["result"]["isError"])  # type: ignore[index]
        self.assertIn("query_index", invalid["result"]["structuredContent"]["error"])  # type: ignore[index]

    def test_real_local_mission_and_plan_closure_without_provider_calls(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            api = LocalMissionApi(Path(directory) / "runs")
            server = CosMatterMcpServer(api)
            created = server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "cosmatter_create_mission", "arguments": {"question": "Why differ?", "material": "BiFeO3", "property": "phase stability", "scope": "thin films", "run_id": "bfo_mcp_local"}}})
            self.assertFalse(created["result"]["isError"])  # type: ignore[index]
            approved = server.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "cosmatter_approve_plan", "arguments": {"run_id": "bfo_mcp_local", "subquestions": ["Which conditions differ?"], "queries": ["BiFeO3 phase stability thin film"], "counter_queries": ["BiFeO3 contradictory phase thin film"]}}})
            self.assertFalse(approved["result"]["isError"])  # type: ignore[index]
            self.assertTrue((Path(directory) / "runs" / "bfo_mcp_local" / "mission.json").exists())
            self.assertTrue((Path(directory) / "runs" / "bfo_mcp_local" / "flight_plan.json").exists())

    def test_stdio_handles_json_lines_and_parse_errors(self) -> None:
        stdin, stdout = io.StringIO('{"jsonrpc":"2.0","id":1,"method":"tools/list"}\nnot-json\n'), io.StringIO()
        self.assertEqual(serve_stdio(stdin=stdin, stdout=stdout, api=self.api), 0)  # type: ignore[arg-type]
        messages = [json.loads(line) for line in stdout.getvalue().splitlines()]
        self.assertEqual(messages[0]["result"]["tools"][0]["name"], "cosmatter_create_mission")
        self.assertEqual(messages[1]["error"]["code"], -32700)


if __name__ == "__main__":
    unittest.main()
