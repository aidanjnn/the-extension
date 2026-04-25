# System Architecture

## Multi-Agent Data Flow (Fetch.ai Track)

```mermaid
graph TD
    User["User via ASI:One"] -->|ExtensionRequest| Orch["Orchestrator Agent\n(Agentverse, Chat Protocol)"]
    Orch -->|CodeGenRequest| CG["CodeGen Agent\n(Gemini LLM)"]
    CG -->|optional| BC["BrowserContext Agent\n(WebSocket Bridge)"]
    BC -->|DOM/logs/elements| CG
    CG -->|CodeGenResponse| Orch
    Orch -->|ValidateRequest| Val["Validator Agent\n(4-layer validation)"]
    Val -->|ValidateResponse invalid| Orch
    Orch -->|CodeGenRequest + fix_errors| CG
    Val -->|ValidateResponse valid| Orch
    Orch -->|ExtensionResponse| User
```

## Browser ↔ Backend Pipeline (Cognition Track)

```mermaid
graph LR
    Sidepanel["Chrome Sidepanel\n(React UI)"] <-->|WebSocket /ws| Backend["FastAPI Backend\n(localhost:8000)"]
    Content["Content Script"] -->|clicked elements| BG["Background Service Worker"]
    BG <-->|WebSocket /ws| Backend
    Backend --> EvolveAgent["EvolveAgent\n(agentic loop)"]
    EvolveAgent --> Tools["11 LangChain Tools"]
    Tools --> GraphRAG["Graph RAG\n(NetworkX + Gemini embeddings)"]
    Tools --> Validator["Extension Validator\n(4-layer)"]
    Tools --> BrowserTools["Browser Tools\n(tab content, console, elements)"]
    BrowserTools <-->|WS Bridge| BG
```

## MCP Server Integration

```mermaid
graph LR
    Agent["AI Coding Agent\n(Devin, Cursor, etc.)"] -->|MCP stdio| MCP["MCP Server\n(backend/mcp/server.py)"]
    MCP --> WSBridge["WebSocket Bridge"]
    WSBridge <-->|ws| Extension["Chrome Extension"]
    Extension -->|get_tab_content| DOM["Live DOM"]
    Extension -->|get_console_logs| Logs["Console Logs"]
    Extension -->|get_clicked_elements| Elements["Selected Elements"]
```

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Chrome Extension (React + TypeScript + Vite + CRXJS) |
| Backend | Python (FastAPI + WebSocket) |
| Agents | Fetch.ai uAgents SDK (Agentverse) |
| LLM | Google Gemini (`gemini-2.5-flash`) |
| Search | Graph RAG (NetworkX + `text-embedding-004`) |
| Plugins | MCP server (stdio transport) |
| Database | SQLite (aiosqlite) |
