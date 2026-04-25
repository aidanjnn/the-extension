"""Extension Architect Agent role."""

from __future__ import annotations

import re

from agentverse_app.messages import ArchitectRequest, ArchitectResult, ExtensionSpec


def _infer_target_urls(query: str, active_tabs: list[dict]) -> list[str]:
    lowered = query.lower()
    if "instagram" in lowered:
        return ["https://www.instagram.com/*", "https://instagram.com/*"]
    if "youtube" in lowered:
        return ["https://www.youtube.com/*"]
    if "twitter" in lowered or "x.com" in lowered:
        return ["https://x.com/*", "https://twitter.com/*"]
    if "gmail" in lowered:
        return ["https://mail.google.com/*"]

    for tab in active_tabs:
        url = tab.get("url", "")
        match = re.match(r"https?://([^/]+)/?", url)
        if match:
            host = match.group(1)
            return [f"https://{host}/*"]
    return ["<all_urls>"]


def _extension_name(query: str) -> str:
    words = re.sub(r"[^a-zA-Z0-9 ]+", " ", query).strip().split()
    title = " ".join(words[:5]).title()
    return title or "Browser Forge Extension"


async def run_architect(request: ArchitectRequest) -> ArchitectResult:
    build = request.build
    target_urls = _infer_target_urls(build.query, build.active_tabs)
    spec = ExtensionSpec(
        job_id=build.job_id,
        project_id=build.project_id,
        name=_extension_name(build.query),
        description=f"Generated extension for: {build.query}",
        target_urls=target_urls,
        files_needed=["manifest.json", "content.js", "content.css"],
        behavior=build.query,
        verification_notes=[
            "Use content scripts for DOM changes.",
            "Handle dynamic single-page app rerenders with a MutationObserver.",
            "Keep permissions minimal for Manifest V3.",
        ],
    )
    return ArchitectResult(
        job_id=build.job_id,
        spec=spec,
        summary=f"Planned a content-script extension for {', '.join(target_urls)}.",
    )
