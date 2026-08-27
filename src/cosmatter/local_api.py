"""Loopback-only application service for the interactive CosMatter workbench.

Provider tokens are loaded only inside this backend.  Browser clients receive
allowlisted task data and never receive a token, provider request object, raw
retrieval payload, audit event payload, or arbitrary file path.
"""

from __future__ import annotations

import json
import re
from threading import Lock, Thread
from dataclasses import dataclass, field
from pathlib import Path
from urllib.request import Request, urlopen
from typing import Any, Callable

from .audit import AuditPathError, FlightRecorder, safe_run_id
from .config import AGENT_ROOT, Settings
from .deepseek import DeepSeekAdapter, DeepSeekConfigurationError, DeepSeekRequestError
from .dispatch import DispatchError, MissionDispatcher
from .metadata_search import MetadataSearchAdapter, MetadataSearchConfigurationError, MetadataSearchRequestError
from .models import MissionBrief, MissionState
from .corpus_preparation import CorpusPreparationError, load_corpus_manifest
from .local_corpus import LocalCorpusSearchError, candidates_from_local_source_index
from .planning import (
    PlanApprovalError,
    approved_flight_plan_from_payload,
    load_approved_flight_plan,
    research_planning_prompts,
    write_approved_flight_plan,
    write_untrusted_plan_draft,
)
from .retrieval import RetrievalArtifactError, candidates_from_sciverse, write_candidate_artifact
from .candidate_screening import CandidateScreeningError, candidate_screening_from_review, candidate_screening_template, load_candidate_screening, require_document_screened_for_fulltext, screening_matches_candidates, write_candidate_screening
from .provider_receipts import ProviderReceiptError, append_provider_receipt, sciverse_search_receipt
from .run_control import RunControlError, build_run_status, cancel_run, load_run_control, require_active_run
from .sciverse import SciverseAdapter, SciverseConfigurationError, SciverseRequestError
from .ui_export import UiExportError, _evidence_cards_from_payloads, _load_array_if_present, _load_object, _mission_from_payload, _verification_decisions_from_payloads, export_run_to_ui
from .mineru import MinerUAdapter, MinerUConfigurationError, MinerURequestError, MinerUTask
from .private_storage import PrivateStorageError, read_markdown, safe_document_id, write_markdown, write_pdf
from .openalex import OpenAlexAdapter, OpenAlexConfigurationError, OpenAlexRequestError, normalize_doi
from .crossref import CrossrefAdapter, CrossrefRequestError
from .citation_expansion import CitationExpansionError, build_citation_expansion, write_citation_expansion
from .run_package import RunPackageError, export_run_package, restore_run_package
from .source_map import SourceMapError, iter_source_maps, load_source_map_for_document, source_map_from_review, write_source_map_for_document
from .provenance_audit import ProvenanceAuditError, audit_accepted_evidence_provenance, write_evidence_provenance_audit
from .material_extraction import MaterialExtractionError, material_facts_from_review, write_material_facts_for_document
from .ingestion import EvidenceIngestionError, ingest_evidence_draft
from .source_parse import SourceParseArtifactError, record_source_parse_task, task_for_document, update_source_parse_task
from .pdf_task_registry import PdfTaskRegistryError, assert_pdf_task_slot, load_pdf_tasks, task_for_pdf_document, write_pdf_task
from .counterevidence import CounterevidenceGateError, require_executed_counterevidence
from .facilities import DiscrepancyMatrix, DiscrepancyRow, FacilityGateError, condition_differential, write_condition_matrix
from .gap_analysis import GapAnalysisError, candidates_from_discrepancies, write_gap_candidates
from .workflow_readiness import WorkflowReadinessError, continuation_next_stage


class LocalApiError(ValueError):
    """A safe API error that is appropriate to return to a local user."""

    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.status = status


def _runs_dir() -> Path:
    return AGENT_ROOT / "runs"


_RUN_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")


def _api_safe_run_id(value: str) -> str:
    candidate = safe_run_id(value)
    if not _RUN_ID_PATTERN.fullmatch(candidate):
        raise LocalApiError("run_id must use letters, numbers, underscores, or hyphens")
    return candidate


def _bounded_text(payload: dict[str, Any], field: str, maximum: int = 3_000) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > maximum:
        raise LocalApiError(f"{field} must be a nonempty string of at most {maximum} characters")
    return value.strip()


