"use strict";

const WORKFLOW_SCHEMA = "1.0";
const MAX_WORKFLOW_BUNDLE_BYTES = 1024 * 1024;
const WORKFLOW_STEPS = [
  ["question_intake", "舰桥接令", "问题、范围与内容许可"],
  ["research_planning", "航线规划", "人工批准的子问题与反例查询"],
  ["search_selection", "远程扫描", "受控主检索与反例检索"],
  ["evidence_extraction", "信号解读", "定位、短摘录和条件记录"],
  ["cross_check_review", "导航校验", "审核、条件差分与反证"],
  ["report_delivery", "星图交付", "仅交付已接受证据的清单式报告"],
];

const workflowDemo = {
  schema_version: WORKFLOW_SCHEMA,
  generated_at: "2026-08-04T00:00:00+00:00",
  mission: { question: "为什么不同薄膜研究出现相反结论？", material: "BiFeO3", property_name: "phase stability" },
  status: { mission_state: "INTAKE", return_reason: null },
  stations: WORKFLOW_STEPS.slice(0, 5).map(([station_type], index) => ({ station_type, status: index === 0 ? "active" : "waiting" })),
  fleet_assignment: { release_gate: "cross_check_review" },
};

function wfText(value, fallback = "unknown") { return typeof value === "string" && value.trim() ? value.trim() : fallback; }

function validateWorkflowBundle(candidate) {
  if (!candidate || typeof candidate !== "object" || Array.isArray(candidate)) throw new Error("JSON 根节点必须是对象。");
  if (candidate.schema_version !== WORKFLOW_SCHEMA) throw new Error(`仅支持 UI JSON v${WORKFLOW_SCHEMA}。`);
  for (const key of ["mission", "status", "stations", "fleet_assignment"]) if (!(key in candidate)) throw new Error(`缺少 UI 契约字段：${key}`);
  if (!candidate.mission || !candidate.status || !candidate.fleet_assignment || !Array.isArray(candidate.stations)) throw new Error("工作流工件字段类型无效。");
  if ("research_guide" in candidate && candidate.research_guide !== null && (!candidate.research_guide || typeof candidate.research_guide !== "object" || !Array.isArray(candidate.research_guide.items))) throw new Error("research_guide 字段无效。");
  return candidate;
}

function workflowCommand(station, bundle) {
  const runId = "<run-id>";
  if (station === "research_planning") return `审核计划后：python -m cosmatter approve-plan --run-id ${runId} --input reviewed_plan.json`;
  if (station === "search_selection") return `执行主检索：python -m cosmatter execute-plan-query --run-id ${runId} --query-index 0；反例检索增加 --counter。`;
  if (station === "evidence_extraction") return `录入可定位证据：python -m cosmatter ingest-evidence --run-id ${runId} --input evidence_draft.json`;
  if (station === "cross_check_review") return `生成条件差分：python -m cosmatter diagnose-conditions --run-id ${runId}`;
  if (station === "report_delivery") return `生成并投影报告：python -m cosmatter build-report --run-id ${runId}；随后 export-ui。`;
  return `在任务舰桥定义问题与许可范围；系统当前状态为 ${wfText(bundle.status.mission_state)}。`;
}

function renderReadingGuide(guide) {
  const target = document.querySelector("#reading-guide-cards");
  const caveat = document.querySelector("#reading-guide-caveat");
  const items = guide && typeof guide === "object" && Array.isArray(guide.items) ? guide.items : [];
  if (!items.length) {
    target.replaceChildren(Object.assign(document.createElement("p"), { className: "notice", textContent: "尚未生成阅读路线。请在完成受控检索后运行 build-reading-guide。" }));
    caveat.textContent = "阅读路线只能从已批准计划与本运行候选工件生成；无路线不代表材料文献或现象不存在。";
    return;
  }
  const roleLabel = { verified_evidence: "已核验证据", primary_candidate: "主检索候选", counterevidence_candidate: "反例候选" };
  target.replaceChildren(...items.map((item) => {
    const card = document.createElement("article"); card.className = `reading-guide-card ${item.track === "counterevidence" ? "counter-route" : "primary-route"}`;
    const header = document.createElement("header"); const order = document.createElement("span"); order.className = "route-order"; order.textContent = String(item.order || "?").padStart(2, "0"); const badge = document.createElement("span"); badge.className = "route-badge"; badge.textContent = roleLabel[item.role] || "候选"; header.append(order, badge);
    const title = document.createElement("h3"); title.textContent = wfText(item.title);
    const meta = document.createElement("p"); meta.className = "route-meta"; meta.textContent = `${wfText(item.source)} · ${item.publication_year || "年份未知"} · ${item.content_status === "authorized" ? "内容访问已授权" : "仅元数据"}`;
    const linked = document.createElement("p"); linked.className = "route-linked"; linked.textContent = Array.isArray(item.evidence_ids) && item.evidence_ids.length ? `已关联证据：${item.evidence_ids.join("、")}` : "尚无已接受证据关联";
    card.append(header, title, meta, linked); return card;
  }));
  caveat.textContent = Array.isArray(guide.caveats) && guide.caveats.length ? guide.caveats.join(" ") : "阅读路线仅组织已批准工件，不代表论文内容已被证实。";
}

