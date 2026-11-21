import cytoscape, { type Core, type ElementDefinition, type NodeSingular } from "cytoscape";
import { createEffect, createSignal, onCleanup, onMount, untrack } from "solid-js";

import { TOPIC_LABELS, isPaperNode, topicFor } from "./literatureTopology";
import { displayPaperTitle } from "./paperTitle";
import type { LiteratureGraphEdge, LiteratureGraphNode } from "./model";
import { zh } from "./zh";

type BaseCluster = "Mission" | "Papers" | "Evidence" | "Conditions" | "References" | "Structure";
type Cluster = string;

export interface GraphCanvasControls {
  fit: () => void;
  zoomIn: () => void;
  zoomOut: () => void;
}

export interface LiteratureGraphCanvasProps {
  theme: () => string;
  nodes: () => LiteratureGraphNode[];
  edges: () => LiteratureGraphEdge[];
  selectedNodeId: () => string | null;
  selectedEdge: () => LiteratureGraphEdge | null;
  onSelectNode: (nodeId: string) => void;
  onSelectEdge: (edge: LiteratureGraphEdge) => void;
  onReady: (controls: GraphCanvasControls | null) => void;
  paperStates: () => Record<string, string>;
}

const COLORS: Record<BaseCluster, string> = {
  Mission: "#2f6fec",
  Papers: "#0f8a83",
  Evidence: "#c97a18",
  Conditions: "#b87818",
  References: "#7442db",
  Structure: "#ba4e70",
};

const topicCaptions: Record<ReturnType<typeof topicFor>, string> = {
  ferroelectric: "铁电性", piezoelectric: "压电性", thin_film: "薄膜与界面",
  domain_microstructure: "畴与微结构", simulation_method: "模拟与方法", other: "其他论文",
};

function baseClusterOf(node: LiteratureGraphNode): BaseCluster {
  if (node.kind === "mission") return "Mission";
  if (isPaperNode(node)) return "Papers";
  if (["accepted_evidence", "evidence_card", "research_gap_candidate"].includes(node.kind)) return "Evidence";
  if (node.kind === "condition_cluster") return "Conditions";
  if (["openalex_work", "crossref_work", "citation_work"].includes(node.kind)) return "References";
  return "Structure";
}

function clusterOf(node: LiteratureGraphNode): Cluster {
  if (isPaperNode(node)) return topicFor(node);
  return node.kind === "research_gap_candidate" ? "Gaps" : baseClusterOf(node);
}

// Topic ink belongs to the map region. The ring around a paper continues to
// encode its workflow state, including when two topics share the same state.
function regionColor(node: LiteratureGraphNode, colors: Record<BaseCluster, string>): string {
  if (!isPaperNode(node)) return colors[baseClusterOf(node)];
  const topicColors = {
    ferroelectric: colors.Papers, piezoelectric: colors.Conditions, thin_film: colors.Mission,
    domain_microstructure: colors.References, simulation_method: colors.Evidence, other: colors.Structure,
  };
  return topicColors[topicFor(node)];
}

function clusterCaption(node: LiteratureGraphNode): string {
  if (isPaperNode(node)) {
    const topic = topicFor(node);
    return zh(topic === "other" ? "Other papers" : TOPIC_LABELS[topic], topicCaptions[topic]);
  }
  switch (clusterOf(node)) {
    case "Mission": return zh("Research question", "研究问题");
    case "Evidence": return zh("Evidence cards", "证据卡");
    case "Gaps": return zh("Proposed gaps", "待审核问题");
    case "Conditions": return zh("Conditions", "实验条件");
    case "References": return zh("References", "引文");
    default: return zh("Document structure", "文献结构");
  }
}

function flightRole(edge: LiteratureGraphEdge): "formation" | "evidence" | "condition" | "bibliography" | "suggestion" | "structure" {
  if (edge.edgeType === "retrieval_candidate") return "formation";
  if (["source_provenance", "gap_evidence_basis"].includes(edge.edgeType)) return "evidence";
  if (["condition_support", "condition_contradiction"].includes(edge.edgeType)) return "condition";
  if (["citation_reference", "citation_cited_by", "algorithmic_related", "crossref_reference"].includes(edge.edgeType)) return "bibliography";
  if (edge.edgeType === "title_similarity_suggestion") return "suggestion";
  return "structure";
}

function edgeColor(edge: LiteratureGraphEdge, colors: Record<BaseCluster, string>): string {
  if (["source_provenance", "gap_evidence_basis"].includes(edge.edgeType)) return colors.Evidence;
  if (["condition_support", "condition_contradiction"].includes(edge.edgeType)) return colors.Conditions;
  if (["citation_reference", "citation_cited_by", "algorithmic_related", "crossref_reference"].includes(edge.edgeType)) return colors.References;
  if (edge.edgeType === "title_similarity_suggestion") return colors.Papers;
  if (edge.edgeType === "retrieval_candidate") return colors.Papers;
  return colors.Structure;
}

