# CosMatter observability plugin for DeepSeek Harness

`cosmatter_workflow_status` exposes a read-only, count-only view of one local
CosMatter run. `cosmatter_stage_contract` adds the same run's fixed completion
requirements, human gates, expected symbolic outputs, and non-executing
recovery-route labels. `cosmatter_operational_telemetry` aggregates only local
receipt/dispatch counts and may show an already human-reviewed cost/latency
disclosure; it is never a provider bill or benchmark. `cosmatter_artifact_manifest` lists only already
generated, fixed allowlist outputs with title, SHA-256, generation time, trust
status, and a fixed download route. None of these tools executes a provider,
reads source content, writes run artifacts, accepts evidence, changes consent,
accepts arbitrary paths, or exposes PDFs, MinerU Markdown, URLs, private paths,
provider payloads, audit details, or credentials.

Only a bare `http://127.0.0.1` endpoint is accepted.

```powershell
npm install
npm test
dsh plugin --profile cosmatter-graph-test add D:\CosMatter\development\CosMatter\plugins\dsh-cosmatter-observability-plugin
```
