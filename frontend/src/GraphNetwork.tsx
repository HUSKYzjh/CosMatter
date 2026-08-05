import { For, Show, createMemo, createSignal } from "solid-js";
import "./graph.css";

import type { ImportedBundle, LiteratureGraphNode } from "./model";

type GraphFilter = "all" | "papers" | "evidence" | "relations" | "structure";
type NodeTone = "blue" | "teal" | "violet" | "orange" | "rose";

interface PositionedNode { node: LiteratureGraphNode; x: number; y: number; tone: NodeTone; }

const FILTERS: Array<{ id: GraphFilter; label: string }> = [
  { id: "all", label: "All" },
  { id: "papers", label: "Papers" },
  { id: "evidence", label: "Accepted evidence" },
  { id: "relations", label: "Citation metadata" },
  { id: "structure", label: "Paper structure" },
];

function toneFor(kind: string): NodeTone {
  if (kind === "mission") return "blue";
  if (kind === "candidate_paper" || kind === "evidence_paper" || kind === "relation_root_paper" || kind === "structured_paper") return "teal";
  if (kind === "accepted_evidence") return "orange";
  if (kind === "openalex_work" || kind === "crossref_work") return "violet";
  return "rose";
}

function matchesFilter(node: LiteratureGraphNode, filter: GraphFilter): boolean {
  if (node.kind === "mission") return true;
  if (filter === "all") return true;
  if (filter === "papers") return ["candidate_paper", "evidence_paper", "relation_root_paper", "structured_paper"].includes(node.kind);
  if (filter === "evidence") return node.kind === "accepted_evidence" || node.kind === "evidence_paper";
  if (filter === "relations") return node.kind === "openalex_work" || node.kind === "crossref_work" || node.kind === "relation_root_paper";
  return node.kind === "paper_entity" || node.kind === "structured_paper";
}

function nodeTitle(node: LiteratureGraphNode): string {
  return node.label.length > 74 ? `${node.label.slice(0, 71)}...` : node.label;
}

function positions(nodes: LiteratureGraphNode[]): PositionedNode[] {
  const mission = nodes.find((node) => node.kind === "mission");
  const remaining = nodes.filter((node) => node !== mission);
  const placed: PositionedNode[] = mission ? [{ node: mission, x: 8, y: 42, tone: toneFor(mission.kind) }] : [];
  remaining.forEach((node, index) => {
    const column = index % 4;
    const row = Math.floor(index / 4);
    placed.push({ node, x: 29 + column * 19, y: 13 + (row % 4) * 22, tone: toneFor(node.kind) });
  });
  return placed;
}

