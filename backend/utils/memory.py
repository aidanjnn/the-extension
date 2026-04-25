from database import get_rules, save_rule


class AgentMemory:
    def __init__(self, project_id: str):
        self.project_id = project_id

    async def extract_rules(self, conversation: list[dict]) -> list[str]:
        from utils.config import get_llm
        llm = get_llm()

        conversation_text = "\n".join(
            f"{m['role']}: {m['content']}" for m in conversation[-10:]
        )
        prompt = (
            "Extract any reusable coding rules or preferences from this conversation. "
            "Return each rule on its own line starting with '- '. "
            "Only extract clear, actionable rules. Return empty if none found.\n\n"
            f"{conversation_text}"
        )
        response = await llm.ainvoke(prompt)
        text = response.content if hasattr(response, "content") else str(response)
        rules = [
            line.lstrip("- ").strip()
            for line in text.splitlines()
            if line.strip().startswith("- ")
        ]
        for rule in rules:
            await save_rule(self.project_id, rule, source="conversation")
        return rules

    async def get_rules(self) -> list[dict]:
        return await get_rules(self.project_id)

    async def format_rules_prompt(self) -> str:
        rules = await self.get_rules()
        if not rules:
            return ""
        lines = "\n".join(f"- {r['content']}" for r in rules)
        return f"\n\n## Learned Rules (follow these):\n{lines}"
