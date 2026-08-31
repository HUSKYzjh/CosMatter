import { For, Show, createMemo, createSignal } from "solid-js";

import type { EvidenceReviewResult, HumanEvidenceReviewInput, PdfTaskStatus, RecordedSourceMapSegment } from "./localApi";
import { uiLanguage } from "./zh";
import { validateEvidenceDraft } from "./evidenceReviewDraft";
import { safeOperationFeedback } from "./importFeedback";

const tr = (zhText: string, enText: string) => uiLanguage() === "zh" ? zhText : enText;
type ConditionDraft = { sample_form: string; strain_percent: string; substrate: string; thickness_nm: string; temperature_k: string; method: string };
const emptyConditions = (): ConditionDraft => ({ sample_form: "", strain_percent: "", substrate: "", thickness_nm: "", temperature_k: "", method: "" });
const numericOrBlank = (value: string): number | "" => {
  const text = value.trim();
  if (!text) return "";
  const parsed = Number(text);
  return Number.isFinite(parsed) ? parsed : "";
};

export function PrivateEvidenceReview(props: {
  pdfTask: PdfTaskStatus | null;
  segments: RecordedSourceMapSegment[];
  onRecord?: (input: HumanEvidenceReviewInput) => Promise<EvidenceReviewResult>;
}) {
  const [segmentId, setSegmentId] = createSignal(props.segments[0]?.segment_id ?? "");
  const [claim, setClaim] = createSignal("");
  const [stance, setStance] = createSignal<HumanEvidenceReviewInput["stance"]>("support");
  const [conditions, setConditions] = createSignal<ConditionDraft>(emptyConditions());
  const [confidence, setConfidence] = createSignal("0.80");
  const [confirmed, setConfirmed] = createSignal(false);
  const [busy, setBusy] = createSignal(false);
  const [message, setMessage] = createSignal<string | null>(null);
  const candidateLinked = () => Boolean(props.pdfTask?.candidate_document_id);
  const conditionsText = createMemo(() => JSON.stringify({
    sample_form: conditions().sample_form.trim(),
    strain_percent: numericOrBlank(conditions().strain_percent),
    substrate: conditions().substrate.trim(),
    thickness_nm: numericOrBlank(conditions().thickness_nm),
    temperature_k: numericOrBlank(conditions().temperature_k),
    method: conditions().method.trim(),
  }));
  const updateCondition = (key: keyof ConditionDraft, value: string) => setConditions((current) => ({ ...current, [key]: value }));
  const validation = createMemo(() => validateEvidenceDraft({ candidateLinked: candidateLinked(), segmentId: segmentId(), segments: props.segments, claim: claim(), conditionsText: conditionsText(), confidenceText: confidence(), confirmed: confirmed(), hasRecordHandler: Boolean(props.onRecord) }));
  const valid = () => validation().ready;
  const conditionReadiness = createMemo(() => {
    const draft = conditions();
    const numericReady = (value: string) => value.trim() !== "" && Number.isFinite(Number(value));
    return [
      { label: tr("样品形态", "Sample form"), ready: Boolean(draft.sample_form.trim()) },
      { label: tr("应变", "Strain"), ready: numericReady(draft.strain_percent) },
      { label: tr("衬底", "Substrate"), ready: Boolean(draft.substrate.trim()) },
      { label: tr("厚度", "Thickness"), ready: numericReady(draft.thickness_nm) },
      { label: tr("温度", "Temperature"), ready: numericReady(draft.temperature_k) },
      { label: tr("方法", "Method"), ready: Boolean(draft.method.trim()) },
    ];
  });
  const completedConditionCount = createMemo(() => conditionReadiness().filter((item) => item.ready).length);
  const reviewVector = createMemo(() => [
    { id: "candidate", label: tr("候选门禁", "CANDIDATE GATE"), value: candidateLinked() ? tr("已关联", "linked") : tr("未关联", "unlinked"), ready: candidateLinked(), detail: candidateLinked() ? tr("已人工筛选的候选 PDF", "human-screened candidate PDF") : tr("需先完成候选筛选", "candidate screening required") },
    { id: "source", label: tr("来源定位", "SOURCE LOCATOR"), value: segmentId() || tr("未选择", "none"), ready: props.segments.some((segment) => segment.segment_id === segmentId()), detail: segmentId() ? props.segments.find((segment) => segment.segment_id === segmentId())?.locator ?? "" : tr("选择已登记片段", "select a recorded segment") },
    { id: "claim", label: tr("可核对主张", "REVIEWABLE CLAIM"), value: claim().trim() ? `${claim().trim().length}/1800` : tr("待填写", "draft"), ready: Boolean(claim().trim()), detail: tr("仅记录可由所选片段核对的主张", "only a claim checkable against the selected segment") },
    { id: "conditions", label: tr("可比条件", "COMPARABLE CONDITIONS"), value: `${completedConditionCount()}/6`, ready: completedConditionCount() === 6, detail: tr("缺失值不会自动推断", "missing values are never inferred") },
    { id: "confirm", label: tr("人工确认", "HUMAN CONFIRMATION"), value: confirmed() ? tr("已确认", "confirmed") : tr("待确认", "pending"), ready: confirmed(), detail: tr("确认后仍由服务端复核", "server revalidates after confirmation") },
  ]);
  const validationMessage = () => {
    const issue = validation().issue;
    if (!issue) return "";
    return ({
      candidate: tr("当前 PDF 未关联到已人工筛选的候选文献。", "The current PDF is not linked to a human-screened candidate."),
      segment: tr("请选择当前已登记 Source Map 中的来源片段。", "Select a segment from the currently recorded Source Map."),
      claim: tr("请填写可由所选来源片段核对的主张。", "Enter a claim that can be checked against the selected source segment."),
      "conditions-json": tr("条件字段中有无效数值；请检查应变、厚度和温度。", "One of the condition values is invalid; check strain, thickness, and temperature."),
      "conditions-required": tr("请显式填写样品形态、应变、衬底、厚度、温度和方法；未知值不能被自动补写。", "Explicitly provide sample form, strain, substrate, thickness, temperature, and method; unknown values are never filled automatically."),
      "conditions-text": tr("样品形态、衬底和方法必须是简短的文本条件。", "Sample form, substrate, and method must be short text conditions."),
      "conditions-range": tr("应变、厚度和温度必须是有限数值；厚度和温度不能为负值。", "Strain, thickness, and temperature must be finite numbers; thickness and temperature cannot be negative."),
      confidence: tr("人工置信度必须在 0 到 1 之间。", "Reviewer confidence must be between 0 and 1."),
      confirmation: tr("请确认已人工核对主张、条件与来源片段。", "Confirm that you checked the claim, conditions, and source segment."),
      handler: tr("当前页面未连接本地 EvidenceCard 记录接口。", "This page is not connected to a local EvidenceCard recording endpoint."),
    }[issue]);
  };
  const submit = async () => {
    if (busy() || !valid() || !props.onRecord) return;
    setBusy(true);
    setMessage(null);
    try {
      const draft = validation();
      if (!draft.ready || !draft.conditions || draft.confidence === null) throw new Error(validationMessage());
      const result = await props.onRecord({ segment_id: segmentId(), claim: claim().trim(), stance: stance(), conditions: draft.conditions, reviewer_confidence: draft.confidence });
      setMessage(tr(`已接受 EvidenceCard ${result.evidence_id}。它可用于当前任务的后续证据核对；跨文献比较与 Gap 仍需额外工件。`, `EvidenceCard ${result.evidence_id} accepted. It can support the next evidence-review step; cross-paper comparison and Gaps still require additional artifacts.`));
    } catch (error) {
      setMessage(safeOperationFeedback(error, tr("无法接受 EvidenceCard；请检查来源定位、条件和人工确认。", "Unable to accept the EvidenceCard. Check the source locator, conditions, and human confirmation.")));
    } finally {
      setBusy(false);
    }
  };

  return <section class="private-evidence-review">
    <header><div><small>{tr("人工 EvidenceCard 审核", "HUMAN EVIDENCECARD REVIEW")}</small><h2>{tr("将已定位片段接受为可审查证据", "Accept a located excerpt as reviewable evidence")}</h2><p>{tr("此操作只适用于已人工纳入并已关联 PDF 的候选文献。服务端从 Source Map 本地解析短引文与定位符；浏览器不提交引文，也不会调用模型。", "This action is only available for a human-included candidate with its PDF attached. The server resolves the excerpt and locator locally from the Source Map; the browser does not submit a quote or call a model.")}</p></div></header>
    <Show when={candidateLinked()} fallback={<p class="empty-copy">{tr("当前私有 PDF 未关联到已筛选的候选文献，因此只能登记 Source Map 和材料事实，不能接受为 EvidenceCard。", "This private PDF is not linked to a screened candidate. You may record a Source Map and material facts, but cannot accept an EvidenceCard.")}</p>}>
      <section class="evidence-acceptance-vector" aria-label={tr("EvidenceCard 审核航线", "EvidenceCard review vector")}>
        <header><small>{tr("证据舰位 / 人工门禁", "EVIDENCE STATIONS / HUMAN GATE")}</small><span>{valid() ? tr("草稿预检已通过；提交后仍由服务端复核。", "Draft preflight is ready; the server will revalidate after submission.") : tr("逐项完成后才会解锁本地提交。", "The local submission unlocks only when every station is complete.")}</span></header>
        <div class="evidence-acceptance-track" role="list"><For each={reviewVector()}>{(station, index) => <div role="listitem" class={`acceptance-station ${station.ready ? "ready" : "pending"}`}><span>{String(index() + 1).padStart(2, "0")}</span><i aria-hidden="true" /><small>{station.label}</small><strong>{station.value}</strong><em>{station.detail}</em></div>}</For></div>
      </section>
      <fieldset class="evidence-review-form"><label>{tr("来源片段", "Source segment")}<select value={segmentId()} onChange={(event) => setSegmentId(event.currentTarget.value)}><For each={props.segments}>{(segment) => <option value={segment.segment_id}>{segment.segment_id} · {segment.locator}</option>}</For></select></label><label>{tr("立场", "Stance")}<select value={stance()} onChange={(event) => setStance(event.currentTarget.value as HumanEvidenceReviewInput["stance"])}><option value="support">{tr("支持", "Supports")}</option><option value="contradict">{tr("矛盾", "Contradicts")}</option><option value="context">{tr("背景", "Context")}</option></select></label><label class="evidence-review-claim">{tr("可核对主张", "Reviewable claim")}<textarea rows="3" value={claim()} onInput={(event) => setClaim(event.currentTarget.value)} maxLength={1800} /></label><fieldset class="evidence-condition-fields"><legend>{tr("可比条件（六项均须人工填写）", "Comparable conditions (all six require human input)")}</legend><label>{tr("样品形态", "Sample form")}<input value={conditions().sample_form} onInput={(event) => updateCondition("sample_form", event.currentTarget.value)} placeholder={tr("如：外延薄膜", "e.g. epitaxial thin film")} /></label><label>{tr("应变（%）", "Strain (%)")}<input type="number" step="any" value={conditions().strain_percent} onInput={(event) => updateCondition("strain_percent", event.currentTarget.value)} /></label><label>{tr("衬底", "Substrate")}<input value={conditions().substrate} onInput={(event) => updateCondition("substrate", event.currentTarget.value)} /></label><label>{tr("厚度（nm）", "Thickness (nm)")}<input type="number" min="0" step="any" value={conditions().thickness_nm} onInput={(event) => updateCondition("thickness_nm", event.currentTarget.value)} /></label><label>{tr("温度（K）", "Temperature (K)")}<input type="number" min="0" step="any" value={conditions().temperature_k} onInput={(event) => updateCondition("temperature_k", event.currentTarget.value)} /></label><label>{tr("方法", "Method")}<input value={conditions().method} onInput={(event) => updateCondition("method", event.currentTarget.value)} placeholder={tr("如：XRD；DFT", "e.g. XRD; DFT")} /></label></fieldset><label>{tr("人工置信度（0–1）", "Reviewer confidence (0–1)")}<input type="number" min="0" max="1" step="0.05" value={confidence()} onInput={(event) => setConfidence(event.currentTarget.value)} /></label></fieldset>
      <Show when={!valid() && validation().issue}><p class="evidence-draft-gate" role="status">{validationMessage()}</p></Show>
      <div class="source-map-controls"><label class="source-map-confirm"><input type="checkbox" checked={confirmed()} onChange={(event) => setConfirmed(event.currentTarget.checked)} />{tr("我已核对该主张、六项条件及所选 Source Map 片段，并同意将其作为本地已接受 EvidenceCard。", "I verified this claim, all six conditions, and the selected Source Map excerpt, and consent to accepting it as a local EvidenceCard.")}</label><button type="button" class="primary-action" disabled={!valid() || busy()} onClick={() => void submit()}>{busy() ? tr("审核中…", "Accepting…") : tr("人工接受 EvidenceCard", "Accept EvidenceCard")}</button></div>
      <Show when={message()}>{(value) => <p class="source-map-message">{value()}</p>}</Show>
    </Show>
  </section>;
}
