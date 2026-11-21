"use strict";

const NETWORK_SCHEMA = "1.0";
const NETWORK_MAX_BYTES = 1024 * 1024;
const networkDemo = {
  schema_version: NETWORK_SCHEMA,
  mission: { material: "BiFeO3", property_name: "phase stability" },
  research_guide: { items: [{ order: 1, document_id: "doc_demo", title: "Synthetic strain study", publication_year: 2025, source: "synthetic fixture", locator_hint: "page:1", track: "primary", role: "primary_candidate", content_status: "provider_advertised", evidence_ids: ["evidence_demo_001"] }] },
  evidence_cards: [{ evidence_id: "evidence_demo_001", claim: "合成示例：条件必须被记录。", stance: "support", review_status: "accepted", provenance: { document_id: "doc_demo", locator: "page:1" } }],
  condition_matrix: [{ condition_cluster: "外延薄膜 · 压缩应变", supporting_evidence_ids: ["evidence_demo_001"], contradicting_evidence_ids: [], differing_fields: ["thickness"], unknowns: ["oxygen vacancy"] }],
};

function netText(value, fallback = "unknown") { return typeof value === "string" && value.trim() ? value.trim() : fallback; }
function netArray(value) { return Array.isArray(value) ? value : []; }

function validateNetworkBundle(candidate) {
  if (!candidate || typeof candidate !== "object" || Array.isArray(candidate)) throw new Error("JSON 根节点必须是对象。");
  if (candidate.schema_version !== NETWORK_SCHEMA) throw new Error(`仅支持 UI JSON v${NETWORK_SCHEMA}。`);
  for (const key of ["mission", "evidence_cards", "condition_matrix"]) if (!(key in candidate)) throw new Error(`缺少 UI 契约字段：${key}`);
  if (!candidate.mission || !Array.isArray(candidate.evidence_cards) || !Array.isArray(candidate.condition_matrix)) throw new Error("星图字段类型无效。");
  if ("research_guide" in candidate && candidate.research_guide !== null && (!candidate.research_guide || typeof candidate.research_guide !== "object" || !Array.isArray(candidate.research_guide.items))) throw new Error("research_guide 字段无效。");
  return candidate;
}

