# the extension

the extension turns a plain-language browser customization request into a Chrome extension. The public entry point is an Agentverse agent that can be discovered and chatted with from ASI:One. The local backend does the work that a hosted chat agent should not do: write files, validate Manifest V3 projects, package artifacts, and hand the browser UI an install path.

The current demo flow is simple:

```text
ASI:One or the Chrome side panel
-> Agentverse Orchestrator
-> specialist build steps
-> FastAPI execution API
-> generated Chrome extension
```

## What is in this repo

- `backend/`: FastAPI app, Agentverse/uAgents integration, extension generation helpers, validation, packaging, SQLite project storage.
- `browser-agent-console/`: the extension Chrome side panel extension built with React, TypeScript, Vite, and CRXJS.
- `backend/generated_extensions/`: local generated extension workspaces and ZIP artifacts. This directory is ignored by git.

## Agentverse and ASI:One

The Orchestrator agent is the public Agent Chat Protocol agent. It is registered on Agentverse and can be discovered from ASI:One. When a user asks for a browser change, the Orchestrator runs the build pipeline:

```text
Orchestrator
-> Architect
-> RAG/context
-> Codegen
-> Validator
-> Packager
```

The specialist roles are implemented in `backend/agentverse_app/`. They currently run in one local uAgents Bureau for reliability during demos. The registered Orchestrator is enough for the end-to-end flow; registering the specialist roles separately gives you extra Agentverse profile pages for the track.

## Requirements

- Python 3.12+
- `uv`
- Node.js and npm
- Chrome or Chromium
- `ngrok` if you want Agentverse/ASI:One to reach your local agent

## Backend

```bash
cd backend
uv sync
uv run main.py
```

The backend listens on `http://localhost:8000`.

Useful checks:

```bash
curl http://localhost:8000/projects
```

## Agentverse agent server

Run the uAgents process in a second terminal:

```bash
cd backend
uv run python -m agentverse_app.main
```

It listens on `http://localhost:8001` and exposes the Chat Protocol endpoint at:

```text
http://localhost:8001/submit
```

Expose it to Agentverse with ngrok:

```bash
ngrok http 8001
```

Use the HTTPS ngrok URL plus `/submit` as the Agentverse endpoint, for example:

```text
https://example.ngrok-free.dev/submit
```

## Chrome side panel

```bash
cd browser-agent-console
npm install
npm run dev
```

Then open `chrome://extensions`, enable Developer mode, choose Load unpacked, and select `browser-agent-console/dist`.

## Generated extensions

Agentverse builds are written to:

```text
backend/generated_extensions/{project_id}
```

Packaged ZIPs are written to:

```text
backend/generated_extensions/_artifacts/{project_id}.zip
```

For local testing, load the generated folder with Chrome's Load unpacked button. Use the folder that contains `manifest.json`, not the `_artifacts` directory.

## Environment

Create `backend/.env` with the keys you need:

```env
GEMINI_API_KEY=...
AGENTVERSE_API_KEY=...
PUBLIC_AGENT_BASE_URL=https://your-ngrok-url
BACKEND_EXECUTION_API_URL=http://localhost:8000
UAGENTS_PORT=8001
AGENTVERSE_EXECUTION_TOKEN=dev-agentverse-token
```

Keep `.env` out of git.

## Demo prompt

In ASI:One or the side panel, try:

```text
Build a Chrome extension that hides Instagram Reels links.
```

The expected response includes a validation summary, an extension path, and load instructions.
