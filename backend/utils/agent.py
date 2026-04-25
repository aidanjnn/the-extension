import asyncio
import os
from collections.abc import AsyncGenerator
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI

from utils.config import PROVIDERS, current_provider
from utils.prompts import CODEBASE_SEARCH_UNAVAILABLE_NOTE, SYSTEM_PROMPT
from utils.tools import (
    ALL_TOOLS,
    DEMO_CODE_BASE,
    current_console_log_cache,
    current_outbound_queue,
    current_pending_tab_requests,
    current_project_dir,
    current_tab_content_cache,
    get_available_tools,
)


class BrowserForgeAgent:
    def __init__(self):
        # Lazily create LLMs so missing keys for unused providers do not break startup.
        self._llms = {}
        # Full tool lookup dict — used for dispatching tool calls at runtime
        self.all_tools = {t.name: t for t in ALL_TOOLS}

    def _get_llm(self, provider: str) -> ChatOpenAI:
        provider = provider if provider in PROVIDERS else "gemini"
        if provider not in self._llms:
            cfg = PROVIDERS[provider]
            api_key = os.getenv(cfg["api_key_env"]) if cfg.get("api_key_env") else None
            self._llms[provider] = ChatOpenAI(
                model=cfg["primary_model"],
                base_url=cfg.get("base_url"),
                api_key=api_key,
            )
        return self._llms[provider]

    def _resolve_tool_name(self, name: str) -> str:
        """Resolve a tool name, handling duplicated names from streaming chunk concatenation.

        When LangChain accumulates AIMessageChunk objects via ``+``, tool-call
        name strings can be concatenated (e.g. ``get_tab_contentget_tab_content``).
        This helper detects that pattern and returns the correct single name.
        """
        if name in self.all_tools:
            return name
        for known in self.all_tools:
            if (
                len(name) > len(known)
                and len(name) % len(known) == 0
                and name == known * (len(name) // len(known))
            ):
                return known
        raise KeyError(f"Unknown tool: {name}")

    def _build_messages(
        self,
        history: list[dict],
        codebase_search_available: bool = True,
        active_tabs: list[dict] | None = None,
        rules: list[str] | None = None,
    ) -> list:
        """Convert dict-based history to LangChain message objects."""
        prompt = SYSTEM_PROMPT
        if not codebase_search_available:
            prompt += CODEBASE_SEARCH_UNAVAILABLE_NOTE

        if rules:
            rule_lines = "\n".join(f"- {r}" for r in rules)
            prompt += (
                "\n\n## Agent Memory\n"
                "The following rules were learned from previous interactions with this user.\n"
                "Follow them unless the user explicitly overrides one.\n"
                + rule_lines
            )

        if active_tabs:
            tab_lines = []
            for tab in active_tabs:
                marker = " (active)" if tab.get("active") else ""
                tab_lines.append(
                    f"- id={tab['id']}  {tab.get('title', '(no title)')}  {tab.get('url', '')}{marker}"
                )
            prompt += (
                "\n\n## User's Open Browser Tabs\n"
                "Use `get_tab_content(tab_id)` to fetch a page's text when needed.\n"
                + "\n".join(tab_lines)
            )

        messages = [SystemMessage(content=prompt)]
        for msg in history:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                messages.append(AIMessage(content=msg["content"]))
        return messages

    def _set_project_context(self, project_id: str) -> Path:
        """Set the current project workspace directory for tool execution.

        Returns the resolved project directory path.
        """
        project_dir = (DEMO_CODE_BASE / project_id).resolve()
        project_dir.mkdir(parents=True, exist_ok=True)
        current_project_dir.set(project_dir)
        return project_dir

    def _prepare_request(self, project_id: str, provider: str = "gemini"):
        """Set context and return the bound LLM with quota-heavy search disabled.

        Graph RAG indexing performs extra embedding/entity-extraction calls, so
        keep codebase_search unavailable during Gemini quota-sensitive demos.
        """
        project_dir = self._set_project_context(project_id)
        current_provider.set(provider)

        cs_available = False
        tools_list = get_available_tools(include_codebase_search=cs_available)
        base_llm = self._get_llm(provider)
        bound_llm = base_llm.bind_tools(tools_list)

        return bound_llm, cs_available

    async def get_chat_response(
        self,
        history: list[dict],
        project_id: str,
        rules: list[str] | None = None,
        provider: str = "gemini",
    ) -> str:
        """Send conversation history to the LLM, execute any tool calls, and return the final reply."""
        bound_llm, cs_available = self._prepare_request(project_id, provider=provider)
        messages = self._build_messages(history, codebase_search_available=cs_available, rules=rules)

        while True:
            response = await bound_llm.ainvoke(messages)
            # Some providers (e.g. NVIDIA) reject empty-string content.
            if not response.content:
                response.content = "\u200b"
            messages.append(response)

            if not response.tool_calls:
                return response.content

            for tool_call in response.tool_calls:
                resolved_name = self._resolve_tool_name(tool_call["name"])
                tool = self.all_tools[resolved_name]
                result = await tool.ainvoke(tool_call["args"])
                print(f"[tool:{resolved_name}] {result}")
                tool_content = str(result) or "(No output)"
                messages.append(
                    ToolMessage(content=tool_content, tool_call_id=tool_call["id"])
                )

    async def stream_chat_response(
        self,
        history: list[dict],
        project_id: str,
        active_tabs: list[dict] | None = None,
        pending_tab_requests: dict | None = None,
        rules: list[str] | None = None,
        provider: str = "gemini",
    ) -> AsyncGenerator[dict, None]:
        """Stream conversation history to the LLM, execute tool calls, and yield event dicts.

        Yields dicts with a "type" key:
        - {"type": "content", "content": "..."} for text chunks
        - {"type": "tool_start", "name": "...", "args": {...}} when a tool begins
        - {"type": "tool_end", "name": "..."} when a tool finishes
        - {"type": "request_tab_content", ...} when a tool needs browser data
        """
        bound_llm, cs_available = self._prepare_request(project_id, provider=provider)
        messages = self._build_messages(
            history,
            codebase_search_available=cs_available,
            active_tabs=active_tabs,
            rules=rules,
        )

        # Set up the outbound queue so get_tab_content can push events
        outbound: asyncio.Queue[dict] = asyncio.Queue()
        current_outbound_queue.set(outbound)
        current_tab_content_cache.set({})
        current_console_log_cache.set({})
        if pending_tab_requests is not None:
            current_pending_tab_requests.set(pending_tab_requests)

        while True:
            full_response = None
            async for chunk in bound_llm.astream(messages):
                if full_response is None:
                    full_response = chunk
                else:
                    full_response = full_response + chunk

                if chunk.content:
                    yield {"type": "content", "content": chunk.content}

            if full_response is None:
                return

            # Some providers (e.g. NVIDIA) reject empty-string content.
            # When the LLM only produces tool calls, content is "".
            if not full_response.content:
                full_response.content = "\u200b"
            messages.append(full_response)

            if not full_response.tool_calls:
                return

            for tool_call in full_response.tool_calls:
                resolved_name = self._resolve_tool_name(tool_call["name"])
                tool = self.all_tools[resolved_name]
                yield {"type": "tool_start", "name": resolved_name, "args": tool_call["args"]}

                # Run the tool concurrently with draining the outbound queue,
                # so request_tab_content events are yielded while the tool awaits.
                tool_task = asyncio.create_task(tool.ainvoke(tool_call["args"]))

                while not tool_task.done():
                    # Drain any outbound events the tool pushed (e.g. request_tab_content)
                    while not outbound.empty():
                        yield outbound.get_nowait()
                    # Give the tool a chance to make progress
                    await asyncio.sleep(0.05)

                result = tool_task.result()
                # Drain any remaining events
                while not outbound.empty():
                    yield outbound.get_nowait()

                print(f"[tool:{resolved_name}] {result}")
                yield {"type": "tool_end", "name": resolved_name}
                tool_content = str(result) or "(No output)"
                messages.append(
                    ToolMessage(content=tool_content, tool_call_id=tool_call["id"])
                )

            # All tool calls done; LLM will process results next iteration
            yield {"type": "thinking"}
