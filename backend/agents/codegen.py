import json
import os
import re
from uagents import Agent, Context
from uagents.setup import fund_agent_if_low

from agents.models import CodeGenRequest, CodeGenResponse

CODEGEN_SEED = os.getenv("CODEGEN_AGENT_SEED", "codegen-default-seed")

codegen = Agent(
    name="the-extension-codegen",
    seed=CODEGEN_SEED,
    port=8002,
    endpoint=["http://localhost:8002/submit"],
)

fund_agent_if_low(codegen.wallet.address())


@codegen.on_message(model=CodeGenRequest)
async def handle_codegen_request(ctx: Context, sender: str, msg: CodeGenRequest):
    ctx.logger.info(f"CodeGen received request: {msg.prompt[:80]}")

    from utils.config import get_llm
    llm = get_llm()

    fix_section = ""
    if msg.fix_errors:
        fix_section = "\n\nFix these validation errors:\n" + "\n".join(
            f"- {e}" for e in msg.fix_errors
        )

    context_section = ""
    if msg.browser_context:
        context_section = f"\n\nBrowser context (DOM/page info):\n{msg.browser_context[:2000]}"

    system_prompt = """You are a Chrome Extension specialist. Generate a complete, working Chrome extension.

Rules:
- Always use Manifest V3
- Include manifest.json, content scripts, and popup if needed
- Return ONLY a JSON object mapping filenames to file contents
- Format: {"manifest.json": "...", "content.js": "...", ...}
- No explanations outside the JSON"""

    user_prompt = f"Build a Chrome extension: {msg.prompt}{context_section}{fix_section}"

    try:
        response = await llm.ainvoke([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ])
        raw = response.content if hasattr(response, "content") else str(response)

        # Extract JSON from response
        json_match = re.search(r"\{[\s\S]*\}", raw)
        if not json_match:
            raise ValueError("No JSON found in LLM response")

        files = json.loads(json_match.group())
        await ctx.send(sender, CodeGenResponse(files=files, success=True))
    except Exception as e:
        ctx.logger.error(f"CodeGen error: {e}")
        await ctx.send(sender, CodeGenResponse(files={}, success=False, error=str(e)))
