import { For, Show } from "solid-js";
import type { EvidenceCard } from "./model";
import { uiLanguage } from "./zh";

export function RecordedConditions(props: { values: EvidenceCard["conditions"]; label: string }) {
  const fields = () => Object.entries(props.values);
  return <Show when={fields().length} fallback={<span>{uiLanguage() === "zh" ? "未登记条件" : "No conditions recorded"}</span>}>
    <dl class="reviewed-qualifiers" aria-label={props.label}>
      <For each={fields()}>{([field, value]) =>
        <div><dt>{field}</dt><dd>{value === null || value === "" ? (uiLanguage() === "zh" ? "未提供" : "Not provided") : String(value)}</dd></div>
      }</For>
    </dl>
  </Show>;
}