function degreeMap(edges: LiteratureGraphEdge[]): Map<string, number> {
  const degrees = new Map<string, number>();
  edges.forEach((edge) => {
    degrees.set(edge.sourceId, (degrees.get(edge.sourceId) ?? 0) + 1);
    degrees.set(edge.targetId, (degrees.get(edge.targetId) ?? 0) + 1);
  });
  return degrees;
}

const chartFont = "Segoe UI, Microsoft YaHei, sans-serif";

interface Box { x: number; y: number; w: number; h: number }
interface Point { x: number; y: number }
interface AtlasGroup { weight: number }
type LabelSide = "below" | "above" | "right" | "left" | "below-start" | "below-end" | "above-start" | "above-end";

function edgeId(edge: LiteratureGraphEdge): string {
  return JSON.stringify(["edge", edge.sourceId, edge.targetId, edge.edgeType, edge.relationSource]);
}

// Recursively split the available rectangle by paper counts. Unlike fixed sector
// centres, a large topic cannot run into a smaller neighbour as the map fills.
function groupCells(groups: AtlasGroup[], area: Box): Box[] {
  if (groups.length === 1) return [area];
  const total = groups.reduce((sum, group) => sum + group.weight, 0);
  let count = 1;
  let weight = groups[0].weight;
  while (count < groups.length - 1 && Math.abs(weight + groups[count].weight - total / 2) < Math.abs(weight - total / 2)) {
    weight += groups[count++].weight;
  }
  const share = weight / total;
  const wide = area.w >= area.h;
  const first = wide ? { ...area, w: area.w * share } : { ...area, h: area.h * share };
  const second = wide ? { ...area, x: area.x + first.w, w: area.w - first.w } : { ...area, y: area.y + first.h, h: area.h - first.h };
  return [...groupCells(groups.slice(0, count), first), ...groupCells(groups.slice(count), second)];
}

function overlaps(a: Box, b: Box): boolean {
  return a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y;
}

function labelBox(p: Point, width: number, height: number, side: LabelSide): Box {
  const inset = 12;
  if (side === "right") return { x: p.x + inset, y: p.y - height / 2, w: width, h: height };
  if (side === "left") return { x: p.x - inset - width, y: p.y - height / 2, w: width, h: height };
  const x = side.endsWith("-start") ? p.x : side.endsWith("-end") ? p.x - width : p.x - width / 2;
  return { x, y: side.startsWith("below") ? p.y + inset : p.y - inset - height, w: width, h: height };
}

function briefLabel(text: string, width: number, measure: (value: string) => number): string {
  const full = text.replace(/\s+/gu, " ").trim();
  if (measure(full) <= width) return full;
  let prefix = "";
  for (const char of full) {
    if (measure(prefix + char + "…") > width) break;
    prefix += char;
  }
  return prefix.trimEnd() + "…";
}

interface RouteObstacle { id: string; point: Point; radius: number; label?: Box }

// Each curve sample only needs the markers/titles that cover its local cell.
function indexObstacles(obstacles: RouteObstacle[], area: Box) {
  const size = 40, columns = Math.ceil(area.w / size), rows = Math.ceil(area.h / size);
  const cells = Array.from({ length: columns * rows }, () => [] as RouteObstacle[]);
  for (const item of obstacles) {
    const { x, y } = item.point, pad = item.radius + 3, label = item.label;
    const left = Math.max(0, Math.floor(Math.min(x - pad, label ? label.x - 2 : x) / size));
    const right = Math.min(columns - 1, Math.floor(Math.max(x + pad, label ? label.x + label.w + 2 : x) / size));
    const top = Math.max(0, Math.floor(Math.min(y - pad, label ? label.y - 2 : y) / size));
    const bottom = Math.min(rows - 1, Math.floor(Math.max(y + pad, label ? label.y + label.h + 2 : y) / size));
    for (let row = top; row <= bottom; row++) {
      for (let column = left; column <= right; column++) cells[row * columns + column].push(item);
    }
  }
  return (x: number, y: number) => cells[Math.floor(y / size) * columns + Math.floor(x / size)];
}

