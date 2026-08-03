"use strict";

const NETWORK_SCHEMA = "1.0";
const NETWORK_MAX_BYTES = 1024 * 1024;
const networkDemo = {
  schema_version: NETWORK_SCHEMA,
  mission: { material: "BiFeO3", property_name: "phase stability" },
  research_guide: { items: [{ order: 1, document_id: "doc_demo", title: "Synthetic strain study", publication_year: 2025, source: "synthetic fixture", locator_hint: "page:1", track: "primary", role: "primary_candidate", content_status: "authorized", evidence_ids: ["evidence_demo_001"] }] },
  evidence_cards: [{ evidence_id: "evidence_demo_001", claim: "合成示例：条件必须被记录。", stance: "support", review_status: "accepted", provenance: { document_id: "doc_demo", locator: "page:1" } }],
  condition_matrix: [{ condition_cluster: "外延薄膜 · 压缩应变", supporting_evidence_ids: ["evidence_demo_001"], contradicting_evidence_ids: [], differing_fields: ["thickness"], unknowns: ["oxygen vacancy"] }],
};

function netText(value, fallback = "unknown") { return typeof value === "string" && value.trim() ? value.trim() : fallback; }
function netArray(value) { return Array.isArray(value) ? value : []; }
function position(index, count, y) { return { x: 110 + ((index + 1) * 780) / (Math.max(count, 1) + 1), y }; }

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
  const addNode = (node) => { if (!byId.has(node.id)) { byId.set(node.id, node); nodes.push(node); } return byId.get(node.id); };
  const mission = addNode({ id: "mission", kind: "mission", label: `${netText(bundle.mission.material)} · ${netText(bundle.mission.property_name)}`, x: 500, y: 82, data: bundle.mission });
  const guideItems = bundle.research_guide && Array.isArray(bundle.research_guide.items) ? bundle.research_guide.items : [];
  guideItems.slice(0, 12).forEach((item, index) => {
    const point = position(index, Math.min(guideItems.length, 12), 220);
    const paper = addNode({ id: `paper:${netText(item.document_id)}`, kind: "paper", label: netText(item.title), x: point.x, y: point.y, data: item });
    edges.push({ from: mission.id, to: paper.id, kind: "retrieval_candidate", label: item.track === "counterevidence" ? "反例检索候选" : "主检索候选" });
  });
  const approved = netArray(bundle.evidence_cards).filter((card) => card && card.review_status === "accepted" && card.provenance);
  approved.forEach((card, index) => {
    const point = position(index, Math.max(approved.length, 1), 365);
    const evidence = addNode({ id: `evidence:${netText(card.evidence_id)}`, kind: "evidence", label: netText(card.evidence_id), x: point.x, y: point.y, data: card });
    const paperId = `paper:${netText(card.provenance.document_id)}`;
    if (!byId.has(paperId)) {
      const paperPoint = position(byId.size, Math.max(approved.length, 1), 220);
      addNode({ id: paperId, kind: "paper", label: netText(card.provenance.document_id), x: paperPoint.x, y: paperPoint.y, data: { document_id: card.provenance.document_id, title: card.provenance.document_id, source: "evidence provenance", content_status: "authorized", track: "unclassified", role: "evidence_source", evidence_ids: [card.evidence_id] } });
      edges.push({ from: mission.id, to: paperId, kind: "retrieval_candidate", label: "证据出处论文" });
    }
    edges.push({ from: paperId, to: evidence.id, kind: "source_provenance", label: "document_id + locator" });
  });
  netArray(bundle.condition_matrix).forEach((row, index) => {
    const point = position(index, Math.max(netArray(bundle.condition_matrix).length, 1), 510);
    const condition = addNode({ id: `condition:${index}`, kind: "condition", label: netText(row.condition_cluster), x: point.x, y: point.y, data: row });
    netArray(row.supporting_evidence_ids).forEach((evidenceId) => edges.push({ from: `evidence:${netText(evidenceId)}`, to: condition.id, kind: "support", label: "审核支持" }));
    netArray(row.contradicting_evidence_ids).forEach((evidenceId) => edges.push({ from: `evidence:${netText(evidenceId)}`, to: condition.id, kind: "contradict", label: "审核反驳" }));
    netArray(row.unknowns).forEach((unknown, unknownIndex) => {
      const unknownPoint = position(index * 3 + unknownIndex, Math.max(netArray(row.unknowns).length * Math.max(netArray(bundle.condition_matrix).length, 1), 1), 635);
      const unknownNode = addNode({ id: `unknown:${index}:${unknownIndex}`, kind: "unknown", label: netText(unknown), x: unknownPoint.x, y: unknownPoint.y, data: { condition_cluster: row.condition_cluster, unknown } });
      edges.push({ from: condition.id, to: unknownNode.id, kind: "open_question", label: "待核查" });
    });
  });
  return { nodes, edges: edges.filter((edge) => byId.has(edge.from) && byId.has(edge.to)) };
}

