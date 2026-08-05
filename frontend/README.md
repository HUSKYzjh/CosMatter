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

All views use a local `ui.json`-compatible mission contract or an explicitly selected local JSON file. By default the frontend makes no network calls and produces no scientific conclusions on its own.
## Preview an exported local mission

Build the Solid app, then let the Python loopback server expose exactly one
already-redacted UI bundle. It never serves a `.env`, audit logs, or arbitrary
run files.

```powershell
npm run build
cd ..
.\.venv\Scripts\python.exe -m cosmatter export-ui --run-id <run_id>
.\.venv\Scripts\python.exe -m cosmatter preview-ui --solid --run-id <run_id> --port 8765
```

Open `http://127.0.0.1:8765/?ui=server`. The `?ui=server` opt-in makes the
workbench fetch only the same-origin `/ui.json` route for the selected run.
Without it, the frontend has no automatic connection and continues to use its
manual local JSON import.
On Windows, the equivalent checked launcher is:

```powershell
.\scripts\start-solid-preview.ps1 -RunId <run_id>
```