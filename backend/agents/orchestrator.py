import os
import uuid
from uagents import Agent, Context
from uagents.setup import fund_agent_if_low

from agents.models import (
    ExtensionRequest,
    ExtensionResponse,
    CodeGenRequest,
    CodeGenResponse,
    ValidateRequest,
    ValidateResponse,
)

ORCHESTRATOR_SEED = os.getenv("ORCHESTRATOR_AGENT_SEED", "orchestrator-default-seed")
CODEGEN_ADDRESS = os.getenv("CODEGEN_AGENT_ADDRESS", "")
VALIDATOR_ADDRESS = os.getenv("VALIDATOR_AGENT_ADDRESS", "")
MAX_RETRIES = 3

orchestrator = Agent(
    name="the-extension-orchestrator",
    seed=ORCHESTRATOR_SEED,
    port=8001,
    endpoint=["http://localhost:8001/submit"],
)

fund_agent_if_low(orchestrator.wallet.address())

# In-flight request state
_pending: dict[str, dict] = {}


@orchestrator.on_message(model=ExtensionRequest)
async def handle_extension_request(ctx: Context, sender: str, msg: ExtensionRequest):
    ctx.logger.info(f"Orchestrator received request: {msg.prompt[:80]}")

    project_id = msg.project_id or str(uuid.uuid4())
    state = {
        "sender": sender,
        "project_id": project_id,
        "prompt": msg.prompt,
        "browser_context": msg.browser_context,
        "retries": 0,
        "fix_errors": None,
    }
    _pending[project_id] = state

    await ctx.send(
        CODEGEN_ADDRESS,
        CodeGenRequest(
            prompt=msg.prompt,
            project_id=project_id,
            browser_context=msg.browser_context,
        ),
    )


@orchestrator.on_message(model=CodeGenResponse)
async def handle_codegen_response(ctx: Context, sender: str, msg: CodeGenResponse):
    if not msg.success:
        ctx.logger.error(f"CodeGen failed: {msg.error}")
        return

    # Find pending state by matching project_id from files context (sent alongside)
    # For simplicity, use the most recent pending request
    project_id = next(iter(_pending), None)
    if not project_id:
        return
    state = _pending[project_id]

    ctx.logger.info(f"CodeGen produced {len(msg.files)} files — sending to Validator")
    state["files"] = msg.files

    await ctx.send(
        VALIDATOR_ADDRESS,
        ValidateRequest(files=msg.files),
    )


@orchestrator.on_message(model=ValidateResponse)
async def handle_validate_response(ctx: Context, sender: str, msg: ValidateResponse):
    project_id = next(iter(_pending), None)
    if not project_id:
        return
    state = _pending[project_id]

    if msg.valid:
        ctx.logger.info("Validation passed — returning extension to user")
        summary = f"Extension built successfully with {len(state['files'])} files."
        response = ExtensionResponse(
            files=state["files"],
            valid=True,
            summary=summary,
        )
        await ctx.send(state["sender"], response)
        del _pending[project_id]
    elif state["retries"] < MAX_RETRIES:
        state["retries"] += 1
        ctx.logger.info(f"Validation failed (retry {state['retries']}/{MAX_RETRIES}): {msg.errors}")

        await ctx.send(
            CODEGEN_ADDRESS,
            CodeGenRequest(
                prompt=state["prompt"],
                project_id=project_id,
                browser_context=state.get("browser_context"),
                fix_errors=msg.errors,
            ),
        )
    else:
        ctx.logger.error("Max retries reached — returning best-effort result")
        await ctx.send(
            state["sender"],
            ExtensionResponse(
                files=state.get("files", {}),
                valid=False,
                summary=f"Validation failed after {MAX_RETRIES} attempts: {'; '.join(msg.errors)}",
            ),
        )
        del _pending[project_id]
