"""Extension Codegen Agent role."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

from agentverse_app import backend_client
from agentverse_app.deterministic_codegen import build_deterministic_files
from agentverse_app.messages import CodegenRequest, CodegenResult
from agentverse_app.nudges import retrieve_context_entries
from utils.config import get_provider_config, get_secondary_client

logger = logging.getLogger(__name__)
CODEGEN_LLM_TIMEOUT_SECONDS = 35
CODEGEN_MAX_ATTEMPTS = 2


USE_CASE_RULES: dict[str, dict[str, Any]] = {
    "youtube-shorts": {"required_any": ["/shorts", "ytd-reel-shelf-renderer", "ytd-guide-entry-renderer"], "min_signals": 2, "behavior": "hide", "require_mutation_observer": True},
    "youtube-comments": {"required_any": ["ytd-comments", "#comments"], "min_signals": 1, "behavior": "hide"},
    "youtube-recommendations": {"required_any": ["#secondary", "ytd-watch-next-secondary-results-renderer", "ytd-compact-video-renderer"], "min_signals": 1, "behavior": "hide"},
    "youtube-keyword-filter": {"required_any": ["ytd-rich-item-renderer", "ytd-video-renderer", "/api/classify"], "min_signals": 2, "behavior": "classify"},
    "youtube-absolute-focus": {"required_any": ["bf-youtube-absolute-focus", "ytd-thumbnail", "ytd-rich-grid-renderer", "#masthead-container", "#secondary"], "min_signals": 3, "behavior": "hide", "require_mutation_observer": True},
    "instagram-nav": {"required_any": ["/reels", "/explore", "/direct", "role=\"listitem\"", "role=listitem"], "min_signals": 2, "behavior": "hide"},
    "instagram-suggested-posts": {"required_any": ["suggested", "article", "role=\"main\"", "role='main'"], "min_signals": 2, "behavior": "hide"},
    "instagram-floating-messages": {"required_any": ["position: fixed", "getboundingclientrect", "direct", "messages"], "min_signals": 2, "behavior": "hide"},
    "instagram-engagement-counts": {"required_any": ["likes", "comments", "aria-label"], "min_signals": 1, "behavior": "hide"},
    "doomscroll-guillotine": {"required_any": ["intersectionobserver", "bf-doomscroll-counter", "bf-doomscroll-wall", "10/10", "wheel"], "min_signals": 4, "behavior": "inject", "require_mutation_observer": True},
    "gmail-tabs": {"required_any": ["role=tab", "role=\"tab\"", "promotions", "social"], "min_signals": 2, "behavior": "hide"},
    "gmail-sender-highlight": {"required_any": ["sender", "role=row", "unread", "tr"], "min_signals": 2, "behavior": "highlight"},
    "gmail-focus": {"required_any": ["side panel", "advertisement", "aria-label*=\"meet\"", "aria-label*=\"chat\""], "min_signals": 1, "behavior": "hide"},
    "email-deadlines": {"required_any": ["/api/classify", "deadline", "action"], "min_signals": 1, "behavior": "classify"},
    "outlook-panels": {"required_any": ["complementary", "advertisement", "premium", "upgrade"], "min_signals": 1, "behavior": "hide"},
    "outlook-highlight-sender": {"required_any": ["sender", "role=row", "highlight"], "min_signals": 2, "behavior": "highlight"},
    "calendar-meeting-prep": {"required_any": ["createelement", "appendchild", "data-", "meeting"], "min_signals": 2, "behavior": "inject"},
    "google-calendar-keywords": {"required_any": ["calendar", "aria-label", "event", "classlist.add"], "min_signals": 2, "behavior": "highlight"},
    "google-calendar-weekends": {"required_any": ["saturday", "sunday", "weekend", "aria-label"], "min_signals": 1, "behavior": "hide"},
    "calendar-missing-location": {"required_any": ["location", "link", "warning", "createelement"], "min_signals": 2, "behavior": "inject"},
    "linkedin-feed": {"required_any": ["/feed", "scaffold-finite-scroll", "feed-shared-update-v2"], "min_signals": 1, "behavior": "hide"},
    "linkedin-promoted": {"required_any": ["promoted", "sponsored", "ad", "feed-shared-update-v2"], "min_signals": 1, "behavior": "hide"},
    "linkedin-page-filter": {"required_any": ["/api/classify", "company", "page"], "min_signals": 1, "behavior": "classify"},
    "x-for-you": {"required_any": ["for you", "following", "data-testid"], "min_signals": 2, "behavior": "hide"},
    "x-trending": {"required_any": ["trending", "what's happening", "right", "complementary"], "min_signals": 1, "behavior": "hide"},
    "x-engagement-bait": {"required_any": ["status", "icon-verified", "cellinnerdiv", "likes", "article"], "min_signals": 4, "behavior": "hide", "require_mutation_observer": True},
    "netflix-roulette": {"required_any": ["button-controls-container", "bf-netflix-roulette", "random episode", "/watch/", "pointerevent"], "min_signals": 3, "behavior": "inject", "require_mutation_observer": True},
    "reddit-sidebar": {"required_any": ["aside", "complementary", "shreddit", "reddit-sidebar", "data-testid", "getboundingclientrect"], "min_signals": 3, "behavior": "hide"},
    "reddit-collapse-comments": {"required_any": ["comment", "collapse", "aria-expanded", "reply"], "min_signals": 1, "behavior": "collapse"},
}


CODEGEN_SYSTEM_PROMPT = """\
You are an expert Chrome extension engineer. You write Manifest V3 content-script \
extensions that perform precise DOM modifications on specific websites.

