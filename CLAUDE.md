# the extension — Master Build Prompt

You are an elite AI coding agent (thinking mode). Act as a senior staff engineer + hackathon product lead. You must output an implementation-first plan and repo scaffold for a hackathon MVP called **the extension**. The goal is to build the MAIN FRAME first so a team can split tasks and code in parallel on GitHub.

> **IMPORTANT:** This product is a specialized coding agent that ships personal software (Chrome extensions) on demand, with the killer detail being that the agent has live access to the running browser via WebSocket, so the extensions it writes are context-aware. "the extension" is the user's browser evolving into a personalized tool. We are building a multi-agent system on Fetch.ai Agentverse and packaging the browser-context tools as agent plugins for the Cognition track. Do NOT build a generic chatbot. Do NOT build a simple wrapper. Build a real multi-agent architecture with discoverable agents.

---

## Product Context

We are building **the extension**, a multi-agent system that generates and installs Chrome extensions from natural language — with live browser context.

**the extension** is not a chatbot. It's not a code generator. It's a swarm of specialist AI agents that can see what you see in your browser, understand your intent, write a Chrome extension, validate it, and install it — all in under 60 seconds.

The system is composed of specialist uAgents registered on Fetch.ai Agentverse:

| Agent | Role |
|---|---|
| **Orchestrator Agent** | Receives user intent, plans, delegates, assembles |
| **CodeGen Agent** | Writes Chrome extension code (manifest, scripts, popup, styles) |
| **Validator Agent** | Runs 4-layer validation (manifest → file refs → JS syntax → MV3 compat) |
| **BrowserContext Agent** | Fetches live DOM, console logs, clicked elements from the user's browser via WebSocket |

These agents communicate via Fetch.ai's Chat Protocol and are discoverable on ASI:One.

The browser-context tools are also packaged as an MCP server — any AI coding agent (Devin, Cursor, etc.) can use them. This is our Cognition track angle.

---

## Track Alignment

### Track 1: Fetch.ai — Agentverse ($2,500 / $1,500 / $1,000)

- Build and Register AI Agents on Agentverse, discoverable via ASI:One
- Multi-agent orchestration that demonstrates reasoning + tool execution
- Chat Protocol is **MANDATORY**
- Payment Protocol is optional (bonus points)
- Demo must happen through ASI:One — no custom frontend required
- **Deliverables:** ASI:One shared chat URL, Agentverse agent URL(s), GitHub repo + demo video

### Track 2: Cognition — Augment the Agent ($3,000 / $2,000 / $1,000)

- Build a tool/integration/product that makes AI coding agents measurably more capable
- Judges want: Impact, Technical Depth, Usability, Creativity
- Their suggested directions we hit:
  - **Smarter context retrieval** → Graph RAG (knowledge graph + vector embeddings)
  - **Better verification** → 4-layer Chrome extension validator
  - **Agent plugins** → Browser context as MCP server tools
  - **Human-AI collaboration** → Click-to-select elements, keyboard shortcuts, streaming tool status

---

## Core User Experience

### Via ASI:One (Fetch.ai track)

User opens ASI:One → finds "the extension" agent → types:

- *"Build me a Chrome extension that hides all YouTube Shorts"*
- *"Create an extension that adds a dark mode toggle to any website"*
- *"Make an extension that highlights all external links in red"*

The orchestrator plans, delegates to CodeGen + Validator, returns the finished extension with download link.

### Via Browser Sidepanel (Cognition track)

User opens sidepanel → types or uses keyboard shortcuts:

- `Cmd+Shift+E` → opens sidepanel
- Clicks elements on page → agent gets CSS selectors as context
- *"Block everything that looks like this"* → agent writes targeted extension
- Agent streams tool calls in real-time, validates, auto-installs

---

## MVP Feature Set (Strict)

### Must Have

#### Multi-Agent System on Agentverse (CORE — Fetch.ai)
- Orchestrator Agent with Chat Protocol (mandatory)
- CodeGen Agent — writes Chrome extensions
- Validator Agent — 4-layer extension validation
- Agent-to-agent messaging via uAgents Model classes
- All agents registered on Agentverse + discoverable via ASI:One

