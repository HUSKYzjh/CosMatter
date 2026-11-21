import { For, Show, batch, createEffect, createSignal, onCleanup } from "solid-js";
import {
  approveEvidenceGraphPlan, draftEvidenceGraphPlan, getEvidenceGraphPage, requestEvidenceGraphReview,
  type EvidenceGraphNodeType, type EvidenceGraphPage, type EvidenceGraphPlanDraft,
} from "./localApi";
import { safeMutationFeedback } from "./importFeedback";
import { createLatestRequestGate } from "./latestRequestGate";

const TYPES: EvidenceGraphNodeType[] = ["EvidenceCard", "Paper", "Entity", "Condition", "Mission"];
const limit = 25;
type Props = { runId: string; missionId: string; locale: "zh" | "en" };
const text = (locale: Props["locale"], zh: string, en: string) => locale === "zh" ? zh : en;
function receiptId(value: unknown, prefix: string): boolean {
  return typeof value === "string" && value.startsWith(prefix) && /^[A-Za-z0-9_-]{1,160}$/.test(value);
}

function matchesPage(response: EvidenceGraphPage, type: EvidenceGraphNodeType, offset: number, mission: string) {
  const meta = response?.page;
  return response?.schema_version === "1.0" && response.trust_status === "accepted_evidence_projection_not_scientific_conclusion"
    && Boolean(mission) && response.mission_id === mission && Boolean(response.graph_id?.startsWith("graph:"))
    && meta?.offset === offset && meta.limit === limit && meta.node_types?.length === 1 && meta.node_types[0] === type
    && Number.isSafeInteger(meta.node_total) && meta.node_total >= 0 && Array.isArray(response.nodes)
    && response.nodes.length === Math.min(limit, Math.max(0, meta.node_total - offset)) && meta.truncated === (offset + response.nodes.length < meta.node_total)
    && response.nodes.every(node => node && typeof node.node_id === "string" && node.node_id.length > 0 && node.node_type === type && typeof node.label === "string")
    && new Set(response.nodes.map(node => node.node_id)).size === response.nodes.length;
}

export function EvidenceGraphExplorer(props: Props) {
  const [activated, setActivated] = createSignal(false);
  return <details class="graph-review-tools" onToggle={event => { if (event.currentTarget.open) setActivated(true); }}>
    <summary>{text(props.locale, "已接受证据的审核队列", "Accepted evidence review queue")}</summary>
    <Show when={activated()}><EvidencePages {...props} /></Show>
  </details>;
}

function EvidencePages(props: Props) {
  const [type, setType] = createSignal<EvidenceGraphNodeType>("EvidenceCard");
  const [offset, setOffset] = createSignal(0);
  const [attempt, retry] = createSignal(0);
  const [page, setPage] = createSignal<EvidenceGraphPage | null>(null);
  const [failed, setFailed] = createSignal(false);
  const reads = createLatestRequestGate();
  const t = (zh: string, en: string) => text(props.locale, zh, en);
  createEffect(() => {
    attempt();
    const run = props.runId, mission = props.missionId, nodeType = type(), start = offset();
    const current = reads.begin();
    setPage(null);
    setFailed(false);
    void getEvidenceGraphPage(run, { nodeType, offset: start, limit }).then(result => {
      if (!current()) return;
      if (!matchesPage(result, nodeType, start, mission)) { setFailed(true); return; }
      setPage(result);
    }).catch(() => { if (current()) setFailed(true); });
  });
  onCleanup(() => reads.invalidate());
  return <section class="evidence-graph-explorer">
    <div class="graph-type-tabs"><For each={TYPES}>{item =>
      <button type="button" classList={{ active: type() === item }} aria-pressed={type() === item}
        onClick={() => batch(() => { setType(item); setOffset(0); })}>{item}</button>
    }</For></div>
    <Show when={failed()}><p class="graph-truncated" role="alert">{t("无法读取当前页。", "Could not load this page.")}</p>
      <button type="button" onClick={() => retry(value => value + 1)}>{t("重试读取", "Retry loading")}</button>
    </Show>
    <Show when={!page() && !failed()}><p role="status">{t("正在读取当前页…", "Loading this page…")}</p></Show>
    <Show when={page()} keyed>{value => <>
      <p>{value.nodes.length ? t(
        `当前 ${value.page.offset + 1}–${value.page.offset + value.nodes.length} / ${value.page.node_total} 个节点`,
        `Showing ${value.page.offset + 1}–${value.page.offset + value.nodes.length} of ${value.page.node_total} nodes`,
      ) : value.page.node_total ? t("当前页已空，可返回上一页。", "This page is empty. Return to the previous page.")
        : t("当前类型没有已核对节点。", "No reviewed nodes of this type.")}</p>
      <Show when={value.nodes.length}><ReviewPage runId={props.runId} locale={props.locale} page={value} /></Show>
      <div class="graph-type-tabs">
        <button type="button" disabled={offset() === 0} onClick={() => setOffset(Math.max(0, offset() - limit))}>{t("上一页", "Previous")}</button>
        <button type="button" disabled={!value.page.truncated} onClick={() => setOffset(offset() + limit)}>{t("下一页", "Next")}</button>
      </div>
    </>}</Show>
  </section>;
}

