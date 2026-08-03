"use strict";

// This page never fetches. It renders either this synthetic demo bundle or a
// JSON file selected explicitly by the user from their local machine.
const UI_SCHEMA_VERSION = "1.0";
const MAX_BUNDLE_BYTES = 1024 * 1024;

const stationLabels = {
  question_intake: "舰桥接令",
  research_planning: "航线规划",
  search_selection: "远程扫描",
  evidence_extraction: "信号解读",
  cross_check_review: "导航校验",
  report_delivery: "星图交付",
};

const facilityLabels = {
  sector_cartography: ["星区测绘阵列", "Sector Cartography"],
  timeline_observatory: ["时间线观测台", "Timeline Observatory"],
  citation_array: ["引文阵列", "Citation Array"],
  source_locator: ["原文定位镜", "Source Locator"],
  evidence_comparator: ["证据比对台", "Evidence Comparator"],
  condition_recorder: ["条件记录仪", "Condition Recorder"],
  trajectory_overlay: ["航迹叠加仪", "Trajectory Overlay"],
  condition_differential: ["条件差分舱", "Condition Differential Chamber"],
  counterevidence_detector: ["反证探测器", "Counterevidence Detector"],
  blind_spot_scan: ["盲区扫描仪", "Blind Spot Scan"],
  variable_combination_scan: ["变量组合扫描仪", "Variable Combination Scan"],
  hypothesis_triage: ["假设分诊台", "Hypothesis Triage"],
  experiment_mission_design: ["实验任务设计器", "Experiment Mission Design"],
  computation_mission_design: ["计算任务设计器", "Computation Mission Design"],
  falsification_monitor: ["证伪监测器", "Falsification Monitor"],
};

const demoBundle = {
  schema_version: UI_SCHEMA_VERSION,
  generated_at: "2026-08-03T00:00:00+00:00",
  mission: {
    mission_id: "mission_demo_route_001",
    question: "为什么两篇论文对 BiFeO3 外延薄膜应变相变有不同结论？",
    material: "BiFeO3",
    property_name: "phase stability",
    scope: "epitaxial thin films",
    source_policy: "authorized",
  },
  fleet_assignment: {
    assignment_id: "assignment_demo_route_001",
    fleet_type: "route_diagnostics",
    display_name_zh: "航道诊断舰队",
    display_name_en: "Route Diagnostics Fleet",
    mission_type: "literature_discrepancy",
    reason: "演示工件：任务含有“不同结论”信号。",
    release_gate: "cross_check_review",
  },
  status: { mission_state: "INTAKE", retry_count: 0, retry_budget: 2, return_reason: null },
  stations: [
    { station_type: "question_intake", status: "active" },
    { station_type: "research_planning", status: "waiting" },
    { station_type: "search_selection", status: "waiting" },
    { station_type: "evidence_extraction", status: "waiting" },
    { station_type: "cross_check_review", status: "waiting" },
  ],
  facilities: [
    { facility_type: "trajectory_overlay", status: "queued" },
    { facility_type: "condition_differential", status: "queued" },
    { facility_type: "counterevidence_detector", status: "queued" },
  ],
  evidence_cards: [{
    evidence_id: "evidence_synthetic_001",
    claim: "合成演示：比较前必须显式记录应变、衬底、厚度与表征条件。",
    stance: "context",
    conditions: { sample_form: "epitaxial thin film", strain_percent: null, temperature: null, method: "synthetic demonstration" },
    review_status: "accepted",
    quote: "Synthetic demonstration only; no paper text is included.",
    provenance: { document_id: "synthetic_demo_not_a_paper", locator: "demo fixture", source: "CosMatter example", access_policy: "local_only" },
    is_synthetic: true,
  }],
  verification_decisions: [],
  condition_matrix: [{ condition_cluster: "外延薄膜 · 压缩应变", supporting_evidence_ids: [], contradicting_evidence_ids: [], unknowns: ["厚度", "氧空位"] }],
  mission_report: null,
};

let activeBundle = demoBundle;
let activeBundleSource = { name: "合成演示工件", bytes: null };

function text(value, fallback = "unknown") {
  return typeof value === "string" && value.trim() ? value.trim() : fallback;
}

function asArray(value) {
  return Array.isArray(value) ? value : [];
}

function setText(selector, value) {
  const target = document.querySelector(selector);
  if (target) target.textContent = value;
}

function element(tag, content, className) {
  const node = document.createElement(tag);
  if (content !== undefined) node.textContent = content;
  if (className) node.className = className;
  return node;
}

