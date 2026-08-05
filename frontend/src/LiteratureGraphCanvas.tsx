import cytoscape, { type Core, type ElementDefinition } from "cytoscape";
import { createEffect, onCleanup, onMount } from "solid-js";

import type { LiteratureGraphEdge, LiteratureGraphNode } from "./model";

type Cluster = "Mission" | "Papers" | "Evidence" | "References" | "Structure";

export interface GraphCanvasControls {
  fit: () => void;
  zoomIn: () => void;
  zoomOut: () => void;
}

interface Props {
  theme: () => string;
  nodes: () => LiteratureGraphNode[];
  edges: () => LiteratureGraphEdge[];
  selectedNodeId: () => string | null;
  selectedEdge: () => LiteratureGraphEdge | null;
  onSelectNode: (nodeId: string) => void;
  onSelectEdge: (edge: LiteratureGraphEdge) => void;
  onReady: (controls: GraphCanvasControls) => void;
}

const COLORS: Record<Cluster, string> = {
  Mission: "#2f6fec",
  Papers: "#0f8a83",
  Evidence: "#c97a18",
  References: "#7442db",
  Structure: "#ba4e70",
};

function clusterOf(node: LiteratureGraphNode): Cluster {
  if (node.kind === "mission") return "Mission";
  if (["candidate_paper", "evidence_paper", "relation_root_paper", "structured_paper"].includes(node.kind)) return "Papers";
  if (node.kind === "accepted_evidence") return "Evidence";
  if (["openalex_work", "crossref_work"].includes(node.kind)) return "References";
  return "Structure";
}

function edgeColor(edge: LiteratureGraphEdge): string {
  if (edge.edgeType === "source_provenance") return COLORS.Evidence;
  if (["citation_reference", "algorithmic_related", "crossref_reference"].includes(edge.edgeType)) return COLORS.References;
  if (edge.edgeType === "retrieval_candidate") return COLORS.Papers;
  return COLORS.Structure;
}

function degreeMap(edges: LiteratureGraphEdge[]): Map<string, number> {
  const degrees = new Map<string, number>();
  edges.forEach((edge) => {
    degrees.set(edge.sourceId, (degrees.get(edge.sourceId) ?? 0) + 1);
    degrees.set(edge.targetId, (degrees.get(edge.targetId) ?? 0) + 1);
  });
  return degrees;
}

function sampleLabelIds(nodes: LiteratureGraphNode[], edges: LiteratureGraphEdge[]): Set<string> {
  const degrees = degreeMap(edges);
  const groups = new Map<Cluster, LiteratureGraphNode[]>();
  nodes.forEach((node) => {
    const group = clusterOf(node);
    groups.set(group, [...(groups.get(group) ?? []), node]);
  });
  const labels = new Set<string>();
  groups.forEach((group) => {
    const limit = group.length <= 8 ? group.length : Math.max(5, Math.ceil(group.length * 0.3));
    [...group].sort((left, right) => (degrees.get(right.nodeId) ?? 0) - (degrees.get(left.nodeId) ?? 0) || left.label.localeCompare(right.label))
      .slice(0, limit)
      .forEach((node) => labels.add(node.nodeId));
  });
  return labels;
}

function trimLabel(label: string): string {
  return label.length > 45 ? `${label.slice(0, 42).trim()}…` : label;
}

function geometry(nodes: LiteratureGraphNode[]): { clusters: ElementDefinition[]; positions: Map<string, { x: number; y: number }> } {
  const groups = new Map<Cluster, LiteratureGraphNode[]>();
  nodes.forEach((node) => {
    const group = clusterOf(node);
    groups.set(group, [...(groups.get(group) ?? []), node]);
  });
  const visibleClusters = [...groups.entries()].filter(([, group]) => group.length);
  const columns = visibleClusters.length <= 3 ? visibleClusters.length : 3;
  const radius = (group: LiteratureGraphNode[]) => Math.max(92, 50 + Math.sqrt(group.length) * 29);
  const positions = new Map<string, { x: number; y: number }>();
  const clusterElements: ElementDefinition[] = [];
  const rows = Array.from({ length: Math.ceil(visibleClusters.length / columns) }, (_, index) => visibleClusters.slice(index * columns, (index + 1) * columns));
  let rowY = 0;
  rows.forEach((row, rowIndex) => {
    const rowRadius = Math.max(...row.map(([, group]) => radius(group)));
    let rowX = 0;
    const placed = row.map(([cluster, group], index) => {
      const clusterRadius = radius(group);
      const item = { cluster, group, x: rowX + clusterRadius, y: rowY + rowRadius, radius: clusterRadius, index };
      rowX += clusterRadius * 2 + 92;
      return item;
    });
    const width = rowX - 92;
    placed.forEach((item) => {
      item.x -= width / 2;
      const clusterId = `cluster:${rowIndex}:${item.cluster}`;
      clusterElements.push({ data: { id: clusterId, isCluster: "yes", label: `${item.cluster}\n${item.group.length} nodes`, color: COLORS[item.cluster], diameter: item.radius * 2 }, position: { x: item.x, y: item.y }, selectable: false, grabbable: false });
      const usableRadius = Math.max(28, item.radius - 35);
      item.group.forEach((node, nodeIndex) => {
        if (item.group.length === 1) {
          positions.set(node.nodeId, { x: item.x, y: item.y });
          return;
        }
        const distance = Math.sqrt((nodeIndex + 0.5) / item.group.length) * usableRadius;
        const angle = nodeIndex * 2.3999632297 + item.index * 0.66;
        positions.set(node.nodeId, { x: item.x + Math.cos(angle) * distance, y: item.y + Math.sin(angle) * distance });
      });
    });
    rowY += rowRadius * 2 + 92;
  });
  return { clusters: clusterElements, positions };
}