function ReviewPage(props: Pick<Props, "runId" | "locale"> & { page: EvidenceGraphPage }) {
  const [selected, setSelected] = createSignal<string[]>([]);
  const [intent, setIntent] = createSignal("");
  const [reviewer, setReviewer] = createSignal("");
  const [draft, setDraft] = createSignal<EvidenceGraphPlanDraft | null>(null);
  const [busy, setBusy] = createSignal(false);
  const [notice, setNotice] = createSignal("");
  const writes = createLatestRequestGate();
  const t = (zh: string, en: string) => text(props.locale, zh, en);
  onCleanup(() => writes.invalidate());

  function resetDraft() {
    writes.invalidate();
    setDraft(null);
    setReviewer("");
    setNotice("");
  }
  function select(id: string) {
    resetDraft();
    setSelected(current => current.includes(id) ? current.filter(item => item !== id) : [...current, id]);
  }
  async function submit(kind: "review" | "draft" | "approve") {
    const run = props.runId, graph = props.page.graph_id, mission = props.page.mission_id;
    const ids = selected(), rationale = intent().trim(), name = reviewer().trim(), plan = draft();
    if (busy() || !ids.length || !rationale || (kind === "approve" && (!plan || !name))) return;
    const current = writes.begin();
    const bound = (result: object) => "graph_id" in result && result.graph_id === graph && "mission_id" in result && result.mission_id === mission;
    const sameSelection = (received: string[]) => Array.isArray(received) && received.length === ids.length && ids.every(id => received.includes(id));
    setBusy(true);
    setNotice("");
    try {
      if (kind === "approve" && plan) {
        const result = await approveEvidenceGraphPlan(run, plan.plan_id, name, rationale);
        if (!current()) return;
        if (!bound(result) || result.plan_id !== plan.plan_id || !receiptId(result.approval_id, "graph_plan_approval_") || result.reviewer !== name || result.rationale !== rationale
          || result.status !== "human_approved_graph_plan_follow_up_not_execution_or_evidence_acceptance") {
          setDraft(null);
          throw new Error("approval identity mismatch");
        }
        setDraft(null);
        setReviewer("");
        setNotice(t(`已记录人工跟进确认 ${result.approval_id}。`, `Human acknowledgement recorded: ${result.approval_id}.`));
      } else if (kind === "draft") {
        setDraft(null);
        setReviewer("");
        const result = await draftEvidenceGraphPlan(run, ids, rationale);
        if (!current()) return;
        if (!bound(result) || !sameSelection(result.node_ids) || !receiptId(result.plan_id, "graph_plan_") || result.intent !== rationale
          || result.proposed_action !== "request_human_to_review_or_project_graph" || result.trust_status !== "untrusted_graph_plan_draft_not_execution_or_evidence_acceptance") throw new Error("draft identity mismatch");
        setDraft(result);
        setNotice(t(`已保存待审核草案 ${result.plan_id}。`, `Draft saved for review: ${result.plan_id}.`));
      } else {
        const result = await requestEvidenceGraphReview(run, ids, rationale);
        if (!current()) return;
        if (!bound(result) || !sameSelection(result.node_ids) || !receiptId(result.request_id, "graph_review_") || result.rationale !== rationale
          || result.status !== "pending_human_review_not_evidence_acceptance") throw new Error("review identity mismatch");
        setNotice(t(`已提交待审请求 ${result.request_id}。`, `Review requested: ${result.request_id}.`));
      }
    } catch (error) {
      if (current()) {
        if (kind === "approve" && error instanceof Error && "failure" in error && error.failure === "write_outcome_unknown") setDraft(null);
        setNotice(safeMutationFeedback(error, t("未能核对操作回执，请检查本次运行的工件。", "Could not verify the receipt. Check this run’s artifacts."),
          t("请求结果未知，请先核对本次运行的工件。", "The outcome is unknown. Check this run’s artifacts first.")));
      }
    } finally { setBusy(false); }
  }
  return <>
    <ul><For each={props.page.nodes}>{node => <li><label>
      <input type="checkbox" disabled={busy()} checked={selected().includes(node.node_id)} onChange={() => select(node.node_id)} />
      <strong>{node.label}</strong><span>{node.node_type}</span>
    </label></li>}</For></ul>
    <section class="graph-plan-review" aria-label={t("图计划人工审核", "Graph plan human review")}>
      <p>{t(`已选择 ${selected().length} 个节点。提交后由研究者核对，确认只登记人工跟进。`,
        `${selected().length} nodes selected. A researcher reviews the request. Acknowledgement records follow-up only.`)}</p>
      <label>{t("审核或检查理由", "Review or inspection rationale")}<input value={intent()} disabled={busy()} maxlength="500"
        onInput={event => { resetDraft(); setIntent(event.currentTarget.value); }} /></label>
      <div class="graph-type-tabs">
        <button type="button" disabled={busy() || !selected().length || !intent().trim()} onClick={() => void submit("review")}>{t("提交待审请求", "Request human review")}</button>
        <button type="button" disabled={busy() || !selected().length || !intent().trim()} onClick={() => void submit("draft")}>{t("创建不可信草案", "Create untrusted draft")}</button>
      </div>
      <Show when={draft()}><label>{t("人工审核者", "Human reviewer")}<input value={reviewer()} maxlength="200" disabled={busy()}
        onInput={event => setReviewer(event.currentTarget.value)} /></label>
        <button type="button" disabled={busy() || !reviewer().trim()} onClick={() => void submit("approve")}>{t("记录人工跟进确认", "Record human acknowledgement")}</button>
      </Show>
      <p class="graph-truncated" role="status">{busy() ? t("正在提交…", "Submitting…") : notice()}</p>
    </section>
  </>;
}
