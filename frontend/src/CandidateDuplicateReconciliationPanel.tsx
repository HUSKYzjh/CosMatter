import { For, Show, createMemo } from "solid-js";

import type { CandidateDuplicateQueue, CandidateDuplicateQueueState, CandidateDuplicateReconciliation, CandidateDuplicateResolution, LiteratureGraph } from "./model";

const copy = (locale: "zh" | "en", zh: string, en: string) => locale === "zh" ? zh : en;
const queueLabel = (locale: "zh" | "en", state: CandidateDuplicateQueueState) => ({
  same_doi_merge_allowed: copy(locale, "DOI 一致，可建立别名", "exact DOI; alias allowed"),
  conflicting_doi_review_required: copy(locale, "DOI 冲突，待人工对账", "conflicting DOI; review required"),
  partial_doi_review_required: copy(locale, "DOI 不完整，待人工对账", "partial DOI; review required"),
  title_only_review_required: copy(locale, "仅题名相同，待人工对账", "title only; review required"),
}[state]);
const resolutionLabel = (locale: "zh" | "en", resolution: CandidateDuplicateResolution | undefined) => {
  if (!resolution) return copy(locale, "未决，未合并", "pending; not merged");
  return ({
    same_work: copy(locale, "确认为同一工作", "confirmed same work"),
    distinct_works: copy(locale, "确认为不同工作", "confirmed distinct works"),
    unresolved: copy(locale, "信息不足，仍未决", "insufficient metadata; unresolved"),
  })[resolution.resolution];
};

export function CandidateDuplicateReconciliationPanel(props: { queue: CandidateDuplicateQueue; reconciliation: CandidateDuplicateReconciliation | null; graph: LiteratureGraph; locale: "zh" | "en" }) {
  const resolutionByGroup = createMemo(() => new Map(props.reconciliation?.resolutions.map((item) => [item.groupId, item]) ?? []));
  const titleByDocument = createMemo(() => new Map(props.graph.nodes.filter((node) => node.nodeId.startsWith("paper:")).map((node) => [node.nodeId.slice(6), node.label])));
  const pendingCount = createMemo(() => props.queue.groups.filter((group) => !resolutionByGroup().has(group.groupId)).length);
  return <section class="candidate-duplicate-panel" aria-label={copy(props.locale, "候选重复待对账", "Candidate duplicate reconciliation queue")}>
    <header><div><small>{copy(props.locale, "候选重复待对账 / 只读", "CANDIDATE DUPLICATE QUEUE / READ ONLY")}</small><h2>{copy(props.locale, "题名相同不是同一篇文献", "An identical title does not establish document identity")}</h2></div><span>{props.queue.groupCount} {copy(props.locale, "组", "group(s)")}</span></header>
    <p>{copy(props.locale, "系统只会为完全一致的规范化 DOI 建立别名。题名相同、DOI 缺失或 DOI 冲突只进入待对账队列，不会重写检索历史，也不会成为科学证据。", "Only exact normalized DOI equality may create an alias. Equal titles, missing DOI, or conflicting DOI enter this queue without rewriting retrieval history and never become scientific evidence.")}</p>
    <dl><div><dt>{copy(props.locale, "DOI 自动别名", "DOI aliases")}</dt><dd>{props.queue.summary.same_doi_merge_allowed}</dd></div><div><dt>{copy(props.locale, "待人工对账", "human review")}</dt><dd>{props.queue.groupCount - props.queue.summary.same_doi_merge_allowed}</dd></div><div><dt>{copy(props.locale, "仍未形成决定", "still pending")}</dt><dd>{pendingCount()}</dd></div></dl>
    <ol><For each={props.queue.groups.slice(0, 12)}>{(group, index) => {
      const resolution = () => resolutionByGroup().get(group.groupId);
      return <li class={`state-${resolution()?.resolution ?? group.doiState}`}><small>{String(index() + 1).padStart(2, "0")} / {queueLabel(props.locale, group.doiState)}</small><strong>{resolutionLabel(props.locale, resolution())}</strong><ul><For each={group.documentIds}>{(documentId) => <li><span>{titleByDocument().get(documentId) ?? documentId}</span><code>{documentId}</code></li>}</For></ul><Show when={resolution()}>{(item) => <p>{copy(props.locale, "依据", "basis")}: {item().basis.replaceAll("_", " ")}</p>}</Show></li>;
    }}</For></ol>
    <Show when={props.queue.groupCount > 12}><p>{copy(props.locale, `仅显示前 12 组；另有 ${props.queue.groupCount - 12} 组保留在当前只读工件中。`, `Showing the first 12 groups; ${props.queue.groupCount - 12} more remain in the current read-only artifact.`)}</p></Show>
  </section>;
}
