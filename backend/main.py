import asyncio
import json
import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from database import init_db, create_project, create_conversation, add_message
from utils.agent import EvolveAgent
from utils.tools import ALL_TOOLS, set_ws_bridge


class WebSocketBridge:
    """Manages all connected extension WebSocket clients and routes messages."""

    def __init__(self):
        self._connections: dict[str, WebSocket] = {}
        self._pending: dict[str, asyncio.Future] = {}
        self._clicked_elements: list[dict] = []
        self._console_logs: list[str] = []

    def connect(self, client_id: str, ws: WebSocket):
        self._connections[client_id] = ws

    def disconnect(self, client_id: str):
        self._connections.pop(client_id, None)

    async def request(self, request_type: str, payload: dict) -> dict:
        if not self._connections:
            raise RuntimeError("No browser extension connected")

        # Send to first connected client
        client_id = next(iter(self._connections))
        ws = self._connections[client_id]

        request_id = str(uuid.uuid4())
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending[request_id] = future

        await ws.send_json({
            "type": request_type,
            "request_id": request_id,
            **payload,
        })

        try:
            return await asyncio.wait_for(future, timeout=10.0)
        except asyncio.TimeoutError:
            del self._pending[request_id]
            raise RuntimeError(f"Browser did not respond to {request_type} within 10s")

    def resolve(self, request_id: str, data: dict):
        future = self._pending.pop(request_id, None)
        if future and not future.done():
            future.set_result(data)

    def record_clicked_element(self, element: dict):
        self._clicked_elements.append(element)
        if len(self._clicked_elements) > 50:
            self._clicked_elements = self._clicked_elements[-50:]

    def record_console_log(self, log: str):
        self._console_logs.append(log)
        if len(self._console_logs) > 200:
            self._console_logs = self._console_logs[-200:]

    def get_clicked_elements(self) -> list[dict]:
        return list(self._clicked_elements)

    def get_console_logs(self) -> list[str]:
        return list(self._console_logs)


ws_bridge = WebSocketBridge()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    set_ws_bridge(ws_bridge)
    yield


app = FastAPI(title="the-extension backend", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── REST Endpoints ──────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/projects")
async def list_projects():
    import aiosqlite
    from database import DB_PATH
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM projects ORDER BY created_at DESC") as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]


@app.get("/api/projects/{project_id}")
async def get_project(project_id: str):
    import aiosqlite
    from database import DB_PATH
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM projects WHERE id = ?", (project_id,)) as cur:
            row = await cur.fetchone()
    if not row:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Project not found")
    return dict(row)


@app.post("/api/chat")
async def chat(body: dict):
    prompt = body.get("prompt", "")
    project_id = body.get("project_id")
    context = body.get("context", "")

    if not project_id:
        project_id = await create_project(name=prompt[:40], path=f"/tmp/projects/{uuid.uuid4()}")

    conversation_id = await create_conversation(project_id)
    await add_message(conversation_id, "user", prompt)

    agent = EvolveAgent(project_id=project_id, tools=ALL_TOOLS)
    events = []
    async for event in agent.run(prompt, context=context):
        events.append(event.to_dict())
        if event.type == "content":
            await add_message(conversation_id, "assistant", event.data)

    return {"project_id": project_id, "conversation_id": conversation_id, "events": events}


# ── WebSocket Endpoint ──────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    client_id = str(uuid.uuid4())
    ws_bridge.connect(client_id, websocket)

    try:
        while True:
            raw = await websocket.receive_text()
            msg = json.loads(raw)
            msg_type = msg.get("type")

            if msg_type == "response":
                # Browser responding to a backend request
                ws_bridge.resolve(msg.get("request_id", ""), msg.get("data", {}))

            elif msg_type == "clicked_element":
                ws_bridge.record_clicked_element(msg.get("element", {}))

            elif msg_type == "console_log":
                ws_bridge.record_console_log(msg.get("log", ""))

            elif msg_type == "chat":
                # Streaming chat from the sidepanel
                prompt = msg.get("prompt", "")
                project_id = msg.get("project_id") or str(uuid.uuid4())
                context = msg.get("context", "")

                agent = EvolveAgent(project_id=project_id, tools=ALL_TOOLS)
                async for event in agent.run(prompt, context=context):
                    await websocket.send_json(event.to_dict())

    except WebSocketDisconnect:
        ws_bridge.disconnect(client_id)
