import { createSignal } from "solid-js";
import { fleetVisualStyle, type FleetVisualKind, type FleetVisualState } from "./fleetVisualState";

export type FleetDecorationKind = FleetVisualKind;

export const AMBIENT_ASSETS: Record<FleetDecorationKind, readonly string[]> = {
  discover: [
    "/ambient-backgrounds/fleet/fleet-01-flagship.png",
    "/ambient-backgrounds/fleet/fleet-02-formation.png",
    "/ambient-backgrounds/fleet/fleet-03-flotilla.png",
    "/ambient-backgrounds/fleet/fleet-04-expedition.png",
    "/ambient-backgrounds/fleet/fleet-05-surveyor.png",
  ],
  workflow: [
    "/ambient-backgrounds/fleet/fleet-01-flagship.png",
    "/ambient-backgrounds/fleet/fleet-02-formation.png",
    "/ambient-backgrounds/fleet/fleet-03-flotilla.png",
    "/ambient-backgrounds/fleet/fleet-04-expedition.png",
    "/ambient-backgrounds/fleet/fleet-05-surveyor.png",
  ],
  graph: [
    "/ambient-backgrounds/starfield/stars-01-constellation.png",
    "/ambient-backgrounds/starfield/stars-02-horizon.png",
    "/ambient-backgrounds/starfield/stars-03-scan.png",
    "/ambient-backgrounds/starfield/stars-04-sector.png",
    "/ambient-backgrounds/starfield/stars-05-crystal.png",
  ],
  reader: [
    "/ambient-backgrounds/fleet/fleet-05-surveyor.png",
    "/ambient-backgrounds/fleet/fleet-01-flagship.png",
    "/ambient-backgrounds/fleet/fleet-02-formation.png",
    "/ambient-backgrounds/fleet/fleet-04-expedition.png",
    "/ambient-backgrounds/fleet/fleet-03-flotilla.png",
  ],
  horizon: [
    "/ambient-backgrounds/starfield/stars-02-horizon.png",
    "/ambient-backgrounds/starfield/stars-05-crystal.png",
    "/ambient-backgrounds/starfield/stars-04-sector.png",
    "/ambient-backgrounds/starfield/stars-03-scan.png",
    "/ambient-backgrounds/starfield/stars-01-constellation.png",
  ],
};

/** Keep the session value deliberately content-free: it is only an asset index. */
export function ambientIndexFromSessionValue(saved: string | null, assetCount: number, random = Math.random): number {
  const parsed = saved !== null && /^\d+$/.test(saved) ? Number.parseInt(saved, 10) : Number.NaN;
  return Number.isInteger(parsed) && parsed >= 0 && parsed < assetCount ? parsed : Math.floor(random() * assetCount);
}

function ambientForSession(kind: FleetDecorationKind): string {
  const assets = AMBIENT_ASSETS[kind];
  const key = `cosmatter.ambient.${kind}.v2`;
  try {
    const saved = window.sessionStorage.getItem(key);
    const index = ambientIndexFromSessionValue(saved, assets.length);
    if (saved === null) window.sessionStorage.setItem(key, String(index));
    return assets[index];
  } catch {
    // Privacy-restricted contexts may deny Web Storage. Decoration must never
    // block access to a local research workspace when that happens.
    return assets[ambientIndexFromSessionValue(null, assets.length)];
  }
}

function FleetMark(props: { class?: string; x: number; y: number; scale?: number; rotate?: number }) {
  const scale = props.scale ?? 1;
  const rotate = props.rotate ?? 0;
  return <g class={`fleet-mark ${props.class ?? ""}`} transform={`translate(${props.x} ${props.y}) rotate(${rotate}) scale(${scale})`}>
    <path class="fleet-hull" d="M-52 0 -18-14 42-5 56 0 42 5-18 14Z" />
    <path class="fleet-wing" d="M-16-9 8-28 28-7M-16 9 8 28 28 7" />
    <path class="fleet-hull-detail" d="M-28 0 5-7 35 0 5 7Z" />
    <path class="fleet-engine" d="M-52-5-70 0-52 5" />
    <circle class="fleet-beacon" cx="14" cy="0" r="2.5" />
  </g>;
}

function DiscoverScene() {
  return <g class="fleet-scene fleet-scene--discover">
    <ellipse class="fleet-orbit fleet-orbit--wide" cx="846" cy="374" rx="346" ry="184" />
    <ellipse class="fleet-orbit fleet-orbit--inner fleet-dashed" cx="846" cy="374" rx="252" ry="128" />
    <path class="fleet-route fleet-dashed" d="M420 452C620 194 952 173 1122 330" />
    <path class="fleet-scan" d="M505 534C669 444 884 424 1060 492" />
    <circle class="fleet-gate" cx="840" cy="374" r="20" />
    <circle class="fleet-signal-point" cx="1042" cy="260" r="6" />
    <g class="fleet-formation fleet-formation--discover"><FleetMark x={836} y={374} scale={1.35} /><FleetMark x={710} y={452} scale={0.54} rotate={-9} /><FleetMark x={746} y={276} scale={0.48} rotate={7} /><FleetMark x={972} y={436} scale={0.43} rotate={-5} /></g>
  </g>;
}

