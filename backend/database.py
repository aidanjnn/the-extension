import uuid
import aiosqlite
from pathlib import Path

DB_PATH = Path(__file__).parent / "the_extension.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"


async def init_db():
    schema = SCHEMA_PATH.read_text()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(schema)
        await db.commit()


async def create_project(name: str, path: str) -> str:
    project_id = str(uuid.uuid4())
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO projects (id, name, path) VALUES (?, ?, ?)",
            (project_id, name, path),
        )
        await db.commit()
    return project_id


async def create_conversation(project_id: str) -> str:
    conversation_id = str(uuid.uuid4())
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO conversations (id, project_id) VALUES (?, ?)",
            (conversation_id, project_id),
        )
        await db.commit()
    return conversation_id


async def add_message(
    conversation_id: str,
    role: str,
    content: str,
    tool_name: str | None = None,
) -> str:
    message_id = str(uuid.uuid4())
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO messages (id, conversation_id, role, content, tool_name) VALUES (?, ?, ?, ?, ?)",
            (message_id, conversation_id, role, content, tool_name),
        )
        await db.commit()
    return message_id


async def get_rules(project_id: str) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM rules WHERE project_id = ? ORDER BY created_at DESC",
            (project_id,),
        ) as cursor:
            rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def save_rule(project_id: str, content: str, source: str | None = None) -> str:
    rule_id = str(uuid.uuid4())
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO rules (id, project_id, content, source) VALUES (?, ?, ?, ?)",
            (rule_id, project_id, content, source),
        )
        await db.commit()
    return rule_id
