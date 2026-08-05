import { For, createSignal } from "solid-js";

import type { ImportedBundle } from "./model";

const PANES = ["Reading task", "Evidence leads", "Review notes"] as const;

export function PaperReader(props: { bundle: ImportedBundle }) {
  const [active, setActive] = createSignal<(typeof PANES)[number]>("Reading task");
  const paneDetail = () => active() === "Reading task"
    ? "Confirm one answerable question and its scope before interpreting a source."
    : active() === "Evidence leads"
      ? "Every lead must point to a paragraph, page, figure, table, or structured field."
      : "Record uncertainty, conflicting conditions, and items that need human confirmation.";

  return (
    <main class="discovery-stage reader-stage">
      <header class="stage-header">
        <div>
          <p class="stage-kicker">COSMATTER / PAPER READING</p>
          <h1>Paper reading desk</h1>
          <p>Prepare evidence locations and review notes for {props.bundle.mission.question}; do not generate a literature conclusion.</p>
        </div>
        <div class="stage-tools">
          <button type="button" aria-label="Previous item">Previous</button>
          <button type="button" aria-label="Reader settings">Settings</button>
          <button type="button" aria-label="Next item">Next</button>
        </div>
      </header>
      <section class="reader-meta">
        <span>Material <strong>{props.bundle.mission.material}</strong></span>
        <span>Scope <strong>{props.bundle.mission.scope}</strong></span>
        <span>Approved snippets <strong>{props.bundle.evidenceCards.length}</strong></span>
        <span>Source maps <strong>{props.bundle.evidenceCards.filter((card) => !card.isSynthetic).length}</strong></span>
      </section>
      <section class="reader-layout" aria-label="Paper reading workbench">
        <aside class="reader-queue">
          <p class="stage-kicker">EVIDENCE QUEUE</p><h2>Reading tasks</h2>
          <For each={PANES}>{(pane, index) => (
            <button type="button" classList={{ active: active() === pane }} onClick={() => setActive(pane)}>
              <span>{String(index() + 1).padStart(2, "0")}</span><strong>{pane}</strong>
              <small>{pane === "Reading task" ? "Confirm scope" : pane === "Evidence leads" ? "Await source locator" : "Await human note"}</small>
            </button>
          )}</For>
          <div class="queue-warning">Without an imported source, no full text, abstract, or inferred content is displayed.</div>
        </aside>
        <article class="source-reader" aria-label="Source reader">
          <div class="source-reader-head"><span>LOCAL SOURCE READER</span><button type="button">Import an authorized paper</button></div>
          <div class="source-empty"><span>*</span><h2>No paper source loaded</h2>
            <p>You will explicitly select a local PDF, HTML file, or authorized open text later. Every evidence snippet must retain a source location after import.</p>
            <dl><div><dt>Planned entry</dt><dd>03_Paper / user-selected file</dd></div><div><dt>Permitted actions</dt><dd>Extract paragraphs, tables, captions, and source locations</dd></div><div><dt>Prohibited actions</dt><dd>Unsupported conclusions or background uploads</dd></div></dl>
          </div>
        </article>
        <aside class="review-notes"><p class="stage-kicker">REVIEW NOTES</p><h2>{active()}</h2><p>{paneDetail()}</p><button type="button">Create local review note</button><small>Notes belong to the mission artifact and are not sent to an external service.</small></aside>
      </section>
      <footer class="stage-note">Source import, parsing, and evidence extraction will be connected separately. This view currently establishes their safe reading boundary.</footer>
    </main>
  );
}