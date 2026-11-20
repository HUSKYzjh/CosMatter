import { For, Show } from "solid-js";
import type { MaterialFact, MaterialFactLedger } from "./model";
import type { RecordedMarkdownLocation } from "./localApi";
import { ActionButton } from "./uiPrimitives";
import { RecordedConditions } from "./RecordedConditions";
import { uiLanguage } from "./zh";

const tr = (zh: string, en: string) => uiLanguage() === "zh" ? zh : en;

export function ReviewedMaterialFacts(props: {
  ledger: MaterialFactLedger;
  sourcePanelId: string;
  locationFor: (fact: MaterialFact) => RecordedMarkdownLocation | null;
  onOpenSource: (fact: MaterialFact, origin: HTMLButtonElement) => void;
}) {
  return <section class="reviewed-fact-ledger" aria-label={tr("本篇材料事实", "Material facts for this paper")}>
    <header>
      <h2>{tr(`本篇材料事实（${props.ledger.facts.length}）`, `Material facts for this paper (${props.ledger.facts.length})`)}</h2>
      <span>{props.ledger.trustStatus === "human_reviewed_structured_material_facts_not_scientific_conclusion"
        ? tr("人工复核的来源观察", "Human-reviewed source observations") : props.ledger.trustStatus}</span>
    </header>
    <ul class="reviewed-facts">
      <For each={props.ledger.facts}>{fact => <li>
        <h3>{fact.name}</h3>
        <p class="reviewed-value">
          <Show when={fact.value !== null} fallback={tr("未提供数值", "Value not provided")}>
            {fact.value} <span>{fact.unit}</span>
          </Show>
        </p>
        <Show when={fact.value === null && fact.unit}><p>{tr("已登记单位", "Recorded unit")} {fact.unit}</p></Show>
        <Show when={fact.normalizedValue !== null && (fact.value !== fact.normalizedValue || fact.unit !== fact.normalizedUnit)}>
          <p>{tr("已登记的规范值", "Recorded normalized value")} {fact.normalizedValue} {fact.normalizedUnit}</p>
        </Show>
        <RecordedConditions values={fact.qualifiers} label={tr("限定条件", "Qualifiers")} />
        <footer>
          <p>{fact.category} · {fact.factId}</p>
          <p>{fact.locator} · {fact.segmentId}</p>
          <Show when={props.locationFor(fact)}>
            <ActionButton size="sm" variant="secondary" aria-controls={props.sourcePanelId}
              aria-label={tr(`查看来源 ${fact.name} · ${fact.factId}`, `View source for ${fact.name} · ${fact.factId}`)}
              onClick={event => props.onOpenSource(fact, event.currentTarget)}>{tr("查看来源", "View source")}</ActionButton>
          </Show>
        </footer>
      </li>}</For>
    </ul>
  </section>;
}
