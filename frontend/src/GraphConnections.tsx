import { For, Show, createMemo, createSignal } from "solid-js";
import type { EvidenceCard, LiteratureGraphEdge, LiteratureGraphNode } from "./model";
import { isAcceptedProvenanceEdge } from "./evidenceLinking";
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

type Locale = "zh" | "en";

export function graphRelationLabel(edgeType: string, outgoing: boolean, locale: Locale): string {
  const labels = Object.hasOwn(relations, edgeType) ? relations[edgeType] : null;
  if (!labels) return edgeType.replaceAll("_", " ") + (outgoing ? " →" : " ←");
  return labels[outgoing ? 0 : 1][locale === "zh" ? 0 : 1];
}

export function EvidenceSourceLink(props: { card: EvidenceCard; locale: Locale; onOpen: (card: EvidenceCard) => void }) {
  const label = () => props.locale === "zh" ? "在原文核对" : "Verify in source";
  return <button type="button" class="graph-source-link" onClick={() => props.onOpen(props.card)}
    aria-label={`${label()} · ${props.card.provenance.locator} · ${props.card.evidenceId}`}>
    <span>{props.card.provenance.locator}</span><span>{label()} <b aria-hidden="true">→</b></span>
  </button>;
}

export function GraphConnections(props: {
  nodeId: string; nodes: ReadonlyMap<string, LiteratureGraphNode>; edges: LiteratureGraphEdge[];
  locale: Locale; onFollow: (node: LiteratureGraphNode) => void;
  sourceForEdge: (edge: LiteratureGraphEdge) => EvidenceCard | undefined; onOpen: (card: EvidenceCard) => void;
}) {
  const t = (zh: string, en: string) => props.locale === "zh" ? zh : en;
  const connections = createMemo(() => props.edges.flatMap(edge => {
    const outgoing = edge.sourceId === props.nodeId;
    if (!outgoing && edge.targetId !== props.nodeId) return [];
    const other = props.nodes.get(outgoing ? edge.targetId : edge.sourceId);
    if (!other || other.nodeId === props.nodeId) return [];
    const card = other.kind === "accepted_evidence" || other.kind === "evidence_card" ? props.sourceForEdge(edge) : undefined;
    return [{ other, edge, card, label: graphRelationLabel(edge.edgeType, outgoing, props.locale), title: graphDisplayLabel(other) }];
  }));
  const evidence = createMemo(() => connections().flatMap(entry => entry.card ? [{ ...entry, card: entry.card }] : []));
  const related = createMemo(() => connections().filter(entry => !entry.card));
  const titleCounts = createMemo(() => {
    const counts = new Map<string, number>();
    for (const { title } of related()) counts.set(title, (counts.get(title) ?? 0) + 1);
    return counts;
  });
  const [limit, setLimit] = createSignal(6);
  const [cardLimit, setCardLimit] = createSignal(6);
  return <section class="graph-connections" aria-label={t("直接关系", "Direct connections")}>
    <Show when={evidence().length}><section class="graph-source-records">
      <h3>{t("关联的已接受证据", "Linked accepted evidence")} <small>{evidence().length}</small></h3>
      <ul><For each={evidence().slice(0, cardLimit())}>{entry => <li class="graph-source-record">
        <button type="button" class="graph-record-follow" onClick={() => props.onFollow(entry.other)}>
          <span class="graph-card-identity">{t("证据卡", "Card")} <code>{entry.card.evidenceId}</code></span>
          <strong>{entry.title || entry.card.claim}</strong>
        </button>
        <Show when={entry.edge.edgeType !== "source_provenance"}><span class="graph-record-relation">{entry.label}</span></Show>
        <div class="graph-record-origins">
          <Show when={props.nodeId !== `paper:${entry.card.provenance.documentId}`}>
            <span>{t("来源文献", "Source document")} · {entry.card.provenance.documentId}</span>
          </Show>
          <span>{t("证据来源", "Evidence source")} · {entry.card.provenance.source}</span>
          <Show when={entry.edge.relationSource && entry.edge.relationSource !== entry.card.provenance.source}>
            <span>{t("关系来源", "Relation source")} · {entry.edge.relationSource}</span>
          </Show>
        </div>
        <EvidenceSourceLink card={entry.card} locale={props.locale} onOpen={props.onOpen} />
      </li>}</For></ul>
      <Show when={evidence().length > cardLimit()}><button class="graph-more-links" type="button" onClick={() => setCardLimit(cardLimit() + 12)}>
        {t(`再显示 ${Math.min(12, evidence().length - cardLimit())} 张证据卡`, `Show ${Math.min(12, evidence().length - cardLimit())} more cards`)}
      </button></Show>
    </section></Show>
    <Show when={related().length || !connections().length}>
      <h3>{evidence().length ? t("其他直接关系", "Other connections") : t("直接关系", "Direct connections")} <small>{related().length}</small></h3>
      <Show when={related().length} fallback={<p>{t("这份星图没有记录该节点的直接关系。", "This map records no direct connections for this node.")}</p>}>
        <ul><For each={related().slice(0, limit())}>{entry => <li><button type="button" class="graph-record-follow" onClick={() => props.onFollow(entry.other)}>
          <small>{entry.label}{entry.edge.relationSource ? " · " + entry.edge.relationSource : ""}</small>
          <strong>{entry.title || entry.other.nodeId}</strong>
          <Show when={entry.edge.edgeType === "source_provenance" && !isAcceptedProvenanceEdge(entry.edge)}>
            <small>{t("来源关系待核对", "Source relation pending review")}</small>
          </Show>
          <Show when={entry.title && (titleCounts().get(entry.title) ?? 0) > 1}><code>{entry.other.nodeId}</code></Show>
        </button></li>}</For></ul>
        <Show when={related().length > limit()}><button class="graph-more-links" type="button" onClick={() => setLimit(limit() + 12)}>
          {t(`再显示 ${Math.min(12, related().length - limit())} 条关系`, `Show ${Math.min(12, related().length - limit())} more connections`)}
        </button></Show>
      </Show>
    </Show>
  </section>;
}