function evidenceBend(edge: LiteratureGraphEdge, source: Point, target: Point, area: Box, nearby: ReturnType<typeof indexObstacles>): number {
  const dx = target.x - source.x, dy = target.y - source.y;
  const length = Math.hypot(dx, dy);
  if (length < 1) return 0;
  const normal = { x: -dy / length, y: dx / length };
  let best = 0, bestScore = -Infinity;
  // Test the straight path first. A small bend should clear unrelated markers
  // and titles before a stronger detour is considered.
  for (const bend of [0, 24, -24, 48, -48, 80, -80, 120, -120]) {
    const steps = Math.ceil((length + Math.abs(bend)) / 6);
    let clearance = Infinity;
    let crossesTitle = false;
    for (let i = 1; i < steps; i++) {
      const t = i / steps;
      const arc = 2 * t * (1 - t) * bend;
      const x = source.x + t * dx + normal.x * arc;
      const y = source.y + t * dy + normal.y * arc;
      if (x < 2 || y < 2 || x > area.w - 2 || y > area.h - 2) { clearance = -Infinity; break; }
      for (const other of nearby(x, y)) {
        if (other.id === edge.sourceId || other.id === edge.targetId) continue;
        const gapX = x - other.point.x, gapY = y - other.point.y;
        const squared = gapX * gapX + gapY * gapY;
        if (squared < (other.radius + 3) ** 2) clearance = Math.min(clearance, Math.sqrt(squared) - other.radius);
        const box = other.label;
        if (box && x >= box.x - 2 && x <= box.x + box.w + 2 && y >= box.y - 2 && y <= box.y + box.h + 2) crossesTitle = true;
      }
    }
    // Three pixels cover the sampling interval. Prioritise the marker over its title.
    if (clearance >= 3 && !crossesTitle) return bend;
    const score = Math.min(clearance, 3) - Number(crossesTitle) * .5;
    if (score > bestScore) { best = bend; bestScore = score; }
  }
  return best;
}

