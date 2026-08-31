"""Narrow stdio MCP server for CosMatter review-gated workflow operations."""

from __future__ import annotations

import json
import sys
from typing import Any, TextIO

from .local_api import LocalApiError, LocalMissionApi

MCP_PROTOCOL_VERSION = "2025-03-26"
SERVER_INFO = {"name": "cosmatter", "version": "0.1.0"}

_TOOL_ARGUMENT_RULES: dict[str, tuple[frozenset[str], frozenset[str]]] = {
    "cosmatter_create_mission": (frozenset({"question", "material", "property", "scope"}), frozenset({"question", "material", "property", "scope", "run_id", "mission_type"})),
    "cosmatter_draft_plan": (frozenset({"run_id", "authorizations", "dsh_call_id"}), frozenset({"run_id", "authorizations", "dsh_call_id", "actor"})),
    "cosmatter_approve_plan": (frozenset({"run_id", "subquestions", "queries", "counter_queries"}), frozenset({"run_id", "subquestions", "queries", "counter_queries", "max_rounds", "max_papers"})),
    "cosmatter_execute_approved_search": (frozenset({"run_id", "query_index", "sources", "authorizations", "dsh_call_id"}), frozenset({"run_id", "query_index", "counter", "sources", "authorizations", "dsh_call_id", "actor"})),
    "cosmatter_execute_approved_local_corpus_search": (frozenset({"run_id", "query_index", "index_path"}), frozenset({"run_id", "query_index", "index_path", "counter"})),
    "cosmatter_project_accepted_evidence_graph": (frozenset({"run_id"}), frozenset({"run_id"})),
    "cosmatter_draft_graph_plan": (frozenset({"run_id", "node_ids", "intent"}), frozenset({"run_id", "node_ids", "intent"})),
    "cosmatter_approve_graph_plan": (frozenset({"run_id", "plan_id", "reviewer", "rationale"}), frozenset({"run_id", "plan_id", "reviewer", "rationale"})),
}


def _text_result(payload: dict[str, object], *, is_error: bool = False) -> dict[str, object]:
    return {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False, sort_keys=True)}], "structuredContent": payload, "isError": is_error}