#### Browser Context Tools (CORE — Cognition)
- `get_tab_content` — fetch DOM/text from user's open tabs
- `get_console_logs` — fetch console output from browser tabs
- `get_clicked_elements` — retrieve user-selected DOM elements + CSS selectors
- Package as MCP server for any agent to use

#### Graph RAG Semantic Code Search
- Knowledge graph of code entities + relationships (NetworkX)
- Vector embeddings for semantic similarity
- BFS graph traversal + re-ranking for context-aware results
- Show measurable improvement vs naive grep search

#### 4-Layer Extension Validator
- **Layer 1:** Manifest structure validation (required fields, valid keys)
- **Layer 2:** File reference verification (all referenced files exist)
- **Layer 3:** JavaScript syntax checking
- **Layer 4:** MV3 compatibility scanning (deprecated API detection)
- Agent-to-agent error loop: Validator → CodeGen → fix → re-validate

#### Keyboard Shortcuts + Click-to-Select
- `Cmd+Shift+E` — open sidepanel
- `Cmd+Enter` — send message
- `Cmd+K` — quick actions
- Click-to-select mode — user clicks page elements, agent receives selectors

#### Agent Observability Dashboard
- Real-time visualization of agent message flow in sidepanel
- Show which agent is active, status, message passing
- Before/after metrics for Graph RAG vs grep

---

## Explicit Non-Goals

