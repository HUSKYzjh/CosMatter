# CosMatter policy plugin for DeepSeek Harness

This independent DSH bundle exposes only non-executing policy tools:

- `cosmatter_plugin_catalogue` reads the static CosMatter capability catalogue.
- `cosmatter_plugin_authorization_plan` evaluates a prospective mission-scoped
  dispatch boundary. It does not record consent, call a provider, dispatch an
  adapter, accept evidence, or grant execution.

The bundle accepts only a bare `http://127.0.0.1` endpoint.

```powershell
npm install
npm test
dsh plugin --profile cosmatter-graph-test add D:\CosMatter\development\CosMatter\plugins\dsh-cosmatter-policy-plugin
```
