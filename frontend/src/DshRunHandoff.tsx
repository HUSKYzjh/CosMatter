import { DshCommandText } from "./DshCommandText";
import { Show } from "solid-js";
import { createDshClipboard, DshManualCopy } from "./DshManualCopy";
import { isLocalRunId, localRunArtifactsLink, localRunScreeningLink } from "./liveRunIdentity";
import { localEvidenceLink, localWorkbenchLocation, type DshEvidenceTarget } from "./dshLocalCommands";
import { ActionButton } from "./uiPrimitives";
import type { UiLocale } from "./fleetRegistry";

function DshCommandHandoff(props: { command: string; label: string; locale: UiLocale; description?: string }) {
  const x = (zh: string, en: string) => props.locale === "zh" ? zh : en;
  const { copy, feedback } = createDshClipboard<"command">();

  return <details class="harness-disclosure dsh-run-handoff">
    <summary><span>{props.label}</span></summary>
    <div>
      <Show when={props.description}><p>{props.description}</p></Show>
      <DshCommandText command={props.command} />
      <ActionButton size="sm" onClick={(event) => void copy("command", () => props.command, event.currentTarget)}>{x("复制 DSH 命令", "Copy DSH command")}</ActionButton>
      <Show when={feedback()}>{(state) => <Show when={state().copied} fallback={<DshManualCopy locale={props.locale}
        label={x("DSH 命令", "DSH command")} value={state().value} source={state().source} />}>
        <p role="status">{x("DSH 命令已复制。", "DSH command copied.")}</p>
      </Show>}</Show>
    </div>
  </details>;
}

export function DshRunHandoff(props: { runId: string; locale: UiLocale }) {
  const location = localWorkbenchLocation();
  return <Show when={location && isLocalRunId(props.runId)}>
    <DshCommandHandoff locale={props.locale} command={`cosmatter dsh-run-status ${props.runId} --port ${location?.port || "80"}`}
      label={props.locale === "zh" ? "在 DSH 查看进度" : "Check progress in DSH"}
      description={props.locale === "zh"
        ? "在 CosMatter 的终端环境运行命令，读取当前进度和下一阶段的门禁。"
        : "Run this in the CosMatter terminal environment to read progress and requirements for the next stage."} />
  </Show>;
}

export function DshRecentRunsHandoff(props: { locale: UiLocale }) {
  const location = localWorkbenchLocation();
  if (!location) return null;
  return <DshCommandHandoff locale={props.locale} command={`cosmatter dsh-recent-runs --port ${location.port || "80"}`}
    label={props.locale === "zh" ? "在 DSH 查找最近任务" : "Find recent runs in DSH"}
    description={props.locale === "zh"
      ? "在 CosMatter 的终端环境运行命令，即可获取最近的运行 ID 和本机打开链接。"
      : "Run this in the CosMatter terminal environment to find recent run IDs and local workbench links."} />;
}

export function DshRunArtifactsHandoff(props: { runId: string; locale: UiLocale }) {
  const x = (zh: string, en: string) => props.locale === "zh" ? zh : en;
  const location = localWorkbenchLocation();
  const href = () => location && isLocalRunId(props.runId) ? localRunArtifactsLink(location.origin, props.runId) : null;
  return <Show when={href()} keyed>{(link) =>
    <DshLinkedHandoff locale={props.locale} link={link} linkLabel={x("工件目录链接", "Artifact list link")}
      copyLabel={x("复制工件目录链接", "Copy artifact list link")} copiedLabel={x("工件目录链接已复制。", "Artifact list link copied.")}
      command={`cosmatter dsh-run-artifacts ${props.runId} --port ${location?.port || "80"}`}
      commandLabel={x("查看工件目录命令", "View artifact list command")} />
  }</Show>;
}

export function DshEvidenceHandoff(props: DshEvidenceTarget & { runId: string; locale: UiLocale }) {
  const x = (zh: string, en: string) => props.locale === "zh" ? zh : en;
  return <Show when={localEvidenceLink(props.runId, props)} keyed>{(link) =>
    <DshLinkedHandoff locale={props.locale} link={link} linkLabel={x("证据链接", "Evidence link")}
      copyLabel={x("复制证据链接", "Copy evidence link")} copiedLabel={x("证据链接已复制。", "Evidence link copied.")}
      command={`cosmatter dsh-evidence '${link}'`} commandLabel={x("查看证据命令", "View evidence command")} />
  }</Show>;
}

export function DshScreeningHandoff(props: { runId: string; revision: string; locale: UiLocale }) {
  const x = (zh: string, en: string) => props.locale === "zh" ? zh : en;
  const location = localWorkbenchLocation();
  const href = () => location && isLocalRunId(props.runId) && /^[a-f0-9]{64}$/.test(props.revision)
    ? localRunScreeningLink(location.origin, props.runId, props.revision) : null;
  return <Show when={href()} keyed>{(link) =>
    <DshLinkedHandoff locale={props.locale} link={link} linkLabel={x("筛选清单链接", "Screening checklist link")}
      copyLabel={x("复制筛选链接", "Copy screening link")} copiedLabel={x("筛选链接已复制。", "Screening link copied.")}
      command={`cosmatter dsh-screening '${link}'`} commandLabel={x("查看筛选清单命令", "View screening checklist command")}
      description={x("命令读取本机已保存的清单和决定。未提交的草稿保留在当前浏览器标签页。", "The command reads the saved checklist and decisions. Draft edits stay in this browser tab.")} />
  }</Show>;
}

function DshLinkedHandoff(props: { locale: UiLocale; link: string; linkLabel: string; copyLabel: string; copiedLabel: string; command: string; commandLabel: string; description?: string }) {
  const x = (zh: string, en: string) => props.locale === "zh" ? zh : en;
  const { copy, feedback } = createDshClipboard<"link" | "command">();
  let preview!: HTMLDetailsElement;

  const copyCommand = async (button: HTMLButtonElement) => {
    if (await copy("command", () => props.command, button) === false) preview.open = true;
  };

  return <div class="dsh-linked-handoff">
    <div class="dsh-linked-actions">
      <ActionButton size="sm" onClick={(event) => void copy("link", () => props.link, event.currentTarget)}>{props.copyLabel}</ActionButton>
      <ActionButton size="sm" onClick={(event) => void copyCommand(event.currentTarget)}>{x("复制 DSH 命令", "Copy DSH command")}</ActionButton>
    </div>
    <Show when={feedback()}>{(state) => <Show when={state().copied} fallback={<DshManualCopy locale={props.locale}
      label={state().target === "link" ? props.linkLabel : x("DSH 命令", "DSH command")} value={state().value} source={state().source} />}>
      <p role="status">{state().target === "command" ? x("DSH 命令已复制。", "DSH command copied.") : props.copiedLabel}</p>
    </Show>}</Show>
    <details ref={preview} class="harness-disclosure dsh-run-handoff">
      <summary><span>{props.commandLabel}</span></summary>
      <div>
        <Show when={props.description}><p>{props.description}</p></Show>
        <DshCommandText command={props.command} />
      </div>
    </details>
  </div>;
}
