"""Runnable Agentverse/uAgents app for Browser Forge.

Run locally with:
    uv run python -m agentverse_app.main

The Orchestrator is ASI:One-compatible through Agent Chat Protocol. Specialist
agents expose typed request/response handlers and can also be registered on
Agentverse for discovery.
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from uagents import Agent, Bureau, Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    TextContent,
    chat_protocol_spec,
)

from agentverse_app.architect import run_architect
from agentverse_app.codegen import run_codegen
from agentverse_app.config import settings
from agentverse_app.messages import (
    ArchitectRequest,
    CodegenRequest,
    PackageRequest,
    RagRequest,
    ValidationRequest,
)
from agentverse_app.orchestrator import create_build_request, run_orchestrator
from agentverse_app.packager import run_packager
from agentverse_app.rag import run_rag
from agentverse_app.validator import run_validator


orchestrator = Agent(
    name="browser_forge_orchestrator",
    seed=settings.orchestrator_seed,
    mailbox=False,
    publish_agent_details=True,
)
architect = Agent(
    name="browser_forge_architect",
    seed=settings.architect_seed,
    mailbox=False,
    publish_agent_details=True,
)
rag = Agent(
    name="browser_forge_rag",
    seed=settings.rag_seed,
    mailbox=False,
    publish_agent_details=True,
)
codegen = Agent(
    name="browser_forge_codegen",
    seed=settings.codegen_seed,
    mailbox=False,
    publish_agent_details=True,
)
validator = Agent(
    name="browser_forge_validator",
    seed=settings.validator_seed,
    mailbox=False,
    publish_agent_details=True,
)
packager = Agent(
    name="browser_forge_packager",
    seed=settings.packager_seed,
    mailbox=False,
    publish_agent_details=True,
)

chat_protocol = Protocol(spec=chat_protocol_spec)


@chat_protocol.on_message(ChatMessage)
async def handle_chat(ctx: Context, sender: str, msg: ChatMessage):
    await ctx.send(
        sender,
        ChatAcknowledgement(
            timestamp=datetime.utcnow(),
            acknowledged_msg_id=msg.msg_id,
        ),
    )

    text = "".join(
        item.text for item in msg.content if isinstance(item, TextContent)
    ).strip()
    if not text:
        text = "Build a simple Chrome extension."

    build = create_build_request(
        query=text,
        project_id=uuid4().hex,
        source="asi_one",
    )
    try:
        result = await run_orchestrator(build)
        response_text = result.final_message
    except Exception as exc:
        ctx.logger.exception("Agentverse orchestration failed")
        response_text = f"Agentverse orchestration failed: {exc}"

    await ctx.send(
        sender,
        ChatMessage(
            timestamp=datetime.utcnow(),
            msg_id=uuid4(),
            content=[
                TextContent(type="text", text=response_text),
                EndSessionContent(type="end-session"),
            ],
        ),
    )


@chat_protocol.on_message(ChatAcknowledgement)
async def handle_chat_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    ctx.logger.info("Received chat acknowledgement from %s", sender)


orchestrator.include(chat_protocol, publish_manifest=True)


@architect.on_message(model=ArchitectRequest)
async def handle_architect(ctx: Context, sender: str, msg: ArchitectRequest):
    await ctx.send(sender, await run_architect(msg))


@rag.on_message(model=RagRequest)
async def handle_rag(ctx: Context, sender: str, msg: RagRequest):
    await ctx.send(sender, await run_rag(msg))


@codegen.on_message(model=CodegenRequest)
async def handle_codegen(ctx: Context, sender: str, msg: CodegenRequest):
    await ctx.send(sender, await run_codegen(msg))


@validator.on_message(model=ValidationRequest)
async def handle_validator(ctx: Context, sender: str, msg: ValidationRequest):
    await ctx.send(sender, await run_validator(msg))


@packager.on_message(model=PackageRequest)
async def handle_packager(ctx: Context, sender: str, msg: PackageRequest):
    await ctx.send(sender, await run_packager(msg))


def main() -> None:
    endpoint = None
    if settings.public_agent_base_url:
        endpoint = settings.public_agent_base_url.rstrip("/") + "/submit"
    bureau = Bureau(port=settings.uagents_port, endpoint=endpoint)
    for agent in (orchestrator, architect, rag, codegen, validator, packager):
        bureau.add(agent)
    bureau.run()


if __name__ == "__main__":
    main()
