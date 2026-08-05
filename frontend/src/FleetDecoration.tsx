export type FleetDecorationKind = "discover" | "workflow" | "graph" | "reader" | "horizon";

export function FleetDecoration(props: { kind: FleetDecorationKind }) {
  return <svg class={`fleet-decoration fleet-decoration--${props.kind}`} viewBox="0 0 1200 800" aria-hidden="true">
    {props.kind === "discover" && <g>
      <ellipse cx="860" cy="390" rx="370" ry="196" /><ellipse class="fleet-dashed" cx="860" cy="390" rx="290" ry="152" />
      <path d="M545 238c108 87 275 115 435 72M582 552c103-75 266-98 407-55" />
      <circle cx="860" cy="390" r="29" /><circle class="fleet-solid" cx="1090" cy="294" r="8" />
    </g>}
    {props.kind === "workflow" && <g>
      <path d="M166 530H378L526 344H748L936 480H1130" /><path class="fleet-dashed" d="M210 588H430L565 425H714L862 558H1100" />
      <circle cx="378" cy="530" r="13" /><circle cx="748" cy="344" r="13" /><circle class="fleet-solid" cx="936" cy="480" r="7" />
    </g>}
    {props.kind === "graph" && <g>
      <path d="M190 533 376 357l194 88 170-226 212 96 144-116" /><path class="fleet-dashed" d="M376 357c93 118 203 126 364 88M570 445c100 89 228 61 382-130" />
      <circle cx="376" cy="357" r="16" /><circle cx="740" cy="219" r="18" /><circle class="fleet-solid" cx="952" cy="315" r="8" />
    </g>}
    {props.kind === "reader" && <g>
      <circle cx="865" cy="286" r="214" /><circle class="fleet-dashed" cx="865" cy="286" r="156" />
      <path d="M865 42v68M865 462v68M620 286h70M1040 286h70M170 660 706 382M278 724l470-246" />
      <circle class="fleet-solid" cx="865" cy="286" r="9" />
    </g>}
    {props.kind === "horizon" && <g>
      <path d="M80 655C342 432 842 423 1140 655" /><path class="fleet-dashed" d="M150 700C420 515 807 508 1090 700" />
      <path d="M596 558 864 198 1010 575ZM864 198v-78M864 198 1070 140" />
      <circle class="fleet-solid" cx="864" cy="198" r="10" /><circle cx="1070" cy="140" r="8" />
    </g>}
  </svg>;
}