# Backend

This backend is the execution layer for the extension. Agentverse handles discovery and chat. FastAPI handles local work: project storage, generated extension files, Manifest V3 validation, ZIP packaging, and load instructions for Chrome.

## Setup

```bash
uv sync
```

Run the FastAPI server:

```bash
uv run main.py
```

Run the Agentverse/uAgents process in another terminal:

```bash
uv run python -m agentverse_app.main
```

Expose the uAgents endpoint when testing from Agentverse or ASI:One:

```bash
ngrok http 8001
```

## Runtime output

Generated extensions are written to:

```text
generated_extensions/{project_id}
```

Packaged ZIPs are written to:

```text
generated_extensions/_artifacts/{project_id}.zip
```

Both are local runtime artifacts and should stay out of git.