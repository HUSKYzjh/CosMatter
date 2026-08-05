import { For, Show, createMemo, createSignal } from "solid-js";
import "./graph.css";
import "./graph-lens.css";

import type { ImportedBundle, LiteratureGraphEdge, LiteratureGraphNode } from "./model";

type GraphFilter = "all" | "papers" | "evidence" | "relations" | "structure";
type GraphView = "network" | "cards" | "insights";
type NodeTone = "blue" | "teal" | "violet" | "orange" | "rose";
type EdgeGroup = "retrieval" | "evidence" | "bibliography" | "structure";
interface PositionedNode { node: LiteratureGraphNode; x: number; y: number; tone: NodeTone; }

const NODE_FILTERS: Array<{ id: GraphFilter; label: string }> = [{ id: "all", label: "All nodes" }, { id: "papers", label: "Papers" }, { id: "evidence", label: "Evidence" }, { id: "relations", label: "References" }, { id: "structure", label: "Structure" }];
const VIEW_MODES: Array<{ id: GraphView; label: string }> = [{ id: "network", label: "Network" }, { id: "cards", label: "Paper cards" }, { id: "insights", label: "Map signals" }];
const EDGE_GROUPS: Array<{ id: EdgeGroup; label: string }> = [{ id: "retrieval", label: "Discovery" }, { id: "evidence", label: "Evidence path" }, { id: "bibliography", label: "Bibliographic" }, { id: "structure", label: "Paper structure" }];

function edgeGroup(edgeType: string): EdgeGroup { if (edgeType === "retrieval_candidate") return "retrieval"; if (edgeType === "source_provenance") return "evidence"; if (["citation_reference", "algorithmic_related", "crossref_reference"].includes(edgeType)) return "bibliography"; return "structure"; }
function toneFor(kind: string): NodeTone { if (kind === "mission") return "blue"; if (["candidate_paper", "evidence_paper", "relation_root_paper", "structured_paper"].includes(kind)) return "teal"; if (kind === "accepted_evidence") return "orange"; if (["openalex_work", "crossref_work"].includes(kind)) return "violet"; return "rose"; }
function matchesFilter(node: LiteratureGraphNode, filter: GraphFilter): boolean { if (node.kind === "mission" || filter === "all") return true; if (filter === "papers") return ["candidate_paper", "evidence_paper", "relation_root_paper", "structured_paper"].includes(node.kind); if (filter === "evidence") return ["accepted_evidence", "evidence_paper"].includes(node.kind); if (filter === "relations") return ["openalex_work", "crossref_work", "relation_root_paper"].includes(node.kind); return ["paper_entity", "structured_paper"].includes(node.kind); }
function nodeTitle(node: LiteratureGraphNode): string { return node.label.length > 74 ? `${node.label.slice(0, 71)}...` : node.label; }
function nodeIsPaper(node: LiteratureGraphNode): boolean { return ["candidate_paper", "evidence_paper", "relation_root_paper", "structured_paper"].includes(node.kind); }
function positions(nodes: LiteratureGraphNode[]): PositionedNode[] {
  const mission = nodes.find((node) => node.kind === "mission");
  const groups: Array<{ kinds: string[]; x: number; y: number }> = [{ kinds: ["candidate_paper", "evidence_paper", "relation_root_paper", "structured_paper"], x: 24, y: 12 }, { kinds: ["accepted_evidence"], x: 51, y: 13 }, { kinds: ["openalex_work", "crossref_work"], x: 75, y: 12 }, { kinds: ["paper_entity"], x: 49, y: 61 }];
  const placed: PositionedNode[] = mission ? [{ node: mission, x: 4, y: 42, tone: toneFor(mission.kind) }] : [];
  groups.forEach((group) => nodes.filter((node) => group.kinds.includes(node.kind)).slice(0, 8).forEach((node, index) => placed.push({ node, x: group.x + (index % 2) * 12, y: group.y + Math.floor(index / 2) * 18, tone: toneFor(node.kind) })));
  return placed;
}

