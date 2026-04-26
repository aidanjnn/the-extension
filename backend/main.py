from __future__ import annotations

import asyncio
import json
import logging
import re
import shutil
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from agentverse_app.config import settings as agentverse_settings
from agentverse_app.orchestrator import (
    create_build_request,
    run_orchestrator,
    stream_orchestrator_events,
)
from utils.companion import load_extension_via_os
from utils.config import get_secondary_client, get_secondary_model
from utils.db import (
    create_conversation,
    create_project,
    delete_project,
    delete_rule,
    get_messages,
    get_rules,
    init_db,
    list_conversations as db_list_conversations,
    list_projects as db_list_projects,
    save_message,
)
from utils.agentverse_execution import (
    ensure_project_workspace,
    get_project_load_info,
    package_project_extension,
    read_project_files,
    reset_project_workspace,
    validate_project_extension,
    write_project_files,
)
from utils.tools import DEMO_CODE_BASE

logger = logging.getLogger(__name__)


async def generate_conversation_title(
    user_message: str, assistant_message: str, provider: str = "gemini"
) -> str:
    """Generate a short conversation title from the first message exchange."""
    client = get_secondary_client(provider)
    model = get_secondary_model(provider)
    response = await client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (
                    "Generate a concise 3-6 word title for this conversation. "
                    "Return only the title text, nothing else. No quotes or punctuation at the end."
                ),
            },
            {
                "role": "user",
                "content": f"User: {user_message[:500]}\n\nAssistant: {assistant_message[:500]}",
            },
        ],
        max_completion_tokens=20,
        temperature=0.5,
    )
    return response.choices[0].message.content.strip()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    DEMO_CODE_BASE.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Models ---


class CreateProjectRequest(BaseModel):
    name: str


class Project(BaseModel):
    id: str
    name: str
    created_at: str


class ChatRequest(BaseModel):
    query: str
    project_id: str
    conversation_id: str | None = None


class ChatResponse(BaseModel):
    message: str
    conversation_id: str


class Conversation(BaseModel):
    id: str
    title: str | None = None
    created_at: str


class Message(BaseModel):
    role: str
    content: str
    created_at: str


class Rule(BaseModel):
    id: str
    content: str
    created_at: str


class AgentverseProjectRequest(BaseModel):
    project_id: str | None = None
    name: str = "Agentverse Extension"


class AgentverseProjectResponse(BaseModel):
    project_id: str
    extension_path: str


class AgentverseWriteFilesRequest(BaseModel):
    files: dict[str, str]


class AgentverseWriteFilesResponse(BaseModel):
    project_id: str
    written_files: list[str]


def require_agentverse_token(x_agentverse_token: str | None) -> None:
    expected = agentverse_settings.execution_api_token
    if expected and x_agentverse_token != expected:
        raise HTTPException(status_code=401, detail="Invalid Agentverse execution token")


# --- Project Routes ---


@app.post("/projects", response_model=Project)
async def create_project_route(request: CreateProjectRequest):
    project_id, created_at = await create_project(request.name)
    (DEMO_CODE_BASE / project_id).mkdir(parents=True, exist_ok=True)
    return Project(id=project_id, name=request.name, created_at=created_at)


@app.get("/projects", response_model=list[Project])
async def list_projects():
    rows = await db_list_projects()
    return [Project(**r) for r in rows]


