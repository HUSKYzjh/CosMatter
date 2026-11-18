import { Show, onMount } from "solid-js";
import type { UiLocale } from "./fleetRegistry";
import { SavedRunArtifacts } from "./SavedRunArtifacts";
import { ActionButton } from "./uiPrimitives";

export interface RunArtifactIdentity { runId: string; missionId: string; stopped: boolean; }

export function RunArtifactRecord(props: { run: RunArtifactIdentity; locale: UiLocale; onOpenRun?: () => void; onClose: () => void }) {
  const x = (zh: string, en: string) => props.locale === "zh" ? zh : en;
  let heading!: HTMLHeadingElement;
  onMount(() => heading.focus());

  return <section class="run-artifact-record" aria-labelledby="run-artifact-record-title">
    <header>
      <div>
        <h3 id="run-artifact-record-title" ref={heading} tabIndex={-1}>{props.run.stopped
          ? x("已停止的任务记录", "Stopped run record") : x("已保存工件", "Saved artifacts")}</h3>
        <code>{props.run.runId}</code>
      </div>
      <ActionButton size="sm" onClick={props.onClose}>{x("关闭记录", "Close record")}</ActionButton>
    </header>
    <Show when={props.run.stopped}>
      <p>{x("可以下载已生成的本机工件。继续研究时请建立新任务。", "Download saved local artifacts here. Start a new run to continue the research.")}</p>
    </Show>
    <SavedRunArtifacts runId={props.run.runId} missionId={props.run.missionId} locale={props.locale} />
    <Show when={!props.run.stopped && props.onOpenRun}>
      <ActionButton size="sm" onClick={() => props.onOpenRun?.()}>{x("打开任务", "Open run")}</ActionButton>
    </Show>
  </section>;
}
