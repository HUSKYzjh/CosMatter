"use strict";

const EXTENSION_MAX_BYTES = 1024 * 1024;
const EXTENSIONS = [
  { id: "database", icon: "◈", name: "星港交叉核验", subtitle: "材料数据库与文献条件对照", task: "针对已批准主张，核查结构、组分、计算设置和可比条件。", gate: "记录数据源、查询日期、字段映射与许可，再由人工确认差异。", output: "database_crosscheck_brief" },
  { id: "experiment", icon: "△", name: "实验远征设计", subtitle: "变量、对照与量测航线", task: "将条件分歧转为可操作的样品、变量、表征和失败判据。", gate: "必须定义对照、资源约束和安全审查；不得由浏览器自动执行。", output: "experiment_mission_brief" },
  { id: "computation", icon: "▣", name: "计算航程编排", subtitle: "模拟复现与敏感性扫描", task: "设计可复现的计算基线、扫描范围与验证输出。", gate: "HPC/容器提交由受控后端和人工审批执行；本页只生成规划草案。", output: "computation_mission_brief" },
  { id: "evaluation", icon: "◎", name: "评测星图校准", subtitle: "冻结问题、盲审与再现性", task: "把发现、条件完整性、反证与可复跑性转化为可报告指标。", gate: "冻结集和人工核查记录必须版本化，不能用演示卡替代真实评测。", output: "evaluation_extension_brief" },
];
let selectedExtension = null;
let extensionBundle = null;

function extensionText(value, fallback = "未记录") { return typeof value === "string" && value.trim() ? value.trim() : fallback; }
function extensionArray(value) { return Array.isArray(value) ? value : []; }
function validateExtensionBundle(candidate) {
  if (!candidate || typeof candidate !== "object" || Array.isArray(candidate) || candidate.schema_version !== "1.0") throw new Error("仅支持 UI JSON v1.0。");
  if (!candidate.mission || typeof candidate.mission !== "object" || !Array.isArray(candidate.evidence_cards) || !Array.isArray(candidate.condition_matrix)) throw new Error("缺少任务、证据或条件矩阵字段。");
  return candidate;
}
function extensionBasis() {
  if (!extensionBundle) return { context_status: "template_without_run_context", approved_evidence_count: 0, condition_clusters: [], unknowns: [] };
  const matrix = extensionArray(extensionBundle.condition_matrix).slice(0, 8);
  return {
    context_status: "redacted_ui_projection",
    mission: { mission_id: extensionText(extensionBundle.mission.mission_id), material: extensionText(extensionBundle.mission.material), property_name: extensionText(extensionBundle.mission.property_name) },
    approved_evidence_count: extensionArray(extensionBundle.evidence_cards).filter((card) => card && card.review_status === "accepted").length,
    condition_clusters: matrix.map((row) => extensionText(row && row.condition_cluster)),
    unknowns: matrix.flatMap((row) => extensionArray(row && row.unknowns)).slice(0, 12),
  };
}
function renderExtensions() {
  const grid = document.querySelector("#extension-grid"); const basis = extensionBasis();
  grid.replaceChildren(...EXTENSIONS.map((extension) => {
    const card = document.createElement("article"); card.className = "extension-card"; card.tabIndex = 0; card.setAttribute("role", "button"); card.setAttribute("aria-pressed", String(selectedExtension && selectedExtension.id === extension.id));
    card.innerHTML = `<span class="extension-icon" aria-hidden="true">${extension.icon}</span><p class="eyebrow"></p><h2></h2><p></p><p class="extension-gate"></p>`;
    card.querySelector(".eyebrow").textContent = extension.subtitle; card.querySelector("h2").textContent = extension.name; card.querySelector("h2").insertAdjacentText("afterend", basis.context_status === "redacted_ui_projection" ? `${extension.task} 当前投影含 ${basis.approved_evidence_count} 条已批准证据与 ${basis.unknowns.length} 项待核查条件。` : extension.task); card.querySelector(".extension-gate").textContent = `门禁：${extension.gate}`;
    const choose = () => { selectedExtension = extension; document.querySelector("#extension-status").textContent = `已选择“${extension.name}”。下载内容为带有限本地上下文、待人工确认的 JSON 草案。`; document.querySelector("#download-extension").disabled = false; renderExtensions(); };
    card.addEventListener("click", choose); card.addEventListener("keydown", (event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); choose(); } }); return card;
  }));
}
function loadExtensionBundle(event) {
  const file = event.target.files && event.target.files[0]; const message = document.querySelector("#extension-import-message");
  if (!file) return; if (file.size > EXTENSION_MAX_BYTES) { message.textContent = "拒绝导入：UI JSON 不得超过 1 MiB。"; return; }
  const reader = new FileReader(); reader.onerror = () => { message.textContent = "无法读取选择的本地文件。"; };
  reader.onload = () => { try { extensionBundle = validateExtensionBundle(JSON.parse(String(reader.result))); const basis = extensionBasis(); message.textContent = `已导入 ${file.name}：${basis.approved_evidence_count} 条已批准证据，${basis.unknowns.length} 项待核查条件。`; renderExtensions(); } catch (error) { message.textContent = `拒绝导入：${error instanceof Error ? error.message : "JSON 无效。"}`; } };
  reader.readAsText(file, "utf-8");
}
function downloadExtension() {
  if (!selectedExtension) return;
  const payload = { schema_version: "0.2", artifact_type: selectedExtension.output, trust_status: "untrusted_research_extension_draft", generated_at: new Date().toISOString(), facility: selectedExtension.id, objective: selectedExtension.task, required_gate: selectedExtension.gate, evidence_basis: extensionBasis(), next_action: "Human review and approved backend execution required." };
  const href = URL.createObjectURL(new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" }));
  const link = document.createElement("a"); link.href = href; link.download = `${selectedExtension.output}.json`; link.click(); URL.revokeObjectURL(href);
}
document.addEventListener("DOMContentLoaded", () => { renderExtensions(); document.querySelector("#download-extension").addEventListener("click", downloadExtension); document.querySelector("#extension-bundle-file").addEventListener("change", loadExtensionBundle); });