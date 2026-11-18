import { Show, createSignal } from "solid-js";
import { isLocalRunId, localRunLink, parseLocalRunLink } from "./liveRunIdentity";
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

export function DshEvidenceHandoff(props: { runId: string; documentId: string; evidenceId: string; locale: UiLocale }) {
  const x = (zh: string, en: string) => props.locale === "zh" ? zh : en;
  const href = () => {
    const { protocol, hostname, origin } = window.location;
    if (protocol !== "http:" || !["127.0.0.1", "localhost"].includes(hostname)) return null;
    const value = localRunLink(origin, props.runId, props.documentId, props.evidenceId);
    return parseLocalRunLink(new URL(value).hash)?.evidenceId === props.evidenceId ? value : null;
  };
  return <Show when={href()} keyed>{(evidenceLink) => {
    const [feedback, setFeedback] = createSignal<{ item: "link" | "command"; copied: boolean } | null>(null);
    const command = `cosmatter dsh-evidence '${evidenceLink}'`;

    async function copy(item: "link" | "command") {
      try {
        await navigator.clipboard.writeText(item === "link" ? evidenceLink : command);
        setFeedback({ item, copied: true });
      } catch {
        setFeedback({ item, copied: false });
      }
    }

    return <div class="dsh-evidence-handoff">
      <ActionButton size="sm" onClick={() => void copy("link")}>{x("复制证据链接", "Copy evidence link")}</ActionButton>
      <Show when={feedback()?.item === "link"}><>
        <p role="status">{feedback()?.copied ? x("证据链接已复制。", "Evidence link copied.") : x("剪贴板不可用，可选中链接复制。", "Clipboard unavailable. Select the link to copy it.")}</p>
        <Show when={!feedback()?.copied}><input aria-label={x("证据链接", "Evidence link")} readOnly value={evidenceLink} onFocus={(event) => event.currentTarget.select()} /></Show>
      </></Show>
      <details class="harness-disclosure dsh-run-handoff">
        <summary><span>{x("在 DSH 查看证据", "View evidence in DSH")}</span></summary>
        <div>
          <code>{command}</code>
          <ActionButton size="sm" onClick={() => void copy("command")}>{x("复制 DSH 命令", "Copy DSH command")}</ActionButton>
          <Show when={feedback()?.item === "command"}><p role="status">{feedback()?.copied
            ? x("DSH 命令已复制。", "DSH command copied.")
            : x("剪贴板不可用，可选中上方命令复制。", "Clipboard unavailable. Select the command above to copy it.")}</p></Show>
        </div>
      </details>
    </div>;
  }}</Show>;
}
