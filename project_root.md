# Project Root — Implementation Plan

> **Goal:** Scaffold the entire `the-extension` monorepo so every file, folder, config, and boilerplate exists for the team to split tasks and code in parallel. After this plan is executed the project should **run** (backend serves, extension builds) even though business logic is stubbed.

---

## 1. Repo Structure (Full File Tree)

```
the-extension/
├── CLAUDE.md                          # ✅ exists
├── README.md                          # ✅ exists (update)
├── project_root.md                    # ✅ this file
├── .env.example                       # [NEW] env var template
├── .gitignore                         # [NEW] Python + Node ignores
│
├── backend/                           # Python — FastAPI + Agents
│   ├── requirements.txt               # [NEW] all pip deps
│   ├── main.py                        # [NEW] FastAPI app, REST + WS
│   ├── database.py                    # [NEW] SQLite setup + helpers
│   ├── schema.sql                     # [NEW] raw DDL for reference
│   │
│   ├── agents/                        # Fetch.ai uAgents
│   │   ├── __init__.py
│   │   ├── models.py                  # [NEW] shared uAgent Model classes
│   │   ├── orchestrator.py            # [NEW] Orchestrator Agent
│   │   ├── codegen.py                 # [NEW] CodeGen Agent
│   │   ├── validator.py               # [NEW] Validator Agent
│   │   └── browser_context.py         # [NEW] BrowserContext Agent
│   │
│   ├── mcp/                           # MCP server (Cognition track)
│   │   ├── __init__.py
│   │   └── server.py                  # [NEW] MCP tool definitions
│   │
│   └── utils/                         # Core business logic
│       ├── __init__.py
│       ├── config.py                  # [NEW] Gemini provider config
│       ├── agent.py                   # [NEW] EvolveAgent agentic loop
│       ├── tools.py                   # [NEW] 11 LangChain tools
│       ├── graph_rag.py               # [NEW] NetworkX + embeddings
│       ├── memory.py                  # [NEW] agent memory / rules
│       └── extension_validator.py     # [NEW] 4-layer validator
│
├── extension/                         # Chrome Extension — React + TS
│   ├── package.json                   # [NEW] deps + scripts
│   ├── tsconfig.json                  # [NEW] TypeScript config
│   ├── vite.config.ts                 # [NEW] Vite + CRXJS
│   ├── manifest.json                  # [NEW] MV3 Chrome manifest
│   │
│   ├── public/
│   │   └── icons/
│   │       ├── icon16.png             # [NEW] placeholder
│   │       ├── icon48.png             # [NEW] placeholder
│   │       └── icon128.png            # [NEW] placeholder
│   │
│   └── src/
│       ├── background.ts             # [NEW] service worker
│       ├── sidepanel/
│       │   ├── index.html             # [NEW] sidepanel entry
│       │   ├── index.tsx              # [NEW] React mount
│       │   ├── App.tsx                # [NEW] main chat UI
│       │   └── App.css                # [NEW] sidepanel styles
│       ├── content/
│       │   ├── content.ts             # [NEW] DOM extraction
│       │   ├── highlighter.ts         # [NEW] click-to-select overlay
│       │   └── content.css            # [NEW] highlight styles
│       └── types/
│           └── messages.ts            # [NEW] TS message interfaces
│
└── docs/                              # Supplementary docs
    └── architecture.md                # [NEW] system diagram in Mermaid
```

---

## 2. Proposed Changes — File by File

### 2.1 Root Config Files

#### [NEW] `.env.example`
```env
GOOGLE_API_KEY=your-gemini-key
ORCHESTRATOR_AGENT_SEED=orchestrator-seed-phrase
CODEGEN_AGENT_SEED=codegen-seed-phrase
VALIDATOR_AGENT_SEED=validator-seed-phrase
BROWSER_CONTEXT_AGENT_SEED=browser-context-seed-phrase
```

#### [NEW] `.gitignore`
Standard Python + Node ignores: `__pycache__`, `node_modules`, `dist`, `.env`, `*.db`, `venv/`, etc.

