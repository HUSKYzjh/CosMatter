"use strict";

const PAPER_SCHEMA_VERSION = "1.0";
const PAPER_MAX_BUNDLE_BYTES = 1024 * 1024;
const paperDemo = {
  schema_version: PAPER_SCHEMA_VERSION,
  research_guide: { items: [{ order: 1, document_id: "synthetic_demo", title: "Synthetic thin-film route", publication_year: 2025, source: "synthetic fixture", locator_hint: "page:1", track: "primary", role: "verified_evidence", content_status: "authorized", evidence_ids: ["evidence_synthetic_001"] }] },
  evidence_cards: [{ evidence_id: "evidence_synthetic_001", claim: "合成示例：应变比较需要记录衬底、厚度和表征条件。", stance: "context", review_status: "accepted", conditions: { sample_form: "film", thickness_nm: 30, method: "synthetic demonstration" }, quote: "Synthetic demonstration only; no paper text is included.", provenance: { document_id: "synthetic_demo", locator: "demo fixture", source: "CosMatter example", access_policy: "local_only" } }],
};

function paperText(value, fallback = "unknown") { return typeof value === "string" && value.trim() ? value.trim() : fallback; }
function paperArray(value) { return Array.isArray(value) ? value : []; }

function validatePaperBundle(candidate) {
  if (!candidate || typeof candidate !== "object" || Array.isArray(candidate)) throw new Error("JSON 根节点必须是对象。");
  if (candidate.schema_version !== PAPER_SCHEMA_VERSION) throw new Error(`仅支持 UI JSON v${PAPER_SCHEMA_VERSION}。`);
  if (!Array.isArray(candidate.evidence_cards)) throw new Error("evidence_cards 必须是数组。");
  if (!candidate.research_guide || typeof candidate.research_guide !== "object" || !Array.isArray(candidate.research_guide.items)) throw new Error("论文导读需要已生成的 research_guide。");
  return candidate;
}

function setGuideOptions(bundle) {
  const select = document.querySelector("#paper-guide-select");
  const current = select.value;
  select.replaceChildren();
  paperArray(bundle.research_guide.items).forEach((item) => { const option = document.createElement("option"); option.value = paperText(item.document_id); option.textContent = `${String(item.order || "?").padStart(2, "0")} · ${paperText(item.title)}`; select.append(option); });
  if ([...select.options].some((option) => option.value === current)) select.value = current;
}

function renderPaper(bundle) {
  const select = document.querySelector("#paper-guide-select");
  const item = paperArray(bundle.research_guide.items).find((candidate) => candidate && candidate.document_id === select.value) || paperArray(bundle.research_guide.items)[0];
  const overview = document.querySelector("#paper-overview"); const provenance = document.querySelector("#paper-provenance"); const evidenceTarget = document.querySelector("#paper-evidence-list");
  if (!item) { overview.replaceChildren(Object.assign(document.createElement("p"), { className: "notice", textContent: "阅读路线中没有候选。" })); provenance.replaceChildren(); evidenceTarget.replaceChildren(); return; }
  const roleLabel = { verified_evidence: "已核验证据", primary_candidate: "主检索候选", counterevidence_candidate: "反例候选" };
  const title = document.createElement("h2"); title.textContent = paperText(item.title);
  const labels = document.createElement("div"); labels.className = "paper-tags";
  [roleLabel[item.role] || "候选", item.track === "counterevidence" ? "反例检索轨道" : "主检索轨道", item.content_status === "authorized" ? "内容访问已授权" : "仅元数据"].forEach((label) => { const tag = document.createElement("span"); tag.textContent = label; labels.append(tag); });
  const metadata = document.createElement("dl"); metadata.className = "inspector-list";
  [["来源", paperText(item.source)], ["发表年份", item.publication_year || "未记录"], ["证据关联", paperArray(item.evidence_ids).join("、") || "尚无"]].forEach(([key, value]) => { const row = document.createElement("div"); const dt = document.createElement("dt"); const dd = document.createElement("dd"); dt.textContent = key; dd.textContent = value; row.append(dt, dd); metadata.append(row); });
  overview.replaceChildren(title, labels, metadata);
  const provenanceList = document.createElement("dl"); provenanceList.className = "inspector-list";
  [["document_id", paperText(item.document_id)], ["候选定位", paperText(item.locator_hint, "未记录")], ["内容状态", item.content_status === "authorized" ? "可进入授权提取流程" : "不可用于证据提取"]].forEach(([key, value]) => { const row = document.createElement("div"); const dt = document.createElement("dt"); const dd = document.createElement("dd"); dt.textContent = key; dd.textContent = value; row.append(dt, dd); provenanceList.append(row); });
  provenance.replaceChildren(provenanceList);
  const cards = paperArray(bundle.evidence_cards).filter((card) => card && card.review_status === "accepted" && card.provenance && card.provenance.document_id === item.document_id);
  if (!cards.length) { evidenceTarget.replaceChildren(Object.assign(document.createElement("p"), { className: "notice", textContent: "此候选尚无可显示的已批准证据。候选不等于科学结论。" })); return; }
  evidenceTarget.replaceChildren(...cards.map((card) => { const article = document.createElement("article"); article.className = "evidence-card"; const claim = document.createElement("p"); claim.className = "claim"; claim.textContent = paperText(card.claim); const quote = document.createElement("p"); quote.className = "quote"; quote.textContent = `短摘录：${paperText(card.quote)}`; const locator = document.createElement("p"); locator.className = "route-meta"; locator.textContent = `定位：${paperText(card.provenance.document_id)} · ${paperText(card.provenance.locator)}`; article.append(claim, quote, locator); return article; }));
}

function loadPaperBundle(event) {
  const file = event.target.files && event.target.files[0]; const message = document.querySelector("#paper-import-message");
  if (!file) return; if (file.size > PAPER_MAX_BUNDLE_BYTES) { message.textContent = "拒绝导入：UI JSON 不得超过 1 MiB。"; return; }
  const reader = new FileReader(); reader.onerror = () => { message.textContent = "无法读取选择的本地文件。"; };
  reader.onload = () => { try { window.paperBundle = validatePaperBundle(JSON.parse(String(reader.result))); setGuideOptions(window.paperBundle); renderPaper(window.paperBundle); message.textContent = `已导入 ${file.name}；仅显示许可工件字段。`; } catch (error) { message.textContent = `拒绝导入：${error instanceof Error ? error.message : "JSON 无效。"}`; } };
  reader.readAsText(file, "utf-8");
}

document.addEventListener("DOMContentLoaded", () => { window.paperBundle = paperDemo; setGuideOptions(paperDemo); renderPaper(paperDemo); document.querySelector("#paper-bundle-file").addEventListener("change", loadPaperBundle); document.querySelector("#paper-guide-select").addEventListener("change", () => renderPaper(window.paperBundle)); });
