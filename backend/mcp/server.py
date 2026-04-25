"""
MCP server exposing browser context tools so any AI coding agent (Devin, Cursor, etc.)
can use live browser data. Run with: python -m mcp.server (stdio transport).
"""
import asyncio
import sys
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

app = Server("the-extension-browser-context")

# WS bridge injected at startup
_ws_bridge = None


def set_ws_bridge(bridge):
    global _ws_bridge
    _ws_bridge = bridge


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="get_tab_content",
            description="Fetch the DOM/text content from the user's active browser tab",
            inputSchema={
                "type": "object",
                "properties": {
                    "tab_id": {
                        "type": "string",
                        "description": "Tab ID to fetch (default: active tab)",
                        "default": "active",
                    }
                },
            },
        ),
        Tool(
            name="get_console_logs",
            description="Fetch console log output from the user's active browser tab",
            inputSchema={
                "type": "object",
                "properties": {
                    "tab_id": {
                        "type": "string",
                        "description": "Tab ID to fetch logs from (default: active tab)",
                        "default": "active",
                    }
                },
            },
        ),
        Tool(
            name="get_clicked_elements",
            description="Retrieve CSS selectors and metadata for elements the user clicked in click-to-select mode",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if _ws_bridge is None:
        return [TextContent(type="text", text="Error: WebSocket bridge not connected")]

    try:
        if name == "get_tab_content":
            result = await _ws_bridge.request("get_tab_content", {"tab_id": arguments.get("tab_id", "active")})
            return [TextContent(type="text", text=result.get("content", "No content"))]

        elif name == "get_console_logs":
            result = await _ws_bridge.request("get_console_logs", {"tab_id": arguments.get("tab_id", "active")})
            logs = result.get("logs", [])
            return [TextContent(type="text", text="\n".join(logs) if logs else "No console logs")]

        elif name == "get_clicked_elements":
            result = await _ws_bridge.request("get_clicked_elements", {})
            elements = result.get("elements", [])
            if not elements:
                return [TextContent(type="text", text="No elements selected")]
            text = "\n".join(
                f"- {e['tag']} | selector: {e['selector']} | text: {e.get('text', '')[:80]}"
                for e in elements
            )
            return [TextContent(type="text", text=text)]

        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

    except Exception as e:
        return [TextContent(type="text", text=f"Error: {e}")]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