@app.delete("/projects/{project_id}")
async def delete_project_route(project_id: str):
    deleted = await delete_project(project_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Project not found")
    workspace = DEMO_CODE_BASE / project_id
    if workspace.exists():
        shutil.rmtree(workspace)
    return {"ok": True}


# --- Public Extension Download ---


def _safe_filename(name: str, fallback: str) -> str:
    cleaned = re.sub(r"[^\w\s-]", "", name).strip()
    cleaned = re.sub(r"\s+", "_", cleaned)
    return cleaned or fallback


def _safe_identifier(value: str, *, label: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]{3,80}", value or ""):
        raise HTTPException(status_code=400, detail=f"Invalid {label}")
    return value


def _public_backend_base_url() -> str:
    return (agentverse_settings.public_backend_base_url or "http://localhost:8000").rstrip("/")


def _download_url_for_project(project_id: str) -> str:
    return f"{_public_backend_base_url()}/download/{project_id}.zip"


def _share_store_dir():
    share_dir = DEMO_CODE_BASE / "_shares"
    share_dir.mkdir(parents=True, exist_ok=True)
    return share_dir


def _share_path(share_id: str):
    safe_id = _safe_identifier(share_id, label="share id")
    return _share_store_dir() / f"{safe_id}.json"


def _share_url_for_id(share_id: str) -> str:
    return f"bf.link/{share_id}"


def _extract_share_id(code: str) -> str:
    raw = (code or "").strip()
    if not raw:
        raise HTTPException(status_code=400, detail="Share code is required")
    tokens = re.findall(r"[A-Za-z0-9_-]{6,80}", raw)
    candidate = tokens[-1] if tokens else raw
    return _safe_identifier(candidate, label="share code")


def _extension_name_from_files(files: dict[str, str], fallback: str) -> str:
    try:
        manifest = json.loads(files.get("manifest.json", "{}"))
    except json.JSONDecodeError:
        return fallback
    name = manifest.get("name") if isinstance(manifest, dict) else None
    return str(name or fallback)[:80]


def _read_share_payload(share_id: str) -> dict:
    path = _share_path(share_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Share code not found")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raise HTTPException(status_code=500, detail="Share payload is unreadable")
    if not isinstance(payload, dict) or payload.get("type") != "extension":
        raise HTTPException(status_code=400, detail="Unsupported share payload")
    return payload


def _materialize_share(share_id: str) -> ShareImportResponse:
    payload = _read_share_payload(share_id)
    files = payload.get("files")
    if not isinstance(files, dict) or "manifest.json" not in files:
        raise HTTPException(status_code=400, detail="Share payload has no extension files")
    clean_files = {
        str(path): str(content)
        for path, content in files.items()
        if isinstance(path, str) and isinstance(content, str)
    }
    project_id = f"sync_{uuid.uuid4().hex}"
    reset_project_workspace(project_id)
    write_project_files(project_id, clean_files)
    validation = validate_project_extension(project_id)
    if not validation.get("ok"):
        raise HTTPException(status_code=400, detail=validation)
    packaged = package_project_extension(project_id)
    name = str(payload.get("name") or _extension_name_from_files(clean_files, project_id))
    return ShareImportResponse(
        share_id=share_id,
        share_url=_share_url_for_id(share_id),
        project_id=project_id,
        name=name,
        extension_path=str(packaged["extension_path"]),
        zip_path=str(packaged["zip_path"]),
        download_url=_download_url_for_project(project_id),
        load_instructions=str(packaged["load_instructions"]),
    )


@app.get("/download/{project_id}.zip")
async def download_extension(project_id: str):
    """Public endpoint that serves the packaged extension zip.

    Used by ASI:One/Agentverse chat replies so users can download the
    generated extension directly. The downloaded file is renamed using the
    extension's manifest name (e.g. ``Hide_Instagram_Reels.zip``).
    """
    legacy_base = DEMO_CODE_BASE.parent / "demo_code"
    artifact_base = DEMO_CODE_BASE
    artifact = artifact_base / "_artifacts" / f"{project_id}.zip"
    if not artifact.exists():
        legacy_artifact = legacy_base / "_artifacts" / f"{project_id}.zip"
        if not legacy_artifact.exists():
            raise HTTPException(status_code=404, detail="Extension not found")
        artifact_base = legacy_base
        artifact = legacy_artifact

    display_name = project_id
    manifest_path = artifact_base / project_id / "manifest.json"
    if manifest_path.exists():
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            display_name = data.get("name", project_id) or project_id
        except (json.JSONDecodeError, OSError):
            pass

    return FileResponse(
        artifact,
        media_type="application/zip",
        filename=f"{_safe_filename(display_name, project_id)}.zip",
    )


# --- Extension Loading ---


class ClassifyItem(BaseModel):
    id: str
    text: str


class ClassifyRequest(BaseModel):
    filter_description: str
    items: list[ClassifyItem]
    provider: str = "gemini"


class ClassifyResponse(BaseModel):
    matches: list[str]


class DomEditOperationRequest(BaseModel):
    id: str
    kind: str
    selector: str
    url: str
    label: str | None = None
    order: int
    createdAt: int
    styles: dict[str, str] | None = None
    text: str | None = None
    description: str


class DomEditExportRequest(BaseModel):
    name: str = "the extension DOM edits"
    target_urls: list[str] = []
    operations: list[DomEditOperationRequest]


class DomEditExportResponse(BaseModel):
    project_id: str
    extension_path: str
    zip_path: str
    download_url: str
    load_instructions: str


class ShareProjectResponse(BaseModel):
    share_id: str
    share_url: str
    project_id: str
    name: str
    created_at: str


class ShareResolveResponse(BaseModel):
    share_id: str
    share_url: str
    source_project_id: str
    name: str
    created_at: str
    file_count: int


class ShareImportRequest(BaseModel):
    code: str


class ShareImportResponse(BaseModel):
    share_id: str
    share_url: str
    project_id: str
    name: str
    extension_path: str
    zip_path: str
    download_url: str
    load_instructions: str


@app.post("/api/classify", response_model=ClassifyResponse)
async def classify(req: ClassifyRequest):
    """Classify a batch of items against a user-supplied filter description.

    Used by generated browser extensions to do semantic content filtering
    (e.g. "show only sports videos") without hardcoded keyword lists.
    """
    import json as _json

    items = [item for item in req.items if item.text.strip()]
    if not items:
        return ClassifyResponse(matches=[])

    client = get_secondary_client(req.provider)
    model = get_secondary_model(req.provider)

    numbered = "\n".join(f"{i.id}: {i.text[:300]}" for i in items)
    system_prompt = (
        "You are a content filter. The user gives you a filter description and a list "
        "of items, each prefixed with an id and a colon. Return JSON: "
        '{"matches": ["id1", "id2", ...]} listing ONLY the ids whose content matches '
        "the filter description. Do not include any other text."
    )
    user_prompt = (
        f"Filter description: {req.filter_description}\n\n"
        f"Items:\n{numbered}\n\n"
        'Return JSON: {"matches": [...ids that match...]}'
    )

    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.0,
        )
    except Exception as exc:
        logger.warning("Classify call failed: %s", exc)
        return ClassifyResponse(matches=[])

    raw = (response.choices[0].message.content or "").strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:]
    try:
        parsed = _json.loads(raw)
    except _json.JSONDecodeError:
        import re as _re
        m = _re.search(r"\{.*\}", raw, _re.DOTALL)
        if not m:
            return ClassifyResponse(matches=[])
        try:
            parsed = _json.loads(m.group(0))
        except _json.JSONDecodeError:
            return ClassifyResponse(matches=[])

    matches_raw = parsed.get("matches") if isinstance(parsed, dict) else None
    if not isinstance(matches_raw, list):
        return ClassifyResponse(matches=[])
    valid_ids = {item.id for item in items}
    return ClassifyResponse(
        matches=[str(m) for m in matches_raw if str(m) in valid_ids]
    )