- No full browser fork (we're a Chrome extension + backend)
- No general-purpose coding agent (Chrome extensions only)
- No blockchain/crypto features (even though Fetch.ai has FET tokens)
- No persistent cloud hosting of generated extensions
- No code review or quality scoring
- No app store or marketplace (keep it focused)

---

## Agent Behavior Rules

### Orchestrator Agent
- Receives user intent from ASI:One Chat Protocol
- Plans: what extension to build, what files needed
- Delegates to CodeGen and Validator in sequence
- Handles errors: if Validator fails, re-prompts CodeGen with specific fixes
- Returns structured response with extension files + instructions

### CodeGen Agent
- Writes complete Chrome extensions: manifest.json, content scripts, popup, styles
- Uses browser context (DOM, console logs) when available
- Follows MV3 best practices
- Never generates binary or non-textual content

### Validator Agent
- Stateless, reusable — any agent on Agentverse can invoke it
- Returns structured report: `{ valid: bool, errors: [...], warnings: [...] }`
- Does NOT fix code — only reports issues

### BrowserContext Agent
- Bridge between Agentverse agents and the browser WebSocket
- Real-time data: DOM content, console logs, clicked elements
- Returns structured page data for CodeGen to use

---

## Technical Architecture

### Stack

| Layer | Technology |
|---|---|
| Frontend | Chrome Extension (React + TypeScript + Vite + CRXJS) — sidepanel chat UI |
| Backend | Python (FastAPI) — REST + WebSocket server |
| Agents | Fetch.ai uAgents SDK — multi-agent orchestration on Agentverse |
| LLM | Google Gemini API (`gemini-2.5-flash` primary, `gemini-2.0-flash` secondary) |
| Search | Graph RAG (NetworkX + vector embeddings via `text-embedding-004`) |
| Plugins | MCP server for browser context tools |
| Database | SQLite (projects, conversations, messages, agent memory rules) |

### Data Flow — Fetch.ai Track

```
ASI:One Chat (user types prompt)
    ↓
Orchestrator Agent (Agentverse, Chat Protocol)
    ↓ plans extension
    ↓ delegates to...
CodeGen Agent ←→ BrowserContext Agent (optional: live page data)
    ↓ writes extension files
Validator Agent
    ↓ validates (loops back to CodeGen on failure)
    ↓ passes
Orchestrator returns finished extension to ASI:One
```

### Data Flow — Cognition Track (Browser Sidepanel)

```
User types in sidepanel / clicks elements / uses shortcuts
    ↓
Chrome Extension → WebSocket → FastAPI Backend
    ↓
EvolveAgent agentic loop:
    Plan → Call Tools → Observe → Repeat
    Tools: create_file, edit_file, grep_search, codebase_search (Graph RAG),
           get_tab_content, get_console_logs, validate_extension, load_extension
    ↓
Stream events back (content, tool_start, tool_end, thinking, done)
    ↓
Extension shows install card → one-click load into Chrome
```

### Message Models (uAgents)

```python
from uagents import Model

class ExtensionRequest(Model):
    prompt: str
    browser_context: str | None = None  # DOM/page content if available
    project_id: str | None = None

class CodeGenRequest(Model):
    prompt: str
    project_id: str
    browser_context: str | None = None
    fix_errors: list[str] | None = None  # from validator, for re-gen

class CodeGenResponse(Model):
    files: dict[str, str]  # filename -> content
    success: bool
    error: str | None = None

class ValidateRequest(Model):
    files: dict[str, str]  # filename -> content

class ValidateResponse(Model):
    valid: bool
    errors: list[str]
    warnings: list[str]

class ExtensionResponse(Model):
    files: dict[str, str]
    valid: bool
    summary: str
```

---

## Risk Mitigation

| Risk | Fallback |
|---|---|
| Agentverse registration fails | Pre-register agents, have URLs ready |
| ASI:One chat breaks | Screen recording backup of working ASI:One demo |
| Gemini rate limits | Use `gemini-2.0-flash` (1500 req/day free tier) |
| Graph RAG indexing slow | Pre-index demo project, don't cold-start in demo |
| Extension auto-load fails | Manual "Load unpacked" in `chrome://extensions` |
| Agent-to-agent latency | Show orchestrator reasoning while waiting |

---

## Demo Script (90 seconds)

### Demo 1: ASI:One (Fetch.ai track)

- **[0:00]** *"Engineers waste hours building browser tweaks. the extension builds them in 30 seconds. Watch."*
- **[0:10]** Open ASI:One, find the extension agent. Type: *"Build me an extension that hides all YouTube Shorts"*
- **[0:15]** Orchestrator: *"Planning extension... Delegating to CodeGen Agent..."*
- **[0:25]** Orchestrator: *"CodeGen produced 3 files. Sending to Validator..."*
- **[0:30]** Orchestrator: *"Validation passed ✅ Here's your extension: manifest.json, content.js, content.css — Download and load via chrome://extensions"*
- **[0:45]** Load extension → YouTube Shorts disappear instantly

### Demo 2: Browser Sidepanel (Cognition track)

- **[0:50]** Open sidepanel on YouTube. Click on a Shorts element. Type: *"Hide everything that looks like this"*
- **[1:00]** Agent streams tool calls → `get_tab_content ✓` → `codebase_search ✓` → `create_file ✓` → `validate_extension ✓` → `load_extension ✓`
- **[1:10]** Extension auto-loads, Shorts disappear. *"That took the agent 12 seconds. Graph RAG found the right code patterns in 1 tool call vs 5 with grep."*
- **[1:25]** END

---

## Build Order

1. **Get the extension running (1 hr)** — Backend + extension, verify full flow works
2. **Build uAgents (4–5 hrs)** — Orchestrator with Chat Protocol, CodeGen Agent, Validator Agent, agent-to-agent messaging with Model classes, register on Agentverse
3. **MCP Server for browser tools (2–3 hrs)** — Package `get_tab_content`, `get_console_logs`, `get_clicked_elements`, expose as MCP tools
4. **Keyboard shortcuts + click-to-select (1–2 hrs)** — `Cmd+Shift+E`, `Cmd+Enter`, `Cmd+K`, polish element highlighter → agent context pipeline
5. **Agent observability dashboard (2 hrs)** — Show agent message flow in sidepanel, before/after metrics for Graph RAG
6. **Demo prep (2 hrs)** — Record ASI:One chat session, prepare 3 compelling demo scenarios, record backup video

---

## Deliverables

### Fetch.ai Track
- [ ] ASI:One shared chat session URL
- [ ] Agentverse agent URL(s) for all agents
- [ ] Public GitHub repo + demo video on Devpost
- [ ] Working multi-agent orchestration via ASI:One

### Cognition Track
- [ ] Public GitHub repo + demo video on Devpost
- [ ] MCP server for browser context tools
- [ ] Measurable before/after metrics (Graph RAG vs grep, validation catch rate)
- [ ] Working browser sidepanel with keyboard shortcuts + click-to-select

---

## Success Criteria

- ✓ Build a working Chrome extension from a single sentence in under 60 seconds
- ✓ Show multi-agent coordination with clear reasoning visible in ASI:One
- ✓ Demonstrate Graph RAG is measurably better than naive code search
- ✓ Feel like a real product, not a hackathon demo
- ✓ Double-dip both tracks with the same project

---

## Required Deliverable Outputs

1. PRD summary + MVP feature definition
2. System architecture diagram (multi-agent data flow + browser integration)
3. Exact repo structure + file tree
4. Tech stack (no ambiguity — see [Stack](#stack) table)
5. SQLite schema for: Projects, Conversations, Messages, Rules
6. uAgent message models (request/response contracts for all agents)
7. Agentverse registration steps + Chat Protocol implementation
8. MCP server tool definitions for browser context
9. Agent orchestration flow (how Orchestrator delegates + handles failures)
10. Graph RAG indexing + search pipeline
11. "FIRST 2 HOURS BUILD ORDER" checklist
12. Exact env vars needed:
    - `GOOGLE_API_KEY` (Gemini)
    - `FETCH_AI_AGENT_SEED` (per agent)
13. Commands to run locally
14. Key code snippets for critical paths

---

## Key Files Reference

| File | Purpose |
|---|---|
| `backend/main.py` | FastAPI app, WebSocket, REST routes |
| `backend/utils/agent.py` | EvolveAgent agentic loop (plan → act → observe → repeat) |
| `backend/utils/tools.py` | 11 LangChain tools (filesystem, Graph RAG, browser, validation) |
| `backend/utils/config.py` | Gemini-only provider config |
| `backend/utils/graph_rag.py` | Graph RAG (NetworkX + vector embeddings) |
| `backend/utils/memory.py` | Agent memory (rule extraction from conversations) |
| `backend/utils/extension_validator.py` | 4-layer Chrome extension validation |
| `evolve-extension/src/sidepanel/App.tsx` | React chat UI |
| `evolve-extension/src/background.ts` | Service worker (state, console capture) |
| `evolve-extension/src/content/` | DOM extraction + element highlighting |

---

## UI Requirements

### Sidepanel Chat (existing, polish)
- Provider dropdown showing "Gemini"
- Streaming tool call status (running/done indicators)
- Extension install cards with one-click load
- Agent memory panel (learned rules)

### Agent Observability (new)
- Real-time agent status indicators (which agent is active)
- Message flow visualization (Orchestrator → CodeGen → Validator)
- Before/after metrics panel (Graph RAG token savings, validation catches)

### Keyboard Shortcuts (new)
- `Cmd+Shift+E` — toggle sidepanel
- `Cmd+Enter` — send message
- `Cmd+K` — quick action menu
- Visual indicator showing available shortcuts

---

## Dev Commands

- **Backend:** `cd backend && uvicorn main:app --reload`
- **Extension:** `cd evolve-extension && npm run dev`
- **Build:** `cd evolve-extension && npm run build`

## Conventions

- Ask clarifying questions when necessary or if confused about implementation.
- When you start, create an entire implementation plan which should review absolutely everything about the app, organize ideas, PRD, identify where user review or interaction is required, and produce a full guide.
- After the implementation plan is approved, create the project root and begin building.

## Do / Don't

- **DO** build a real multi-agent architecture with discoverable agents
- **DO** package browser context tools as MCP server plugins
- **DO** use Chat Protocol for all Agentverse communication
- **DON'T** build a generic chatbot
- **DON'T** build a simple wrapper
- **DON'T** rewrite key files from scratch — wrap and extend them
