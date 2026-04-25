import asyncio
from dataclasses import dataclass
from typing import AsyncGenerator, Any

from utils.config import get_llm
from utils.memory import AgentMemory

MAX_ITERATIONS = 10


@dataclass
class StreamEvent:
    type: str  # content | tool_start | tool_end | thinking | error | done
    data: str = ""
    tool_name: str = ""
    tool_input: dict = None
    tool_output: str = ""

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "data": self.data,
            "tool_name": self.tool_name,
            "tool_input": self.tool_input or {},
            "tool_output": self.tool_output,
        }


class EvolveAgent:
    def __init__(self, project_id: str, tools: list, llm=None):
        self.project_id = project_id
        self.tools = tools
        self.llm = llm or get_llm()
        self.memory = AgentMemory(project_id)
        self._tool_map = {t.name: t for t in tools}

    async def run(self, prompt: str, context: str = "") -> AsyncGenerator[StreamEvent, None]:
        rules_prompt = await self.memory.format_rules_prompt()

        system = (
            "You are EvolveAgent — an expert Chrome extension developer. "
            "You build complete, working Chrome extensions from user descriptions. "
            "Always use MV3. Always validate before finishing."
            f"{rules_prompt}"
        )

        messages = [
            {"role": "system", "content": system},
        ]
        if context:
            messages.append({"role": "user", "content": f"Browser context:\n{context}"})
        messages.append({"role": "user", "content": prompt})

        llm_with_tools = self.llm.bind_tools(self.tools)

        for iteration in range(MAX_ITERATIONS):
            yield StreamEvent(type="thinking", data=f"Iteration {iteration + 1}")

            try:
                response = await llm_with_tools.ainvoke(messages)
            except Exception as e:
                yield StreamEvent(type="error", data=str(e))
                break

            # Stream text content
            content = response.content if hasattr(response, "content") else str(response)
            if content:
                yield StreamEvent(type="content", data=content)

            # Handle tool calls
            tool_calls = getattr(response, "tool_calls", [])
            if not tool_calls:
                break

            messages.append({"role": "assistant", "content": response})

            for tc in tool_calls:
                tool_name = tc["name"]
                tool_input = tc["args"]

                yield StreamEvent(type="tool_start", tool_name=tool_name, tool_input=tool_input)

                tool_fn = self._tool_map.get(tool_name)
                if tool_fn is None:
                    tool_output = f"Error: unknown tool {tool_name}"
                else:
                    try:
                        if asyncio.iscoroutinefunction(tool_fn.func):
                            tool_output = await tool_fn.ainvoke(tool_input)
                        else:
                            tool_output = await asyncio.get_event_loop().run_in_executor(
                                None, lambda: tool_fn.invoke(tool_input)
                            )
                    except Exception as e:
                        tool_output = f"Tool error: {e}"

                yield StreamEvent(
                    type="tool_end",
                    tool_name=tool_name,
                    tool_output=str(tool_output),
                )

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.get("id", tool_name),
                    "content": str(tool_output),
                })
        else:
            yield StreamEvent(type="error", data="Max iterations reached")

        yield StreamEvent(type="done")
