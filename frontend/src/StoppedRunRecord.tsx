import { For, Show, createMemo, createResource, onMount } from "solid-js";
import { DshRunArtifactsHandoff } from "./DshRunHandoff";
import type { UiLocale } from "./fleetRegistry";
import { getApprovedRunArtifacts } from "./localApi";
import { ActionButton, ActionLink } from "./uiPrimitives";

export interface StoppedRunIdentity { runId: string; missionId: string; }

export function StoppedRunRecord(props: { run: StoppedRunIdentity; locale: UiLocale; onClose: () => void }) {
  const x = (zh: string, en: string) => props.locale === "zh" ? zh : en;
  const [artifacts, { refetch }] = createResource(() => getApprovedRunArtifacts(props.run.runId, props.run.missionId));
  const dateFormat = createMemo(() => new Intl.DateTimeFormat(props.locale === "zh" ? "zh-CN" : "en", { dateStyle: "medium", timeStyle: "short" }));
  const rows = () => artifacts.state === "ready" ? artifacts.latest ?? [] : [];
  let heading!: HTMLHeadingElement;
  onMount(() => heading.focus());

  return <section class="stopped-run-record" aria-labelledby="stopped-run-title">
    <header>
      <div>
        <h3 id="stopped-run-title" ref={heading} tabIndex={-1}>{x("已停止的任务记录", "Stopped run record")}</h3>
        <code>{props.run.runId}</code>
      </div>
      <ActionButton size="sm" onClick={props.onClose}>{x("关闭记录", "Close record")}</ActionButton>
    </header>
    <p>{x("可以下载已生成的本机工件。继续研究时请建立新任务。", "Download saved local artifacts here. Start a new run to continue the research.")}</p>
    <Show when={artifacts.loading}><p role="status">{x("正在读取工件目录…", "Loading the artifact list…")}</p></Show>
    <Show when={artifacts.state === "errored"}>
      <p role="status">{x("暂时无法核验工件目录。", "The artifact list could not be verified.")}</p>
      <ActionButton size="sm" onClick={() => void refetch()}>{x("重试读取目录", "Retry artifact list")}</ActionButton>
    </Show>
    <Show when={artifacts.state === "ready" && rows().length === 0}><p role="status">{x("暂无可下载的工件。", "No saved artifacts are available for download.")}</p></Show>
    <Show when={rows().length}>
      <ul class="stopped-run-artifacts">
        <For each={rows()}>{(artifact) => <li>
          <div><strong>{artifact.title}</strong><time dateTime={artifact.generated_at}>{dateFormat().format(new Date(artifact.generated_at))}</time></div>
          <ActionLink href={artifact.download_path} size="sm" aria-label={x(`下载${artifact.title}`, `Download ${artifact.title}`)}>{x("下载", "Download")}</ActionLink>
        </li>}</For>
      </ul>
    </Show>
    <DshRunArtifactsHandoff runId={props.run.runId} locale={props.locale} />
  </section>;
}
