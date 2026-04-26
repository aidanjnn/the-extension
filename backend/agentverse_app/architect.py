"""Extension Architect Agent role."""

from __future__ import annotations

import re

from agentverse_app.messages import ArchitectRequest, ArchitectResult, ExtensionSpec


def _strip_chip_html(text: str) -> str:
    cleaned = re.sub(
        r"<!--EVOLVE_CHIP_START:[^>]*-->.*?<!--EVOLVE_CHIP_END-->",
        "",
        text,
        flags=re.DOTALL,
    )
    return re.sub(r"\s+", " ", cleaned).strip()


def _infer_target_urls(query: str, active_tabs: list[dict]) -> list[str]:
    lowered = query.lower()
    if "instagram" in lowered:
        return ["https://www.instagram.com/*", "https://instagram.com/*"]
    if any(term in lowered for term in ("messages", "message bar", "direct", "dm")):
        return ["https://www.instagram.com/*", "https://instagram.com/*"]
    if "youtube" in lowered:
        return ["https://www.youtube.com/*"]
    if "twitter" in lowered or "x.com" in lowered:
        return ["https://x.com/*", "https://twitter.com/*"]
    if "gmail" in lowered:
        return ["https://mail.google.com/*"]

    for tab in active_tabs:
        if tab.get("active"):
            url = tab.get("url", "")
            match = re.match(r"https?://([^/]+)/?", url)
            if match:
                host = match.group(1)
                return [f"https://{host}/*"]

    for tab in active_tabs:
        url = tab.get("url", "")
        match = re.match(r"https?://([^/]+)/?", url)
        if match:
            host = match.group(1)
            return [f"https://{host}/*"]
    return ["<all_urls>"]


_ACTION_WORDS = {
    "hide", "remove", "block", "clean", "highlight", "summarize", "translate",
    "filter", "minimize", "expand", "darken", "lighten", "show", "skip", "mute",
    "save", "download", "auto", "redirect",
}
_SITE_WORDS = {
    "instagram", "youtube", "twitter", "x", "gmail", "linkedin", "amazon",
    "facebook", "reddit", "tiktok", "github", "spotify", "netflix", "twitch",
    "medium", "substack", "notion",
}
_TARGET_WORDS = {
    "reels", "shorts", "ads", "messages", "notifications", "sidebar", "stories",
    "comments", "feed", "suggestions", "prices", "videos", "posts", "thumbnails",
    "recommendations", "trending", "explore", "promoted", "sponsored", "popups",
}
_BRAND_CASE = {
    "youtube": "YouTube",
    "tiktok": "TikTok",
    "linkedin": "LinkedIn",
    "github": "GitHub",
    "x": "X",
    "instagram": "Instagram",
    "twitter": "Twitter",
    "gmail": "Gmail",
    "facebook": "Facebook",
    "amazon": "Amazon",
    "reddit": "Reddit",
    "spotify": "Spotify",
    "netflix": "Netflix",
    "twitch": "Twitch",
    "medium": "Medium",
    "substack": "Substack",
    "notion": "Notion",
}
_STOP_WORDS = {
    "chrome", "extension", "browser", "website", "site", "page", "app",
    "build", "make", "create", "generate", "write", "develop", "code",
    "a", "an", "the", "that", "which", "who", "what", "this", "these",
    "to", "for", "from", "on", "in", "at", "with", "by", "of", "into",
    "me", "my", "please", "can", "you", "will", "would", "could", "should",
    "i", "want", "need", "like", "have", "get", "let", "do", "does",
    "and", "or", "but", "so", "is", "are", "be", "been", "being",
}


def _cap(word: str) -> str:
    return _BRAND_CASE.get(word, word.title())


def _extension_name(query: str) -> str:
    words = re.findall(r"[a-zA-Z]+", query.lower())
    if not words:
        return "Browser Forge Extension"

    action = next((w for w in words if w in _ACTION_WORDS), None)
    site = next((w for w in words if w in _SITE_WORDS), None)
    target = next((w for w in words if w in _TARGET_WORDS), None)

    parts = [p for p in (action, site, target) if p]
    if len(parts) >= 2:
        return " ".join(_cap(p) for p in parts)

    meaningful = [w for w in words if w not in _STOP_WORDS and len(w) > 1]
    if not meaningful:
        return "Browser Forge Extension"

    return " ".join(_cap(w) for w in meaningful[:4])


async def run_architect(request: ArchitectRequest) -> ArchitectResult:
    build = request.build
    clean_query = _strip_chip_html(build.query)
    target_urls = _infer_target_urls(clean_query, build.active_tabs)
    spec = ExtensionSpec(
        job_id=build.job_id,
        project_id=build.project_id,
        name=_extension_name(clean_query),
        description=f"Generated extension for: {clean_query}"[:200],
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
