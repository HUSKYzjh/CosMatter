import { For, Show, createSignal } from "solid-js";

import type { HumanMaterialFactInput, RecordedSourceMapSegment } from "./localApi";
import { validateMaterialFactDraft } from "./materialFactDraft";
import { materialFactScalar } from "./materialFactValue";
import { uiLanguage } from "./zh";
import { safeOperationFeedback } from "./importFeedback";

const tr = (zhText: string, enText: string) => uiLanguage() === "zh" ? zhText : enText;
const categories = ["composition", "structure", "property", "processing", "experimental_condition", "simulation_method"] as const;
const categoryLabel = (category: typeof categories[number]) => ({
  composition: tr("成分", "Composition"), structure: tr("结构", "Structure"), property: tr("性能", "Property"),
  processing: tr("工艺", "Processing"), experimental_condition: tr("实验条件", "Experimental condition"), simulation_method: tr("模拟方法", "Simulation method"),
}[category]);

type DraftFact = Omit<HumanMaterialFactInput, "value" | "unit" | "normalized_value" | "normalized_unit" | "qualifiers"> & {
  value: string; unit: string; normalized_value: string; normalized_unit: string; qualifiers_json: string;
};
const emptyFact = (segmentId = "", ordinal = 1): DraftFact => ({ fact_id: `fact_${String(ordinal).padStart(2, "0")}`, segment_id: segmentId, category: "property", name: "", value: "", unit: "", normalized_value: "", normalized_unit: "", qualifiers_json: "{}" });