function makeGraph(bundle) {
  const nodes = [];
  const edges = [];
  const byId = new Map();
  const addNode = (node) => {
    if (!byId.has(node.id)) {
      if (node.kind === "paper") {
        const title = netText(node.data.title, "");
        node.phrase = (title && title !== node.data.document_id && CosMatterPaperLabels.paperKeyphrase(title, "zh")) || "题名待补";
      }
      byId.set(node.id, node);
      nodes.push(node);
    }
    return byId.get(node.id);
  };
  const mission = addNode({ id: "mission", kind: "mission", label: `${netText(bundle.mission.material)} · ${netText(bundle.mission.property_name)}`, data: bundle.mission });
  const guideItems = bundle.research_guide && Array.isArray(bundle.research_guide.items) ? bundle.research_guide.items : [];
  guideItems.slice(0, 12).forEach((item) => {
    const paper = addNode({ id: `paper:${netText(item.document_id)}`, kind: "paper", label: netText(item.title), data: item });
    edges.push({ from: mission.id, to: paper.id, kind: "retrieval_candidate", label: item.track === "counterevidence" ? "反例检索候选" : "主检索候选" });
  });
  const approved = netArray(bundle.evidence_cards).filter((card) => card && card.review_status === "accepted" && card.provenance);
  approved.forEach((card) => {
    const evidence = addNode({ id: `evidence:${netText(card.evidence_id)}`, kind: "evidence", label: netText(card.evidence_id), data: card });
    const paperId = `paper:${netText(card.provenance.document_id)}`;
    if (!byId.has(paperId)) {
      addNode({ id: paperId, kind: "paper", label: netText(card.provenance.document_id), data: { document_id: card.provenance.document_id, title: card.provenance.document_id, source: "evidence provenance", content_status: "confirmed", track: "unclassified", role: "evidence_source", evidence_ids: [card.evidence_id] } });
      edges.push({ from: mission.id, to: paperId, kind: "retrieval_candidate", label: "证据出处论文" });
    }
    edges.push({ from: paperId, to: evidence.id, kind: "source_provenance", label: "document_id + locator" });
  });
  const settingNodeIds = new Map();
  approved.forEach((card) => {
    Object.entries(card.conditions || {}).slice(0, 12).forEach(([field, value]) => {
      if (value === null || typeof value === "object") return;
      const encoded = `${field}:${String(value)}`;
      let settingId = settingNodeIds.get(encoded);
      const computational = /method|code|functional|cutoff|kpoint|supercell|calculation/i.test(field);
      if (!settingId) {
        settingId = `setting:${encoded}`;
        settingNodeIds.set(encoded, settingId);
        addNode({ id: settingId, kind: "setting", label: `${field} = ${String(value)}`, data: { field, value: String(value), category: computational ? "computational_setting" : "experimental_setting" } });
      }
      edges.push({ from: `evidence:${netText(card.evidence_id)}`, to: settingId, kind: "condition_recorded", label: "reported condition; not causal" });
    });
  });
  const relations = bundle.literature_relations;
  if (relations && relations.trust_status === "public_relation_metadata_not_scientific_evidence" && relations.source && Array.isArray(relations.edges)) {
    const sourceDocumentId = netText(relations.source.document_id);
    const sourcePaperId = `paper:${sourceDocumentId}`;
    if (!byId.has(sourcePaperId)) {
      addNode({ id: sourcePaperId, kind: "paper", label: sourceDocumentId, data: { document_id: sourceDocumentId, title: sourceDocumentId, source: "accepted evidence provenance", content_status: "confirmed", track: "unclassified", role: "relation_source", evidence_ids: [relations.source.evidence_id] } });
    }
    netArray(relations.edges).slice(0, 24).forEach((relation) => {
      if (!relation || !["citation_reference", "algorithmic_related"].includes(relation.edge_type)) return;
      const targetId = netText(relation.target_openalex_id);

      const target = addNode({ id: `external:${targetId}`, kind: "external_relation", label: targetId.replace("https://openalex.org/", ""), data: { relation_type: relation.edge_type, trust_status: relations.trust_status } });
      edges.push({ from: sourcePaperId, to: target.id, kind: relation.edge_type, label: relation.edge_type === "citation_reference" ? "OpenAlex reference metadata" : "OpenAlex algorithmic related-work metadata" });
    });
  }
  const crossrefRelations = bundle.crossref_relations;
  if (crossrefRelations && crossrefRelations.trust_status === "public_bibliographic_reference_metadata_not_scientific_evidence" && crossrefRelations.source && Array.isArray(crossrefRelations.edges)) {
    const sourceDocumentId = netText(crossrefRelations.source.document_id);
    const sourcePaperId = `paper:${sourceDocumentId}`;
    if (!byId.has(sourcePaperId)) {
      addNode({ id: sourcePaperId, kind: "paper", label: sourceDocumentId, data: { document_id: sourceDocumentId, title: sourceDocumentId, source: "accepted evidence provenance", content_status: "confirmed", track: "unclassified", role: "relation_source", evidence_ids: [crossrefRelations.source.evidence_id] } });
    }
    netArray(crossrefRelations.edges).slice(0, 12).forEach((relation) => {
      if (!relation || relation.edge_type !== "crossref_reference") return;
      const targetDoi = netText(relation.target_doi);
      if (!targetDoi.startsWith("10.") || !targetDoi.includes("/")) return;
      const target = addNode({ id: `crossref:${targetDoi}`, kind: "external_relation", label: `Crossref · ${targetDoi}`, data: { relation_type: "crossref_reference", relation_source: "Crossref", trust_status: crossrefRelations.trust_status, reference_field_present: crossrefRelations.reference_field_present === true } });
      edges.push({ from: sourcePaperId, to: target.id, kind: "crossref_reference", label: "Crossref deposited reference metadata; not scientific evidence" });
    });
  }
  const reconciliation = bundle.relation_reconciliation;
  if (reconciliation && reconciliation.trust_status === "human_reviewed_cross_source_identity_not_scientific_evidence" && Array.isArray(reconciliation.mappings)) {
    reconciliation.mappings.slice(0, 12).forEach((mapping) => {
      if (!mapping || !["matched", "conflict", "unresolved"].includes(mapping.status)) return;
      const openalexId = `external:${netText(mapping.openalex_work_id)}`;
      const crossrefId = `crossref:${netText(mapping.crossref_doi)}`;
      if (byId.has(openalexId) && byId.has(crossrefId)) edges.push({ from: openalexId, to: crossrefId, kind: `identity_${mapping.status}`, label: `human-reviewed identity ${mapping.status}; not scientific evidence` });
    });
  }
  netArray(bundle.condition_matrix).forEach((row, index) => {
    const condition = addNode({ id: `condition:${index}`, kind: "condition", label: netText(row.condition_cluster), data: row });
    netArray(row.supporting_evidence_ids).forEach((evidenceId) => edges.push({ from: `evidence:${netText(evidenceId)}`, to: condition.id, kind: "support", label: "审核支持" }));
    netArray(row.contradicting_evidence_ids).forEach((evidenceId) => edges.push({ from: `evidence:${netText(evidenceId)}`, to: condition.id, kind: "contradict", label: "审核反驳" }));
    netArray(row.unknowns).forEach((unknown, unknownIndex) => {
      const unknownNode = addNode({ id: `unknown:${index}:${unknownIndex}`, kind: "unknown", label: netText(unknown), data: { condition_cluster: row.condition_cluster, unknown } });
      edges.push({ from: condition.id, to: unknownNode.id, kind: "open_question", label: "待核查" });
    });
  });
  return { nodes, edges: edges.filter((edge) => byId.has(edge.from) && byId.has(edge.to)) };
}

