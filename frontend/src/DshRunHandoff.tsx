import { Show, createSignal } from "solid-js";
import { isLocalRunId } from "./liveRunIdentity";
import { localEvidenceLink, localWorkbenchLocation, type DshEvidenceTarget } from "./dshLocalCommands";
import { ActionButton } from "./uiPrimitives";
import type { UiLocale } from "./fleetRegistry";

function DshCommandHandoff(props: { command: string; label: string; locale: UiLocale; description?: string }) {
  const x = (zh: string, en: string) => props.locale === "zh" ? zh : en;
  const [feedback, setFeedback] = createSignal<"copied" | "manual" | null>(null);

  async function copyCommand() {
    try {
      await navigator.clipboard.writeText(props.command);
      setFeedback("copied");
    } catch {
      setFeedback("manual");
    }
  }

  return <details class="harness-disclosure dsh-run-handoff">
    <summary><span>{props.label}</span></summary>
    <div>
      <Show when={props.description}><p>{props.description}</p></Show>
      <code>{props.command}</code>
      <ActionButton size="sm" onClick={() => void copyCommand()}>{x("复制 DSH 命令", "Copy DSH command")}</ActionButton>
      <Show when={feedback()}>{(state) => <p role="status">{state() === "copied"
        ? x("DSH 命令已复制。", "DSH command copied.")
        : x("剪贴板不可用，可选中上方命令复制。", "Clipboard unavailable. Select the command above to copy it.")}</p>}</Show>
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
  const location = localWorkbenchLocation();
  if (!location || !isLocalRunId(props.runId)) return null;
  return <DshCommandHandoff locale={props.locale} command={`cosmatter dsh-run-artifacts ${props.runId} --port ${location.port || "80"}`}
    label={props.locale === "zh" ? "在 DSH 查看工件目录" : "View artifact list in DSH"} />;
}

export function DshEvidenceHandoff(props: DshEvidenceTarget & { runId: string; locale: UiLocale }) {
  const x = (zh: string, en: string) => props.locale === "zh" ? zh : en;
  const href = () => localEvidenceLink(props.runId, props);
  return <Show when={href()} keyed>{(evidenceLink) => {
    const [feedback, setFeedback] = createSignal<"copied" | "manual" | null>(null);
    const command = `cosmatter dsh-evidence '${evidenceLink}'`;

    async function copyLink() {
      try {
        await navigator.clipboard.writeText(evidenceLink);
        setFeedback("copied");
      } catch {
        setFeedback("manual");
      }
    }

    return <div class="dsh-evidence-handoff">
      <ActionButton size="sm" onClick={() => void copyLink()}>{x("复制证据链接", "Copy evidence link")}</ActionButton>
      <Show when={feedback()}>{(state) => <>
        <p role="status">{state() === "copied" ? x("证据链接已复制。", "Evidence link copied.") : x("剪贴板不可用，可选中链接复制。", "Clipboard unavailable. Select the link to copy it.")}</p>
        <Show when={state() === "manual"}><input aria-label={x("证据链接", "Evidence link")} readOnly value={evidenceLink} onFocus={(event) => event.currentTarget.select()} /></Show>
      </>}</Show>
      <DshCommandHandoff locale={props.locale} command={command} label={x("在 DSH 查看证据", "View evidence in DSH")} />
    </div>;
  }}</Show>;
}