function atlasLayout(nodes: LiteratureGraphNode[], edges: LiteratureGraphEdge[], width: number, height: number, compact: boolean, colors: Record<BaseCluster, string>) {
  const groups = new Map<string, LiteratureGraphNode[]>();
  for (const node of nodes) {
    const key = clusterOf(node);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(node);
  }
  const rank = (node: LiteratureGraphNode) => {
    const paperFirst = compact ? ["Papers", "Evidence", "Mission"] : ["Mission", "Papers", "Evidence"];
    const index = paperFirst.indexOf(baseClusterOf(node));
    return index < 0 ? 3 : index;
  };
  const ordered = [...groups.values()].sort((a, b) => rank(a[0]) - rank(b[0]) || clusterOf(a[0]).localeCompare(clusterOf(b[0])));
  const weights = ordered.map(members => ({ weight: Math.sqrt(members.length) + .7 }));
  const area = { x: 0, y: 0, w: width, h: height };
  const denseNarrow = compact && nodes.length > 16;
  const totalWeight = weights.reduce((sum, group) => sum + group.weight, 0);
  const bandMinimum = Math.min(47, height / Math.max(1, ordered.length));
  let bandTop = 0;
  const cells = denseNarrow ? weights.map(group => {
    const band = { ...area, y: bandTop, h: bandMinimum + (height - bandMinimum * ordered.length) * group.weight / totalWeight };
    bandTop += band.h;
    return band;
  }) : ordered.length ? groupCells(weights, area) : [];
  const occupied: Box[] = [];
  const positions = new Map<string, Point>();
  const captions: ElementDefinition[] = [];
  const context = document.createElement("canvas").getContext("2d")!;
  const measure = (text: string) => context.measureText(text).width;
  const fontSize = compact ? 12 : 13;
  const titleWidth = compact ? 103 : 150;
  const prefixes = new Map<string, number>();
  const titles = new Map<string, string>();
  context.font = `600 ${fontSize}px ${chartFont}`;
  for (const node of nodes) {
    const title = isPaperNode(node) ? displayPaperTitle(node.label) : node.label;
    titles.set(node.nodeId, title);
    const prefix = briefLabel(title, titleWidth, measure);
    prefixes.set(prefix, (prefixes.get(prefix) ?? 0) + 1);
  }
  const nodeLabel = (node: LiteratureGraphNode, available: number) => {
    const title = titles.get(node.nodeId)!;
    const prefix = briefLabel(title, titleWidth, measure);
    if (prefixes.get(prefix) === 1) return briefLabel(title, available, measure);
    const id = node.nodeId.replace(/^[^:]+:/u, "");
    const hint = id.length > 9 ? "…" + id.slice(-6) : id;
    return briefLabel(hint + " · " + title, available, measure);
  };
  const labels = new Map<string, { text: string; visible: boolean; side: LabelSide }>();
  const bounds = new Map<string, Box>();
  const degrees = degreeMap(edges);
  const byImportance = ordered.map(members => [...members].sort((a, b) =>
    (degrees.get(b.nodeId) ?? 0) - (degrees.get(a.nodeId) ?? 0) || a.label.localeCompare(b.label)));
  ordered.forEach((members, index) => {
    const cell = cells[index];
    const cap = members[0];
    context.font = `600 12px ${chartFont}`;
    const count = ` · ${members.length}`;
    const title = briefLabel(clusterCaption(cap), Math.max(18, cell.w - 32 - measure(count)), measure) + count;
    const inset = denseNarrow ? 2 : 3;
    const panel = { x: cell.x + inset, y: cell.y + inset, w: Math.max(1, cell.w - 2 * inset), h: Math.max(1, cell.h - 2 * inset) };
    const capPos = { x: panel.x + 9, y: panel.y + 11 };
    const groupId = clusterOf(cap);
    bounds.set(groupId, panel);
    captions.push({ data: { id: `sector:${index}:${groupId}`, isCluster: "yes", region: groupId, label: title,
      color: regionColor(cap, colors), width: panel.w, height: panel.h, labelInset: 9 - panel.w },
      position: { x: panel.x + panel.w / 2, y: panel.y + panel.h / 2 }, selectable: false, grabbable: false });
    occupied.push({ x: capPos.x - 4, y: capPos.y - 10, w: measure(title) + 20, h: 22 });
    let groupNodes = members;
    let room = { x: cell.x + 10, y: cell.y + 26, w: Math.max(4, cell.w - 20), h: Math.max(6, cell.h - 31) };
    if (denseNarrow) {
      // Each topic keeps one title even in a 49-paper overview on a phone.
      // Its label occupies the left column; the remaining markers use the right.
      const representative = byImportance[index][0];
      const clearance = representative.kind === "mission" ? 16 : 10;
      const point = { x: panel.x + clearance + 4,
        y: Math.min(panel.y + panel.h - clearance, Math.max(capPos.y + 18, cell.y + cell.h * .66)) };
      const labelColumn = Math.min(118, cell.w * .45);
      context.font = `600 ${fontSize}px ${chartFont}`;
      const text = nodeLabel(representative, labelColumn - 29);
      positions.set(representative.nodeId, point);
      labels.set(representative.nodeId, { text, visible: true, side: "right" });
      occupied.push(labelBox(point, measure(text) + 7, fontSize + 5, "right"));
      groupNodes = members.filter(member => member !== representative);
      room = { x: cell.x + labelColumn + 8, y: cell.y + 6, w: cell.w - labelColumn - 14, h: Math.max(16, cell.h - 10) };
    }
    if (!groupNodes.length) return;
    const columns = Math.max(1, Math.min(groupNodes.length, Math.round(Math.sqrt(groupNodes.length * room.w / room.h))));
    const rows = Math.ceil(groupNodes.length / columns);
    groupNodes.forEach((member, i) => {
      const row = Math.floor(i / columns);
      const rowLength = Math.min(columns, groupNodes.length - row * columns);
      // Stagger neighbouring rows slightly to separate parallel paths at their endpoints.
      const x = room.x + ((i % columns + 0.5 + (columns > 1 && rowLength > 1 ? (row % 2 ? .12 : -.12) : 0)) / rowLength) * room.w;
      const stagger = columns > 1 && (!denseNarrow || rows < 3) ? ((i % columns + index) % 3 - 1) * .12 : 0;
      const y = room.y + (row + .44 + stagger) * room.h / rows;
      positions.set(member.nodeId, { x, y });
      occupied.push({ x: x - 10, y: y - 10, w: 20, h: 20 });
    });
  });

  context.font = `600 ${fontSize}px ${chartFont}`;
  // Give every topic a first label before spending the remaining space on its other papers.
  const max = Math.max(0, ...byImportance.map(group => group.length));
  for (let i = 0; i < max; i++) {
    for (const members of byImportance) {
      const node = members[i];
      if (!node || labels.has(node.nodeId)) continue;
      const p = positions.get(node.nodeId)!;
      const panel = bounds.get(clusterOf(node))!;
      const sides: LabelSide[] = ["below", "above", "below-start", "below-end", "above-start", "above-end", "right", "left"];
      let chosen = { text: nodeLabel(node, titleWidth), visible: false, side: sides[0] };
      for (const side of sides) {
        const left = p.x - panel.x - 4;
        const right = panel.x + panel.w - p.x - 4;
        const space = side === "left" ? left - 16 : side === "right" ? right - 16
          : side.endsWith("-start") ? right : side.endsWith("-end") ? left : Math.min(left, right) * 2;
        const text = nodeLabel(node, Math.min(titleWidth, space - 7));
        if (space < 38 || text === "…") continue;
        const box = labelBox(p, Math.ceil(measure(text)) + 8, fontSize + 6, side);
        if (box.y < panel.y + 2 || box.y + box.h > panel.y + panel.h - 2 || occupied.some(other => overlaps(box, other))) continue;
        if (!chosen.visible || measure(text) > measure(chosen.text)) chosen = { text, visible: true, side };
      }
      if (chosen.visible) occupied.push(labelBox(p, Math.ceil(measure(chosen.text)) + 8, fontSize + 6, chosen.side));
      labels.set(node.nodeId, chosen);
    }
  }
  // Let a busy retrieval hub fan towards each topic. Each curve still has its
  // own original endpoints; no extra edges or citation relationships are added.
  const routes = new Map<string, { weight: number; distance: number }>();
  const nodeById = new Map(nodes.map(node => [node.nodeId, node]));
  const nearby = indexObstacles(nodes.map(node => {
    const point = positions.get(node.nodeId)!;
    const label = labels.get(node.nodeId)!;
    return { id: node.nodeId, point, radius: node.kind === "mission" ? 17 : 12,
      label: label.visible ? labelBox(point, measure(label.text) + 6, fontSize + 4, label.side) : undefined };
  }), area);
  for (const edge of edges) {
    const role = flightRole(edge);
    const a = positions.get(edge.sourceId)!;
    const b = positions.get(edge.targetId)!;
    if (role === "evidence" || role === "condition") {
      routes.set(edgeId(edge), { weight: .5, distance: evidenceBend(edge, a, b, area, nearby) });
      continue;
    }
    if (role !== "formation" || (degrees.get(edge.sourceId) ?? 0) < 8) continue;
    const target = nodeById.get(edge.targetId)!;
    if (!isPaperNode(target)) continue;
    const panel = bounds.get(clusterOf(target))!;
    const dx = b.x - a.x, dy = b.y - a.y;
    const length = Math.hypot(dx, dy);
    if (length < 1) continue;
    const cx = (panel.x + panel.w * (denseNarrow ? .8 : .5) - a.x) * .7;
    const cy = (panel.y + panel.h * .5 - a.y) * .45;
    const weight = Math.min(.82, Math.max(.18, (cx * dx + cy * dy) / (length * length)));
    const distance = Math.min(length * .32, Math.max(-length * .32, (dx * cy - dy * cx) / length));
    routes.set(edgeId(edge), { weight, distance });
  }
  return { captions, positions, labels, routes };
}