You will receive a user request describing a browser customization. Your job is to \
output a complete Chrome extension as JSON with exactly three files: manifest.json, \
content.js, and content.css. content.js and content.css must both contain meaningful \
implementation code; never leave either one empty.

You may also receive retrieved implementation context. Treat it as DOM guidance, \
safety constraints, and selector starting points. Adapt it to the exact user \
request, target URLs, and page evidence.

Critical rules:
1. Use SITE-SPECIFIC selectors, not generic ones. Research the site's actual DOM \
   structure (e.g., for YouTube use `ytd-rich-section-renderer`, \
   `ytd-reel-shelf-renderer`, etc.; for Instagram use `[role="main"]` with specific \
   article selectors; for Twitter use `[data-testid="..."]`).
2. NEVER use overly broad selectors like `[class*="shorts" i]` or matching on \
   `textContent` of any element — they will hide entire page sections.
3. NEVER walk up to ancestor containers using generic tags like \
   `closest('section, article, nav, aside')` — you will hide the whole page.
4. Use a MutationObserver for dynamic single-page apps; debounce with \
   requestAnimationFrame if needed.
5. Use CSS `:has()` selectors where supported for clean hide rules, but pair CSS \
   with JS so the extension also handles dynamic single-page app rerenders.
6. Keep permissions minimal. content_scripts only — no service worker unless needed.
7. The manifest description must be a plain string, no HTML.

8. NEVER add `icons`, `web_accessible_resources`, `action`, `background`, or any \
   field that references files you are not generating. You only generate three \
   files: manifest.json, content.js, content.css. The manifest MUST NOT reference \
   any other file. No PNG icons, no popup HTML, no service worker.
9. NEVER include `permissions` unless the content script genuinely needs them. \
   Most hide-this-element tasks need none. Use `host_permissions` ONLY when you \
   need to fetch the local classification backend (see rule 10).

