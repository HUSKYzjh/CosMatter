import { For, Show, createMemo, createSignal, lazy } from "solid-js";

import type { GraphCanvasControls } from "./LiteratureGraphCanvas";
import { TOPIC_KEYS, TOPIC_LABELS, isPaperNode, relatedLiteraturePairs, topicFor, type RelatedLiteraturePair, type TopicKey } from "./literatureTopology";
import type { ImportedBundle, LiteratureGraphEdge, LiteratureGraphNode } from "./model";
import "./frontier-graph.css";
import { zh } from "./zh";

const LiteratureGraphCanvas = lazy(() => import("./LiteratureGraphCanvas").then((module) => ({ default: module.LiteratureGraphCanvas })));

type GraphView = "graph" | "cards";
type NodeGroup = "mission" | "papers" | "evidence" | "references" | "structure";
type EdgeGroup = "discovery" | "evidence" | "bibliography" | "related" | "structure";
type NavigateView = "discover" | "workflow" | "reader" | "horizon";

const NODE_GROUPS: Array<{ id: NodeGroup; label: string; color: string }> = [
  { id: "mission", label: zh("Mission scope"), color: "var(--blue)" },
  { id: "papers", label: zh("Papers"), color: "var(--teal)" },
  { id: "evidence", label: zh("Accepted evidence"), color: "var(--orange)" },
  { id: "references", label: zh("Reference metadata"), color: "var(--violet)" },
  { id: "structure", label: zh("Structure / collections"), color: "var(--rose)" },
];
const EDGE_GROUPS: Array<{ id: EdgeGroup; label: string; color: string }> = [
  { id: "discovery", label: zh("Discovery route"), color: "var(--teal)" },
  { id: "evidence", label: zh("Evidence provenance"), color: "var(--orange)" },
  { id: "bibliography", label: zh("Bibliographic links"), color: "var(--violet)" },
  { id: "related", label: zh("Related-title suggestions"), color: "var(--blue)" },
  { id: "structure", label: zh("Document / collection links"), color: "var(--rose)" },
];

function nodeGroup(node: LiteratureGraphNode): NodeGroup {
  if (node.kind === "mission") return "mission";
  if (isPaperNode(node)) return "papers";
  if (node.kind === "accepted_evidence") return "evidence";
  if (["openalex_work", "crossref_work"].includes(node.kind)) return "references";
  return "structure";
}
function edgeGroup(edge: LiteratureGraphEdge): EdgeGroup {
  if (edge.edgeType === "retrieval_candidate") return "discovery";
  if (edge.edgeType === "source_provenance") return "evidence";
  if (edge.edgeType === "title_similarity_suggestion") return "related";
  if (["citation_reference", "algorithmic_related", "crossref_reference"].includes(edge.edgeType)) return "bibliography";
  return "structure";
}
function edgeKey(edge: LiteratureGraphEdge): string { return `${edge.sourceId}|${edge.targetId}|${edge.edgeType}`; }
function label(node: LiteratureGraphNode): string { return node.label.length > 92 ? `${node.label.slice(0, 89).trim()}...` : node.label; }

