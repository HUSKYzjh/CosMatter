import { Show, createEffect, createSignal, createUniqueId, on, onCleanup } from "solid-js";
import type { UiLocale } from "./fleetRegistry";
import { isLocalRunId } from "./liveRunIdentity";
import { ActionButton } from "./uiPrimitives";

export function DshCommandRow(props: { locale: UiLocale; command: string; label: string }) {
  const [feedback, setFeedback] = createSignal<{ command: string; copied: boolean } | null>(null);
  let copyAttempt = 0;
  let reset: ReturnType<typeof setTimeout> | undefined;
  createEffect(on(() => props.command, () => {
    copyAttempt++;
    clearTimeout(reset);
    setFeedback(null);
  }, { defer: true }));
  onCleanup(() => { copyAttempt++; clearTimeout(reset); });
  const current = () => feedback()?.command === props.command ? feedback() : null;
  const x = (zh: string, en: string) => props.locale === "zh" ? zh : en;
  const copy = async () => {
    const attempt = ++copyAttempt;
    const command = props.command;
    clearTimeout(reset);
    let copied = false;
    try {
      await navigator.clipboard.writeText(command);
      copied = true;
    } catch {
      // Keep the selectable command available when the system denies clipboard access.
    }
    if (attempt !== copyAttempt || command !== props.command) return;
    setFeedback({ command, copied });
    if (copied) reset = setTimeout(() => setFeedback(null), 2500);
  };
  return <div class="dsh-session-command">
    <div class="harness-copy-row">
      <code>{props.command}</code>
      <div class="dsh-copy-control" classList={{ copied: current()?.copied }}>
        <ActionButton size="sm" aria-label={props.label} onClick={() => void copy()}>
          <span class="dsh-copy-icon" aria-hidden="true">⧉</span>{props.label}
        </ActionButton>
        <Show when={current()?.copied}><span role="status">{x("已复制。", "Copied.")}</span></Show>
      </div>
    </div>
    <Show when={current()?.copied === false}><p role="status">
      {x("剪贴板不可用，请选中命令手动复制。", "Clipboard unavailable. Select the command and copy it manually.")}
    </p></Show>
  </div>;
}

export function DshSessionLaunch(props: { locale: UiLocale; port: number; runId?: string | null }) {
  const [showLink, setShowLink] = createSignal(false);
  const choiceName = createUniqueId();
  const runId = () => props.runId && isLocalRunId(props.runId) ? props.runId : null;
  const command = () => `cosmatter open-dsh-workbench --port ${props.port}${runId() ? ` --run-id ${runId()}` : ""}${showLink() ? " --no-open" : ""}`;
  const x = (zh: string, en: string) => props.locale === "zh" ? zh : en;
  return <section class="harness-session-launch" aria-label={x("打开 DSH 会话", "Open a DSH session")}>
    <p class="dsh-session-target">
      <span>{x(`工作台端口 ${props.port}`, `Workbench port ${props.port}`)}</span>
      <Show when={runId()}>{(id) => <span>{x("当前任务", "Current run")} <code>{id()}</code></span>}</Show>
    </p>
    <fieldset class="dsh-launch-mode" role="radiogroup" aria-label={x("网页打开方式", "How to open DSH")}>
      <legend>{x("网页打开方式", "How to open DSH")}</legend>
      <div>
        <label><input type="radio" name={choiceName} checked={!showLink()} onChange={() => setShowLink(false)} />{x("自动打开网页", "Open browser automatically")}</label>
        <label><input type="radio" name={choiceName} checked={showLink()} onChange={() => setShowLink(true)} />{x("在终端显示链接", "Show link in terminal")}</label>
      </div>
    </fieldset>
    <p>{showLink() ? x("在 CosMatter 终端运行命令，再打开终端显示的本机链接。", "Run in the CosMatter terminal, then open the local link it prints.")
      : x("在 CosMatter 终端运行命令，DSH 将在浏览器中打开。", "Run in the CosMatter terminal to open DSH in your browser.")}</p>
    <DshCommandRow locale={props.locale} command={command()} label={x("复制 DSH 启动命令", "Copy DSH launch command")} />
  </section>;
}
