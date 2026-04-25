import os
from uagents import Agent, Context
from uagents.setup import fund_agent_if_low
from uagents import Model

BROWSER_CONTEXT_SEED = os.getenv("BROWSER_CONTEXT_AGENT_SEED", "browser-context-default-seed")

browser_context_agent = Agent(
    name="the-extension-browser-context",
    seed=BROWSER_CONTEXT_SEED,
    port=8004,
    endpoint=["http://localhost:8004/submit"],
)

fund_agent_if_low(browser_context_agent.wallet.address())

# Reference to the WS bridge, injected by main.py
_ws_bridge = None


def set_ws_bridge(bridge):
    global _ws_bridge
    _ws_bridge = bridge


class BrowserContextRequest(Model):
    request_type: str  # tab_content | console_logs | clicked_elements
    tab_id: str | None = None


class BrowserContextResponse(Model):
    content: str
    success: bool
    error: str | None = None


@browser_context_agent.on_message(model=BrowserContextRequest)
async def handle_browser_context_request(ctx: Context, sender: str, msg: BrowserContextRequest):
    ctx.logger.info(f"BrowserContext received request: {msg.request_type}")

    if _ws_bridge is None:
        await ctx.send(
            sender,
            BrowserContextResponse(content="", success=False, error="WebSocket bridge not connected"),
        )
        return

    try:
        result = await _ws_bridge.request(msg.request_type, {"tab_id": msg.tab_id})
        content = str(result.get("content") or result.get("logs") or result.get("elements") or "")
        await ctx.send(sender, BrowserContextResponse(content=content, success=True))
    except Exception as e:
        await ctx.send(sender, BrowserContextResponse(content="", success=False, error=str(e)))
