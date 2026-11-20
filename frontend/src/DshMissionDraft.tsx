import { For, Show, createMemo, createUniqueId } from "solid-js";
import { DshCopyAction } from "./DshManualCopy";
import { prepareDshMissionHandoff } from "./dshMissionHandoff";
import type { UiLocale } from "./fleetRegistry";
import type { LaunchMissionBoundary, LaunchMissionField } from "./launchMissionValidation";
import { ActionButton } from "./uiPrimitives";

export function DshMissionDraft(props: { locale: UiLocale; draft: LaunchMissionBoundary; onEditField?: (field: LaunchMissionField) => void }) {
  const handoff = createMemo(() => prepareDshMissionHandoff(props.draft, props.locale));
  const message = () => handoff()?.message ?? null;
  const label = () => props.locale === "zh" ? "DSH 聊天草稿" : "DSH chat draft";
  return <Show when={handoff()}>{(current) => <section class="dsh-mission-draft" aria-label={label()}>
    <p>{current().hint}</p>
    <For each={current().overLimit}>{issue => {
      const countId = createUniqueId();
      return <div class="harness-copy-row">
        <p id={countId}>{issue.label} · {props.locale === "zh"
          ? `已用 ${issue.length}，上限 ${issue.limit}`
          : `${issue.length} used, maximum ${issue.limit}`}</p>
        <Show when={props.onEditField}><ActionButton size="sm" variant="quiet" aria-describedby={countId}
          onClick={() => props.onEditField?.(issue.field)}>
          {props.locale === "zh" ? `返回修改${issue.label}` : `Edit ${issue.label}`}
        </ActionButton></Show>
      </div>;
    }}</For>
    <DshCopyAction locale={props.locale} value={message()} manualLabel={label()}
      label={props.locale === "zh" ? "复制到 DSH 聊天" : "Copy to DSH chat"}
      successLabel={props.locale === "zh" ? "聊天草稿已复制。" : "Chat draft copied."}>
      <Show when={message()}>{(value) => <details class="harness-disclosure dsh-draft-preview">
        <summary>{props.locale === "zh" ? "预览聊天草稿" : "Preview chat draft"}</summary>
        <pre>{value()}</pre>
      </details>}</Show>
    </DshCopyAction>
  </section>}</Show>;
}