export function GraphNetwork(props: { bundle: ImportedBundle; theme: string; onNavigate: (view: NavigateView) => void }) {
  const [view, setView] = createSignal<GraphView>("graph");
  const [query, setQuery] = createSignal("");
  const [selectedTopic, setSelectedTopic] = createSignal<TopicKey | "all">("all");
  const [nodeVisibility, setNodeVisibility] = createSignal<Record<NodeGroup, boolean>>({ mission: true, papers: true, evidence: true, references: true, structure: true });
  const [edgeVisibility, setEdgeVisibility] = createSignal<Record<EdgeGroup, boolean>>({ discovery: true, evidence: true, bibliography: true, related: true, structure: true });
  const [selectedNodeId, setSelectedNodeId] = createSignal<string | null>(null);
  const [selectedEdge, setSelectedEdge] = createSignal<LiteratureGraphEdge | null>(null);
  const [focusSelection, setFocusSelection] = createSignal(false);
  const [controls, setControls] = createSignal<GraphCanvasControls | null>(null);
  const graph = () => props.bundle.literatureGraph;
  const suggestedPairs = createMemo(() => relatedLiteraturePairs(graph().nodes));
  const graphEdges = createMemo(() => {
    const supplied = graph().edges;
    const keys = new Set(supplied.map(edgeKey));
    return [...supplied, ...suggestedPairs().map((pair) => pair.edge).filter((edge) => !keys.has(edgeKey(edge)))];
  });
  const filteredNodes = createMemo(() => {
    const term = query().trim().toLocaleLowerCase();
    return graph().nodes.filter((node) => nodeVisibility()[nodeGroup(node)]
      && (!isPaperNode(node) || selectedTopic() === "all" || topicFor(node) === selectedTopic())
      && (!term || `${node.label} ${node.source ?? ""} ${node.kind}`.toLocaleLowerCase().includes(term)));
  });
  const visibleNodes = createMemo(() => {
    const nodes = filteredNodes();
    const selected = selectedNodeId();
    if (!focusSelection() || !selected) return nodes;
    const neighbors = new Set([selected]);
    graphEdges().forEach((edge) => {
      if (edge.sourceId === selected) neighbors.add(edge.targetId);
      if (edge.targetId === selected) neighbors.add(edge.sourceId);
    });
    return nodes.filter((node) => neighbors.has(node.nodeId));
  });
  const visibleIds = createMemo(() => new Set(visibleNodes().map((node) => node.nodeId)));
  const visibleEdges = createMemo(() => graphEdges().filter((edge) => edgeVisibility()[edgeGroup(edge)] && visibleIds().has(edge.sourceId) && visibleIds().has(edge.targetId)));
  const selectedNode = createMemo(() => graph().nodes.find((node) => node.nodeId === selectedNodeId()) ?? visibleNodes().find((node) => node.kind === "mission") ?? visibleNodes()[0] ?? null);
  const paperCards = createMemo(() => visibleNodes().filter(isPaperNode));
  const topicCounts = createMemo(() => Object.fromEntries(TOPIC_KEYS.map((topic) => [topic, graph().nodes.filter((node) => isPaperNode(node) && topicFor(node) === topic).length])) as Record<TopicKey, number>);
  const selectedRelated = createMemo(() => selectedEdge()?.edgeType === "title_similarity_suggestion" ? suggestedPairs().find((pair) => edgeKey(pair.edge) === edgeKey(selectedEdge()!)) ?? null : null);
  const relatedForSelected = createMemo(() => {
    const selected = selectedNode();
    if (!selected || !isPaperNode(selected)) return [] as Array<{ node: LiteratureGraphNode; pair: RelatedLiteraturePair }>;
    return suggestedPairs().flatMap((pair) => {
      const otherId = pair.edge.sourceId === selected.nodeId ? pair.edge.targetId : pair.edge.targetId === selected.nodeId ? pair.edge.sourceId : null;
      const node = otherId ? graph().nodes.find((item) => item.nodeId === otherId) : null;
      return node ? [{ node, pair }] : [];
    });
  });
  const countNodes = (group: NodeGroup) => graph().nodes.filter((node) => nodeGroup(node) === group).length;
  const countEdges = (group: EdgeGroup) => graphEdges().filter((edge) => edgeGroup(edge) === group).length;
  const selectNode = (nodeId: string) => { setSelectedNodeId(nodeId || null); setSelectedEdge(null); };
  const selectEdge = (edge: LiteratureGraphEdge) => { setSelectedEdge(edge); setSelectedNodeId(null); };
  const toggleNode = (group: NodeGroup) => setNodeVisibility((current) => ({ ...current, [group]: !current[group] }));
  const toggleEdge = (group: EdgeGroup) => setEdgeVisibility((current) => ({ ...current, [group]: !current[group] }));

  return <main class="frontier-literature-workbench">
    <aside class="lens-sidebar" aria-label="\u6587\u732e\u56fe\u8c31\u63a7\u5236">
      <a class="lens-wordmark" href="/" onClick={(event) => { event.preventDefault(); props.onNavigate("discover"); }}>Cos<span>Matter</span></a>
      <p class="lens-kicker">\u6587\u732e\u5bfc\u822a\u4e2d\u5fc3 / LITERATURE NAVIGATION</p>
      <nav class="lens-navigation" aria-label="\u5de5\u4f5c\u53f0\u89c6\u56fe">
        <button type="button" onClick={() => props.onNavigate("discover")}>{zh("Discover")}</button><button type="button" onClick={() => props.onNavigate("workflow")}>{zh("Workflow")}</button><button class="active" type="button">{zh("Graph")}</button><button type="button" onClick={() => props.onNavigate("reader")}>{zh("Reading")}</button><button type="button" onClick={() => props.onNavigate("horizon")}>{zh("Horizon")}</button>
      </nav>
      <section class="lens-stats" aria-label="\u56fe\u8c31\u8986\u76d6\u60c5\u51b5">
        <div><strong>{paperCards().length}</strong><span>\u53ef\u89c1\u8bba\u6587</span></div><div><strong>{visibleEdges().length}</strong><span>\u53ef\u89c1\u5173\u8054</span></div><div><strong>{suggestedPairs().length}</strong><span>\u9898\u540d\u5efa\u8bae</span></div><div><strong>{new Set(paperCards().map((node) => node.source ?? "local")).size}</strong><span>\u6765\u6e90\u901a\u9053</span></div>
      </section>
      <section class="lens-question"><p>\u7814\u7a76\u8303\u56f4</p><strong>{props.bundle.mission.question}</strong><small>{props.bundle.mission.material} / {props.bundle.mission.property}</small></section>
      <label class="lens-search">\u68c0\u7d22\u53ef\u89c1\u56fe\u8c31<input aria-label="\u68c0\u7d22\u6587\u732e\u56fe\u8c31" value={query()} onInput={(event) => setQuery(event.currentTarget.value)} placeholder="\u9898\u540d\u6216\u6765\u6e90" /></label>
      <Show when={view() === "graph"}>
        <section class="lens-filter-section"><h2>{zh("Topic clusters")}</h2><div class="lens-topic-choices"><button type="button" classList={{ active: selectedTopic() === "all" }} onClick={() => setSelectedTopic("all")}>{zh("All")} <span>{graph().nodes.filter(isPaperNode).length}</span></button><For each={TOPIC_KEYS.filter((topic) => topicCounts()[topic])}>{(topic) => <button type="button" classList={{ active: selectedTopic() === topic }} onClick={() => setSelectedTopic(topic)}>{TOPIC_LABELS[topic]} <span>{topicCounts()[topic]}</span></button>}</For></div></section>
        <section class="lens-filter-section"><h2>{zh("Node types")}</h2><For each={NODE_GROUPS}>{(item) => <label classList={{ "is-muted": !nodeVisibility()[item.id] }}><input type="checkbox" checked={nodeVisibility()[item.id]} onChange={() => toggleNode(item.id)} /><i style={{ background: item.color }} /><strong>{item.label}</strong><span>{countNodes(item.id)}</span></label>}</For></section>
        <section class="lens-filter-section"><h2>{zh("Relation types")}</h2><For each={EDGE_GROUPS}>{(item) => <label classList={{ "is-muted": !edgeVisibility()[item.id] }}><input type="checkbox" checked={edgeVisibility()[item.id]} onChange={() => toggleEdge(item.id)} /><i style={{ background: item.color }} /><strong>{item.label}</strong><span>{countEdges(item.id)}</span></label>}</For></section>
      </Show>
      <p class="lens-boundary">Topic grouping and related-title links use display-title metadata only. They are navigation aids, never citation, content, or material-science evidence.</p>
    </aside>
    <section class="lens-main">
      <header class="lens-scope-banner"><div><span>\u6587\u732e\u661f\u56fe / SCIVERSE</span><h1>\u9650\u5b9a\u4efb\u52a1\u8303\u56f4\u7684\u63a2\u7d22</h1><p>{props.bundle.mission.scope}</p></div><div class="lens-view-tabs"><button type="button" classList={{ active: view() === "cards" }} onClick={() => setView("cards")}>{zh("Card view")}</button><button type="button" classList={{ active: view() === "graph" }} onClick={() => setView("graph")}>{zh("Relationship graph")}</button></div></header>
      <Show when={view() === "graph"} fallback={<section class="lens-card-board"><For each={paperCards()}>{(node, index) => <article><span>{String(index() + 1).padStart(2, "0")}</span><small>{TOPIC_LABELS[topicFor(node)]} / {node.source ?? "local artifact"}{node.publicationYear ? ` / ${node.publicationYear}` : ""}</small><h2>{node.label}</h2><p>{node.trustStatus.replaceAll("_", " ")}</p><button type="button" onClick={() => { selectNode(node.nodeId); setView("graph"); }}>{zh("Open in graph")}</button></article>}</For><Show when={!paperCards().length}><p class="lens-empty">No paper metadata matches the current lens.</p></Show></section>}>
        <section class="lens-canvas-region">
          <div class="lens-canvas-tools"><button type="button" onClick={() => controls()?.fit()}>{zh("Fit")}</button><button type="button" classList={{ active: focusSelection() }} disabled={!selectedNodeId()} onClick={() => setFocusSelection((value) => !value)}>{zh("Focus")}</button><button type="button" aria-label="Zoom in graph" onClick={() => controls()?.zoomIn()}>+</button><button type="button" aria-label="Zoom out graph" onClick={() => controls()?.zoomOut()}>-</button></div>
          <LiteratureGraphCanvas theme={() => props.theme} nodes={visibleNodes} edges={visibleEdges} selectedNodeId={selectedNodeId} selectedEdge={selectedEdge} onSelectNode={selectNode} onSelectEdge={selectEdge} onReady={setControls} />
          <p class="lens-footnote">Showing {visibleNodes().length} bounded nodes and {visibleEdges().length} typed relations. Select a paper to inspect and focus its immediate map neighborhood.</p>
        </section>
      </Show>
    </section>
    <aside class="lens-inspector" aria-label="Selected graph artifact">
      <Show when={selectedEdge()} fallback={<Show when={selectedNode()} fallback={<><p class="lens-kicker">{"\u68c0\u67e5\u5668"}</p><h2>{"\u9009\u62e9\u8282\u70b9\u6216\u5173\u7cfb"}</h2><p>{"\u8be6\u60c5\u7f6e\u4e8e\u56fe\u8c31\u4e4b\u5916\uff0c\u4fdd\u6301\u5173\u7cfb\u533a\u57df\u6e05\u6670\u3002"}</p></>}>
        {(node) => <><p class="lens-kicker">{"\u8282\u70b9"}</p><i style={{ background: NODE_GROUPS.find((item) => item.id === nodeGroup(node()))?.color }} /><h2>{label(node())}</h2><small>{node().kind.replaceAll("_", " ")}</small><dl><div><dt>{"\u53ef\u4fe1\u8fb9\u754c"}</dt><dd>{node().trustStatus.replaceAll("_", " ")}</dd></div><Show when={isPaperNode(node())}><div><dt>{"\u9898\u540d\u6d3e\u751f\u4e3b\u9898\u7c07"}</dt><dd>{TOPIC_LABELS[topicFor(node())]}</dd></div></Show><Show when={node().source}><div><dt>{"\u5143\u6570\u636e\u6765\u6e90"}</dt><dd>{node().source}</dd></div></Show><Show when={node().publicationYear}><div><dt>{"\u53d1\u8868\u5e74\u4efd"}</dt><dd>{node().publicationYear}</dd></div></Show><Show when={node().isContentAccessible !== undefined}><div><dt>{"\u5185\u5bb9\u8bbf\u95ee"}</dt><dd>{node().isContentAccessible ? "\u53ef\u8bbf\u95ee\u5019\u9009" : "\u4ec5\u5143\u6570\u636e"}</dd></div></Show></dl><Show when={relatedForSelected().length}><section class="lens-related-panel"><h3>{zh("Related titles")}</h3><p>{"\u4ec5\u6309\u5171\u4eab\u9898\u540d\u5173\u952e\u8bcd\u5efa\u8bae\uff1b\u4e0d\u662f\u5f15\u6587\u6216\u8bc1\u636e\u3002"}</p><For each={relatedForSelected()}>{(item) => <button type="button" onClick={() => selectNode(item.node.nodeId)}><strong>{label(item.node)}</strong><span>{"\u5171\u4eab\u8bcd\uff1a"} {item.pair.sharedTerms.join(", ")}</span></button>}</For></section></Show></>}
      </Show>}>
        {(edge) => <><p class="lens-kicker">{"\u5173\u7cfb"}</p><i style={{ background: EDGE_GROUPS.find((item) => item.id === edgeGroup(edge()))?.color }} /><h2>{edge().edgeType.replaceAll("_", " ")}</h2><small>{edge().relationSource}</small><dl><div><dt>{"\u5173\u7cfb\u8fb9\u754c"}</dt><dd>{edge().trustStatus.replaceAll("_", " ")}</dd></div><div><dt>{"\u8d77\u70b9"}</dt><dd>{edge().sourceId}</dd></div><div><dt>{"\u7ec8\u70b9"}</dt><dd>{edge().targetId}</dd></div></dl><Show when={selectedRelated()}>{(pair) => <section class="lens-related-panel"><h3>{"\u4e3a\u4f55\u5efa\u8bae\uff1f"}</h3><p>{"\u4e24\u4e2a\u663e\u793a\u9898\u540d\u5747\u5305\u542b\uff1a"} {pair().sharedTerms.join(", ")}.</p></section>}</Show></>}
      </Show>
      <p class="lens-inspector-note">{"\u5c06\u6587\u732e\u89c6\u4e3a\u8bc1\u636e\u524d\uff0c\u8bf7\u5148\u68c0\u67e5\u6eaf\u6e90\u3002"}</p>
    </aside>
  </main>;
}
