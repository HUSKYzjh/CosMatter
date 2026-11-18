import { For, Show, createEffect, createMemo, createSignal, onCleanup, onMount } from "solid-js";

import type { CandidateScreening, CandidateScreeningDecision } from "./localApi";
import { hasScreeningDecision, isScreeningComplete, sameScreeningDecision, screeningDraftChanges, screeningDraftForCandidates, screeningSubmission, type ScreeningDraft } from "./candidateScreeningDraft";
import { safeOperationFeedback } from "./importFeedback";
import { ActionButton } from "./uiPrimitives";

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

function savedScreeningDecision(value: unknown): value is CandidateScreeningDecision {
  if (!value || typeof value !== "object") return false;
  const { document_id, decision, reason_codes } = value as Record<string, unknown>;
  if (typeof document_id !== "string" || typeof decision !== "string" || !Array.isArray(reason_codes) || reason_codes.length > 6) return false;
  if (decision === "unreviewed") return reason_codes.length === 0;
  return Object.hasOwn(REASONS, decision) && reason_codes.every((code) => REASONS[decision].some(([allowed]) => allowed === code))
    && new Set(reason_codes).size === reason_codes.length;
}

const draftKey = (screening: CandidateScreening) => "cosmatter.screening-draft:v1:" + screening.run_id;
const hasRevision = (screening: CandidateScreening) => typeof screening.checklist_revision === "string" && /^[a-f0-9]{64}$/.test(screening.checklist_revision);