export function GraphNetwork(props: { bundle: ImportedBundle }) {
  const [filter, setFilter] = createSignal<GraphFilter>("all");
  const [search, setSearch] = createSignal("");
  const [selectedId, setSelectedId] = createSignal<string | null>(null);
  const graph = () => props.bundle.literatureGraph;
  const visibleNodes = createMemo(() => {
    const term = search().trim().toLowerCase();
    return graph().nodes.filter((node) => matchesFilter(node, filter()) && (!term || `${node.label} ${node.kind} ${node.source ?? ""}`.toLowerCase().includes(term))).slice(0, 24);
  });
  const positioned = createMemo(() => positions(visibleNodes()));
  const visibleIds = createMemo(() => new Set(visibleNodes().map((node) => node.nodeId)));
  const visibleEdges = createMemo(() => graph().edges.filter((edge) => visibleIds().has(edge.sourceId) && visibleIds().has(edge.targetId)));
  const selected = createMemo(() => graph().nodes.find((node) => node.nodeId === selectedId()) ?? visibleNodes()[0] ?? null);
  const selectedTone = createMemo(() => selected() ? toneFor(selected()!.kind) : "blue");
  const coordinate = (nodeId: string) => positioned().find((item) => item.node.nodeId === nodeId);

  return (
    <main class="discovery-stage graph-stage">
      <header class="stage-header">
        <div><p class="stage-kicker">COSMATTER / LITERATURE GRAPH</p><h1>Literature navigation graph</h1><p>Candidate metadata, accepted evidence, and bibliographic links stay visibly separated. A graph edge is not a scientific conclusion.</p></div>
        <div class="stage-tools"><span>{graph().nodes.length} nodes</span><span>{graph().edges.length} edges</span></div>
      </header>
      <section class="graph-meta" aria-label="Literature graph summary">
        <span>Mission <strong>{props.bundle.mission.missionId}</strong></span>
        <span>Approved evidence <strong>{props.bundle.evidenceCards.length}</strong></span>
        <span>OpenAlex <strong>{props.bundle.literatureRelations?.edgeCount ?? 0}</strong></span>
        <span>Crossref <strong>{props.bundle.crossrefRelations?.edgeCount ?? 0}</strong></span>
      </section>
      <section class="graph-controls" aria-label="Literature graph controls">
        <div class="filter-group"><For each={FILTERS}>{(item) => <button type="button" classList={{ selected: filter() === item.id }} onClick={() => setFilter(item.id)}>{item.label}</button>}</For></div>
        <input aria-label="Search graph nodes" value={search()} onInput={(event) => setSearch(event.currentTarget.value)} placeholder="Filter titles, sources, node types" />
      </section>
      <section class="graph-workspace" aria-label="Literature relationship network">
        <div class="graph-canvas graph-literature-canvas">
          <div class="graph-title"><span>LOCAL LITERATURE MAP</span><strong>Bounded documents and relation metadata</strong><small>{graph().trustStatus.replaceAll("_", " ")}</small></div>
          <Show when={positioned().length} fallback={<p class="graph-empty">Run an approved Sciverse query or import a UI bundle containing literature graph artifacts.</p>}>
            <svg class="graph-edges" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
              <For each={visibleEdges()}>{(edge) => {
                const source = coordinate(edge.sourceId); const target = coordinate(edge.targetId);
                return source && target ? <path classList={{ dashed: edge.edgeType !== "source_provenance" }} d={`M ${source.x + 7} ${source.y + 6} L ${target.x + 7} ${target.y + 6}`} /> : null;
              }}</For>
            </svg>
            <For each={positioned()}>{(item) => <button type="button" class={`graph-node graph-node-${item.node.kind} tone-${item.tone}`} classList={{ active: selected()?.nodeId === item.node.nodeId }} style={{ left: `${item.x}%`, top: `${item.y}%` }} onClick={() => setSelectedId(item.node.nodeId)}><span>{item.node.kind.replaceAll("_", " ")}</span><strong>{nodeTitle(item.node)}</strong><small>{item.node.source ?? item.node.trustStatus.replaceAll("_", " ")}</small></button>}</For>
          </Show>
        </div>
        <aside class="graph-inspector" aria-label="Selected literature graph node">
          <Show when={selected()} fallback={<><p class="stage-kicker">NODE INSPECTOR</p><h2>No node selected</h2><p>Use filters or run a bounded literature search to populate the graph.</p></>}>
            {(node) => <><p class="stage-kicker">NODE INSPECTOR</p><span class={`inspector-dot tone-${selectedTone()}`} /><h2>{nodeTitle(node())}</h2><small>{node().kind.replaceAll("_", " ")}</small><dl><div><dt>Trust boundary</dt><dd>{node().trustStatus.replaceAll("_", " ")}</dd></div><Show when={node().source}><div><dt>Metadata source</dt><dd>{node().source}</dd></div></Show><Show when={node().publicationYear}><div><dt>Publication year</dt><dd>{node().publicationYear}</dd></div></Show><Show when={node().isContentAccessible !== undefined}><div><dt>Content access flag</dt><dd>{node().isContentAccessible ? "accessible candidate" : "metadata only"}</dd></div></Show><Show when={node().entityKind}><div><dt>Reviewed entity kind</dt><dd>{node().entityKind}</dd></div></Show></dl><p class="graph-boundary">Bibliographic and retrieval relations guide navigation only. Evidence nodes are present only after review.</p></>}
          </Show>
        </aside>
      </section>
      <footer class="stage-note">Visible graph types: retrieval candidate, accepted evidence source, OpenAlex relation metadata, Crossref reference metadata, and reviewer-recorded paper structure. None implies material causality by itself.</footer>
    </main>
  );
}