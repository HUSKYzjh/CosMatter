import { For, Show, createMemo } from "solid-js";

import type { RelationReconciliation, RelationReconciliationStatus } from "./model";

const copy = (locale: "zh" | "en", zh: string, en: string) => locale === "zh" ? zh : en;
const label = (locale: "zh" | "en", status: RelationReconciliationStatus) => ({
  matched: copy(locale, "人工标注匹配", "human-marked match"),
  conflict: copy(locale, "冲突，未合并", "conflict; not merged"),
  unresolved: copy(locale, "未决，未合并", "unresolved; not merged"),
}[status]);

export function RelationReconciliationPanel(props: { reconciliation: RelationReconciliation; locale: "zh" | "en" }) {
  const counts = createMemo(() => props.reconciliation.mappings.reduce<Record<RelationReconciliationStatus, number>>((result, mapping) => ({ ...result, [mapping.status]: result[mapping.status] + 1 }), { matched: 0, conflict: 0, unresolved: 0 }));
  return <section class="relation-reconciliation-panel" aria-label={copy(props.locale, "跨源标识人工对账", "Human cross-source identity reconciliation")}>
    <header><div><small>{copy(props.locale, "跨源标识人工对账 / 只读", "CROSS-SOURCE IDENTITY RECONCILIATION / READ ONLY")}</small><h2>{copy(props.locale, "书目映射不等于材料结论", "Bibliographic mapping is not a materials conclusion")}</h2></div><span>{props.reconciliation.trustStatus}</span></header>
    <p>{copy(props.locale, `该对账绑定 EvidenceCard ${props.reconciliation.sourceEvidenceId} 与文献 ${props.reconciliation.sourceDocumentId}。仅人工记录的映射会显示；同名、题名相似或单一来源缺失均不会自动合并。`, `This reconciliation is bound to EvidenceCard ${props.reconciliation.sourceEvidenceId} and document ${props.reconciliation.sourceDocumentId}. Only human-recorded mappings are shown; matching names, title similarity, or one-source absence never auto-merges identifiers.`)}</p>
    <dl class="relation-reconciliation-counts"><div><dt>{copy(props.locale, "匹配", "matched")}</dt><dd>{counts().matched}</dd></div><div><dt>{copy(props.locale, "冲突", "conflicts")}</dt><dd>{counts().conflict}</dd></div><div><dt>{copy(props.locale, "未决", "unresolved")}</dt><dd>{counts().unresolved}</dd></div></dl>
    <Show when={props.reconciliation.mappings.length} fallback={<p class="relation-reconciliation-empty">{copy(props.locale, "当前没有人工对账映射；这不表示两个来源不存在同一工作，也不表示可以自动合并。", "There are no human reconciliation mappings yet. This neither proves that the sources lack the same work nor permits an automatic merge.")}</p>}>
      <ol><For each={props.reconciliation.mappings}>{(mapping, index) => <li class={`state-${mapping.status}`}><small>{String(index() + 1).padStart(2, "0")} / {label(props.locale, mapping.status)}</small><code>{mapping.openAlexWorkId}</code><i aria-hidden="true">↔</i><code>{mapping.crossrefDoi}</code><span>{mapping.basis}</span></li>}</For></ol>
    </Show>
    <Show when={props.reconciliation.revisionHistory.length} fallback={<p class="relation-reconciliation-history-empty">{copy(props.locale, "此导出来自旧版对账工件，未附带修订摘要；当前映射仍须人工核对。", "This export came from a legacy reconciliation artifact without revision summaries; the current mappings still require human review.")}</p>}>
      <details class="relation-reconciliation-history"><summary>{copy(props.locale, `修订摘要（${props.reconciliation.revisionHistory.length} 次）`, `Revision summaries (${props.reconciliation.revisionHistory.length})`)}</summary><p>{copy(props.locale, "这是本地工件登记时间与状态计数，不是审核人身份、原文或科学结论。", "These are local artifact record times and status counts, not reviewer identity, source text, or scientific conclusions.")}</p><ol><For each={props.reconciliation.revisionHistory}>{(revision) => <li><small>R{String(revision.revision).padStart(2, "0")} / {revision.recordedAt}</small><span>{copy(props.locale, `映射 ${revision.mappingCount} · 匹配 ${revision.statusCounts.matched} · 冲突 ${revision.statusCounts.conflict} · 未决 ${revision.statusCounts.unresolved}`, `maps ${revision.mappingCount} · matched ${revision.statusCounts.matched} · conflicts ${revision.statusCounts.conflict} · unresolved ${revision.statusCounts.unresolved}`)}</span></li>}</For></ol></details>
    </Show>
  </section>;
}