function inspector(node) {
  document.querySelector(".atlas-inspector-label").textContent = nodeKinds[node.kind];
  document.querySelector("#node-title").textContent = node.label;
  const panel = document.querySelector("#node-inspector");
  let fields;
  if (node.kind === "paper") fields = [["阅读角色", netText(node.data.role, "未记录")], ["检索轨道", netText(node.data.track, "未记录")], ["访问状态", netText(node.data.content_status, "未记录")], ["来源定位", netText(node.data.locator_hint, "未记录")], ["导读证据 ID", netArray(node.data.evidence_ids).join("、") || "未登记"]];
  else if (node.kind === "evidence") fields = [["类型", "已批准证据"], ["立场", netText(node.data.stance)], ["定位", `${netText(node.data.provenance.document_id)} · ${netText(node.data.provenance.locator)}`], ["主张", netText(node.data.claim)]];
  else if (node.kind === "condition") fields = [["类型", "条件簇"], ["差异字段", netArray(node.data.differing_fields).join("、") || "未记录"], ["支持证据", netArray(node.data.supporting_evidence_ids).join("、") || "无"], ["反驳证据", netArray(node.data.contradicting_evidence_ids).join("、") || "无"]];
  else if (node.kind === "setting") fields = [["类型", node.data.category === "computational_setting" ? "计算设置" : "实验设置"], ["记录字段", netText(node.data.field)], ["报告值", netText(node.data.value)]];
  else if (node.kind === "external_relation") fields = [["类型", "公开书目关系"], ["关系字段", netText(node.data.relation_type)], ["来源", netText(node.data.relation_source, "OpenAlex")], ["参考文献字段", node.data.relation_source === "Crossref" ? (node.data.reference_field_present ? "已有登记" : "未登记或不可用") : "不适用"]];
  else if (node.kind === "unknown") fields = [["类型", "待核查项"], ["所属条件簇", netText(node.data.condition_cluster)], ["未知项", netText(node.data.unknown)]];
  else fields = [["类型", "任务锚点"], ["材料", netText(node.data.material)], ["性质", netText(node.data.property_name)]];
  const list = document.createElement("dl"); list.className = "inspector-list";
  fields.forEach(([name, value]) => { const row = document.createElement("div"); const key = document.createElement("dt"); const body = document.createElement("dd"); key.textContent = name; body.textContent = value; row.append(key, body); list.append(row); });
  panel.replaceChildren(list);
}

let inspectedId = null;
let overviewId = null;
const nodeKinds = { mission: "研究任务", paper: "论文", evidence: "已接受证据", setting: "研究条件", condition: "条件簇", unknown: "待核查", external_relation: "书目记录" };
const edgeNames = new Map(Array.from(document.querySelectorAll(".graph-legend li"), item => [item.className.slice(5), item.textContent]));
const labelMeasure = document.createElement("canvas").getContext("2d");