SAFE_DOM_STYLE_PROPERTIES = {
    "display",
    "opacity",
    "filter",
    "transform",
    "transform-origin",
    "outline",
    "outline-offset",
    "box-shadow",
    "background",
    "background-color",
    "color",
    "border",
    "border-radius",
    "overflow",
    "min-height",
    "max-height",
    "width",
    "min-width",
    "max-width",
    "margin",
    "margin-left",
    "margin-right",
    "margin-top",
    "margin-bottom",
    "padding",
}


def _safe_dom_style_value(value: str) -> str:
    return re.sub(r"[{};]", "", str(value)).strip()[:160]


def _target_urls_from_dom_request(req: DomEditExportRequest) -> list[str]:
    if req.target_urls:
        return req.target_urls
    origins: list[str] = []
    for op in req.operations:
        match = re.match(r"https?://[^/]+", op.url)
        if match and match.group(0) not in origins:
            origins.append(match.group(0))
    return [f"{origin}/*" for origin in origins] or ["<all_urls>"]


def _build_dom_edit_extension_files(req: DomEditExportRequest) -> dict[str, str]:
    operations: list[dict] = []
    for op in sorted(req.operations, key=lambda item: item.order):
        styles = {
            key: _safe_dom_style_value(value)
            for key, value in (op.styles or {}).items()
            if key in SAFE_DOM_STYLE_PROPERTIES and _safe_dom_style_value(value)
        }
        operations.append(
            {
                "id": op.id,
                "kind": op.kind,
                "selector": op.selector,
                "url": op.url,
                "label": op.label,
                "order": op.order,
                "styles": styles,
                "text": op.text[:500] if op.text else None,
                "description": op.description,
            }
        )

    name = _safe_filename(req.name, "the extension DOM Edits").replace("_", " ")[:45]
    manifest = {
        "manifest_version": 3,
        "name": name,
        "version": "1.0",
        "description": "Persistent DOM edits exported from the extension.",
        "content_scripts": [
            {
                "matches": _target_urls_from_dom_request(req),
                "js": ["content.js"],
                "css": ["content.css"],
                "run_at": "document_idle",
            }
        ],
    }
    content_js = f"""
const OPERATIONS = {json.dumps(operations, indent=2)};
let rafToken = 0;

function applyOperation(operation) {{
  if (!operation || !operation.selector) return;
  let nodes = [];
  try {{
    nodes = Array.from(document.querySelectorAll(operation.selector));
  }} catch {{
    return;
  }}
  for (const node of nodes) {{
    if (!(node instanceof HTMLElement)) continue;
    if (operation.kind === 'hide') {{
      node.style.setProperty('display', 'none', 'important');
    }}
    if (operation.kind === 'text' && typeof operation.text === 'string') {{
      node.textContent = operation.text;
    }}
    const styles = operation.styles || {{}};
    for (const [property, value] of Object.entries(styles)) {{
      if (!value) continue;
      node.style.setProperty(property, String(value), 'important');
    }}
  }}
}}

function applyAll() {{
  for (const operation of OPERATIONS) {{
    applyOperation(operation);
  }}
}}

function scheduleApply() {{
  if (rafToken) cancelAnimationFrame(rafToken);
  rafToken = requestAnimationFrame(() => {{
    rafToken = 0;
    applyAll();
  }});
}}

if (document.readyState === 'loading') {{
  document.addEventListener('DOMContentLoaded', applyAll, {{ once: true }});
}} else {{
  applyAll();
}}

const root = document.documentElement || document.body;
if (root) {{
  new MutationObserver(scheduleApply).observe(root, {{ childList: true, subtree: true }});
}}
window.addEventListener('popstate', scheduleApply);
window.addEventListener('hashchange', scheduleApply);
""".strip()
    content_css = """
/* the extension DOM edits are applied inline by content.js so they win over page styles. */
""".strip()
    return {
        "manifest.json": json.dumps(manifest, indent=2),
        "content.js": content_js,
        "content.css": content_css,
    }