function WorkflowScene() {
  return <g class="fleet-scene fleet-scene--workflow">
    <path class="fleet-route fleet-route--main" d="M146 560H332L492 390H702L870 510H1124" />
    <path class="fleet-route fleet-route--parallel fleet-dashed" d="M182 620H366L524 450H670L834 570H1096" />
    <path class="fleet-approval-beam" d="M332 560 492 390 702 390" />
    <circle class="fleet-gate" cx="332" cy="560" r="11" /><circle class="fleet-gate" cx="702" cy="390" r="11" />
    <circle class="fleet-signal-point" cx="870" cy="510" r="6" />
    <g class="fleet-formation fleet-formation--workflow"><FleetMark x={500} y={376} scale={.94} rotate={-17} /><FleetMark x={614} y={391} scale={.48} /><FleetMark x={812} y={495} scale={.48} rotate={20} /></g>
  </g>;
}

function GraphScene() {
  return <g class="fleet-scene fleet-scene--graph">
    <path class="fleet-citation-arc" d="M274 538C360 270 560 230 696 430S946 528 1090 248" />
    <path class="fleet-citation-arc fleet-dashed" d="M328 606C518 480 618 520 762 354S972 354 1122 470" />
    <path class="fleet-constellation" d="M370 436 528 304 694 410 856 228 1018 352M528 304 650 548 856 228M694 410 918 548" />
    <g class="fleet-cluster"><circle class="fleet-gate" cx="370" cy="436" r="13" /><circle class="fleet-gate" cx="528" cy="304" r="11" /><circle class="fleet-gate" cx="694" cy="410" r="15" /><circle class="fleet-gate" cx="856" cy="228" r="11" /><circle class="fleet-gate" cx="1018" cy="352" r="13" /><circle class="fleet-gate" cx="650" cy="548" r="9" /><circle class="fleet-gate" cx="918" cy="548" r="9" /></g>
    <g class="fleet-formation fleet-formation--graph"><FleetMark x={694} y={410} scale={.52} rotate={-14} /><FleetMark x={846} y={224} scale={.32} rotate={8} /><FleetMark x={926} y={544} scale={.30} rotate={-20} /></g>
    <circle class="fleet-signal-point" cx="856" cy="228" r="5" />
  </g>;
}

function ReaderScene() {
  return <g class="fleet-scene fleet-scene--reader">
    <circle class="fleet-aperture" cx="870" cy="286" r="218" /><circle class="fleet-aperture fleet-dashed" cx="870" cy="286" r="158" />
    <path class="fleet-source-beam" d="M178 676 710 390 870 286" /><path class="fleet-source-beam fleet-source-beam--secondary" d="M284 730 744 470 870 286" />
    <path class="fleet-locator-ticks" d="M870 40v74M870 458v74M624 286h74M1042 286h74" />
    <g class="fleet-formation fleet-formation--reader"><FleetMark x={700} y={394} scale={.8} rotate={-28} /><FleetMark x={550} y={476} scale={.34} rotate={-28} /></g>
    <circle class="fleet-signal-point" cx="870" cy="286" r="6" />
  </g>;
}

function HorizonScene() {
  return <g class="fleet-scene fleet-scene--horizon">
    <path class="fleet-horizon-line" d="M74 656C330 438 832 418 1140 656" /><path class="fleet-horizon-line fleet-dashed" d="M144 710C406 516 824 500 1090 710" />
    <path class="fleet-probe-cone" d="M650 590 886 202 1042 592Z" /><path class="fleet-probe-vector fleet-dashed" d="M886 202 1098 128" />
    <g class="fleet-formation fleet-formation--horizon"><FleetMark x={812} y={334} scale={.68} rotate={-57} /><FleetMark x={756} y={430} scale={.40} rotate={-57} /><FleetMark x={864} y={464} scale={.34} rotate={-57} /></g>
    <circle class="fleet-gate" cx="886" cy="202" r="8" /><circle class="fleet-signal-point" cx="1098" cy="128" r="6" />
  </g>;
}

export function FleetDecoration(props: { kind: FleetDecorationKind; state: FleetVisualState }) {
  const [ambientAsset] = createSignal(ambientForSession(props.kind));
  return <>
    <div class={`ambient-texture ambient-texture--${props.kind}`} aria-hidden="true"><img src={ambientAsset()} alt="" /></div>
    <svg class={`fleet-decoration fleet-decoration--${props.kind}`} data-fleet-mode={props.state.mode} style={fleetVisualStyle(props.state)} viewBox="0 0 1200 800" aria-hidden="true">
      {props.kind === "discover" && <DiscoverScene />}
      {props.kind === "workflow" && <WorkflowScene />}
      {props.kind === "graph" && <GraphScene />}
      {props.kind === "reader" && <ReaderScene />}
      {props.kind === "horizon" && <HorizonScene />}
    </svg>
  </>;
}