function svgPart(name, attributes, text) {
  const element = document.createElementNS("http://www.w3.org/2000/svg", name);
  for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, value);
  if (text !== undefined) element.textContent = text;
  return element;
}

function shortLabel(value, maxWidth) {
  if (labelMeasure.measureText(value).width <= maxWidth) return value;
  const letters = Array.from(value);
  const tail = letters.slice(-5).join("");
  let low = 0;
  let high = letters.length - 5;
  while (low < high) {
    const mid = Math.ceil((low + high) / 2);
    if (labelMeasure.measureText(letters.slice(0, mid).join("") + "…" + tail).width <= maxWidth) low = mid;
    else high = mid - 1;
  }
  return letters.slice(0, low).join("") + "…" + tail;
}

function layoutAtlas(nodes, width) {
  const margin = 16;
  const columns = Math.max(1, Math.floor((width - 2 * margin) / 194));
  let y = 43;
  for (const [level, kind] of Object.keys(nodeKinds).entries()) {
    const group = nodes.filter(node => node.kind === kind);
    for (let offset = 0; offset < group.length; offset += columns) {
      const row = group.slice(offset, offset + columns);
      const cell = (width - 2 * margin) / row.length;
      for (const [column, node] of row.entries()) {
        node.width = Math.min(214, cell - 8);
        const fraction = group.length === 1 ? [0.34, 0.68, 0.29, 0.64, 0.71, 0.37, 0.58][level] : 0.5;
        node.x = Math.round(margin + column * cell + (cell - node.width) * fraction + 17);
        node.y = y;
      }
      y += 76;
    }
  }
  return Math.max(144, y - 36);
}

// Each neighbor owns a separate row. Long connections stay in the gap between
// the two columns, or in the left margin on a phone, clear of other cards.
function layoutNeighbors(nodes, width) {
  const [center, ...neighbors] = nodes;
  const sideBySide = width >= 580;
  center.width = sideBySide ? Math.min(width * .37, 270) : Math.min(width - 46, 300);
  center.x = sideBySide ? 36 : 33;
  center.y = sideBySide ? 48 + 34 * Math.min(2, Math.max(0, neighbors.length - 1)) : 43;
  for (const [index, node] of neighbors.entries()) {
    node.x = sideBySide ? Math.round(width * .53) : 54;
    node.width = Math.min(width - node.x + 2, sideBySide ? 360 : 310);
    node.y = (sideBySide ? 48 : 123) + 68 * index;
  }
  return Math.max(150, nodes.at(-1).y + 44);
}

function neighborPath(center, other, width, offset) {
  const x2 = other.x - 17;
  if (width < 580) {
    const rail = 10 + offset;
    return `M ${center.x - 9} ${center.y + 24} Q ${rail} ${center.y + 24} ${rail} ${center.y + 41} V ${other.y - 11} Q ${rail} ${other.y + offset} ${rail + 12} ${other.y + offset} H ${x2}`;
  }
  const x1 = center.x + center.width - 17;
  const half = (x2 - x1) * .53;
  return `M ${x1} ${center.y + offset} C ${x1 + half} ${center.y + offset}, ${x2 - half} ${other.y + offset}, ${x2} ${other.y + offset}`;
}

function edgePath(a, b) {
  if (a.y === b.y) {
    const middle = (a.x + b.x) / 2;
    return `M ${a.x} ${a.y} Q ${middle} ${a.y - 48} ${b.x} ${b.y}`;
  }
  const middle = (a.y + b.y) / 2;
  return `M ${a.x} ${a.y} C ${a.x} ${middle}, ${b.x} ${middle}, ${b.x} ${b.y}`;
}