CONTENT CLASSIFICATION TASKS:
10. If the user's request requires deciding whether each item on the page matches \
   some semantic criterion ("only show sports videos", "hide political content", \
   "filter for tutorials"), you MUST NOT use hardcoded keyword lists or regex. \
   Instead, generate code that calls the local classification backend at runtime:

   - Add `"host_permissions": ["http://localhost:8000/*"]` to the manifest.
   - In content.js, identify each candidate item element on the page and assign it \
     a stable id (extract from a video URL, data attribute, or generate one and \
     stash it in a WeakMap).
   - Collect each item's title text plus channel/source/description if available, \
     truncated to ~300 chars.
   - Batch up to 30 items at a time and POST them to:
       POST http://localhost:8000/api/classify
       body: {"filter_description": "<user filter>", "items": [{"id": "...", "text": "..."}]}
       response: {"matches": ["id1", "id2", ...]}
   - Hide items whose id is NOT in `matches`. Show items whose id IS in `matches`.
   - Cache classification results in a Map so the same id is never re-classified.
   - Use a MutationObserver and re-run the collect-and-classify cycle when new \
     items appear. Debounce with setTimeout (300ms) to batch sibling DOM updates.
   - Default state for un-classified items: keep them VISIBLE (do not hide pending \
     items). Only hide once classification returns and the id is not in matches.

   Hide via a CSS class added in content.css, e.g. `.bf-hidden { display: none !important; }`.
   Set the `filter_description` string to a clean restatement of the user's intent.

11. For SIMPLE STRUCTURAL tasks (hide the Shorts shelf, remove the sidebar), use \
    static CSS/JS — DO NOT call the classification backend. Classification is for \
    semantic content judgment, not for hiding known DOM regions.

Output format: a single JSON object with exactly these keys:
{
  "manifest": { ... full manifest.json object ... },
  "content_js": "...full JS source...",
  "content_css": "...full CSS source..."
}

