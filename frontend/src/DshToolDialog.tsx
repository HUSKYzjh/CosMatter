import { onMount } from "solid-js";
import { DshToolCatalogueContent, type DshToolCatalogueProps } from "./DshToolCatalogue";
import { ActionButton } from "./uiPrimitives";

export function DshToolDialog(props: DshToolCatalogueProps & { onDismiss: () => void }) {
  let dialog!: HTMLDialogElement;
  let heading!: HTMLHeadingElement;
  const initialStage = props.currentStage;

  onMount(() => {
    dialog.showModal();
    const initialFocus = window.matchMedia("(pointer: coarse)").matches ? heading : dialog.querySelector<HTMLInputElement>('input[type="search"]');
    initialFocus?.focus();
  });

  return <dialog ref={dialog} class="dsh-tool-dialog" aria-labelledby="dsh-tool-dialog-title" onClose={() => props.onDismiss()}>
    <header>
      <h2 id="dsh-tool-dialog-title" ref={heading} tabIndex={-1}>{props.locale === "zh" ? "查找 DSH 工具" : "Find DSH tools"}</h2>
      <ActionButton size="sm" variant="quiet" aria-label={props.locale === "zh" ? "关闭工具目录" : "Close tool catalogue"}
        onClick={() => dialog.close()}>{props.locale === "zh" ? "关闭" : "Close"}</ActionButton>
    </header>
    <DshToolCatalogueContent locale={props.locale} plugins={props.plugins} profile={props.profile} profileHealth={props.profileHealth}
      currentStage={props.currentStage} runId={props.runId} evidence={props.evidence} onRefreshProfile={props.onRefreshProfile} initialStage={initialStage} scrollResults />
  </dialog>;
}