def _tools() -> list[dict[str, object]]:
    return [
        {"name": "cosmatter_create_mission", "description": "Create a bounded materials-literature Mission Brief and fleet assignment locally. No external provider is called.", "inputSchema": {"type": "object", "additionalProperties": False, "required": ["question", "material", "property", "scope"], "properties": {"question": {"type": "string"}, "material": {"type": "string"}, "property": {"type": "string"}, "scope": {"type": "string"}, "run_id": {"type": "string"}, "mission_type": {"type": "string"}}}},
        {"name": "cosmatter_draft_plan", "description": "Create an untrusted plan draft for an active run only after explicit mission-scoped and DeepSeek consent. It records a hashed call identity, cannot execute until a human approves it, and never accepts evidence.", "inputSchema": {"type": "object", "additionalProperties": False, "required": ["run_id", "authorizations", "dsh_call_id"], "properties": {"run_id": {"type": "string"}, "authorizations": {"type": "array", "minItems": 2, "items": {"type": "string", "enum": ["mission_scoped_egress_consent", "deepseek_request_consent"]}}, "dsh_call_id": {"type": "string", "minLength": 1, "maxLength": 256}, "actor": {"type": "string", "minLength": 1, "maxLength": 200}}}},
        {"name": "cosmatter_approve_plan", "description": "Persist a human-reviewed bounded FlightPlan. This is required before an approved-plan search can execute.", "inputSchema": {"type": "object", "additionalProperties": False, "required": ["run_id", "subquestions", "queries", "counter_queries"], "properties": {"run_id": {"type": "string"}, "subquestions": {"type": "array", "items": {"type": "string"}}, "queries": {"type": "array", "items": {"type": "string"}}, "counter_queries": {"type": "array", "items": {"type": "string"}}, "max_rounds": {"type": "integer", "minimum": 1}, "max_papers": {"type": "integer", "minimum": 1}}}},
        {"name": "cosmatter_execute_approved_search", "description": "Execute exactly one approved metadata query only after explicit mission-scoped provider consent. It records a hashed call identity and provider receipts; it never converts a candidate into evidence or reads full text.", "inputSchema": {"type": "object", "additionalProperties": False, "required": ["run_id", "query_index", "sources", "authorizations", "dsh_call_id"], "properties": {"run_id": {"type": "string"}, "query_index": {"type": "integer", "minimum": 0}, "counter": {"type": "boolean", "default": False}, "sources": {"type": "array", "minItems": 1, "items": {"type": "string", "enum": ["sciverse", "openalex", "crossref"]}}, "authorizations": {"type": "array", "minItems": 2, "items": {"type": "string", "enum": ["mission_scoped_egress_consent", "metadata_provider_consent"]}}, "dsh_call_id": {"type": "string", "minLength": 1, "maxLength": 256}, "actor": {"type": "string", "minLength": 1, "maxLength": 200}}}},
        {"name": "cosmatter_execute_approved_local_corpus_search", "description": "Execute exactly one approved query against an explicit authorized local Sci-Base or reviewed Markdown index. The private index path and parsed text stay process-local; only metadata candidates are returned.", "inputSchema": {"type": "object", "additionalProperties": False, "required": ["run_id", "query_index", "index_path"], "properties": {"run_id": {"type": "string"}, "query_index": {"type": "integer", "minimum": 0}, "index_path": {"type": "string", "minLength": 1}, "counter": {"type": "boolean", "default": False}}}},
        {"name": "cosmatter_project_accepted_evidence_graph", "description": "Build and return a versioned mission-scoped graph from already accepted evidence only. It excludes quotations, private paths, provider payloads, and unreviewed cards; it is not a scientific conclusion.", "inputSchema": {"type": "object", "additionalProperties": False, "required": ["run_id"], "properties": {"run_id": {"type": "string"}}}},
        {"name": "cosmatter_draft_graph_plan", "description": "Record a bounded, untrusted graph-inspection draft for selected existing graph nodes. It cannot query a provider, modify the graph, execute an action, or accept evidence; a human must review any follow-up.", "inputSchema": {"type": "object", "additionalProperties": False, "required": ["run_id", "node_ids", "intent"], "properties": {"run_id": {"type": "string"}, "node_ids": {"type": "array", "minItems": 1, "maxItems": 25, "items": {"type": "string"}}, "intent": {"type": "string", "minLength": 1, "maxLength": 500}}}},
        {"name": "cosmatter_approve_graph_plan", "description": "Record a human acknowledgement for an existing graph-plan draft. This is not an execution grant and cannot alter graph data or accept evidence.", "inputSchema": {"type": "object", "additionalProperties": False, "required": ["run_id", "plan_id", "reviewer", "rationale"], "properties": {"run_id": {"type": "string"}, "plan_id": {"type": "string"}, "reviewer": {"type": "string", "minLength": 1, "maxLength": 200}, "rationale": {"type": "string", "minLength": 1, "maxLength": 1000}}}},
    ]


