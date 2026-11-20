import { DshCommandText } from "./DshCommandText";
import { formatDshCommand } from "./dshTerminalCommand";
import { Show, createSignal, createUniqueId, type Signal } from "solid-js";
import { DshCopyAction } from "./DshManualCopy";
import type { UiLocale } from "./fleetRegistry";
import { isLocalRunId } from "./liveRunIdentity";

export function DshCommandRow(props: { locale: UiLocale; command: string; label: string }) {
  const command = () => formatDshCommand(props.command);
  return <div class="dsh-session-command">
    <DshCopyAction locale={props.locale} value={command()} label={props.label}
      manualLabel={props.locale === "zh" ? "DSH 命令" : "DSH command"} beforeButton={<DshCommandText command={command()} />} />
  </div>;
}

export type DshLaunchMode = "browser" | "link" | "tui";

export function DshSessionLaunch(props: { locale: UiLocale; port: number; runId?: string | null; portInReceipt?: boolean; launchPreference?: Signal<DshLaunchMode> }) {
  const [mode, setMode] = props.launchPreference ?? createSignal<DshLaunchMode>("browser");
  const choiceName = createUniqueId();
  const runId = () => props.runId && isLocalRunId(props.runId) ? props.runId : null;
  const suffix = { browser: "", link: " --no-open", tui: " --surface tui" } as const;
  const command = () => `cosmatter open-dsh-workbench --port ${props.port}${runId() ? ` --run-id ${runId()}` : ""}${suffix[mode()]}`;
  const x = (zh: string, en: string) => props.locale === "zh" ? zh : en;
  return <section class="harness-session-launch" aria-label={x("打开 DSH 会话", "Open a DSH session")}>
    <Show when={!props.portInReceipt || runId()}><p class="dsh-session-target">
      <Show when={!props.portInReceipt}><span>{x(`工作台端口 ${props.port}`, `Workbench port ${props.port}`)}</span></Show>
      <Show when={runId()}>{(id) => <span>{x("当前任务", "Current run")} <code>{id()}</code></span>}</Show>
    </p></Show>
    <fieldset class="dsh-launch-mode" role="radiogroup" aria-label={x("会话打开方式", "How to open DSH")}>
      <legend>{x("会话打开方式", "How to open DSH")}</legend>
      <div>
        <label><input type="radio" name={choiceName} checked={mode() === "browser"} onChange={() => setMode("browser")} />{x("自动打开网页", "Open browser automatically")}</label>
        <label><input type="radio" name={choiceName} checked={mode() === "link"} onChange={() => setMode("link")} />{x("在终端显示链接", "Show link in terminal")}</label>
        <label><input type="radio" name={choiceName} checked={mode() === "tui"} onChange={() => setMode("tui")} />{x("在 Orca / 本机终端运行", "Run in Orca / local terminal")}</label>
      </div>
    </fieldset>
    <p>{mode() === "tui" ? x("在这台电脑的 Orca 工作树终端或本机终端粘贴命令。若 DSH 的 tui 配置缺少交互前端，请选「在终端显示链接」打开网页版。", "Paste the command into an Orca worktree terminal or a local terminal on this computer. If your DSH tui profile lacks an interactive frontend, choose “Show link in terminal” to open DSH Web.")
      : mode() === "link" ? x("在 CosMatter 终端运行命令，再打开终端显示的本机链接。", "Run in the CosMatter terminal, then open the local link it prints.")
      : x("在 CosMatter 终端运行命令，DSH 将在浏览器中打开。", "Run in the CosMatter terminal to open DSH in your browser.")}</p>
    <DshCommandRow locale={props.locale} command={command()} label={x("复制 DSH 启动命令", "Copy DSH launch command")} />
    <Show when={!runId()}><p>{x("创建任务时，告诉 DSH 你的研究问题、材料、目标性质和研究范围，再打开它返回的工作台链接。",
      "To create a run, give DSH your question, material, target property and study scope. Open the workbench link it returns.")}</p></Show>
  </section>;
}