export function CandidateScreeningPanel(props: {
  locale: Locale;
  screening: CandidateScreening | null;
  load: () => Promise<void>;
  submit: (decisions: CandidateScreeningDecision[], revision?: string) => Promise<void>;
  onClose: () => void;
  focusDocumentId?: string | null;
  linkedRevision?: string | null;
}) {
  const [draft, setDraft] = createSignal<ScreeningDraft>({});
  const [activeDocumentId, setActiveDocumentId] = createSignal<string | null>(null);
  const [busy, setBusy] = createSignal(false);
  const [error, setError] = createSignal<string | null>(null);
  const [draftNotice, setDraftNotice] = createSignal<"invalidated" | "storage_unavailable" | null>(null);
  const [linkAcknowledged, setLinkAcknowledged] = createSignal(false);
  let heading!: HTMLHeadingElement;
  let draftRevision: string | undefined;
  const t = (zh: string, en: string) => copy(props.locale, zh, en);
  const candidates = createMemo(() => props.screening?.candidates ?? []);
  const complete = createMemo(() => props.screening ? isScreeningComplete(props.screening.candidates, draft()) : false);
  const pendingCandidates = createMemo(() => candidates().filter((candidate) => !hasScreeningDecision(draft()[candidate.document_id])));
  const reviewedCount = () => candidates().length - pendingCandidates().length;
  const changes = createMemo(() => props.screening ? screeningDraftChanges(props.screening, draft()) : []);
  const editedIds = createMemo(() => new Set(changes().map((decision) => decision.document_id)));
  const includedCount = createMemo(() => Object.values(draft()).filter((item) => item.decision === "include_for_fulltext").length);
  const persistedReview = createMemo(() => props.screening?.trust_status === "human_reviewed_candidate_screening_not_scientific_evidence");
  const linkedRevisionChanged = () => props.linkedRevision !== props.screening?.checklist_revision;
  const activeCandidate = createMemo(() => {
    const list = candidates();
    const current = activeDocumentId();
    return list.find((candidate) => candidate.document_id === current)
      ?? pendingCandidates()[0]
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
    if (!screening) return;
    const revision = hasRevision(screening) ? screening.checklist_revision : undefined;
    const draftIdentity = revision ? draftKey(screening) + ":" + revision : undefined;
    if (draftIdentity && draftIdentity === draftRevision) return;
    draftRevision = draftIdentity;
    const restored = screeningDraftForCandidates(screening);
    if (revision) {
      try {
        const raw = window.sessionStorage.getItem(draftKey(screening));
        if (raw && raw.length <= 500_000) {
          const saved = JSON.parse(raw) as { revision?: string; changes?: unknown };
          const changes = Array.isArray(saved?.changes) && saved.changes.every(savedScreeningDecision) ? saved.changes : [];
          if (saved?.revision !== revision) {
            window.sessionStorage.removeItem(draftKey(screening));
            if (changes.some((item) => !sameScreeningDecision(item, restored[item.document_id]))) setDraftNotice("invalidated");
          } else if (changes.length <= screening.candidate_count) {
            for (const change of changes) {
              if (Object.hasOwn(restored, change.document_id)) restored[change.document_id] = change;
            }
          }
        }
      } catch {
        setDraftNotice("storage_unavailable");
      }
    }
    setDraft(restored);
    setActiveDocumentId((current) => screening.candidates.some((candidate) => candidate.document_id === current)
      ? current
      : screening.candidates.find((candidate) => !hasScreeningDecision(restored[candidate.document_id]))?.document_id ?? screening.candidates[0]?.document_id ?? null);
  });
  createEffect(() => {
    const focus = props.focusDocumentId;
    if (focus && candidates().some((candidate) => candidate.document_id === focus)) setActiveDocumentId(focus);
  });
  onMount(() => {
    if (!props.screening) void request();
    if (props.linkedRevision) {
      const focus = window.requestAnimationFrame(() => heading.focus());
      onCleanup(() => window.cancelAnimationFrame(focus));
    }
  });

  const updateDraft = (decision: CandidateScreeningDecision) => {
    const next = { ...draft(), [decision.document_id]: decision };
    setDraft(next);
    const screening = props.screening;
    if (!screening || !hasRevision(screening)) return;
    const changed = screeningDraftChanges(screening, next);
    try {
      if (changed.length) window.sessionStorage.setItem(draftKey(screening), JSON.stringify({ revision: screening.checklist_revision, changes: changed }));
      else window.sessionStorage.removeItem(draftKey(screening));
      setDraftNotice(null);
    } catch {
      setDraftNotice("storage_unavailable");
    }
  };
  const updateDecision = (documentId: string, decision: string) => updateDraft({ document_id: documentId, decision, reason_codes: [] });
  const updateReason = (documentId: string, reason: string) => updateDraft({ ...draft()[documentId], reason_codes: reason ? [reason] : [] });
  const moveCandidate = (offset: number) => {
    const list = candidates();
    if (!list.length) return;
    const current = Math.max(0, activeIndex());
    setActiveDocumentId(list[Math.max(0, Math.min(list.length - 1, current + offset))]?.document_id ?? null);
  };
  const nextPending = () => {
    const next = pendingCandidates().filter((candidate) => candidate !== activeCandidate());
    return next.find((candidate) => candidates().indexOf(candidate) > activeIndex()) ?? next[0];
  };
  const request = async () => {
    setBusy(true);
    setError(null);
    try {
      await props.load();
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
      await props.submit(screeningSubmission(props.screening.candidates, draft()), props.screening.checklist_revision);
      setLinkAcknowledged(true);
    } catch (cause) {
      setError(safeOperationFeedback(cause, t("无法登记人工筛选。请刷新清单，核对记录后再提交。", "Unable to record screening. Refresh the checklist and verify the record before submitting.")));
    } finally {
      setBusy(false);
    }
  };

  return <section class="candidate-screening" aria-label={t("候选文献人工筛选", "Candidate literature human screening")}>
    <header>
      <h2 ref={heading} tabIndex={props.linkedRevision ? -1 : undefined}>{t("候选文献人工筛选", "Human screening of candidate papers")}</h2>
      <div class="screening-header-actions">
        <ActionButton size="sm" busy={busy()} busyLabel={t("处理中…", "Working…")} onClick={() => void request()}>{t("刷新筛选清单", "Refresh checklist")}</ActionButton>
        <ActionButton size="sm" variant="quiet" disabled={busy()} onClick={() => props.onClose()}>{t("收起筛选", "Hide screening")}</ActionButton>
      </div>
    </header>
    <Show when={props.linkedRevision && props.screening && !linkAcknowledged()}>
      <p class="screening-notice screening-link-notice" classList={{ "revision-changed": linkedRevisionChanged() }} role="status">{linkedRevisionChanged()
        ? t("DSH 链接中的清单已更新，请按当前版本重新核对。", "The linked DSH checklist has changed. Review the current version.")
        : t("已从 DSH 打开同一版本的筛选清单。", "Opened the same checklist revision from DSH.")}</p>
    </Show>
    <Show when={error()}>{(message) => <p class="screening-error" role="alert">{message()}</p>}</Show>
    <Show when={draftNotice()}>{(notice) => <p class="screening-notice" role="status">{notice() === "invalidated"
      ? t("清单或登记记录已更新，请按当前版本重新核对。", "The checklist or recorded review changed. Review the current version before submitting.")
      : t("当前浏览器无法暂存草稿，请在本面板完成筛选。", "This browser could not save the draft. Complete screening in this panel.")}</p>}</Show>
    <Show when={props.screening && props.screening.candidates.length === 0}><p class="screening-empty">{t("当前检索没有返回可筛选的候选。", "This search returned no candidates to screen.")}</p></Show>
    <Show when={props.screening && props.screening.candidates.length > 0}><div class="screening-list">
      <section class="screening-progress" aria-live="polite">
        <div>
          <strong>{t(`已填 ${reviewedCount()} / ${candidates().length}`, `Filled ${reviewedCount()} / ${candidates().length}`)}</strong>
          <span>{t(`已登记 ${persistedReview() ? candidates().length : 0} 篇 · 草稿修改 ${changes().length} 篇`, `Recorded ${persistedReview() ? candidates().length : 0} · Edited locally ${changes().length}`)}</span>
        </div>
        <progress max={candidates().length || 1} value={reviewedCount()} aria-label={t("候选筛选填表进度", "Candidate screening form progress")} />
      </section>
      <nav class="screening-contact-strip" aria-label={t("候选队列", "Candidate queue")}>
        <For each={candidates()}>{(item, index) => {
          const itemDecision = () => draft()[item.document_id]?.decision ?? "unreviewed";
          const caption = () => editedIds().has(item.document_id)
            ? t("草稿 · ", "Draft · ") + (itemDecision() !== "unreviewed" && !hasScreeningDecision(draft()[item.document_id])
              ? t("待填理由", "reason required") : decisionLabel(itemDecision()))
            : decisionLabel(itemDecision());
          return <button type="button" class={`screening-contact state-${itemDecision()}`}
            classList={{ active: activeCandidate()?.document_id === item.document_id }}
            aria-pressed={activeCandidate()?.document_id === item.document_id} onClick={() => setActiveDocumentId(item.document_id)}>
            <small>{String(index() + 1).padStart(2, "0")}</small><strong>{item.title}</strong><span>{caption()}</span>
          </button>;
        }}</For>
      </nav>
      <Show when={activeCandidate()}>{(candidate) => {
        const decision = () => draft()[candidate().document_id] ?? { document_id: candidate().document_id, decision: "unreviewed", reason_codes: [] };
        return <article class="screening-queue-card" classList={{ focused: candidate().document_id === props.focusDocumentId }}>
          <header>
            <div><small>{t("当前候选", "CURRENT CANDIDATE")} · {activeIndex() + 1} / {candidates().length}</small><strong>{candidate().title}</strong><span>{candidate().source}{candidate().publication_year ? ` · ${candidate().publication_year}` : ""}</span></div>
            <nav aria-label={t("候选队列导航", "Candidate queue navigation")}>
              <ActionButton size="sm" onClick={() => moveCandidate(-1)} disabled={activeIndex() <= 0}>{t("上一篇", "Previous")}</ActionButton>
              <ActionButton size="sm" onClick={() => moveCandidate(1)} disabled={activeIndex() >= candidates().length - 1}>{t("下一篇", "Next")}</ActionButton>
              <ActionButton size="sm" onClick={() => setActiveDocumentId(nextPending()?.document_id ?? null)} disabled={!nextPending()}>{t("下一待审", "Next unfinished")}</ActionButton>
            </nav>
          </header>
          <div class="screening-decision-fields">
            <label>{t("决定", "Decision")}<select disabled={busy()} value={decision().decision} onChange={(event) => updateDecision(candidate().document_id, event.currentTarget.value)}><option value="unreviewed">{t("请选择", "Select")}</option><For each={DECISIONS}>{([value, zh, en]) => <option value={value}>{t(zh, en)}</option>}</For></select></label>
            <Show when={decision().decision !== "unreviewed"}>
              <label>{t("理由", "Reason")}<select disabled={busy()} value={decision().reason_codes[0] ?? ""} onChange={(event) => updateReason(candidate().document_id, event.currentTarget.value)}><option value="">{t("请选择理由", "Select reason")}</option><For each={REASONS[decision().decision] ?? []}>{([value, zh, en]) => <option value={value}>{t(zh, en)}</option>}</For></select></label>
            </Show>
          </div>
        </article>;
      }}</Show>
      <footer>
        <span>{!complete() ? t(`还有 ${pendingCandidates().length} 篇需要决定与理由。`, `${pendingCandidates().length} paper(s) still need a decision and reason.`)
          : changes().length ? t(`草稿已填完，纳入 ${includedCount()} 篇。提交后登记完整清单。`, `Draft complete with ${includedCount()} included. Submit to record the checklist.`)
          : t("完整清单已登记。", "The complete checklist is recorded.")}</span>
        <ActionButton variant="primary" busy={busy()} busyLabel={t("处理中…", "Working…")} disabled={!complete() || !changes().length} onClick={() => void submit()}>{t("提交人工筛选决定", "Submit human screening decisions")}</ActionButton>
      </footer>
    </div></Show>
  </section>;
}
