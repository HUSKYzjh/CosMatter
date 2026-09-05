"""Loopback-only application service for the interactive CosMatter workbench.

Provider tokens are loaded only inside this backend.  Browser clients receive
allowlisted task data and never receive a token, provider request object, raw
retrieval payload, audit event payload, or arbitrary file path.
"""

from __future__ import annotations

import json
import hashlib
import math
import re
from threading import Lock, Thread
from dataclasses import dataclass, field
from pathlib import Path
from urllib.request import Request, urlopen
from typing import Any, Callable

from .audit import AuditPathError, FlightRecorder, safe_run_id
from .config import AGENT_ROOT, Settings, data_root
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
from .provider_receipts import ProviderReceiptError, append_provider_receipt, mineru_task_receipt, sciverse_search_receipt
from .run_control import RunControlError, build_run_status, cancel_run, load_run_control, require_active_run
from .sciverse import SciverseAdapter, SciverseConfigurationError, SciverseRequestError
from .ui_export import UiExportError, _evidence_cards_from_payloads, _load_array_if_present, _load_object, _mission_from_payload, _verification_decisions_from_payloads, export_run_to_ui
from .mineru import MinerUAdapter, MinerUConfigurationError, MinerURequestError, MinerUTask
from .private_storage import PrivateStorageError, read_markdown, safe_document_id, write_markdown, write_pdf
from .openalex import OpenAlexAdapter, OpenAlexConfigurationError, OpenAlexRequestError, normalize_doi
from .crossref import CrossrefAdapter, CrossrefRequestError
from .citation_expansion import CitationExpansionError, build_citation_expansion, validate_citation_expansion, write_citation_expansion
from .run_package import RunPackageError, export_run_package, restore_run_package
from .source_map import SourceMapError, iter_source_maps, load_source_map_for_document, source_map_from_review, write_source_map_for_document
from .provenance_audit import ProvenanceAuditError, audit_accepted_evidence_provenance, write_evidence_provenance_audit
from .material_extraction import MaterialExtractionError, material_facts_from_review, write_material_facts_for_document
from .ingestion import EvidenceIngestionError, ingest_evidence_draft, require_eligible_candidate
from .source_parse import SourceParseArtifactError, private_task_id_for_document, record_source_parse_task, task_for_document, update_source_parse_task
from .pdf_task_registry import PdfTaskRegistryError, assert_pdf_task_slot, load_pdf_tasks, task_for_pdf_document, write_pdf_task
from .counterevidence import CounterevidenceGateError, require_executed_counterevidence
from .facilities import DiscrepancyMatrix, DiscrepancyRow, FacilityGateError, condition_differential, write_condition_matrix
from .facility_contracts import facility_contracts
from .gap_analysis import GapAnalysisError, candidates_from_discrepancies, write_gap_candidates
from .workflow_readiness import WorkflowReadinessError, continuation_next_stage, workflow_readiness
from .graph_builder import build_accepted_evidence_graph
from .graph_projection import bounded_graph_projection, external_graph_projection
from .graph_validation import GraphContractError, validate_graph_payload
from .harness_receipts import PluginExecutionReceipt
from .graph_plan import GraphPlanDraft
from .graph_model_plan import GraphModelPlanError, graph_plan_assist_prompts, normalized_graph_model_plan_draft
from .graph_review import GraphReviewRequest
from .graph_plan_review import GraphPlanApproval
from .harness_catalog import CosMatterHarnessCatalogue
from .harness_policy import MissionAuthorization, evaluate_mission_authorization
from .external_dispatch import (
    ExternalDispatchError,
    begin_external_dispatch,
    complete_external_dispatch,
    mark_external_dispatch_unknown,
)
from .accepted_evidence_search import AcceptedEvidenceSearchError, search_accepted_evidence
from .runtime_invariants import RuntimeInvariantError, audit_runtime_invariants
from .artifact_contract import ArtifactContractError, ArtifactDownload, approved_artifact_download, artifact_manifest
from .stage_contract import StageContractError, stage_contract
from .operational_telemetry import OperationalTelemetryError, operational_telemetry
from .workflow_dag import WorkflowDagError, workflow_dag_projection
from .reminder_board import ReminderBoardError, project_reminder_board


class LocalApiError(ValueError):
    """A safe API error that is appropriate to return to a local user."""

    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.status = status


