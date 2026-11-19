import { DshCommandText } from "./DshCommandText";
import { Show, createSignal, createUniqueId } from "solid-js";
import { createDshClipboard, DshManualCopy } from "./DshManualCopy";
import type { UiLocale } from "./fleetRegistry";
import { isLocalRunId } from "./liveRunIdentity";
import { ActionButton } from "./uiPrimitives";

export function DshCommandRow(props: { locale: UiLocale; command: string; label: string }) {
  const { copy, feedback: current } = createDshClipboard<"command">(2500);
  const x = (zh: string, en: string) => props.locale === "zh" ? zh : en;
  return <div class="dsh-session-command">
    <div class="harness-copy-row">
      <DshCommandText command={props.command} />
      <div class="dsh-copy-control" classList={{ copied: current()?.copied }}>
        <ActionButton size="sm" aria-label={props.label} onClick={(event) => void copy("command", () => props.command, event.currentTarget)}>
          <span class="dsh-copy-icon" aria-hidden="true">⧉</span>{props.label}
        </ActionButton>
        <Show when={current()?.copied}><span role="status">{x("已复制。", "Copied.")}</span></Show>
      </div>
    </div>
    <Show when={current()?.copied === false && current()}>{(state) => <DshManualCopy locale={props.locale}
      label={x("DSH 命令", "DSH command")} value={state().value} source={state().source} />}</Show>
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
