# CosMatter research plugin for DeepSeek Harness

This bundle adds offline materials calculations and literature research tools to DeepSeek Harness.

## Materials calculations

Use `cosmatter_pst_occupancy_count` to check the Pb fraction and count labeled A-site arrangements in an 8×8×8 (PbₓSr₁₋ₓ)TiO₃ supercell. Each of the 512 positions holds one Pb or Sr. Supply the exact fraction as text.

```json
{"pb_fraction":"1/512"}
```

This input gives one Pb, 511 Sr and 512 possible placements. The tool returns the binomial coefficient as a decimal string so large integers survive JSON transport. Translation and other crystal symmetries can identify equivalent placements. For `"1/3"`, the result has `realizable: false` and lists both adjacent choices, 170 Pb or 171 Pb. Use the chosen option’s `pb_fraction` to run a new count.

Use `cosmatter_md_field_response` with equilibrated means from two MD runs at opposite fields of the same magnitude. Match the structure, temperature, mechanical boundary and polarization branch. For a longitudinal relative permittivity use `polarization_C_per_m2`. For a longitudinal converse piezoelectric coefficient use `normal_strain` at `fixed_stress`, with strain as a dimensionless fraction. For example, the following **synthetic** input exercises the numerical conversion.

```json
{"axis":"z","mechanical_boundary":"fixed_stress","observable":"normal_strain","field_magnitude_V_per_m":1000000,"mean_at_minus_field":-0.0001,"mean_at_plus_field":0.0001}
```

The synthetic result is `d33 = 100 pm/V`. Each tool operates locally on its arguments. MD trajectories, estimates of uncertainty and checks across field magnitudes must come from the simulation workflow.

## Research planning and literature retrieval

The following tools use the CosMatter loopback API.

- `cosmatter_research_plan_draft` sends the bounded Mission Brief to DeepSeek only after the exact explicit authorizations `mission_scoped_egress_consent` and `deepseek_request_consent` are supplied. Its output remains `untrusted_draft`.
- `cosmatter_research_plan_approve` records a separately reviewed, bounded FlightPlan. It never consumes the model draft implicitly.
- `cosmatter_research_query_execute` sends one selected approved query to Sciverse, OpenAlex, and/or Crossref after the exact explicit authorizations `mission_scoped_egress_consent` and `metadata_provider_consent` are supplied. The result card shows the number of metadata candidates and a same-machine workbench link. When the local stage contract permits screening, the link targets the verified checklist revision. While retrieval is still in progress or the checklist cannot be verified, the link opens the run at its current stage.

The bundle hard-codes neither credentials nor provider URLs. It only connects to a bare `http://127.0.0.1:<port>` CosMatter backend. It cannot download full text, invoke MinerU, record candidate screening, accept evidence, launch a shell, or access the filesystem.
