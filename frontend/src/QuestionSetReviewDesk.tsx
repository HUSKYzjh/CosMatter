import { For, Show, createMemo, createSignal, onMount } from "solid-js";

import {
  QUESTION_REVIEW_CHECKS,
  exportQuestionSetReviewDraft,
  parseQuestionSetReviewDraft,
  questionSetReviewReadiness,
  type QuestionReviewCheck,
  type QuestionReviewCheckValue,
  type QuestionReviewDecision,
  type QuestionSetReviewDraft,
} from "./questionSetReviewDraft";

const CHECK_LABELS: Record<QuestionReviewCheck, { zh: string; en: string }> = {
  answerable_by_literature: { zh: "可由文献回答", en: "Answerable by literature" },
  material_explicit: { zh: "材料对象明确", en: "Material is explicit" },
  target_property_explicit: { zh: "目标性质明确", en: "Target property is explicit" },
  scope_bounded: { zh: "范围有明确边界", en: "Scope is bounded" },
  avoids_assumed_answer: { zh: "未预设答案", en: "Does not assume an answer" },
};

const SESSION_DRAFT_KEY = "cosmatter.question-set-review-draft/v1";

export function QuestionSetReviewDesk(props: { locale: "zh" | "en" }) {
  const tr = (zh: string, en: string) => props.locale === "zh" ? zh : en;
  const [draft, setDraft] = createSignal<QuestionSetReviewDraft | null>(null);
  const [fileName, setFileName] = createSignal<string | null>(null);
  const [error, setError] = createSignal<string | null>(null);
  const [attested, setAttested] = createSignal(false);
  const [clearArmed, setClearArmed] = createSignal(false);
  const [sessionStatus, setSessionStatus] = createSignal<"saved" | "restored" | "unavailable" | null>(null);
  const readiness = createMemo(() => draft() ? questionSetReviewReadiness(draft()!) : null);

  function persistSession(nextDraft: QuestionSetReviewDraft, nextFileName: string | null) {
    try {
      window.sessionStorage.setItem(SESSION_DRAFT_KEY, JSON.stringify({ draft: nextDraft, file_name: nextFileName }));
      setSessionStatus("saved");
    } catch {
      setSessionStatus("unavailable");
    }
  }

  onMount(() => {
    let stored: string | null;
    try {
      stored = window.sessionStorage.getItem(SESSION_DRAFT_KEY);
    } catch {
      setSessionStatus("unavailable");
      return;
    }
    if (!stored) return;
    try {
      const envelope = JSON.parse(stored) as { draft?: unknown; file_name?: unknown };
      const restored = exportQuestionSetReviewDraft(parseQuestionSetReviewDraft(envelope.draft), false);
      setDraft(restored);
      setFileName(typeof envelope.file_name === "string" ? envelope.file_name.slice(0, 160) : null);
      setSessionStatus("restored");
    } catch {
      try { window.sessionStorage.removeItem(SESSION_DRAFT_KEY); } catch { setSessionStatus("unavailable"); }
    }
  });

  async function importFile(file: File | undefined) {
    if (!file) return;
    setError(null);
    setAttested(false);
    setClearArmed(false);
    if (file.size > 512 * 1024) {
      setError(tr("问题集审核文件不得超过 512 KiB。", "Question-set review files must not exceed 512 KiB."));
      return;
    }
    try {
      const parsed = exportQuestionSetReviewDraft(parseQuestionSetReviewDraft(JSON.parse(await file.text())), false);
      const boundedFileName = file.name.slice(0, 160);
      setDraft(parsed);
      setFileName(boundedFileName);
      persistSession(parsed, boundedFileName);
    } catch {
      setError(tr("所选文件不是受支持的问题集审核 JSON；没有导入任何内容。", "The selected file is not a supported question-set review JSON; nothing was imported."));
    }
  }

  function updateQuestion(index: number, update: (question: QuestionSetReviewDraft["questions"][number]) => QuestionSetReviewDraft["questions"][number]) {
    const current = draft();
    if (!current) return;
    const questions = current.questions.map((question, currentIndex) => currentIndex === index ? update(structuredClone(question)) : question);
    const next = { ...current, questions };
    setDraft(next);
    persistSession(next, fileName());
    setAttested(false);
    setClearArmed(false);
  }

  function clearSession() {
    if (!clearArmed()) {
      setClearArmed(true);
      return;
    }
    let storageUnavailable = false;
    try { window.sessionStorage.removeItem(SESSION_DRAFT_KEY); } catch { storageUnavailable = true; }
    setDraft(null);
    setFileName(null);
    setError(null);
    setAttested(false);
    setClearArmed(false);
    setSessionStatus(storageUnavailable ? "unavailable" : null);
  }

  function updateDecision(index: number, decision: QuestionReviewDecision) {
    updateQuestion(index, (question) => ({ ...question, review_decision: decision }));
  }

  function updateCheck(index: number, check: QuestionReviewCheck, value: QuestionReviewCheckValue) {
    updateQuestion(index, (question) => ({ ...question, review_checks: { ...question.review_checks, [check]: value } }));
  }

  function exportReview() {
    const current = draft();
    if (!current) return;
    const payload = exportQuestionSetReviewDraft(current, attested());
    const blob = new Blob([JSON.stringify(payload, null, 2) + "\n"], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${payload.question_set_id.replace(/[^A-Za-z0-9._-]+/g, "-") || "question-set"}.review.json`;
    anchor.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 0);
  }

  return <details class="question-review-desk" aria-label={tr("冻结问题集人工审核台", "Human frozen-question-set review desk")}>
    <summary>{tr("人工问题集审核台", "Human question-set review desk")}</summary>
    <p>{tr("显式选择本地审核模板后逐题填写。内容只保留在当前浏览器会话；本页不联网、不冻结问题集，也不写入运行目录。", "Select a local review template explicitly and review each question. Content remains in this browser session; this page does not use the network, freeze the set, or write into a run directory.")}</p>
    <label class="question-review-import">
      <span>{tr("选择问题集审核 JSON", "Select question-set review JSON")}</span>
      <input type="file" accept="application/json,.json" onChange={(event) => { const file = event.currentTarget.files?.[0]; event.currentTarget.value = ""; void importFile(file); }} />
    </label>
    <Show when={sessionStatus()}>{(status) => <p class="question-review-session-note" role="status">{status() === "restored" ? tr("已恢复本浏览器会话中的审核草稿；独立审核声明需要重新确认。", "The review draft was restored from this browser session; independent-review attestation must be confirmed again.") : status() === "saved" ? tr("审核草稿已暂存在本浏览器会话中。", "The review draft is temporarily saved in this browser session.") : tr("浏览器会话暂存不可用；请及时导出本地草稿。", "Browser-session storage is unavailable; export a local draft promptly.")}</p>}</Show>
    <Show when={error()}>{(message) => <p class="question-review-error" role="alert">{message()}</p>}</Show>
    <Show when={draft()}>{(current) => <>
      <header class="question-review-status" aria-live="polite">
        <div><small>{tr("本地审核草稿", "LOCAL REVIEW DRAFT")}</small><strong>{current().question_set_id}</strong><span>{fileName()} · {current().material_family}</span></div>
        <dl>
          <div><dt>{tr("已决定", "Decided")}</dt><dd>{readiness()!.decidedCount}/{readiness()!.questionCount}</dd></div>
          <div><dt>{tr("检查完成", "Checks complete")}</dt><dd>{readiness()!.checksCompletedCount}/{readiness()!.questionCount}</dd></div>
          <div><dt>{tr("理由完成", "Notes complete")}</dt><dd>{readiness()!.notesCompletedCount}/{readiness()!.questionCount}</dd></div>
          <div><dt>{tr("纳入", "Included")}</dt><dd>{readiness()!.includedCount}</dd></div>
        </dl>
      </header>
      <section class="question-review-list">
        <For each={current().questions}>{(question, index) => <article classList={{ "question-review-item": true, complete: question.review_decision !== "unreviewed" && QUESTION_REVIEW_CHECKS.every((check) => typeof question.review_checks[check] === "boolean") && Boolean(question.review_note.trim()), invalid: question.review_decision === "include" && QUESTION_REVIEW_CHECKS.some((check) => question.review_checks[check] !== true) }}>
          <header><small>{String(index() + 1).padStart(2, "0")} · {question.question_id}</small><span>{question.intended_evidence_level.replaceAll("_", " ")}</span></header>
          <h3>{question.question}</h3>
          <dl><div><dt>{tr("材料", "Material")}</dt><dd>{question.material}</dd></div><div><dt>{tr("目标性质", "Target property")}</dt><dd>{question.target_property}</dd></div><div><dt>{tr("边界", "Scope")}</dt><dd>{question.scope}</dd></div></dl>
          <label>{tr("审核决定", "Review decision")}<select value={question.review_decision} onChange={(event) => updateDecision(index(), event.currentTarget.value as QuestionReviewDecision)}><option value="unreviewed">{tr("待审核", "Unreviewed")}</option><option value="include">{tr("纳入", "Include")}</option><option value="exclude">{tr("排除", "Exclude")}</option></select></label>
          <fieldset><legend>{tr("五项质量检查", "Five quality checks")}</legend><div><For each={QUESTION_REVIEW_CHECKS}>{(check) => <label><span>{tr(CHECK_LABELS[check].zh, CHECK_LABELS[check].en)}</span><select value={question.review_checks[check] === null ? "unset" : String(question.review_checks[check])} onChange={(event) => updateCheck(index(), check, event.currentTarget.value === "unset" ? null : event.currentTarget.value === "true")}><option value="unset">{tr("未判断", "Unset")}</option><option value="true">{tr("通过", "Pass")}</option><option value="false">{tr("不通过", "Fail")}</option></select></label>}</For></div></fieldset>
          <label>{tr("审核理由（最多 500 字符）", "Review reason (500 characters maximum)")}<textarea rows="2" maxLength={500} value={question.review_note} onInput={(event) => updateQuestion(index(), (item) => ({ ...item, review_note: event.currentTarget.value }))} /></label>
        </article>}</For>
      </section>
      <section class="question-review-release">
        <div><small>{tr("冻结前人工门禁", "HUMAN GATE BEFORE FREEZE")}</small><strong>{readiness()!.readyForAttestation ? tr("内容完整；仍需独立审核声明", "Content complete; independent-review attestation remains") : tr("审核尚未完整", "Review remains incomplete")}</strong><p>{readiness()!.invalidIncludedCount ? tr(`有 ${readiness()!.invalidIncludedCount} 条纳入问题未通过全部五项检查。`, `${readiness()!.invalidIncludedCount} included question(s) do not pass all five checks.`) : readiness()!.includedCount < 3 ? tr("至少需要纳入三条问题。", "At least three questions must be included.") : tr("所有问题均须有决定、五项明确判断和非空理由。", "Every question needs a decision, five explicit checks, and a non-empty reason.")}</p></div>
        <label class="consent"><input type="checkbox" disabled={!readiness()!.readyForAttestation} checked={attested()} onChange={(event) => setAttested(event.currentTarget.checked)} />{tr("我确认这是独立研究者逐题完成的审核；导出仅供后续 CLI 冻结验证，不代表评测结果。", "I confirm that an independent researcher reviewed every question. The export is only for subsequent CLI freeze validation and is not an evaluation result.")}</label>
        <div class="question-review-actions"><button type="button" classList={{ "clear-armed": clearArmed() }} onClick={clearSession}>{clearArmed() ? tr("再次点击确认清除", "Click again to confirm clear") : tr("清除本会话草稿", "Clear session draft")}</button><button type="button" class="primary-action" onClick={exportReview}>{attested() && readiness()!.readyForAttestation ? tr("导出可冻结审核 JSON", "Export freeze-eligible review JSON") : tr("导出本地审核草稿", "Export local review draft")}</button></div>
      </section>
    </>}</Show>
  </details>;
}