function validateBundle(candidate) {
  if (!candidate || typeof candidate !== "object" || Array.isArray(candidate)) throw new Error("JSON 根节点必须是对象。");
if (candidate.schema_version !== UI_SCHEMA_VERSION) throw new Error(`仅支持 UI JSON v${UI_SCHEMA_VERSION}。`);
  if ("generated_at" in candidate && !text(candidate.generated_at, "")) throw new Error("generated_at 必须是非空字符串。");
  for (const key of ["mission", "fleet_assignment", "status", "stations", "facilities", "evidence_cards", "condition_matrix"]) {
    if (!(key in candidate)) throw new Error(`缺少 UI 契约字段：${key}`);
  }
  if (!candidate.mission || !candidate.fleet_assignment || !candidate.status) throw new Error("任务、舰队和状态字段必须是对象。");
  for (const key of ["question", "material", "property_name", "scope", "source_policy"]) {
    if (!text(candidate.mission[key], "")) throw new Error(`任务字段无效：${key}`);
  }
  if (!text(candidate.fleet_assignment.display_name_zh, "")) throw new Error("舰队中文名称不能为空。");
if ("timeline" in candidate && (!Array.isArray(candidate.timeline) || !candidate.timeline.every((entry) => entry && typeof entry === "object" && ["station_type", "action", "state", "occurred_at"].every((key) => text(entry[key], ""))))) {
    throw new Error("timeline 必须是脱敏动作摘要数组。");
  }
  for (const key of ["stations", "facilities", "evidence_cards", "condition_matrix"]) {
    if (!Array.isArray(candidate[key])) throw new Error(`${key} 必须是数组。`);
  }
  return candidate;
}

function renderJourney(stations) {
  const list = document.querySelector("#stations-list");
  list.replaceChildren(...stations.map((station) => {
    const item = element("li", stationLabels[station.station_type] || text(station.station_type));
    if (station.status === "active") item.classList.add("active");
    if (station.status === "done" || station.status === "complete") item.classList.add("done");
    return item;
  }));
}

function renderFacilities(facilities) {
  const list = document.querySelector("#facilities-list");
  list.replaceChildren(...facilities.map((facility) => {
    const [zh, en] = facilityLabels[facility.facility_type] || [text(facility.facility_type), "Unknown facility"];
    const card = element("article", undefined, "facility");
    card.append(element("strong", zh), element("small", en), element("code", text(facility.facility_type)));
    return card;
  }));
}

function replaceSelectOptions(selector, values, allLabel) {
  const select = document.querySelector(selector);
  if (!select) return;
  const current = select.value;
  select.replaceChildren(element("option", allLabel));
  select.firstChild.value = "all";
  values.forEach((value) => {
    const option = element("option", value);
    option.value = value;
    select.append(option);
  });
  select.value = [...select.options].some((option) => option.value === current) ? current : "all";
}

function configureEvidenceFilters(cards) {
  const approved = cards.filter((card) => card && card.review_status === "accepted" && card.provenance && text(card.quote, ""));
  replaceSelectOptions("#evidence-stance-filter", [...new Set(approved.map((card) => text(card.stance)))].sort(), "全部立场");
  const conditionKeys = [...new Set(approved.flatMap((card) => Object.keys(card.conditions && typeof card.conditions === "object" ? card.conditions : {})))].sort();
  replaceSelectOptions("#evidence-condition-filter", conditionKeys, "全部条件字段");
}

function renderTimeline(entries) {
  const list = document.querySelector("#run-timeline");
  if (!list) return;
  if (!entries.length) {
    list.replaceChildren(element("li", "尚无可安全投影的航程动作。", "timeline-empty"));
    return;
  }
  list.replaceChildren(...entries.map((entry) => {
    const item = element("li", undefined, "timeline-item");
    const marker = element("span", "", "timeline-marker");
    const content = element("div");
    content.append(element("strong", text(entry.action)), element("span", `${text(entry.station_type)} · ${text(entry.state)}`, "timeline-meta"), element("time", text(entry.occurred_at), "timeline-meta"));
    item.append(marker, content);
    return item;
  }));
}

