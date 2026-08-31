"""Run one public synthetic DSH-style replay without provider credentials.

The fixture is deliberately a narrow, review-gated workflow rather than a
model transcript: it exercises actual local persistence, authorization,
idempotency, screening, accepted-evidence graph projection and the restricted
artifact contract while faking only the network adapter.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cosmatter.config import Settings
from cosmatter.local_api import LocalMissionApi
from cosmatter.models import AccessPolicy, EvidenceCard, Provenance, ReviewStatus, Stance
from cosmatter.sciverse import SciverseResponse
from cosmatter.verification import VerificationDecision


class ReplayFixtureError(ValueError):
    pass


class _SyntheticSciverse:
    def __init__(self, _settings: Settings) -> None:
        pass

    def agentic_search(self, _query: str, *, top_k: int) -> SciverseResponse:
        return SciverseResponse(
            payload={"hits": [{"doc_id": "synthetic-doc", "title": "Synthetic metadata candidate", "is_content_accessible": True, "score": 0.9}]},
            status_code=200,
            request_id="synthetic-request",
        )


def run_fixture(session_path: Path, expected_path: Path) -> dict[str, object]:
    steps = _load_session(session_path)
    expected = _load_expected(expected_path)
    with tempfile.TemporaryDirectory(prefix="cosmatter_dsh_replay_") as directory:
        root = Path(directory)
        api = LocalMissionApi(root / "runs", settings_loader=lambda: Settings.load({"SCIVERSE_API_TOKEN": "fixture-token"}))
        run_id, mission_id = _execute(api, steps)
        run_dir = root / "runs" / run_id
        observed = _observed(run_dir, api, run_id, mission_id)
        _assert_expected(observed, expected["expected"])
    return {
        "schema_version": "1.0",
        "fixture_id": expected["fixture_id"],
        "trust_status": "synthetic_replay_verification_not_scientific_evidence_or_provider_execution",
        "passed": True,
        "checks": {
            "candidate_count": observed["candidate_count"],
            "screening_decision_count": observed["screening_decision_count"],
            "accepted_evidence_count": observed["accepted_evidence_count"],
            "artifact_count": len(observed["artifact_ids"]),
            "dispatch_state_count": len(observed["dispatch_states"]),
        },
    }


def _execute(api: LocalMissionApi, steps: list[dict[str, object]]) -> tuple[str, str]:
    run_id: str | None = None
    mission_id: str | None = None
    for step in steps:
        kind = step["kind"]
        if kind == "mission_create":
            created = api.create_mission({"run_id": step["run_id"], "question": step["question"], "material": step["material"], "property": step["property"], "scope": step["scope"]})
            run_id, mission_id = str(created["run_id"]), str(created["mission_id"])
        elif kind == "plan_approve":
            _require_run(run_id, mission_id)
            api.approve_plan(run_id, {key: step[key] for key in ("subquestions", "queries", "counter_queries")})
        elif kind == "authorized_metadata_query":
            _require_run(run_id, mission_id)
            with patch("cosmatter.local_api.SciverseAdapter", _SyntheticSciverse):
                api.execute_authorized_plan_query(run_id, {key: step[key] for key in ("authorizations", "query_index", "sources", "dsh_call_id")})
        elif kind == "candidate_screening":
            _require_run(run_id, mission_id)
            api.record_candidate_screening(run_id, {"decisions": step["decisions"]})
        elif kind == "accepted_evidence_fixture":
            _require_run(run_id, mission_id)
            _write_synthetic_accepted_evidence(api.runs_dir / run_id, mission_id, step)
        elif kind == "graph_project":
            _require_run(run_id, mission_id)
            api.project_accepted_evidence_graph(run_id)
        elif kind == "artifact_manifest":
            _require_run(run_id, mission_id)
            run_dir = api.runs_dir / run_id
            # The export is deliberately minimal but is still validated by the fixed contract.
            (run_dir / "ui.json").write_text(json.dumps({"schema_version": "1.0", "mission_id": mission_id, "mission": {"mission_id": mission_id}}), encoding="utf-8")
            api.approved_artifacts(run_id)
        else:  # pragma: no cover - fixture schema catches this first
            raise ReplayFixtureError("unsupported synthetic replay step")
    _require_run(run_id, mission_id)
    return run_id, mission_id


def _write_synthetic_accepted_evidence(run_dir: Path, mission_id: str, step: dict[str, object]) -> None:
    evidence_id, document_id = step["evidence_id"], step["document_id"]
    if not isinstance(evidence_id, str) or not isinstance(document_id, str):
        raise ReplayFixtureError("synthetic evidence fixture is invalid")
    card = EvidenceCard(
        "Synthetic reviewed condition observation", Stance.SUPPORT, "BiFeO3", "phase stability",
        {"sample_form": "film", "strain_percent": 1.0}, "Synthetic bounded quote.",
        Provenance(document_id, "synthetic:1", "synthetic_fixture", access_policy=AccessPolicy.AUTHORIZED), evidence_id=evidence_id,
    )
    decision = VerificationDecision(mission_id, evidence_id, ReviewStatus.ACCEPTED, "synthetic human review")
    (run_dir / "evidence_cards.json").write_text(json.dumps([card.to_dict()]), encoding="utf-8")
    (run_dir / "verification_decisions.json").write_text(json.dumps([decision.to_dict()]), encoding="utf-8")


def _observed(run_dir: Path, api: LocalMissionApi, run_id: str, mission_id: str) -> dict[str, object]:
    candidates = json.loads((run_dir / "retrieval_candidates.json").read_text(encoding="utf-8"))
    screening = json.loads((run_dir / "candidate_screening.json").read_text(encoding="utf-8"))
    decisions = json.loads((run_dir / "verification_decisions.json").read_text(encoding="utf-8"))
    ledger = json.loads((run_dir / "external_dispatch_ledger.json").read_text(encoding="utf-8"))
    graph = json.loads((run_dir / "graph_snapshot.json").read_text(encoding="utf-8"))
    manifest = api.approved_artifacts(run_id)
    serialised = json.dumps({"candidates": candidates, "screening": screening, "decisions": decisions, "ledger": ledger, "graph": graph, "manifest": manifest})
    return {
        "candidate_count": len(candidates["candidates"]),
        "candidate_document_ids": sorted(item["document_id"] for item in candidates["candidates"]),
        "dispatch_states": [item["state"] for item in ledger["entries"]],
        "screening_decision_count": len(screening["decisions"]),
        "accepted_evidence_count": sum(item.get("status") == "accepted" and item.get("mission_id") == mission_id for item in decisions),
        "graph_node_type_count": len({item["node_type"] for item in graph["nodes"]}),
        "artifact_ids": sorted(item["artifact_id"] for item in manifest["artifacts"]),
        "serialised": serialised,
    }


def _assert_expected(observed: dict[str, object], expected: dict[str, object]) -> None:
    for key in ("candidate_count", "candidate_document_ids", "dispatch_states", "screening_decision_count", "accepted_evidence_count", "graph_node_type_count", "artifact_ids"):
        if observed[key] != expected[key]:
            raise ReplayFixtureError(f"synthetic replay expectation failed: {key}")
    serialised = str(observed["serialised"])
    for forbidden in expected["forbidden_substrings"]:
        if forbidden in serialised:
            raise ReplayFixtureError("synthetic replay leaked forbidden fixture material")


def _load_session(path: Path) -> list[dict[str, object]]:
    try:
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except (OSError, json.JSONDecodeError) as error:
        raise ReplayFixtureError("synthetic replay session is invalid") from error
    expected_kinds = ["mission_create", "plan_approve", "authorized_metadata_query", "candidate_screening", "accepted_evidence_fixture", "graph_project", "artifact_manifest"]
    if [item.get("kind") if isinstance(item, dict) else None for item in rows] != expected_kinds or any(not isinstance(item, dict) or item.get("schema_version") != "1.0" for item in rows):
        raise ReplayFixtureError("synthetic replay session steps are invalid")
    return rows


def _load_expected(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ReplayFixtureError("synthetic replay expectations are invalid") from error
    if not isinstance(payload, dict) or set(payload) != {"schema_version", "fixture_id", "trust_status", "expected"} or payload.get("schema_version") != "1.0" or payload.get("trust_status") != "synthetic_replay_expectations_not_scientific_evidence" or not isinstance(payload.get("fixture_id"), str) or not isinstance(payload.get("expected"), dict):
        raise ReplayFixtureError("synthetic replay expectations are invalid")
    expected = payload["expected"]
    required = {"candidate_count", "candidate_document_ids", "dispatch_states", "screening_decision_count", "accepted_evidence_count", "graph_node_type_count", "artifact_ids", "forbidden_substrings"}
    if set(expected) != required or not all(isinstance(item, str) and item for item in expected["forbidden_substrings"]):
        raise ReplayFixtureError("synthetic replay expectations are invalid")
    return payload


def _require_run(run_id: str | None, mission_id: str | None) -> None:
    if not run_id or not mission_id:
        raise ReplayFixtureError("synthetic replay must create a mission first")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="verify a keyless synthetic CosMatter DSH replay fixture")
    parser.add_argument("--session", type=Path, default=ROOT / "fixtures" / "dsh_replay" / "synthetic_review_gated_workflow.session.jsonl")
    parser.add_argument("--expected", type=Path, default=ROOT / "fixtures" / "dsh_replay" / "synthetic_review_gated_workflow.workspace.expected.json")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(run_fixture(args.session, args.expected), ensure_ascii=False, sort_keys=True))
    except ReplayFixtureError as error:
        print(json.dumps({"passed": False, "error": str(error)}, ensure_ascii=False))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
