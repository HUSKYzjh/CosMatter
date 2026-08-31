import { For, Show, createMemo, createSignal } from "solid-js";

import { FleetDecoration } from "./FleetDecoration";
import { fleetVisualState } from "./fleetVisualState";
import type { EvidenceCard, ImportedBundle } from "./model";
import { evidenceGate, selectedEvidence, type ResearchSession } from "./researchSession";
import { evidenceForPaper, evidenceMatchesPaper } from "./evidenceLinking";
import { PrivateSourceMapReview } from "./PrivateSourceMapReview";
import { readerSourceIntake } from "./readerSourceIntake";
import { readerSourceAction } from "./readerSourceAction";
import { paperPdfIntake } from "./paperPdfIntake";
import { materialFactsForSelectedPaper } from "./readerMaterialFacts";
import { researchExtensionReadiness } from "./researchExtensionReadiness";
import { ReadOnlyPreviewContext } from "./ReadOnlyPreviewContext";
import type { EvidenceReviewResult, HumanEvidenceReviewInput, HumanMaterialFactInput, PdfTaskStatus, PrivateSourceMapSegment, SourceMapRecordResult } from "./localApi";
import { uiLanguage } from "./zh";

type View = "discover" | "workflow" | "graph" | "reader" | "horizon";
const EN: Record<string, string> = {
  "先从文献星图选择一篇论文。": "Select a paper from the literature map first.",
  "从与当前论文显式关联的已接受 EvidenceCard 中选择一张。": "Select an accepted EvidenceCard explicitly linked to the current paper.",
  "该论文尚无已审核的来源映射与 EvidenceCard 关联。": "This paper has no reviewed source-map link to an EvidenceCard yet.",
  "所选 EvidenceCard 没有与当前论文对应的已审核来源映射。": "The selected EvidenceCard has no reviewed source-map link for the current paper.",
  "所选 EvidenceCard 缺少 document ID 或来源定位。": "The selected EvidenceCard is missing a document ID or source locator.",
  "所选 EvidenceCard 对应文献尚无可审计的来源映射片段。": "The paper for the selected EvidenceCard has no auditable source-map segment yet.",
  "当前已接受 EvidenceCard 尚未全部通过精确来源映射审计。": "Accepted EvidenceCards have not all passed the exact source-map provenance audit yet.",
  "证据核对": "Evidence verification",
  "从文献选择到来源定位": "From paper selection to source location",
  "本页不加载全文或调用模型；仅在已筛选候选、已定位片段与人工确认同时满足时，才可在本机接受 EvidenceCard。": "This page neither loads full text nor calls a model. An EvidenceCard can be accepted locally only after candidate screening, source location, and human confirmation.",
  "证据核对步骤": "Evidence-verification steps",
  "选择文献": "Select paper",
  "尚未选择": "Not selected",
  "登记来源定位": "Record source locations",
  "已存在图谱溯源关联": "A graph provenance link already exists",
  "来源定位已登记，待人工登记材料事实与 EvidenceCard": "Source locations are recorded; material facts and an EvidenceCard await human review",
  "当前授权 PDF 已关联，等待人工登记来源定位": "The authorised PDF is linked and awaits human source-location review",
  "等待与当前论文匹配的授权 PDF 或导入证据": "Awaiting an authorised PDF or imported evidence that matches the current paper",
  "先选择论文": "Select a paper first",
  "选择并核对 EvidenceCard": "Select and verify an EvidenceCard",
  "当前会话可进入研究拓展": "The current session can enter research extension",
  "尚未选择待核对论文": "No paper is selected for verification",
  "先在文献星图选择一篇候选论文；独立 PDF 可用于私有 Markdown 与书目导航，但未与人工筛选候选关联时，不能登记 Source Map 或 EvidenceCard。": "Select a candidate paper in the literature map first. A standalone PDF can support private Markdown and bibliography navigation, but cannot record a Source Map or EvidenceCard unless it is linked to a human-screened candidate.",
  "返回文献星图": "Return to literature map",
  "当前论文": "Current paper",
  "本地工件": "Local artifact",
  "更换论文": "Change paper",
  "步骤 03 / 与当前论文关联的已接受 EvidenceCard": "STEP 03 / Accepted EvidenceCards linked to the current paper",
  "选择待核对证据": "Select evidence to verify",
  "仅显示存在已审核 source_provenance 映射的卡片；本界面不会生成、改写或猜测该关联。": "Only cards with a reviewed source_provenance map are shown. This interface never creates, rewrites, or guesses that link.",
  "当前论文还没有可审计的来源映射与已接受 EvidenceCard。完成上方的来源登记后，或返回星图选择已有溯源关联的论文。": "The current paper has no auditable source map and accepted EvidenceCard yet. Complete source registration above or select a paper with a recorded provenance link in the map.",
  "步骤 03 / 核验已接受 EvidenceCard": "STEP 03 / Verify accepted EvidenceCard",
  "尚未选择关联 EvidenceCard": "No linked EvidenceCard selected",
  "只有与当前论文显式关联的已接受卡片才能显示其短引用、条件字段和定位符。": "Only accepted cards explicitly linked to the current paper can display their short excerpt, conditions, and locator.",
  "核对已导入来源": "Verify imported source",
  "文档 ID": "Document ID",
  "缺失": "Missing",
  "定位符": "Locator",
  "来源与访问策略": "Source and access policy",
  "条件字段": "Condition fields",
  "未提供": "Not provided",
  "该定位来自已导入的审核工件，且图谱已登记其与当前论文的来源关系；页面不显示全文。": "This locator comes from an imported reviewed artifact and the graph records its source link to the current paper; full text is not displayed.",
  "研究拓展门禁": "Research-extension gate",
  "当前会话满足最小来源核对条件。": "The current session meets the minimum source-verification condition.",
  "进入研究拓展": "Enter research extension",
  "浏览器本地复核草稿": "Browser-local review draft",
  "记录不确定性、条件差异或需要人工核对的问题": "Record uncertainty, condition differences, or questions needing human review",
  "此草稿仅存于当前浏览器内存，不是运行工件，也不会发送到外部服务。": "This draft exists only in browser memory. It is not a run artifact and is never sent to an external service.",
  "来源映射与 EvidenceCard 均须显式人工确认；本页不会自动生成主张、接受证据或调用外部服务。": "Source maps and EvidenceCards both require explicit human confirmation. This page never generates claims, accepts evidence automatically, or calls external services.",
};
const tr = (zhText: string, enText?: string) => uiLanguage() === "zh" ? zhText : enText ?? EN[zhText] ?? zhText;