#### [MODIFY] `README.md`
Replace the single-line placeholder with a proper project overview: name, one-liner, quickstart (backend + extension), env var setup, and link to `CLAUDE.md` for full spec.

---

### 2.2 Backend — FastAPI Core

#### [NEW] `backend/requirements.txt`
```
fastapi>=0.110
uvicorn[standard]>=0.29
websockets>=12.0
langchain>=0.2
langchain-google-genai>=1.0
google-generativeai>=0.5
networkx>=3.3
numpy>=1.26
aiosqlite>=0.20
python-dotenv>=1.0
uagents>=0.14
mcp>=1.0
```

#### [NEW] `backend/main.py`
- `FastAPI()` app instance
- **REST endpoints:**
  - `POST /api/chat` — create conversation / send message
  - `GET /api/projects` — list projects
  - `GET /api/projects/{id}` — get project + files
  - `GET /api/health` — healthcheck
- **WebSocket endpoint:**
  - `WS /ws` — bidirectional streaming (browser ↔ backend)
  - Handles message types: `chat`, `tab_content`, `console_logs`, `clicked_element`
- CORS middleware allowing Chrome extension origin
- Lifespan handler: init DB, start agent bureau on startup

#### [NEW] `backend/database.py`
- `init_db()` — creates tables from `schema.sql` if not exists
- Helper functions: `create_project()`, `create_conversation()`, `add_message()`, `get_rules()`, `save_rule()`