@app.post("/api/dom-edits/export", response_model=DomEditExportResponse)
async def export_dom_edits(req: DomEditExportRequest):
    if not req.operations:
        raise HTTPException(status_code=400, detail="No DOM edits to export")
    project_id = f"dom_{uuid.uuid4().hex}"
    files = _build_dom_edit_extension_files(req)
    reset_project_workspace(project_id)
    write_project_files(project_id, files)
    packaged = package_project_extension(project_id)
    base_url = agentverse_settings.public_backend_base_url or "http://localhost:8000"
    download_url = f"{base_url.rstrip('/')}/download/{project_id}.zip"
    return DomEditExportResponse(
        project_id=project_id,
        extension_path=str(packaged["extension_path"]),
        zip_path=str(packaged["zip_path"]),
        download_url=download_url,
        load_instructions=str(packaged["load_instructions"]),
    )


@app.post("/api/share/project/{project_id}", response_model=ShareProjectResponse)
async def share_project(project_id: str):
    project_id = _safe_identifier(project_id, label="project id")
    project_dir = DEMO_CODE_BASE / project_id
    if not (project_dir / "manifest.json").exists():
        raise HTTPException(status_code=404, detail="Project extension not found")
    files = read_project_files(project_id)
    if "manifest.json" not in files or "content.js" not in files:
        raise HTTPException(status_code=400, detail="Project is not a shareable extension")

    share_id = uuid.uuid4().hex[:10]
    created_at = datetime.now(timezone.utc).isoformat()
    name = _extension_name_from_files(files, project_id)
    payload = {
        "version": 1,
        "type": "extension",
        "share_id": share_id,
        "source_project_id": project_id,
        "name": name,
        "created_at": created_at,
        "files": files,
    }
    _share_path(share_id).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return ShareProjectResponse(
        share_id=share_id,
        share_url=_share_url_for_id(share_id),
        project_id=project_id,
        name=name,
        created_at=created_at,
    )


