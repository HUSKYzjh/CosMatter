export type FleetDecorationKind = "discover" | "workflow" | "graph" | "reader" | "horizon";

export function FleetDecoration(props: { kind: FleetDecorationKind }) {
  return <svg class={`fleet-decoration fleet-decoration--${props.kind}`} viewBox="0 0 1200 800" aria-hidden="true">
    {props.kind === "discover" && <g>
      <ellipse cx="800" cy="390" rx="330" ry="170" /><ellipse class="fleet-dashed" cx="800" cy="390" rx="245" ry="128" />
      <path d="M448 390h703M800 164v452M585 208c75 95 246 132 409 90M580 560c96-83 265-108 424-59" />
      <circle cx="800" cy="390" r="41" /><circle class="fleet-solid" cx="1060" cy="315" r="13" /><circle class="fleet-solid" cx="587" cy="505" r="8" /><circle class="fleet-solid" cx="939" cy="242" r="6" />
    </g>}
    {props.kind === "workflow" && <g>
      <path d="M85 515H300L442 330H660L798 470H1110" /><path class="fleet-dashed" d="M90 570H360L492 398H636L745 535H1085" />
      <path d="m1058 426 53 44-53 44M392 282l50 48-60 33M442 330V108M798 470V670" />
      <circle cx="300" cy="515" r="17" /><circle cx="442" cy="330" r="23" /><circle class="fleet-solid" cx="660" cy="330" r="12" /><circle cx="798" cy="470" r="18" />
    </g>}
    {props.kind === "graph" && <g>
      <path d="M116 526 286 342l172 81 149-236 190 92 157-129 146 192" /><path class="fleet-dashed" d="M286 342c90 116 184 118 321 81M458 423c89 88 210 92 339-144M607 187c90 150 219 207 347 150" />
      <path d="M152 196c146-77 291-59 393 36M669 615c149-108 287-115 415-42" />
      <circle class="fleet-solid" cx="116" cy="526" r="18" /><circle cx="286" cy="342" r="25" /><circle class="fleet-solid" cx="458" cy="423" r="13" /><circle cx="607" cy="187" r="30" /><circle class="fleet-solid" cx="797" cy="279" r="16" /><circle cx="954" cy="150" r="22" /><circle class="fleet-solid" cx="1100" cy="342" r="12" />
    </g>}
    {props.kind === "reader" && <g>
      <circle cx="815" cy="294" r="186" /><circle class="fleet-dashed" cx="815" cy="294" r="132" /><path d="M815 51v76M815 461v76M572 294h76M982 294h76M122 634 632 371M194 690l518-264M330 730l450-230" />
      <path d="M626 366 1094 570H704ZM844 250h134v182H844zM872 281h78M872 321h78M872 361h52" /><circle class="fleet-solid" cx="815" cy="294" r="16" />
    </g>}
    {props.kind === "horizon" && <g>
      <path d="M85 625C320 416 805 405 1125 625" /><path class="fleet-dashed" d="M128 673C389 491 790 484 1076 673" /><path d="M555 535 823 177 990 560ZM823 177v-95M772 247l-55-52M876 247l57-52M823 177 1060 112M823 177 1100 250M362 613h128M406 568v89" />
      <circle class="fleet-solid" cx="823" cy="177" r="21" /><circle class="fleet-solid" cx="1060" cy="112" r="11" /><circle class="fleet-solid" cx="1100" cy="250" r="8" />
    </g>}
  </svg>;
}