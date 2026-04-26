"""Extension RAG Agent role."""

from __future__ import annotations

from agentverse_app.config import settings
from agentverse_app.messages import RagRequest, RagResult
from agentverse_app.nudges import retrieve_context


CURATED_PATTERNS = [
    "Manifest V3 content scripts should declare matches, css/js files, and run_at when DOM timing matters.",
    "For dynamic sites, combine CSS selectors with a content.js MutationObserver and a short interval fallback.",
    "Prefer target-site matches over <all_urls> unless the user asks for global behavior.",
    "Static validation only proves manifest/file/syntax correctness; real DOM behavior needs browser checks.",
]


async def run_rag(request: RagRequest) -> RagResult:
    snippets = list(CURATED_PATTERNS)
    snippets.extend(retrieve_context(request.query, request.spec.target_urls))
    if settings.enable_graph_rag:
        snippets.append(
            "Graph RAG is enabled, but the first Agentverse implementation keeps curated context as the stable fallback."
        )
    return RagResult(
        job_id=request.job_id,
        snippets=snippets,
        summary=f"Retrieved {len(snippets)} extension implementation patterns.",
    )
