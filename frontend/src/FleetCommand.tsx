import { For, Show, createEffect, createMemo, createSignal, onCleanup } from "solid-js";

import { FleetDecoration } from "./FleetDecoration";
import { fleetVisualState } from "./fleetVisualState";
import { auditableAcceptedEvidence, reviewablePaperCount } from "./evidenceLinking";
import { FLEETS, fleetChannels, label, statusLabel, type FleetRecord, type FleetShip, type UiLocale } from "./fleetRegistry";
import type { ImportedBundle } from "./model";
import type { FacilityCatalogueHealth, FacilityContractManifest, HarnessAuthorization, PdfTaskStatus } from "./localApi";
import { workflowNextState } from "./workflowNextState";
import { counterevidenceReadiness } from "./counterevidenceReadiness";
import { researchExtensionReadiness } from "./researchExtensionReadiness";
import { fleetMissionRole, fleetParticipantsForMission, fleetRuntimeLabel, fleetRuntimeStatus } from "./fleetRuntimeState";
import { fleetOrchestration, type FleetRouteState } from "./fleetOrchestration";
import { missionFlightRecorder, type FlightRecordEntry, type FlightRecordState } from "./missionFlightRecorder";
import { missionEventLedger, type MissionEventState } from "./missionEventLedger";
import { flightRecordDestination } from "./missionFlightNavigation";
import { ReadOnlyPreviewContext } from "./ReadOnlyPreviewContext";
import { bfoTemplateDeployment } from "./bfoTemplateDeployment";
import { facilityContractCoverage, facilityContractDeck } from "./facilityContractDeck";
import { safeOperationFeedback } from "./importFeedback";
import type { PdfTaskSnapshotFreshness } from "./pdfTaskFreshness";

type View = "discover" | "workflow" | "graph" | "reader" | "horizon";
const t = (locale: UiLocale, zh: string, en: string) => locale === "zh" ? zh : en;