#### [NEW] `backend/schema.sql`
```sql
CREATE TABLE IF NOT EXISTS projects (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    path        TEXT NOT NULL,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS conversations (
    id          TEXT PRIMARY KEY,
    project_id  TEXT NOT NULL REFERENCES projects(id),
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS messages (
    id              TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id),
    role            TEXT NOT NULL CHECK(role IN ('user','assistant','tool')),
    content         TEXT NOT NULL,
    tool_name       TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS rules (
    id          TEXT PRIMARY KEY,
    project_id  TEXT NOT NULL REFERENCES projects(id),
    content     TEXT NOT NULL,
    source      TEXT,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

### 2.3 Backend — Utils (Core Logic)

#### [NEW] `backend/utils/__init__.py`
Empty init.

#### [NEW] `backend/utils/config.py`
- Load `GOOGLE_API_KEY` from env
- Export `get_llm()` → returns `ChatGoogleGenerativeAI(model="gemini-2.5-flash")`
- Export `get_embeddings()` → returns `GoogleGenerativeAIEmbeddings(model="text-embedding-004")`
- Fallback model constant: `FALLBACK_MODEL = "gemini-2.0-flash"`

#### [NEW] `backend/utils/agent.py`
- `EvolveAgent` class — the agentic loop:
  - `__init__(project_id, tools, llm)` 
  - `async run(prompt, context) -> AsyncGenerator[StreamEvent]` — plan → act → observe → repeat
  - `StreamEvent` dataclass with types: `content`, `tool_start`, `tool_end`, `thinking`, `error`, `done`
  - Max iterations guard (default 10)
  - Integrates agent memory (rules) into system prompt

#### [NEW] `backend/utils/tools.py`
- 11 LangChain `@tool` functions, each stubbed with docstring + signature:
  1. `create_file(path, content)` — write file to project dir
  2. `edit_file(path, old, new)` — find-and-replace in file
  3. `read_file(path)` — read file contents
  4. `list_files(path)` — list directory
  5. `grep_search(pattern, path)` — ripgrep-style search
  6. `codebase_search(query)` — Graph RAG semantic search
  7. `get_tab_content(tab_id)` — fetch DOM from browser via WS
  8. `get_console_logs(tab_id)` — fetch console logs via WS
  9. `get_clicked_elements()` — get user-selected elements
  10. `validate_extension(project_path)` — run 4-layer validator
  11. `load_extension(project_path)` — trigger chrome extension reload

#### [NEW] `backend/utils/graph_rag.py`
- `CodeGraph` class:
  - `build_graph(directory)` — parse files, extract entities, build NetworkX graph
  - `index_embeddings(entities)` — generate vector embeddings via Gemini
  - `search(query, top_k)` — embed query → BFS traversal → re-rank → return results
  - `get_metrics()` — return search stats for observability (tokens used, nodes traversed)

#### [NEW] `backend/utils/memory.py`
- `AgentMemory` class:
  - `extract_rules(conversation)` — use LLM to extract reusable rules
  - `get_rules(project_id)` — fetch from DB
  - `format_rules_prompt(rules)` — format for system prompt injection

#### [NEW] `backend/utils/extension_validator.py`
- `validate_extension(files: dict[str, str]) -> ValidatorResult`:
  - **Layer 1:** `validate_manifest()` — required fields, valid structure
  - **Layer 2:** `validate_file_references()` — all content_scripts/popup files exist in `files` dict
  - **Layer 3:** `validate_js_syntax()` — basic JS/TS syntax check (regex + ast-level)
  - **Layer 4:** `validate_mv3_compat()` — scan for deprecated `chrome.` APIs (MV2 patterns)
- Returns `ValidatorResult(valid, errors, warnings)`

---

### 2.4 Backend — Agents (Fetch.ai)

#### [NEW] `backend/agents/__init__.py`
Empty init.

#### [NEW] `backend/agents/models.py`
All shared uAgent Model classes (copy from CLAUDE.md message models section):
`ExtensionRequest`, `CodeGenRequest`, `CodeGenResponse`, `ValidateRequest`, `ValidateResponse`, `ExtensionResponse`

#### [NEW] `backend/agents/orchestrator.py`
- Create `Agent(name="orchestrator", seed=ORCHESTRATOR_AGENT_SEED)`
- Register Chat Protocol handler
- `on_message(ExtensionRequest)`:
  1. Plan extension file structure
  2. Send `CodeGenRequest` to CodeGen agent
  3. Receive `CodeGenResponse`
  4. Send `ValidateRequest` to Validator agent
  5. If invalid → re-send to CodeGen with `fix_errors`
  6. Max 3 retry loops
  7. Return `ExtensionResponse`

#### [NEW] `backend/agents/codegen.py`
- Create `Agent(name="codegen", seed=CODEGEN_AGENT_SEED)`
- `on_message(CodeGenRequest)`:
  1. Build prompt with extension requirements + any `fix_errors`
  2. Optionally include `browser_context`
  3. Call Gemini LLM
  4. Parse response into `files` dict
  5. Return `CodeGenResponse`

#### [NEW] `backend/agents/validator.py`
- Create `Agent(name="validator", seed=VALIDATOR_AGENT_SEED)`
- `on_message(ValidateRequest)`:
  1. Run `extension_validator.validate_extension(files)`
  2. Return `ValidateResponse(valid, errors, warnings)`

#### [NEW] `backend/agents/browser_context.py`
- Create `Agent(name="browser_context", seed=BROWSER_CONTEXT_AGENT_SEED)`
- Bridges WebSocket data from `main.py` to agent protocol
- Responds to requests for DOM content, console logs, clicked elements

---

### 2.5 Backend — MCP Server

#### [NEW] `backend/mcp/__init__.py`
Empty init.

#### [NEW] `backend/mcp/server.py`
- MCP server exposing 3 tools:
  - `get_tab_content(tab_id?) -> str` — returns DOM/text
  - `get_console_logs(tab_id?) -> list[str]` — returns console output
  - `get_clicked_elements() -> list[dict]` — returns `{selector, tag, text, attributes}`
- Transport: stdio (standard MCP pattern)
- Each tool calls into the backend WebSocket bridge

---

### 2.6 Chrome Extension

#### [NEW] `extension/package.json`
```json
{
  "name": "the-extension",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.3.0",
    "react-dom": "^18.3.0"
  },
  "devDependencies": {
    "@crxjs/vite-plugin": "^2.0.0-beta.25",
    "@types/chrome": "^0.0.268",
    "@types/react": "^18.3.0",
    "@types/react-dom": "^18.3.0",
    "typescript": "^5.4.0",
    "vite": "^5.4.0",
    "@vitejs/plugin-react": "^4.3.0"
  }
}
```

#### [NEW] `extension/manifest.json`
```json
{
  "manifest_version": 3,
  "name": "the extension",
  "version": "0.1.0",
  "description": "AI-powered Chrome extension builder",
  "permissions": ["sidePanel", "activeTab", "scripting", "storage", "tabs"],
  "side_panel": {
    "default_path": "src/sidepanel/index.html"
  },
  "background": {
    "service_worker": "src/background.ts",
    "type": "module"
  },
  "content_scripts": [{
    "matches": ["<all_urls>"],
    "js": ["src/content/content.ts"],
    "css": ["src/content/content.css"]
  }],
  "commands": {
    "_execute_action": {
      "suggested_key": { "default": "Ctrl+Shift+E", "mac": "MacCtrl+Shift+E" },
      "description": "Toggle sidepanel"
    },
    "send_message": {
      "suggested_key": { "default": "Ctrl+Enter", "mac": "Command+Enter" },
      "description": "Send message"
    },
    "quick_actions": {
      "suggested_key": { "default": "Ctrl+K", "mac": "Command+K" },
      "description": "Quick action menu"
    }
  },
  "icons": {
    "16": "public/icons/icon16.png",
    "48": "public/icons/icon48.png",
    "128": "public/icons/icon128.png"
  }
}
```

#### [NEW] `extension/vite.config.ts`
- Import `crx` from `@crxjs/vite-plugin`
- Import `manifest.json`
- Configure React plugin + CRXJS plugin
- Set `build.outDir` to `dist`

#### [NEW] `extension/tsconfig.json`
Standard React + TS config targeting `ES2020`, JSX `react-jsx`, strict mode.

#### [NEW] `extension/src/background.ts`
- Service worker:
  - Listen for `chrome.sidePanel.open()` command
  - Maintain WebSocket connection to `ws://localhost:8000/ws`
  - Capture console logs from tabs via `chrome.debugger` API
  - Relay messages between content scripts and backend
  - Store state in `chrome.storage.local`

