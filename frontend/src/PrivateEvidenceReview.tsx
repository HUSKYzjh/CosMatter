import { For, Show, createMemo, createSignal } from "solid-js";

import type { EvidenceReviewResult, HumanEvidenceReviewInput, PdfTaskStatus, RecordedSourceMapSegment } from "./localApi";
import { uiLanguage } from "./zh";
import { validateEvidenceDraft } from "./evidenceReviewDraft";

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
  const validationMessage = () => {
    const issue = validation().issue;
    if (!issue) return "";
    return ({
      candidate: tr("当前 PDF 未关联到已人工筛选的候选文献。", "The current PDF is not linked to a human-screened candidate."),
      segment: tr("请选择当前已登记 Source Map 中的来源片段。", "Select a segment from the currently recorded Source Map."),
      claim: tr("请填写可由所选来源片段核对的主张。", "Enter a claim that can be checked against the selected source segment."),
      "conditions-json": tr("条件字段中有无效数值；请检查应变、厚度和温度。", "One of the condition values is invalid; check strain, thickness, and temperature."),
      "conditions-required": tr("请显式填写样品形态、应变、衬底、厚度、温度和方法；未知值不能被自动补写。", "Explicitly provide sample form, strain, substrate, thickness, temperature, and method; unknown values are never filled automatically."),
      confidence: tr("人工置信度必须在 0 到 1 之间。", "Reviewer confidence must be between 0 and 1."),
      confirmation: tr("请确认已人工核对主张、条件与来源片段。", "Confirm that you checked the claim, conditions, and source segment."),
      handler: tr("当前页面未连接本地 EvidenceCard 记录接口。", "This page is not connected to a local EvidenceCard recording endpoint."),
    }[issue]);
  };
  const submit = async () => {
    if (!valid() || !props.onRecord) return;
    setBusy(true);
    setMessage(null);
    try {
      const draft = validation();
      if (!draft.ready || !draft.conditions || draft.confidence === null) throw new Error(validationMessage());
      const result = await props.onRecord({ segment_id: segmentId(), claim: claim().trim(), stance: stance(), conditions: draft.conditions, reviewer_confidence: draft.confidence });
      setMessage(tr(`已接受 EvidenceCard ${result.evidence_id}。它可用于当前任务的后续证据核对；跨文献比较与 Gap 仍需额外工件。`, `EvidenceCard ${result.evidence_id} accepted. It can support the next evidence-review step; cross-paper comparison and Gaps still require additional artifacts.`));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : tr("无法接受 EvidenceCard。", "Unable to accept the EvidenceCard."));
    } finally {
      setBusy(false);
    }
  };

  return <section class="private-evidence-review">
    <header><div><small>{tr("人工 EvidenceCard 审核", "HUMAN EVIDENCECARD REVIEW")}</small><h2>{tr("将已定位片段接受为可审查证据", "Accept a located excerpt as reviewable evidence")}</h2><p>{tr("此操作只适用于已人工纳入并已关联 PDF 的候选文献。服务端从 Source Map 本地解析短引文与定位符；浏览器不提交引文，也不会调用模型。", "This action is only available for a human-included candidate with its PDF attached. The server resolves the excerpt and locator locally from the Source Map; the browser does not submit a quote or call a model.")}</p></div></header>
    <Show when={candidateLinked()} fallback={<p class="empty-copy">{tr("当前私有 PDF 未关联到已筛选的候选文献，因此只能登记 Source Map 和材料事实，不能接受为 EvidenceCard。", "This private PDF is not linked to a screened candidate. You may record a Source Map and material facts, but cannot accept an EvidenceCard.")}</p>}>
      <fieldset class="evidence-review-form"><label>{tr("来源片段", "Source segment")}<select value={segmentId()} onChange={(event) => setSegmentId(event.currentTarget.value)}><For each={props.segments}>{(segment) => <option value={segment.segment_id}>{segment.segment_id} · {segment.locator}</option>}</For></select></label><label>{tr("立场", "Stance")}<select value={stance()} onChange={(event) => setStance(event.currentTarget.value as HumanEvidenceReviewInput["stance"])}><option value="support">{tr("支持", "Supports")}</option><option value="contradict">{tr("矛盾", "Contradicts")}</option><option value="context">{tr("背景", "Context")}</option></select></label><label class="evidence-review-claim">{tr("可核对主张", "Reviewable claim")}<textarea rows="3" value={claim()} onInput={(event) => setClaim(event.currentTarget.value)} maxLength={1800} /></label><fieldset class="evidence-condition-fields"><legend>{tr("可比条件（六项均须人工填写）", "Comparable conditions (all six require human input)")}</legend><label>{tr("样品形态", "Sample form")}<input value={conditions().sample_form} onInput={(event) => updateCondition("sample_form", event.currentTarget.value)} placeholder={tr("如：外延薄膜", "e.g. epitaxial thin film")} /></label><label>{tr("应变（%）", "Strain (%)")}<input type="number" step="any" value={conditions().strain_percent} onInput={(event) => updateCondition("strain_percent", event.currentTarget.value)} /></label><label>{tr("衬底", "Substrate")}<input value={conditions().substrate} onInput={(event) => updateCondition("substrate", event.currentTarget.value)} /></label><label>{tr("厚度（nm）", "Thickness (nm)")}<input type="number" min="0" step="any" value={conditions().thickness_nm} onInput={(event) => updateCondition("thickness_nm", event.currentTarget.value)} /></label><label>{tr("温度（K）", "Temperature (K)")}<input type="number" min="0" step="any" value={conditions().temperature_k} onInput={(event) => updateCondition("temperature_k", event.currentTarget.value)} /></label><label>{tr("方法", "Method")}<input value={conditions().method} onInput={(event) => updateCondition("method", event.currentTarget.value)} placeholder={tr("如：XRD；DFT", "e.g. XRD; DFT")} /></label></fieldset><label>{tr("人工置信度（0–1）", "Reviewer confidence (0–1)")}<input type="number" min="0" max="1" step="0.05" value={confidence()} onInput={(event) => setConfidence(event.currentTarget.value)} /></label></fieldset>
      <Show when={!valid() && validation().issue}><p class="evidence-draft-gate" role="status">{validationMessage()}</p></Show>
      <div class="source-map-controls"><label class="source-map-confirm"><input type="checkbox" checked={confirmed()} onChange={(event) => setConfirmed(event.currentTarget.checked)} />{tr("我已核对该主张、六项条件及所选 Source Map 片段，并同意将其作为本地已接受 EvidenceCard。", "I verified this claim, all six conditions, and the selected Source Map excerpt, and consent to accepting it as a local EvidenceCard.")}</label><button type="button" class="primary-action" disabled={!valid() || busy()} onClick={() => void submit()}>{busy() ? tr("审核中…", "Accepting…") : tr("人工接受 EvidenceCard", "Accept EvidenceCard")}</button></div>
      <Show when={message()}>{(value) => <p class="source-map-message">{value()}</p>}</Show>
    </Show>
  </section>;
}