import { DshCommandText } from "./DshCommandText";
import { formatDshCommand } from "./dshTerminalCommand";
import { Show, createSignal, createUniqueId, type Signal } from "solid-js";
import { DshCopyAction } from "./DshManualCopy";
import type { UiLocale } from "./fleetRegistry";
import { isLocalRunId } from "./liveRunIdentity";
import { continuationStageLabel } from "./continuationStage";
import type { WorkflowStageName } from "./localApi";

export function DshCommandRow(props: { locale: UiLocale; command: string; label: string }) {
  const command = () => formatDshCommand(props.command);
  return <div class="dsh-session-command">
    <DshCopyAction locale={props.locale} value={command()} label={props.label}
      manualLabel={props.locale === "zh" ? "DSH 命令" : "DSH command"} beforeButton={<DshCommandText command={command()} />} />
  </div>;
}

export type DshLaunchMode = "browser" | "link" | "tui";

export function DshSessionLaunch(props: { locale: UiLocale; port: number; runId?: string | null; currentStage?: WorkflowStageName | null; portInReceipt?: boolean; launchPreference?: Signal<DshLaunchMode> }) {
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
      <Show when={runId() && props.currentStage}>{stage => <span>{x("已核验阶段", "Verified stage")} · {continuationStageLabel(stage(), props.locale)}</span>}</Show>
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
    <Show when={runId()} keyed fallback={<p>{x("创建任务时，告诉 DSH 你的研究问题、材料、目标性质和研究范围，再打开它返回的工作台链接。",
      "To create a run, give DSH your question, material, target property and study scope. Open the workbench link it returns.")}</p>}>
      {id => {
        const query = () => x(
          `以 {} 调用 cosmatter_workflow_status，核对返回的 run_id 是否为 ${id}。匹配后，用该 run_id 调用 cosmatter_artifact_manifest，核对 workbench_url 的端口是否为 ${props.port}。两项均匹配时，以 {} 调用 cosmatter_stage_contract，告诉我下一步、需要人工确认的事项，并附上已核对的工件链接。核对失败时，报告实际返回值并停止。`,
          `Call cosmatter_workflow_status with {} and check that run_id is ${id}. If it matches, call cosmatter_artifact_manifest with that run_id and check that the port in workbench_url is ${props.port}. If both match, call cosmatter_stage_contract with {}. Show the next step, any required human review, and the verified artifact link. If a check fails, report the returned value and stop.`,
        );
        return <details class="harness-disclosure dsh-run-query">
          <summary><span>{x("在 DSH 聊天中查询下一步", "Check the next step in DSH chat")}</span></summary>
          <div>
            <p>{query()}</p>
            <DshCopyAction locale={props.locale} value={query()} label={x("复制只读查询", "Copy read-only query")}
              manualLabel={x("DSH 只读查询", "DSH read-only query")} successLabel={x("已复制，可粘贴到当前 DSH 聊天。", "Copied. Paste into the current DSH chat.")} />
          </div>
        </details>;
      }}
    </Show>
  </section>;
}