class CosMatterMcpServer:
    """JSON-RPC handler separated from standard I/O for deterministic tests."""

    def __init__(self, api: LocalMissionApi) -> None:
        self._api = api

    def handle(self, raw_request: object) -> dict[str, object] | None:
        if not isinstance(raw_request, dict):
            return _error(None, -32600, "request must be an object")
        request_id = raw_request.get("id")
        method = raw_request.get("method")
        if raw_request.get("jsonrpc") != "2.0" or not isinstance(method, str):
            return _error(request_id, -32600, "invalid JSON-RPC request")
        if method == "notifications/initialized":
            return None
        if method == "initialize":
            return _result(request_id, {"protocolVersion": MCP_PROTOCOL_VERSION, "capabilities": {"tools": {}}, "serverInfo": SERVER_INFO, "instructions": "CosMatter uses human-reviewed FlightPlans and evidence gates. Do not treat metadata candidates or model drafts as scientific evidence."})
        if method == "tools/list":
            return _result(request_id, {"tools": _tools()})
        if method == "tools/call":
            return self._call_tool(request_id, raw_request.get("params"))
        return _error(request_id, -32601, "method not found")

    def _call_tool(self, request_id: object, raw_params: object) -> dict[str, object]:
        if not isinstance(raw_params, dict):
            return _error(request_id, -32602, "tools/call params must be an object")
        tool_name, arguments = raw_params.get("name"), raw_params.get("arguments", {})
        if not isinstance(tool_name, str) or not isinstance(arguments, dict):
            return _error(request_id, -32602, "tool name and arguments are required")
        if tool_name not in _TOOL_ARGUMENT_RULES:
            return _error(request_id, -32602, "unknown CosMatter tool")
        try:
            _validate_arguments(tool_name, arguments)
            if tool_name == "cosmatter_create_mission":
                payload = self._api.create_mission(arguments)
            elif tool_name == "cosmatter_draft_plan":
                payload = self._api.draft_authorized_plan(_required_string(arguments, "run_id"), {key: value for key, value in arguments.items() if key != "run_id"})
            elif tool_name == "cosmatter_approve_plan":
                payload = self._api.approve_plan(_required_string(arguments, "run_id"), {key: value for key, value in arguments.items() if key != "run_id"})
            elif tool_name == "cosmatter_execute_approved_search":
                payload = self._api.execute_authorized_plan_query(_required_string(arguments, "run_id"), {key: value for key, value in arguments.items() if key != "run_id"})
            elif tool_name == "cosmatter_execute_approved_local_corpus_search":
                payload = self._api.execute_plan_local_corpus_query(_required_string(arguments, "run_id"), {key: value for key, value in arguments.items() if key != "run_id"})
            elif tool_name == "cosmatter_project_accepted_evidence_graph":
                payload = self._api.project_accepted_evidence_graph(_required_string(arguments, "run_id"))
            elif tool_name == "cosmatter_draft_graph_plan":
                payload = self._api.draft_graph_plan(_required_string(arguments, "run_id"), {key: value for key, value in arguments.items() if key != "run_id"})
            elif tool_name == "cosmatter_approve_graph_plan":
                payload = self._api.approve_graph_plan(_required_string(arguments, "run_id"), {key: value for key, value in arguments.items() if key != "run_id"})
            else:
                return _error(request_id, -32602, "unknown CosMatter tool")
        except (LocalApiError, ValueError) as error:
            return _result(request_id, _text_result({"error": str(error)}, is_error=True))
        return _result(request_id, _text_result(payload))


def serve_stdio(*, stdin: TextIO = sys.stdin, stdout: TextIO = sys.stdout, api: LocalMissionApi | None = None) -> int:
    """Serve newline-delimited JSON-RPC over standard input/output."""
    server = CosMatterMcpServer(api or LocalMissionApi.from_project())
    for line in stdin:
        if not line.strip():
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            response: dict[str, object] | None = _error(None, -32700, "parse error")
        else:
            response = server.handle(request)
        if response is not None:
            stdout.write(json.dumps(response, ensure_ascii=False, separators=(",", ":")) + "\n")
            stdout.flush()
    return 0