export function GraphNetwork(props: { bundle: ImportedBundle }) {
  const [view, setView] = createSignal<GraphView>("network");
  const [filter, setFilter] = createSignal<GraphFilter>("all");
  const [search, setSearch] = createSignal("");
  const [selectedId, setSelectedId] = createSignal<string | null>(null);
  const [selectedEdge, setSelectedEdge] = createSignal<LiteratureGraphEdge | null>(null);
  const [neighborsOnly, setNeighborsOnly] = createSignal(false);
  const [edgeVisibility, setEdgeVisibility] = createSignal<Record<EdgeGroup, boolean>>({ retrieval: true, evidence: true, bibliography: true, structure: true });
  const graph = () => props.bundle.literatureGraph;
  const visibleBaseNodes = createMemo(() => { const term = search().trim().toLowerCase(); return graph().nodes.filter((node) => matchesFilter(node, filter()) && (!term || `${node.label} ${node.kind} ${node.source ?? ""}`.toLowerCase().includes(term))); });
  const baseIds = createMemo(() => new Set(visibleBaseNodes().map((node) => node.nodeId)));
  const filteredEdges = createMemo(() => graph().edges.filter((edge) => edgeVisibility()[edgeGroup(edge.edgeType)] && baseIds().has(edge.sourceId) && baseIds().has(edge.targetId)));
  const visibleNodes = createMemo(() => { if (!neighborsOnly() || !selectedId()) return visibleBaseNodes().slice(0, 33); const focus = selectedId()!; const connected = new Set([focus, `mission:${props.bundle.mission.missionId}`]); filteredEdges().forEach((edge) => { if (edge.sourceId === focus) connected.add(edge.targetId); if (edge.targetId === focus) connected.add(edge.sourceId); }); return visibleBaseNodes().filter((node) => connected.has(node.nodeId)).slice(0, 33); });
  const visibleIds = createMemo(() => new Set(visibleNodes().map((node) => node.nodeId)));
  const visibleEdges = createMemo(() => filteredEdges().filter((edge) => visibleIds().has(edge.sourceId) && visibleIds().has(edge.targetId)));
  const positioned = createMemo(() => positions(visibleNodes()));
  const selectedNode = createMemo(() => graph().nodes.find((node) => node.nodeId === selectedId()) ?? visibleNodes()[0] ?? null);
  const selectedTone = createMemo(() => selectedNode() ? toneFor(selectedNode()!.kind) : "blue");
  const coordinate = (nodeId: string) => positioned().find((item) => item.node.nodeId === nodeId);
  const paperCards = createMemo(() => visibleBaseNodes().filter(nodeIsPaper));
  const sourceCoverage = createMemo(() => {
    const counts = new Map<string, number>();
    paperCards().forEach((node) => {
      const source = node.source ?? "local artifact";
      counts.set(source, (counts.get(source) ?? 0) + 1);
    });
    return [...counts.entries()].sort((left, right) => right[1] - left[1]);
  });
  const temporalCoverage = createMemo(() => {
    const years = paperCards().map((node) => node.publicationYear).filter((year): year is number => typeof year === "number").sort((left, right) => left - right);
    return years.length ? `${years[0]} - ${years[years.length - 1]}` : "year not supplied";
  });
  const countEdges = (group: EdgeGroup) => graph().edges.filter((edge) => edgeGroup(edge.edgeType) === group).length;
  const selectNode = (nodeId: string) => { setSelectedId(nodeId); setSelectedEdge(null); setView("network"); };
  const toggleGroup = (group: EdgeGroup) => setEdgeVisibility((current) => ({ ...current, [group]: !current[group] }));

  return <main class="discovery-stage graph-stage">
    <header class="stage-header"><div><p class="stage-kicker">COSMATTER / LITERATURE GRAPH</p><h1>Literature navigation graph</h1><p>One bounded research scope, three complementary views: paper cards, relationship map, and next-reading signals.</p></div><div class="stage-tools graph-mode-switch"><For each={VIEW_MODES}>{(mode) => <button type="button" classList={{ active: view() === mode.id }} onClick={() => setView(mode.id)}>{mode.label}</button>}</For></div></header>
    <section class="graph-meta"><span>Mission <strong>{props.bundle.mission.missionId}</strong></span><span>Papers <strong>{graph().nodes.filter(nodeIsPaper).length}</strong></span><span>Accepted evidence <strong>{props.bundle.evidenceCards.length}</strong></span><span>Visible edges <strong>{visibleEdges().length}</strong></span></section>
    <section class="graph-controls"><div class="filter-group"><For each={NODE_FILTERS}>{(item) => <button type="button" classList={{ selected: filter() === item.id }} onClick={() => setFilter(item.id)}>{item.label}</button>}</For></div><input aria-label="Search graph nodes" value={search()} onInput={(event) => setSearch(event.currentTarget.value)} placeholder="Filter titles, sources, node types" /></section>
    <section class="edge-filter-strip"><For each={EDGE_GROUPS}>{(group) => <button type="button" classList={{ active: edgeVisibility()[group.id] }} onClick={() => toggleGroup(group.id)}><span class={`edge-dot edge-${group.id}`} />{group.label}<small>{countEdges(group.id)}</small></button>}</For><button type="button" classList={{ active: neighborsOnly() }} disabled={!selectedId()} onClick={() => setNeighborsOnly((value) => !value)}>Focus selection</button></section>
    <Show when={view() === "network"} fallback={view() === "cards" ? <section class="graph-card-list"><For each={paperCards()}>{(node) => <article class="literature-card"><div><span>{node.kind.replaceAll("_", " ")}</span><small>{node.source ?? "local artifact"}{node.publicationYear ? ` · ${node.publicationYear}` : ""}</small></div><h2>{node.label}</h2><p>{node.trustStatus.replaceAll("_", " ")}</p><footer><em>{node.isContentAccessible === false ? "metadata only" : "source access recorded"}</em><button type="button" onClick={() => selectNode(node.nodeId)}>Inspect on graph →</button></footer></article>}</For><Show when={!paperCards().length}><p class="graph-empty">No paper metadata is currently available in this bounded mission.</p></Show></section> : <section class="graph-insights"><article><span>01</span><small>Reading surface</small><strong>{paperCards().length} paper nodes</strong><p>Start with candidates, then keep only sources that can enter the evidence-review route.</p></article><article><span>02</span><small>Evidence gate</small><strong>{graph().nodes.filter((node) => node.kind === "accepted_evidence").length} reviewed nodes</strong><p>Candidate and bibliographic links are not evidence.</p></article><article><span>03</span><small>Map extension</small><strong>{countEdges("bibliography")} bibliographic links</strong><p>Use OpenAlex and Crossref links to choose a next reading route.</p></article><article><span>04</span><small>Coverage window</small><strong>{temporalCoverage()}</strong><p>{sourceCoverage().length ? `${sourceCoverage()[0][0]} leads ${sourceCoverage()[0][1]} visible paper record(s).` : "No source metadata is currently available."}</p><p class="insight-secondary">{sourceCoverage().length} distinct source channel(s) in this bounded map.</p></article></section>}>
      <section class="graph-workspace"><div class="graph-canvas graph-literature-canvas" onClick={() => { setSelectedId(null); setSelectedEdge(null); }}><div class="graph-title"><span>LOCAL LITERATURE MAP</span><strong>Clustered by artifact role</strong><small>{graph().trustStatus.replaceAll("_", " ")}</small></div><div class="cluster-label cluster-papers">PAPERS</div><div class="cluster-label cluster-evidence">EVIDENCE</div><div class="cluster-label cluster-relations">REFERENCES</div><div class="cluster-label cluster-structure">STRUCTURE</div><Show when={positioned().length} fallback={<p class="graph-empty">Run an approved Sciverse query or import a UI bundle containing literature graph artifacts.</p>}><svg class="graph-edges" viewBox="0 0 100 100" preserveAspectRatio="none"><For each={visibleEdges()}>{(edge) => { const source = coordinate(edge.sourceId); const target = coordinate(edge.targetId); return source && target ? <path tabindex="0" class={`edge-${edgeGroup(edge.edgeType)}`} classList={{ dashed: edge.edgeType !== "source_provenance", selected: selectedEdge()?.sourceId === edge.sourceId && selectedEdge()?.targetId === edge.targetId && selectedEdge()?.edgeType === edge.edgeType }} d={`M ${source.x + 7} ${source.y + 6} L ${target.x + 7} ${target.y + 6}`} onClick={(event) => { event.stopPropagation(); setSelectedEdge(edge); setSelectedId(null); }} /> : null; }}</For></svg><For each={positioned()}>{(item) => <button type="button" class={`graph-node graph-node-${item.node.kind} tone-${item.tone}`} classList={{ active: selectedNode()?.nodeId === item.node.nodeId }} style={{ left: `${item.x}%`, top: `${item.y}%` }} onClick={(event) => { event.stopPropagation(); selectNode(item.node.nodeId); }}><span>{item.node.kind.replaceAll("_", " ")}</span><strong>{nodeTitle(item.node)}</strong><small>{item.node.source ?? item.node.trustStatus.replaceAll("_", " ")}</small></button>}</For></Show></div>
      <aside class="graph-inspector"><Show when={selectedEdge()} fallback={<Show when={selectedNode()} fallback={<><p class="stage-kicker">MAP INSPECTOR</p><h2>Choose a node or relation</h2><p>Use filters to reduce the map before comparing a local path.</p></>}>
        {(node) => <><p class="stage-kicker">NODE INSPECTOR</p><span class={`inspector-dot tone-${selectedTone()}`} /><h2>{nodeTitle(node())}</h2><small>{node().kind.replaceAll("_", " ")}</small><dl><div><dt>Trust boundary</dt><dd>{node().trustStatus.replaceAll("_", " ")}</dd></div><Show when={node().source}><div><dt>Metadata source</dt><dd>{node().source}</dd></div></Show><Show when={node().publicationYear}><div><dt>Publication year</dt><dd>{node().publicationYear}</dd></div></Show><Show when={node().isContentAccessible !== undefined}><div><dt>Content access flag</dt><dd>{node().isContentAccessible ? "accessible candidate" : "metadata only"}</dd></div></Show></dl></>}
      </Show>}>
        {(edge) => <><p class="stage-kicker">RELATION INSPECTOR</p><span class="inspector-dot tone-violet" /><h2>{edge().edgeType.replaceAll("_", " ")}</h2><small>{edge().relationSource}</small><dl><div><dt>Relation boundary</dt><dd>{edge().trustStatus.replaceAll("_", " ")}</dd></div><div><dt>Source node</dt><dd>{edge().sourceId}</dd></div><div><dt>Target node</dt><dd>{edge().targetId}</dd></div></dl></>}
      </Show><p class="graph-boundary">Links help navigate and inspect provenance. They never imply material causality or replace evidence review.</p></aside></section>
    </Show>
    <footer class="stage-note">Inspired by FrontierLens’ card-to-graph workflow, adapted to CosMatter’s evidence gate: candidates, metadata relations, and reviewed evidence remain visually and semantically distinct.</footer>
  </main>;
}