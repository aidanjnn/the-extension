# the extension

> Build Chrome extensions from natural language — with live browser context.

A multi-agent system on Fetch.ai Agentverse that generates, validates, and installs Chrome extensions in under 60 seconds.

## Quickstart

### 1. Environment

```bash
cp .env.example .env
# Fill in GOOGLE_API_KEY and agent seeds
```

### 2. Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
# → http://localhost:8000/api/health
```

### 3. Chrome Extension

```bash
cd the-extension
npm install
npm run dev   # dev mode with HMR
# or
npm run build # production build → dist/
```

Load in Chrome: `chrome://extensions` → Enable Developer Mode → Load Unpacked → select `the-extension/dist/`

## Architecture

See [docs/architecture.md](docs/architecture.md) for full system diagrams.

| Agent | Role |
|---|---|
| Orchestrator | Receives intent, plans, delegates, assembles |
| CodeGen | Writes Chrome extension files (Gemini LLM) |
| Validator | 4-layer validation (manifest → files → JS → MV3) |
| BrowserContext | Live DOM, console logs, clicked elements via WebSocket |

## Environment Variables

| Variable | Description |
|---|---|
| `GOOGLE_API_KEY` | Gemini API key |
| `ORCHESTRATOR_AGENT_SEED` | Fetch.ai agent seed phrase |
| `CODEGEN_AGENT_SEED` | Fetch.ai agent seed phrase |
| `VALIDATOR_AGENT_SEED` | Fetch.ai agent seed phrase |
| `BROWSER_CONTEXT_AGENT_SEED` | Fetch.ai agent seed phrase |

## Dev Commands

- **Backend:** `cd backend && uvicorn main:app --reload`
- **Extension dev:** `cd the-extension && npm run dev`
- **Extension build:** `cd the-extension && npm run build`
- **MCP server:** `cd backend && python -m mcp.server`

See [CLAUDE.md](CLAUDE.md) for full product spec and architecture decisions.
