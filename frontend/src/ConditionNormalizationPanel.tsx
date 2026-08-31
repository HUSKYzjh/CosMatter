import { For, Show, createMemo } from "solid-js";

import type { ConditionNormalization, EvidenceCard } from "./model";

const copy = (locale: "zh" | "en", zh: string, en: string) => locale === "zh" ? zh : en;

export function ConditionNormalizationPanel(props: { normalization: ConditionNormalization; locale: "zh" | "en"; evidenceCards: EvidenceCard[]; onFocusEvidence?: (evidence: EvidenceCard) => void }) {
  const canonicalCount = createMemo(() => new Set(props.normalization.mappings.map((mapping) => mapping.canonicalField)).size);
  const evidenceById = createMemo(() => new Map(props.evidenceCards.map((card) => [card.evidenceId, card])));
  return <section class="condition-normalization-panel" aria-label={copy(props.locale, "人工条件字段规范化", "Human condition-field normalization")}>
    <header><div><small>{copy(props.locale, "条件字段规范化 / 只读", "CONDITION-FIELD NORMALIZATION / READ ONLY")}</small><h2>{copy(props.locale, "统一字段名，不换算数值", "Normalize field names; do not convert values")}</h2></div><span>{props.normalization.trustStatus}</span></header>
    <p>{copy(props.locale, "此清单只保留人工审核的原始字段名、规范字段名和申明单位。它不展示数值，不执行单位换算，也不使跨文献条件自动可比。", "This ledger retains only human-reviewed raw field names, canonical field names, and declared units. It exposes no values, performs no unit conversion, and never makes conditions automatically comparable across papers.")}</p>
    <dl><div><dt>{copy(props.locale, "人工映射", "reviewed mappings")}</dt><dd>{props.normalization.mappings.length}</dd></div><div><dt>{copy(props.locale, "规范字段", "canonical fields")}</dt><dd>{canonicalCount()}</dd></div></dl>
    <Show when={props.normalization.mappings.length} fallback={<p class="condition-normalization-empty">{copy(props.locale, "当前没有人工字段映射；这不表示字段不存在，也不允许系统以名称相似性合并条件。", "There are no human field mappings yet. This neither proves a field is absent nor permits the system to merge conditions by name similarity.")}</p>}>
      <ol><For each={props.normalization.mappings}>{(mapping, index) => {
        const evidence = () => evidenceById().get(mapping.evidenceId);
        return <li><small>{String(index() + 1).padStart(2, "0")} / {mapping.evidenceId}</small><code>{mapping.rawField}</code><i aria-hidden="true">→</i><strong>{mapping.canonicalField}</strong><em>{mapping.unit}</em><Show when={evidence() && props.onFocusEvidence}><button type="button" onClick={() => props.onFocusEvidence?.(evidence()!)}>{copy(props.locale, "定位 EvidenceCard", "focus EvidenceCard")}</button></Show></li>;
      }}</For></ol>
    </Show>
  </section>;
}