export function LiteratureGraphCanvas(props: Props) {
  let host: HTMLDivElement | undefined;
  let cy: Core | undefined;

  const applySelection = () => {
    if (!cy) return;
    cy.elements().removeClass("is-emphasized");
    const nodeId = props.selectedNodeId();
    if (nodeId) cy.getElementById(nodeId).addClass("is-emphasized");
    const edge = props.selectedEdge();
    if (edge) cy.getElementById(`${edge.sourceId}|${edge.targetId}|${edge.edgeType}`).addClass("is-emphasized");
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
    const labelIds = sampleLabelIds(nodes, edges);
    const { clusters, positions } = geometry(nodes);
    const elements: ElementDefinition[] = [
      ...clusters,
      ...nodes.map((node) => ({ data: { id: node.nodeId, isCluster: "no", label: node.label, displayLabel: labelIds.has(node.nodeId) ? trimLabel(node.label) : "", color: COLORS[clusterOf(node)], nodeKind: node.kind }, position: positions.get(node.nodeId) })),
      ...edges.map((edge) => ({ data: { id: `${edge.sourceId}|${edge.targetId}|${edge.edgeType}`, source: edge.sourceId, target: edge.targetId, label: edge.edgeType.replaceAll("_", " "), color: edgeColor(edge), edgeType: edge.edgeType } })),
    ];
    cy?.destroy();
    cy = cytoscape({
      container: host,
      elements,
      layout: { name: "preset", fit: true, padding: 62 },
      autoungrabify: true,
      minZoom: 0.3,
      maxZoom: 2.5,
      wheelSensitivity: 0.16,
      style: [
        { selector: 'node[isCluster = "yes"]', style: { shape: "ellipse", width: "data(diameter)", height: "data(diameter)", "background-color": "data(color)", "background-opacity": 0.065, "border-color": "data(color)", "border-opacity": 0.24, "border-width": 1.1, label: "data(label)", color: "data(color)", "font-size": "10px", "font-weight": 800, "text-wrap": "wrap", "text-valign": "top", "text-halign": "center", "text-margin-y": -10, events: "no", "z-index": -10, "overlay-opacity": 0 } },
        { selector: 'node[isCluster = "no"]', style: { width: 11, height: 11, "background-color": "data(color)", "border-color": paper, "border-width": 1.5, label: "data(displayLabel)", color: ink, "font-size": "10px", "font-weight": 650, "text-wrap": "wrap", "text-max-width": "145px", "text-halign": "right", "text-margin-x": 9, "text-background-color": paper, "text-background-opacity": 0.78, "text-background-padding": "2px", "text-background-shape": "roundrectangle", "overlay-opacity": 0 } },
        { selector: 'node[nodeKind = "mission"]', style: { width: 16, height: 16, shape: "round-rectangle", "background-color": COLORS.Mission } },
        { selector: "node.is-emphasized", style: { width: 16, height: 16, "border-width": 2.5, label: "data(label)", "z-index": 20 } },
        { selector: "edge", style: { width: 1.1, "line-color": "data(color)", "target-arrow-color": "data(color)", "target-arrow-shape": "triangle", "arrow-scale": 0.65, "curve-style": "bezier", opacity: 0.66, label: "", "overlay-opacity": 0 } },
        { selector: "edge.is-emphasized", style: { width: 2.1, opacity: 1, label: "data(label)", "font-size": "8px", color: muted, "text-background-color": paper, "text-background-opacity": 0.9, "text-background-padding": "2px", "text-rotation": "autorotate", "z-index": 20 } },
      ],
    });
    cy.on("tap", 'node[isCluster = "no"]', (event) => props.onSelectNode(event.target.id()));
    cy.on("tap", "edge", (event) => {
      const id = event.target.id().split("|");
      const edge = edges.find((item) => item.sourceId === id[0] && item.targetId === id[1] && item.edgeType === id[2]);
      if (edge) props.onSelectEdge(edge);
    });
    cy.on("tap", (event) => { if (event.target === cy) props.onSelectNode(""); });
    props.onReady({ fit: () => cy?.fit(undefined, 62), zoomIn: () => { if (cy) cy.zoom({ level: Math.min(2.5, cy.zoom() * 1.22), renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 } }); }, zoomOut: () => { if (cy) cy.zoom({ level: Math.max(0.3, cy.zoom() / 1.22), renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 } }); } });
    applySelection();
  };

  onMount(() => createEffect(() => { props.theme(); props.nodes(); props.edges(); redraw(); }));
  createEffect(applySelection);
  onCleanup(() => cy?.destroy());
  return <div class="cytoscape-literature-canvas" ref={host} aria-label="Interactive literature graph" />;
}