export function PaperReader(props: { bundle: ImportedBundle; session: ResearchSession; pdfTask: PdfTaskStatus | null; screeningAllowsSourceReview: boolean; markdownUrl: string | null; onRecordSourceMap?: (segments: PrivateSourceMapSegment[]) => Promise<SourceMapRecordResult>; onLoadSourceMap?: () => Promise<SourceMapRecordResult>; onRecordMaterialFacts?: (facts: HumanMaterialFactInput[]) => Promise<void>; onRecordEvidence?: (input: HumanEvidenceReviewInput) => Promise<EvidenceReviewResult>; readOnlyPreview?: boolean; onExitPreview?: () => void; onNavigate: (view: View) => void; onSelectEvidence: (evidence: EvidenceCard) => boolean }) {
  const [note, setNote] = createSignal("");
  const selected = createMemo(() => selectedEvidence(props.bundle, props.session));
  const linkedEvidence = createMemo(() => evidenceForPaper(props.bundle, props.session.selectedNode));
  const intake = createMemo(() => readerSourceIntake(props.bundle, props.session, props.pdfTask));
  const currentMaterialFacts = createMemo(() => materialFactsForSelectedPaper(props.bundle, props.session));
  const privatePdfState = createMemo(() => paperPdfIntake(props.pdfTask, props.session.selectedNode).state);
  const sourceAction = createMemo(() => readerSourceAction({ hasLinkedEvidence: intake().hasLinkedEvidence, hasMatchingPrivatePdf: ["source-map", "evidence-review"].includes(privatePdfState()), privatePdfParsing: privatePdfState() === "parsing", privatePdfFailed: privatePdfState() === "failed", hasOtherPaperPdf: Boolean(intake().attachedDocumentId) && !intake().matchingPrivatePdf, screeningAllowsSourceReview: props.screeningAllowsSourceReview }));
  const linkedSelected = createMemo(() => evidenceMatchesPaper(props.bundle, props.session.selectedNode, selected()) ? selected() : null);
  const gate = createMemo(() => evidenceGate(props.bundle, props.session));
  const comparison = createMemo(() => researchExtensionReadiness(props.bundle));
  const reason = createMemo(() => ({ paper: tr("先从文献星图选择一篇论文。"), evidence: linkedEvidence().length ? tr("从与当前论文显式关联的已接受 EvidenceCard 中选择一张。") : tr("该论文尚无已审核的来源映射与 EvidenceCard 关联。"), "source-link": tr("所选 EvidenceCard 没有与当前论文对应的已审核来源映射。"), locator: tr("所选 EvidenceCard 缺少 document ID 或来源定位。"), "source-map": tr("所选 EvidenceCard 对应文献尚无可审计的来源映射片段。"), "provenance-audit": tr("当前已接受 EvidenceCard 尚未全部通过精确来源映射审计。") }[gate().reason ?? "evidence"]));
  const proofChain = createMemo(() => {
    const selectedPaper = props.session.selectedNode;
    const hasSourceAnchor = intake().hasLinkedEvidence || intake().sourceMapRecorded;
    const sourceRoute = sourceAction();
    const sourceTarget: View | null = sourceRoute === "await_private_parsing" ? "workflow" : ["choose_authorized_pdf", "retry_authorized_pdf"].includes(sourceRoute) ? "graph" : null;
    const sourceValue = intake().hasLinkedEvidence ? tr("导入溯源", "imported link") : intake().sourceMapRecorded ? tr("已登记", "recorded") : sourceRoute === "await_private_parsing" ? tr("解析中", "parsing") : sourceRoute === "record_source_locations" ? tr("待定位", "locate") : tr("待接入", "pending");
    const sourceDetail = intake().hasLinkedEvidence ? tr("图谱已登记论文—来源关系", "graph records paper-to-source relation") : intake().sourceMapRecorded ? tr("人工来源定位已登记", "human source locations recorded") : sourceRoute === "await_private_parsing" ? tr("返回舰桥查看私有解析", "return to bridge for private parsing") : sourceRoute === "record_source_locations" ? tr("在本页登记人工来源定位", "record human source locations on this page") : tr("需先在星图完成授权全文路线", "complete authorised full-text route in map first");
    return [
      { id: "paper", label: tr("论文舰位", "PAPER STATION"), value: selectedPaper ? tr("已选择", "selected") : tr("待选择", "pending"), detail: selectedPaper?.label ?? tr("从文献星图选择候选论文", "select a candidate paper in the map"), ready: Boolean(selectedPaper), target: "graph" as View },
      { id: "fulltext", label: tr("授权全文", "AUTHORISED FULL TEXT"), value: props.screeningAllowsSourceReview ? tr("已纳入", "included") : intake().hasLinkedEvidence ? tr("导入工件", "imported") : tr("待人工筛选", "screening pending"), detail: props.screeningAllowsSourceReview ? tr("可走受控私有 PDF 路线", "eligible for controlled private PDF route") : tr("筛选决定不是科学证据", "screening is not scientific evidence"), ready: props.screeningAllowsSourceReview || intake().hasLinkedEvidence, target: props.screeningAllowsSourceReview ? "graph" as View : null },
      { id: "source", label: tr("来源泊位", "SOURCE BERTH"), value: sourceValue, detail: sourceDetail, ready: hasSourceAnchor, target: sourceTarget },
      { id: "evidence", label: tr("EvidenceCard", "EVIDENCECARD"), value: linkedSelected() ? linkedSelected()!.evidenceId : linkedEvidence().length ? tr("待选择", "choose") : tr("待接受", "pending"), detail: linkedSelected() ? `${linkedSelected()!.provenance.documentId} · ${linkedSelected()!.provenance.locator}` : tr("仅显示与当前论文显式关联的已接受卡片", "only accepted cards explicitly linked to this paper appear"), ready: Boolean(linkedSelected()), target: null },
      { id: "horizon", label: tr("研究拓展门", "HORIZON GATE"), value: gate().ready ? tr("可进入", "ready") : tr("未解锁", "locked"), detail: gate().ready ? comparison().ready ? tr("可继续查看跨文献比较边界", "may inspect cross-paper comparison boundary") : tr("来源链已完整；跨文献比较另有门禁", "source chain is complete; cross-paper comparison has a separate gate") : reason(), ready: gate().ready, target: gate().ready ? "horizon" as View : null },
    ];
  });

  return <main class="discovery-stage reader-stage">
    <FleetDecoration kind="reader" state={fleetVisualState(props.bundle, "reader")} />
    <header class="stage-header"><div><p class="stage-kicker">COSMATTER / {tr("证据核对")}</p><h1>{tr("从文献选择到来源定位")}</h1><p>{tr("本页不加载全文或调用模型；仅在已筛选候选、已定位片段与人工确认同时满足时，才可在本机接受 EvidenceCard。")}</p></div></header>
    <Show when={props.readOnlyPreview}><ReadOnlyPreviewContext locale={uiLanguage()} onExit={props.onExitPreview} /></Show>
    <ol class="verification-steps" aria-label={tr("证据核对步骤")}><li classList={{ complete: Boolean(props.session.selectedNode) }}><span>01</span><strong>{tr("选择文献")}</strong><small>{props.session.selectedNode ? props.session.selectedNode.label : tr("尚未选择")}</small></li><li classList={{ complete: intake().sourceMapRecorded || intake().hasLinkedEvidence }}><span>02</span><strong>{tr("登记来源定位")}</strong><small>{intake().hasLinkedEvidence ? tr("已存在图谱溯源关联") : intake().sourceMapRecorded ? tr("来源定位已登记，待人工登记材料事实与 EvidenceCard") : sourceAction() === "await_private_parsing" ? tr("当前授权 PDF 正在私有解析；请在舰桥查看状态", "The authorised PDF is parsing privately; inspect status in the bridge") : sourceAction() === "retry_authorized_pdf" ? tr("当前授权 PDF 解析失败；请返回星图重新选择", "The authorised PDF failed to parse; choose it again in the map") : sourceAction() === "record_source_locations" ? tr("当前授权 PDF 已关联，等待人工登记来源定位") : sourceAction() === "choose_authorized_pdf" ? tr("已纳入全文核对；请在星图选择授权 PDF", "Included for full-text review; choose an authorised PDF in the map") : props.session.selectedNode ? tr("等待与当前论文匹配的授权 PDF 或导入证据") : tr("先选择论文")}</small></li><li classList={{ complete: gate().ready }}><span>03</span><strong>{tr("选择并核对 EvidenceCard")}</strong><small>{gate().ready ? comparison().ready ? tr("当前会话可进入研究拓展") : tr("当前证据链已就绪；跨文献比较另有门禁", "Current evidence chain is ready; cross-paper comparison has a separate gate.") : reason()}</small></li></ol>
    <section class="reader-proof-chain" aria-label={tr("当前论文的证明链", "Proof chain for the current paper")}>
      <header><small>{tr("证明链 / 当前会话", "PROOF CHAIN / CURRENT SESSION")}</small><span>{tr("只投影当前论文与已登记工件；不会把其他文献的 PDF、事实或证据混入本链。", "Projects only the selected paper and registered artifacts; no PDF, fact, or evidence from another paper is mixed into this chain.")}</span></header>
      <div class="reader-proof-track"><For each={proofChain()}>{(station, index) => <button type="button" disabled={!station.target} class={`reader-proof-station ${station.ready ? "ready" : "pending"}`} onClick={() => { if (station.target) props.onNavigate(station.target); }}><span>{String(index() + 1).padStart(2, "0")}</span><i aria-hidden="true" /><small>{station.label}</small><strong>{station.value}</strong><em>{station.detail}</em></button>}</For></div>
    </section>
    <Show when={currentMaterialFacts()}>{(ledger) => <section class="reviewed-fact-ledger"><header><div><small>{tr("当前论文的已登记材料事实", "RECORDED FACTS FOR CURRENT PAPER")}</small><h2>{tr(`当前论文已登记 ${ledger().facts.length} 条人工复核事实`, `${ledger().facts.length} human-reviewed fact(s) are recorded for this paper`)}</h2><p>{tr("以下是绑定当前论文来源定位的结构化观察，尚未成为 EvidenceCard 或跨文献结论。", "These are structured observations bound to locators for the current paper; they are not EvidenceCards or cross-paper conclusions.")}</p></div><span>{ledger().trustStatus}</span></header><dl><For each={ledger().facts}>{(fact) => <div><dt>{fact.category} · {fact.name}</dt><dd>{fact.value === null ? tr("未提供数值", "no reported value") : String(fact.value)}{fact.unit ? ` ${fact.unit}` : ""} <small>{fact.locator}</small></dd></div>}</For></dl></section>}</Show>
    <Show when={props.session.selectedNode} fallback={<section class="reader-empty"><h2>{tr("尚未选择待核对论文")}</h2><p>{tr("先在文献星图选择一篇候选论文；独立 PDF 可用于私有 Markdown 与书目导航，但未与人工筛选候选关联时，不能登记 Source Map 或 EvidenceCard。")}</p><button type="button" class="primary-action" onClick={() => props.onNavigate("graph")}>{tr("返回文献星图")}</button></section>}>
      <section class="reader-selection"><div><small>{tr("当前论文")}</small><strong>{props.session.selectedNode!.label}</strong><span>{props.session.selectedNode!.source ?? tr("本地工件")}</span></div><button type="button" onClick={() => props.onNavigate("graph")}>{tr("更换论文")}</button></section>
      <Show when={props.bundle.materialFacts && !currentMaterialFacts()}><section class="reader-intake-note"><small>{tr("其他文献的事实已隐藏", "FACTS FOR ANOTHER PAPER HIDDEN")}</small><p>{tr("本任务存在与当前论文不匹配的已登记材料事实；为避免跨文献混用，本页不会显示它们。请在星图选择对应论文后再核对。", "This mission has recorded material facts for a paper other than the current selection. They are hidden here to prevent cross-paper mixing; select the matching paper in the map to review them.")}</p><button type="button" onClick={() => props.onNavigate("graph")}>{tr("返回文献星图", "Return to literature map")}</button></section></Show>
      <Show when={sourceAction() === "record_source_locations"}>
        <details class="reader-source-intake" open={!intake().hasLinkedEvidence}>
          <summary>{tr("步骤 02 / 从当前授权 PDF 登记来源、材料事实与 EvidenceCard", "STEP 02 / Register source, material facts, and EvidenceCard from the current authorised PDF")}</summary>
          <PrivateSourceMapReview pdfTask={props.pdfTask} markdownUrl={props.markdownUrl} onRecord={props.onRecordSourceMap} onLoad={props.onLoadSourceMap} onRecordFacts={props.onRecordMaterialFacts} materialFactsRecorded={Boolean(currentMaterialFacts()?.facts.length)} onRecordEvidence={props.onRecordEvidence} />
        </details>
      </Show>
      <Show when={sourceAction() === "await_private_parsing"}>
        <section class="reader-intake-note"><small>{tr("私有解析进行中", "PRIVATE PARSING IN PROGRESS")}</small><p>{tr("当前论文的授权 PDF 已绑定，但 MinerU 私有解析尚未完成。解析完成前不会显示 Markdown、登记来源定位或接受 EvidenceCard。", "An authorised PDF is bound to this paper, but private MinerU parsing is not finished. Markdown, source locations, and EvidenceCard acceptance stay unavailable until it completes.")}</p><button type="button" onClick={() => props.onNavigate("workflow")}>{tr("返回舰桥查看解析状态", "Return to bridge for parsing status")}</button></section>
      </Show>
      <Show when={sourceAction() === "retry_authorized_pdf"}>
        <section class="reader-intake-note"><small>{tr("私有解析失败", "PRIVATE PARSING FAILED")}</small><p>{tr("当前论文此前绑定的授权 PDF 未能完成私有解析。该失败不构成来源定位或证据；请返回星图重新选择你有权处理的 PDF。", "The authorised PDF previously bound to this paper did not finish private parsing. This failure is not a source location or evidence; return to the map and choose a PDF you are allowed to process again.")}</p><button type="button" onClick={() => props.onNavigate("graph")}>{tr("返回星图重新选择授权 PDF", "Return to map and choose authorised PDF again")}</button></section>
      </Show>      <Show when={intake().attachedDocumentId && !intake().matchingPrivatePdf}>
        <section class="reader-intake-note"><small>{tr("来源定位尚未对齐", "SOURCE INTAKE NOT ALIGNED")}</small><p>{tr(`当前私有 PDF 只关联候选 ${intake().attachedDocumentId}，而非当前论文 ${intake().selectedDocumentId ?? "未知"}。请返回星图选择该候选，或为当前论文完成筛选后再附加授权 PDF。`, `The current private PDF is attached only to candidate ${intake().attachedDocumentId}, not the selected paper ${intake().selectedDocumentId ?? "unknown"}. Select that candidate in the map, or screen the current paper before attaching an authorised PDF.`)}</p><button type="button" onClick={() => props.onNavigate("graph")}>{tr("返回文献星图对齐论文", "Return to map and align paper")}</button></section>
      </Show>
      <Show when={!intake().matchingPrivatePdf && !intake().attachedDocumentId && !intake().hasLinkedEvidence}>
        <section class="reader-intake-note"><small>{tr("尚缺授权全文工件", "AUTHORISED FULL TEXT PENDING")}</small><p>{sourceAction() === "choose_authorized_pdf" ? tr("当前论文已被人工纳入全文核对，但尚未绑定对应的授权 PDF。请返回星图选择你有权处理的 PDF；未完成来源定位前不会建立 EvidenceCard。", "This paper is already human-included for full-text review but has no matching authorised PDF. Return to the map and choose a PDF you are allowed to process; no EvidenceCard is created before source location.") : tr("当前论文还没有与人工筛选结果匹配的私有 PDF，也没有已导入的溯源证据。请先在星图完成候选筛选，再选择有权处理的 PDF。", "The selected paper has neither a private PDF matched to a human screening decision nor imported provenance-linked evidence. Complete candidate screening in the map, then choose a PDF you are authorised to process.")}</p><button type="button" onClick={() => props.onNavigate("graph")}>{sourceAction() === "choose_authorized_pdf" ? tr("返回星图选择授权 PDF", "Return to map and choose authorised PDF") : tr("返回星图进行候选筛选", "Return to map for candidate screening")}</button></section>
      </Show>
      <Show when={linkedEvidence().length} fallback={<section class="reader-evidence-pending"><small>{tr("待接受 EvidenceCard", "EVIDENCECARD PENDING")}</small><strong>{tr("先完成当前论文的来源定位与人工审核", "Complete source location and human review for the current paper first")}</strong><p>{tr("本页暂不显示空的证据队列或核对面板。完成上方 Source Map、材料事实和条件审核后，已接受 EvidenceCard 会以显式溯源关系回到此处。", "Empty evidence queues and verification panels stay hidden here. After the Source Map, material facts, and condition review are complete, an accepted EvidenceCard returns here through an explicit provenance link.")}</p></section>}>
      <section class="reader-layout">
        <article class="evidence-queue"><small>{tr("步骤 03 / 与当前论文关联的已接受 EvidenceCard")}</small><h2>{tr("选择待核对证据")}</h2><p>{tr("仅显示存在已审核 source_provenance 映射的卡片；本界面不会生成、改写或猜测该关联。")}</p><Show when={linkedEvidence().length} fallback={<p class="empty-copy">{tr("当前论文还没有可审计的来源映射与已接受 EvidenceCard。完成上方的来源登记后，或返回星图选择已有溯源关联的论文。")}</p>}><For each={linkedEvidence()}>{(evidence) => <button type="button" classList={{ selected: linkedSelected()?.evidenceId === evidence.evidenceId }} onClick={() => props.onSelectEvidence(evidence)}><strong>{evidence.evidenceId}</strong><span>{evidence.claim}</span><small>{evidence.provenance.documentId} · {evidence.provenance.locator}</small></button>}</For></Show></article>
        <article class="source-reader"><small>{tr("步骤 03 / 核验已接受 EvidenceCard")}</small><Show when={linkedSelected()} fallback={<><h2>{tr("尚未选择关联 EvidenceCard")}</h2><p>{tr("只有与当前论文显式关联的已接受卡片才能显示其短引用、条件字段和定位符。")}</p></>}>{(evidence) => <><h2>{tr("核对已导入来源")}</h2><dl class="evidence-locator"><div><dt>{tr("文档 ID")}</dt><dd>{evidence().provenance.documentId || tr("缺失")}</dd></div><div><dt>{tr("定位符")}</dt><dd>{evidence().provenance.locator || tr("缺失")}</dd></div><div><dt>{tr("来源与访问策略")}</dt><dd>{evidence().provenance.source} / {evidence().provenance.accessPolicy}</dd></div><div><dt>{tr("条件字段")}</dt><dd>{Object.entries(evidence().conditions).map(([key, value]) => `${key}: ${String(value)}`).join("; ") || tr("未提供")}</dd></div></dl><blockquote>{evidence().quote}</blockquote><p class="evidence-boundary">{tr("该定位来自已导入的审核工件，且图谱已登记其与当前论文的来源关系；页面不显示全文。")}</p></>}</Show></article>
      </section>
      <section class="reader-gate"><div><small>{tr("研究拓展门禁")}</small><strong>{gate().ready ? comparison().ready ? tr("当前会话满足最小来源核对条件，并已具备跨文献比较前置工件。", "The current session meets source-verification requirements and has the prerequisites for an across-paper comparison.") : tr("当前会话满足最小来源核对条件；请查看跨文献比较门禁。", "The current session meets source-verification requirements; inspect the cross-paper comparison gate.") : reason()}</strong></div><button type="button" class="primary-action" disabled={!gate().ready} onClick={() => props.onNavigate("horizon")}>{tr(comparison().ready ? "进入研究拓展" : "查看跨文献比较门禁", comparison().ready ? "Enter research extension" : "View cross-paper comparison gate")}</button></section>
      </Show>
      <details class="reader-notes"><summary>{tr("浏览器本地复核草稿")}</summary><label>{tr("记录不确定性、条件差异或需要人工核对的问题")}<textarea rows="5" value={note()} onInput={(event) => setNote(event.currentTarget.value)} /></label><small>{tr("此草稿仅存于当前浏览器内存，不是运行工件，也不会发送到外部服务。")}</small></details>
    </Show>
    <footer class="stage-note">{tr("来源映射与 EvidenceCard 均须显式人工确认；本页不会自动生成主张、接受证据或调用外部服务。")}</footer>
  </main>;
}