export function FleetCommand(props: { bundle: ImportedBundle; locale: UiLocale; facilityContracts?: FacilityContractManifest[] | null; facilityCatalogueHealth?: FacilityCatalogueHealth; onRefreshFacilityContracts?: () => void; bfoTemplateId?: string | null; selectedDocumentId: string | null; pdfTask: PdfTaskStatus | null; pdfTaskFreshness?: PdfTaskSnapshotFreshness; pdfTasks?: PdfTaskStatus[]; onSelectPdf?: (task: PdfTaskStatus) => void; markdownUrl: string | null; onRefreshPdf?: () => Promise<void>; onConfirmPdfDoi?: (doi: string) => Promise<void>; onExpandPdfCitations?: () => Promise<void>; onOpenTaskControl?: () => void; automaticMissionPending?: boolean; automaticCancellationRequested?: boolean; onCancelAutomaticMission?: () => Promise<void>; automaticAuthorization?: HarnessAuthorization | null; readOnlyPreview?: boolean; onExitPreview?: () => void; onNavigate: (view: View) => void }) {
  const [catalogueOpen, setCatalogueOpen] = createSignal(false);
  const [selectedFleet, setSelectedFleet] = createSignal<FleetRecord | null>(null);
  const [selectedShip, setSelectedShip] = createSignal<FleetShip | null>(null);
  const [manualDoi, setManualDoi] = createSignal("");
  const [doiBusy, setDoiBusy] = createSignal(false);
  const [doiError, setDoiError] = createSignal<string | null>(null);
  const [pdfRefreshBusy, setPdfRefreshBusy] = createSignal(false);
  const [pdfRefreshError, setPdfRefreshError] = createSignal<string | null>(null);
  let drawerReturnFocus: HTMLElement | null = null;
  let fleetInspector: HTMLElement | undefined;
  const confirmDoi = async () => { const value = manualDoi().trim(); if (doiBusy() || !value || !props.onConfirmPdfDoi) return; setDoiBusy(true); setDoiError(null); try { await props.onConfirmPdfDoi(value); setManualDoi(""); } catch (cause) { setDoiError(safeOperationFeedback(cause, x("无法确认 DOI；请核对格式和当前 PDF 任务。", "Unable to confirm the DOI. Check its format and the current PDF task."))); } finally { setDoiBusy(false); } };
  const x = (zh: string, en: string) => t(props.locale, zh, en);
  const refreshPdf = async () => { if (pdfRefreshBusy() || !props.onRefreshPdf) return; setPdfRefreshBusy(true); setPdfRefreshError(null); try { await props.onRefreshPdf(); } catch (cause) { setPdfRefreshError(safeOperationFeedback(cause, x("无法刷新本机 PDF 状态；当前记录保留，可稍后再次刷新。", "Unable to refresh local PDF status. The current record is retained; refresh again later."))); } finally { setPdfRefreshBusy(false); } };
  const pdfFreshness = () => props.pdfTaskFreshness ?? { state: "pending" as const, observedAt: null, ageMs: null };
  const participants = createMemo(() => fleetParticipantsForMission(props.bundle));
  const templateFormation = createMemo(() => props.bfoTemplateId ? bfoTemplateDeployment(props.bfoTemplateId, props.bundle, props.locale) : []);
  const orchestration = createMemo(() => fleetOrchestration(props.bundle));
  const flightRecord = createMemo(() => missionFlightRecorder(props.bundle, props.pdfTask));
  const eventLedger = createMemo(() => missionEventLedger(props.bundle));
  const auditableEvidenceCount = createMemo(() => auditableAcceptedEvidence(props.bundle).length);
  const flightDestination = (entry: FlightRecordEntry) => flightRecordDestination(entry.id, {
    paperCount: paperCount(),
    hasReviewContext: Boolean(props.selectedDocumentId || props.pdfTask || props.bundle.sourceMapSummary.segmentCount || props.bundle.materialFactSummary.factCount || auditableEvidenceCount()),
    hasEvidence: auditableEvidenceCount() > 0,
    hasGapCandidate: props.bundle.researchGapCandidates.length > 0,
  });
  const routeStateLabel = (state: FleetRouteState) => ({
    active: x("当前编排", "current route"), next: x("下一交接", "next handoff"),
    standby: x("待命", "standby"), framework: x("仅模板", "template only"),
  }[state]);
  const fleetStatusLabel = (status: ReturnType<typeof fleetRuntimeStatus>) => fleetRuntimeLabel(status, props.locale);
  const templateRouteLabel = (state: FleetRouteState) => ({
    active: x("当前阶段编入", "in current stage"), next: x("下一交接", "next handoff"),
    standby: x("计划待命", "planned standby"), framework: x("仅框架", "framework only"),
  }[state]);
  const flightStateLabel = (state: FlightRecordState) => ({
    complete: x("已登记", "recorded"), active: x("当前门禁", "current gate"),
    waiting: x("等待", "waiting"), blocked: x("受阻", "blocked"),
  }[state]);
  const flightLabel = (entry: FlightRecordEntry) => ({
    brief: x("任务简报", "MISSION BRIEF"), candidates: x("候选文献", "REVIEWABLE PAPERS"),
    fulltext: x("私有全文", "PRIVATE FULL TEXT"), "source-map": x("来源定位", "SOURCE MAP"),
    facts: x("材料事实", "MATERIAL FACTS"), evidence: x("EvidenceCard", "EVIDENCECARD"), horizon: x("研究拓展", "RESEARCH HORIZON"),
  }[entry.id]);
  const eventStateLabel = (state: MissionEventState) => ({
    complete: x("已完成", "complete"), active: x("进行中", "active"),
    waiting: x("等待", "waiting"), blocked: x("受阻", "blocked"),
  }[state]);
  const eventTime = (value: string) => value || x("未提供时间戳", "timestamp not supplied");
  const selectedRole = createMemo(() => selectedFleet() ? fleetMissionRole(selectedFleet()!, props.bundle) : null);
  const paperCount = createMemo(() => reviewablePaperCount(props.bundle));
  const nextState = createMemo(() => workflowNextState(paperCount(), props.pdfTask, props.selectedDocumentId));
  const completedFlightStations = createMemo(() => flightRecord().filter((entry) => entry.state === "complete").length);
  const quickNextLabel = () => ({
    "align-pdf-context": x("对齐论文与 PDF", "align paper and PDF"), "select-attached-paper": x("选择绑定论文", "select attached paper"),
    "source-map": x("登记来源定位", "register source map"), "evidence-review": x("审核 EvidenceCard", "review EvidenceCard"),
    "citation-map": x("构建引文图", "build citation map"), "standalone-markdown": x("核对私有 Markdown", "review private Markdown"),
    "literature-map": x("选择待核对文献", "choose a paper"), "pdf-parsing": x("等待私有解析", "wait for private parse"),
    "pdf-failed": x("更换授权 PDF", "replace authorised PDF"), waiting: x("等待任务工件", "await task artifact"),
  }[nextState()]);
  const previewMetric = (zh: string, en: string) => props.readOnlyPreview ? x(`演示 · ${zh}`, `DEMO · ${en}`) : x(zh, en);
  const comparison = createMemo(() => researchExtensionReadiness(props.bundle));
  const counterevidence = createMemo(() => counterevidenceReadiness(props.bundle));
  const counterevidenceNeeded = createMemo(() => (comparison().reason === "conditions" || comparison().ready) && !counterevidence().ready);
  const inspectFleet = (fleet: FleetRecord) => {
    const activeElement = document.activeElement;
    drawerReturnFocus = activeElement instanceof HTMLElement ? activeElement : null;
    setSelectedFleet(fleet);
    setSelectedShip(fleet.ships.find((ship) => ship.id === fleet.flagshipId) ?? fleet.ships[0] ?? null);
  };
  const closeFleetInspector = () => {
    setSelectedFleet(null);
    setSelectedShip(null);
    const returnFocus = drawerReturnFocus;
    drawerReturnFocus = null;
    queueMicrotask(() => {
      if (returnFocus?.isConnected) returnFocus.focus();
    });
  };
  createEffect(() => {
    if (!selectedFleet()) return;
    const inspector = fleetInspector;
    const closeButton = inspector?.querySelector<HTMLButtonElement>("button");
    const keepFocusInDrawer = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        closeFleetInspector();
        return;
      }
      if (event.key !== "Tab" || !inspector) return;
      const focusable = Array.from(inspector.querySelectorAll<HTMLElement>("a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex='-1'])"))
        .filter((element) => !element.hasAttribute("hidden") && element.getAttribute("aria-hidden") !== "true");
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    window.addEventListener("keydown", keepFocusInDrawer);
    queueMicrotask(() => closeButton?.focus());
    onCleanup(() => {
      window.removeEventListener("keydown", keepFocusInDrawer);
    });
  });
  const inputs = () => [props.bundle.mission.material, props.bundle.mission.property, props.bundle.mission.scope];
  const fleetCapacity = (fleet: FleetRecord) => {
    const toolCount = fleet.ships.reduce((total, ship) => total + ship.tools.length, 0);
    return x(`${fleet.ships.length} 型舰船 · ${toolCount} 项工具`, `${fleet.ships.length} ship types · ${toolCount} tools`);
  };
  const outputs = () => [
    props.bundle.stations.length ? x("任务站点工件", "task-station artifact") : x("待建立任务站点", "task station pending"),
    props.bundle.timeline.length ? x("已登记时间线", "registered timeline") : x("待登记时间线", "timeline pending"),
    paperCount() ? x(`${paperCount()} 篇可审查文献`, `${paperCount()} reviewable paper(s)`) : x("待检索或导入文献子图", "literature subgraph pending retrieval or import"),
  ];
  const deploymentManifest = createMemo(() => participants().map((fleet) => {
    const role = fleetMissionRole(fleet, props.bundle);
    return {
      fleet,
      role,
      runtime: fleetRuntimeStatus(fleet, props.bundle),
      outputCount: fleet.bridgeOutputs.length,
    };
  }));
  const deploymentClass = (index: number) => `deployment-ship--${index % 5}`;
  const facilityDeck = createMemo(() => facilityContractDeck(props.bundle.facilities, props.facilityContracts ?? null));
  const facilityCoverage = createMemo(() => facilityContractCoverage(props.bundle.facilities, facilityDeck()));
  const facilityHealth = () => props.facilityCatalogueHealth ?? (props.facilityContracts ? "ready" : "disabled");
  const hasFacilityCatalogue = () => facilityHealth() === "ready" && (props.facilityContracts?.length ?? 0) > 0;
  const hasAssignedFacilities = () => props.bundle.facilities.length > 0;

  return <main class="fleet-command-stage workflow-stage">
    <FleetDecoration kind="workflow" state={fleetVisualState(props.bundle, "workflow")} />
    <header class="stage-header"><div><p class="stage-kicker">COSMATTER / {x("舰桥编排", "BRIDGE ORCHESTRATION")}</p><h1>{x("从任务工件到文献星图", "From mission artifacts to a literature map")}</h1><p>{x("舰队仅标识当前参与单元；所有输出必须经由任务门禁登记。", "Fleets identify participating units only; every output must be registered through the task gate.")}</p></div></header>
    <Show when={props.readOnlyPreview}><ReadOnlyPreviewContext locale={props.locale} onExit={props.onExitPreview} /></Show>
    <nav class="bridge-quick-nav" aria-label={x("舰桥快速导航", "Bridge quick navigation")}>
      <a href="#bridge-flight"><small>01 / {x("任务航线", "MISSION ROUTE")}</small><strong>{previewMetric(`${completedFlightStations()}/${flightRecord().length} 已登记`, `${completedFlightStations()}/${flightRecord().length} recorded`)}</strong><span>{x("工件门禁", "artifact gates")}</span></a>
      <a href="#bridge-fleet"><small>02 / {x("舰队编队", "FLEET FORMATION")}</small><strong>{previewMetric(`${participants().length} 个当前舰位`, `${participants().length} current station(s)`)}</strong><span>{x("职责与交接", "roles and handoffs")}</span></a>
      <a href="#bridge-private-review"><small>03 / {x("私有全文", "PRIVATE FULL TEXT")}</small><strong>{props.pdfTask ? `${props.pdfTask.state} / ${props.pdfTask.doi_status}` : x("未入港", "not docked")}</strong><span>{x("仅本机工件", "local artifact only")}</span></a>
      <a href="#bridge-next"><small>04 / {x("下一门禁", "NEXT GATE")}</small><strong>{quickNextLabel()}</strong><span>{x("受控跳转", "controlled handoff")}</span></a>
    </nav>
    <Show when={props.automaticMissionPending || props.automaticCancellationRequested}><section class="automatic-mission-pending" aria-live="polite"><small>{props.automaticCancellationRequested ? x("取消请求已登记", "CANCELLATION REQUEST RECORDED") : x("受控检索请求进行中", "CONTROLLED RETRIEVAL REQUEST IN PROGRESS")}</small><strong>{props.automaticCancellationRequested ? x("本机已阻止后续提供方调用", "The local service blocked later provider calls") : x("等待本机服务登记任务", "Waiting for the local service to register the task")}</strong><p>{props.automaticCancellationRequested ? x("取消标记是持久化的。已在途的 HTTP 请求不能被强制终止，但完成后不会写入候选、来源定位或 EvidenceCard。", "The cancellation marker is durable. An HTTP request already in flight cannot be force-stopped, but on completion it cannot write candidates, source locations, or EvidenceCards.") : x("当前只保留空任务壳，未返回任何论文、来源定位或 EvidenceCard。任务号返回前无法发起取消；若你改动任务边界，迟到结果会被忽略。", "Only an empty mission shell is present. No paper, source locator, or EvidenceCard has returned. The task cannot be cancelled until its local run ID is returned; if you change the mission boundary, late results will be ignored.")}</p><Show when={props.onCancelAutomaticMission}><button type="button" class="rail-recovery-action" onClick={() => void props.onCancelAutomaticMission?.()}>{x("取消本次自动检索", "Cancel this automatic retrieval")}</button></Show><Show when={props.automaticAuthorization}>{(authorization) => <p class="automatic-authorization">{x("Harness 已核验：", "Harness verified: ")}<For each={authorization().plugin_authorization_decisions.filter((item) => item.permitted)}>{(item, index) => <>{index() ? " · " : ""}<code>{item.plugin_id}</code></>}</For>{x("。这只授权受控元数据操作，不接受证据或上传全文。", ". This authorizes controlled metadata operations only; it does not accept evidence or upload full text.")}</p>}</Show></section></Show>
    <section class="workflow-artifact-flow" aria-label={x("编排工件流", "Orchestration artifact flow")}>
      <article><small>01 / {x("输入", "INPUT")}</small><h2>{x("任务边界", "Mission boundary")}</h2><For each={inputs()}>{(item) => <span>{item}</span>}</For></article>
      <i aria-hidden="true">→</i>
      <article><small>02 / {x("参与单元", "PARTICIPANTS")}</small><h2>{x("当前舰队", "Active roles")}</h2><For each={participants()}>{(fleet) => <button type="button" class={`state-${fleetRuntimeStatus(fleet, props.bundle)}`} aria-controls="fleet-participant-drawer" aria-expanded={selectedFleet()?.id === fleet.id} onClick={() => inspectFleet(fleet)}>{label(fleet, props.locale)}<small>{fleetStatusLabel(fleetRuntimeStatus(fleet, props.bundle))}</small></button>}</For></article>
      <i aria-hidden="true">→</i>
      <article><small>03 / {x("输出", "OUTPUT")}</small><h2>{x("下游工件", "Downstream artifacts")}</h2><For each={outputs()}>{(item) => <span>{item}</span>}</For></article>
      <i aria-hidden="true">→</i>
      <article><small>04 / {x("门禁", "GATE")}</small><h2>{x("人工确认", "Human confirmation")}</h2><p>{x("本页不会重复启动检索、全文解析或证据接受；它只呈现已登记的任务状态。", "This page does not restart retrieval, full-text parsing, or evidence acceptance; it only presents registered task state.")}</p></article>
    </section>
    <Show when={facilityHealth() === "loading"}><section class="facility-contract-status" aria-live="polite" aria-label={x("设施契约目录状态", "Facility contract catalogue status")}><small>{x("当前设施契约 / 只读", "CURRENT FACILITY CONTRACTS / READ ONLY")}</small><h2>{x("正在加载本地设施目录", "Loading local facility catalogue")}</h2><p>{x("目录仅描述固定契约；加载期间不会把设施显示为已执行，也不会发起任何工具调用。", "The catalogue describes fixed contracts only. While loading, no facility is shown as executed and no tool call is started.")}</p></section></Show>
    <Show when={facilityHealth() === "unavailable"}><section class="facility-contract-status state-unavailable" aria-live="polite" aria-label={x("设施契约目录不可用", "Facility contract catalogue unavailable")}><small>{x("当前设施契约 / 只读", "CURRENT FACILITY CONTRACTS / READ ONLY")}</small><h2>{x("本地设施目录当前不可用", "Local facility catalogue is currently unavailable")}</h2><p>{x("为避免把缺失目录误读为能力，当前不显示设施契约，也不影响任务门禁。可重试本机只读目录请求。", "To avoid treating a missing catalogue as capability, facility contracts are not displayed and task gates are unchanged. You may retry the local read-only catalogue request.")}</p><Show when={props.onRefreshFacilityContracts}><button type="button" onClick={() => props.onRefreshFacilityContracts?.()}>{x("重试加载目录", "Retry catalogue load")}</button></Show></section></Show>
    <Show when={facilityDeck().length}><section class="facility-contract-deck" aria-label={x("当前设施契约", "Current facility contracts")}>
      <header><div><small>{x("当前设施契约 / 只读", "CURRENT FACILITY CONTRACTS / READ ONLY")}</small><h2>{x("输入、输出与失败边界", "Inputs, outputs, and failure boundaries")}</h2></div><span>{x(`已映射 ${facilityCoverage().mappedCount}/${facilityCoverage().assignedCount} 项 · ${facilityCoverage().humanReviewCount} 项需人工复核`, `${facilityCoverage().mappedCount}/${facilityCoverage().assignedCount} mapped · ${facilityCoverage().humanReviewCount} require human review`)}<br />{x("静态目录不执行设施", "Static catalogue; no facility execution")}</span></header>
      <div role="list"><For each={facilityDeck()}>{(facility, index) => <article role="listitem"><small>{String(index() + 1).padStart(2, "0")} / {facility.status}</small><strong>{props.locale === "zh" ? facility.labelZh : facility.labelEn}</strong><code>{facility.facilityType}</code><dl><div><dt>{x("输入", "input")}</dt><dd>{facility.inputSchema.join(" · ")}</dd></div><div><dt>{x("输出", "output")}</dt><dd>{facility.outputSchema.join(" · ")}</dd></div><div><dt>{x("失败边界", "failure boundary")}</dt><dd>{facility.failureModes.join(" · ")}</dd></div></dl><em>{facility.humanReviewRequired ? x("需人工复核", "human review required") : x("无额外人工门", "no additional human gate")}</em></article>}</For></div>
      <p>{x("目录只说明当前任务设施可接收或产出的工件类别；它不代表设施已运行，也不会发起检索、解析、模型调用或证据接受。", "The catalogue only states the artifact classes assigned facilities may consume or produce. It does not mean a facility ran and never starts retrieval, parsing, model calls, or evidence acceptance.")}</p>
      <Show when={facilityCoverage().unmappedCount > 0}><p class="facility-contract-warning">{x(`另有 ${facilityCoverage().unmappedCount} 项已登记设施无法与本地静态契约匹配，未显示且不被视为可执行能力。请核对导入工件和目录版本。`, `${facilityCoverage().unmappedCount} additional assigned facility(s) do not match the local static contracts; they are hidden and not treated as executable capability. Check the imported artifact and catalogue version.`)}</p></Show>
    </section></Show>
    <Show when={hasFacilityCatalogue() && !facilityDeck().length}><section class="facility-contract-empty" aria-label={x("当前设施契约状态", "Current facility contract status")}><small>{x("当前设施契约 / 只读", "CURRENT FACILITY CONTRACTS / READ ONLY")}</small><h2>{hasAssignedFacilities() ? x("未显示未映射设施", "Assigned facilities are not mapped for display") : x("当前任务尚未登记设施", "No facility is registered for this task")}</h2><p>{hasAssignedFacilities() ? x("当前任务的设施类型未能匹配本地静态契约，因而不会显示、更不会被当作可执行能力。请检查导入工件与本机契约目录是否属于同一版本。", "The task's facility types do not match the local static contracts, so they are neither displayed nor treated as executable capability. Check that the imported artifact and local catalogue use the same version.") : x("本机静态目录已加载，但当前任务没有登记设施。此空态不表示设施已运行、调用失败或系统自动补全了任何能力。", "The local static catalogue is loaded, but the current task records no facilities. This empty state does not mean a facility ran, a call failed, or the system filled in any capability automatically.")}</p></section></Show>
    <Show when={templateFormation().length}><section class="bridge-template-contract" aria-label={x("BFO 模板编队契约", "BFO template formation contract")}><header><div><small>{x("BFO 本会话模板标签 / 只读", "BFO SESSION TEMPLATE TAG / READ ONLY")}</small><h2>{x("起始页确认的计划舰位", "Planned stations confirmed at launch")}</h2></div><span>{x("仅随当前浏览器任务保留；导入、恢复或更改边界会解除该标签。", "Stored only with this browser task; import, resume, or a boundary change clears this tag.")}</span></header><div role="list"><For each={templateFormation()}>{(station, index) => <article role="listitem" class={`state-${station.routeState}`}><small>{String(index() + 1).padStart(2, "0")} / {station.fleetLabel}</small><b>{templateRouteLabel(station.routeState)}</b><strong>{station.role}</strong><span>{x("输入", "INPUT")}: {station.intake}</span><span>{x("输出", "OUTPUT")}: {station.artifact}</span><em>{x("门禁", "GATE")}: {station.acceptanceGate}</em></article>}</For></div><p>{x("状态仅对照当前任务航线：它不表示工具已经执行，也不把计划舰位伪造成运行中的本地站点。", "These states compare only with the current mission route: they do not mean a tool has run or that a planned station is an executing local station.")}</p></section></Show>
    <section id="bridge-flight" class="mission-flight-recorder" aria-label={x("任务飞行记录", "Mission flight recorder")}>
      <header><small>{x("任务飞行记录 / 工件门禁", "MISSION FLIGHT RECORDER / ARTIFACT GATES")}</small><span>{x("每一站只从当前本地任务工件推导；候选、私有全文、事实、证据与 Gap 不会互相越级。", "Every station is derived only from current local task artifacts; candidates, private full text, facts, evidence, and Gaps cannot leapfrog one another.")}</span></header>
      <div class="mission-flight-track"><For each={flightRecord()}>{(entry, index) => { const destination = () => flightDestination(entry); return <button type="button" class={`mission-flight-station state-${entry.state}`} disabled={!destination()} onClick={() => { const view = destination(); if (view) props.onNavigate(view); }}><span>{String(index() + 1).padStart(2, "0")}</span><i aria-hidden="true" /><small>{flightLabel(entry)}</small><strong>{props.locale === "zh" ? entry.valueZh : entry.valueEn}</strong><em>{props.locale === "zh" ? entry.detailZh : entry.detailEn}</em><b>{flightStateLabel(entry.state)}{destination() ? " · ↗" : ""}</b></button>; }}</For></div>
      <footer>{x("记录板不执行任务，也不传输全文；它仅显示已经登记的本地状态和当前不可跨越的审核边界。", "The recorder does not execute work or transfer full text; it only displays registered local state and the review boundaries that cannot be crossed.")}</footer>
    </section>
    <section class="mission-event-ledger" aria-label={x("已登记任务事件", "Registered mission events")}>
      <header><small>{x("旗舰事件账本 / 只读", "FLAGSHIP EVENT LEDGER / READ ONLY")}</small><span>{x(`显示最近 ${eventLedger().length}/${props.bundle.timeline.length} 条已登记事件；不把当前状态、目录能力或等待动作伪造成历史记录。`, `Showing the latest ${eventLedger().length}/${props.bundle.timeline.length} recorded event(s); current state, catalogue capability, and waiting work are never fabricated as history.`)}</span></header>
      <Show when={eventLedger().length} fallback={<p class="mission-event-empty">{x("当前本地任务没有可投影的时间线事件。任务继续由上方飞行记录和下一步门禁说明。", "This local mission has no timeline event to project. The flight recorder and next-step gate above remain the source of current status.")}</p>}><ol><For each={eventLedger()}>{(event) => <li class={`state-${event.stateClass}`}><span>{String(event.ordinal).padStart(2, "0")}</span><strong>{event.stationType}</strong><em>{event.action}</em><small>{eventStateLabel(event.stateClass)} · {eventTime(event.occurredAt)}</small></li>}</For></ol></Show>
    </section>
    <section id="bridge-fleet" class="fleet-deployment-radar" aria-label={x("战术编队盘", "Tactical fleet deployment")}>
      <header><div><small>{x("战术编队盘", "TACTICAL FLEET DEPLOYMENT")}</small><h2>{x("以旗舰为中心的受控舰位", "Controlled stations around the flagship")}</h2><p>{x("舰位只显示当前任务的已登记参与单元。点击舰位查看职责、允许工件与可用工具；这不会启动子 Agent 或外部调用。", "Stations show only registered participants for this mission. Select one to inspect its role, allowed artifacts, and available tools; this never starts a sub-agent or external call.")}</p></div><span>{previewMetric(`${participants().length} 个参与单元 · ${props.bundle.stations.length} 个任务站点 · ${paperCount()} 篇可审查文献`, `${participants().length} participating unit(s) · ${props.bundle.stations.length} task station(s) · ${paperCount()} reviewable paper(s)`)}</span></header>
      <div class="deployment-plane">
        <i class="deployment-orbit deployment-orbit--outer" aria-hidden="true" /><i class="deployment-orbit deployment-orbit--inner" aria-hidden="true" /><i class="deployment-vector deployment-vector--port" aria-hidden="true" /><i class="deployment-vector deployment-vector--starboard" aria-hidden="true" />
        <div class="deployment-flagship"><small>{x("旗舰节点", "FLAGSHIP NODE")}</small><strong>CosMatter</strong><span>{x("任务包 / 人工门禁 / 工件登记", "task packages / human gates / artifact registry")}</span></div>
        <For each={participants()}>{(fleet, index) => <button type="button" class={`deployment-ship ${deploymentClass(index())} state-${fleetRuntimeStatus(fleet, props.bundle)}`} classList={{ selected: selectedFleet()?.id === fleet.id }} aria-controls="fleet-participant-drawer" aria-expanded={selectedFleet()?.id === fleet.id} onClick={() => inspectFleet(fleet)}><small>{x(`舰位 ${String(index() + 1).padStart(2, "0")}`, `STATION ${String(index() + 1).padStart(2, "0")}`)}</small><strong>{label(fleet, props.locale)}</strong><span>{fleetStatusLabel(fleetRuntimeStatus(fleet, props.bundle))}</span></button>}</For>
      </div>
      <footer><span>{x("星图候选", "MAP CANDIDATES")} <strong>{paperCount()}</strong></span><i aria-hidden="true">→</i><span>{x("来源定位", "SOURCE LOCATORS")} <strong>{props.bundle.sourceMapSummary.segmentCount}</strong></span><i aria-hidden="true">→</i><span>{x("可审计 EvidenceCard", "AUDITABLE EVIDENCECARDS")} <strong>{auditableEvidenceCount()}</strong></span></footer>
      <section class="fleet-handoff-manifest" aria-label={x("舰桥交接清单", "Bridge handoff manifest")}>
        <header><small>{x("舰队交接清单", "FLEET HANDOFF MANIFEST")}</small><span>{x("仅显示当前任务已登记的职责与允许工件；选择一项查看完整能力契约。", "Shows only the current mission's registered role and allowed artifacts; select an item for the full capability contract.")}</span></header>
        <div><For each={deploymentManifest()}>{(entry, index) => <button type="button" class={`handoff-manifest-entry state-${entry.runtime}`} aria-pressed={selectedFleet()?.id === entry.fleet.id} aria-controls="fleet-participant-drawer" aria-expanded={selectedFleet()?.id === entry.fleet.id} onClick={() => inspectFleet(entry.fleet)}><span>{String(index() + 1).padStart(2, "0")}</span><strong>{label(entry.fleet, props.locale)}</strong><em>{props.locale === "zh" ? entry.role.reasonZh : entry.role.reasonEn}</em><small>{x(`${entry.outputCount} 项允许工件`, `${entry.outputCount} allowed artifact(s)`)}</small><i>{props.locale === "zh" ? entry.role.handoffZh : entry.role.handoffEn}</i></button>}</For></div>
      </section>
      <section class="fleet-route-board" aria-label={x("跨阶段舰队编排航线", "Cross-stage fleet orchestration route")}>
        <header><small>{x("跨阶段编队航线", "CROSS-STAGE FORMATION ROUTE")}</small><span>{x("由当前任务状态推导；当前、下一交接、待命与模板能力严格区分。选择舰位可查看其受控能力契约。", "Derived from the current mission state; current, next, standby, and template capabilities remain distinct. Select a station to inspect its controlled capability contract.")}</span></header>
        <div class="fleet-route-track"><For each={orchestration()}>{(entry, index) => <button type="button" class={`fleet-route-station state-${entry.state}`} aria-pressed={selectedFleet()?.id === entry.fleet.id} aria-controls="fleet-participant-drawer" aria-expanded={selectedFleet()?.id === entry.fleet.id} onClick={() => inspectFleet(entry.fleet)}><span>{String(index() + 1).padStart(2, "0")}</span><i aria-hidden="true" /><small>{routeStateLabel(entry.state)}</small><strong>{label(entry.fleet, props.locale)}</strong><em>{props.locale === "zh" ? entry.detailZh : entry.detailEn}</em><b>{x(`${entry.fleet.bridgeOutputs.length} 项可登记工件`, `${entry.fleet.bridgeOutputs.length} registrable artifact(s)`)}</b></button>}</For></div>
        <footer>{x("编队图只解释任务状态与可达交接；不会将目录能力、框架模板或待命舰位显示为正在执行。", "This formation explains registered state and reachable handoffs only; it never presents catalogue capability, templates, or standby fleets as running.")}</footer>
      </section>
    </section>
    <span id="bridge-private-review" class="bridge-anchor" aria-hidden="true" /><Show when={(props.pdfTasks?.length ?? 0) > 1}><section class="pdf-task-selector"><label>{x("当前私有 PDF", "ACTIVE PRIVATE PDF")}<select value={props.pdfTask?.document_id ?? ""} onChange={(event) => { const selected = props.pdfTasks?.find((item) => item.document_id === event.currentTarget.value); if (selected) props.onSelectPdf?.(selected); }}><For each={props.pdfTasks}>{(item) => <option value={item.document_id}>{item.file_name} · {item.state}</option>}</For></select></label><small>{x("每篇 PDF 有独立的解析、来源定位和 DOI 状态；切换只改变当前审阅对象。", "Each PDF has independent parsing, source-location, and DOI state; switching only changes the current review target.")}</small></section></Show><Show when={props.pdfTask}>{(task) => <section class="pdf-task-progress"><div><small>{x("私有 PDF 解析", "PRIVATE PDF PARSING")}</small><h2>{task().file_name}</h2><p>{x(`MinerU 状态：${task().state}；DOI 状态：${task().doi_status}。完整 Markdown 不进入 UI 工件。`, `MinerU state: ${task().state}; DOI state: ${task().doi_status}. Full Markdown never enters UI artifacts.`)}</p><p class={`pdf-task-snapshot state-${pdfFreshness().state}`}><strong>{pdfFreshness().state === "current" ? x("本机状态已确认", "local status confirmed") : pdfFreshness().state === "aging" ? x("本机状态正在老化", "local status is aging") : pdfFreshness().state === "unavailable" ? x("最近状态读取不可用", "latest status read unavailable") : x("等待本机状态确认", "awaiting local status confirmation")}</strong> · {pdfFreshness().state === "current" || pdfFreshness().state === "aging" ? x(`该 PDF 任务最近于 ${new Intl.DateTimeFormat("zh-CN", { hour: "2-digit", minute: "2-digit", second: "2-digit" }).format(new Date(pdfFreshness().observedAt!))} 由本机确认。`, `This PDF task was last confirmed locally at ${new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit" }).format(new Date(pdfFreshness().observedAt!))}.`) : pdfFreshness().state === "unavailable" ? x("保留最后登记的任务记录供审核；请刷新状态，不要重新上传同一文件。", "The last registered task record is retained for review; refresh status instead of re-uploading the same file.") : x("任务提交回执或后续状态读取尚未形成可确认快照；不会据此开放全文或证据操作。", "The submission receipt or a later status read has not formed a confirmable snapshot; no full-text or evidence action is opened from it.")}</p><Show when={task().candidate_document_id}>{(candidateId) => <p class="pdf-linkage">{x(`已关联本任务中人工纳入的候选：${candidateId()}。`, `Linked to the human-included candidate in this task: ${candidateId()}.`)}</p>}</Show><Show when={task().markdown_ready && task().audit_state === "done" && task().source_map_review_status !== "recorded"}><p class="pdf-audit-ready">{task().candidate_document_id ? x(`解析任务已登记到来源定位审计台账（文献：${task().audit_document_id}）。请在本地 Markdown 中人工定位段落、表格或图注后，再创建 Source Map；这一步不会自动接受 EvidenceCard。`, `The completed parse is registered in the source-location audit ledger (paper: ${task().audit_document_id}). Locate paragraphs, tables, or captions in the local Markdown before creating a Source Map; this does not auto-accept an EvidenceCard.`) : x("私有解析台账已完成，但尚未关联到已筛选的候选文献；不能据此创建 EvidenceCard。", "The private parse ledger is complete, but it is not linked to a screened literature candidate; it cannot create an EvidenceCard.")}</p></Show><Show when={task().source_map_review_status === "recorded"}><p class="pdf-audit-ready">{task().candidate_document_id ? x(`已人工登记 ${task().source_map_segment_count} 条来源定位；下一步可登记材料事实或在条件完整时人工接受 EvidenceCard。`, `${task().source_map_segment_count} human-reviewed source location(s) are recorded. Next, register material facts or, when conditions are complete, accept an EvidenceCard by human review.`) : x(`已人工登记 ${task().source_map_segment_count} 条私有来源定位，但该 PDF 未关联本任务候选，不能创建 EvidenceCard。`, `${task().source_map_segment_count} private source location(s) are recorded, but this PDF is not linked to a current-task candidate and cannot create an EvidenceCard.`)}</p></Show></div><div class="pdf-task-actions"><button type="button" disabled={pdfRefreshBusy() || !props.onRefreshPdf} onClick={() => void refreshPdf()}>{pdfRefreshBusy() ? x("刷新中…", "Refreshing…") : x("刷新解析状态", "Refresh parsing status")}</button><Show when={task().markdown_ready && props.markdownUrl}><a href={props.markdownUrl!} download="private-markdown.md">{x("下载私有 Markdown", "Download private Markdown")}</a></Show><button type="button" class="primary-action" disabled={!task().markdown_ready || !["resolved", "human_confirmed"].includes(task().doi_status)} onClick={() => void props.onExpandPdfCitations?.()}>{x("构建双向两层引文图", "Build two-hop citation map")}</button></div><Show when={pdfRefreshError()}>{(message) => <p class="pdf-refresh-error">{message()}</p>}</Show><Show when={task().state === "failed"}><p class="pdf-gate-copy">{x("私有 PDF 解析失败；未生成 Markdown、来源定位或 EvidenceCard。可返回星图重新选择已授权 PDF。", "Private PDF parsing failed. No Markdown, source location, or EvidenceCard was created. Return to the map to choose an authorized PDF again.")}</p></Show><Show when={task().doi_status === "needs_human_doi"}><form class="pdf-doi-confirm" onSubmit={(event) => { event.preventDefault(); void confirmDoi(); }}><p class="pdf-gate-copy">{x("未识别可靠 DOI；请人工核对文献页后补充。该 DOI 仅用于书目导航，不会作为材料事实或 EvidenceCard。", "No reliable DOI was found. Confirm it against the paper record before entering it. The DOI supports bibliography navigation only; it is not a material fact or an EvidenceCard.")}</p><label>{x("人工确认 DOI", "Human-confirmed DOI")}<input value={manualDoi()} onInput={(event) => setManualDoi(event.currentTarget.value)} placeholder="10.xxxx/xxxxx" /></label><button type="submit" disabled={!manualDoi().trim() || doiBusy() || !props.onConfirmPdfDoi}>{doiBusy() ? x("确认中…", "Confirming…") : x("确认 DOI 并解锁引文导航", "Confirm DOI and unlock citation navigation")}</button><Show when={doiError()}>{(message) => <span class="pdf-doi-error">{message()}</span>}</Show></form></Show><Show when={task().doi_status === "human_confirmed"}><p class="pdf-gate-copy">{x("DOI 已由人工确认；可继续构建书目引文图，但引用关系仍不是材料证据。", "The DOI was human-confirmed. You may build a bibliography map; citation relations are still not materials evidence.")}</p></Show></section>}</Show>
    <section id="bridge-next" class="workflow-next"><div><small>{x("当前下一步", "NEXT STEP")}</small><strong>{nextState() === "align-pdf-context" ? x("当前选择的私有 PDF 与会话论文不一致；请先在文献星图对齐两者，再继续任何来源核对。", "The selected private PDF and session paper differ. Align them in the literature map before any source review.") : nextState() === "select-attached-paper" ? x("私有解析已完成；先在文献星图选择已绑定的候选论文，再登记来源定位。", "Private parsing is complete; first select its attached candidate paper in the literature map, then register source locations.") : nextState() === "source-map" ? x("当前已选择绑定论文；进入证据核对，在本机 Markdown 中人工登记来源定位。", "The attached paper is already selected; enter evidence verification and register source locations from local Markdown by human review.") : nextState() === "evidence-review" ? x("当前已选择绑定论文，且来源定位已登记；继续审核材料事实与 EvidenceCard。", "The attached paper is selected and source locations are recorded; continue with material-fact and EvidenceCard review.") : nextState() === "citation-map" ? x("私有 Markdown 与 DOI 已就绪；建立双向两层引文图以继续书目导航。", "Private Markdown and DOI are ready; build the two-hop citation map to continue bibliography navigation.") : nextState() === "standalone-markdown" ? x("私有 Markdown 已可查看；可先核对原文并完成 DOI 书目导航，但它尚未关联筛选候选。", "Private Markdown is available. Inspect it and complete DOI bibliography navigation, but it is not linked to a screened candidate.") : nextState() === "literature-map" ? x("打开文献星图，选择一篇待核对文献。", "Open the literature map and select a paper to verify.") : nextState() === "pdf-parsing" ? x("私有 PDF 正在解析；刷新状态后再查看 Markdown、DOI 与书目导航。", "The private PDF is being parsed. Refresh its status before using Markdown, DOI, or bibliography navigation.") : x("等待受控检索或导入可审查文献子图。", "Wait for controlled retrieval or import of a reviewable literature subgraph.")}</strong><Show when={nextState() === "align-pdf-context"}><p>{x(`当前会话论文为 ${props.selectedDocumentId ?? "未选择"}，而私有 PDF 关联 ${props.pdfTask?.candidate_document_id ?? "未关联候选"}。切换 PDF 不会重写会话论文；请在星图显式选择需要继续的论文。`, `The session paper is ${props.selectedDocumentId ?? "not selected"}, while this private PDF is attached to ${props.pdfTask?.candidate_document_id ?? "no candidate"}. Switching PDFs never rewrites the session paper; explicitly choose the paper to continue in the map.`)}</p></Show><Show when={nextState() === "citation-map"}><p>{x("此引文图只扩展公开书目信息；它不会创建材料事实、Source Map 或 EvidenceCard。", "This citation map expands public bibliographic metadata only; it does not create material facts, Source Maps, or EvidenceCards.")}</p></Show><Show when={nextState() === "standalone-markdown"}><p>{x("该支线只提供私有全文核对与引文导航；未经过当前任务候选筛选，不能登记 Source Map 或接受 EvidenceCard。", "This branch supports private full-text inspection and citation navigation only. Without current-task candidate screening, it cannot register a Source Map or accept an EvidenceCard.")}</p></Show><Show when={nextState() === "pdf-parsing"}><p>{x("当前没有可审查论文工件；舰桥不会把任务标记或演示数据误作检索结果。", "No reviewable paper artifact is available; the bridge will not mistake a mission marker or demo data for a retrieval result.")}</p></Show><Show when={nextState() === "pdf-failed"}><p>{x("失败原因显示在上方解析状态中；不会删除候选筛选决定、已有图谱或审计记录。", "The failure reason appears in the parsing status above; candidate-screening decisions, the graph, and audit records are retained.")}</p></Show><Show when={nextState() === "waiting"}><p>{props.automaticMissionPending ? x("任务请求仍在登记中；舰桥不会将等待状态误作检索结果。", "The task request is still being registered; the bridge does not treat waiting as a retrieval result.") : x("当前没有论文工件；自动检索可能未返回候选或全部来源失败。请返回任务定义调整边界，或使用高级控制复现并检查来源。", "No paper artifact is available. Automatic retrieval may have returned no candidates or all sources may have failed. Return to task definition to adjust the boundary, or use advanced control to reproduce and inspect sources.")}</p></Show></div><Show when={nextState() === "standalone-markdown" && props.markdownUrl} fallback={<button type="button" class="primary-action" disabled={nextState() === "pdf-parsing" || Boolean(props.automaticMissionPending) || (nextState() === "citation-map" && !props.onExpandPdfCitations)} onClick={() => nextState() === "citation-map" ? void props.onExpandPdfCitations?.() : props.onNavigate(["source-map", "evidence-review"].includes(nextState()) ? "reader" : nextState() === "waiting" ? "discover" : "graph")}>{nextState() === "citation-map" ? x("构建双向两层引文图", "Build two-hop citation map") : nextState() === "align-pdf-context" ? x("在星图对齐论文与 PDF", "Align paper and PDF in map") : nextState() === "select-attached-paper" ? x("打开星图选择绑定论文", "Open map and select attached paper") : nextState() === "source-map" ? x("进入证据核对登记来源", "Enter evidence verification to register source") : nextState() === "evidence-review" ? x("进入证据核对继续审核", "Enter evidence verification to continue review") : nextState() === "literature-map" ? x("打开文献星图", "Open literature map") : nextState() === "pdf-parsing" ? x("等待解析完成", "Wait for parsing") : nextState() === "pdf-failed" ? x("返回星图重新选择 PDF", "Return to map and choose PDF again") : props.automaticMissionPending ? x("等待任务登记", "Wait for task registration") : x("返回任务定义调整边界", "Return to task definition and adjust boundary")}</button>}>{(url) => <a class="primary-action" href={url()} download="private-markdown.md">{x("查看私有 Markdown", "View private Markdown")}</a>}</Show></section>
    <Show when={counterevidenceNeeded()}>
      <section class="workflow-counterevidence-gate" aria-live="polite">
        <div><small>{x("反例边界门禁", "COUNTEREVIDENCE BOUNDARY")}</small><h2>{x("条件比较尚不能生成", "Condition comparison cannot be generated yet")}</h2><p>{counterevidence().message}</p><span>{x("已执行 / 已批准", "executed / approved")}: {counterevidence().executedQueryCount}/{counterevidence().plannedQueryCount}</span></div>
        <button type="button" class="primary-action" onClick={() => { if (props.onOpenTaskControl) props.onOpenTaskControl(); else props.onNavigate("discover"); }}>{counterevidence().nextAction}</button>
      </section>
    </Show>
    <details class="fleet-catalogue" open={catalogueOpen()} onToggle={(event) => setCatalogueOpen(event.currentTarget.open)}>
      <summary>{x("架构目录", "Architecture catalogue")}</summary>
      <Show when={catalogueOpen()}>
        <div>
          <For each={FLEETS}>{(fleet) => <button type="button" class={`state-${fleetRuntimeStatus(fleet, props.bundle)}`} onClick={() => inspectFleet(fleet)}>
            <strong>{label(fleet, props.locale)}</strong>
            <span>{props.locale === "zh" ? fleet.purposeZh : fleet.purposeEn}</span>
            <em>{fleetStatusLabel(fleetRuntimeStatus(fleet, props.bundle))} · {fleetCapacity(fleet)}</em>
          </button>}</For>
        </div>
      </Show>
    </details>