@app.get("/api/share/{share_id}", response_model=ShareResolveResponse)
async def resolve_share(share_id: str):
    share_id = _safe_identifier(share_id, label="share id")
    payload = _read_share_payload(share_id)
    files = payload.get("files") if isinstance(payload.get("files"), dict) else {}
    return ShareResolveResponse(
        share_id=share_id,
        share_url=_share_url_for_id(share_id),
        source_project_id=str(payload.get("source_project_id") or ""),
        name=str(payload.get("name") or share_id),
        created_at=str(payload.get("created_at") or ""),
        file_count=len(files),
    )


@app.post("/api/share/{share_id}/materialize", response_model=ShareImportResponse)
async def materialize_share(share_id: str):
    share_id = _safe_identifier(share_id, label="share id")
    return _materialize_share(share_id)


@app.post("/api/share/import", response_model=ShareImportResponse)
async def import_share(req: ShareImportRequest):
    share_id = _extract_share_id(req.code)
    return _materialize_share(share_id)


@app.post("/api/load-extension/{project_id}")
async def api_load_extension(project_id: str):
    """Trigger OS automation to load the extension into Chrome."""
    project_dir = DEMO_CODE_BASE / project_id
    if not project_dir.exists():
        raise HTTPException(status_code=404, detail="Project not found")
    manifest = project_dir / "manifest.json"
    if not manifest.exists():
        raise HTTPException(
            status_code=400,
            detail="No manifest.json found in the project workspace.",
        )
    extension_path = str(project_dir.resolve())
    result = await load_extension_via_os(extension_path)
    return result


# --- Agentverse Execution API ---


@app.post("/internal/agentverse/projects", response_model=AgentverseProjectResponse)
async def agentverse_create_project(
    request: AgentverseProjectRequest,
    x_agentverse_token: str | None = Header(default=None),
):
    require_agentverse_token(x_agentverse_token)
    if request.project_id:
        project_id = request.project_id
        project_dir = ensure_project_workspace(project_id)
    else:
        project_id, _ = await create_project(request.name)
        project_dir = ensure_project_workspace(project_id)
    return AgentverseProjectResponse(
        project_id=project_id,
        extension_path=str(project_dir),
    )


@app.post(
    "/internal/agentverse/projects/{project_id}/files",
    response_model=AgentverseWriteFilesResponse,
)
async def agentverse_write_files(
    project_id: str,
    request: AgentverseWriteFilesRequest,
    x_agentverse_token: str | None = Header(default=None),
):
    require_agentverse_token(x_agentverse_token)
    reset_project_workspace(project_id)
    written = write_project_files(project_id, request.files)
    return AgentverseWriteFilesResponse(project_id=project_id, written_files=written)


@app.get("/internal/agentverse/projects/{project_id}/files")
async def agentverse_read_files(
    project_id: str,
    x_agentverse_token: str | None = Header(default=None),
):
    require_agentverse_token(x_agentverse_token)
    return {"project_id": project_id, "files": read_project_files(project_id)}


@app.post("/internal/agentverse/projects/{project_id}/validate")
async def agentverse_validate_project(
    project_id: str,
    x_agentverse_token: str | None = Header(default=None),
):
    require_agentverse_token(x_agentverse_token)
    return validate_project_extension(project_id)


@app.post("/internal/agentverse/projects/{project_id}/package")
async def agentverse_package_project(
    project_id: str,
    x_agentverse_token: str | None = Header(default=None),
):
    require_agentverse_token(x_agentverse_token)
    return package_project_extension(project_id)


@app.post("/internal/agentverse/projects/{project_id}/load-info")
async def agentverse_load_info(
    project_id: str,
    x_agentverse_token: str | None = Header(default=None),
):
    require_agentverse_token(x_agentverse_token)
    return get_project_load_info(project_id)