def _validate_arguments(tool_name: str, arguments: dict[str, Any]) -> None:
    required, allowed = _TOOL_ARGUMENT_RULES[tool_name]
    unexpected = sorted(set(arguments) - allowed)
    missing = sorted(required - set(arguments))
    if unexpected:
        raise ValueError(f"unsupported arguments: {', '.join(unexpected)}")
    if missing:
        raise ValueError(f"missing required arguments: {', '.join(missing)}")
    if tool_name == "cosmatter_approve_plan":
        for field in ("subquestions", "queries", "counter_queries"):
            value = arguments[field]
            if not isinstance(value, list) or not value or any(not isinstance(item, str) or not item.strip() for item in value):
                raise ValueError(f"{field} must be a nonempty list of strings")
        for field in ("max_rounds", "max_papers"):
            if field in arguments and (not isinstance(arguments[field], int) or isinstance(arguments[field], bool) or arguments[field] < 1):
                raise ValueError(f"{field} must be a positive integer")
    if tool_name == "cosmatter_draft_plan":
        authorizations, call_id = arguments["authorizations"], arguments["dsh_call_id"]
        if not isinstance(authorizations, list) or set(authorizations) != {"mission_scoped_egress_consent", "deepseek_request_consent"}:
            raise ValueError("authorizations must contain the exact DeepSeek consent pair")
        if not isinstance(call_id, str) or not call_id.strip() or len(call_id.strip()) > 256:
            raise ValueError("dsh_call_id must be a bounded nonempty string")
        if "actor" in arguments and (not isinstance(arguments["actor"], str) or not arguments["actor"].strip() or len(arguments["actor"].strip()) > 200):
            raise ValueError("actor must be a bounded nonempty string")
    if tool_name == "cosmatter_execute_approved_local_corpus_search":
        index = arguments["query_index"]
        index_path = arguments["index_path"]
        if not isinstance(index, int) or isinstance(index, bool) or index < 0:
            raise ValueError("query_index must be a nonnegative integer")
        if not isinstance(index_path, str) or not index_path.strip() or len(index_path.strip()) > 2_000:
            raise ValueError("index_path must be a bounded nonempty string")
        if "counter" in arguments and not isinstance(arguments["counter"], bool):
            raise ValueError("counter must be a boolean")
    if tool_name == "cosmatter_draft_graph_plan":
        node_ids, intent = arguments["node_ids"], arguments["intent"]
        if not isinstance(node_ids, list) or not 1 <= len(node_ids) <= 25 or any(not isinstance(node_id, str) or not node_id.strip() for node_id in node_ids):
            raise ValueError("node_ids must be 1 to 25 nonempty strings")
        if len({node_id.strip() for node_id in node_ids}) != len(node_ids):
            raise ValueError("node_ids must be unique")
        if not isinstance(intent, str) or not intent.strip() or len(intent.strip()) > 500:
            raise ValueError("intent must be a bounded nonempty string")
    if tool_name == "cosmatter_approve_graph_plan":
        for field, maximum in (("plan_id", 200), ("reviewer", 200), ("rationale", 1_000)):
            value = arguments[field]
            if not isinstance(value, str) or not value.strip() or len(value.strip()) > maximum:
                raise ValueError(f"{field} must be a bounded nonempty string")
    if tool_name == "cosmatter_execute_approved_search":
        index = arguments["query_index"]
        if not isinstance(index, int) or isinstance(index, bool) or index < 0:
            raise ValueError("query_index must be a nonnegative integer")
        authorizations, call_id = arguments["authorizations"], arguments["dsh_call_id"]
        if not isinstance(authorizations, list) or set(authorizations) != {"mission_scoped_egress_consent", "metadata_provider_consent"}:
            raise ValueError("authorizations must contain the exact metadata-provider consent pair")
        if not isinstance(call_id, str) or not call_id.strip() or len(call_id.strip()) > 256:
            raise ValueError("dsh_call_id must be a bounded nonempty string")
        if "counter" in arguments and not isinstance(arguments["counter"], bool):
            raise ValueError("counter must be a boolean")
        if "sources" in arguments:
            sources = arguments["sources"]
            allowed_sources = {"sciverse", "openalex", "crossref"}
            if not isinstance(sources, list) or not sources or any(not isinstance(source, str) or source not in allowed_sources for source in sources):
                raise ValueError("sources must be a nonempty list of approved providers")


def _required_string(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a nonempty string")
    return value.strip()


def _result(request_id: object, result: object) -> dict[str, object]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error(request_id: object, code: int, message: str) -> dict[str, object]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}
