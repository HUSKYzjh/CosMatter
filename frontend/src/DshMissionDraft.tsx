import { Show, createMemo } from "solid-js";
import { createDshClipboard, DshManualCopy } from "./DshManualCopy";
import { prepareDshMissionHandoff } from "./dshMissionHandoff";
import type { UiLocale } from "./fleetRegistry";
import type { LaunchMissionBoundary } from "./launchMissionValidation";
import { ActionButton } from "./uiPrimitives";

export function DshMissionDraft(props: { locale: UiLocale; draft: LaunchMissionBoundary }) {
  const handoff = createMemo(() => prepareDshMissionHandoff(props.draft, props.locale));
  const message = () => handoff()?.message ?? null;
  const { copy, feedback } = createDshClipboard<"draft">(2500);
  const label = () => props.locale === "zh" ? "DSH 聊天草稿" : "DSH chat draft";
  return <Show when={handoff()}>{(current) => <section class="dsh-mission-draft" aria-label={label()}>
    <p>{current().hint}</p>
    <ActionButton size="sm" disabled={!message()} onClick={(event) => void copy("draft", message, event.currentTarget)}>
      {props.locale === "zh" ? "复制到 DSH 聊天" : "Copy to DSH chat"}
    </ActionButton>
    <Show when={message()}>{(value) => <details class="harness-disclosure dsh-draft-preview">
      <summary>{props.locale === "zh" ? "预览聊天草稿" : "Preview chat draft"}</summary>
      <pre>{value()}</pre>
    </details>}</Show>
    <Show when={feedback()}>{(state) => <Show when={state().copied} fallback={<DshManualCopy locale={props.locale}
      label={label()} value={state().value} source={state().source} />}>
      <p role="status">{props.locale === "zh" ? "聊天草稿已复制。" : "Chat draft copied."}</p>
    </Show>}</Show>
  </section>}</Show>;
}