<Show when={selectedFleet()}>{(fleet) => <aside ref={(element) => { fleetInspector = element; }} id="fleet-participant-drawer" class="artifact-drawer" role="dialog" aria-modal="true" aria-labelledby="fleet-participant-title"><button type="button" onClick={closeFleetInspector} aria-label={x("关闭详情", "Close details")}>×</button><small>{x("参与单元", "PARTICIPANT")}</small><h2 id="fleet-participant-title">{label(fleet(), props.locale)}</h2><p>{props.locale === "zh" ? fleet().purposeZh : fleet().purposeEn}</p><Show when={selectedRole()}>{(role) => <section class="fleet-stage-role"><small>{x("当前阶段职责", "CURRENT STAGE ROLE")}</small><strong>{props.locale === "zh" ? role().reasonZh : role().reasonEn}</strong><dl><div><dt>{x("任务状态", "MISSION STATE")}</dt><dd>{role().missionState}</dd></div><div><dt>{x("编排状态", "ORCHESTRATION STATUS")}</dt><dd>{fleetStatusLabel(fleetRuntimeStatus(fleet(), props.bundle))}</dd></div><div><dt>{x("下一交接", "NEXT HANDOFF")}</dt><dd>{props.locale === "zh" ? role().handoffZh : role().handoffEn}</dd></div></dl><Show when={!role().participates}><p>{x("该舰队不会参与当前阶段，也不会因此启动任何工具或外部操作。", "This fleet does not participate in the current stage and does not start a tool or external action.")}</p></Show></section>}</Show><section><small>{x("允许交接的工件", "REGISTERED OUTPUTS")}</small><For each={fleet().bridgeOutputs}>{(item) => <code>{item}</code>}</For></section><section class="fleet-communication-ledger"><small>{x("旗舰中继账本", "FLAGSHIP-MEDIATED LEDGER")}</small><p>{x("这是注册的通信契约，不是实时消息流或已启动的子 Agent。所有功能舰均经旗舰收发任务包。", "This is a registered communication contract, not a live message stream or launched sub-agent. Every functional ship exchanges task packages through the flagship.")}</p><ol><For each={fleetChannels(fleet())}>{(channel) => { const source = fleet().ships.find((ship) => ship.id === channel.from)!; const target = fleet().ships.find((ship) => ship.id === channel.to)!; return <li><code>{label(source, props.locale)}</code><span>{channel.direction === "in" ? x("状态 + 工件引用 →", "status + artifact reference →") : x("← 已批准任务包", "← approved task package")}</span><code>{label(target, props.locale)}</code></li>; }}</For></ol></section><section class="fleet-ship-deck"><small>{x("舰载处理逻辑", "ONBOARD PROCESSING")}</small><p>{x("选择一艘舰查看其可用工具与单次太空梭任务。能力清单不代表当前调用。", "Select a ship to inspect its available tools and single-use shuttle tasks. Capability listings do not imply a current invocation.")}</p><div><For each={fleet().ships}>{(ship) => <button type="button" classList={{ selected: selectedShip()?.id === ship.id }} onClick={() => setSelectedShip(ship)}><strong>{label(ship, props.locale)}</strong><small>{props.locale === "zh" ? ship.hullZh : ship.hullEn} · {x(`${ship.count} 个舰槽`, `${ship.count} slot(s)`)}</small></button>}</For></div></section><Show when={selectedShip()}>{(ship) => <section class="fleet-ship-inspector"><small>{x("受控处理链", "CONTROLLED PROCESSING CHAIN")}</small><h3>{label(ship(), props.locale)}</h3><p>{props.locale === "zh" ? ship().workZh : ship().workEn}</p><p class="fleet-chain-copy">{x("已批准任务包 → 本舰工具/子 Agent → 旗舰审查 → 已登记的舰桥工件；不允许功能舰之间点对点交接。", "Approved task package → this ship's tools/sub-agents → flagship review → registered bridge artifact; no functional-ship peer-to-peer handoff is allowed.")}</p><ul><For each={ship().tools}>{(tool) => <li><strong>{label(tool, props.locale)}</strong><span>{statusLabel(tool.status, props.locale)}</span><p>{props.locale === "zh" ? tool.detailZh : tool.detailEn}</p></li>}</For></ul><Show when={(ship().shuttles?.length ?? 0) > 0}><div class="fleet-shuttle-list"><small>{x("单次太空梭", "SINGLE-USE SHUTTLES")}</small><For each={ship().shuttles}>{(shuttle) => <p><strong>{label(shuttle, props.locale)}</strong>{x("：", ": ")}{props.locale === "zh" ? shuttle.taskZh : shuttle.taskEn}</p>}</For></div></Show></section>}</Show></aside>}</Show>
    <footer class="stage-note">{x("舰桥只编排任务和工件边界，不代表外部工具已经执行。", "The bridge orchestrates task and artifact boundaries; it does not claim external tools have run.")}</footer>
  </main>;
}




