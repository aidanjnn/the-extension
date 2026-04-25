import asyncio
import re
from pathlib import Path
from typing import Any

from langchain_core.tools import tool

from utils.extension_validator import validate_extension as _validate_extension
from utils.graph_rag import CodeGraph

# Shared instances
_code_graph = CodeGraph()
_ws_bridge: Any = None  # set by main.py on startup


def set_ws_bridge(bridge):
    global _ws_bridge
    _ws_bridge = bridge


@tool
def create_file(path: str, content: str) -> str:
    """Write content to a file in the project directory, creating parent dirs if needed."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return f"Created {path} ({len(content)} bytes)"


@tool
def edit_file(path: str, old: str, new: str) -> str:
    """Find old text in a file and replace it with new text."""
    p = Path(path)
    if not p.exists():
        return f"Error: {path} does not exist"
    content = p.read_text()
    if old not in content:
        return f"Error: pattern not found in {path}"
    p.write_text(content.replace(old, new, 1))
    return f"Edited {path}"


@tool
def read_file(path: str) -> str:
    """Read and return the contents of a file."""
    p = Path(path)
    if not p.exists():
        return f"Error: {path} does not exist"
    return p.read_text()


@tool
def list_files(path: str = ".") -> str:
    """List files and directories at the given path."""
    p = Path(path)
    if not p.exists():
        return f"Error: {path} does not exist"
    entries = sorted(p.iterdir(), key=lambda x: (x.is_file(), x.name))
    return "\n".join(
        f"{'[dir]' if e.is_dir() else '[file]'} {e.name}" for e in entries
    )


@tool
def grep_search(pattern: str, path: str = ".") -> str:
    """Search for a regex pattern across files in the given path."""
    results = []
    root = Path(path)
    for file in root.rglob("*"):
        if not file.is_file():
            continue
        if any(p in str(file) for p in ["node_modules", "__pycache__", ".git", "dist"]):
            continue
        try:
            content = file.read_text(errors="ignore")
            for i, line in enumerate(content.splitlines(), 1):
                if re.search(pattern, line):
                    results.append(f"{file}:{i}: {line.strip()}")
        except Exception:
            continue
    return "\n".join(results[:50]) if results else "No matches found"


@tool
def codebase_search(query: str) -> str:
    """Semantic Graph RAG search across the codebase. Better than grep for intent-based queries."""
    results = _code_graph.search(query, top_k=5)
    if not results:
        return "No results found"
    parts = []
    for r in results:
        parts.append(f"[{r.node_type}] {r.file} (score: {r.score:.2f})\n{r.snippet}\n")
    metrics = _code_graph.get_metrics()
    parts.append(f"\n[Graph RAG] Nodes traversed: {metrics['nodes_traversed']}, Total nodes: {metrics['nodes_total']}")
    return "\n".join(parts)


@tool
def get_tab_content(tab_id: str = "active") -> str:
    """Fetch DOM content from the user's browser tab via WebSocket bridge."""
    if _ws_bridge is None:
        return "Error: WebSocket bridge not initialized"
    try:
        result = asyncio.get_event_loop().run_until_complete(
            _ws_bridge.request("get_tab_content", {"tab_id": tab_id})
        )
        return result.get("content", "No content returned")
    except Exception as e:
        return f"Error fetching tab content: {e}"


@tool
def get_console_logs(tab_id: str = "active") -> str:
    """Fetch browser console logs from the user's tab via WebSocket bridge."""
    if _ws_bridge is None:
        return "Error: WebSocket bridge not initialized"
    try:
        result = asyncio.get_event_loop().run_until_complete(
            _ws_bridge.request("get_console_logs", {"tab_id": tab_id})
        )
        logs = result.get("logs", [])
        return "\n".join(logs) if logs else "No console logs"
    except Exception as e:
        return f"Error fetching console logs: {e}"


@tool
def get_clicked_elements() -> str:
    """Retrieve CSS selectors and info for elements the user clicked in the browser."""
    if _ws_bridge is None:
        return "Error: WebSocket bridge not initialized"
    try:
        result = asyncio.get_event_loop().run_until_complete(
            _ws_bridge.request("get_clicked_elements", {})
        )
        elements = result.get("elements", [])
        if not elements:
            return "No elements selected (user has not clicked any elements)"
        return "\n".join(
            f"- {e['tag']} | selector: {e['selector']} | text: {e.get('text','')[:80]}"
            for e in elements
        )
    except Exception as e:
        return f"Error fetching clicked elements: {e}"


@tool
def validate_extension(project_path: str) -> str:
    """Run 4-layer validation on a Chrome extension directory. Returns errors and warnings."""
    root = Path(project_path)
    if not root.exists():
        return f"Error: {project_path} does not exist"

    files: dict[str, str] = {}
    for file in root.rglob("*"):
        if file.is_file():
            rel = str(file.relative_to(root))
            try:
                files[rel] = file.read_text(errors="ignore")
            except Exception:
                pass

    result = _validate_extension(files)
    lines = [f"Valid: {result.valid}"]
    if result.errors:
        lines.append("Errors:\n" + "\n".join(f"  - {e}" for e in result.errors))
    if result.warnings:
        lines.append("Warnings:\n" + "\n".join(f"  - {w}" for w in result.warnings))
    return "\n".join(lines)


@tool
def load_extension(project_path: str) -> str:
    """Trigger Chrome to reload the extension from the given path via WebSocket bridge."""
    if _ws_bridge is None:
        return "Error: WebSocket bridge not initialized"
    try:
        result = asyncio.get_event_loop().run_until_complete(
            _ws_bridge.request("load_extension", {"path": project_path})
        )
        return result.get("status", "Extension load triggered")
    except Exception as e:
        return f"Error loading extension: {e}"


ALL_TOOLS = [
    create_file,
    edit_file,
    read_file,
    list_files,
    grep_search,
    codebase_search,
    get_tab_content,
    get_console_logs,
    get_clicked_elements,
    validate_extension,
    load_extension,
]
