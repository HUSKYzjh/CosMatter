import { For, createSignal } from "solid-js";

import type { ImportedBundle } from "./model";

type Proposal = { id: string; status: string; title: string; rationale: string; requirement: string; tone: "blue" | "teal" | "violet"; };
const PROPOSALS: Proposal[] = [
  { id: "counterexample", status: "OPEN QUESTION", title: "Design a counterexample search", rationale: "Explore where the current material-property relationship may fail under a clearly bounded condition.", requirement: "Needs: approved query plan and condition schema", tone: "blue" },
  { id: "normalization", status: "METHOD GAP", title: "Normalize condition fields", rationale: "Build comparable fields before combining evidence from different sample geometries or measurement routes.", requirement: "Needs: field dictionary and reviewer sign-off", tone: "teal" },
  { id: "evidence", status: "EVIDENCE GAP", title: "Expand source coverage", rationale: "Collect only source records that can be located and reviewed, then expose remaining coverage gaps.", requirement: "Needs: authorized source set and provenance checks", tone: "violet" },
];

export function ResearchExpansion(props: { bundle: ImportedBundle }) {
  const [armed, setArmed] = createSignal<string | null>(null);
  return (
    <main class="discovery-stage expansion-stage">
      <header class="stage-header"><div><p class="stage-kicker">COSMATTER / RESEARCH EXTENSION</p><h1>Research extension</h1><p>Turn unresolved material questions into explicit, human-approved follow-up missions.</p></div><div class="stage-tools"><button type="button" aria-label="Previous horizon">Previous</button><button type="button" aria-label="Horizon settings">Settings</button><button type="button" aria-label="Next horizon">Next</button></div></header>
      <section class="expansion-brief"><span>Current mission <strong>{props.bundle.mission.missionId}</strong></span><span>Question <strong>{props.bundle.mission.question}</strong></span><span>Outbound actions <strong>0</strong></span></section>
      <section class="horizon-intro"><p class="stage-kicker">RESEARCH HORIZON</p><h2>Do not close a contradiction too early.</h2><p>These are proposed directions, not generated scientific claims. They become executable only after a researcher approves a new task boundary and its evidence requirements.</p></section>
      <section class="proposal-grid" aria-label="Follow-up research proposals"><For each={PROPOSALS}>{(proposal, index) => <article class={`proposal-card tone-${proposal.tone}`}><span>{String(index() + 1).padStart(2, "0")}</span><small>{proposal.status}</small><h2>{proposal.title}</h2><p>{proposal.rationale}</p><footer><em>{proposal.requirement}</em><button type="button" classList={{ armed: armed() === proposal.id }} onClick={() => setArmed(armed() === proposal.id ? null : proposal.id)}>{armed() === proposal.id ? "Marked for review" : "Mark for review"}</button></footer></article>}</For></section>
      <section class="approval-strip"><div><p class="stage-kicker">APPROVAL GATE</p><strong>{armed() ? "One proposed direction is marked for human review." : "No new research action is armed."}</strong></div><button type="button">Create approved follow-up mission</button></section>
      <footer class="stage-note">This page keeps future work separate from current evidence. No new mission, external query, or model call is started from this preview.</footer>
    </main>
  );
}