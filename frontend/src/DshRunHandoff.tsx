import { Show, createSignal } from "solid-js";
import { isLocalRunId } from "./liveRunIdentity";
import { ActionButton } from "./uiPrimitives";
import type { UiLocale } from "./fleetRegistry";

export function DshRunHandoff(props: { runId: string; locale: UiLocale }) {
  const x = (zh: string, en: string) => props.locale === "zh" ? zh : en;
  const [feedback, setFeedback] = createSignal<"copied" | "manual" | null>(null);
  const { protocol, hostname, port } = window.location;
  const command = () => isLocalRunId(props.runId) && protocol === "http:" && (hostname === "127.0.0.1" || hostname === "localhost")
    ? `cosmatter dsh-run-status ${props.runId} --port ${port || "80"}`
    : null;

  async function copyCommand(value: string) {
    try {
      await navigator.clipboard.writeText(value);
      setFeedback("copied");
    } catch {
      setFeedback("manual");
    }
  }

  return <Show when={command()}>{(value) =>
    <details class="harness-disclosure dsh-run-handoff">
      <summary><span>{x("在 DSH 查看进度", "Check progress in DSH")}</span></summary>
      <div>
        <p>{x("在 CosMatter 的终端环境运行命令，读取当前进度和下一阶段的门禁。", "Run this in the CosMatter terminal environment to read progress and requirements for the next stage.")}</p>
        <code>{value()}</code>
        <ActionButton size="sm" onClick={() => void copyCommand(value())}>{x("复制 DSH 命令", "Copy DSH command")}</ActionButton>
        <Show when={feedback()}>{(state) => <p role="status">{state() === "copied"
          ? x("DSH 命令已复制。", "DSH command copied.")
          : x("剪贴板不可用，可选中上方命令复制。", "Clipboard unavailable. Select the command above to copy it.")}</p>}</Show>
      </div>
    </details>
  }</Show>;
}
