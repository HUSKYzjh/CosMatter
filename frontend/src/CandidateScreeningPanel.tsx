import { For, Show, createEffect, createMemo, createSignal } from "solid-js";

import type { CandidateScreening, CandidateScreeningCandidate, CandidateScreeningDecision } from "./localApi";
import { isScreeningComplete, recordedIncludedCandidates, screeningDraftForCandidates, screeningSubmission } from "./candidateScreeningDraft";
import { safeOperationFeedback } from "./importFeedback";

type Locale = "zh" | "en";
const copy = (locale: Locale, zh: string, en: string) => locale === "zh" ? zh : en;

const DECISIONS = [
  ["include_for_fulltext", "纳入全文核对", "Include for full-text review"],
  ["exclude", "排除", "Exclude"],
  ["needs_metadata_review", "需补元数据", "Needs metadata review"],
] as const;

const REASONS: Record<string, readonly [string, string, string][]> = {
  include_for_fulltext: [["material_match", "材料匹配", "Material match"], ["property_match", "性质匹配", "Property match"], ["scope_match", "范围匹配", "Scope match"], ["method_match", "方法匹配", "Method match"], ["primary_evidence", "主要证据", "Primary evidence"], ["counterevidence", "反例证据", "Counterevidence"]],
  exclude: [["out_of_scope_material", "材料不符", "Material out of scope"], ["out_of_scope_property", "性质不符", "Property out of scope"], ["review_or_protocol", "综述或方案", "Review or protocol"], ["duplicate_or_version", "重复或版本", "Duplicate or version"], ["not_enough_metadata", "元数据不足", "Insufficient metadata"]],
  needs_metadata_review: [["not_enough_metadata", "元数据不足", "Insufficient metadata"]],
};