export function LiteratureGraphCanvas(props: LiteratureGraphCanvasProps) {
  let host: HTMLDivElement | undefined;
  let cy: Core | undefined;
  let resizeObserver: ResizeObserver | undefined;
  let resizeFrame: number | undefined;
  let resizeLayout: (() => void) | undefined;
  let previousLayout = "";
  const [compactLayout, setCompactLayout] = createSignal(false);
  const [zoomPercent, setZoomPercent] = createSignal(100);

  const settleLabels = () => {
    if (!cy) return;
    const nodes = cy.nodes();
    nodes.removeClass("label-collision");
    // The layout estimates glyph widths; Cytoscape's measured bounds also
    // account for the actual fallback font, outline and selected font weight.
    const labels = nodes.filter(node => Boolean(node.style("label")))
      .sort((left, right) => Number(right.hasClass("is-emphasized")) - Number(left.hasClass("is-emphasized")));
    const boxes: Box[] = [];
    const hide: NodeSingular[] = [];
    for (const node of labels) {
      const area = node.boundingBox({ includeNodes: false, includeEdges: false, includeLabels: true, includeOverlays: false, includeUnderlays: false });
      const box = { x: area.x1 - 1, y: area.y1 - 1, w: area.w + 2, h: area.h + 2 };
      if (boxes.some(other => overlaps(box, other))) hide.push(node);
      else boxes.push(box);
    }
    cy.batch(() => { for (const node of hide) node.addClass("label-collision"); });
  };

  const revealSelection = () => {
    if (!cy) return;
    const target = cy.$(".is-emphasized");
    if (target.empty() || !cy.width() || !cy.height()) return;
    const box = target.renderedBoundingBox({ includeOverlays: false, includeUnderlays: false });
    const inset = 8;
    // Keep the label as well as the marker inside a narrowed inspector view.
    const offset = (start: number, end: number, size: number) =>
      end - start > size - 2 * inset ? size / 2 - (start + end) / 2 : start < inset ? inset - start : end > size - inset ? size - inset - end : 0;
    const x = offset(box.x1, box.x2, cy.width());
    const y = offset(box.y1, box.y2, cy.height());
    if (x || y) cy.panBy({ x, y });
  };
  const applySelection = () => {
    const nodeId = props.selectedNodeId();
    const edge = props.selectedEdge();
    if (!cy) return;
    const elements = cy.elements();
    const target = nodeId ? cy.getElementById(nodeId) : edge ? cy.getElementById(edgeId(edge)) : cy.collection();
    cy.batch(() => {
      elements.removeClass("is-emphasized is-adjacent is-subdued active-region");
      if (target.empty()) return;
      const adjacent = target.nodes().nonempty() ? target.neighborhood() : target.connectedNodes();
      elements.difference(adjacent.union(target)).addClass("is-subdued");
      adjacent.addClass("is-adjacent");
      target.addClass("is-emphasized");
      const selectedRegions = new Set((nodeId ? target.nodes() : target.connectedNodes()).map(node => node.data("region")));
      cy!.nodes('[isCluster = "yes"]').filter(node => selectedRegions.has(node.data("region"))).removeClass("is-subdued").addClass("active-region");
    });
    settleLabels();
    revealSelection();
  };

  let fittedZoom: number | undefined;
  const fit = () => {
    if (!cy) return;
    cy.fit(undefined, Math.min(22, cy.width() * .05));
    if (cy.zoom() > 1.35) {
      cy.zoom(1.35);
      cy.center();
    }
    fittedZoom = cy.zoom();
  };
  const zoomBy = (factor: number) => {
    if (cy) cy.zoom({ level: Math.max(cy.minZoom(), Math.min(cy.maxZoom(), cy.zoom() * factor)), renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 } });
  };
  const onKeyDown = (event: KeyboardEvent) => {
    if (event.altKey || event.ctrlKey || event.metaKey || !cy) return;
    switch (event.key) {
      case "+": case "=": zoomBy(1.22); break;
      case "-": zoomBy(1 / 1.22); break;
      case "0": fit(); break;
      case "ArrowLeft": cy.panBy({ x: 40, y: 0 }); break;
      case "ArrowRight": cy.panBy({ x: -40, y: 0 }); break;
      case "ArrowUp": cy.panBy({ x: 0, y: 40 }); break;
      case "ArrowDown": cy.panBy({ x: 0, y: -40 }); break;
      default: return;
    }
    event.preventDefault();
  };

  const redraw = () => {
    if (!host) return;
    props.theme();
    const themeStyle = getComputedStyle(host);
    const paper = themeStyle.getPropertyValue("--paper").trim() || "#ffffff";
    const ink = themeStyle.getPropertyValue("--ink").trim() || "#27344b";
    const muted = themeStyle.getPropertyValue("--muted").trim() || "#56616d";
    const nodes = props.nodes().slice(0, 96);
    const nodeIds = new Set(nodes.map((node) => node.nodeId));
    const edges = props.edges().filter((edge) => nodeIds.has(edge.sourceId) && nodeIds.has(edge.targetId)).slice(0, 144);
    const edgesById = new Map(edges.map(edge => [edgeId(edge), edge]));
    const compact = compactLayout();
    const paperStates = props.paperStates();
    const token = (name: string, fallback: string) => themeStyle.getPropertyValue(name).trim() || fallback;
    const colors: Record<BaseCluster, string> = {
      Mission: token("--signal-blue", COLORS.Mission), Papers: token("--signal-teal", COLORS.Papers),
      Evidence: token("--signal-violet", COLORS.Evidence), Conditions: token("--signal-amber", COLORS.Conditions),
      References: token("--signal-rose", COLORS.References), Structure: muted,
    };
    const reviewColors: Record<string, string> = {
      screening: muted, included: colors.Papers, parsing: colors.Mission, source_recorded: colors.Conditions,
      source_map: colors.Conditions, evidence_review: colors.Papers, provenance_audit: colors.Conditions,
      accepted_evidence: colors.Evidence, failed: colors.References, excluded: muted,
    };
    const container = host;
    let chartWidth = container.clientWidth;
    let chartHeight = container.clientHeight;
    const layout = () => atlasLayout(nodes, edges, Math.max(240, chartWidth - 42), Math.max(240, chartHeight - 42), compact, colors);
    const { captions, positions, labels, routes } = layout();
    const layoutKey = JSON.stringify([compact, nodes.map(node => [node.nodeId, clusterOf(node)])]);
    const viewport = cy && layoutKey === previousLayout ? { zoom: cy.zoom(), pan: cy.pan() } : null;
    previousLayout = layoutKey;
    const elements: ElementDefinition[] = [
      ...captions,
      ...nodes.map(node => {
        const group = baseClusterOf(node);
        const reviewState = paperStates[node.nodeId];
        const label = labels.get(node.nodeId)!;
        return { data: { id: node.nodeId, isCluster: "no", label: node.label, shortLabel: label.text,
          displayLabel: label.visible ? label.text : "", labelSide: label.side, color: colors[group], nodeKind: node.kind,
          group, region: clusterOf(node), regionColor: regionColor(node, colors),
          reviewColor: reviewColors[reviewState] ?? colors[group] }, position: positions.get(node.nodeId) };
      }),
      ...Array.from(edgesById, ([id, edge]) => ({ data: { id, source: edge.sourceId, target: edge.targetId,
        label: edge.edgeType.replaceAll("_", " "), color: edgeColor(edge, colors), flightRole: flightRole(edge), ...routes.get(id) } })),
    ];
    cy?.destroy();
    cy = undefined;
    cy = cytoscape({
      container: host,
      elements,
      layout: { name: "preset", fit: false },
      autoungrabify: true,
      minZoom: 0.1,
      maxZoom: 2.5,
      wheelSensitivity: 0.16,
      style: [
        { selector: 'node[isCluster = "yes"]', style: {
          shape: "round-rectangle", "corner-radius": "9px", width: "data(width)", height: "data(height)",
          "background-color": "data(color)", "background-opacity": .068,
          "border-color": "data(color)", "border-width": 1, "border-opacity": .30,
          label: "data(label)", color: "data(color)", "font-family": chartFont, "font-size": 12, "font-weight": 600,
          "text-valign": "top", "text-halign": "right", "text-margin-x": (node: NodeSingular) => node.data("labelInset"), "text-margin-y": 20,
          "z-compound-depth": "bottom", events: "no", "overlay-opacity": 0,
        } },
        { selector: 'node[isCluster = "no"]', style: {
          shape: "ellipse", width: 13, height: 13, "background-color": "data(color)",
          "border-color": "data(reviewColor)", "border-width": 2, "border-position": "outside",
          label: "data(displayLabel)", color: ink, "font-family": chartFont, "font-size": compact ? 12 : 13, "font-weight": 600,
          "text-valign": "bottom", "text-halign": "center", "text-margin-y": 5, "text-outline-color": paper, "text-outline-width": 1.5,
          "overlay-opacity": 0, "z-index": 2,
        } },
        { selector: 'node[group = "Mission"]', style: { width: 22, height: 22, shape: "hexagon", "border-color": "data(color)", "border-width": 1.5, "outline-color": "data(color)", "outline-offset": 2, "outline-width": 1 } },
        { selector: 'node[group = "Papers"]', style: { "background-color": paper, "border-width": 2.3,
          "pie-size": "36%", "pie-1-background-color": "data(regionColor)", "pie-1-background-size": 100 } },
        { selector: 'node[group = "Evidence"]', style: { width: 14, height: 14, shape: "round-diamond" } },
        { selector: 'node[nodeKind = "research_gap_candidate"]', style: { shape: "triangle", "background-color": paper, "border-style": "dashed" } },
        { selector: 'node[group = "Conditions"]', style: { shape: "round-rectangle", "background-color": paper } },
        { selector: 'node[group = "References"]', style: { shape: "diamond", width: 10, height: 10, "background-color": paper } },
        { selector: 'node[group = "Structure"]', style: { width: 9, height: 9 } },
        { selector: 'node[labelSide ^= "above"]', style: { "text-valign": "top", "text-margin-y": -5 } },
        { selector: 'node[labelSide $= "-start"]', style: { "text-halign": "right", "text-margin-x": -6.5 } },
        { selector: 'node[labelSide $= "-end"]', style: { "text-halign": "left", "text-margin-x": 6.5 } },
        { selector: 'node[labelSide = "right"]', style: { "text-valign": "center", "text-halign": "right", "text-margin-x": 6, "text-margin-y": 0 } },
        { selector: 'node[labelSide = "left"]', style: { "text-valign": "center", "text-halign": "left", "text-margin-x": -6, "text-margin-y": 0 } },
        { selector: "edge", style: { width: 1.35, "line-color": "data(color)", "target-arrow-color": "data(color)",
          "target-arrow-shape": "triangle", "arrow-scale": .65, "curve-style": "bezier", opacity: .72,
          label: "", "overlay-opacity": 0, "z-index": 0 } },
        { selector: 'edge[flightRole = "formation"]', style: { width: 1, "line-color": muted, "target-arrow-shape": "none", opacity: nodes.length > 18 ? .18 : .44 } },
        { selector: "edge[weight]", style: { "curve-style": "unbundled-bezier", "edge-distances": "node-position",
          "control-point-distances": "data(distance)", "control-point-weights": "data(weight)" } },
        { selector: 'edge[flightRole = "bibliography"]', style: { opacity: .72 } },
        { selector: 'edge[flightRole = "suggestion"]', style: { "line-style": "dotted", opacity: .50, "target-arrow-shape": "none" } },
        { selector: "node.is-subdued", style: { opacity: .50 } },
        { selector: "edge.is-subdued", style: { opacity: .09 } },
        { selector: "node.active-region", style: { "border-width": 1.6, "border-opacity": .78, "background-opacity": .105 } },
        { selector: "node.is-adjacent", style: { "outline-color": "data(color)", "outline-width": 1, "outline-offset": 2, "z-index": 5 } },
        { selector: "edge.is-adjacent", style: { width: 2, opacity: .94, "z-index": 1 } },
        { selector: "node.is-emphasized", style: { label: "data(shortLabel)", "background-color": "data(color)", "border-color": paper,
          "border-width": 2, "outline-color": "data(color)", "outline-offset": 1, "outline-width": 2,
          "font-weight": 700, "text-outline-width": 2.5, "z-index": 10 } },
        { selector: 'node[group = "Papers"].is-emphasized', style: { "background-color": paper,
          "border-color": "data(reviewColor)", "border-width": 2.3, "outline-color": ink, "outline-offset": 2.5,
          "outline-width": 2.2, "pie-1-background-color": "data(regionColor)" } },
        { selector: "edge.is-emphasized", style: { width: 2.8, opacity: 1, label: "data(label)", "font-family": chartFont,
          "font-size": 12, color: ink, "text-background-color": paper, "text-background-opacity": 1, "text-background-padding": "3px", "z-index": 8 } },
        { selector: "node.label-collision", style: { label: "" } },
      ],
    });
    cy.on("tap", 'node[isCluster = "no"]', (event) => props.onSelectNode(event.target.id()));
    cy.on("tap", "edge", (event) => {
      const edge = edgesById.get(event.target.id());
      if (edge) props.onSelectEdge(edge);
    });
    cy.on("tap", (event) => { if (event.target === cy) props.onSelectNode(""); });
    cy.on("zoom", () => { if (cy) setZoomPercent(Math.round(cy.zoom() * 100)); });
    resizeLayout = () => {
      if (!cy || (container.clientWidth === chartWidth && container.clientHeight === chartHeight)) return;
      chartWidth = container.clientWidth;
      chartHeight = container.clientHeight;
      const next = layout();
      cy.startBatch();
      for (const caption of next.captions) {
        const marker = cy.getElementById(caption.data.id!);
        marker.position(caption.position!).data(caption.data);
      }
      for (const [id, point] of next.positions) {
        const label = next.labels.get(id)!;
        cy.getElementById(id).position(point).data({
          shortLabel: label.text, displayLabel: label.visible ? label.text : "", labelSide: label.side,
        });
      }
      for (const [id, route] of next.routes) cy.getElementById(id).data(route);
      cy.endBatch();
      settleLabels();
    };
    if (viewport) cy.viewport(viewport);
    else fit();
    setZoomPercent(Math.round(cy.zoom() * 100));
    props.onReady({ fit, zoomIn: () => zoomBy(1.22), zoomOut: () => zoomBy(1 / 1.22) });
    // A selection is a style change. Keep its reactive reads out of the renderer lifecycle.
    untrack(applySelection);
  };

  onMount(() => {
    const narrow = window.matchMedia("(max-width: 760px)");
    const updateLayout = () => setCompactLayout(narrow.matches);
    updateLayout();
    narrow.addEventListener("change", updateLayout);
    onCleanup(() => narrow.removeEventListener("change", updateLayout));
    if (host) {
      // A scroll or a panel above the canvas can move it without resizing it.
      // Refresh Cytoscape's page offset before its renderer hit-tests the press.
      const container = host;
      const refreshHitCoordinates = () => cy?.resize();
      const starts = typeof PointerEvent !== "undefined" ? ["pointerdown"] : ["mousedown", "touchstart"];
      for (const event of starts) container.addEventListener(event, refreshHitCoordinates, { capture: true, passive: true });
      onCleanup(() => {
        for (const event of starts) container.removeEventListener(event, refreshHitCoordinates, true);
      });
    }
    if (host && typeof ResizeObserver !== "undefined") {
      resizeObserver = new ResizeObserver(() => {
        if (resizeFrame !== undefined) window.cancelAnimationFrame(resizeFrame);
        resizeFrame = window.requestAnimationFrame(() => {
          if (!cy) return;
          const wasFitted = Math.abs(cy.zoom() - (fittedZoom ?? 0)) < .001;
          cy.resize();
          if (wasFitted) { resizeLayout?.(); fit(); }
          revealSelection();
        });
      });
      resizeObserver.observe(host);
    }
    createEffect(redraw);
  });
  createEffect(applySelection);
  onCleanup(() => {
    resizeObserver?.disconnect();
    if (resizeFrame !== undefined) window.cancelAnimationFrame(resizeFrame);
    cy?.destroy();
    cy = undefined;
    props.onReady(null);
  });
  return <>
    <div class="cytoscape-literature-canvas" ref={host} tabIndex={0} role="group" onKeyDown={onKeyDown}
      aria-label={zh("Interactive literature graph", "交互式文献图谱")}
      aria-description={zh("Arrow keys pan, plus and minus zoom, and zero fits the map.", "方向键平移，加减键缩放，0 键适配画布。")} />
    <output class="canvas-zoom-readout" aria-label={zh("Map zoom level", "图谱缩放比例")} aria-live="off">{zoomPercent()}%</output>
  </>;
}
