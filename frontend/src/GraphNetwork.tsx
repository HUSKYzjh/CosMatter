import { For, Show, createMemo, createSignal, lazy } from "solid-js";

import type { GraphCanvasControls } from "./LiteratureGraphCanvas";
import type { ImportedBundle, LiteratureGraphEdge, LiteratureGraphNode } from "./model";
import "./frontier-graph.css";

const LiteratureGraphCanvas = lazy(() => import("./LiteratureGraphCanvas").then((module) => ({ default: module.LiteratureGraphCanvas })));

type GraphView = "graph" | "cards";
type NodeGroup = "mission" | "papers" | "evidence" | "references" | "structure";
type EdgeGroup = "discovery" | "evidence" | "bibliography" | "structure";

type NavigateView = "discover" | "workflow" | "reader" | "horizon";

const NODE_GROUPS: Array<{ id: NodeGroup; label: string; color: string }> = [
  { id: "mission", label: "Mission scope", color: "var(--blue)" },
  { id: "papers", label: "Papers", color: "var(--teal)" },
  { id: "evidence", label: "Accepted evidence", color: "var(--orange)" },
  { id: "references", label: "Reference metadata", color: "var(--violet)" },
  { id: "structure", label: "Structure / collections", color: "var(--rose)" },
];
const EDGE_GROUPS: Array<{ id: EdgeGroup; label: string; color: string }> = [
  { id: "discovery", label: "Discovery route", color: "var(--teal)" },
  { id: "evidence", label: "Evidence provenance", color: "var(--orange)" },
  { id: "bibliography", label: "Bibliographic links", color: "var(--violet)" },
  { id: "structure", label: "Document / collection links", color: "var(--rose)" },
];

function nodeGroup(node: LiteratureGraphNode): NodeGroup {
  if (node.kind === "mission") return "mission";
  if (["candidate_paper", "evidence_paper", "relation_root_paper", "structured_paper"].includes(node.kind)) return "papers";
  if (node.kind === "accepted_evidence") return "evidence";
  if (["openalex_work", "crossref_work"].includes(node.kind)) return "references";
  return "structure";
}
function edgeGroup(edge: LiteratureGraphEdge): EdgeGroup {
  if (edge.edgeType === "retrieval_candidate") return "discovery";
  if (edge.edgeType === "source_provenance") return "evidence";
  if (["citation_reference", "algorithmic_related", "crossref_reference"].includes(edge.edgeType)) return "bibliography";
  return "structure";
}
function isPaper(node: LiteratureGraphNode): boolean { return nodeGroup(node) === "papers"; }
function label(node: LiteratureGraphNode): string { return node.label.length > 92 ? `${node.label.slice(0, 89).trim()}…` : node.label; }

