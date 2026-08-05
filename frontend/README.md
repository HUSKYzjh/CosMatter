# CosMatter Solid workbench

This is the independent TypeScript + SolidJS + Vite frontend. It does not replace the existing static `web/` demo and it never reads `.env` files.

## Run locally

```powershell
cd frontend
npm install
npm run dev
```

Run checks before integration:

```powershell
npm run test
npm run build
```

## Views

- Discovery: define a research question and inspect local task objects.
- Workflow: follow an evidence-first research and reading route.
- Graph: navigate local concepts and review dependencies.
- Reading: reserve a three-pane workflow for explicitly imported sources.
- Extension: prepare human-approved follow-up missions.

All views use a local `ui.json`-compatible mission contract or an explicitly selected local JSON file. The frontend makes no network calls and produces no scientific conclusions on its own.