import { For, Show, createMemo, createSignal } from "solid-js";
import type { LiteratureGraphEdge, LiteratureGraphNode } from "./model";
import { graphDisplayLabel } from "./graphSearch";
import "./graph-connections.css";

type Label = readonly [string, string];
const cites: Label = ["引用了", "Cites"];
const citedBy: Label = ["被其引用", "Cited by"];
const relations: Record<string, readonly [Label, Label]> = {
  citation_reference: [cites, citedBy],
  crossref_reference: [cites, citedBy],
  citation_cited_by: [citedBy, cites],
  source_provenance: [["来源中的证据卡", "Evidence from this source"], ["证据来源", "Evidence source"]],
  retrieval_candidate: [["检索到的论文", "Retrieved paper"], ["检索任务", "Retrieval mission"]],
  condition_support: [["支持的条件簇", "Supported condition cluster"], ["支持该条件的记录", "Record supporting this condition"]],
  condition_contradiction: [["存在分歧的条件簇", "Conflicting condition cluster"], ["与该条件有分歧的记录", "Record conflicting with this condition"]],
  gap_evidence_basis: [["基于该证据的待审问题", "Proposed gap using this evidence"], ["待审问题的依据", "Evidence behind the proposed gap"]],
  algorithmic_related: [["算法相关文献", "Algorithmically related work"], ["算法相关文献", "Algorithmically related work"]],
  title_similarity_suggestion: [["题名相似建议", "Similar-title suggestion"], ["题名相似建议", "Similar-title suggestion"]],
  paper_contains: [["论文中的条目", "Item in this paper"], ["所属论文", "Containing paper"]],
};

export function GraphConnections(props: {
  nodeId: string; nodes: ReadonlyMap<string, LiteratureGraphNode>; edges: LiteratureGraphEdge[];
  locale: "zh" | "en"; onFollow: (node: LiteratureGraphNode) => void;
}) {
  const t = (zh: string, en: string) => props.locale === "zh" ? zh : en;
  const connections = createMemo(() => props.edges.flatMap(edge => {
    const outgoing = edge.sourceId === props.nodeId;
    if (!outgoing && edge.targetId !== props.nodeId) return [];
    const other = props.nodes.get(outgoing ? edge.targetId : edge.sourceId);
    if (!other || other.nodeId === props.nodeId) return [];
    const labels = Object.hasOwn(relations, edge.edgeType) ? relations[edge.edgeType] : null;
    const label = labels ? t(...labels[outgoing ? 0 : 1]) : edge.edgeType.replaceAll("_", " ") + (outgoing ? " →" : " ←");
    return [{ other, edge, label, title: graphDisplayLabel(other) }];
  }));
  const titleCounts = createMemo(() => {
    const counts = new Map<string, number>();
    for (const { title } of connections()) counts.set(title, (counts.get(title) ?? 0) + 1);
    return counts;
  });
  const [limit, setLimit] = createSignal(6);
  return <section class="graph-connections" aria-label={t("直接关系", "Direct connections")}>
    <h3>{t("直接关系", "Direct connections")} <small>{connections().length}</small></h3>
    <Show when={connections().length} fallback={<p>{t("这份星图没有记录该节点的直接关系。", "This map records no direct connections for this node.")}</p>}>
      <ul><For each={connections().slice(0, limit())}>{entry => <li><button type="button" onClick={() => props.onFollow(entry.other)}>
        <small>{entry.label}{entry.edge.relationSource ? " · " + entry.edge.relationSource : ""}</small>
        <strong>{entry.title || entry.other.nodeId}</strong>
        <Show when={entry.title && (titleCounts().get(entry.title) ?? 0) > 1}>
          <code>{entry.other.nodeId}</code>
        </Show>
      </button></li>}</For></ul>
      <Show when={connections().length > limit()}><button class="graph-more-links" type="button" onClick={() => setLimit(limit() + 12)}>
        {t(`再显示 ${Math.min(12, connections().length - limit())} 条关系`, `Show ${Math.min(12, connections().length - limit())} more connections`)}
      </button></Show>
    </Show>
  </section>;
}
