import { For, Show, createEffect, createSignal } from "solid-js";

import { PrivateMaterialFactReview } from "./PrivateMaterialFactReview";
import { PrivateEvidenceReview } from "./PrivateEvidenceReview";
import { sourceMapTaskKey } from "./readerSourceIntake";
import { shouldAutoLoadRecordedSourceMap } from "./sourceMapLoadRecovery";
import type { EvidenceReviewResult, HumanEvidenceReviewInput, HumanMaterialFactInput, PdfTaskStatus, PrivateSourceMapSegment, SourceMapRecordResult } from "./localApi";
import { uiLanguage } from "./zh";
import { safeOperationFeedback } from "./importFeedback";

type SourceKind = PrivateSourceMapSegment["kind"];
type DraftSegment = PrivateSourceMapSegment;
const tr = (zhText: string, enText: string) => uiLanguage() === "zh" ? zhText : enText;
const emptySegment = (): DraftSegment => ({ locator: "", kind: "paragraph", quote: "" });

export function PrivateSourceMapReview(props: {
  pdfTask: PdfTaskStatus | null;
  markdownUrl: string | null;
  onRecord?: (segments: PrivateSourceMapSegment[]) => Promise<SourceMapRecordResult>;
  onLoad?: () => Promise<SourceMapRecordResult>;
  onRecordFacts?: (facts: HumanMaterialFactInput[]) => Promise<void>;
  materialFactsRecorded?: boolean;
  onRecordEvidence?: (input: HumanEvidenceReviewInput) => Promise<EvidenceReviewResult>;
}) {
  const [segments, setSegments] = createSignal<DraftSegment[]>([emptySegment()]);
  const [recorded, setRecorded] = createSignal<SourceMapRecordResult | null>(null);
  const [confirmed, setConfirmed] = createSignal(false);
  const [busy, setBusy] = createSignal(false);
  const [loadingRecorded, setLoadingRecorded] = createSignal(false);
  const [loadAttemptedFor, setLoadAttemptedFor] = createSignal<string | null>(null);
  const [message, setMessage] = createSignal<string | null>(null);
  let activeTaskKey = sourceMapTaskKey(props.pdfTask);
  const ready = () => Boolean(props.pdfTask?.markdown_ready && props.pdfTask.audit_state === "done" && props.markdownUrl);
  const sourceMapRecorded = () => Boolean(recorded() || props.pdfTask?.source_map_review_status === "recorded");
  const valid = () => segments().length > 0 && segments().every((segment) => segment.locator.trim() && segment.quote.trim()) && confirmed() && Boolean(props.onRecord);
  const completeDraftSegmentCount = () => segments().filter((segment) => Boolean(segment.locator.trim() && segment.quote.trim())).length;
  const recordedSegmentCount = () => recorded()?.segments.length ?? props.pdfTask?.source_map_segment_count ?? 0;
  const sourceMapVector = () => [
    { id: "markdown", label: tr("私有 Markdown", "PRIVATE MARKDOWN"), value: ready() ? tr("已就绪", "ready") : tr("等待解析", "waiting"), ready: ready(), detail: ready() ? tr("仅在本机人工核对", "reviewed locally only") : tr("需等待私有解析完成", "wait for private parsing") },
    { id: "draft", label: tr("来源泊位", "SOURCE BERTHS"), value: sourceMapRecorded() ? `${recordedSegmentCount()}` : `${completeDraftSegmentCount()}/${segments().length}`, ready: sourceMapRecorded() || (segments().length > 0 && completeDraftSegmentCount() === segments().length), detail: sourceMapRecorded() ? tr("已登记来源定位", "registered source locations") : tr("定位符和短引文需逐条核对", "verify locator and short quote for each") },
    { id: "confirm", label: tr("人工确认", "HUMAN CONFIRMATION"), value: sourceMapRecorded() || confirmed() ? tr("已确认", "confirmed") : tr("待确认", "pending"), ready: sourceMapRecorded() || confirmed(), detail: tr("不传输全文，不调用模型", "no full text transfer or model call") },
    { id: "registry", label: tr("审计登记", "AUDIT REGISTRY"), value: sourceMapRecorded() ? tr("已登记", "recorded") : tr("待写入", "pending"), ready: sourceMapRecorded(), detail: sourceMapRecorded() ? tr("下游事实与 EvidenceCard 仍须人工核对", "downstream facts and EvidenceCards still need human review") : tr("完成四站后可写入本地工件", "writes local artifact after all stations") },
  ];
  const update = (index: number, field: keyof DraftSegment, value: string) => setSegments((current) => current.map((segment, itemIndex) => itemIndex === index ? { ...segment, [field]: value } : segment));

  createEffect(() => {
    const nextTaskKey = sourceMapTaskKey(props.pdfTask);
    if (nextTaskKey === activeTaskKey) return;
    activeTaskKey = nextTaskKey;
    setSegments([emptySegment()]);
    setRecorded(null);
    setConfirmed(false);
    setBusy(false);
    setLoadingRecorded(false);
    setLoadAttemptedFor(null);
    setMessage(null);
  });

  const loadRecordedSourceMap = async () => {
    const load = props.onLoad;
    const taskKey = sourceMapTaskKey(props.pdfTask);
    if (!load || !taskKey || !ready() || !sourceMapRecorded() || recorded() || loadingRecorded()) return;
    setLoadAttemptedFor(taskKey);
    setMessage(null);
    setLoadingRecorded(true);
    try {
      const result = await load();
      if (taskKey === sourceMapTaskKey(props.pdfTask)) setRecorded(result);
    } catch (error) {
      if (taskKey === sourceMapTaskKey(props.pdfTask)) setMessage(safeOperationFeedback(error, tr("无法读取已登记的 Source Map；当前输入未被修改。", "Unable to load the recorded Source Map; current input was not changed.")));
    } finally {
      if (taskKey === sourceMapTaskKey(props.pdfTask)) setLoadingRecorded(false);
    }
  };

  createEffect(() => {
    const taskKey = sourceMapTaskKey(props.pdfTask);
    if (!shouldAutoLoadRecordedSourceMap({ taskKey, hasLoader: Boolean(props.onLoad), ready: ready(), sourceMapRecorded: sourceMapRecorded(), hasRecordedSegments: Boolean(recorded()), loading: loadingRecorded(), attemptedFor: loadAttemptedFor() })) return;
    void loadRecordedSourceMap();
  });

  const submit = async () => {
    if (busy() || !valid() || !props.onRecord) return;
    const taskKey = sourceMapTaskKey(props.pdfTask);
    if (!taskKey) return;
    setBusy(true);
    setMessage(null);
    try {
      const result = await props.onRecord(segments().map((segment) => ({ locator: segment.locator.trim(), kind: segment.kind, quote: segment.quote.trim() })));
      if (taskKey !== sourceMapTaskKey(props.pdfTask)) return;
      setRecorded(result);
      setMessage(tr("已登记 Source Map。它是人工核对后的来源定位，不是 EvidenceCard；现在可登记与其绑定的材料事实。", "Source Map recorded. It is human-reviewed provenance, not an EvidenceCard; you may now register material facts bound to it."));
    } catch (error) {
      if (taskKey === sourceMapTaskKey(props.pdfTask)) setMessage(safeOperationFeedback(error, tr("无法登记来源定位；请检查段落范围、短片段和人工确认。", "Unable to record source locations. Check the locator range, short excerpts, and human confirmation.")));
    } finally {
      if (taskKey === sourceMapTaskKey(props.pdfTask)) setBusy(false);
    }
  };

  return <section class="private-source-map-review">
    <header><div><small>{tr("人工来源定位 / HUMAN SOURCE MAP", "HUMAN SOURCE MAP")}</small><h2>{sourceMapRecorded() ? tr("沿已登记定位继续核对", "Continue from recorded source locations") : tr("从私有 Markdown 登记可审计短片段", "Register auditable excerpts from private Markdown")}</h2><p>{sourceMapRecorded() ? tr("已登记的片段不会在此表单中重写。可在下方登记与这些片段绑定的结构化材料事实，或在条件完整时人工接受 EvidenceCard。", "Recorded excerpts are not rewritten in this form. Register structured material facts bound to them below, or accept an EvidenceCard by human review once conditions are complete.") : tr("先下载并在本机核对 MinerU Markdown，再仅复制必要的短引文。服务端确认它位于给定行区间；不传输全文、不调用模型，也不自动创建 EvidenceCard。", "Download and inspect the MinerU Markdown locally, then copy only essential short excerpts. The loopback service validates their line range; it never sends full text, calls a model, or creates an EvidenceCard automatically.")}</p></div><Show when={ready() && props.markdownUrl}>{(url) => <a href={url()} download="private-markdown.md">{tr("下载私有 Markdown", "Download private Markdown")}</a>}</Show></header>
    <Show when={ready()} fallback={<p class="empty-copy">{tr("等待私有解析完成后，才能登记 Source Map。", "Wait for private parsing to finish before recording a Source Map.")}</p>}>
      <section class="source-map-docking-vector" aria-label={tr("Source Map 来源泊位", "Source Map docking stations")}>
        <header><small>{tr("来源泊位 / 人工溯源", "SOURCE BERTHS / HUMAN PROVENANCE")}</small><span>{sourceMapRecorded() ? tr("已登记片段只读展示；后续每一步仍保留独立人工门禁。", "Recorded segments remain read-only; each follow-up retains an independent human gate.") : tr("此处仅登记必要短引文和定位符；每项状态均来自当前表单。", "Only essential short quotes and locators are registered here; every state reflects the active form.")}</span></header>
        <div class="source-map-docking-track" role="list"><For each={sourceMapVector()}>{(station, index) => <div role="listitem" class={`source-docking-station ${station.ready ? "ready" : "pending"}`}><span>{String(index() + 1).padStart(2, "0")}</span><i aria-hidden="true" /><small>{station.label}</small><strong>{station.value}</strong><em>{station.detail}</em></div>}</For></div>
      </section>
      <Show when={!sourceMapRecorded()}><>
        <div class="source-map-instructions"><code>markdown_line:起始行-结束行</code><span>{tr("例如：markdown_line:42-47。每条引文不得超过 500 个字符，最多登记 12 条。", "For example: markdown_line:42-47. Each quote is limited to 500 characters; at most 12 may be recorded.")}</span></div>
        <For each={segments()}>{(segment, index) => <fieldset class="source-map-segment"><legend>{tr(`片段 ${String(index() + 1).padStart(2, "0")}`, `EXCERPT ${String(index() + 1).padStart(2, "0")}`)}</legend><label>{tr("来源定位", "Source locator")}<input value={segment.locator} onInput={(event) => update(index(), "locator", event.currentTarget.value)} placeholder="markdown_line:42-47" /></label><label>{tr("类型", "Kind")}<select value={segment.kind} onChange={(event) => update(index(), "kind", event.currentTarget.value as SourceKind)}><option value="paragraph">{tr("段落", "Paragraph")}</option><option value="table">{tr("表格", "Table")}</option><option value="formula">{tr("公式", "Formula")}</option><option value="figure_caption">{tr("图注", "Figure caption")}</option></select></label><label class="source-map-quote">{tr("人工核对的短引文", "Human-checked short quote")}<textarea rows="3" value={segment.quote} onInput={(event) => update(index(), "quote", event.currentTarget.value)} maxLength={500} /></label><Show when={segments().length > 1}><button type="button" class="quiet-action" onClick={() => setSegments((current) => current.filter((_, itemIndex) => itemIndex !== index()))}>{tr("移除此片段", "Remove excerpt")}</button></Show></fieldset>}</For>
        <div class="source-map-controls"><button type="button" class="quiet-action" disabled={segments().length >= 12} onClick={() => setSegments((current) => [...current, emptySegment()])}>{tr("添加片段", "Add excerpt")}</button><label class="source-map-confirm"><input type="checkbox" checked={confirmed()} onChange={(event) => setConfirmed(event.currentTarget.checked)} />{tr("我已在本地 Markdown 中核对以上定位符和短引文，且同意仅将它们写入本地审计工件。", "I verified these locators and excerpts in local Markdown and consent to writing only them to the local audit artifact.")}</label><button type="button" class="primary-action" disabled={!valid() || busy()} onClick={() => void submit()}>{busy() ? tr("登记中…", "Recording…") : tr("登记人工 Source Map", "Record human Source Map")}</button></div>
      </></Show>
      <Show when={message()}>{(value) => <p class="source-map-message">{value()}</p>}</Show>
      <Show when={sourceMapRecorded()}><section class="source-map-recorded"><small>{tr("已登记来源定位", "RECORDED SOURCE LOCATIONS")}</small><p>{tr(`服务端已确认 ${props.pdfTask?.source_map_segment_count ?? 0} 条来源定位；仅显示定位符和类型，不显示全文或短引文。`, `${props.pdfTask?.source_map_segment_count ?? 0} source locations are confirmed by the service. Only locators and kinds are shown; full text and excerpts stay private.`)}</p><Show when={loadingRecorded()}><p class="empty-copy">{tr("正在读取已登记片段…", "Loading recorded segments…")}</p></Show><Show when={sourceMapRecorded() && !recorded() && !loadingRecorded()}><section class="source-map-recovery"><strong>{tr("已登记的来源定位尚未载入", "Recorded source locations are not loaded")}</strong><p>{tr("在来源定位重新载入前，材料事实与 EvidenceCard 登记保持锁定，避免以不完整工件继续核对。", "Material-fact and EvidenceCard registration stay locked until the recorded source locations are reloaded, preventing review from incomplete artifacts.")}</p><button type="button" class="quiet-action" disabled={!props.onLoad} onClick={() => { setLoadAttemptedFor(null); void loadRecordedSourceMap(); }}>{tr("重新读取已登记定位", "Reload recorded locations")}</button></section></Show><Show when={recorded()}>{(result) => <><dl class="recorded-source-map"><For each={result().segments}>{(segment) => <div><dt>{segment.segment_id}</dt><dd>{segment.kind} · {segment.locator}</dd></div>}</For></dl><section class="source-map-followups" aria-label={tr("后续人工核对步骤", "Follow-up human review steps")}><details class="source-map-followup" open><summary><span>{tr("步骤 02 / 登记结构化材料事实（建议）", "STEP 02 / Register structured material facts (recommended)")}</span><small>{tr("仅登记来源片段明确支持的观察", "Record only observations explicitly supported by source excerpts")}</small></summary><PrivateMaterialFactReview segments={result().segments} onRecord={props.onRecordFacts} /></details><details class="source-map-followup" open={props.materialFactsRecorded}><summary><span>{tr("步骤 03 / 人工接受 EvidenceCard", "STEP 03 / Human acceptance of an EvidenceCard")}</span><small>{props.materialFactsRecorded ? tr("已登记材料事实；可继续核对本条证据", "Material facts are recorded; continue to verify this evidence") : tr("可在核对主张与六项条件后继续；不会推断缺失事实", "Continue only after checking the claim and six conditions; missing facts are never inferred")}</small></summary><PrivateEvidenceReview pdfTask={props.pdfTask} segments={result().segments} onRecord={props.onRecordEvidence} /></details></section></>}</Show></section></Show>
    </Show>
  </section>;
}