#### [NEW] `extension/src/sidepanel/index.html`
Minimal HTML with `<div id="root">` and script tag pointing to `index.tsx`.

#### [NEW] `extension/src/sidepanel/index.tsx`
React 18 `createRoot` mount.

#### [NEW] `extension/src/sidepanel/App.tsx`
- Main chat UI component:
  - Message list (user + assistant bubbles)
  - Input box with send button
  - Streaming tool call indicators (tool name + running/done)
  - Extension install card (download button)
  - Agent status bar (which agent is active)
  - Provider badge ("Gemini")
- State: messages, isLoading, activeAgent, toolCalls

#### [NEW] `extension/src/sidepanel/App.css`
- Dark theme, modern design
- Chat bubble styles, tool status indicators
- Agent observability bar styles

#### [NEW] `extension/src/content/content.ts`
- DOM extraction: `getPageContent()` → serialized DOM text
- Click-to-select mode:
  - Listen for activation message from background
  - On hover → highlight element with overlay
  - On click → capture CSS selector, tag, text, attributes → send to background

#### [NEW] `extension/src/content/highlighter.ts`
- `ElementHighlighter` class:
  - `activate()` / `deactivate()`
  - Adds hover overlay (border + label showing selector)
  - Returns `SelectedElement` on click

#### [NEW] `extension/src/content/content.css`
Highlight overlay styles (border, background tint, selector label tooltip).

#### [NEW] `extension/src/types/messages.ts`
TypeScript interfaces for all WebSocket message types:
`ChatMessage`, `TabContent`, `ConsoleLogs`, `ClickedElement`, `StreamEvent`, `ToolStatus`