function renderWorkflow(bundle) {
  const mission = bundle.mission;
  document.querySelector("#workflow-mission").textContent = `${wfText(mission.material)} · ${wfText(mission.property_name)}：${wfText(mission.question)}`;
  document.querySelector("#workflow-state").textContent = `当前状态：${wfText(bundle.status.mission_state)}${bundle.status.return_reason ? ` · 退回原因：${wfText(bundle.status.return_reason)}` : ""}`;
  renderReadingGuide(bundle.research_guide);
  const current = new Map(bundle.stations.map((item) => [item.station_type, item.status]));
  const lane = document.querySelector("#workflow-lane");
  lane.replaceChildren(...WORKFLOW_STEPS.map(([station, title, detail], index) => {
    const status = current.get(station) || "waiting";
    const item = document.createElement("article");
    item.className = `workflow-step ${status}`;
    item.tabIndex = 0;
    item.setAttribute("role", "button");
    item.setAttribute("aria-label", `${title}：${status}`);
    item.innerHTML = `<span class="workflow-index">${String(index + 1).padStart(2, "0")}</span><h2></h2><p></p><span class="workflow-status"></span>`;
    item.querySelector("h2").textContent = title;
    item.querySelector("p").textContent = detail;
    item.querySelector(".workflow-status").textContent = status;
    const select = () => { document.querySelector("#workflow-command").textContent = workflowCommand(station, bundle); };
    item.addEventListener("click", select);
    item.addEventListener("keydown", (event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); select(); } });
    return item;
  }));
  const gate = wfText(bundle.fleet_assignment.release_gate, "cross_check_review");
  const gatePanel = document.querySelector("#workflow-gates");
  const accepted = bundle.stations.some((item) => item.station_type === gate && ["done", "complete"].includes(item.status));
  gatePanel.replaceChildren(
    Object.assign(document.createElement("p"), { textContent: `报告门禁：${gate}` }),
    Object.assign(document.createElement("p"), { className: accepted ? "gate-ok" : "gate-waiting", textContent: accepted ? "门禁状态：已达到（仍需人工确认发布）。" : "门禁状态：未达到；报告不会被前端或 CLI 跳步生成。" })
  );
  const active = bundle.stations.find((item) => item.status === "active");
  document.querySelector("#workflow-command").textContent = workflowCommand(active ? active.station_type : "question_intake", bundle);
}

function loadWorkflowBundle(event) {
  const file = event.target.files && event.target.files[0];
  const message = document.querySelector("#workflow-import-message");
  if (!file) return;
  if (file.size > MAX_WORKFLOW_BUNDLE_BYTES) { message.textContent = "拒绝导入：UI JSON 不得超过 1 MiB。"; return; }
  const reader = new FileReader();
  reader.onerror = () => { message.textContent = "无法读取选择的本地文件。"; };
  reader.onload = () => {
    try { const bundle = validateWorkflowBundle(JSON.parse(String(reader.result))); renderWorkflow(bundle); message.textContent = `已导入 ${file.name}；只读取本地工件。`; }
    catch (error) { message.textContent = `拒绝导入：${error instanceof Error ? error.message : "JSON 无效。"}`; }
  };
  reader.readAsText(file, "utf-8");
}

document.addEventListener("DOMContentLoaded", () => {
  renderWorkflow(workflowDemo);
  document.querySelector("#workflow-bundle-file").addEventListener("change", loadWorkflowBundle);
});