export function GraphNetwork(props: { bundle: ImportedBundle; theme: string; onNavigate: (view: NavigateView) => void }) {
  const [view, setView] = createSignal<GraphView>("graph");
  const [query, setQuery] = createSignal("");
  const [nodeVisibility, setNodeVisibility] = createSignal<Record<NodeGroup, boolean>>({ mission: true, papers: true, evidence: true, references: true, structure: true });
  const [edgeVisibility, setEdgeVisibility] = createSignal<Record<EdgeGroup, boolean>>({ discovery: true, evidence: true, bibliography: true, structure: true });
  const [selectedNodeId, setSelectedNodeId] = createSignal<string | null>(null);
  const [selectedEdge, setSelectedEdge] = createSignal<LiteratureGraphEdge | null>(null);
  const [controls, setControls] = createSignal<GraphCanvasControls | null>(null);
  const graph = () => props.bundle.literatureGraph;
  const visibleNodes = createMemo(() => {
    const term = query().trim().toLocaleLowerCase();
    return graph().nodes.filter((node) => nodeVisibility()[nodeGroup(node)] && (!term || `${node.label} ${node.source ?? ""} ${node.kind}`.toLocaleLowerCase().includes(term)));
  });
  const visibleIds = createMemo(() => new Set(visibleNodes().map((node) => node.nodeId)));
  const visibleEdges = createMemo(() => graph().edges.filter((edge) => edgeVisibility()[edgeGroup(edge)] && visibleIds().has(edge.sourceId) && visibleIds().has(edge.targetId)));
  const selectedNode = createMemo(() => graph().nodes.find((node) => node.nodeId === selectedNodeId()) ?? visibleNodes().find((node) => node.kind === "mission") ?? visibleNodes()[0] ?? null);
  const paperCards = createMemo(() => visibleNodes().filter(isPaper));
  const countNodes = (group: NodeGroup) => graph().nodes.filter((node) => nodeGroup(node) === group).length;
  const countEdges = (group: EdgeGroup) => graph().edges.filter((edge) => edgeGroup(edge) === group).length;
  const selectNode = (nodeId: string) => { setSelectedNodeId(nodeId || null); setSelectedEdge(null); };
  const selectEdge = (edge: LiteratureGraphEdge) => { setSelectedEdge(edge); setSelectedNodeId(null); };
  const toggleNode = (group: NodeGroup) => setNodeVisibility((current) => ({ ...current, [group]: !current[group] }));
  const toggleEdge = (group: EdgeGroup) => setEdgeVisibility((current) => ({ ...current, [group]: !current[group] }));

  return <main class="frontier-literature-workbench">
    <aside class="lens-sidebar" aria-label="Literature graph controls">
      <a class="lens-wordmark" href="/" onClick={(event) => { event.preventDefault(); props.onNavigate("discover"); }}>◈ Cos<span>Matter</span></a>
      <p class="lens-kicker">MATERIALS / LITERATURE</p>
      <nav class="lens-navigation" aria-label="Workbench views">
        <button type="button" onClick={() => props.onNavigate("discover")}>Discover</button>
        <button type="button" onClick={() => props.onNavigate("workflow")}>Workflow</button>
        <button class="active" type="button">Graph</button>
        <button type="button" onClick={() => props.onNavigate("reader")}>Reading</button>
        <button type="button" onClick={() => props.onNavigate("horizon")}>Horizon</button>
      </nav>
      <section class="lens-stats" aria-label="Graph coverage">
        <div><strong>{paperCards().length}</strong><span>visible papers</span></div>
        <div><strong>{visibleEdges().length}</strong><span>visible links</span></div>
        <div><strong>{props.bundle.evidenceCards.length}</strong><span>accepted evidence</span></div>
        <div><strong>{new Set(paperCards().map((node) => node.source ?? "local")).size}</strong><span>source channels</span></div>
      </section>
      <section class="lens-question"><p>Research scope</p><strong>{props.bundle.mission.question}</strong><small>{props.bundle.mission.material} · {props.bundle.mission.property}</small></section>
      <label class="lens-search">Search visible map<input aria-label="Search literature graph" value={query()} onInput={(event) => setQuery(event.currentTarget.value)} placeholder="titles or sources" /></label>
      <Show when={view() === "graph"}>
        <section class="lens-filter-section"><h2>Node types</h2><For each={NODE_GROUPS}>{(item) => <label classList={{ "is-muted": !nodeVisibility()[item.id] }}><input type="checkbox" checked={nodeVisibility()[item.id]} onChange={() => toggleNode(item.id)} /><i style={{ background: item.color }} /><strong>{item.label}</strong><span>{countNodes(item.id)}</span></label>}</For></section>
        <section class="lens-filter-section"><h2>Relation types</h2><For each={EDGE_GROUPS}>{(item) => <label classList={{ "is-muted": !edgeVisibility()[item.id] }}><input type="checkbox" checked={edgeVisibility()[item.id]} onChange={() => toggleEdge(item.id)} /><i style={{ background: item.color }} /><strong>{item.label}</strong><span>{countEdges(item.id)}</span></label>}</For></section>
      </Show>
      <p class="lens-boundary">Map facts are task-scoped metadata and reviewed artifacts. A link is never a material-science conclusion.</p>
    </aside>
    <section class="lens-main">
      <header class="lens-scope-banner"><div><span>SCIVERSE-STYLE LITERATURE MAP</span><h1>Query-scoped exploration</h1><p>{props.bundle.mission.scope}</p></div><div class="lens-view-tabs"><button type="button" classList={{ active: view() === "cards" }} onClick={() => setView("cards")}>Card view</button><button type="button" classList={{ active: view() === "graph" }} onClick={() => setView("graph")}>Relationship graph</button></div></header>
      <Show when={view() === "graph"} fallback={<section class="lens-card-board"><For each={paperCards()}>{(node, index) => <article><span>{String(index() + 1).padStart(2, "0")}</span><small>{node.source ?? "local artifact"}{node.publicationYear ? ` · ${node.publicationYear}` : ""}</small><h2>{node.label}</h2><p>{node.trustStatus.replaceAll("_", " ")}</p><button type="button" onClick={() => { selectNode(node.nodeId); setView("graph"); }}>Open in graph →</button></article>}</For><Show when={!paperCards().length}><p class="lens-empty">No paper metadata matches the current lens.</p></Show></section>}>
        <section class="lens-canvas-region">
          <div class="lens-canvas-tools"><button type="button" onClick={() => controls()?.fit()}>Fit</button><button type="button" aria-label="Zoom in graph" onClick={() => controls()?.zoomIn()}>+</button><button type="button" aria-label="Zoom out graph" onClick={() => controls()?.zoomOut()}>−</button></div>
          <LiteratureGraphCanvas theme={() => props.theme} nodes={visibleNodes} edges={visibleEdges} selectedNodeId={selectedNodeId} selectedEdge={selectedEdge} onSelectNode={selectNode} onSelectEdge={selectEdge} onReady={setControls} />
          <p class="lens-footnote">Showing {visibleNodes().length} bounded nodes and {visibleEdges().length} typed relations. Pan, zoom, or narrow the lens from the sidebar.</p>
        </section>
      </Show>
    </section>
    <aside class="lens-inspector" aria-label="Selected graph artifact">
      <Show when={selectedEdge()} fallback={<Show when={selectedNode()} fallback={<><p class="lens-kicker">INSPECTOR</p><h2>Choose a node or relation</h2><p>Details stay outside the map so the relationship field remains readable.</p></>}>
        {(node) => <><p class="lens-kicker">NODE</p><i style={{ background: NODE_GROUPS.find((item) => item.id === nodeGroup(node()))?.color }} /><h2>{label(node())}</h2><small>{node().kind.replaceAll("_", " ")}</small><dl><div><dt>Trust boundary</dt><dd>{node().trustStatus.replaceAll("_", " ")}</dd></div><Show when={node().source}><div><dt>Metadata source</dt><dd>{node().source}</dd></div></Show><Show when={node().publicationYear}><div><dt>Publication year</dt><dd>{node().publicationYear}</dd></div></Show><Show when={node().isContentAccessible !== undefined}><div><dt>Content access</dt><dd>{node().isContentAccessible ? "accessible candidate" : "metadata only"}</dd></div></Show></dl></>}
      </Show>}>
        {(edge) => <><p class="lens-kicker">RELATION</p><i style={{ background: EDGE_GROUPS.find((item) => item.id === edgeGroup(edge()))?.color }} /><h2>{edge().edgeType.replaceAll("_", " ")}</h2><small>{edge().relationSource}</small><dl><div><dt>Relation boundary</dt><dd>{edge().trustStatus.replaceAll("_", " ")}</dd></div><div><dt>From</dt><dd>{edge().sourceId}</dd></div><div><dt>To</dt><dd>{edge().targetId}</dd></div></dl></>}
      </Show>
      <p class="lens-inspector-note">Inspect provenance before treating any document as evidence.</p>
    </aside>
  </main>;
}