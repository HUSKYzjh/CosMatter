import { For, Show, createMemo, createResource, createSignal } from "solid-js";
import { DshRunArtifactsHandoff } from "./DshRunHandoff";
import type { UiLocale } from "./fleetRegistry";
import { getApprovedRunArtifacts, type ApprovedRunArtifact } from "./localApi";
import { ActionButton, ActionLink } from "./uiPrimitives";

interface ArtifactScope { runId: string; missionId: string; locale: UiLocale; }

function ArtifactHash(props: { artifact: ApprovedRunArtifact; locale: UiLocale }) {
  const x = (zh: string, en: string) => props.locale === "zh" ? zh : en;
  const [feedback, setFeedback] = createSignal<"copied" | "manual" | null>(null);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(props.artifact.sha256);
      setFeedback("copied");
    } catch {
      setFeedback("manual");
    }
  };
  return <details class="harness-disclosure saved-artifact-hash">
    <summary><span>{x("查看校验值", "View checksum")}</span></summary>
    <div>
      <code>{props.artifact.sha256}</code>
      <ActionButton size="sm" onClick={() => void copy()}>{x("复制 SHA-256", "Copy SHA-256")}</ActionButton>
      <Show when={feedback()}>{(status) => <p role="status">{status() === "copied"
        ? x("SHA-256 已复制。", "SHA-256 copied.")
        : x("剪贴板不可用，可选中上方校验值复制。", "Clipboard unavailable. Select the checksum above to copy it.")}</p>}</Show>
    </div>
  </details>;
}

export function SavedRunArtifacts(props: ArtifactScope) {
  const x = (zh: string, en: string) => props.locale === "zh" ? zh : en;
  const [artifacts, { refetch }] = createResource(
    () => [props.runId, props.missionId] as const,
    ([runId, missionId]) => getApprovedRunArtifacts(runId, missionId),
  );
  const dateFormat = createMemo(() => new Intl.DateTimeFormat(props.locale === "zh" ? "zh-CN" : "en", { dateStyle: "medium", timeStyle: "short" }));
  const rows = () => artifacts.state === "ready" ? artifacts.latest ?? [] : [];

  return <div class="saved-run-artifacts-body">
    <Show when={artifacts.loading}><p role="status">{x("正在读取工件目录…", "Loading the artifact list…")}</p></Show>
    <Show when={artifacts.state === "errored"}>
      <p role="status">{x("暂时无法核验工件目录。", "The artifact list could not be verified.")}</p>
      <ActionButton size="sm" onClick={() => void refetch()}>{x("重试读取目录", "Retry artifact list")}</ActionButton>
    </Show>
    <Show when={artifacts.state === "ready" && !rows().length}><p role="status">{x("暂无可下载的工件。", "No saved artifacts are available for download.")}</p></Show>
    <Show when={rows().length}>
      <ul class="saved-run-artifacts">
        <For each={rows()}>{(artifact) => <li>
          <div><strong>{artifact.title}</strong><time dateTime={artifact.generated_at}>{dateFormat().format(new Date(artifact.generated_at))}</time></div>
          <ActionLink href={artifact.download_path} size="sm" aria-label={x(`下载${artifact.title}`, `Download ${artifact.title}`)}>{x("下载", "Download")}</ActionLink>
          <ArtifactHash artifact={artifact} locale={props.locale} />
        </li>}</For>
      </ul>
    </Show>
    <Show when={artifacts.state === "ready"}>
      <ActionButton size="sm" variant="quiet" onClick={() => void refetch()}>{x("刷新工件目录", "Refresh artifact list")}</ActionButton>
    </Show>
    <DshRunArtifactsHandoff runId={props.runId} locale={props.locale} />
  </div>;
}

export function SavedRunArtifactDisclosure(props: ArtifactScope) {
  const [open, setOpen] = createSignal(false);
  const title = () => props.locale === "zh" ? "已保存工件" : "Saved artifacts";
  return <details class="harness-disclosure saved-run-artifacts-deck" open={open()} onToggle={(event) => setOpen(event.currentTarget.open)}>
    <summary><span>{title()}</span></summary>
    <Show when={open()}>
      <section aria-label={title()}>
        <SavedRunArtifacts runId={props.runId} missionId={props.missionId} locale={props.locale} />
      </section>
    </Show>
  </details>;
}