function renderEvidence(cards) {
  const list = document.querySelector("#evidence-list");
  const approved = cards.filter((card) => card && card.review_status === "accepted" && card.provenance && text(card.quote, ""));
  const stance = document.querySelector("#evidence-stance-filter").value;
  const conditionKey = document.querySelector("#evidence-condition-filter").value;
  const needle = document.querySelector("#evidence-query-filter").value.trim().toLocaleLowerCase("zh-CN");
  const visible = approved.filter((card) => {
    if (stance !== "all" && card.stance !== stance) return false;
    if (conditionKey !== "all" && !(conditionKey in (card.conditions || {}))) return false;
    const searchable = [card.claim, card.quote, card.provenance.document_id, card.provenance.locator, ...Object.values(card.conditions || {})]
      .map((value) => value === null ? "unknown" : String(value)).join(" ").toLocaleLowerCase("zh-CN");
    return !needle || searchable.includes(needle);
  });
  setText("#evidence-filter-summary", `已显示 ${visible.length} / ${approved.length} 张已批准证据卡；未批准证据不会导出到浏览器。`);
  if (!visible.length) {
    list.replaceChildren(element("p", approved.length ? "没有证据卡符合当前筛选条件。" : "当前没有可公开显示的已批准证据卡。", "notice"));
    return;
  }
  list.replaceChildren(...visible.map((card) => {
    const article = element("article", undefined, "evidence-card");
    const top = element("div", undefined, "card-topline");
    top.append(element("span", `${text(card.review_status)}${card.is_synthetic ? " · 合成示例" : ""}`, "state-chip accepted"), element("code", text(card.evidence_id)));
    const claim = element("p", text(card.claim), "claim");
    const conditions = element("dl", undefined, "conditions");
    Object.entries(card.conditions && typeof card.conditions === "object" ? card.conditions : {}).forEach(([key, value]) => {
      const row = element("div");
      row.append(element("dt", key), element("dd", value === null ? "unknown" : text(String(value))));
      conditions.append(row);
    });
    const quote = element("p", `短摘录：${text(card.quote)}`, "quote");
    const footer = element("footer");
    footer.append(element("span", `document_id: ${text(card.provenance.document_id)}`), element("span", `locator: ${text(card.provenance.locator)}`));
    article.append(top, claim, conditions, quote, footer);
    return article;
  }));
}

function matrixDetail(rowData) {
  const detail = element("details", undefined, "matrix-detail");
  detail.append(element("summary", "展开差异字段与证据 ID"));
  const items = [
    ["差异字段", asArray(rowData.differing_fields)],
    ["支持证据", asArray(rowData.supporting_evidence_ids)],
    ["反驳证据", asArray(rowData.contradicting_evidence_ids)],
  ];
  const list = element("ul");
  items.forEach(([label, values]) => list.append(element("li", `${label}：${values.length ? values.map((value) => text(String(value))).join("、") : "未记录"}`)));
  detail.append(list);
  return detail;
}

function renderMatrix(rows) {
  const body = document.querySelector("#condition-matrix-body");
  if (!rows.length) {
    const row = element("tr");
    const cell = element("td", "尚无已批准的条件矩阵工件。", "empty-cell");
    cell.colSpan = 5;
    row.append(cell);
    body.replaceChildren(row);
    return;
  }
  body.replaceChildren(...rows.map((rowData) => {
    const row = element("tr");
    const support = asArray(rowData.supporting_evidence_ids).length ? `证据 ${asArray(rowData.supporting_evidence_ids).length} 条` : "待定位";
    const contradict = asArray(rowData.contradicting_evidence_ids).length ? `证据 ${asArray(rowData.contradicting_evidence_ids).length} 条` : "待反例检索";
    row.append(
      element("td", text(rowData.condition_cluster)),
      element("td", support),
      element("td", contradict),
      element("td", asArray(rowData.unknowns).map((item) => text(String(item))).join("、") || "无"),
      (() => { const cell = element("td"); cell.append(matrixDetail(rowData)); return cell; })()
    );
    return row;
  }));
}

function renderReport(report) {
  const target = document.querySelector("#mission-report");
  if (!target) return;
  if (!report || typeof report !== "object") {
    target.replaceChildren(element("p", "No review-gated mission report has been exported for this run.", "notice"));
    return;
  }
  const article = element("article", undefined, "evidence-card");
  article.append(element("p", text(report.summary), "claim"));
  const evidenceIds = asArray(report.evidence_ids).map((item) => text(String(item))).filter((item) => item !== "unknown");
  article.append(element("p", `Accepted evidence cards: ${evidenceIds.length}`, "quote"));
  const limitations = asArray(report.limitations);
  if (limitations.length) {
    const list = element("ul");
    limitations.forEach((item) => list.append(element("li", text(String(item)))));
    article.append(element("h3", "Limitations"), list);
  }
  const nextSteps = asArray(report.next_steps);
  if (nextSteps.length) {
    const list = element("ul");
    nextSteps.forEach((item) => list.append(element("li", text(String(item)))));
    article.append(element("h3", "Next validation steps"), list);
  }
  target.replaceChildren(article);
}
function renderBundleMetadata(bundle, source) {
  const target = document.querySelector("#bundle-metadata");
  if (!target) return;
  const sourceLabel = source && source.name ? source.name : "当前本地预览";
  const sourceSize = source && Number.isInteger(source.bytes) ? `${source.bytes.toLocaleString("en-US")} bytes` : "无文件传输";
  const accepted = asArray(bundle.evidence_cards).filter((card) => card && card.review_status === "accepted").length;
  const rows = [
    ["来源", sourceLabel],
    ["工件版本", `UI JSON v${text(bundle.schema_version)}`],
    ["生成时间", text(bundle.generated_at, "未声明")],
    ["本地文件大小", sourceSize],
    ["可显示证据", `${accepted} 张已批准卡`],
    ["条件矩阵", `${asArray(bundle.condition_matrix).length} 个条件簇`],
  ];
  target.replaceChildren(...rows.map(([key, value]) => { const row = element("div"); row.append(element("dt", key), element("dd", value)); return row; }));
}