@dataclass
class LocalMissionApi:
    """Application operations shared by a local-only HTTP handler and tests."""

    runs_dir: Path
    settings_loader: Callable[[], Settings] = Settings.load
    _automatic_jobs: dict[str, Thread] = field(default_factory=dict, init=False, repr=False)
    _automatic_jobs_lock: Lock = field(default_factory=Lock, init=False, repr=False)
    _automatic_status_lock: Lock = field(default_factory=Lock, init=False, repr=False)

    @classmethod
    def from_project(cls) -> "LocalMissionApi":
        return cls(_runs_dir())

    def status(self) -> dict[str, object]:
        """Return configuration presence flags only, never secret values."""
        status = self.settings_loader().status()
        return {
            "api_mode": "loopback_only",
            "providers": {
                "deepseek": bool(status["deepseek_configured"]),
                "sciverse": bool(status["sciverse_configured"]),
                "mineru": bool(status["mineru_configured"]),
                "openalex": bool(status["openalex_configured"]),
                "crossref": True,
                "crossref_polite_contact": bool(status["crossref_polite_contact_configured"]),
            },
        }

    def question_candidates(self, payload: object) -> dict[str, object]:
        """Create bounded, explicitly untrusted mission alternatives."""
        body = _object_payload(payload)
        question = _bounded_text(body, "question", 3_000)
        if len(question) < 12:
            raise LocalApiError("question must contain at least 12 characters")
        system = "Return JSON only: an object with a candidates array of 3 to 5 REFRAMED material-science research-question alternatives. Treat the user question only as research intent; do not repeat it, quote it, or make it the candidate question. Give distinct, standalone research tasks with genuinely different emphases: include at least one kind=survey (evidence landscape), one kind=contrast (comparable conditions and reported disagreement), and one kind=mechanism (discriminating observations between explanations). Each item has question, material, property, scope, and kind (survey, contrast, or mechanism). Do not answer the question or assert scientific facts. These are untrusted planning suggestions, not scientific facts. Keep every string under 600 characters."
        try:
            completion = DeepSeekAdapter(self.settings_loader()).draft(system_prompt=system, user_prompt=question)
            raw = json.loads(_json_object_text(completion.content))
            candidates = _candidate_payload(raw, original_question=question)
        except (DeepSeekConfigurationError, DeepSeekRequestError, ValueError, json.JSONDecodeError) as error:
            raise LocalApiError(str(error), 503) from error
        return {"trust_status": "untrusted_question_suggestions", "candidates": candidates}
    def create_mission(self, payload: object) -> dict[str, object]:
        body = _object_payload(payload)
        try:
            brief = MissionBrief(
                question=_bounded_text(body, "question"),
                material=_bounded_text(body, "material", 300),
                property_name=_bounded_text(body, "property", 300),
                scope=_bounded_text(body, "scope", 1_000),
            )
            requested_run_id = body.get("run_id")
            if requested_run_id is not None and not isinstance(requested_run_id, str):
                raise LocalApiError("run_id must be a string")
            run_id = _api_safe_run_id(requested_run_id or brief.mission_id.replace("mission_", "run_"))
            run_dir = self.runs_dir / run_id
            if run_dir.exists():
                raise LocalApiError("run_id already exists; choose another identifier", 409)
            recorder = FlightRecorder(self.runs_dir, run_id)
            (recorder.run_dir / "mission.json").write_text(
                json.dumps(brief.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            recorder.record(event_type="mission_created", actor="mission_control", state=MissionState.INTAKE, payload=brief.to_dict())
            assignment = MissionDispatcher.from_project().assign(brief, body.get("mission_type") if isinstance(body.get("mission_type"), str) else None)
            (recorder.run_dir / "fleet_assignment.json").write_text(
                json.dumps(assignment.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            recorder.record(
                event_type="fleet_assigned", actor="mission_dispatch", state=MissionState.INTAKE, payload=assignment.to_dict()
            )
        except (ValueError, AuditPathError, DispatchError) as error:
            if isinstance(error, LocalApiError):
                raise
            raise LocalApiError(str(error)) from error
        return {
            "run_id": run_id,
            "mission_id": brief.mission_id,
            "fleet_type": assignment.fleet_type.value,
            "mission_type": assignment.mission_type,
            "state": MissionState.INTAKE.value,
        }

    def auto_mission(self, payload: object) -> dict[str, object]:
        """Register one bounded consented mission and run it cooperatively in background.

        The response returns a safe local run identifier immediately. Provider
        calls remain metadata-only and consult the durable cancellation marker
        before each external submission, so the browser can poll and cancel.
        """
        body = _object_payload(payload)
        if body.get("consent") is not True:
            raise LocalApiError("automatic execution requires explicit consent")
        sources = list(_selected_sources(body.get("sources")))
        created = self.create_mission(body)
        run_id = str(created["run_id"])
        run_dir, mission = self._active_mission(run_id)
        plan_payload = {
            "subquestions": [mission.question],
            "queries": [mission.question],
            "counter_queries": [f"counterevidence {mission.question}"],
            "max_rounds": 1,
            "max_papers": 20,
        }
        automatic_plan = {"schema_version": "1.0", "mission_id": mission.mission_id, "trust_status": "consent_authorized_metadata_plan_not_human_approved", **plan_payload, "sources": list(sources)}
        _write_json(run_dir / "automatic_execution_plan.json", automatic_plan)
        self._write_automatic_execution_status(run_dir, mission.mission_id, state="queued")
        recorder = FlightRecorder(self.runs_dir, run_id)
        recorder.record(event_type="automatic_execution_authorized", actor="user_consent", state=MissionState.PLAN, payload={"sources": sources, "trust_status": "one_time_user_consent"})
        recorder.record(event_type="automatic_plan_created", actor="research_planning", state=MissionState.PLAN, payload={"trust_status": "consent_authorized_metadata_plan_not_human_approved"})
        worker = Thread(target=self._run_automatic_mission, args=(run_id, mission, tuple(sources)), daemon=True, name=f"cosmatter-auto-{run_id}")
        with self._automatic_jobs_lock:
            self._automatic_jobs[run_id] = worker
        worker.start()
        return {**created, "trust_status": "metadata_only_automatic_run", "status": self.run_status(run_id), "candidate_count": 0, "failures": []}

    def _automatic_status_path(self, run_dir: Path) -> Path:
        return run_dir / "automatic_execution_status.json"

    def _write_automatic_execution_status(
        self,
        run_dir: Path,
        mission_id: str,
        *,
        state: str,
        candidate_count: int = 0,
        failure_count: int = 0,
        failed_sources: tuple[str, ...] = (),
        planning_warning: bool = False,
    ) -> None:
        if state not in {"queued", "running", "succeeded", "failed", "cancelled"}:
            raise ValueError("automatic execution state is invalid")
        normalized_sources = tuple(sorted({source.strip() for source in failed_sources if isinstance(source, str) and source.strip()}))
        if failure_count < len(normalized_sources):
            raise ValueError("automatic execution failure count is invalid")
        payload = {
            "schema_version": "1.1",
            "mission_id": mission_id,
            "state": state,
            "candidate_count": candidate_count,
            "failure_count": failure_count,
            "failed_sources": list(normalized_sources),
            "planning_warning": planning_warning,
            "trust_status": "metadata_only_automatic_run",
        }
        with self._automatic_status_lock:
            _write_json(self._automatic_status_path(run_dir), payload)

    def _automatic_execution_status(self, run_dir: Path, mission_id: str) -> dict[str, object] | None:
        path = self._automatic_status_path(run_dir)
        with self._automatic_status_lock:
            if not path.exists():
                return None
            try:
                payload = _load_object(path, "automatic execution status")
            except UiExportError as error:
                raise LocalApiError(str(error), 500) from error
        legacy_expected = {"schema_version", "mission_id", "state", "candidate_count", "failure_count", "planning_warning", "trust_status"}
        current_expected = {*legacy_expected, "failed_sources"}
        if (set(payload) != legacy_expected and set(payload) != current_expected) or payload.get("schema_version") not in {"1.0", "1.1"} or payload.get("mission_id") != mission_id:
            raise LocalApiError("automatic execution status is invalid", 500)
        if payload.get("state") not in {"queued", "running", "succeeded", "failed", "cancelled"}:
            raise LocalApiError("automatic execution status is invalid", 500)
        if not isinstance(payload.get("candidate_count"), int) or not isinstance(payload.get("failure_count"), int) or not isinstance(payload.get("planning_warning"), bool):
            raise LocalApiError("automatic execution status is invalid", 500)
        failed_sources = payload.get("failed_sources", [])
        if not isinstance(failed_sources, list) or not all(isinstance(source, str) and source.strip() for source in failed_sources):
            raise LocalApiError("automatic execution status is invalid", 500)
        if payload["failure_count"] < len(failed_sources):
            raise LocalApiError("automatic execution status is invalid", 500)
        return {key: payload[key] for key in ("state", "candidate_count", "failure_count", "planning_warning", "trust_status")} | {"failed_sources": failed_sources}

    def _run_automatic_mission(self, run_id: str, mission: MissionBrief, sources: tuple[str, ...]) -> None:
        run_dir = self.runs_dir / run_id
        recorder = FlightRecorder(self.runs_dir, run_id)
        candidate_count = 0
        failure_count = 0
        failed_sources: tuple[str, ...] = ()
        planning_warning = False
        try:
            require_active_run(run_dir, mission.mission_id)
            self._write_automatic_execution_status(run_dir, mission.mission_id, state="running")
            recorder.record(event_type="automatic_execution_started", actor="mission_control", state=MissionState.RETRIEVE, payload={"sources": list(sources), "trust_status": "metadata_only_automatic_run"})
            try:
                self.draft_plan(run_id)
            except LocalApiError:
                planning_warning = True
            require_active_run(run_dir, mission.mission_id)
            retrieval = self._execute_automatic_query(run_id, mission, mission.question, sources)
            candidate_count = int(retrieval["candidate_count"])
            failed_sources = tuple(str(source) for source in retrieval["failed_sources"])
            failure_count = len(failed_sources)
            if bool(retrieval["all_sources_failed"]):
                self._write_automatic_execution_status(
                    run_dir,
                    mission.mission_id,
                    state="failed",
                    candidate_count=candidate_count,
                    failure_count=failure_count,
                    failed_sources=failed_sources,
                    planning_warning=planning_warning,
                )
                recorder.record(
                    event_type="automatic_retrieval_failed",
                    actor="search_selection",
                    state=MissionState.FAILED,
                    payload={"sources": list(sources), "failed_sources": list(failed_sources), "safe_reason": "all selected providers failed"},
                )
                return
            self._write_automatic_execution_status(
                run_dir,
                mission.mission_id,
                state="succeeded",
                candidate_count=candidate_count,
                failure_count=failure_count,
                failed_sources=failed_sources,
                planning_warning=planning_warning,
            )
            recorder.record(
                event_type="automatic_execution_completed",
                actor="mission_control",
                state=MissionState.SELECT,
                payload={
                    "candidate_count": candidate_count,
                    "failed_sources": list(failed_sources),
                    "planning_warning": planning_warning,
                    "trust_status": "metadata_only_not_scientific_evidence",
                },
            )
        except RunControlError:
            self._write_automatic_execution_status(
                run_dir,
                mission.mission_id,
                state="cancelled",
                candidate_count=candidate_count,
                failure_count=failure_count,
                failed_sources=failed_sources,
                planning_warning=planning_warning,
            )
        except LocalApiError as error:
            failure_count = max(failure_count, 1)
            self._write_automatic_execution_status(
                run_dir,
                mission.mission_id,
                state="failed",
                candidate_count=candidate_count,
                failure_count=failure_count,
                failed_sources=failed_sources,
                planning_warning=planning_warning,
            )
            recorder.record(event_type="automatic_retrieval_failed", actor="search_selection", state=MissionState.FAILED, payload={"sources": list(sources), "failed_sources": list(failed_sources), "safe_reason": str(error)[:300]})
        finally:
            with self._automatic_jobs_lock:
                self._automatic_jobs.pop(run_id, None)

    def _execute_automatic_query(self, run_id: str, mission: MissionBrief, query: str, sources: tuple[str, ...]) -> dict[str, object]:
        """Run consent-authorized metadata retrieval with isolated source failures.

        A successful provider writes its metadata candidate contribution even if
        another selected provider is unavailable.  Only a run in which every
        provider fails is terminally failed; no result is ever upgraded to an
        EvidenceCard by this operation.
        """
        run_dir = self.runs_dir / run_id
        settings = self.settings_loader()
        recorder = FlightRecorder(self.runs_dir, run_id)
        candidates = []
        counts: dict[str, int] = {}
        failures: dict[str, str] = {}
        successful_sources: list[str] = []

        def collect(source: str, action: Callable[[], object]) -> None:
            require_active_run(run_dir, mission.mission_id)
            try:
                current = action()
                require_active_run(run_dir, mission.mission_id)
            except RunControlError:
                raise
            except Exception as error:  # Provider failures must not discard other selected sources.
                failures[source] = str(error)[:300]
                recorder.record(
                    event_type="automatic_metadata_source_failed",
                    actor="search_selection",
                    state=MissionState.RETRIEVE,
                    payload={"source": source, "safe_reason": failures[source], "trust_status": "metadata_only_not_scientific_evidence"},
                )
                return
            if not isinstance(current, tuple):
                raise LocalApiError(f"{source} returned an invalid candidate sequence")
            candidates.extend(current)
            counts[source] = len(current)
            successful_sources.append(source)
            recorder.record(
                event_type="automatic_metadata_source_completed",
                actor="search_selection",
                state=MissionState.RETRIEVE,
                payload={"source": source, "candidate_count": len(current), "trust_status": "metadata_only_not_scientific_evidence"},
            )

        if "sciverse" in sources:
            collect("Sciverse", lambda: candidates_from_sciverse(SciverseAdapter(settings).agentic_search(query, top_k=20).payload, query, 20))
        if "openalex" in sources:
            collect("OpenAlex", lambda: MetadataSearchAdapter(settings).search_openalex(query, top_k=20))
        if "crossref" in sources:
            collect("Crossref", lambda: MetadataSearchAdapter(settings).search_crossref(query, top_k=20))
        require_active_run(run_dir, mission.mission_id)
        failed_sources = tuple(sorted(failures))
        if not successful_sources:
            return {"candidate_count": 0, "source_counts": counts, "failed_sources": failed_sources, "all_sources_failed": True}
        write_candidate_artifact(run_dir, query, tuple(candidates))
        recorder.record(
            event_type="automatic_metadata_query_executed",
            actor="search_selection",
            state=MissionState.RETRIEVE,
            payload={
                "sources": list(sources),
                "successful_sources": successful_sources,
                "failed_sources": list(failed_sources),
                "candidate_count": len(candidates),
                "trust_status": "metadata_only_not_scientific_evidence",
            },
        )
        return {"candidate_count": len(candidates), "source_counts": counts, "failed_sources": failed_sources, "all_sources_failed": False}

    def draft_plan(self, run_id: str) -> dict[str, object]:
        run_dir, mission = self._active_mission(run_id)
        try:
            system_prompt, user_prompt = research_planning_prompts(mission)
            completion = DeepSeekAdapter(self.settings_loader()).draft(system_prompt=system_prompt, user_prompt=user_prompt)
            write_untrusted_plan_draft(run_dir, completion)
        except (DeepSeekConfigurationError, DeepSeekRequestError, ValueError) as error:
            raise LocalApiError(str(error), 503) from error
        FlightRecorder(self.runs_dir, run_id).record(
            event_type="research_plan_drafted",
            actor="research_planning",
            state=MissionState.PLAN,
            payload={"model": completion.model, "request_id": completion.request_id, "trust_status": "untrusted_draft"},
        )
        return {"run_id": run_id, "trust_status": "untrusted_draft", "content": completion.content}

    def approve_plan(self, run_id: str, payload: object) -> dict[str, object]:
        run_dir, mission = self._active_mission(run_id)
        try:
            plan = approved_flight_plan_from_payload(mission, _object_payload(payload))
            write_approved_flight_plan(run_dir, plan)
        except PlanApprovalError as error:
            raise LocalApiError(str(error)) from error
        FlightRecorder(self.runs_dir, run_id).record(
            event_type="flight_plan_approved",
            actor="human_plan_review",
            state=MissionState.PLAN,
            payload={"plan_id": plan.artifact_id, "query_count": len(plan.queries), "counter_query_count": len(plan.counter_queries)},
        )
        return {"run_id": run_id, "plan_id": plan.artifact_id, "queries": list(plan.queries), "counter_queries": list(plan.counter_queries)}

    def execute_plan_query(self, run_id: str, payload: object) -> dict[str, object]:
        """Run an approved query against explicitly selected metadata sources.

        External activity is possible only after plan approval and this endpoint
        is invoked. Every provider result is metadata-only candidate data, not
        evidence or full text.
        """
        run_dir, mission = self._active_mission(run_id)
        body = _object_payload(payload)
        try:
            plan = load_approved_flight_plan(run_dir, mission.mission_id)
            index = body.get("query_index")
            counter = body.get("counter", False)
            sources = _selected_sources(body.get("sources"))
            if not isinstance(index, int) or isinstance(index, bool):
                raise LocalApiError("query_index must be an integer")
            if not isinstance(counter, bool):
                raise LocalApiError("counter must be a boolean")
            approved_queries = plan.counter_queries if counter else plan.queries
            if not 0 <= index < len(approved_queries):
                raise LocalApiError("query_index is outside the approved query list")
            query = approved_queries[index]
            settings = self.settings_loader()
            source_counts: dict[str, int] = {}
            provider_receipt_ids: list[str] = []
            source_provenance: dict[str, dict[str, str]] = {}
            candidates = []
            if "sciverse" in sources:
                response = SciverseAdapter(settings).agentic_search(query, top_k=plan.max_papers)
                current = candidates_from_sciverse(response.payload, query, plan.max_papers)
                source_counts["Sciverse"] = len(current)
                candidates.extend(current)
                receipt = sciverse_search_receipt(query=query, top_k=plan.max_papers, status_code=response.status_code, request_id=response.request_id, candidate_count=len(current))
                append_provider_receipt(run_dir, receipt)
                provider_receipt_ids.append(receipt["receipt_id"])
                source_provenance["Sciverse"] = {"provider": "sciverse", "operation": "agentic_search", "receipt_id": receipt["receipt_id"], "query_sha256": receipt["query_sha256"]}
            metadata = MetadataSearchAdapter(settings)
            if "openalex" in sources:
                current = metadata.search_openalex(query, top_k=min(plan.max_papers, 20))
                source_counts["OpenAlex"] = len(current)
                candidates.extend(current)
            if "crossref" in sources:
                current = metadata.search_crossref(query, top_k=min(plan.max_papers, 20))
                source_counts["Crossref"] = len(current)
                candidates.extend(current)
            write_candidate_artifact(run_dir, query, tuple(candidates), source_provenance=source_provenance or None)
        except (PlanApprovalError, ProviderReceiptError, RetrievalArtifactError, SciverseConfigurationError, SciverseRequestError, MetadataSearchConfigurationError, MetadataSearchRequestError, ValueError) as error:
            if isinstance(error, LocalApiError):
                raise
            raise LocalApiError(str(error), 503) from error
        FlightRecorder(self.runs_dir, run_id).record(
            event_type="approved_plan_query_executed",
            actor="search_selection",
            state=MissionState.RETRIEVE,
            payload={"plan_id": plan.artifact_id, "query_kind": "counter" if counter else "primary", "query_index": index, "sources": list(sources), "candidate_count": len(candidates), "source_counts": source_counts, "provider_receipt_ids": provider_receipt_ids},
        )
        return {"run_id": run_id, "query_kind": "counter" if counter else "primary", "query_index": index, "sources": list(sources), "source_counts": source_counts, "candidate_count": len(candidates), "candidates": [candidate.to_dict() for candidate in candidates]}
    def execute_plan_local_corpus_query(self, run_id: str, payload: object) -> dict[str, object]:
        """Search an approved query against an explicit private local corpus index.

        The index and parsed text are read only in this local process. They are
        never returned by MCP, included in audit events, or written to run
        artifacts; only regular metadata candidates are persisted.
        """
        run_dir, mission = self._active_mission(run_id)
        body = _object_payload(payload)
        try:
            index = body.get("query_index")
            counter = body.get("counter", False)
            index_path = body.get("index_path")
            if not isinstance(index, int) or isinstance(index, bool):
                raise LocalApiError("query_index must be an integer")
            if not isinstance(counter, bool):
                raise LocalApiError("counter must be a boolean")
            if not isinstance(index_path, str) or not index_path.strip() or len(index_path.strip()) > 2_000:
                raise LocalApiError("index_path must be a bounded nonempty string")
            plan = load_approved_flight_plan(run_dir, mission.mission_id)
            approved_queries = plan.counter_queries if counter else plan.queries
            if not 0 <= index < len(approved_queries):
                raise LocalApiError("query_index is outside the approved query list")
            manifest = load_corpus_manifest(run_dir / "corpus_manifest.json", mission.mission_id)
            if manifest is None:
                raise CorpusPreparationError("approved local corpus query requires a recorded corpus manifest")
            query = approved_queries[index]
            candidates = candidates_from_local_source_index(
                manifest=manifest,
                index_path=Path(index_path),
                query=query,
                top_k=plan.max_papers,
            )
            write_candidate_artifact(run_dir, query, candidates)
        except (PlanApprovalError, CorpusPreparationError, LocalCorpusSearchError, RetrievalArtifactError, ValueError) as error:
            if isinstance(error, LocalApiError):
                raise
            raise LocalApiError(str(error)) from error
        FlightRecorder(self.runs_dir, run_id).record(
            event_type="approved_plan_local_corpus_query_executed",
            actor="local_corpus_retriever",
            state=MissionState.RETRIEVE,
            payload={
                "plan_id": plan.artifact_id,
                "query_kind": "counter" if counter else "primary",
                "query_index": index,
                "candidate_count": len(candidates),
                "source": "authorized_local_parsed_corpus",
            },
        )
        return {
            "run_id": run_id,
            "query_kind": "counter" if counter else "primary",
            "query_index": index,
            "source": "authorized_local_parsed_corpus",
            "candidate_count": len(candidates),
            "candidates": [candidate.to_dict() for candidate in candidates],
        }

    def candidate_screening_template(self, run_id: str) -> dict[str, object]:
        """Return a bounded, metadata-only human screening template.

        This endpoint never authorizes parsing. It exposes only the same
        bibliographic metadata already allowlisted for the literature graph;
        the final decisions must be submitted as one complete review.
        """
        run_dir, mission = self._active_mission(run_id)
        try:
            candidate_payload = _load_object(run_dir / "retrieval_candidates.json", "retrieval candidate artifact")
            existing = load_candidate_screening(run_dir / "candidate_screening.json", mission.mission_id)
            template = existing if existing is not None and screening_matches_candidates(existing, candidate_payload) else candidate_screening_template(mission.mission_id, candidate_payload)
            candidates = _screening_candidate_projection(candidate_payload)
        except (CandidateScreeningError, UiExportError, ValueError) as error:
            raise LocalApiError(str(error), 404) from error
        return {
            "run_id": _api_safe_run_id(run_id),
            "trust_status": template["trust_status"],
            "candidate_count": len(candidates),
            "candidates": candidates,
            "decisions": template["decisions"],
        }

    def record_candidate_screening(self, run_id: str, payload: object) -> dict[str, object]:
        """Persist a complete human screening review before full-text work."""
        run_dir, mission = self._active_mission(run_id)
        try:
            candidate_payload = _load_object(run_dir / "retrieval_candidates.json", "retrieval candidate artifact")
            artifact = candidate_screening_from_review(mission.mission_id, candidate_payload, _object_payload(payload))
            write_candidate_screening(run_dir, artifact)
        except (CandidateScreeningError, UiExportError, ValueError) as error:
            raise LocalApiError(str(error)) from error
        counts: dict[str, int] = {}
        for decision in artifact["decisions"]:
            value = str(decision["decision"])
            counts[value] = counts.get(value, 0) + 1
        FlightRecorder(self.runs_dir, _api_safe_run_id(run_id)).record(
            event_type="candidate_screening_reviewed",
            actor="human_candidate_review",
            state=MissionState.SELECT,
            payload={"candidate_count": artifact["candidate_count"], "decision_counts": counts, "trust_status": artifact["trust_status"]},
        )
        return {
            "run_id": _api_safe_run_id(run_id),
            "candidate_count": artifact["candidate_count"],
            "decision_counts": counts,
            "trust_status": artifact["trust_status"],
        }
    def create_pdf_run(self, payload: object, file_name: str, content: bytes) -> dict[str, object]:
        """Create a consented private MinerU task; never expose file paths or URLs."""
        body = _object_payload(payload)
        if body.get("consent") is not True:
            raise LocalApiError("PDF submission requires explicit MinerU consent")
        if not isinstance(file_name, str) or not file_name.lower().endswith(".pdf") or len(file_name) > 240:
            raise LocalApiError("upload must contain one bounded PDF filename")
        if not content.startswith(b"%PDF-") or not 0 < len(content) <= 200 * 1024 * 1024:
            raise LocalApiError("upload must contain one PDF of at most 200 MB")
        requested_run_id = body.get("run_id")
        candidate_document_id = body.get("candidate_document_id")
        if (requested_run_id is None) != (candidate_document_id is None):
            raise LocalApiError("candidate PDF intake requires both run_id and candidate_document_id")
        if requested_run_id is not None:
            if not isinstance(requested_run_id, str) or not isinstance(candidate_document_id, str):
                raise LocalApiError("candidate PDF intake identifiers must be strings")
            run_id = _api_safe_run_id(requested_run_id)
            run_dir, mission = self._active_mission(run_id)
            try:
                candidates = _load_object(run_dir / "retrieval_candidates.json", "retrieval candidate artifact")
                require_document_screened_for_fulltext(run_dir, mission.mission_id, candidates, candidate_document_id)
            except (CandidateScreeningError, UiExportError, ValueError) as error:
                raise LocalApiError(str(error)) from error
            created = {"run_id": run_id, "mission_id": mission.mission_id, "fleet_type": "fulltext_intake", "mission_type": "candidate_pdf"}
        else:
            created = self.create_mission(body)
            run_id = str(created["run_id"])
            run_dir, mission = self._active_mission(run_id)
        try:
            assert_pdf_task_slot(run_dir, mission.mission_id, candidate_document_id if isinstance(candidate_document_id, str) else None)
            document_id = safe_document_id(run_id, file_name, content)
            _, pdf_sha256 = write_pdf(document_id, content)
            batch = MinerUAdapter(self.settings_loader()).submit_local_file(file_name, content)
        except (PrivateStorageError, MinerUConfigurationError, MinerURequestError, ValueError) as error:
            raise LocalApiError(str(error), 503) from error
        artifact = {"schema_version": "1.0", "mission_id": mission.mission_id, "document_id": document_id, "candidate_document_id": candidate_document_id, "file_name": file_name, "pdf_sha256": pdf_sha256, "byte_count": len(content), "consent": True, "batch_id": batch.batch_id, "state": batch.state, "markdown_sha256": None, "doi": None, "doi_status": "pending"}
        try:
            record_source_parse_task(
                run_dir,
                mission_id=mission.mission_id,
                document_id=_pdf_audit_document_id(artifact),
                source_url=f"private-upload:{document_id}",
                task=_mineru_task_from_pdf_batch(batch.batch_id, batch.state),
                model_version=self.settings_loader().mineru_model_version,
            )
        except SourceParseArtifactError as error:
            raise LocalApiError(f"cannot record private PDF audit task: {error}", 500) from error
        _write_pdf_intake(run_dir, mission.mission_id, artifact)
        FlightRecorder(self.runs_dir, run_id).record(event_type="private_pdf_submitted", actor="user_consent", state=MissionState.EXTRACT, payload={"document_id": document_id, "candidate_screening_linked": candidate_document_id is not None, "byte_count": len(content), "trust_status": "private_pdf_outside_run"})
        return {**created, "document_id": document_id, "candidate_document_id": candidate_document_id, "state": batch.state, "doi_status": "pending"}

    def pdf_status(self, run_id: str, document_id: str | None = None) -> dict[str, object]:
        run_dir, mission = self._active_mission(run_id)
        artifact = _pdf_intake(run_dir, mission.mission_id, document_id)
        if artifact["state"] in {"done", "failed"}:
            try:
                record_source_parse_task(
                    run_dir,
                    mission_id=mission.mission_id,
                    document_id=_pdf_audit_document_id(artifact),
                    source_url=f"private-upload:{artifact['document_id']}",
                    task=_mineru_task_from_pdf_batch(str(artifact["batch_id"]), str(artifact["state"])),
                    model_version=self.settings_loader().mineru_model_version,
                )
            except SourceParseArtifactError as error:
                raise LocalApiError(f"cannot reconcile private PDF audit task: {error}", 500) from error
            return _pdf_public_status(artifact, _source_map_review_status(run_dir, mission.mission_id, artifact))
        try:
            result = MinerUAdapter(self.settings_loader()).get_batch(str(artifact["batch_id"]))
            artifact["state"] = result.state
            if result.state == "done":
                if not result.markdown_url:
                    raise MinerURequestError("MinerU completed without private Markdown")
                request = Request(result.markdown_url, method="GET")
                with urlopen(request, timeout=self.settings_loader().http_timeout_seconds) as response:
                    markdown = response.read(80 * 1024 * 1024 + 1)
                if len(markdown) > 80 * 1024 * 1024:
                    raise MinerURequestError("MinerU Markdown exceeds the private size limit")
                _, digest = write_markdown(str(artifact["document_id"]), markdown)
                artifact["markdown_sha256"] = digest
                doi = _doi_from_markdown(markdown.decode("utf-8"))
                artifact["doi"] = doi
                artifact["doi_status"] = "resolved" if doi else "needs_human_doi"
            elif result.state == "failed":
                artifact["error"] = (result.error or "MinerU extraction failed")[:300]
        except (MinerUConfigurationError, MinerURequestError, PrivateStorageError, OSError, UnicodeDecodeError) as error:
            artifact["state"] = "failed"
            artifact["error"] = str(error)[:300]
        try:
            update_source_parse_task(
                run_dir,
                mission_id=mission.mission_id,
                document_id=_pdf_audit_document_id(artifact),
                task=_mineru_task_from_pdf_batch(str(artifact["batch_id"]), str(artifact["state"])),
            )
        except SourceParseArtifactError as error:
            raise LocalApiError(f"cannot update private PDF audit task: {error}", 500) from error
        _write_pdf_intake(run_dir, mission.mission_id, artifact)
        return _pdf_public_status(artifact, _source_map_review_status(run_dir, mission.mission_id, artifact))

    def pdf_tasks(self, run_id: str) -> dict[str, object]:
        """Return public status projections for every private document task."""
        run_dir, mission = self._active_mission(run_id)
        try:
            document_ids = [str(item["document_id"]) for item in load_pdf_tasks(run_dir, mission.mission_id)]
        except PdfTaskRegistryError as error:
            raise LocalApiError(str(error), 404) from error
        return {"run_id": run_id, "tasks": [self.pdf_status(run_id, document_id) for document_id in document_ids], "trust_status": "private_pdf_task_registry_metadata_only"}
    def private_markdown(self, run_id: str, document_id: str) -> bytes:
        run_dir, mission = self._active_mission(run_id)
        artifact = _pdf_intake(run_dir, mission.mission_id, document_id)
        if artifact.get("document_id") != document_id or artifact.get("state") != "done" or not artifact.get("markdown_sha256"):
            raise LocalApiError("private Markdown is not ready", 404)
        try:
            return read_markdown(document_id)
        except PrivateStorageError as error:
            raise LocalApiError(str(error), 404) from error

    def pdf_source_map_context(self, run_id: str, document_id: str | None = None) -> dict[str, object]:
        """Return only review metadata needed to resume local source-map work."""
        run_dir, mission = self._active_mission(run_id)
        intake = _pdf_intake(run_dir, mission.mission_id, document_id)
        audit_document_id = _pdf_audit_document_id(intake)
        source_map = load_source_map_for_document(run_dir, mission.mission_id, audit_document_id)
        if source_map is None:
            return {
                "run_id": run_id,
                "document_id": audit_document_id,
                "segment_count": 0,
                "segments": [],
                "trust_status": "no_human_reviewed_source_map",
            }
        return {
            "run_id": run_id,
            "document_id": audit_document_id,
            "segment_count": len(source_map["segments"]),
            "segments": [
                {"segment_id": item["segment_id"], "locator": item["locator"], "kind": item["kind"]}
                for item in source_map["segments"]
            ],
            "trust_status": "human_reviewed_parser_selection_not_evidence_card",
        }
    def record_pdf_source_map(self, run_id: str, payload: object) -> dict[str, object]:
        """Keep only human-confirmed bounded excerpts from private Markdown."""
        body = _object_payload(payload)
        if body.get("human_confirmed") is not True:
            raise LocalApiError("Source Map recording requires explicit human confirmation")
        run_dir, mission = self._active_mission(run_id)
        intake = _pdf_intake(run_dir, mission.mission_id, _pdf_document_id_from_payload(body))
        if intake.get("state") != "done" or not intake.get("markdown_sha256"):
            raise LocalApiError("Source Map recording requires completed private PDF parsing")
        candidate_document_id = intake.get("candidate_document_id")
        audit_document_id = _pdf_audit_document_id(intake)
        if isinstance(candidate_document_id, str) and candidate_document_id.strip():
            try:
                candidates = _load_object(run_dir / "retrieval_candidates.json", "retrieval candidate artifact")
                require_document_screened_for_fulltext(run_dir, mission.mission_id, candidates, candidate_document_id)
            except (CandidateScreeningError, UiExportError, ValueError) as error:
                raise LocalApiError(str(error)) from error
        try:
            try:
                task = task_for_document(run_dir, mission_id=mission.mission_id, document_id=audit_document_id)
            except SourceParseArtifactError as error:
                if "does not exist" not in str(error) and "has no recorded" not in str(error):
                    raise
                record_source_parse_task(
                    run_dir,
                    mission_id=mission.mission_id,
                    document_id=audit_document_id,
                    source_url=f"private-upload:{intake['document_id']}",
                    task=_mineru_task_from_pdf_batch(str(intake["batch_id"]), str(intake["state"])),
                    model_version=self.settings_loader().mineru_model_version,
                )
                task = task_for_document(run_dir, mission_id=mission.mission_id, document_id=audit_document_id)
            if task["state"] != "done":
                update_source_parse_task(
                    run_dir,
                    mission_id=mission.mission_id,
                    document_id=audit_document_id,
                    task=_mineru_task_from_pdf_batch(str(intake["batch_id"]), str(intake["state"])),
                )
                task = task_for_document(run_dir, mission_id=mission.mission_id, document_id=audit_document_id)
            selection = _source_map_selection_from_private_markdown(body, intake, audit_document_id)
            source_map = source_map_from_review(
                mission_id=mission.mission_id,
                document_id=audit_document_id,
                source_task=task,
                selection=selection,
            )
            source_map["schema_version"] = "1.1"
            source_map["source_markdown_sha256"] = intake["markdown_sha256"]
            write_source_map_for_document(run_dir, source_map)
        except (PrivateStorageError, SourceParseArtifactError, SourceMapError, UnicodeDecodeError, ValueError) as error:
            raise LocalApiError(str(error)) from error
        FlightRecorder(self.runs_dir, run_id).record(
            event_type="source_map_reviewed",
            actor="human_source_reviewer",
            state=MissionState.EXTRACT,
            payload={
                "document_id": audit_document_id,
                "segment_count": len(source_map["segments"]),
                "access_mode": "screened_candidate" if candidate_document_id else "human_authorized_private_pdf",
                "trust_status": "human_reviewed_parser_selection_not_evidence_card",
            },
        )
        return {"run_id": run_id, "document_id": audit_document_id, "segment_count": len(source_map["segments"]), "segments": [{"segment_id": item["segment_id"], "locator": item["locator"], "kind": item["kind"]} for item in source_map["segments"]], "trust_status": "human_reviewed_parser_selection_not_evidence_card"}
    def record_pdf_material_facts(self, run_id: str, payload: object) -> dict[str, object]:
        """Persist human-reviewed structured facts tied to an existing Source Map."""
        body = _object_payload(payload)
        if body.get("human_confirmed") is not True:
            raise LocalApiError("material fact recording requires explicit human confirmation")
        run_dir, mission = self._active_mission(run_id)
        try:
            require_active_run(run_dir, mission.mission_id)
            intake = _pdf_intake(run_dir, mission.mission_id, _pdf_document_id_from_payload(body))
            document_id = _pdf_audit_document_id(intake)
            source_map = load_source_map_for_document(run_dir, mission.mission_id, document_id)
            if source_map is None:
                raise MaterialExtractionError("material fact recording requires a reviewed Source Map")
            artifact = material_facts_from_review(
                mission_id=mission.mission_id,
                source_map=source_map,
                selection={"document_id": document_id, "facts": body.get("facts")},
            )
            write_material_facts_for_document(run_dir, artifact)
        except (RunControlError, SourceMapError, MaterialExtractionError, ValueError) as error:
            raise LocalApiError(str(error)) from error
        FlightRecorder(self.runs_dir, run_id).record(
            event_type="material_facts_reviewed",
            actor="human_material_reviewer",
            state=MissionState.EXTRACT,
            payload={"document_id": document_id, "fact_count": len(artifact["facts"]), "trust_status": artifact["trust_status"]},
        )
        return {"run_id": run_id, "document_id": document_id, "fact_count": len(artifact["facts"]), "trust_status": artifact["trust_status"]}
    def record_pdf_evidence_card(self, run_id: str, payload: object) -> dict[str, object]:
        """Accept one human-reviewed EvidenceCard from an existing Source Map segment.

        The browser may submit only the claim, stance, structured conditions, a
        confidence value, and a segment identifier.  Quote text and locator are
        resolved locally from the reviewed Source Map, so the UI cannot invent
        or alter the source binding.
        """
        body = _object_payload(payload)
        required = {"human_confirmed", "segment_id", "claim", "stance", "conditions", "reviewer_confidence"}
        if body.get("human_confirmed") is not True:
            raise LocalApiError("evidence acceptance requires explicit human confirmation")
        if set(body) not in (required, required | {"document_id"}):
            raise LocalApiError("evidence review has unsupported or missing fields")
        segment_id = body.get("segment_id")
        claim = body.get("claim")
        stance = body.get("stance")
        conditions = body.get("conditions")
        confidence = body.get("reviewer_confidence")
        if not isinstance(segment_id, str) or not segment_id.strip() or len(segment_id) > 160:
            raise LocalApiError("evidence review segment identifier is invalid")
        if not isinstance(claim, str) or not claim.strip() or len(claim) > 1800:
            raise LocalApiError("evidence review claim is invalid")
        if stance not in {"support", "contradict", "context"}:
            raise LocalApiError("evidence review stance is invalid")
        if not isinstance(conditions, dict) or len(conditions) > 24:
            raise LocalApiError("evidence review conditions are invalid")
        required_conditions = ("sample_form", "strain_percent", "substrate", "thickness_nm", "temperature_k", "method")
        missing_conditions = [key for key in required_conditions if conditions.get(key) in (None, "", "unknown")]
        if missing_conditions:
            raise LocalApiError("evidence acceptance requires explicit conditions: " + ", ".join(missing_conditions))
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= float(confidence) <= 1:
            raise LocalApiError("reviewer confidence must be between 0 and 1")
        run_dir, mission = self._active_mission(run_id)
        intake = _pdf_intake(run_dir, mission.mission_id, _pdf_document_id_from_payload(body))
        candidate_document_id = intake.get("candidate_document_id")
        if not isinstance(candidate_document_id, str) or not candidate_document_id.strip():
            raise LocalApiError("evidence acceptance requires a PDF attached to a human-screened candidate")
        document_id = _pdf_audit_document_id(intake)
        if document_id != candidate_document_id:
            raise LocalApiError("evidence acceptance requires the candidate-linked audit document")
        try:
            source_map = load_source_map_for_document(run_dir, mission.mission_id, document_id)
            if source_map is None:
                raise EvidenceIngestionError("evidence acceptance requires a reviewed Source Map")
            segment = next((item for item in source_map["segments"] if item["segment_id"] == segment_id), None)
            if segment is None:
                raise EvidenceIngestionError("evidence acceptance segment is not in the reviewed Source Map")
            evidence_id = f"human_evidence_{run_id}_{len(segment_id)}_{len(claim.strip())}"
            suffix = 1
            while (run_dir / "evidence_cards.json").exists() and f'"evidence_id": "{evidence_id}"' in (run_dir / "evidence_cards.json").read_text(encoding="utf-8"):
                suffix += 1
                evidence_id = f"human_evidence_{run_id}_{len(segment_id)}_{len(claim.strip())}_{suffix}"
            draft = {
                "claim": claim.strip(),
                "stance": stance,
                "material": mission.material,
                "property_name": mission.property_name,
                "conditions": conditions,
                "quote": segment["quote"],
                "provenance": {
                    "document_id": document_id,
                    "locator": segment["locator"],
                    "source": "human-reviewed MinerU source map",
                    "doi": intake.get("doi") if intake.get("doi_status") in {"resolved", "human_confirmed"} else None,
                    "content_hash": intake.get("markdown_sha256"),
                    "access_policy": "authorized",
                },
                "extractor_confidence": float(confidence),
                "evidence_id": evidence_id,
            }
            decision = ingest_evidence_draft(run_dir, draft)
            cards = _evidence_cards_from_payloads(_load_array_if_present(run_dir / "evidence_cards.json", "evidence artifacts"))
            decisions = _verification_decisions_from_payloads(_load_array_if_present(run_dir / "verification_decisions.json", "verification decisions"))
            provenance_audit = audit_accepted_evidence_provenance(
                mission=mission,
                cards=cards,
                decisions=decisions,
                source_maps=iter_source_maps(run_dir, mission.mission_id),
            )
            write_evidence_provenance_audit(run_dir, provenance_audit)
        except (EvidenceIngestionError, SourceMapError, ProvenanceAuditError, ValueError, OSError) as error:
            raise LocalApiError(str(error)) from error
        FlightRecorder(self.runs_dir, run_id).record(
            event_type="human_evidence_card_accepted",
            actor="human_evidence_reviewer",
            state=MissionState.VERIFY,
            payload={
                "evidence_id": evidence_id,
                "document_id": document_id,
                "segment_id": segment_id,
                "decision": decision.status.value,
                "trust_status": "human_reviewed_accepted_evidence_card",
            },
        )
        return {
            "run_id": run_id,
            "evidence_id": evidence_id,
            "document_id": document_id,
            "locator": segment["locator"],
            "review_status": decision.status.value,
            "trust_status": "human_reviewed_accepted_evidence_card",
        }
    def confirm_pdf_doi(self, run_id: str, payload: object) -> dict[str, object]:
        """Record a human-confirmed DOI for bibliography navigation only."""
        body = _object_payload(payload)
        if body.get("human_confirmed") is not True:
            raise LocalApiError("manual DOI entry requires explicit human confirmation")
        raw_doi = _bounded_text(body, "doi", 320)
        run_dir, mission = self._active_mission(run_id)
        intake = _pdf_intake(run_dir, mission.mission_id, _pdf_document_id_from_payload(body))
        if intake.get("state") != "done" or not intake.get("markdown_sha256"):
            raise LocalApiError("manual DOI entry requires completed private PDF parsing")
        try:
            doi = normalize_doi(raw_doi)
        except ValueError as error:
            raise LocalApiError("manual DOI must be a normalized DOI") from error
        intake["doi"] = doi
        intake["doi_status"] = "human_confirmed"
        intake.pop("error", None)
        _write_pdf_intake(run_dir, mission.mission_id, intake)
        FlightRecorder(self.runs_dir, run_id).record(
            event_type="pdf_doi_human_confirmed",
            actor="human_bibliography_review",
            state=MissionState.EXTRACT,
            payload={"document_id": intake["document_id"], "trust_status": "human_confirmed_bibliographic_identifier_not_scientific_evidence"},
        )
        return _pdf_public_status(intake, _source_map_review_status(run_dir, mission.mission_id, intake))

    def expand_pdf_citations(self, run_id: str, document_id: str | None = None) -> dict[str, object]:
        run_dir, mission = self._active_mission(run_id)
        intake = _pdf_intake(run_dir, mission.mission_id, document_id)
        doi = intake.get("doi")
        if intake.get("doi_status") not in {"resolved", "human_confirmed"} or not isinstance(doi, str):
            raise LocalApiError("citation expansion requires a normalized DOI")
        settings = self.settings_loader()
        crossref = CrossrefAdapter(settings)
        openalex = OpenAlexAdapter(settings)
        def relations(current: str) -> dict[str, tuple[str, ...]]:
            references: tuple[str, ...] = ()
            cited_by: tuple[str, ...] = ()
            try:
                references = crossref.work_references_by_doi(current).referenced_dois
            except CrossrefRequestError:
                pass
            try:
                cited_by = openalex.citing_dois_by_doi(current, limit=25)
            except (OpenAlexRequestError, OpenAlexConfigurationError):
                pass
            return {"references": references, "cited_by": cited_by}
        try:
            expansion = build_citation_expansion(mission.mission_id, doi, relations)
            write_citation_expansion(run_dir, expansion)
        except (CitationExpansionError, ValueError) as error:
            raise LocalApiError(str(error), 503) from error
        FlightRecorder(self.runs_dir, run_id).record(event_type="citation_graph_expanded", actor="bibliography_navigation", state=MissionState.RETRIEVE, payload={"node_count": len(expansion["nodes"]), "edge_count": len(expansion["edges"]), "trust_status": "public_bibliographic_metadata_not_scientific_evidence"})
        return {"run_id": run_id, "node_count": len(expansion["nodes"]), "edge_count": len(expansion["edges"]), "failure_count": len(expansion["failures"]), "trust_status": expansion["trust_status"]}

    def diagnose_conditions(self, run_id: str) -> dict[str, object]:
        """Build a deterministic comparison matrix from accepted reviewed evidence only."""
        run_dir, mission = self._active_mission(run_id)
        try:
            plan = load_approved_flight_plan(run_dir, mission.mission_id)
            history = _load_object(run_dir / "retrieval_candidates.json", "retrieval candidate history")
            counterevidence = require_executed_counterevidence(plan, history)
            cards = _evidence_cards_from_payloads(_load_array_if_present(run_dir / "evidence_cards.json", "evidence artifacts"))
            decisions = _verification_decisions_from_payloads(_load_array_if_present(run_dir / "verification_decisions.json", "verification decisions"))
            provenance_audit = audit_accepted_evidence_provenance(
                mission=mission,
                cards=cards,
                decisions=decisions,
                source_maps=iter_source_maps(run_dir, mission.mission_id),
            )
            write_evidence_provenance_audit(run_dir, provenance_audit)
            accepted_ids = {decision.evidence_id for decision in decisions if decision.mission_id == mission.mission_id and decision.status.value == "accepted"}
            accepted_cards = tuple(card for card in cards if card.evidence_id in accepted_ids)
            distinct_documents = {card.provenance.document_id for card in accepted_cards}
            if len(distinct_documents) < 2:
                raise FacilityGateError(
                    "diagnostics requires accepted evidence from at least two distinct source documents"
                )
            matrix = condition_differential(accepted_cards, plan.counter_queries)
            write_condition_matrix(run_dir, matrix)
        except (UiExportError, PlanApprovalError, CounterevidenceGateError, FacilityGateError, ProvenanceAuditError, SourceMapError, ValueError) as error:
            raise LocalApiError(str(error)) from error
        FlightRecorder(self.runs_dir, run_id).record(event_type="condition_diagnostics_completed", actor="condition_differential", state=MissionState.MAP, payload={"matrix_row_count": len(matrix.rows), "differing_field_count": sum(len(row.differing_fields) for row in matrix.rows), "planned_counter_query_count": counterevidence.planned_query_count, "executed_counter_query_count": counterevidence.executed_query_count})
        return {"run_id": run_id, "matrix_row_count": len(matrix.rows), "trust_status": "deterministic_condition_comparison_not_scientific_conclusion"}

    def generate_gap_candidates(self, run_id: str) -> dict[str, object]:
        """Create review-required candidates from an executed counterevidence boundary and condition matrix."""
        run_dir, mission = self._active_mission(run_id)
        try:
            plan = load_approved_flight_plan(run_dir, mission.mission_id)
            history = _load_object(run_dir / "retrieval_candidates.json", "retrieval candidate history")
            counterevidence = require_executed_counterevidence(plan, history)
            cards = _evidence_cards_from_payloads(_load_array_if_present(run_dir / "evidence_cards.json", "evidence artifacts"))
            decisions = _verification_decisions_from_payloads(_load_array_if_present(run_dir / "verification_decisions.json", "verification decisions"))
            provenance_audit = audit_accepted_evidence_provenance(
                mission=mission,
                cards=cards,
                decisions=decisions,
                source_maps=iter_source_maps(run_dir, mission.mission_id),
            )
            write_evidence_provenance_audit(run_dir, provenance_audit)
            payload = _load_array_if_present(run_dir / "condition_matrix.json", "condition matrix")
            rows = tuple(DiscrepancyRow(str(row["condition_cluster"]), tuple(str(item) for item in row["supporting_evidence_ids"]), tuple(str(item) for item in row["contradicting_evidence_ids"]), tuple(str(item) for item in row["differing_fields"]), tuple(str(item) for item in row["unknowns"])) for row in payload)
            candidates = candidates_from_discrepancies(mission.mission_id, mission.material, mission.property_name, cards, decisions, DiscrepancyMatrix(rows, plan.counter_queries), counterevidence)
            write_gap_candidates(run_dir, candidates)
        except (UiExportError, PlanApprovalError, CounterevidenceGateError, GapAnalysisError, ProvenanceAuditError, SourceMapError, KeyError, TypeError, ValueError) as error:
            raise LocalApiError(str(error)) from error
        FlightRecorder(self.runs_dir, run_id).record(event_type="research_gap_candidates_generated", actor="gap_analysis", state=MissionState.HAZARD_SCAN, payload={"candidate_count": len(candidates), "evidence_bound": True, "planned_counter_query_count": counterevidence.planned_query_count, "executed_counter_query_count": counterevidence.executed_query_count})
        return {"run_id": run_id, "candidate_count": len(candidates), "trust_status": "evidence_bound_candidate_requires_human_review"}
    def export_run_package(self, run_id: str) -> bytes:
        run_dir, _ = self._active_mission(run_id)
        try:
            return (json.dumps(export_run_package(run_dir), ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
        except RunPackageError as error:
            raise LocalApiError(str(error)) from error

    def import_run_package(self, payload: object) -> dict[str, object]:
        body = _object_payload(payload)
        package = body.get("package")
        requested = body.get("run_id")
        if requested is not None and not isinstance(requested, str):
            raise LocalApiError("run_id must be a string")
        try:
            mission = package.get("mission") if isinstance(package, dict) else None
            base = requested or ("resume_" + str(mission.get("mission_id", "run"))[-12:] if isinstance(mission, dict) else "resume_run")
            run_id = _api_safe_run_id(base)
            destination = restore_run_package(self.runs_dir, run_id, package)
        except (RunPackageError, AuditPathError) as error:
            raise LocalApiError(str(error)) from error
        restored = _mission_from_payload(_load_object(destination / "mission.json", "mission artifact"))
        next_stage = "plan"
        readiness_path = destination / "workflow_readiness.json"
        if readiness_path.is_file():
            try:
                next_stage = continuation_next_stage(
                    _load_object(readiness_path, "workflow readiness artifact"),
                    restored.mission_id,
                )
            except WorkflowReadinessError as error:
                raise LocalApiError(str(error)) from error
        FlightRecorder(self.runs_dir, run_id).record(event_type="run_package_imported", actor="mission_control", state=MissionState.INTAKE, payload={"trust_status": "allowlisted_continuation_package"})
        return {"run_id": run_id, "mission_id": restored.mission_id, "next_stage": next_stage, "trust_status": "allowlisted_continuation_package"}
    def run_status(self, run_id: str) -> dict[str, object]:
        run_dir, mission = self._active_mission(run_id, require_active=False)
        state = MissionState.INTAKE
        events_path = run_dir / "events.jsonl"
        if events_path.is_file():
            for line in events_path.read_text(encoding="utf-8").splitlines():
                try:
                    event = json.loads(line)
                    value = event.get("state") if isinstance(event, dict) else None
                    if isinstance(value, str) and value in MissionState._value2member_map_:
                        state = MissionState(value)
                except json.JSONDecodeError:
                    continue
        summary = build_run_status(_api_safe_run_id(run_id), mission.mission_id, state, load_run_control(run_dir / "run_control.json", mission.mission_id))
        automatic = self._automatic_execution_status(run_dir, mission.mission_id)
        if automatic is not None:
            summary["automatic_execution"] = automatic
        return summary

    def cancel(self, run_id: str) -> dict[str, object]:
        run_dir, mission = self._active_mission(run_id)
        cancel_run(run_dir, mission.mission_id)
        FlightRecorder(self.runs_dir, run_id).record(event_type="mission_cancelled", actor="mission_control", state=MissionState.CANCELLED, payload={"trust_status": "local_control"})
        return self.run_status(run_id)
    def ui_bundle(self, run_id: str) -> bytes:
        try:
            destination = export_run_to_ui(self.runs_dir, _api_safe_run_id(run_id))
            return destination.read_bytes()
        except (AuditPathError, UiExportError, OSError) as error:
            raise LocalApiError(str(error), 404) from error

    def _active_mission(self, run_id: str, *, require_active: bool = True) -> tuple[Path, MissionBrief]:
        try:
            run_id = _api_safe_run_id(run_id)
            run_dir = self.runs_dir / run_id
            mission = _mission_from_payload(_load_object(run_dir / "mission.json", "mission artifact"))
            if require_active:
                require_active_run(run_dir, mission.mission_id)
            return run_dir, mission
        except (AuditPathError, UiExportError, RunControlError) as error:
            raise LocalApiError(str(error), 404) from error


def _screening_candidate_projection(payload: object) -> list[dict[str, object]]:
    """Allowlist bibliographic candidate metadata for a human review checklist."""
    if not isinstance(payload, dict) or not isinstance(payload.get("candidates"), list):
        raise CandidateScreeningError("candidate screening requires a retrieval candidates artifact")
    projected: list[dict[str, object]] = []
    seen: set[str] = set()
    for candidate in payload["candidates"]:
        if not isinstance(candidate, dict):
            raise CandidateScreeningError("candidate screening metadata is invalid")
        document_id = candidate.get("document_id")
        title = candidate.get("title")
        source = candidate.get("source")
        year = candidate.get("publication_year")
        if (
            not isinstance(document_id, str) or not document_id or document_id in seen
            or not isinstance(title, str) or not title.strip()
            or not isinstance(source, str) or not source.strip()
            or year is not None and (not isinstance(year, int) or not 1600 <= year <= 3000)
        ):
            raise CandidateScreeningError("candidate screening metadata is invalid")
        projected.append({"document_id": document_id, "title": title.strip()[:500], "source": source.strip()[:120], "publication_year": year})
        seen.add(document_id)
    if not projected or len(projected) > 250:
        raise CandidateScreeningError("candidate screening requires 1 to 250 candidates")
    return projected

def _selected_sources(value: object) -> tuple[str, ...]:
    allowed = {"sciverse", "openalex", "crossref"}
    if value is None:
        return ("sciverse",)
    if not isinstance(value, list) or not value or len(value) > len(allowed):
        raise LocalApiError("sources must be a nonempty list of approved providers")
    selected: list[str] = []
    for item in value:
        if not isinstance(item, str) or item not in allowed or item in selected:
            raise LocalApiError("sources contains an unsupported provider")
        selected.append(item)
    return tuple(selected)

def _object_payload(payload: object) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise LocalApiError("request body must be a JSON object")
    return payload


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _pdf_document_id_from_payload(payload: dict[str, Any]) -> str | None:
    value = payload.get("document_id")
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > 120:
        raise LocalApiError("private PDF document_id is invalid")
    return value.strip()

def _pdf_intake(run_dir: Path, mission_id: str, document_id: str | None = None) -> dict[str, object]:
    try:
        return task_for_pdf_document(run_dir, mission_id, document_id)
    except PdfTaskRegistryError as error:
        raise LocalApiError(str(error), 404) from error


def _write_pdf_intake(run_dir: Path, mission_id: str, artifact: dict[str, object]) -> None:
    """Persist one task into the registry and retain a legacy latest-task mirror."""
    try:
        write_pdf_task(run_dir, mission_id, artifact)
    except PdfTaskRegistryError as error:
        raise LocalApiError(str(error)) from error
    # Older local clients/tests read one task only. The mirror is never used by
    # new registry-aware code and contains metadata/hashes only.
    _write_json(run_dir / "pdf_intake.json", artifact)


def _source_map_review_status(run_dir: Path, mission_id: str, artifact: dict[str, object]) -> dict[str, object]:
    """Expose only document-scoped Source Map review metadata, never excerpts."""
    try:
        source_map = load_source_map_for_document(run_dir, mission_id, _pdf_audit_document_id(artifact))
    except SourceMapError:
        return {"source_map_review_status": "invalid", "source_map_segment_count": 0}
    if source_map is None:
        return {"source_map_review_status": "absent", "source_map_segment_count": 0}
    return {
        "source_map_review_status": "recorded",
        "source_map_segment_count": len(source_map["segments"]),
    }


def _pdf_public_status(artifact: dict[str, object], source_map_review: dict[str, object] | None = None) -> dict[str, object]:
    audit_document_id = _pdf_audit_document_id(artifact)
    review = source_map_review or {"source_map_review_status": "absent", "source_map_segment_count": 0}
    return {"document_id": artifact["document_id"], "candidate_document_id": artifact.get("candidate_document_id"), "audit_document_id": audit_document_id, "audit_state": _audit_state_from_pdf_state(str(artifact["state"])), "file_name": artifact["file_name"], "state": artifact["state"], "doi": artifact["doi"], "doi_status": artifact["doi_status"], "markdown_ready": bool(artifact.get("markdown_sha256")), "source_map_review_status": review["source_map_review_status"], "source_map_segment_count": review["source_map_segment_count"], "error": artifact.get("error"), "trust_status": "private_markdown_outside_run_not_scientific_evidence"}


def _pdf_audit_document_id(artifact: dict[str, object]) -> str:
    """Keep a screened metadata record as evidence-facing provenance when present."""
    candidate_document_id = artifact.get("candidate_document_id")
    if isinstance(candidate_document_id, str) and candidate_document_id.strip():
        return candidate_document_id.strip()
    document_id = artifact.get("document_id")
    if not isinstance(document_id, str) or not document_id.strip():
        raise LocalApiError("PDF intake document identity is invalid", 500)
    return document_id


def _audit_state_from_pdf_state(state: str) -> str:
    return {"waiting-file": "pending", "uploading": "pending", "pending": "pending", "converting": "running", "running": "running", "done": "done", "failed": "failed"}.get(state, "pending")


def _mineru_task_from_pdf_batch(batch_id: str, state: str) -> MinerUTask:
    return MinerUTask(task_id=batch_id, state=_audit_state_from_pdf_state(state), request_id=None)



_PRIVATE_MARKDOWN_LOCATOR = re.compile(r"markdown_line:(\d+)-(\d+)(?::part:\d+)?$")


def _source_map_selection_from_private_markdown(body: dict[str, Any], intake: dict[str, object], document_id: str) -> dict[str, object]:
    raw_segments = body.get("segments")
    if not isinstance(raw_segments, list) or not 1 <= len(raw_segments) <= 12:
        raise LocalApiError("Source Map must contain 1 to 12 reviewed excerpts")
    content = read_markdown(str(intake["document_id"])).decode("utf-8")
    lines = content.splitlines()
    segments: list[dict[str, str]] = []
    for index, raw in enumerate(raw_segments, 1):
        if not isinstance(raw, dict) or set(raw) != {"locator", "kind", "quote"}:
            raise LocalApiError("each Source Map excerpt must contain locator, kind, and quote")
        locator, kind, quote = raw.get("locator"), raw.get("kind"), raw.get("quote")
        if not all(isinstance(value, str) and value.strip() for value in (locator, kind, quote)):
            raise LocalApiError("Source Map excerpt values must be nonempty")
        locator = locator.strip(); kind = kind.strip(); quote = quote.strip()
        if kind not in {"paragraph", "table", "formula", "figure_caption"} or len(locator) > 240 or len(quote) > 500:
            raise LocalApiError("Source Map excerpt locator, kind, or quote is invalid")
        match = _PRIVATE_MARKDOWN_LOCATOR.fullmatch(locator)
        if match is None:
            raise LocalApiError("private Markdown locators must use markdown_line:start-end")
        start, end = int(match.group(1)), int(match.group(2))
        if start < 1 or end < start or end > len(lines):
            raise LocalApiError("Source Map locator is outside the private Markdown")
        if quote not in "\n".join(lines[start - 1 : end]):
            raise LocalApiError("Source Map quote does not match its private Markdown line range")
        segments.append({"segment_id": f"private_md_{index:03d}", "locator": locator, "kind": kind, "quote": quote})
    return {"document_id": document_id, "segments": segments}

_DOI_PATTERN = re.compile(r"(?:https?://(?:dx\.)?doi\.org/|doi\s*:\s*)?(10\.\d{4,9}/[-._;()/:a-z0-9]+)", re.IGNORECASE)


def _doi_from_markdown(markdown: str) -> str | None:
    match = _DOI_PATTERN.search(markdown[:200_000])
    if not match:
        return None
    try:
        return normalize_doi(match.group(1).rstrip(".,;"))
    except ValueError:
        return None

def _json_object_text(value: str) -> str:
    value = value.strip()
    if value.startswith("```"):
        value = value.split("\n", 1)[1] if "\n" in value else ""
        if value.rstrip().endswith("```"):
            value = value.rstrip()[:-3]
    start, end = value.find("{"), value.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("DeepSeek did not return a JSON object")
    return value[start : end + 1]


def _candidate_payload(payload: object, *, original_question: str | None = None) -> list[dict[str, str]]:
    items = payload.get("candidates") if isinstance(payload, dict) else None
    if not isinstance(items, list) or not 3 <= len(items) <= 5:
        raise ValueError("DeepSeek candidates must contain 3 to 5 items")
    result: list[dict[str, str]] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError("DeepSeek candidate must be an object")
        candidate: dict[str, str] = {"id": f"candidate_{index + 1}"}
        for field in ("question", "material", "property", "scope", "kind"):
            value = item.get(field)
            if not isinstance(value, str) or not value.strip() or len(value.strip()) > 600:
                raise ValueError(f"DeepSeek candidate {field} is invalid")
            candidate[field] = value.strip()
        if candidate["kind"] not in {"survey", "contrast", "mechanism"}:
            raise ValueError("DeepSeek candidate kind is invalid")
        result.append(candidate)
    normalized_questions = {_normalized_candidate_question(item["question"]) for item in result}
    if len(normalized_questions) != len(result):
        raise ValueError("DeepSeek candidates must contain distinct reframed questions")
    if original_question is not None and _normalized_candidate_question(original_question) in normalized_questions:
        raise ValueError("DeepSeek candidate must reframe rather than repeat the original question")
    if not {"survey", "contrast", "mechanism"}.issubset({item["kind"] for item in result}):
        raise ValueError("DeepSeek candidates must cover survey, contrast, and mechanism focuses")
    return result


def _normalized_candidate_question(value: str) -> str:
    return "".join(character.casefold() for character in value if character.isalnum())
