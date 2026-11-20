# CosMatter mission plugin for DeepSeek Harness

This independent DSH bundle exposes one bounded tool:

- `cosmatter_mission_create` creates a local CosMatter Mission Brief and fleet
  assignment through the loopback API. It never calls a model or literature
  provider, approves a search plan, accepts evidence, or accesses the file
  system directly.

Only `http://127.0.0.1` is accepted as the API endpoint. The tool rejects
oversized inputs and response objects containing sensitive-looking fields.
After creation, the DSH result card shows the run ID and its workbench URL.
Open that URL in a browser on the same machine to continue the run in CosMatter.
The structured tool result includes the same link as `workbench_url`.

```powershell
npm install
npm test
dsh plugin --profile cosmatter add D:\CosMatter\development\CosMatter\plugins\dsh-cosmatter-mission-plugin
```