#### [NEW] `extension/public/icons/icon16.png`, `icon48.png`, `icon128.png`
Generated placeholder icons (simple colored squares or "TE" text icons).

---

### 2.7 Documentation

#### [NEW] `docs/architecture.md`
Mermaid diagram of the full system:
- Multi-agent data flow (Orchestrator → CodeGen → Validator → BrowserContext)
- Browser ↔ WebSocket ↔ FastAPI pipeline
- MCP server integration point

---

## 3. Implementation Order

This is the exact order files should be created to minimize broken imports:

| Step | Files | Why first |
|---|---|---|
| 1 | `.env.example`, `.gitignore` | Prevent secrets + junk from leaking |
| 2 | `backend/requirements.txt` | Pin deps before any Python code |
| 3 | `backend/schema.sql`, `backend/database.py` | DB is the foundation |
| 4 | `backend/utils/__init__.py`, `config.py` | Everything imports config |
| 5 | `backend/utils/extension_validator.py` | No deps beyond stdlib |
| 6 | `backend/utils/graph_rag.py` | Depends on config (embeddings) |
| 7 | `backend/utils/memory.py` | Depends on config + database |
| 8 | `backend/utils/tools.py` | Depends on all utils above |
| 9 | `backend/utils/agent.py` | Depends on tools + config |
| 10 | `backend/agents/models.py` | Shared models, no deps |
| 11 | `backend/agents/orchestrator.py`, `codegen.py`, `validator.py`, `browser_context.py` | Depend on models + utils |
| 12 | `backend/mcp/server.py` | Depends on WS bridge in main |
| 13 | `backend/main.py` | Imports everything above |
| 14 | `extension/package.json`, `tsconfig.json`, `vite.config.ts`, `manifest.json` | Extension config first |
| 15 | `extension/src/types/messages.ts` | Shared types |
| 16 | `extension/src/content/*` | Content scripts (no React dep) |
| 17 | `extension/src/background.ts` | Service worker |
| 18 | `extension/src/sidepanel/*` | React UI (depends on types) |
| 19 | Icons + `docs/architecture.md` | Polish |
| 20 | `README.md` update | Final |

---

## 4. Verification Plan

### Automated Checks

1. **Backend starts without crash:**
   ```bash
   cd backend && pip install -r requirements.txt && python -c "from main import app; print('OK')"
   ```
2. **Database initializes:**
   ```bash
   cd backend && python -c "import asyncio; from database import init_db; asyncio.run(init_db()); print('DB OK')"
   ```
3. **Extension builds:**
   ```bash
   cd extension && npm install && npm run build
   ```
4. **Validator runs standalone:**
   ```bash
   cd backend && python -c "
   from utils.extension_validator import validate_extension
   result = validate_extension({'manifest.json': '{\"manifest_version\":3,\"name\":\"test\",\"version\":\"1.0\"}'})
   print(result)
   "
   ```
5. **Agent models import cleanly:**
   ```bash
   cd backend && python -c "from agents.models import ExtensionRequest, CodeGenRequest, ValidateRequest; print('Models OK')"
   ```

### Manual Verification

1. **Backend server runs:** `cd backend && uvicorn main:app --reload` → visit `http://localhost:8000/api/health` → expect `{"status": "ok"}`
2. **Extension loads in Chrome:** Go to `chrome://extensions` → Enable Developer Mode → Load Unpacked → select `extension/dist/` → confirm sidepanel opens
3. **WebSocket connects:** Open sidepanel → check browser DevTools console for `WebSocket connected` log

---

## 5. What Needs User Input

> [!IMPORTANT]
> **Before building, confirm:**
> 1. Is the extension folder name `extension/` OK, or do you want `evolve-extension/` (as in `CLAUDE.md` key files table)?
> 2. Should I generate real icons (via image generation), or use simple placeholder PNGs?
> 3. Should I `npm install` and `pip install` as part of execution, or leave that to you?