Output ONLY the JSON object, no prose, no markdown fences.
"""


def _strip_chip_html(text: str) -> str:
    """Strip Browser Forge chip HTML markers from a query."""
    cleaned = re.sub(
        r"<!--EVOLVE_CHIP_START:[^>]*-->.*?<!--EVOLVE_CHIP_END-->",
        "",
        text,
        flags=re.DOTALL,
    )
    return re.sub(r"\s+", " ", cleaned).strip()


def _extract_json(content: str) -> dict[str, Any] | None:
    """Pull a JSON object out of an LLM response that may have stray text."""
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```\s*$", "", content)
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", content, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


_SITE_ALIASES: dict[str, tuple[str, ...]] = {
    "youtube": ("youtube", "youtube.com", "youtu.be"),
    "instagram": ("instagram", "instagram.com"),
    "tiktok": ("tiktok", "tiktok.com"),
    "gmail": ("gmail", "mail.google.com"),
    "outlook": ("outlook", "outlook.com", "outlook.live.com", "outlook.office.com", "office.com"),
    "calendar": ("calendar", "calendar.google.com", "google.com/calendar"),
    "linkedin": ("linkedin", "linkedin.com"),
    "reddit": ("reddit", "reddit.com", "old.reddit.com"),
    "x": ("x", "x.com", "twitter", "twitter.com"),
    "twitter": ("x", "x.com", "twitter", "twitter.com"),
    "netflix": ("netflix", "netflix.com"),
}


def _entry_has_site_alignment(
    entry: dict[str, Any],
    query_lower: str,
    target_urls: list[str],
) -> bool:
    """True when a site-specific corpus entry applies to this request/target.

    Generic words like "sidebar" can match several corpus entries. The quality
    gate should only enforce a site's DOM selectors when the query or manifest
    target actually names that site.
    """
    sites = [str(site).lower() for site in entry.get("sites", []) if str(site).strip()]
    if not sites:
        return True

    haystack = f"{query_lower} {' '.join(target_urls)}".lower()
    tokens = set(re.findall(r"[a-z0-9]+", haystack))
    for site in sites:
        aliases = _SITE_ALIASES.get(site, (site,))
        for alias in aliases:
            alias_lower = alias.lower()
            if "." in alias_lower or "/" in alias_lower:
                if alias_lower in haystack:
                    return True
                continue
            if alias_lower in tokens:
                return True
    return False


async def _generate_with_llm(
    query: str,
    target_urls: list[str],
    extension_name: str,
    provider: str,
    rag_snippets: list[str],
    quality_feedback: list[str] | None = None,
) -> dict[str, str] | None:
    """Call the LLM to produce manifest/content.js/content.css. Returns None on failure."""
    client = get_secondary_client(provider)
    model = get_provider_config(provider).get("primary_model") or get_provider_config(
        provider
    )["secondary_model"]

    retrieved_context = "\n".join(f"- {snippet}" for snippet in rag_snippets)
    user_prompt = (
        f"User request: {_strip_chip_html(query)}\n\n"
        f"Target URLs (use these as manifest content_scripts.matches): "
        f"{json.dumps(target_urls)}\n"
        f"Extension display name: {extension_name}\n\n"
        "If the request is bespoke (not a single off-the-shelf pattern), still apply "
        "the site overviews and DOM notes below, and invent selectors that match the "
        "user’s specific goal for that page structure.\n\n"
        f"Retrieved implementation context:\n{retrieved_context}\n\n"
        + (
            "The previous output failed these checks. Fix every issue:\n"
            + "\n".join(f"- {issue}" for issue in quality_feedback)
            + "\n\n"
            if quality_feedback
            else ""
        )
        + "Produce the JSON object now."
    )

    try:
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": CODEGEN_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
            ),
            timeout=CODEGEN_LLM_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        logger.warning("Codegen LLM call timed out after %ss", CODEGEN_LLM_TIMEOUT_SECONDS)
        return None
    except Exception as exc:
        logger.warning("Codegen LLM call failed: %s", exc)
        return None

    raw = response.choices[0].message.content or ""
    parsed = _extract_json(raw)
    if not parsed or not isinstance(parsed, dict):
        logger.warning("Codegen LLM returned unparseable output: %s", raw[:200])
        return None

    manifest = parsed.get("manifest")
    content_js = parsed.get("content_js")
    content_css = parsed.get("content_css", "")
    if not isinstance(manifest, dict) or not isinstance(content_js, str):
        logger.warning("Codegen LLM output missing required keys")
        return None
    if not isinstance(content_css, str):
        content_css = ""

    manifest.setdefault("manifest_version", 3)
    manifest.setdefault("version", "1.0")
    manifest.setdefault("name", extension_name[:45])
    manifest["description"] = _strip_chip_html(str(manifest.get("description", extension_name)))[:120]

    scripts = manifest.get("content_scripts") or []
    if not scripts:
        manifest["content_scripts"] = [
            {
                "matches": target_urls,
                "css": ["content.css"] if content_css else [],
                "js": ["content.js"],
                "run_at": "document_idle",
            }
        ]

    has_css = bool(content_css.strip())
    _sanitize_manifest(manifest, has_css=has_css)
    for script in manifest.get("content_scripts") or []:
        if isinstance(script, dict):
            # Structural DOM modification extensions are more reliable at document_idle.
            script["run_at"] = "document_idle"

    files = {
        "manifest.json": json.dumps(manifest, indent=2),
        "content.js": content_js,
    }
    if has_css:
        files["content.css"] = content_css
    return files


def _sanitize_manifest(manifest: dict[str, Any], *, has_css: bool) -> None:
    """Strip any manifest fields that reference files we are not generating."""
    allowed_files = {"content.js"} | ({"content.css"} if has_css else set())

    for key in ("icons", "web_accessible_resources", "action", "background", "options_page", "options_ui", "side_panel", "chrome_url_overrides", "devtools_page"):
        manifest.pop(key, None)

    cleaned_scripts: list[dict[str, Any]] = []
    for script in manifest.get("content_scripts") or []:
        if not isinstance(script, dict):
            continue
        js = [f for f in (script.get("js") or []) if f in allowed_files]
        css = [f for f in (script.get("css") or []) if f in allowed_files]
        if not js and not css:
            continue
        new_script = dict(script)
        if js:
            new_script["js"] = js
        else:
            new_script.pop("js", None)
        if css:
            new_script["css"] = css
        else:
            new_script.pop("css", None)
        cleaned_scripts.append(new_script)
    if cleaned_scripts:
        manifest["content_scripts"] = cleaned_scripts
    else:
        manifest["content_scripts"] = [
            {
                "matches": ["<all_urls>"],
                "js": ["content.js"],
                "run_at": "document_idle",
                **({"css": ["content.css"]} if has_css else {}),
            }
        ]


def _quality_issues(
    files: dict[str, str],
    target_urls: list[str],
    query: str,
    rag_snippets: list[str],
    focus_use_case_id: str | None = None,
) -> list[str]:
    issues: list[str] = []
    manifest_raw = files.get("manifest.json", "")
    content_js = files.get("content.js", "")
    content_css = files.get("content.css", "")

    if len(content_js.strip()) < 80:
        issues.append("content_js is empty or too small; implement meaningful runtime logic.")
    if len(content_css.strip()) < 20:
        issues.append("content_css is empty or too small; include targeted CSS rules.")

    try:
        manifest = json.loads(manifest_raw)
    except json.JSONDecodeError:
        return ["manifest.json is not valid JSON."]

    scripts = manifest.get("content_scripts")
    if not isinstance(scripts, list) or not scripts:
        issues.append("manifest.content_scripts must include a content script entry.")
        return issues

    first_script = scripts[0] if isinstance(scripts[0], dict) else {}
    matches = first_script.get("matches") or []
    if sorted(matches) != sorted(target_urls):
        issues.append("manifest content_scripts.matches must exactly use the supplied target URLs.")
    if "content.js" not in (first_script.get("js") or []):
        issues.append("manifest content script must reference content.js.")
    if content_css.strip() and "content.css" not in (first_script.get("css") or []):
        issues.append("manifest content script must reference content.css when CSS is generated.")
    run_at = str(first_script.get("run_at", "document_idle")).lower()

    combined = f"{content_js}\n{content_css}".lower()
    if re.search(r"\[class\*=['\"][^'\"]+['\"]\s+i?\]", combined):
        issues.append("Do not use broad class substring selectors like [class*=...].")
    if "document.body.style" in combined or "document.documentelement.style" in combined:
        issues.append("Do not style or hide document.body/documentElement.")
    if "display', 'none" in combined and "document.queryselectorall('*')" in combined:
        issues.append("Do not iterate over every DOM node and hide matches.")
    if "textcontent" in combined and "closest('section, article, nav, aside" in combined:
        issues.append("Do not combine broad textContent matching with generic ancestor hiding.")
    if "closest('section, article" in combined or 'closest("section, article' in combined:
        issues.append("Avoid generic closest('section, article...') ancestors; use site-specific containers.")
    if run_at == "document_start" and "observe(document.body" in combined:
        issues.append("Avoid observing document.body at document_start without a body-ready guard; use document_idle or wait for body.")
    if run_at == "document_start" and "queryselectorall(" in combined and "domcontentloaded" not in combined:
        issues.append("document_start scripts that query the DOM must wait for DOMContentLoaded or body availability.")

    retrieved_tokens = [
        token.strip()
        for snippet in rag_snippets
        for token in re.findall(r"`([^`]+)`", snippet)
        if len(token.strip()) > 2
    ]
    selector_like_tokens = [
        token.lower()
        for token in retrieved_tokens
        if any(ch in token for ch in ("/", "[", "]", "=", "-", ":", "."))
    ][:10]
    query_lower = query.lower()
    query_tokens = set(re.findall(r"[a-z0-9]+", query_lower))
    explicit_element_query = any(
        marker in query_lower
        for marker in ("clicked", "selected element", "orange", "chip", "selector")
    )
    if (
        explicit_element_query
        and selector_like_tokens
        and not any(token in combined for token in selector_like_tokens)
    ):
        issues.append(
            "Generated code does not reflect retrieved site implementation context; include at least some of the provided selectors/attributes."
        )

    matched_entries = retrieve_context_entries(query, target_urls, limit=8)
    for entry in matched_entries:
        entry_id = str(entry.get("id", ""))
        if focus_use_case_id and entry_id != focus_use_case_id:
            continue
        if not focus_use_case_id and not _entry_has_site_alignment(entry, query_lower, target_urls):
            continue
        terms = [str(term).lower() for term in entry.get("terms", [])]
        if terms and not any(
            (term in query_lower) or (term in query_tokens)
            for term in terms
        ):
            # Skip cross-case entries that only matched because the site is similar.
            continue
        rule = USE_CASE_RULES.get(entry_id)
        if not rule:
            continue
        required_any = [str(s).lower() for s in rule.get("required_any", [])]
        min_signals = int(rule.get("min_signals", 1))
        found = sum(1 for signal in required_any if signal in combined)
        if required_any and found < min_signals:
            issues.append(
                f"Use-case '{entry.get('title')}' is under-specified; expected >= {min_signals} matching DOM signals."
            )

        behavior = str(rule.get("behavior", "")).lower()
        if behavior == "hide" and not _has_hide_behavior(combined):
            issues.append(f"Use-case '{entry.get('title')}' should visibly hide/remove target UI.")
        if behavior == "highlight" and not _has_highlight_behavior(combined):
            issues.append(f"Use-case '{entry.get('title')}' should add a visible highlight style/class.")
        if behavior == "inject" and not _has_inject_behavior(combined):
            issues.append(f"Use-case '{entry.get('title')}' should inject a small DOM marker/banner.")
        if behavior == "collapse" and not _has_collapse_behavior(combined):
            issues.append(f"Use-case '{entry.get('title')}' should collapse/expand comment bodies safely.")
        if behavior == "classify" and "/api/classify" not in combined:
            issues.append(f"Use-case '{entry.get('title')}' should use /api/classify for semantic matching.")
        if rule.get("require_mutation_observer") and "mutationobserver" not in combined:
            issues.append(f"Use-case '{entry.get('title')}' must include MutationObserver for SPA rerenders.")

    targets_lower = " ".join(target_urls).lower()
    if "youtube" in query_lower or "youtube" in targets_lower:
        if "shorts" in query_lower:
            if "/shorts" not in combined:
                issues.append("YouTube Shorts behavior must key off `/shorts` URLs or attributes.")
            yt_signals = (
                "ytd-reel-shelf-renderer",
                "ytd-guide-entry-renderer",
                "ytd-mini-guide-entry-renderer",
                "ytd-rich-item-renderer",
                "ytd-video-renderer",
            )
            if not any(signal in combined for signal in yt_signals):
                issues.append("YouTube Shorts removal must target YouTube-specific containers, not generic nodes.")
            if "mutationobserver" not in combined:
                issues.append("YouTube Shorts removal must watch SPA rerenders with a MutationObserver.")
    if "reddit" in query_lower or "reddit" in targets_lower:
        if any(term in query_lower for term in ("recent", "sidebar", "right")):
            required_signals = (
                "aside",
                "complementary",
                "shreddit",
                "reddit-sidebar",
                "getboundingclientrect",
                "right",
                "aria-label",
                "data-testid",
            )
            signal_count = sum(1 for signal in required_signals if signal in combined)
            if signal_count < 4:
                issues.append(
                    "Reddit right-rail widgets need multiple DOM/layout signals: include aside/complementary/custom-element selectors plus right-side or bounding-box checks."
                )
            if 'div[data-testid="sidebar-widget"]' in combined and signal_count < 5:
                issues.append(
                    "Do not rely primarily on div[data-testid='sidebar-widget']; add modern Reddit custom elements, ARIA/text, and right-rail fallbacks."
                )
            if "recent" not in combined:
                issues.append("Recent-posts requests must explicitly look for recent/recent posts labels or attributes.")

    return issues


def _has_hide_behavior(text: str) -> bool:
    return any(
        signal in text
        for signal in (
            "display: none",
            "display:none",
            "visibility: hidden",
            ".remove(",
            "bf-hidden",
            "classlist.add(",
        )
    )


def _has_highlight_behavior(text: str) -> bool:
    return any(
        signal in text
        for signal in (
            "highlight",
            "background",
            "outline",
            "box-shadow",
            "border",
            "classlist.add(",
        )
    )


def _has_inject_behavior(text: str) -> bool:
    return any(
        signal in text
        for signal in (
            "createelement(",
            "appendchild(",
            "insertbefore(",
            "prepend(",
            "dataset.",
        )
    )


def _has_collapse_behavior(text: str) -> bool:
    return any(
        signal in text
        for signal in (
            "collapse",
            "aria-expanded",
            ".click(",
            "toggle",
            "hidden",
        )
    )


async def _generate_checked(
    query: str,
    target_urls: list[str],
    extension_name: str,
    provider: str,
    rag_snippets: list[str],
) -> dict[str, str] | None:
    feedback: list[str] | None = None
    for attempt in range(CODEGEN_MAX_ATTEMPTS):
        files = await _generate_with_llm(
            query=query,
            target_urls=target_urls,
            extension_name=extension_name,
            provider=provider,
            rag_snippets=rag_snippets,
            quality_feedback=feedback,
        )
        if files is None:
            feedback = [
                "The response was missing valid manifest/content_js/content_css JSON or timed out. Return valid JSON quickly."
            ]
            continue

        issues = _quality_issues(files, target_urls, query, rag_snippets)
        if not issues:
            return files

        logger.warning("Codegen quality check failed on attempt %s: %s", attempt + 1, issues)
        feedback = issues

    return None


async def run_codegen(request: CodegenRequest) -> CodegenResult:
    spec = request.spec
    source = "llm"
    deterministic = build_deterministic_files(
        query=spec.behavior,
        target_urls=spec.target_urls,
        extension_name=spec.name,
    )
    if deterministic:
        files, use_case_id = deterministic
        deterministic_issues = _quality_issues(
            files,
            spec.target_urls,
            spec.behavior,
            request.rag.snippets,
            focus_use_case_id=use_case_id,
        )
        if deterministic_issues:
            logger.warning(
                "Deterministic template %s failed quality checks: %s",
                use_case_id,
                deterministic_issues,
            )
            files = await _generate_checked(
                query=spec.behavior,
                target_urls=spec.target_urls,
                extension_name=spec.name,
                provider=request.build.provider,
                rag_snippets=request.rag.snippets,
            )
        else:
            source = f"deterministic:{use_case_id}"
    else:
        files = await _generate_checked(
            query=spec.behavior,
            target_urls=spec.target_urls,
            extension_name=spec.name,
            provider=request.build.provider,
            rag_snippets=request.rag.snippets,
        )

    if files is None:
        raise RuntimeError(
            "Code generation failed (LLM unavailable, timed out, or quota exhausted). "
            "No extension was produced. Retry shortly or switch provider/API quota."
        )

    response = await backend_client.write_files(spec.project_id, files)
    written = response.get("written_files", list(files))
    return CodegenResult(
        job_id=request.job_id,
        project_id=spec.project_id,
        files=files,
        written_files=written,
        summary=f"Wrote {len(written)} extension file(s): {', '.join(written)}. Source={source}.",
    )
