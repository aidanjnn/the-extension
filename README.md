# the extension

> personalize your browsing experience in seconds

**the extension** is an AI-agent powered Chrome side panel that turns one sentence into a real, installable Chrome extension. Type what you want, and an Agentverse-registered agent plans it, writes it, validates the Manifest V3 manifest, packages a ZIP, and hands you a Load Unpacked card. End to end, prompt to installed extension, takes under a minute.

It also has an **Edit DOM mode**: hold ⌘, hover any element on a webpage, click to select it, and tell the agent things like "make this 30% wider," "hide it," "move it to the top," or "change the text to 'inbox zero'." Watch the page change live. When you're happy with the edits, one button exports them as a permanent Chrome extension that re-applies your changes every time you visit that site.

- 🌐 Landing page: **[thewebisboring.design](https://thewebisboring.design)**
- 🤖 Public agent on ASI:One / Agentverse: **[the extension orchestrator](https://agentverse.ai/agents/details/agent1q0a82jftlsmgjnuxw32mm2ewhtsyr4mnhke8tnmxv34nra5qjz8uzvmwgkw/profile)**
- 🛠 Built at **[LA Hacks](https://lahacks.com)** for the Flicker to Flow track.

## Repo layout

```text
backend/                FastAPI execution layer + uAgents (Agentverse) app
browser-agent-console/  Chrome side panel (React + TypeScript + Vite)
ARCHITECTURE.md         deeper architecture reference
DEVPOST.md              Devpost submission writeup
```

## Requirements

- Python 3.12+
- [`uv`](https://github.com/astral-sh/uv)
- Node.js 18+ and npm
- Chrome or Chromium
- [`ngrok`](https://ngrok.com) (free tier is fine)

## Clone and install

```bash
git clone https://github.com/aidanjnn/the-extension.git
cd the-extension

# backend deps
cd backend && uv sync && cd ..

# extension deps
cd browser-agent-console && npm install && cd ..
```

## Environment

Create `backend/.env` (this file is gitignored). The seeds determine the agent's on-Agentverse identity, so leave them alone unless you want to register a fresh agent.

```env
GEMINI_API_KEY=your_gemini_key
AGENTVERSE_API_KEY=your_agentverse_key

PUBLIC_AGENT_BASE_URL=https://your-static-ngrok-uagents-url
PUBLIC_BACKEND_BASE_URL=https://your-public-backend-url
BACKEND_EXECUTION_API_URL=http://localhost:8000
UAGENTS_PORT=8001
AGENTVERSE_EXECUTION_TOKEN=dev-agentverse-token

ORCHESTRATOR_SEED=the-extension-orchestrator-demo-seed
ARCHITECT_SEED=the-extension-architect-demo-seed
RAG_SEED=the-extension-rag-demo-seed
CODEGEN_SEED=the-extension-codegen-demo-seed
VALIDATOR_SEED=the-extension-validator-demo-seed
PACKAGER_SEED=the-extension-packager-demo-seed
```

Set up an ngrok config at `~/Library/Application Support/ngrok/ngrok.yml` so a single command starts both tunnels:

```yaml
version: "3"
agent:
  authtoken: <your-ngrok-authtoken>
tunnels:
  uagents:
    proto: http
    addr: 8001
    domain: <your-static-ngrok-domain>.ngrok-free.dev
  backend:
    proto: http
    addr: 8000
```

The `uagents` tunnel needs a static domain so Agentverse can keep reaching your registered agent. The `backend` tunnel can be ephemeral.

## Run the four dev servers

You'll want four terminals running at once.

**1. FastAPI backend** — port 8000

```bash
cd backend
uv run main.py
```

**2. uAgents Chat Protocol server** — port 8001

```bash
cd backend
uv run python -m agentverse_app.main
```

**3. ngrok tunnels** — exposes 8000 and 8001 publicly

```bash
ngrok start uagents backend
```

After ngrok prints the backend URL, copy it into `PUBLIC_BACKEND_BASE_URL` in `backend/.env` and restart the FastAPI server.

**4. Chrome side panel dev build**

```bash
cd browser-agent-console
npm run dev
```

Then open `chrome://extensions`, enable Developer mode, click **Load unpacked**, and select `browser-agent-console/dist`. Pin the side panel and you're good.

## Try it

In the side panel (or via ASI:One on the agent's [public page](https://agentverse.ai/agents/details/agent1q0a82jftlsmgjnuxw32mm2ewhtsyr4mnhke8tnmxv34nra5qjz8uzvmwgkw/profile)):

```text
Hide YouTube comments and Shorts on the homepage.
```

You should see progress events, an `extension_ready` install card, and a folder + ZIP under `backend/generated_extensions/`. Load the unpacked folder, refresh YouTube, comments are gone.

## Where things live

- `backend/main.py` — FastAPI routes, WebSocket chat, DOM-edits export endpoint
- `backend/agentverse_app/` — uAgents Bureau, Orchestrator, and specialist roles (Architect / RAG / Codegen / Validator / Packager)
- `browser-agent-console/src/sidepanel/` — Create / Edit DOM UI
- `browser-agent-console/src/content/` — Cmd-hover purple overlay and live DOM ops

For the deeper architecture see [`ARCHITECTURE.md`](./ARCHITECTURE.md). For the Devpost writeup see [`DEVPOST.md`](./DEVPOST.md).
