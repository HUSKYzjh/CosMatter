import { Show } from "solid-js";
import { DshCommandRow } from "./DshSessionLaunch";
import type { DshSessionReadiness } from "./dshSessionReadiness";
import type { UiLocale } from "./fleetRegistry";
import { isLocalRunId } from "./liveRunIdentity";
import { updatedWorkbenchCommand } from "./dshLocalCommands";

export function WorkbenchUpdateCommand(props: { locale: UiLocale; runId?: string | null }) {
  const x = (zh: string, en: string) => props.locale === "zh" ? zh : en;
  const run = () => props.runId && isLocalRunId(props.runId) ? props.runId : null;
  return <section class="dsh-workbench-update" aria-label={x("启动新版工作台", "Start the updated workbench")}>
    <p>{x("新开终端，进入安装了新版 CosMatter 的环境，再运行下方命令。",
      "Open a new terminal in the environment where the updated CosMatter CLI is installed and run the command below.")}{" "}
      {run() ? x("打开终端打印的地址，即可继续当前任务。", "Open the printed URL to continue this run.")
        : x("打开终端打印的地址，端口由系统分配。", "Open the printed URL on the newly allocated port.")}</p>
    <DshCommandRow locale={props.locale} command={updatedWorkbenchCommand(run())} label={x("复制新版工作台命令", "Copy workbench command")} />
  </section>;
}

export function OtherPortReceiptHelp(props: {
  locale: UiLocale; runId?: string | null; readiness: DshSessionReadiness;
  port: number | null; receiptPort?: number;
}) {
  const otherPort = () => props.readiness === "loopback-check" && props.port && props.receiptPort !== props.port && props.receiptPort;
  return <Show when={otherPort()}>{(previous) =>
    <details class="harness-disclosure dsh-port-help">
      <summary>{props.locale === "zh" ? "为什么显示其它端口的回执？" : "Why is the receipt for another port?"}</summary>
      <p>{props.locale === "zh"
        ? `工作台在端口 ${props.port}，收到的回执来自端口 ${previous()}。请先核验当前端口。如果切换工作台后回执端口反复变化，可在新版工作台继续。`
        : `This workbench is on port ${props.port}. The receipt is for port ${previous()}. Check the current port first. If the receipt keeps changing as you switch workbenches, you can continue in an updated workbench.`}</p>
      <WorkbenchUpdateCommand locale={props.locale} runId={props.runId} />
    </details>
  }</Show>;
}