function nodeMarker(node) {
  const paths = {
    mission: "M-7 0 -3.5 -6.5 H3.5 L7 0 3.5 6.5 H-3.5 Z",
    evidence: "M0 -7.5 7.5 0 0 7.5 -7.5 0Z",
    setting: "M-6 -6H6V6H-6Z",
    condition: "M-7 4 -3 -5H7L3 4Z",
    unknown: "M0 -7 7 6H-7Z",
    external_relation: "M-6 1A5 5 0 0 1 0 -5L2 -3 M6 -1A5 5 0 0 1 0 5L-2 3",
  };
  return node.kind === "paper"
    ? svgPart("circle", { class: "atlas-marker", cx: node.x, cy: node.y, r: 6 })
    : svgPart("path", { class: "atlas-marker", d: paths[node.kind], transform: `translate(${node.x} ${node.y})` });
}

function drawNode(node, caption) {
  const group = svgPart("g", { class: "graph-node " + node.kind, tabindex: 0, role: "button", "aria-label": node.label, "aria-pressed": "false" });
  const x = node.x;
  const y = node.y;
  group.append(svgPart("title", {}, node.label),
    svgPart("rect", { class: "atlas-node-box", x: x - 17, y: y - 24, width: node.width, height: 48, rx: 5 }),
    nodeMarker(node));
  if (node.kind === "paper") {
    const text = svgPart("text", { class: "atlas-title", x: x + 16, y: y + 5 });
    const phrase = node.phrase;
    const maxWidth = node.width - 41;
    if (labelMeasure.measureText(phrase).width <= maxWidth) {
      text.textContent = phrase;
    } else {
      // Keep the entire phrase across two lines, preferring a word boundary.
      const words = phrase.match(/\S+\s*/gu) ?? [];
      const parts = words.length > 1 ? words : Array.from(phrase);
      let split = 1;
      while (split < parts.length - 1 && labelMeasure.measureText(parts.slice(0, split + 1).join("")).width <= maxWidth) split++;
      for (const [index, line] of [parts.slice(0, split).join(""), parts.slice(split).join("")].entries()) {
        const span = svgPart("tspan", { x: x + 16, y: y - 4 + index * 18 }, line);
        if (labelMeasure.measureText(line.trimEnd()).width > maxWidth) {
          span.setAttribute("textLength", String(maxWidth));
          span.setAttribute("lengthAdjust", "spacingAndGlyphs");
        }
        text.append(span);
      }
    }
    group.append(text);
  } else {
    group.append(svgPart("text", { class: "atlas-kind", x: x + 16, y: y - 6 }, shortLabel(caption ?? nodeKinds[node.kind], node.width - 41)),
      svgPart("text", { class: "atlas-title", x: x + 16, y: y + 15 }, shortLabel(node.label, node.width - 41)));
  }
  return group;
}

function directRelations(edges, id) {
  const neighbors = new Map();
  for (const edge of edges) {
    if (edge.from !== id && edge.to !== id) continue;
    const other = edge.from === id ? edge.to : edge.from;
    if (other === id) continue;
    if (!neighbors.has(other)) neighbors.set(other, []);
    neighbors.get(other).push(edge);
  }
  return neighbors;
}

function relatedLabels(edges) {
  return [...new Set(edges.map(edge => edgeNames.get(edge.kind)))].join(" · ");
}

function showNeighborIndex(links, byId, visit) {
  const nav = document.querySelector(".atlas-neighbors");
  const list = nav.querySelector("ul");
  const previousFocus = nav.contains(document.activeElement) ? document.activeElement.dataset.nodeId : null;
  nav.hidden = !links.size;
  list.replaceChildren();
  for (const [id, edges] of links) {
    const item = document.createElement("li");
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.nodeId = id;
    const relation = document.createElement("small");
    relation.textContent = relatedLabels(edges);
    const label = document.createElement("span");
    label.textContent = byId.get(id).label;
    button.append(relation, label);
    button.addEventListener("click", () => visit(byId.get(id)));
    item.append(button);
    list.append(item);
    if (id === previousFocus) button.focus({ preventScroll: true });
  }
}

function revealNode(button) {
  const frame = button.closest(".atlas-plot-window");
  const card = button.getBoundingClientRect();
  const bounds = frame.getBoundingClientRect();
  if (card.top < bounds.top + 8) frame.scrollTop += card.top - bounds.top - 8;
  else if (card.bottom > bounds.bottom - 8) frame.scrollTop += card.bottom - bounds.bottom + 8;
}

