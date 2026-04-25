# Browser Forge Chat Context

Browser Forge turns browser customization requests into Chrome extension artifacts.

Current workspace:

```text
/Users/abdullahrajput/Documents/evolve-browser
```

Current structure:

- `browser-agent-console/`: installed Chrome side panel UI.
- `backend/`: FastAPI execution API, Agentverse/uAgents app, validation, packaging, and storage.
- `backend/generated_extensions/{project_id}/`: generated Chrome extension folders.
- `backend/generated_extensions/_artifacts/`: ZIP artifacts for generated extensions.

Current user-facing flow:

```text
ASI:One or Browser Agent Console
-> Agentverse Browser Orchestrator
-> Architect / RAG / Codegen / Validator / Packager roles
-> FastAPI execution API
-> generated extension folder and ZIP artifact
```

ASI:One is the discovery and chat surface. Agentverse hosts the registered agent profile and routes Chat Protocol traffic to the public uAgents `/submit` endpoint. The backend remains local execution infrastructure.

Runtime ports:

```text
8000  FastAPI backend
8001  uAgents Chat Protocol endpoint
4040  ngrok inspector
```

Local run commands:

```bash
cd backend
uv run main.py
```

```bash
cd backend
uv run python -m agentverse_app.main
```

```bash
ngrok http 8001
```

Chrome side panel:

```bash
cd browser-agent-console
npm install
npm run dev
```

Load `browser-agent-console/dist` from `chrome://extensions`.