function renderBundle(bundle) {
  const mission = bundle.mission;
  const fleet = bundle.fleet_assignment;
  const status = bundle.status;
  document.querySelector("#question").value = text(mission.question);
  document.querySelector("#material").value = text(mission.material);
  document.querySelector("#property").value = text(mission.property_name);
  document.querySelector("#scope").value = text(mission.scope);
  const policy = document.querySelector("#source-policy");
  if ([...policy.options].some((option) => option.value === mission.source_policy)) policy.value = mission.source_policy;
  setText("#fleet-name", text(fleet.display_name_zh));
  setText("#fleet-en", text(fleet.display_name_en));
  setText("#mission-state", text(status.mission_state));
  setText("#mission-type", text(fleet.mission_type));
  setText("#dispatch-reason", text(fleet.reason));
  setText("#release-gate", text(fleet.release_gate));
  setText("#retry-budget", `${Number.isInteger(status.retry_count) ? status.retry_count : 0} / ${Number.isInteger(status.retry_budget) ? status.retry_budget : 0}`);
  setText("#return-reason", status.return_reason === null ? "无" : text(status.return_reason));
renderBundleMetadata(bundle, activeBundleSource);
  configureEvidenceFilters(asArray(bundle.evidence_cards));
  renderJourney(asArray(bundle.stations));
  renderFacilities(asArray(bundle.facilities));
  renderTimeline(asArray(bundle.timeline));
  renderEvidence(asArray(bundle.evidence_cards));
  renderMatrix(asArray(bundle.condition_matrix));
  renderReport(bundle.mission_report);
}

function updatePreview(event) {
  event.preventDefault();
  const question = document.querySelector("#question").value.trim();
  const material = document.querySelector("#material").value.trim();
  const message = document.querySelector("#form-message");
  if (!question || !material) {
    message.textContent = "请填写研究问题和材料体系；此操作只更新本地预览。";
    return;
  }
  activeBundle = { ...activeBundle, mission: { ...activeBundle.mission, question, material, property_name: document.querySelector("#property").value.trim(), scope: document.querySelector("#scope").value.trim(), source_policy: document.querySelector("#source-policy").value } };
  renderBundle(activeBundle);
  setText("#dispatch-reason", "本地预览已更新；实际分派由 Python 的 mission dispatcher 产生。");
  message.textContent = `已更新 ${material} 的本地预览，未发送任何网络请求。`;
}

function importBundle(event) {
  const file = event.target.files && event.target.files[0];
  const message = document.querySelector("#ui-bundle-message");
  if (!file) return;
  if (file.size > MAX_BUNDLE_BYTES) {
    message.textContent = "拒绝导入：UI JSON 不得超过 1 MiB。";
    return;
  }
  const reader = new FileReader();
  reader.onerror = () => { message.textContent = "无法读取选择的本地文件。"; };
  reader.onload = () => {
    try {
activeBundle = validateBundle(JSON.parse(String(reader.result)));
      activeBundleSource = { name: file.name, bytes: file.size };
      renderBundle(activeBundle);
      message.textContent = `已导入 ${file.name}；页面未发起网络请求。`;
    } catch (error) {
      message.textContent = `拒绝导入：${error instanceof Error ? error.message : "JSON 无效。"}`;
    }
  };
  reader.readAsText(file, "utf-8");
}

document.addEventListener("DOMContentLoaded", () => {
  renderBundle(activeBundle);
  document.querySelector("#mission-form").addEventListener("submit", updatePreview);
document.querySelector("#ui-bundle-file").addEventListener("change", importBundle);
  ["#evidence-stance-filter", "#evidence-condition-filter", "#evidence-query-filter"].forEach((selector) => {
    document.querySelector(selector).addEventListener("input", () => renderEvidence(asArray(activeBundle.evidence_cards)));
    document.querySelector(selector).addEventListener("change", () => renderEvidence(asArray(activeBundle.evidence_cards)));
  });
});