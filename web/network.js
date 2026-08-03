"use strict";

const NETWORK_SCHEMA = "1.0";
const NETWORK_MAX_BYTES = 1024 * 1024;
const networkDemo = {
  schema_version: NETWORK_SCHEMA,
  mission: { material: "BiFeO3", property_name: "phase stability" },
  evidence_cards: [{ evidence_id: "evidence_demo_001", claim: "合成示例：条件必须被记录。", stance: "context", review_status: "accepted", provenance: { document_id: "synthetic_demo", locator: "demo" } }],
  condition_matrix: [{ condition_cluster: "外延薄膜 · 压缩应变", supporting_evidence_ids: ["evidence_demo_001"], contradicting_evidence_ids: [], differing_fields: ["thickness"], unknowns: ["oxygen vacancy"] }],
};

function netText(value, fallback = "unknown") { return typeof value === "string" && value.trim() ? value.trim() : fallback; }
function netArray(value) { return Array.isArray(value) ? value : []; }

function validateNetworkBundle(candidate) {
  if (!candidate || typeof candidate !== "object" || Array.isArray(candidate)) throw new Error("JSON 根节点必须是对象。");
  if (candidate.schema_version !== NETWORK_SCHEMA) throw new Error(`仅支持 UI JSON v${NETWORK_SCHEMA}。`);
  for (const key of ["mission", "evidence_cards", "condition_matrix"]) if (!(key in candidate)) throw new Error(`缺少 UI 契约字段：${key}`);
  if (!candidate.mission || !Array.isArray(candidate.evidence_cards) || !Array.isArray(candidate.condition_matrix)) throw new Error("星图字段类型无效。");
  return candidate;
}

function makeGraph(bundle) {
  const nodes = [{ id: "mission", kind: "mission", label: `${netText(bundle.mission.material)} · ${netText(bundle.mission.property_name)}`, x: 490, y: 90, data: bundle.mission }];
  const edges = [];
  const approved = netArray(bundle.evidence_cards).filter((card) => card && card.review_status === "accepted" && card.provenance);
  approved.forEach((card, index) => {
    const id = `evidence:${netText(card.evidence_id)}`;
    nodes.push({ id, kind: "evidence", label: netText(card.evidence_id), x: 185 + (index % 4) * 210, y: 260, data: card });
    edges.push(["mission", id]);
  });
  netArray(bundle.condition_matrix).forEach((row, index) => {
    const id = `condition:${index}`;
    nodes.push({ id, kind: "condition", label: netText(row.condition_cluster), x: 150 + (index % 4) * 230, y: 420, data: row });
    edges.push(["mission", id]);
    [...netArray(row.supporting_evidence_ids), ...netArray(row.contradicting_evidence_ids)].forEach((evidenceId) => edges.push([`evidence:${netText(evidenceId)}`, id]));
    netArray(row.unknowns).forEach((unknown, unknownIndex) => {
      const unknownId = `unknown:${index}:${unknownIndex}`;
      nodes.push({ id: unknownId, kind: "unknown", label: netText(unknown), x: 115 + ((index * 2 + unknownIndex) % 6) * 155, y: 535, data: { condition_cluster: row.condition_cluster, unknown } });
      edges.push([id, unknownId]);
    });
  });
  return { nodes, edges };
}

function inspector(node) {
  document.querySelector("#node-title").textContent = node.label;
  const panel = document.querySelector("#node-inspector");
  const fields = node.kind === "evidence"
    ? [["类型", "已批准证据"], ["立场", netText(node.data.stance)], ["定位", `${netText(node.data.provenance.document_id)} · ${netText(node.data.provenance.locator)}`], ["主张", netText(node.data.claim)]]
    : node.kind === "condition"
      ? [["类型", "条件簇"], ["差异字段", netArray(node.data.differing_fields).join("、") || "未记录"], ["支持证据", netArray(node.data.supporting_evidence_ids).join("、") || "无"], ["反驳证据", netArray(node.data.contradicting_evidence_ids).join("、") || "无"]]
      : node.kind === "unknown" ? [["类型", "待核查项"], ["所属条件簇", netText(node.data.condition_cluster)], ["未知项", netText(node.data.unknown)]]
      : [["类型", "任务锚点"], ["材料", netText(node.data.material)], ["性质", netText(node.data.property_name)]];
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
  graph.edges.filter(([from, to]) => shownIds.has(from) && shownIds.has(to)).forEach(([from, to]) => {
    const a = graph.nodes.find((node) => node.id === from); const b = graph.nodes.find((node) => node.id === to);
    const line = document.createElementNS("http://www.w3.org/2000/svg", "line"); line.setAttribute("x1", a.x); line.setAttribute("y1", a.y); line.setAttribute("x2", b.x); line.setAttribute("y2", b.y); line.setAttribute("class", "graph-edge"); svg.append(line);
  });
  shown.forEach((node) => {
    const group = document.createElementNS("http://www.w3.org/2000/svg", "g"); group.setAttribute("class", `graph-node ${node.kind}`); group.setAttribute("tabindex", "0"); group.setAttribute("role", "button"); group.setAttribute("aria-label", node.label);
    const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle"); circle.setAttribute("cx", node.x); circle.setAttribute("cy", node.y); circle.setAttribute("r", node.kind === "mission" ? "43" : "31");
    const label = document.createElementNS("http://www.w3.org/2000/svg", "text"); label.setAttribute("x", node.x); label.setAttribute("y", node.y + 5); label.setAttribute("text-anchor", "middle"); label.textContent = node.label.length > 18 ? `${node.label.slice(0, 17)}…` : node.label;
    group.append(circle, label); const select = () => inspector(node); group.addEventListener("click", select); group.addEventListener("keydown", (event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); select(); } }); svg.append(group);
  });
  inspector(graph.nodes[0]);
}

function loadNetworkBundle(event) {
  const file = event.target.files && event.target.files[0]; const message = document.querySelector("#network-import-message");
  if (!file) return; if (file.size > NETWORK_MAX_BYTES) { message.textContent = "拒绝导入：UI JSON 不得超过 1 MiB。"; return; }
  const reader = new FileReader(); reader.onerror = () => { message.textContent = "无法读取选择的本地文件。"; };
  reader.onload = () => { try { window.networkBundle = validateNetworkBundle(JSON.parse(String(reader.result))); renderNetwork(window.networkBundle); message.textContent = `已导入 ${file.name}；图仅由许可字段派生。`; } catch (error) { message.textContent = `拒绝导入：${error instanceof Error ? error.message : "JSON 无效。"}`; } };
  reader.readAsText(file, "utf-8");
}

document.addEventListener("DOMContentLoaded", () => { window.networkBundle = networkDemo; renderNetwork(networkDemo); document.querySelector("#network-bundle-file").addEventListener("change", loadNetworkBundle); document.querySelector("#network-kind-filter").addEventListener("change", () => renderNetwork(window.networkBundle)); });