function renderNetwork(bundle, preserveAnchor = false) {
  const svg = document.querySelector("#evidence-network");
  const filter = document.querySelector("#network-kind-filter").value;
  const terms = document.querySelector("#network-search").value.normalize("NFKC").trim().toLowerCase().split(/\s+/u).filter(Boolean);
  const graph = makeGraph(bundle);
  const matches = graph.nodes.filter(node => {
    if (filter !== "all" && node.kind !== filter) return false;
    const text = [node.label, node.phrase, node.id, node.data.doi, node.data.document_id, node.data.locator_hint, node.data.provenance?.locator]
      .filter(value => typeof value === "string").join(" ").normalize("NFKC").toLowerCase();
    return terms.every(term => text.includes(term));
  });
  // The task anchor keeps retrieval routes visible when a node category is selected.
  const anchor = graph.nodes.find(node => node.kind === "mission");
  const eligible = filter !== "all" && !terms.length && matches.length && anchor ? [anchor, ...matches] : matches;
  const allById = new Map(graph.nodes.map(node => [node.id, node]));
  const eligibleIds = new Set(eligible.map(node => node.id));
  const toggle = document.querySelector("#atlas-neighborhood");
  const focused = matches.length > 0 && toggle.getAttribute("aria-pressed") === "true";
  const keepSelection = preserveAnchor && (focused || eligibleIds.has(inspectedId));
  const center = (keepSelection ? allById.get(inspectedId) : matches.find(node => node.id === inspectedId))
    ?? matches.find(node => node.id === overviewId) ?? matches[0];
  const eligibleEdges = focused ? graph.edges : graph.edges.filter(edge => eligibleIds.has(edge.from) && eligibleIds.has(edge.to));
  const neighbors = focused ? directRelations(graph.edges, center.id) : new Map();
  const shown = focused ? [center, ...Array.from(neighbors.keys(), id => allById.get(id))] : eligible;
  const buttons = new Map();
  const drawnEdges = [];
  const focusedNode = svg.contains(document.activeElement) ? document.activeElement.dataset.nodeId : null;
  const selectNode = node => {
    const links = directRelations(graph.edges, node.id);
    buttons.get(inspectedId)?.setAttribute("aria-pressed", "false");
    inspectedId = node.id;
    if (!focused) overviewId = node.id;
    buttons.get(node.id)?.setAttribute("aria-pressed", "true");
    for (const [id, button] of buttons) button.classList.toggle("adjacent", links.has(id));
    for (const { edge, path } of drawnEdges) path.classList.toggle("incident", edge.from === node.id || edge.to === node.id);
    inspector(node);
    showNeighborIndex(links, allById, other => {
      if (!focused && !eligibleIds.has(other.id)) {
        toggle.setAttribute("aria-pressed", "true");
        inspectedId = other.id;
        renderNetwork(bundle, true);
      } else {
        inspect(other);
      }
      revealNode(svg.querySelector('[aria-pressed="true"]'));
      document.querySelector("#node-title").focus();
    });
  };
  const scrollFrame = svg.parentElement;
  const inspect = node => {
    if (focused && node.id !== center.id) {
      inspectedId = node.id;
      renderNetwork(bundle, true);
      scrollFrame.scrollTop = 0;
    } else {
      selectNode(node);
    }
  };
  toggle.disabled = !center;
  document.querySelector("#network-count").textContent = focused
    ? `图内相连 ${neighbors.size} 项`
    : `匹配 ${matches.length} / ${graph.nodes.length} 个节点`;
  const width = Math.max(1, scrollFrame.clientWidth);
  const height = focused ? layoutNeighbors(shown, width) : layoutAtlas(shown, width);
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.style.height = height + "px";
  labelMeasure.font = "600 15px " + getComputedStyle(svg).fontFamily;
  const drawing = document.createDocumentFragment();
  const edgeKinds = new Set();
  for (const edge of eligibleEdges) {
    let route;
    if (focused) {
      if (edge.from !== center.id && edge.to !== center.id) continue;
      const other = edge.from === center.id ? edge.to : edge.from;
      const siblings = neighbors.get(other);
      if (!siblings) continue;
      const offset = siblings.length === 1 ? 0 : (siblings.indexOf(edge) / (siblings.length - 1) - .5) * 8;
      route = neighborPath(center, allById.get(other), width, offset);
    } else {
      route = edgePath(allById.get(edge.from), allById.get(edge.to));
    }
    const path = svgPart("path", { class: "graph-edge graph-edge-" + edge.kind, d: route });
    path.append(svgPart("title", {}, edge.label));
    drawing.append(path);
    edgeKinds.add(edge.kind);
    drawnEdges.push({ edge, path });
  }
  for (const item of document.querySelectorAll(".graph-legend li")) item.hidden = !edgeKinds.has(item.className.slice(5));
  document.querySelector(".graph-legend").hidden = !edgeKinds.size;
  for (const node of shown) {
    const group = drawNode(node, neighbors.has(node.id) ? relatedLabels(neighbors.get(node.id)) : undefined);
    group.dataset.nodeId = node.id;
    buttons.set(node.id, group);
    const activate = () => {
      inspect(node);
      if (focused) svg.querySelector('[aria-pressed="true"]')?.focus();
      else if (window.matchMedia("(max-width: 980px)").matches) document.querySelector("#node-title").focus();
    };
    group.addEventListener("click", activate);
    group.addEventListener("keydown", event => {
      if (event.key === "Enter" || event.key === " ") { event.preventDefault(); activate(); }
    });
    drawing.append(group);
  }
  if (!matches.length) drawing.append(svgPart("text", { x: width / 2, y: height / 2, "text-anchor": "middle", class: "atlas-empty" }, "没有匹配节点"));
  svg.replaceChildren(drawing);
  document.querySelector("#atlas-back-to-node").hidden = !matches.length;
  if (focusedNode) buttons.get(focusedNode)?.focus({ preventScroll: true });
  if (center) selectNode(center);
  else {
    inspectedId = null;
    document.querySelector(".atlas-neighbors").hidden = true;
    document.querySelector(".atlas-inspector-label").textContent = "节点详情";
    document.querySelector("#node-title").textContent = "没有匹配节点";
    document.querySelector("#node-inspector").textContent = "可以更改检索词或节点类别。";
  }
}