# --- Chat Routes ---


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    if request.conversation_id:
        conv_id = request.conversation_id
    else:
        conv_id, _ = await create_conversation(request.project_id)

    await save_message(conv_id, "user", request.query)

    build = create_build_request(
        query=request.query,
        project_id=request.project_id,
        source="sidepanel",
    )
    result = await run_orchestrator(build)
    assistant_msg = result.final_message

    await save_message(conv_id, "assistant", assistant_msg)

    return ChatResponse(message=assistant_msg, conversation_id=conv_id)


@app.websocket("/ws/{project_id}")
async def ws_chat(websocket: WebSocket, project_id: str):
    await websocket.accept()

    # Shared across all chat turns on this connection
    pending_tab_requests: dict[str, asyncio.Future] = {}
    # Queue for incoming FE messages (tab_content_response, etc.) while the
    # agent is streaming.  A background listener task fills this queue.
    incoming: asyncio.Queue[dict] = asyncio.Queue()

    async def _listen_for_responses():
        """Read WS messages and route them: chat messages go on `incoming`,
        tab_content_response resolves the matching Future directly."""
        try:
            while True:
                data = await websocket.receive_json()
                msg_type = data.get("type")

                if msg_type == "tab_content_response":
                    rid = data.get("request_id")
                    content = data.get("content", "")
                    fut = pending_tab_requests.pop(rid, None)
                    if fut and not fut.done():
                        fut.set_result(content)
                elif msg_type == "console_logs_response":
                    rid = data.get("request_id")
                    content = data.get("content", "")
                    fut = pending_tab_requests.pop(rid, None)
                    if fut and not fut.done():
                        fut.set_result(content)
                else:
                    await incoming.put(data)
        except WebSocketDisconnect:
            await incoming.put({"type": "_disconnect"})

    listener = asyncio.create_task(_listen_for_responses())

    try:
        while True:
            data = await incoming.get()
            if data.get("type") == "_disconnect":
                break
            if data.get("type") != "chat":
                continue

            query = data["query"]
            conversation_id = data.get("conversation_id")
            active_tabs = data.get("active_tabs")
            provider = data.get("provider", "gemini")

            if conversation_id:
                conv_id = conversation_id
            else:
                conv_id, _ = await create_conversation(project_id)

            await save_message(conv_id, "user", query)

            # Let the client know the conversation id first
            await websocket.send_json(
                {"type": "conversation_id", "conversation_id": conv_id}
            )

            collected: list[str] = []
            try:
                build = create_build_request(
                    query=query,
                    project_id=project_id,
                    provider=provider,
                    source="sidepanel",
                    active_tabs=active_tabs,
                )
                async for event in stream_orchestrator_events(build):
                    if event["type"] == "content":
                        collected.append(event["content"])
                    await websocket.send_json(event)

                content = "".join(collected)
                await save_message(conv_id, "assistant", content)
                await websocket.send_json(
                    {
                        "type": "done",
                        "conversation_id": conv_id,
                        "content": content,
                    }
                )

            except WebSocketDisconnect:
                break
            except Exception as exc:
                logger.exception("Error during agent streaming")
                try:
                    await websocket.send_json(
                        {"type": "error", "message": str(exc)}
                    )
                except Exception:
                    break
    finally:
        listener.cancel()


# --- Conversation Routes ---


@app.get("/projects/{project_id}/conversations", response_model=list[Conversation])
async def list_conversations(project_id: str):
    rows = await db_list_conversations(project_id)
    return [Conversation(**r) for r in rows]


@app.get("/conversations/{conversation_id}", response_model=list[Message])
async def get_conversation(conversation_id: str):
    rows = await get_messages(conversation_id)
    return [Message(**r) for r in rows]


# --- Rules Routes ---


@app.get("/projects/{project_id}/rules", response_model=list[Rule])
async def list_rules(project_id: str):
    rows = await get_rules(project_id)
    return [Rule(**r) for r in rows]


@app.delete("/rules/{rule_id}")
async def delete_rule_route(rule_id: str):
    deleted = await delete_rule(rule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Rule not found")
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
