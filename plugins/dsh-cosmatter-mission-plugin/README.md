# CosMatter mission plugin for DeepSeek Harness

This independent DSH bundle exposes one bounded tool:

- `cosmatter_mission_create` creates a local CosMatter Mission Brief and fleet
  assignment through the loopback API. It never calls a model or literature
  provider, approves a search plan, accepts evidence, or accesses the file
  system directly.

Only `http://127.0.0.1` is accepted as the API endpoint. The tool rejects
oversized inputs and response objects containing sensitive-looking fields.
The result includes `workbench_url`. Open it in a browser on the same machine
to load the existing run in CosMatter. The link uses the configured API port
and carries the run ID in its fragment.

```powershell
npm install
npm test
dsh plugin --profile cosmatter add D:\CosMatter\development\CosMatter\plugins\dsh-cosmatter-mission-plugin
```