export function PrivateMaterialFactReview(props: {
  segments: RecordedSourceMapSegment[];
  onRecord?: (facts: HumanMaterialFactInput[]) => Promise<void>;
}) {
  const [facts, setFacts] = createSignal<DraftFact[]>([emptyFact(props.segments[0]?.segment_id, 1)]);
  const [confirmed, setConfirmed] = createSignal(false);
  const [busy, setBusy] = createSignal(false);
  const [message, setMessage] = createSignal<string | null>(null);
  const toPreflight = (items: DraftFact[], confirmedValue = confirmed(), hasHandler = Boolean(props.onRecord)) => validateMaterialFactDraft({
    facts: items.map((fact) => ({ factId: fact.fact_id, segmentId: fact.segment_id, category: fact.category, name: fact.name, value: fact.value, unit: fact.unit, normalizedValue: fact.normalized_value, normalizedUnit: fact.normalized_unit, qualifiersJson: fact.qualifiers_json })),
    segmentIds: props.segments.map((segment) => segment.segment_id), confirmed: confirmedValue, hasRecordHandler: hasHandler,
  });
  const qualifiersAreValid = (value: string) => {
    const check = toPreflight([{ ...emptyFact(props.segments[0]?.segment_id), qualifiers_json: value, fact_id: "probe", name: "probe" }], true, true);
    return check.issue !== "qualifiers-json" && check.issue !== "qualifiers";
  };
  const factReady = (fact: DraftFact) => toPreflight([fact], true, true).ready;
  const completeFactCount = () => facts().filter(factReady).length;
  const qualifierReadyCount = () => facts().filter((fact) => qualifiersAreValid(fact.qualifiers_json)).length;
  const boundSegmentCount = () => new Set(facts().map((fact) => fact.segment_id).filter(Boolean)).size;
  const categoryCount = () => new Set(facts().filter((fact) => fact.name.trim()).map((fact) => fact.category)).size;
  const factVector = () => [
    { id: "source", label: tr("来源片段", "SOURCE SEGMENTS"), value: `${boundSegmentCount()}/${props.segments.length}`, ready: boundSegmentCount() > 0, detail: tr("每条事实必须绑定已审核片段", "every fact must bind a reviewed segment") },
    { id: "draft", label: tr("事实草稿", "FACT DRAFTS"), value: `${completeFactCount()}/${facts().length}`, ready: completeFactCount() === facts().length, detail: tr("需要 ID、片段、字段名称与限定条件", "requires ID, segment, field name, and qualifiers") },
    { id: "qualifiers", label: tr("条件 JSON", "QUALIFIER JSON"), value: `${qualifierReadyCount()}/${facts().length}`, ready: qualifierReadyCount() === facts().length, detail: tr(`${categoryCount()} 个已填写类别`, `${categoryCount()} populated category type(s)`) },
    { id: "confirm", label: tr("人工确认", "HUMAN CONFIRMATION"), value: confirmed() ? tr("已确认", "confirmed") : tr("待确认", "pending"), ready: confirmed(), detail: tr("不从空白字段推断事实", "facts are never inferred from blanks") },
  ];
  const update = (index: number, field: keyof DraftFact, value: string) => setFacts((current) => current.map((fact, itemIndex) => itemIndex === index ? { ...fact, [field]: value } : fact));
  const preflight = () => toPreflight(facts());
  const valid = () => preflight().ready;
  const submit = async () => {
    if (busy() || !valid() || !props.onRecord) return;
    setBusy(true); setMessage(null);
    try {
      const reviewed = facts().map((fact) => {
        let qualifiers: Record<string, string | number | null>;
        try { qualifiers = JSON.parse(fact.qualifiers_json) as Record<string, string | number | null>; } catch { throw new Error(tr("限定条件必须是 JSON 对象。", "Qualifiers must be a JSON object.")); }
        if (!qualifiers || Array.isArray(qualifiers) || typeof qualifiers !== "object") throw new Error(tr("限定条件必须是 JSON 对象。", "Qualifiers must be a JSON object."));
        return { fact_id: fact.fact_id.trim(), segment_id: fact.segment_id, category: fact.category, name: fact.name.trim(), value: materialFactScalar(fact.value), unit: fact.unit.trim() || null, normalized_value: materialFactScalar(fact.normalized_value), normalized_unit: fact.normalized_unit.trim() || null, qualifiers };
      });
      await props.onRecord(reviewed);
      setMessage(tr("已登记结构化材料事实。它们是经人工复核的来源观察，不是 EvidenceCard，也不是科学结论。", "Structured material facts recorded. They are human-reviewed source observations, not EvidenceCards or scientific conclusions."));
    } catch (error) { setMessage(safeOperationFeedback(error, tr("无法登记材料事实；请检查来源定位和人工确认。", "Unable to record material facts. Check the source locator and human confirmation."))); }
    finally { setBusy(false); }
  };
  return <Show when={props.segments.length}><section class="private-material-fact-review">
    <header><div><small>{tr("人工材料事实 / HUMAN MATERIAL FACTS", "HUMAN MATERIAL FACTS")}</small><h2>{tr("登记与来源片段绑定的结构化事实", "Register structured facts bound to reviewed excerpts")}</h2><p>{tr("此表单只写入本地运行工件；每条事实必须选择已核对的 Source Map 片段。请保留不确定性和条件，不从空白处推断。", "This form writes only to the local run artifact. Each fact must select a reviewed Source Map excerpt; retain uncertainty and conditions rather than inferring beyond the text.")}</p></div></header>
    <section class="material-fact-vector" aria-label={tr("材料事实账本状态", "Material fact ledger status")}><header><small>{tr("事实账本 / 人工限定", "FACT LEDGER / HUMAN QUALIFIERS")}</small><span>{valid() ? tr("草稿预检已通过；纯数值会以数值提交，由本地服务复核单位换算。", "Draft preflight is ready; standalone numeric entries are sent as numbers and unit conversion is revalidated locally.") : tr("每条事实须绑定已审核片段；ID 不可重复，限定条件只能是简短标量 JSON。", "Every fact must bind a reviewed segment; IDs must be unique and qualifiers must be short scalar JSON.")}</span></header><div class="material-fact-track" role="list"><For each={factVector()}>{(station, index) => <div role="listitem" class={`material-fact-station ${station.ready ? "ready" : "pending"}`}><span>{String(index() + 1).padStart(2, "0")}</span><i aria-hidden="true" /><small>{station.label}</small><strong>{station.value}</strong><em>{station.detail}</em></div>}</For></div></section>
    <For each={facts()}>{(fact, index) => <fieldset class={`material-fact-item ${factReady(fact) ? "ready" : "pending"}`}><legend>{tr(`事实 ${String(index() + 1).padStart(2, "0")} · ${categoryLabel(fact.category)}`, `FACT ${String(index() + 1).padStart(2, "0")} · ${categoryLabel(fact.category)}`)}</legend><label>{tr("事实 ID", "Fact ID")}<input value={fact.fact_id} onInput={(event) => update(index(), "fact_id", event.currentTarget.value)} placeholder={`fact_${index() + 1}`} /></label><label>{tr("来源片段", "Source segment")}<select value={fact.segment_id} onChange={(event) => update(index(), "segment_id", event.currentTarget.value)}><For each={props.segments}>{(segment) => <option value={segment.segment_id}>{segment.segment_id} · {segment.locator}</option>}</For></select></label><label>{tr("类别", "Category")}<select value={fact.category} onChange={(event) => update(index(), "category", event.currentTarget.value)}><For each={categories}>{(category) => <option value={category}>{categoryLabel(category)}</option>}</For></select></label><label>{tr("字段名称", "Field name")}<input value={fact.name} onInput={(event) => update(index(), "name", event.currentTarget.value)} placeholder={tr("如：居里温度", "e.g. Curie temperature")} /></label><label>{tr("原始值", "Reported value")}<input value={fact.value} onInput={(event) => update(index(), "value", event.currentTarget.value)} /></label><label>{tr("原始单位", "Reported unit")}<input value={fact.unit} onInput={(event) => update(index(), "unit", event.currentTarget.value)} placeholder={tr("可留空", "optional")} /></label><label>{tr("规范化值", "Normalized value")}<input value={fact.normalized_value} onInput={(event) => update(index(), "normalized_value", event.currentTarget.value)} /></label><label>{tr("规范化单位", "Normalized unit")}<input value={fact.normalized_unit} onInput={(event) => update(index(), "normalized_unit", event.currentTarget.value)} placeholder={tr("可留空", "optional")} /></label><label class="material-fact-qualifiers">{tr("限定条件（JSON）", "Qualifiers (JSON)")}<input value={fact.qualifiers_json} onInput={(event) => update(index(), "qualifiers_json", event.currentTarget.value)} /></label><Show when={facts().length > 1}><button type="button" class="quiet-action" onClick={() => setFacts((current) => current.filter((_, itemIndex) => itemIndex !== index()))}>{tr("移除此事实", "Remove fact")}</button></Show></fieldset>}</For>
    <Show when={preflight().issue === "conversion"}><p class="source-map-message" role="status" aria-live="polite">{tr("已知数值单位的规范化值与原始值不一致。请人工修正；未知单位或文本量不会由浏览器猜测或换算，本机服务仍会再次复核。", "The normalized value is inconsistent with the reported value for known numeric units. Correct it manually; the browser never guesses unknown units or textual quantities, and the local service revalidates on submission.")}</p></Show>
    <div class="source-map-controls"><button type="button" class="quiet-action" disabled={facts().length >= 48} onClick={() => setFacts((current) => [...current, emptyFact(props.segments[0]?.segment_id, current.length + 1)])}>{tr("添加事实", "Add fact")}</button><label class="source-map-confirm"><input type="checkbox" checked={confirmed()} onChange={(event) => setConfirmed(event.currentTarget.checked)} />{tr("我已人工核对每一事实均由所选来源片段支持，并同意将其登记为本地、非结论性的结构化材料事实。", "I verified each fact against its selected source excerpt and consent to recording it locally as a non-conclusive structured material fact.")}</label><button type="button" class="primary-action" disabled={!valid() || busy()} onClick={() => void submit()}>{busy() ? tr("登记中…", "Recording…") : tr("登记人工材料事实", "Record human material facts")}</button></div>
    <Show when={message()}>{(value) => <p class="source-map-message">{value()}</p>}</Show>
  </section></Show>;
}

