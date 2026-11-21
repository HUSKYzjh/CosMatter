import { For, Show, createEffect, createMemo, createSignal, onCleanup, onMount } from "solid-js";

import type { CandidateScreening, CandidateScreeningDecision } from "./localApi";
import { DshScreeningHandoff } from "./DshRunHandoff";
import { checkpointKey, encodeCheckpoint, hasChecklistRevision, readCheckpoint, type ScreeningCheckpoint } from "./candidateScreeningCheckpoint";
import { hasScreeningDecision, isScreeningComplete, sameScreeningDecision, screeningDraftChanges, screeningDraftForCandidates, screeningSubmission, type ScreeningDraft } from "./candidateScreeningDraft";
import { safeOperationFeedback } from "./importFeedback";
import { ActionButton } from "./uiPrimitives";
import "./screeningReasons.css";

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

export function CandidateScreeningPanel(props: {
  locale: Locale;
  missionId: string;
  screening: CandidateScreening | null;
  load: () => Promise<void>;
  submit: (decisions: CandidateScreeningDecision[], revision?: string) => Promise<void>;
  onClose: () => void;
  focusDocumentId?: string | null;
  linkedRevision?: string | null;
  liveRunId?: string | null;
}) {
  const [draft, setDraft] = createSignal<ScreeningDraft>({});
  const [activeDocumentId, setActiveDocumentId] = createSignal<string | null>(null);
  const [busy, setBusy] = createSignal(false);
  const [error, setError] = createSignal<string | null>(null);
  const [draftNotice, setDraftNotice] = createSignal<"invalidated" | "storage_unavailable" | null>(null);
  const [linkAcknowledged, setLinkAcknowledged] = createSignal(false);
  const [savedProgress, setSavedProgress] = createSignal<ScreeningCheckpoint | null>(null);
  const [progressMessage, setProgressMessage] = createSignal<"saved" | "restored" | "cleared" | "expired" | "unavailable" | "offline" | "refresh" | null>(null);
  let currentTitle: HTMLElement | undefined;
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
  const handoffRevision = createMemo(() => {
    const screening = props.screening;
    return screening && screening.run_id === props.liveRunId && candidates().length > 0 && hasChecklistRevision(screening)
      ? screening.checklist_revision : null;
  });
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
    const revision = hasChecklistRevision(screening) ? screening.checklist_revision : undefined;
    const draftIdentity = revision ? JSON.stringify([screening.run_id, props.missionId, revision, screening.candidates.map(item => item.document_id)]) : undefined;
    if (draftIdentity && draftIdentity === draftRevision) return;
    draftRevision = draftIdentity;
    const restored = screeningDraftForCandidates(screening);
    if (revision) {
      try {
        const raw = window.sessionStorage.getItem(draftKey(screening));
        if (raw && raw.length <= 500_000) {
          const saved = JSON.parse(raw) as { version?: number; revision?: string; changes?: unknown };
          const changes = Array.isArray(saved?.changes) && saved.changes.every(savedScreeningDecision) ? saved.changes : [];
          // Older tab drafts used the server revision only. Current drafts also bind the mission and candidate IDs.
          if (saved?.revision !== revision || (saved.version !== undefined && !readCheckpoint(raw, screening, props.missionId, savedScreeningDecision))) {
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

  const updateDraft = (next: ScreeningDraft) => {
    setDraft(next);
    const screening = props.screening;
    if (!screening || !hasChecklistRevision(screening)) return;
    const changed = screeningDraftChanges(screening, next);
    try {
      const current = activeCandidate()?.document_id;
      if (changed.length && current) window.sessionStorage.setItem(draftKey(screening), encodeCheckpoint(screening, props.missionId, current, changed));
      else window.sessionStorage.removeItem(draftKey(screening));
      setDraftNotice(null);
    } catch {
      setDraftNotice("storage_unavailable");
    }
  };
  const editDecision = (decision: CandidateScreeningDecision) => updateDraft({ ...draft(), [decision.document_id]: decision });
  function syncCheckpoint(expireStale = false) {
    const screening = props.screening;
    setSavedProgress(null);
    setProgressMessage(null);
    if (!screening || screening.run_id !== props.liveRunId || !props.missionId) return;
    try {
      const key = checkpointKey(screening.run_id);
      const raw = window.localStorage.getItem(key);
      if (raw === null) return;
      const saved = readCheckpoint(raw, screening, props.missionId, savedScreeningDecision);
      if (saved) setSavedProgress(saved);
      else {
        // A tab observing another tab's storage event can have an older checklist in memory.
        // Only an authoritative checklist refresh may expire a saved revision.
        if (expireStale && window.localStorage.getItem(key) === raw) window.localStorage.removeItem(key);
        setProgressMessage("expired");
      }
    } catch { setProgressMessage("unavailable"); }
  }
  createEffect(() => syncCheckpoint(true));
  onMount(() => {
    const onStorage = (event: StorageEvent) => {
      if (event.storageArea === window.localStorage && (event.key === null || event.key === checkpointKey(props.liveRunId ?? ""))) syncCheckpoint();
    };
    window.addEventListener("storage", onStorage);
    onCleanup(() => window.removeEventListener("storage", onStorage));
  });
  function saveCheckpoint() {
    const screening = props.screening, current = activeCandidate()?.document_id;
    if (!screening || !current || screening.run_id !== props.liveRunId) return;
    try {
      const key = checkpointKey(screening.run_id), existing = window.localStorage.getItem(key);
      if (existing !== null && !readCheckpoint(existing, screening, props.missionId, savedScreeningDecision)) {
        setProgressMessage("refresh");
        return;
      }
      const raw = encodeCheckpoint(screening, props.missionId, current, changes());
      window.localStorage.setItem(key, raw);
      syncCheckpoint();
      setProgressMessage("saved");
    } catch { setProgressMessage("unavailable"); }
  }
  function clearCheckpoint() {
    const screening = props.screening;
    if (!screening || screening.run_id !== props.liveRunId) return;
    try {
      const key = checkpointKey(screening.run_id), existing = window.localStorage.getItem(key);
      if (existing !== null && !readCheckpoint(existing, screening, props.missionId, savedScreeningDecision)) {
        syncCheckpoint();
        setProgressMessage("refresh");
        return;
      }
      window.localStorage.removeItem(key);
      setSavedProgress(null);
      setProgressMessage("cleared");
    } catch { setProgressMessage("unavailable"); }
  }
  async function restoreCheckpoint() {
    const activeRun = props.liveRunId, mission = props.missionId;
    if (!savedProgress() || busy()) return;
    setBusy(true);
    try {
      await props.load();
      if (props.liveRunId !== activeRun || props.missionId !== mission) return;
      syncCheckpoint(true);
      const saved = savedProgress(), screening = props.screening;
      if (!saved || !screening) { setProgressMessage("expired"); return; }
      const next = screeningDraftForCandidates(screening);
      for (const change of saved.changes) next[change.document_id] = change;
      updateDraft(next);
      setActiveDocumentId(saved.current);
      setProgressMessage("restored");
      currentTitle?.focus();
    } catch { setProgressMessage("offline"); }
    finally { setBusy(false); }
  }
  const updateDecision = (documentId: string, decision: string) => {
    if (draft()[documentId]?.decision !== decision) editDecision({ document_id: documentId, decision, reason_codes: [] });
  };
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
      const screening = props.screening, mission = props.missionId;
      await props.submit(screeningSubmission(screening.candidates, draft()), screening.checklist_revision);
      try {
        const key = checkpointKey(screening.run_id), raw = window.localStorage.getItem(key);
        if (raw && readCheckpoint(raw, screening, mission, savedScreeningDecision)) window.localStorage.removeItem(key);
        if (props.screening?.run_id === screening.run_id && props.missionId === mission) syncCheckpoint();
      } catch { setProgressMessage("unavailable"); }
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
    <Show when={handoffRevision()}>{(revision) => <DshScreeningHandoff runId={props.liveRunId!} revision={revision()} locale={props.locale} />}</Show>
    <Show when={props.screening && props.screening.candidates.length === 0}><p class="screening-empty">{t("当前检索没有返回可筛选的候选。", "This search returned no candidates to screen.")}</p></Show>
    <Show when={props.screening && props.screening.candidates.length > 0}><div class="screening-list">
      <Show when={handoffRevision() && props.missionId}><div class="screening-checkpoint-actions">
        <ActionButton size="sm" disabled={busy()} onClick={saveCheckpoint}>{t("保存进度到本机", "Save progress on this device")}</ActionButton>
        <Show when={savedProgress()}>
          <ActionButton size="sm" disabled={busy()} onClick={() => void restoreCheckpoint()}>{t("恢复上次进度", "Restore saved progress")}</ActionButton>
          <ActionButton size="sm" variant="quiet" disabled={busy()} onClick={clearCheckpoint}>{t("清除已存进度", "Clear saved progress")}</ActionButton>
        </Show>
        <span role="status">{({
          saved: t("已保存当前文献和筛选草稿。", "Current paper and draft saved."),
          restored: t("已回到保存的文献和草稿。", "Returned to the saved paper and draft."),
          cleared: t("已清除本机保存的进度。", "Saved progress cleared."),
          expired: t("当前清单已变化，已存进度失效。", "The saved progress no longer matches this checklist."),
          unavailable: t("本机存储不可用，仍可在本页筛选。", "Device storage is unavailable. You can continue in this tab."),
          offline: t("无法核对最新清单。请刷新清单后再恢复。", "Could not verify the current checklist. Refresh it and try again."),
          refresh: t("另一个清单版本已保存进度，请先刷新清单。", "Another checklist revision has saved progress. Refresh the checklist first."),
        })[progressMessage()!]}</span>
      </div></Show>
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
        const reasons = () => REASONS[decision().decision] ?? [];
        const selectedReasons = () => reasons().filter(([code]) => decision().reason_codes.includes(code));
        let reasonPicker: HTMLSelectElement | undefined;
        return <article class="screening-queue-card" classList={{ focused: candidate().document_id === props.focusDocumentId }}>
          <header>
            <div><small>{t("当前候选", "CURRENT CANDIDATE")} · {activeIndex() + 1} / {candidates().length}</small><strong ref={element => { currentTitle = element; }} tabIndex={-1}>{candidate().title}</strong><span>{candidate().source}{candidate().publication_year ? ` · ${candidate().publication_year}` : ""}</span></div>
            <nav aria-label={t("候选队列导航", "Candidate queue navigation")}>
              <ActionButton size="sm" onClick={() => moveCandidate(-1)} disabled={activeIndex() <= 0}>{t("上一篇", "Previous")}</ActionButton>
              <ActionButton size="sm" onClick={() => moveCandidate(1)} disabled={activeIndex() >= candidates().length - 1}>{t("下一篇", "Next")}</ActionButton>
              <ActionButton size="sm" onClick={() => setActiveDocumentId(nextPending()?.document_id ?? null)} disabled={!nextPending()}>{t("下一待审", "Next unfinished")}</ActionButton>
            </nav>
          </header>
          <div class="screening-decision-fields">
            <label>{t("决定", "Decision")}<select disabled={busy()} value={decision().decision} onChange={(event) => updateDecision(candidate().document_id, event.currentTarget.value)}><option value="unreviewed">{t("请选择", "Select")}</option><For each={DECISIONS}>{([value, zh, en]) => <option value={value}>{t(zh, en)}</option>}</For></select></label>
            <Show when={decision().decision !== "unreviewed"}>
              <div class="screening-reasons">
                <label>{t("理由", "Reason")}<select ref={reasonPicker} disabled={busy()} onChange={(event) => {
                  const code = event.currentTarget.value;
                  event.currentTarget.value = "";
                  const current = decision();
                  if (code && !current.reason_codes.includes(code)) editDecision({ ...current, reason_codes: [...current.reason_codes, code] });
                }}>
                  <option value="">{selectedReasons().length === reasons().length
                    ? t("已选全部理由", "All reasons selected") : t("添加理由（可多选）", "Add a reason (one or more)")}</option>
                  <For each={reasons()}>{([code, zh, en]) => <option value={code} disabled={decision().reason_codes.includes(code)}>{t(zh, en)}</option>}</For>
                </select></label>
                <Show when={selectedReasons().length}><ul aria-label={t("已选理由", "Selected reasons")}>
                  <For each={selectedReasons()}>{([code, zh, en]) => <li><button type="button" disabled={busy()}
                    aria-label={t(`移除理由：${zh}`, `Remove reason: ${en}`)} onClick={() => {
                      const current = decision();
                      editDecision({ ...current, reason_codes: current.reason_codes.filter(reason => reason !== code) });
                      reasonPicker?.focus();
                    }}>{t(zh, en)} <span aria-hidden="true">×</span></button></li>}</For>
                </ul></Show>
              </div>
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