function inspector(node) {
  document.querySelector("#node-title").textContent = node.label;
  const panel = document.querySelector("#node-inspector");
  let fields;
  if (node.kind === "paper") fields = [["类型", "有界候选论文"], ["阅读角色", netText(node.data.role)], ["检索轨道", netText(node.data.track)], ["访问状态", netText(node.data.content_status)], ["来源定位", netText(node.data.locator_hint, "未记录")], ["关联证据", netArray(node.data.evidence_ids).join("、") || "尚无"]];
  else if (node.kind === "evidence") fields = [["类型", "已批准证据"], ["立场", netText(node.data.stance)], ["定位", `${netText(node.data.provenance.document_id)} · ${netText(node.data.provenance.locator)}`], ["主张", netText(node.data.claim)]];
  else if (node.kind === "condition") fields = [["类型", "条件簇"], ["差异字段", netArray(node.data.differing_fields).join("、") || "未记录"], ["支持证据", netArray(node.data.supporting_evidence_ids).join("、") || "无"], ["反驳证据", netArray(node.data.contradicting_evidence_ids).join("、") || "无"]];
  else if (node.kind === "unknown") fields = [["类型", "待核查项"], ["所属条件簇", netText(node.data.condition_cluster)], ["未知项", netText(node.data.unknown)]];
  else fields = [["类型", "任务锚点"], ["材料", netText(node.data.material)], ["性质", netText(node.data.property_name)]];
  const list = document.createElement("dl"); list.className = "inspector-list";
  fields.forEach(([name, value]) => { const row = document.createElement("div"); const key = document.createElement("dt"); const body = document.createElement("dd"); key.textContent = name; body.textContent = value; row.append(key, body); list.append(row); });
  panel.replaceChildren(list);
}

function renderNetwork(bundle) {
  const svg = document.querySelector("#evidence-network");
  const filter = document.querySelector("#network-kind-filter").value;
  const graph = makeGraph(bundle);
  const shown = graph.nodes.filter((node) => filter === "all" || node.kind === "mission" || node.kind === filter);
  const shownIds = new Set(shown.map((node) => node.id));
  svg.replaceChildren();
  graph.edges.filter((edge) => shownIds.has(edge.from) && shownIds.has(edge.to)).forEach((edge) => {
    const a = graph.nodes.find((node) => node.id === edge.from); const b = graph.nodes.find((node) => node.id === edge.to);
    const line = document.createElementNS("http://www.w3.org/2000/svg", "line"); line.setAttribute("x1", a.x); line.setAttribute("y1", a.y); line.setAttribute("x2", b.x); line.setAttribute("y2", b.y); line.setAttribute("class", `graph-edge graph-edge-${edge.kind}`); const title = document.createElementNS("http://www.w3.org/2000/svg", "title"); title.textContent = edge.label; line.append(title); svg.append(line);
  });
  shown.forEach((node) => {
    const group = document.createElementNS("http://www.w3.org/2000/svg", "g"); group.setAttribute("class", `graph-node ${node.kind}`); group.setAttribute("tabindex", "0"); group.setAttribute("role", "button"); group.setAttribute("aria-label", node.label);
    const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle"); circle.setAttribute("cx", node.x); circle.setAttribute("cy", node.y); circle.setAttribute("r", node.kind === "mission" ? "43" : node.kind === "paper" ? "35" : "31");
    const label = document.createElementNS("http://www.w3.org/2000/svg", "text"); label.setAttribute("x", node.x); label.setAttribute("y", node.y + 5); label.setAttribute("text-anchor", "middle"); label.textContent = node.label.length > 18 ? `${node.label.slice(0, 17)}…` : node.label;
    group.append(circle, label); const select = () => inspector(node); group.addEventListener("click", select); group.addEventListener("keydown", (event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); select(); } }); svg.append(group);
  });
  inspector(graph.nodes[0]);
}

function loadNetworkBundle(event) {
  const file = event.target.files && event.target.files[0]; const message = document.querySelector("#network-import-message");
  if (!file) return; if (file.size > NETWORK_MAX_BYTES) { message.textContent = "拒绝导入：UI JSON 不得超过 1 MiB。"; return; }
  const reader = new FileReader(); reader.onerror = () => { message.textContent = "无法读取选择的本地文件。"; };
  reader.onload = () => { try { window.networkBundle = validateNetworkBundle(JSON.parse(String(reader.result))); renderNetwork(window.networkBundle); message.textContent = `已导入 ${file.name}；关系仅由许可工件字段派生。`; } catch (error) { message.textContent = `拒绝导入：${error instanceof Error ? error.message : "JSON 无效。"}`; } };
  reader.readAsText(file, "utf-8");
}

document.addEventListener("DOMContentLoaded", () => { window.networkBundle = networkDemo; renderNetwork(networkDemo); document.querySelector("#network-bundle-file").addEventListener("change", loadNetworkBundle); document.querySelector("#network-kind-filter").addEventListener("change", () => renderNetwork(window.networkBundle)); });