# CosMatter graph plugin for DeepSeek Harness

This is an independent DeepSeek Harness bundle. It exposes four tools:

- `cosmatter_graph_query` reads a previously projected graph through the loopback-only CosMatter API.
- `cosmatter_accepted_evidence_search` accepts a keyword `query` or one exact `evidence_id` for a run. Each eligible hit includes a same-machine `workbench_url` for CosMatter's reader. The reader's **View evidence in DSH** command uses that same link to look up the exact card.
- `cosmatter_graph_plan` writes an untrusted, non-executing graph-inspection draft for selected existing nodes.
- `cosmatter_graph_review_request` submits a pending human-review request; it cannot accept evidence or modify the graph.

The bundle accepts only `http://127.0.0.1` endpoints. It validates the complete
`cosmatter.graph-snapshot/v1` response and rejects raw quotations, private paths,
credentials, unreviewed evidence, and oversized responses. Graph projection is
performed explicitly by CosMatter (`cosmatter_project_accepted_evidence_graph`
through MCP or `POST /api/runs/<run_id>/graph/project`) before this bundle can read
`GET /api/runs/<run_id>/graph`.

Build and test locally:

```powershell
npm install
npm test
```

After the DeepSeek Harness CLI is installed, add this checkout to a profile:

```powershell
dsh plugin --profile cosmatter add D:\CosMatter\development\CosMatter\plugins\dsh-cosmatter-graph-plugin
```

The `dsh.bundle` manifest activates `cordis.patch.yml`. The plugin follows the
standard `apply(ctx)` shape and declares `inject = ['tools']`; tool registrations
and event effects are scoped to Cordis lifecycle cleanup.