def _runs_dir() -> Path:
    return data_root() / "runs"


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

    def plugin_catalogue(self) -> dict[str, object]:
        """Expose static, non-executable capability contracts to local adapters."""
        catalogue = CosMatterHarnessCatalogue()
        return {
            "catalogue_api_version": "2.0",
            "plugins": catalogue.manifests(),
            "trust_status": "static_catalogue_not_plugin_execution_or_evidence_acceptance",
        }

    def facility_contract_catalogue(self) -> dict[str, object]:
        """Expose static facility schemas and safety boundaries only.

        This is catalogue data, not an invocation handle: it contains no task
        content, provider route, command, retry request, or credential.
        """
        return {
            "schema_version": "cosmatter.facility-contract-catalogue/v1",
            "trust_status": "static_facility_contracts_not_execution_or_evidence_acceptance",
            "contracts": [contract.manifest() for contract in facility_contracts()],
        }

    def plan_plugin_authorization(self, run_id: str, payload: object) -> dict[str, object]:
        """Evaluate a prospective adapter dispatch without persisting a grant or dispatching it."""
        _, mission = self._active_mission(run_id)
        body = _object_payload(payload)
        plugin_id, raw_authorizations, actor = body.get("plugin_id"), body.get("authorizations"), body.get("actor", "human_researcher")
        if not isinstance(plugin_id, str) or not plugin_id.strip() or len(plugin_id.strip()) > 120 or not isinstance(raw_authorizations, list) or len(raw_authorizations) > 12 or not all(isinstance(item, str) and item.strip() and len(item.strip()) <= 120 for item in raw_authorizations) or not isinstance(actor, str) or not actor.strip() or len(actor.strip()) > 200:
            raise LocalApiError("plugin authorization plan is invalid")
        try:
            decision = evaluate_mission_authorization(
                CosMatterHarnessCatalogue(),
                MissionAuthorization(mission.mission_id, plugin_id.strip(), tuple(item.strip() for item in raw_authorizations), actor.strip()),
            )
        except ValueError as error:
            raise LocalApiError(str(error)) from error
        FlightRecorder(self.runs_dir, run_id).record(
            event_type="plugin_authorization_planned", actor="harness_policy_plan", state=MissionState.PLAN,
            payload={"plugin_id": decision["plugin_id"], "permitted": decision["permitted"], "reason": decision["reason"], "missing_authorizations": decision["missing_authorizations"], "trust_status": "nonexecuting_authorization_plan_not_consent_or_execution"},
        )
        return {**decision, "trust_status": "nonexecuting_authorization_plan_not_consent_or_execution"}

    def question_candidates(self, payload: object) -> dict[str, object]:
        """Create bounded, explicitly untrusted mission alternatives."""
        body = _object_payload(payload)
        if body.get("candidate_generation_authorized") is not True:
            raise LocalApiError("question-candidate generation requires explicit consent")
        question = _bounded_text(body, "question", 3_000)
        if len(question) < 12:
            raise LocalApiError("question must contain at least 12 characters")
        system = "Return JSON only: an object with a candidates array of 3 to 5 REFRAMED material-science research-question alternatives. Write every candidate in the same natural language as the user's question. Treat the user question only as research intent; do not repeat it, quote it, or make it the candidate question. The visible question field of EVERY candidate must itself name each explicitly stated material or chemical formula and the target property or phenomenon from the user's question; placing those anchors only in material, property, or scope is invalid. Change the evidence angle, not the subject. Give distinct, standalone, directly searchable research tasks with genuinely different emphases: include at least one kind=survey that names concrete reported values, ranges, methods, sample states, or primary signals; one kind=contrast that names concrete conditions to align; and one kind=mechanism that names observations or controls able to distinguish explanations. Each visible question must contain route-specific variables or observables, not merely words such as literature, evidence, conditions, reports, or competing explanations. Each item has question, material, property, scope, and kind (survey, contrast, or mechanism). Never use generic references such as 'this topic', 'the research question', or 'relevant evidence' in place of the named material and property. Do not answer the question or assert scientific facts. These are untrusted planning suggestions, not scientific facts. Keep every string under 600 characters."
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
            # A provider may have returned just as a user cancels the run.  Do
            # not publish a success/failure terminal status after that point;
            # the durable control marker is authoritative for all later work.
            require_active_run(run_dir, mission.mission_id)
            candidate_count = int(retrieval["candidate_count"])
            failed_sources = tuple(str(source) for source in retrieval["failed_sources"])
            failure_count = len(failed_sources)
            if bool(retrieval["all_sources_failed"]):
                recorder.record(
                    event_type="automatic_retrieval_failed",
                    actor="search_selection",
                    state=MissionState.FAILED,
                    payload={"sources": list(sources), "failed_sources": list(failed_sources), "safe_reason": "all selected providers failed"},
                )
                self._write_automatic_execution_status(
                    run_dir,
                    mission.mission_id,
                    state="failed",
                    candidate_count=candidate_count,
                    failure_count=failure_count,
                    failed_sources=failed_sources,
                    planning_warning=planning_warning,
                )
                return
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
            self._write_automatic_execution_status(
                run_dir,
                mission.mission_id,
                state="succeeded",
                candidate_count=candidate_count,
                failure_count=failure_count,
                failed_sources=failed_sources,
                planning_warning=planning_warning,
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
            recorder.record(event_type="automatic_retrieval_failed", actor="search_selection", state=MissionState.FAILED, payload={"sources": list(sources), "failed_sources": list(failed_sources), "safe_reason": str(error)[:300]})
            self._write_automatic_execution_status(
                run_dir,
                mission.mission_id,
                state="failed",
                candidate_count=candidate_count,
                failure_count=failure_count,
                failed_sources=failed_sources,
                planning_warning=planning_warning,
            )
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

    def draft_authorized_plan(self, run_id: str, payload: object) -> dict[str, object]:
        """Dispatch one DeepSeek planning draft only after a durable explicit receipt."""
        body = self._record_explicit_external_authorization(run_id, payload, "literature.plan_draft")
        run_dir, mission = self._active_mission(run_id)
        call_id = _dsh_call_id(body)
        try:
            _require_runtime_invariant_safety(run_dir, mission.mission_id)
            dispatch = begin_external_dispatch(
                run_dir, mission_id=mission.mission_id, dsh_call_id=call_id,
                plugin_id="literature.plan_draft", operation="deepseek_plan_draft",
                request_shape={"run_id": run_id, "operation": "deepseek_plan_draft"},
            )
            if dispatch["duplicate"]:
                return _completed_draft_result(run_dir, run_id)
            result = self.draft_plan(run_id)
            complete_external_dispatch(run_dir, mission_id=mission.mission_id, dsh_call_id=call_id)
            return result
        except (DeepSeekConfigurationError, DeepSeekRequestError, ExternalDispatchError, LocalApiError, OSError, ValueError) as error:
            if not isinstance(error, ExternalDispatchError) or "already" not in str(error):
                try:
                    mark_external_dispatch_unknown(run_dir, mission_id=mission.mission_id, dsh_call_id=call_id)
                except ExternalDispatchError:
                    pass
            if isinstance(error, LocalApiError):
                raise
            raise LocalApiError(str(error), 503) from error

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

    def execute_authorized_plan_query(self, run_id: str, payload: object) -> dict[str, object]:
        """Run a metadata query only after recording the named provider consent."""
        raw_body = _object_payload(payload)
        if "sources" not in raw_body:
            raise LocalApiError("authorized metadata retrieval requires explicitly selected sources")
        _selected_sources(raw_body.get("sources"))
        body = self._record_explicit_external_authorization(run_id, raw_body, "literature.metadata_retrieval")
        run_dir, mission = self._active_mission(run_id)
        call_id = _dsh_call_id(body)
        request = {key: body[key] for key in ("query_index", "counter", "sources") if key in body}
        try:
            _require_runtime_invariant_safety(run_dir, mission.mission_id)
            dispatch = begin_external_dispatch(
                run_dir, mission_id=mission.mission_id, dsh_call_id=call_id,
                plugin_id="literature.metadata_retrieval", operation="metadata_query", request_shape=request,
            )
            if dispatch["duplicate"]:
                return _completed_query_result(run_dir, run_id, request)
            result = self.execute_plan_query(run_id, request)
            receipt_ids = _latest_provider_receipt_ids(run_dir, provider="sciverse", operation="agentic_search") if "sciverse" in request.get("sources", []) else ()
            complete_external_dispatch(run_dir, mission_id=mission.mission_id, dsh_call_id=call_id, provider_receipt_ids=receipt_ids)
            return result
        except (SciverseConfigurationError, SciverseRequestError, MetadataSearchConfigurationError, MetadataSearchRequestError, ExternalDispatchError, LocalApiError, OSError, ValueError) as error:
            if not isinstance(error, ExternalDispatchError) or "already" not in str(error):
                try:
                    mark_external_dispatch_unknown(run_dir, mission_id=mission.mission_id, dsh_call_id=call_id)
                except ExternalDispatchError:
                    pass
            if isinstance(error, LocalApiError):
                raise
            raise LocalApiError(str(error), 503) from error

    def submit_authorized_mineru_source(self, run_id: str, payload: object) -> dict[str, object]:
        """Submit one screened, content-authorized HTTPS source to MinerU without exposing its URL."""
        body = self._record_explicit_external_authorization(
            run_id, payload, "document.mineru_private_parse", state=MissionState.EXTRACT,
        )
        document_id, source_url = body.get("document_id"), body.get("source_url")
        if not isinstance(document_id, str) or not document_id.strip() or len(document_id.strip()) > 255:
            raise LocalApiError("document_id is invalid")
        if not isinstance(source_url, str):
            raise LocalApiError("source_url is invalid")
        run_dir, mission = self._active_mission(run_id)
        call_id = _dsh_call_id(body)
        try:
            _require_runtime_invariant_safety(run_dir, mission.mission_id)
            dispatch = begin_external_dispatch(
                run_dir, mission_id=mission.mission_id, dsh_call_id=call_id,
                plugin_id="document.mineru_private_parse", operation="mineru_submit",
                request_shape={"document_id": document_id.strip(), "source_url_sha256": hashlib.sha256(source_url.encode("utf-8")).hexdigest()},
            )
            if dispatch["duplicate"]:
                return _completed_mineru_result(run_dir, mission.mission_id, run_id, document_id)
            candidates = _load_object(run_dir / "retrieval_candidates.json", "retrieval candidate artifact")
            require_eligible_candidate(run_dir, document_id)
            require_document_screened_for_fulltext(run_dir, mission.mission_id, candidates, document_id)
            settings = self.settings_loader()
            task = MinerUAdapter(settings).submit_remote_source(source_url)
            source_digest = hashlib.sha256(source_url.encode("utf-8")).hexdigest()
            receipt = mineru_task_receipt(
                operation="source_parse_submit",
                document_id=document_id,
                source_url_sha256=source_digest,
                task_id=task.task_id,
                task_state=task.state,
                model_version=settings.mineru_model_version,
                status_code=task.status_code,
                request_id=task.request_id,
            )
            append_provider_receipt(run_dir, receipt)
            record_source_parse_task(
                run_dir,
                mission_id=mission.mission_id,
                document_id=document_id,
                source_url=source_url,
                task=task,
                model_version=settings.mineru_model_version,
            )
            complete_external_dispatch(run_dir, mission_id=mission.mission_id, dsh_call_id=call_id, provider_receipt_ids=(receipt["receipt_id"],))
        except (CandidateScreeningError, EvidenceIngestionError, MinerUConfigurationError, MinerURequestError, ProviderReceiptError, SourceParseArtifactError, UiExportError, ExternalDispatchError, ValueError) as error:
            try:
                mark_external_dispatch_unknown(run_dir, mission_id=mission.mission_id, dsh_call_id=call_id)
            except ExternalDispatchError:
                pass
            raise LocalApiError(str(error), 503 if isinstance(error, (MinerUConfigurationError, MinerURequestError)) else 400) from error
        FlightRecorder(self.runs_dir, run_id).record(
            event_type="source_parse_submitted",
            actor="document_parser",
            state=MissionState.EXTRACT,
            payload={"document_id": document_id, "provider": "mineru", "task_state": task.state, "receipt_id": receipt["receipt_id"]},
        )
        return {"run_id": run_id, "document_id": document_id, "provider": "mineru", "task_state": task.state, "trust_status": "authorized_parse_dispatch_not_evidence_acceptance"}

    def poll_authorized_mineru_source(self, run_id: str, payload: object) -> dict[str, object]:
        """Poll one prior MinerU task after the same explicit mission consent; never fetch parser output."""
        body = self._record_explicit_external_authorization(
            run_id, payload, "document.mineru_private_parse", state=MissionState.EXTRACT,
        )
        document_id = body.get("document_id")
        if not isinstance(document_id, str) or not document_id.strip() or len(document_id.strip()) > 255:
            raise LocalApiError("document_id is invalid")
        run_dir, mission = self._active_mission(run_id)
        call_id = _dsh_call_id(body)
        try:
            _require_runtime_invariant_safety(run_dir, mission.mission_id)
            dispatch = begin_external_dispatch(
                run_dir, mission_id=mission.mission_id, dsh_call_id=call_id,
                plugin_id="document.mineru_private_parse", operation="mineru_poll",
                request_shape={"document_id": document_id.strip()},
            )
            if dispatch["duplicate"]:
                return _completed_mineru_result(run_dir, mission.mission_id, run_id, document_id)
            stored = task_for_document(run_dir, mission_id=mission.mission_id, document_id=document_id)
            require_active_run(run_dir, mission.mission_id)
            settings = self.settings_loader()
            task = MinerUAdapter(settings).get_task(private_task_id_for_document(run_dir, mission_id=mission.mission_id, document_id=document_id))
            receipt = mineru_task_receipt(
                operation="source_parse_poll",
                document_id=document_id,
                source_url_sha256=stored["source_url_sha256"],
                task_id=task.task_id,
                task_state=task.state,
                model_version=stored["model_version"],
                status_code=task.status_code,
                request_id=task.request_id,
            )
            append_provider_receipt(run_dir, receipt)
            update_source_parse_task(run_dir, mission_id=mission.mission_id, document_id=document_id, task=task)
            complete_external_dispatch(run_dir, mission_id=mission.mission_id, dsh_call_id=call_id, provider_receipt_ids=(receipt["receipt_id"],))
        except (MinerUConfigurationError, MinerURequestError, ProviderReceiptError, SourceParseArtifactError, RunControlError, ExternalDispatchError, ValueError) as error:
            try:
                mark_external_dispatch_unknown(run_dir, mission_id=mission.mission_id, dsh_call_id=call_id)
            except ExternalDispatchError:
                pass
            raise LocalApiError(str(error), 503 if isinstance(error, (MinerUConfigurationError, MinerURequestError)) else 400) from error
        FlightRecorder(self.runs_dir, run_id).record(
            event_type="source_parse_polled",
            actor="document_parser",
            state=MissionState.EXTRACT,
            payload={"document_id": document_id, "provider": "mineru", "task_state": task.state, "receipt_id": receipt["receipt_id"]},
        )
        return {"run_id": run_id, "document_id": document_id, "provider": "mineru", "task_state": task.state, "trust_status": "authorized_parse_status_not_evidence_acceptance"}

    def _record_explicit_external_authorization(
        self,
        run_id: str,
        payload: object,
        plugin_id: str,
        *,
        state: MissionState = MissionState.PLAN,
    ) -> dict[str, object]:
        """Validate and persist a user-supplied, mission-scoped external dispatch receipt."""
        body = _object_payload(payload)
        raw_authorizations = body.get("authorizations")
        actor = body.get("actor", "human_researcher")
        if (
            not isinstance(raw_authorizations, list)
            or not raw_authorizations
            or len(raw_authorizations) > 12
            or not all(isinstance(item, str) and item.strip() and len(item.strip()) <= 120 for item in raw_authorizations)
            or not isinstance(actor, str)
            or not actor.strip()
            or len(actor.strip()) > 200
        ):
            raise LocalApiError("explicit external authorization is invalid")
        dsh_call_id = _dsh_call_id(body)
        _, mission = self._active_mission(run_id)
        normalized = tuple(sorted({item.strip() for item in raw_authorizations}))
        try:
            decision = evaluate_mission_authorization(
                CosMatterHarnessCatalogue(),
                MissionAuthorization(mission.mission_id, plugin_id, normalized, actor.strip()),
            )
        except ValueError as error:
            raise LocalApiError(str(error)) from error
        if not decision["permitted"]:
            raise LocalApiError("explicit external authorization does not permit this dispatch", 403)
        FlightRecorder(self.runs_dir, run_id).record(
            event_type="external_plugin_dispatch_authorized",
            actor="user_consent",
            state=state,
            payload={
                "plugin_id": plugin_id,
                "authorizations": list(normalized),
                "dsh_call_id_sha256": hashlib.sha256(dsh_call_id.encode("utf-8")).hexdigest(),
                "trust_status": "explicit_mission_authorization_receipt_not_execution_receipt",
            },
        )
        return body
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
        if candidate_document_id is not None and requested_run_id is None:
            raise LocalApiError("candidate PDF intake requires a run_id")
        if requested_run_id is not None:
            if not isinstance(requested_run_id, str) or (candidate_document_id is not None and not isinstance(candidate_document_id, str)):
                raise LocalApiError("PDF intake identifiers must be strings")
            run_id = _api_safe_run_id(requested_run_id)
            if (self.runs_dir / run_id).exists():
                run_dir, mission = self._active_mission(run_id)
                if candidate_document_id is None:
                    expected = (_bounded_text(body, "question"), _bounded_text(body, "material", 300), _bounded_text(body, "property", 300), _bounded_text(body, "scope", 1_000))
                    if expected != (mission.question, mission.material, mission.property_name, mission.scope):
                        raise LocalApiError("PDF submission identity is already bound to a different mission", 409)
                    created = {"run_id": run_id, "mission_id": mission.mission_id, "fleet_type": "fulltext_intake", "mission_type": "private_pdf"}
                else:
                    created = {"run_id": run_id, "mission_id": mission.mission_id, "fleet_type": "fulltext_intake", "mission_type": "candidate_pdf"}
            elif candidate_document_id is None:
                created = self.create_mission({**body, "run_id": run_id})
                run_dir, mission = self._active_mission(run_id)
            else:
                run_dir, mission = self._active_mission(run_id)
                created = {"run_id": run_id, "mission_id": mission.mission_id, "fleet_type": "fulltext_intake", "mission_type": "candidate_pdf"}
            if candidate_document_id is not None:
                try:
                    candidates = _load_object(run_dir / "retrieval_candidates.json", "retrieval candidate artifact")
                    require_document_screened_for_fulltext(run_dir, mission.mission_id, candidates, candidate_document_id)
                except (CandidateScreeningError, UiExportError, ValueError) as error:
                    raise LocalApiError(str(error)) from error
        else:
            created = self.create_mission(body)
            run_id = str(created["run_id"])
            run_dir, mission = self._active_mission(run_id)
        try:
            document_id = safe_document_id(run_id, file_name, content)
            try:
                existing = task_for_pdf_document(run_dir, mission.mission_id, document_id)
            except PdfTaskRegistryError:
                existing = None
            if existing is not None:
                return {**created, "document_id": document_id, "candidate_document_id": existing.get("candidate_document_id"), "state": existing["state"], "doi_status": existing["doi_status"], "idempotency_status": "duplicate_completed"}
            assert_pdf_task_slot(run_dir, mission.mission_id, candidate_document_id if isinstance(candidate_document_id, str) else None)
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
            # A prior transport/download error is recoverable.  Once the
            # provider answers again, remove that stale warning instead of
            # making a healthy pending or completed task look broken forever.
            artifact.pop("error", None)
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
        except MinerUConfigurationError as error:
            artifact["state"] = "failed"
            artifact["error"] = str(error)[:300]
        except (MinerURequestError, PrivateStorageError, OSError, UnicodeDecodeError) as error:
            # A status/download failure does not prove that MinerU failed. Keep
            # this task pollable so a later local refresh can reconcile it.
            artifact["state"] = "running"
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
        for key in ("sample_form", "substrate", "method"):
            value = conditions[key]
            if not isinstance(value, str) or not value.strip() or len(value.strip()) > 240:
                raise LocalApiError(f"evidence review {key} must be a non-empty short text value")
        for key in ("strain_percent", "thickness_nm", "temperature_k"):
            value = conditions[key]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                raise LocalApiError(f"evidence review {key} must be a finite number")
        for key in ("thickness_nm", "temperature_k"):
            if float(conditions[key]) < 0:
                raise LocalApiError(f"evidence review {key} must be non-negative")
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

    def expand_authorized_pdf_citations(self, run_id: str, payload: object) -> dict[str, object]:
        """Expand a DOI bibliography only after recording explicit metadata consent."""
        raw_body = _object_payload(payload)
        document_id = raw_body.get("document_id")
        if not isinstance(document_id, str) or not document_id.strip() or len(document_id.strip()) > 255:
            raise LocalApiError("document_id is invalid")
        body = self._record_explicit_external_authorization(run_id, raw_body, "bibliography.two_hop_expand", state=MissionState.RETRIEVE)
        run_dir, mission = self._active_mission(run_id)
        call_id = _dsh_call_id(body)
        document_id = document_id.strip()
        try:
            _require_runtime_invariant_safety(run_dir, mission.mission_id)
            dispatch = begin_external_dispatch(
                run_dir, mission_id=mission.mission_id, dsh_call_id=call_id,
                plugin_id="bibliography.two_hop_expand", operation="citation_expansion",
                request_shape={"document_id": document_id},
            )
            if dispatch["duplicate"]:
                return _completed_citation_result(run_dir, mission.mission_id, run_id, document_id)
            result = self._expand_pdf_citations(run_id, document_id)
            complete_external_dispatch(run_dir, mission_id=mission.mission_id, dsh_call_id=call_id)
            return result
        except (CitationExpansionError, CrossrefRequestError, OpenAlexConfigurationError, OpenAlexRequestError, ExternalDispatchError, LocalApiError, OSError, ValueError) as error:
            if not isinstance(error, ExternalDispatchError) or "already" not in str(error):
                try:
                    mark_external_dispatch_unknown(run_dir, mission_id=mission.mission_id, dsh_call_id=call_id)
                except ExternalDispatchError:
                    pass
            if isinstance(error, LocalApiError):
                raise
            raise LocalApiError(str(error), 503) from error

    def _expand_pdf_citations(self, run_id: str, document_id: str | None = None) -> dict[str, object]:
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

    def workflow_status(self, run_id: str) -> dict[str, object]:
        """Return a count-only workflow projection for loopback harness adapters.

        It recomputes readiness from local artifacts rather than returning those
        artifacts. Candidates, excerpts, URLs, private paths, provider payloads
        and credentials are deliberately excluded.
        """
        run_dir, mission = self._active_mission(run_id, require_active=False)
        try:
            readiness = workflow_readiness(run_dir, mission)
        except WorkflowReadinessError as error:
            raise LocalApiError(str(error)) from error
        return {
            "schema_version": "1.0",
            "run_id": _api_safe_run_id(run_id),
            "mission_id": mission.mission_id,
            "trust_status": "loopback_workflow_status_not_scientific_evidence",
            "next_stage": readiness["next_stage"],
            "stages": [
                {"stage": item["stage"], "status": item["status"], "counts": item["counts"]}
                for item in readiness["stages"]
            ],
        }

    def stage_contract(self, run_id: str) -> dict[str, object]:
        """Return a fixed, count-only completion and recovery contract.

        This is a read-only projection: symbolic recovery routes do not grant
        consent, dispatch a provider, mutate a run, or expose audit details.
        """
        run_dir, mission = self._active_mission(run_id, require_active=False)
        try:
            contract = stage_contract(run_dir, mission)
        except StageContractError as error:
            raise LocalApiError(str(error)) from error
        return {"run_id": _api_safe_run_id(run_id), **contract}

    def operational_telemetry(self, run_id: str) -> dict[str, object]:
        """Return local aggregate operations, never a provider bill or payload."""
        run_dir, mission = self._active_mission(run_id, require_active=False)
        try:
            telemetry = operational_telemetry(run_dir, mission)
        except OperationalTelemetryError as error:
            raise LocalApiError(str(error)) from error
        return {"run_id": _api_safe_run_id(run_id), **telemetry}

    def workflow_dag(self, run_id: str) -> dict[str, object]:
        """Return a declared DAG readiness view; it never schedules a stage."""
        run_dir, mission = self._active_mission(run_id, require_active=False)
        try:
            return workflow_dag_projection(_api_safe_run_id(run_id), run_dir, mission)
        except WorkflowDagError as error:
            raise LocalApiError(str(error)) from error

    def reminder_board(self) -> dict[str, object]:
        """Read bounded local cross-session reminders; never schedule work."""
        summaries: list[dict[str, object]] = []
        if self.runs_dir.exists():
            for candidate in sorted(self.runs_dir.iterdir(), key=lambda item: item.name):
                if not candidate.is_dir() or candidate.is_symlink():
                    continue
                try:
                    run_id = _api_safe_run_id(candidate.name)
                    run_dir, mission = self._active_mission(run_id, require_active=False)
                    contract = stage_contract(run_dir, mission)
                    telemetry = operational_telemetry(run_dir, mission)
                    state = self.run_status(run_id)
                except (LocalApiError, StageContractError, OperationalTelemetryError):
                    continue
                summaries.append({
                    "run_id": run_id,
                    "terminal": bool(state["terminal"]),
                    "runtime_safety": contract["runtime_safety"],
                    "incomplete_dispatch_count": sum(item["incomplete_count"] for item in telemetry["dispatch_operations"]),
                    "unknown_dispatch_count": sum(item["unknown_outcome_count"] for item in telemetry["dispatch_operations"]),
                    "stages": [{"stage": item["stage"], "status": item["status"]} for item in contract["stages"]],
                })
        try:
            return project_reminder_board(summaries, self.runs_dir.parent / "project_decision_memory")
        except ReminderBoardError as error:
            raise LocalApiError(str(error)) from error

    def approved_artifacts(self, run_id: str) -> dict[str, object]:
        """List only fixed, already-generated safe artifacts; no filesystem paths."""
        run_dir, mission = self._active_mission(run_id, require_active=False)
        try:
            return artifact_manifest(run_dir=run_dir, run_id=_api_safe_run_id(run_id), mission_id=mission.mission_id)
        except ArtifactContractError as error:
            raise LocalApiError(str(error), 404) from error

    def approved_artifact_download(self, run_id: str, artifact_id: str) -> ArtifactDownload:
        """Read a fixed allowlisted export, never an arbitrary run-relative file."""
        run_dir, mission = self._active_mission(run_id, require_active=False)
        try:
            return approved_artifact_download(
                run_dir=run_dir, run_id=_api_safe_run_id(run_id), mission_id=mission.mission_id, artifact_id=artifact_id,
            )
        except ArtifactContractError as error:
            raise LocalApiError(str(error), 404) from error

    def search_accepted_evidence(self, run_id: str, payload: object) -> dict[str, object]:
        """Search only reviewed evidence-card metadata; never read source text."""
        run_dir, mission = self._active_mission(run_id, require_active=False)
        body = _object_payload(payload)
        query, limit = body.get("query"), body.get("limit", 8)
        try:
            cards = _evidence_cards_from_payloads(_load_array_if_present(run_dir / "evidence_cards.json", "evidence artifacts"))
            decisions = _verification_decisions_from_payloads(_load_array_if_present(run_dir / "verification_decisions.json", "verification decisions"))
            result = search_accepted_evidence(mission=mission, cards=cards, decisions=decisions, query=query, limit=limit)
        except (AcceptedEvidenceSearchError, UiExportError, ValueError) as error:
            raise LocalApiError(str(error)) from error
        FlightRecorder(self.runs_dir, run_id).record(
            event_type="accepted_evidence_searched", actor="accepted_evidence_search", state=MissionState.MAP,
            payload={"query_sha256": result["query_sha256"], "result_count": result["result_count"], "trust_status": result["trust_status"]},
        )
        return result

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

    def project_accepted_evidence_graph(self, run_id: str) -> dict[str, object]:
        """Build one persisted, read-only graph from accepted evidence only."""
        run_dir, mission = self._active_mission(run_id)
        try:
            cards = _evidence_cards_from_payloads(
                _load_array_if_present(run_dir / "evidence_cards.json", "evidence artifacts")
            )
            decisions = _verification_decisions_from_payloads(
                _load_array_if_present(run_dir / "verification_decisions.json", "verification decisions")
            )
            payload = external_graph_projection(build_accepted_evidence_graph(mission, cards, decisions))
        except (UiExportError, ValueError) as error:
            raise LocalApiError(str(error)) from error
        _write_json(run_dir / "graph_snapshot.json", payload)
        FlightRecorder(self.runs_dir, run_id).record(
            event_type="graph_snapshot_projected",
            actor="graph_projection",
            state=MissionState.MAP,
            payload={
                "schema_version": payload["schema_version"],
                "node_count": len(payload["nodes"]),
                "edge_count": len(payload["edges"]),
                "trust_status": payload["trust_status"],
            },
        )
        return payload

    def graph_projection(self, run_id: str, *, node_types: tuple[str, ...] = (), offset: int = 0, limit: int = 50) -> dict[str, object]:
        """Read an already-projected graph; this endpoint never derives data."""
        run_dir, _ = self._active_mission(run_id, require_active=False)
        try:
            payload = _load_object(run_dir / "graph_snapshot.json", "graph snapshot")
            validated = validate_graph_payload(payload)
            from .graph_validation import graph_snapshot_from_payload
            page = bounded_graph_projection(graph_snapshot_from_payload(validated), node_types=node_types, offset=offset, limit=limit)
        except (UiExportError, GraphContractError) as error:
            raise LocalApiError(str(error), 404) from error
        digest = hashlib.sha256(json.dumps(page, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        receipt = PluginExecutionReceipt(
            mission_id=str(page["mission_id"]), plugin_id="graph.export_projection",
            authorization_receipt_id="local_safe_graph_projection", outcome="completed", output_artifact_hashes=(digest,),
        )
        FlightRecorder(self.runs_dir, run_id).record(
            event_type="plugin_execution_receipt", actor="graph_projection_api", state=MissionState.MAP,
            payload=receipt.as_audit_payload(),
        )
        return page

    def request_graph_review(self, run_id: str, payload: object) -> dict[str, object]:
        """Record a pending human graph-review request; never accept evidence."""
        run_dir, mission = self._active_mission(run_id)
        body = _object_payload(payload)
        raw_nodes, rationale = body.get("node_ids"), body.get("rationale")
        if not isinstance(raw_nodes, list) or not raw_nodes or not all(isinstance(item, str) for item in raw_nodes) or not isinstance(rationale, str):
            raise LocalApiError("graph review request is invalid")
        try:
            snapshot = validate_graph_payload(_load_object(run_dir / "graph_snapshot.json", "graph snapshot"))
            node_ids = tuple(item.strip() for item in raw_nodes)
            if not set(node_ids).issubset({str(node["node_id"]) for node in snapshot["nodes"]}):
                raise LocalApiError("graph review nodes are not in this graph")
            request = GraphReviewRequest(mission.mission_id, str(snapshot["graph_id"]), node_ids, rationale.strip())
        except (GraphContractError, ValueError) as error:
            raise LocalApiError(str(error)) from error
        requests_path = run_dir / "graph_review_requests.jsonl"
        with requests_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(request.to_dict(), ensure_ascii=False, sort_keys=True) + "\n")
        FlightRecorder(self.runs_dir, run_id).record(event_type="graph_review_requested", actor="human_review_request", state=MissionState.MAP, payload={"request_id": request.request_id, "graph_id": request.graph_id, "node_count": len(request.node_ids), "trust_status": "pending_human_review_not_evidence_acceptance"})
        return request.to_dict()

    def draft_graph_plan(self, run_id: str, payload: object) -> dict[str, object]:
        """Persist an untrusted graph-inspection draft; it cannot execute or accept evidence."""
        run_dir, mission = self._active_mission(run_id)
        body = _object_payload(payload)
        raw_nodes, intent = body.get("node_ids"), body.get("intent")
        if not isinstance(raw_nodes, list) or not all(isinstance(item, str) for item in raw_nodes) or not isinstance(intent, str):
            raise LocalApiError("graph plan draft is invalid")
        try:
            snapshot = validate_graph_payload(_load_object(run_dir / "graph_snapshot.json", "graph snapshot"))
            node_ids = tuple(item.strip() for item in raw_nodes)
            if not set(node_ids).issubset({str(node["node_id"]) for node in snapshot["nodes"]}):
                raise LocalApiError("graph plan nodes are not in this graph")
            draft = GraphPlanDraft(mission.mission_id, str(snapshot["graph_id"]), node_ids, intent)
        except (GraphContractError, ValueError) as error:
            raise LocalApiError(str(error)) from error
        drafts_path = run_dir / "graph_plan_drafts.jsonl"
        with drafts_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(draft.to_dict(), ensure_ascii=False, sort_keys=True) + "\n")
        FlightRecorder(self.runs_dir, run_id).record(
            event_type="graph_plan_drafted", actor="graph_plan_draft", state=MissionState.MAP,
            payload={"graph_id": draft.graph_id, "node_count": len(draft.node_ids), "trust_status": "untrusted_graph_plan_draft_not_execution_or_evidence_acceptance"},
        )
        return draft.to_dict()

    def assist_authorized_graph_plan(self, run_id: str, payload: object) -> dict[str, object]:
        """Request one untrusted DeepSeek graph-plan draft after a durable consent receipt."""
        raw_body = _object_payload(payload)
        raw_nodes, intent = raw_body.get("node_ids"), raw_body.get("intent")
        if not isinstance(raw_nodes, list) or not all(isinstance(item, str) for item in raw_nodes) or not isinstance(intent, str):
            raise LocalApiError("graph model plan request is invalid")
        body = self._record_explicit_external_authorization(run_id, raw_body, "graph.plan_assist", state=MissionState.MAP)
        run_dir, mission = self._active_mission(run_id)
        call_id = _dsh_call_id(body)
        node_ids = tuple(item.strip() for item in raw_nodes)
        intent = intent.strip()
        try:
            _require_runtime_invariant_safety(run_dir, mission.mission_id)
            dispatch = begin_external_dispatch(
                run_dir, mission_id=mission.mission_id, dsh_call_id=call_id,
                plugin_id="graph.plan_assist", operation="deepseek_graph_plan_draft",
                request_shape={"node_ids": node_ids, "intent": intent},
            )
            if dispatch["duplicate"]:
                return _completed_graph_model_plan_result(run_dir, mission.mission_id, node_ids, intent)
            result = self._assist_graph_plan(run_id, raw_body)
            complete_external_dispatch(run_dir, mission_id=mission.mission_id, dsh_call_id=call_id)
            return result
        except (GraphContractError, GraphModelPlanError, DeepSeekConfigurationError, DeepSeekRequestError, ExternalDispatchError, LocalApiError, OSError, ValueError) as error:
            if not isinstance(error, ExternalDispatchError) or "already" not in str(error):
                try:
                    mark_external_dispatch_unknown(run_dir, mission_id=mission.mission_id, dsh_call_id=call_id)
                except ExternalDispatchError:
                    pass
            if isinstance(error, LocalApiError):
                raise
            raise LocalApiError(str(error), 503 if isinstance(error, (DeepSeekConfigurationError, DeepSeekRequestError)) else 400) from error

    def _assist_graph_plan(self, run_id: str, payload: object) -> dict[str, object]:
        """Perform one already-authorized graph-plan request; never call directly from a route."""
        run_dir, mission = self._active_mission(run_id)
        body = _object_payload(payload)
        raw_nodes, intent = body.get("node_ids"), body.get("intent")
        if not isinstance(raw_nodes, list) or not all(isinstance(item, str) for item in raw_nodes) or not isinstance(intent, str):
            raise LocalApiError("graph model plan request is invalid")
        try:
            snapshot = validate_graph_payload(_load_object(run_dir / "graph_snapshot.json", "graph snapshot"))
            node_ids = tuple(item.strip() for item in raw_nodes)
            system_prompt, user_prompt = graph_plan_assist_prompts(snapshot, node_ids, intent)
            completion = DeepSeekAdapter(self.settings_loader()).draft(system_prompt=system_prompt, user_prompt=user_prompt)
            draft = normalized_graph_model_plan_draft(snapshot, node_ids, intent, completion.content, completion.model)
        except (GraphContractError, GraphModelPlanError, DeepSeekConfigurationError, DeepSeekRequestError, ValueError) as error:
            raise LocalApiError(str(error), 503 if isinstance(error, (DeepSeekConfigurationError, DeepSeekRequestError)) else 400) from error
        with (run_dir / "graph_model_plan_drafts.jsonl").open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(draft, ensure_ascii=False, sort_keys=True) + "\n")
        digest = hashlib.sha256(json.dumps(draft, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        FlightRecorder(self.runs_dir, run_id).record(event_type="graph_model_plan_drafted", actor="graph_model_plan", state=MissionState.MAP, payload={"plugin_id": "graph.plan_assist", "model": completion.model, "output_artifact_hash": digest, "trust_status": draft["trust_status"]})
        return draft

    def approve_graph_plan(self, run_id: str, payload: object) -> dict[str, object]:
        """Record a human plan acknowledgement without granting execution capability."""
        run_dir, mission = self._active_mission(run_id)
        body = _object_payload(payload)
        plan_id, reviewer, rationale = body.get("plan_id"), body.get("reviewer"), body.get("rationale")
        if not all(isinstance(value, str) for value in (plan_id, reviewer, rationale)):
            raise LocalApiError("graph plan approval is invalid")
        try:
            snapshot = validate_graph_payload(_load_object(run_dir / "graph_snapshot.json", "graph snapshot"))
            draft = _graph_plan_draft_by_id(run_dir, plan_id.strip())
            if draft is None or draft.get("mission_id") != mission.mission_id or draft.get("graph_id") != snapshot["graph_id"]:
                raise LocalApiError("graph plan approval does not reference this mission graph draft")
            approval = GraphPlanApproval(mission.mission_id, str(snapshot["graph_id"]), plan_id.strip(), reviewer, rationale)
        except (GraphContractError, ValueError) as error:
            raise LocalApiError(str(error)) from error
        with (run_dir / "graph_plan_approvals.jsonl").open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(approval.to_dict(), ensure_ascii=False, sort_keys=True) + "\n")
        FlightRecorder(self.runs_dir, run_id).record(event_type="graph_plan_human_approved", actor="human_graph_plan_review", state=MissionState.MAP, payload={"approval_id": approval.approval_id, "plan_id": approval.plan_id, "graph_id": approval.graph_id, "trust_status": "human_approved_graph_plan_follow_up_not_execution_or_evidence_acceptance"})
        return approval.to_dict()

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


def _graph_plan_draft_by_id(run_dir: Path, plan_id: str) -> dict[str, object] | None:
    """Read only known, normalized plan-draft ledgers; never scan the run directory."""
    if not plan_id.startswith(("graph_plan_", "graph_model_plan_")):
        return None
    matches: list[dict[str, object]] = []
    for filename in ("graph_plan_drafts.jsonl", "graph_model_plan_drafts.jsonl"):
        path = run_dir / filename
        if not path.is_file():
            continue
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                item = json.loads(line)
                if isinstance(item, dict) and item.get("plan_id") == plan_id:
                    matches.append(item)
        except (OSError, json.JSONDecodeError) as error:
            raise LocalApiError("graph plan draft ledger is invalid") from error
    if len(matches) > 1:
        raise LocalApiError("graph plan draft identifier is ambiguous")
    return matches[0] if matches else None


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


def _dsh_call_id(payload: dict[str, Any]) -> str:
    value = payload.get("dsh_call_id")
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > 256:
        raise LocalApiError("DSH call identity is required for external dispatch")
    return value.strip()


def _require_runtime_invariant_safety(run_dir: Path, mission_id: str) -> None:
    """Block a new sensitive dispatch on structural, not recoverable, corruption.

    A prior ``unknown`` outcome is intentionally not silently cleared here.
    It remains visible in the audit and the same call ID is rejected by the
    ledger.  A *new* explicitly authorised call may follow human/provider
    status review, whereas broken state history, unpaired authorization,
    receipt/result links, or evidence decisions block all sensitive dispatch.
    """
    try:
        audit = audit_runtime_invariants(run_dir, mission_id)
    except RuntimeInvariantError as error:
        raise LocalApiError("runtime invariant audit could not establish a safe dispatch boundary", 409) from error
    checks = audit["checks"]
    authorization = checks["authorization_dispatch"]
    safe = (
        checks["state_transitions"]["passed"]
        and checks["provider_results"]["passed"]
        and checks["evidence_decisions"]["passed"]
        and authorization["unpaired_dispatch_count"] == 0
        and authorization["incomplete_dispatch_count"] == 0
    )
    if not safe:
        raise LocalApiError("runtime invariant audit blocks sensitive dispatch; repair local artifact relationships first", 409)


def _completed_draft_result(run_dir: Path, run_id: str) -> dict[str, object]:
    try:
        payload = _load_object(run_dir / "research_plan_draft.json", "research plan draft")
    except UiExportError as error:
        raise LocalApiError("completed external draft has no safe local result") from error
    if set(payload) != {"schema_version", "trust_status", "model", "content"} or payload.get("schema_version") != "1.0" or payload.get("trust_status") != "untrusted_draft" or not isinstance(payload.get("content"), str) or not payload["content"].strip() or len(payload["content"]) > 16_000:
        raise LocalApiError("completed external draft has no safe local result")
    return {"run_id": run_id, "trust_status": "untrusted_draft", "content": payload["content"], "idempotency_status": "duplicate_completed"}


def _completed_query_result(run_dir: Path, run_id: str, request: dict[str, object]) -> dict[str, object]:
    try:
        mission = _mission_from_payload(_load_object(run_dir / "mission.json", "mission artifact"))
        plan = load_approved_flight_plan(run_dir, mission.mission_id)
        counter = request.get("counter", False)
        index = request.get("query_index")
        sources = _selected_sources(request.get("sources"))
        if not isinstance(counter, bool) or not isinstance(index, int) or isinstance(index, bool):
            raise ValueError
        queries = plan.counter_queries if counter else plan.queries
        query = queries[index]
        artifact = _load_object(run_dir / "retrieval_candidates.json", "retrieval candidate artifact")
        searches = artifact.get("searches")
        if not isinstance(searches, list):
            raise ValueError
        match = next((item for item in reversed(searches) if isinstance(item, dict) and item.get("query") == query and isinstance(item.get("candidates"), list)), None)
        if match is None:
            raise ValueError
        candidates = match["candidates"]
    except (IndexError, PlanApprovalError, UiExportError, ValueError) as error:
        raise LocalApiError("completed metadata dispatch has no safe local result") from error
    return {
        "run_id": run_id,
        "query_kind": "counter" if counter else "primary",
        "query_index": index,
        "sources": list(sources),
        "source_counts": {},
        "candidate_count": len(candidates),
        "candidates": candidates,
        "idempotency_status": "duplicate_completed",
    }


def _completed_mineru_result(run_dir: Path, mission_id: str, run_id: str, document_id: str) -> dict[str, object]:
    try:
        task = task_for_document(run_dir, mission_id=mission_id, document_id=document_id)
    except SourceParseArtifactError as error:
        raise LocalApiError("completed MinerU dispatch has no safe local task record") from error
    state = task.get("state")
    if state not in {"pending", "running", "done", "failed"}:
        raise LocalApiError("completed MinerU dispatch has an invalid local task record")
    return {
        "run_id": run_id,
        "document_id": document_id,
        "provider": "mineru",
        "task_state": state,
        "trust_status": "authorized_parse_status_not_evidence_acceptance",
        "idempotency_status": "duplicate_completed",
    }


def _completed_citation_result(run_dir: Path, mission_id: str, run_id: str, document_id: str) -> dict[str, object]:
    try:
        intake = _pdf_intake(run_dir, mission_id, document_id)
        payload = _load_object(run_dir / "citation_expansion.json", "citation expansion")
        validate_citation_expansion(payload)
        if payload.get("mission_id") != mission_id or payload.get("root_doi") != intake.get("doi"):
            raise ValueError
        nodes, edges, failures = payload["nodes"], payload["edges"], payload["failures"]
        if not isinstance(failures, list):
            raise ValueError
    except (CitationExpansionError, LocalApiError, UiExportError, ValueError) as error:
        raise LocalApiError("completed citation dispatch has no safe local result") from error
    return {
        "run_id": run_id,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "failure_count": len(failures),
        "trust_status": payload["trust_status"],
        "idempotency_status": "duplicate_completed",
    }


def _completed_graph_model_plan_result(
    run_dir: Path,
    mission_id: str,
    node_ids: tuple[str, ...],
    intent: str,
) -> dict[str, object]:
    """Return only a locally validated prior draft for an idempotent DeepSeek call."""
    try:
        snapshot = validate_graph_payload(_load_object(run_dir / "graph_snapshot.json", "graph snapshot"))
        path = run_dir / "graph_model_plan_drafts.jsonl"
        if not path.is_file():
            raise ValueError
        records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        for draft in reversed(records):
            if not isinstance(draft, dict):
                continue
            if draft.get("mission_id") != mission_id or draft.get("graph_id") != snapshot["graph_id"]:
                continue
            if draft.get("requested_node_ids") != list(node_ids) or draft.get("intent") != intent:
                continue
            model = draft.get("model")
            if not isinstance(model, str) or not isinstance(draft.get("suggestions"), list):
                continue
            checked = normalized_graph_model_plan_draft(
                snapshot, node_ids, intent, json.dumps({"suggestions": draft["suggestions"]}), model,
            )
            stable_fields = ("schema_version", "mission_id", "graph_id", "requested_node_ids", "intent", "model", "suggestions", "trust_status", "next_boundary")
            if (
                set(draft) != {"plan_id", *stable_fields, "created_at"}
                or not isinstance(draft.get("plan_id"), str)
                or not draft["plan_id"].startswith("graph_model_plan_")
                or not isinstance(draft.get("created_at"), str)
                or any(draft[field] != checked[field] for field in stable_fields)
            ):
                continue
            return {**draft, "idempotency_status": "duplicate_completed"}
    except (GraphContractError, GraphModelPlanError, OSError, UiExportError, ValueError, json.JSONDecodeError) as error:
        raise LocalApiError("completed graph model dispatch has no safe local result") from error
    raise LocalApiError("completed graph model dispatch has no safe local result")


def _latest_provider_receipt_ids(run_dir: Path, *, provider: str, operation: str) -> tuple[str, ...]:
    path = run_dir / "provider_receipts.jsonl"
    if not path.exists():
        return ()
    try:
        matches = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except (OSError, json.JSONDecodeError) as error:
        raise LocalApiError("provider receipt ledger is invalid") from error
    for receipt in reversed(matches):
        if isinstance(receipt, dict) and receipt.get("provider") == provider and receipt.get("operation") == operation and isinstance(receipt.get("receipt_id"), str):
            return (receipt["receipt_id"],)
    return ()


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
    if original_question is not None:
        formulas = _explicit_formula_anchors(original_question)
        focus_patterns = [pattern for pattern in _CANDIDATE_FOCUS_PATTERNS if pattern.search(original_question)]
        requires_chinese = bool(re.search(r"[\u3400-\u9fff]", original_question))
        for candidate in result:
            candidate_text = " ".join(candidate[field] for field in ("question", "material", "property", "scope"))
            candidate_formulas = set(_explicit_formula_anchors(candidate_text))
            if any(formula not in candidate_formulas for formula in formulas):
                raise ValueError("DeepSeek candidate must remain anchored to every explicit material formula")
            if focus_patterns and not any(pattern.search(candidate_text) for pattern in focus_patterns):
                raise ValueError("DeepSeek candidate must remain anchored to the target property or phenomenon")
            visible_question = candidate["question"]
            if requires_chinese and not re.search(r"[\u3400-\u9fff]", visible_question):
                raise ValueError("DeepSeek candidate question must use the input question language")
            visible_formulas = set(_explicit_formula_anchors(visible_question))
            if any(formula not in visible_formulas for formula in formulas):
                raise ValueError("DeepSeek candidate question must name every explicit material formula")
            if focus_patterns and not any(pattern.search(visible_question) for pattern in focus_patterns):
                raise ValueError("DeepSeek candidate question must name the target property or phenomenon")
            if not _candidate_question_has_route_detail(candidate["kind"], visible_question):
                raise ValueError("DeepSeek candidate question must name concrete route variables or observables")
    return result


def _normalized_candidate_question(value: str) -> str:
    return "".join(character.casefold() for character in value if character.isalnum())


_CANDIDATE_ROUTE_DETAIL_PATTERNS = {
    "survey": re.compile(
        r"温区|数值|相结构|晶体结构|样品|谱线|曲线|循环数|倍率|电压窗口|前驱体|化学计量|"
        r"range|value|phase assignment|crystal structure|sample|spectr|curve|cycle count|current rate|voltage window|precursor|stoichiometry|method",
        re.IGNORECASE,
    ),
    "contrast": re.compile(
        r"体相|单晶|陶瓷|薄膜|应变|升温|降温|气氛|载量|倍率|电压窗口|接触|频率|边界条件|"
        r"bulk|single crystal|ceramic|thin[- ]?film|strain|heating|cooling|atmosphere|loading|current rate|voltage window|contact|frequency|boundary condition|preparation|measurement",
        re.IGNORECASE,
    ),
    "mechanism": re.compile(
        r"原始|信号|衍射|谱线|曲线|对照|证伪|分解|伪影|结构|化学|循环后|"
        r"raw|signal|diffraction|spectr|curve|control|falsif|decomposition|artefact|artifact|structural|chemical|post[- ]?test|observation",
        re.IGNORECASE,
    ),
}


def _candidate_question_has_route_detail(kind: str, question: str) -> bool:
    pattern = _CANDIDATE_ROUTE_DETAIL_PATTERNS.get(kind)
    return bool(pattern and pattern.search(question))


_CANDIDATE_FOCUS_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"相(?:转变|变)(?:温度)?|phase[- ]?(?:transition|stability|transformation)",
        r"居里温度|curie temperature",
        r"奈尔温度|n[eé]el temperature",
        r"磁(?:转变|相变)(?:温度)?|magnetic transition",
        r"循环稳定性|容量保持率|cycling stability|cycle life|capacity retention",
        r"带隙|band[- ]?gap",
        r"电导率|electrical conductivity",
        r"热导率|thermal conductivity",
        r"矫顽场|coercive field",
        r"剩余极化|remanent polarization",
        r"介电常数|dielectric (?:constant|permittivity)",
        r"漏电流|leakage current",
        r"催化活性|catalytic activity",
        r"吸附能|adsorption energy",
        r"形成能|formation energy",
        r"晶格常数|lattice constant",
        r"制备|合成|生长|退火|沉积|synthesi[sz]|fabricat|growth|anneal|deposition",
    )
)


def _explicit_formula_anchors(value: str) -> tuple[str, ...]:
    normalized = value.translate(str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789"))
    formulas = {
        match.group(0).casefold()
        for match in re.finditer(r"(?<![A-Za-z0-9])(?:[A-Z][a-z]?\d*(?:\.\d+)?){2,}(?![A-Za-z0-9])", normalized)
        if any(character.isdigit() for character in match.group(0))
    }
    return tuple(sorted(formulas))