export function CandidateScreeningPanel(props: {
  locale: Locale;
  screening: CandidateScreening | null;
  load: () => Promise<void>;
  submit: (decisions: CandidateScreeningDecision[]) => Promise<void>;
  onRequestFulltext?: (candidate: CandidateScreeningCandidate) => void;
  focusDocumentId?: string | null;
  autoOpen?: boolean;
}) {
  const [open, setOpen] = createSignal(false);
  const [draft, setDraft] = createSignal<Record<string, CandidateScreeningDecision>>({});
  const [activeDocumentId, setActiveDocumentId] = createSignal<string | null>(null);
  const [busy, setBusy] = createSignal(false);
  const [error, setError] = createSignal<string | null>(null);
  const t = (zh: string, en: string) => copy(props.locale, zh, en);
  const candidates = createMemo(() => props.screening?.candidates ?? []);
  const complete = createMemo(() => props.screening ? isScreeningComplete(props.screening.candidates, draft()) : false);
  const reviewedCount = createMemo(() => candidates().filter((candidate) => (draft()[candidate.document_id]?.decision ?? "unreviewed") !== "unreviewed").length);
  const includedCount = createMemo(() => Object.values(draft()).filter((item) => item.decision === "include_for_fulltext").length);
  const persistedReview = createMemo(() => props.screening?.trust_status === "human_reviewed_candidate_screening_not_scientific_evidence");
  const recordedIncluded = createMemo(() => recordedIncludedCandidates(props.screening));
  const activeCandidate = createMemo(() => {
    const list = candidates();
    const current = activeDocumentId();
    return list.find((candidate) => candidate.document_id === current)
      ?? list.find((candidate) => (draft()[candidate.document_id]?.decision ?? "unreviewed") === "unreviewed")
      ?? list[0]
      ?? null;
  });
  const activeIndex = createMemo(() => {
    const current = activeCandidate();
    return current ? candidates().findIndex((candidate) => candidate.document_id === current.document_id) : -1;
  });
  const decisionLabel = (decision: string) => {
    if (decision === "include_for_fulltext") return t("已纳入全文核对", "included for full-text review");
    if (decision === "exclude") return t("已排除", "excluded");
    if (decision === "needs_metadata_review") return t("待补元数据", "metadata review");
    return t("待人工筛选", "awaiting human screening");
  };

  createEffect(() => {
    const screening = props.screening;
    if (!screening) {
      setDraft({});
      setActiveDocumentId(null);
      return;
    }
    setDraft(screeningDraftForCandidates(screening));
    setActiveDocumentId((current) => screening.candidates.some((candidate) => candidate.document_id === current)
      ? current
      : screening.candidates.find((candidate) => (screening.decisions.find((decision) => decision.document_id === candidate.document_id)?.decision ?? "unreviewed") === "unreviewed")?.document_id ?? screening.candidates[0]?.document_id ?? null);
  });
  createEffect(() => {
    const focus = props.focusDocumentId;
    if (focus && candidates().some((candidate) => candidate.document_id === focus)) setActiveDocumentId(focus);
  });
  createEffect(() => {
    if (!props.autoOpen && !props.focusDocumentId) return;
    setOpen(true);
    if (!props.screening && !busy()) void request();
  });

  const updateDecision = (documentId: string, decision: string) => {
    const firstReason = REASONS[decision]?.[0]?.[0] ?? "";
    setDraft((current) => ({ ...current, [documentId]: { document_id: documentId, decision, reason_codes: firstReason ? [firstReason] : [] } }));
  };
  const updateReason = (documentId: string, reason: string) => setDraft((current) => ({ ...current, [documentId]: { ...current[documentId], reason_codes: reason ? [reason] : [] } }));
  const moveCandidate = (offset: number) => {
    const list = candidates();
    if (!list.length) return;
    const current = Math.max(0, activeIndex());
    setActiveDocumentId(list[Math.max(0, Math.min(list.length - 1, current + offset))]?.document_id ?? null);
  };
  const request = async () => {
    setBusy(true);
    setError(null);
    try {
      await props.load();
      setOpen(true);
    } catch (cause) {
      setError(safeOperationFeedback(cause, t("无法载入候选筛选清单；当前决定未被修改。", "Unable to load the candidate-screening checklist; current decisions were not changed.")));
    } finally {
      setBusy(false);
    }
  };
  const submit = async () => {
    if (busy() || !props.screening || !complete()) return;
    setBusy(true);
    setError(null);
    try {
      await props.submit(screeningSubmission(props.screening.candidates, draft()));
      setOpen(false);
    } catch (cause) {
      setError(safeOperationFeedback(cause, t("无法提交人工筛选决定；请检查每篇候选的决定与理由。", "Unable to submit human screening decisions. Check the decision and reason for every candidate.")));
    } finally {
      setBusy(false);
    }
  };

  return <section class="candidate-screening" aria-label={t("候选文献人工筛选", "Candidate literature human screening")}>
    <header><div><small>{t("步骤 01.5 / 人工门禁", "STEP 01.5 / HUMAN GATE")}</small><h2>{t("先筛选候选，再申请全文处理", "Screen candidates before requesting full-text work")}</h2><p>{t("候选论文只含书目信息。每篇候选都必须人工决定一次；“纳入”只允许后续受控全文流程，不产生 EvidenceCard。", "Candidate papers contain bibliographic metadata only. Every candidate needs one human decision; inclusion only permits a later controlled full-text flow and never creates an EvidenceCard.")}</p></div><button type="button" aria-expanded={open()} onClick={() => { if (props.screening && !open()) { setOpen(true); return; } void request(); }} disabled={busy()}>{busy() ? t("处理中…", "Working…") : !props.screening ? t("载入筛选清单", "Load screening checklist") : !open() ? persistedReview() ? t("查看或修改人工筛选", "View or revise human screening") : t(`开始人工筛选（${props.screening.candidate_count} 篇）`, `Start human screening (${props.screening.candidate_count})`) : t("刷新筛选清单", "Refresh checklist")}</button></header>
    <Show when={error()}>{(message) => <p class="screening-error">{message()}</p>}</Show>
    <Show when={open() && props.screening && props.screening.candidates.length === 0}><p class="screening-empty">{t("当前受控检索没有返回可供人工筛选的候选；无法申请全文处理。", "The controlled retrieval returned no candidates to screen; full-text intake is unavailable.")}</p></Show>
    <Show when={open() && props.screening}>{(screening) => <div class="screening-list">
      <p>{screening().trust_status === "human_reviewed_candidate_screening_not_scientific_evidence" ? t(`已登记 ${screening().candidate_count} 篇候选论文的人工筛选；修改后需重新提交完整清单。`, `A human screening review for ${screening().candidate_count} candidate paper(s) is recorded. Submit the complete checklist again after edits.`) : t(`本次必须审阅 ${screening().candidate_count} 篇候选论文。未完成时不会写入工件。`, `${screening().candidate_count} candidate paper(s) must be reviewed. Nothing is written until the checklist is complete.`)}</p>
      <section class="screening-progress" aria-live="polite"><div><small>{t("人工筛选进度", "HUMAN SCREENING PROGRESS")}</small><strong>{t(`已审 ${reviewedCount()} / ${candidates().length}`, `Reviewed ${reviewedCount()} / ${candidates().length}`)}</strong><span>{complete() ? t("决定与理由已完整，可提交审计记录。", "Every decision and reason is complete; the audit record can be submitted.") : t(`尚余 ${Math.max(0, candidates().length - reviewedCount())} 篇待审。`, `${Math.max(0, candidates().length - reviewedCount())} paper(s) remain.`)}</span></div><progress max={candidates().length || 1} value={reviewedCount()} aria-label={t("候选筛选完成进度", "Candidate screening completion progress")} /></section>
      <nav class="screening-contact-strip" aria-label={t("候选编队队列", "Candidate formation queue")}><For each={candidates()}>{(item, index) => { const itemDecision = () => draft()[item.document_id]?.decision ?? "unreviewed"; return <button type="button" class={`screening-contact state-${itemDecision()}`} classList={{ active: activeCandidate()?.document_id === item.document_id }} aria-pressed={activeCandidate()?.document_id === item.document_id} onClick={() => setActiveDocumentId(item.document_id)}><small>{String(index() + 1).padStart(2, "0")}</small><strong>{item.title}</strong><span>{decisionLabel(itemDecision())}</span></button>; }}</For></nav>
      <Show when={activeCandidate()}>{(candidate) => {
        const decision = () => draft()[candidate().document_id] ?? { document_id: candidate().document_id, decision: "unreviewed", reason_codes: [] };
        return <article class="screening-queue-card" classList={{ focused: candidate().document_id === props.focusDocumentId }}>
          <header><div><small>{t("当前候选", "CURRENT CANDIDATE")} · {activeIndex() + 1} / {candidates().length}</small><strong>{candidate().title}</strong><span>{candidate().source}{candidate().publication_year ? ` · ${candidate().publication_year}` : ""}</span></div><nav aria-label={t("候选队列导航", "Candidate queue navigation")}><button type="button" onClick={() => moveCandidate(-1)} disabled={activeIndex() <= 0}>{t("上一篇", "Previous")}</button><button type="button" onClick={() => moveCandidate(1)} disabled={activeIndex() >= candidates().length - 1}>{t("下一篇", "Next")}</button></nav></header>
          <div class="screening-decision-fields"><label>{t("决定", "Decision")}<select value={decision().decision} onChange={(event) => updateDecision(candidate().document_id, event.currentTarget.value)}><option value="unreviewed">{t("请选择", "Select")}</option><For each={DECISIONS}>{([value, zh, en]) => <option value={value}>{t(zh, en)}</option>}</For></select></label><Show when={decision().decision !== "unreviewed"}><label>{t("理由", "Reason")}<select value={decision().reason_codes[0] ?? ""} onChange={(event) => updateReason(candidate().document_id, event.currentTarget.value)}><For each={REASONS[decision().decision] ?? []}>{([value, zh, en]) => <option value={value}>{t(zh, en)}</option>}</For></select></label></Show></div>
        </article>;
      }}</Show>
      <footer><span>{complete() ? t(`筛选完整：${includedCount()} 篇已纳入后续受控全文流程；系统不会自动下载或解析全文。`, `Checklist complete: ${includedCount()} paper(s) are included for a later controlled full-text workflow; no full text is downloaded or parsed automatically.`) : t("请按队列为每篇候选填写决定与理由；可随时回看已审条目。", "Use the queue to record a decision and reason for every candidate; reviewed items remain editable.")}</span><button type="button" class="primary-action" disabled={!complete() || busy()} onClick={() => void submit()}>{t("提交人工筛选决定", "Submit human screening decisions")}</button></footer>
      <Show when={screening().trust_status === "human_reviewed_candidate_screening_not_scientific_evidence" && recordedIncluded().length > 0 && props.onRequestFulltext}><section class="screening-fulltext-intake"><small>{t("后续受控全文入口", "NEXT CONTROLLED FULL-TEXT STEP")}</small><p>{t("这里只显示已提交并重新载入的“纳入全文核对”决定。浏览器中的未提交修改不能申请 PDF 处理；提交完整清单后会再次核验本任务记录。", "Only persisted, reloaded include-for-full-text decisions appear here. Unsubmitted browser edits cannot request PDF processing; the current task record is checked again after a complete checklist is submitted.")}</p><For each={recordedIncluded()}>{(candidate) => <button type="button" onClick={() => props.onRequestFulltext?.(candidate)}>{t("为此候选选择授权 PDF", "Choose an authorized PDF for this candidate")} · {candidate.title}</button>}</For></section></Show>
    </div>}</Show>
  </section>;
}