function loadNetworkBundle(event) {
  const file = event.target.files && event.target.files[0]; const message = document.querySelector("#network-import-message");
  if (!file) return; if (file.size > NETWORK_MAX_BYTES) { message.textContent = "拒绝导入：UI JSON 不得超过 1 MiB。"; return; }
  const reader = new FileReader(); reader.onerror = () => { message.textContent = "无法读取选择的本地文件。"; };
  reader.onload = () => { try { window.networkBundle = validateNetworkBundle(JSON.parse(String(reader.result))); inspectedId = null; overviewId = null; renderNetwork(window.networkBundle); message.textContent = `已导入 ${file.name}；关系仅由许可工件字段派生。`; } catch (error) { message.textContent = `拒绝导入：${error instanceof Error ? error.message : "JSON 无效。"}`; } };
  reader.readAsText(file, "utf-8");
}

document.addEventListener("DOMContentLoaded", () => {
  window.networkBundle = networkDemo;
  renderNetwork(networkDemo);
  document.querySelector("#network-bundle-file").addEventListener("change", loadNetworkBundle);
  document.querySelector("#network-kind-filter").addEventListener("change", () => renderNetwork(window.networkBundle));
  document.querySelector("#network-search").addEventListener("input", () => renderNetwork(window.networkBundle));
  document.querySelector("#atlas-neighborhood").addEventListener("click", event => {
    const button = event.currentTarget;
    const focus = button.getAttribute("aria-pressed") !== "true";
    button.setAttribute("aria-pressed", String(focus));
    renderNetwork(window.networkBundle, true);
    const selected = document.querySelector('#evidence-network [aria-pressed="true"]');
    if (selected) revealNode(selected);
  });
  document.querySelector("#atlas-back-to-node").addEventListener("click", () => {
    document.querySelector('#evidence-network [aria-pressed="true"]')?.focus();
  });
  const frame = document.querySelector(".atlas-plot-window");
  let lastWidth = frame.clientWidth;
  new ResizeObserver(() => {
    if (frame.clientWidth !== lastWidth) { lastWidth = frame.clientWidth; renderNetwork(window.networkBundle, true); }
  }).observe(frame);
});
