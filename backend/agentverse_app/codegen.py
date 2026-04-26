"""Extension Codegen Agent role."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from agentverse_app import backend_client
from agentverse_app.messages import CodegenRequest, CodegenResult
from utils.config import get_provider_config, get_secondary_client

logger = logging.getLogger(__name__)


CODEGEN_SYSTEM_PROMPT = """\
You are an expert Chrome extension engineer. You write Manifest V3 content-script \
extensions that perform precise DOM modifications on specific websites.

You will receive a user request describing a browser customization. Your job is to \
output a complete Chrome extension as JSON with exactly three files: manifest.json, \
content.js, and content.css. content.js and content.css must both contain meaningful \
implementation code; never leave either one empty.

Critical rules:
1. Use SITE-SPECIFIC selectors, not generic ones. Research the site's actual DOM \
   structure (e.g., for YouTube use `ytd-rich-section-renderer`, \
   `ytd-reel-shelf-renderer`, etc.; for Instagram use `[role="main"]` with specific \
   article selectors; for Twitter use `[data-testid="..."]`).
2. NEVER use overly broad selectors like `[class*="shorts" i]` or matching on \
   `textContent` of any element — they will hide entire page sections.
3. NEVER walk up to ancestor containers using generic tags like \
   `closest('section, article, nav, aside')` — you will hide the whole page. \
   Also never set `document.body.style.display` or `document.body.style.visibility` \
   to hide the entire page; direct style changes like `backgroundColor` are fine.
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

ELEMENT CONTEXT CHIPS:
When the user provides an "The user explicitly selected the following elements" block, it
contains the outerHTML of one specific instance of the element they want to target. Use it
to identify the correct tag names, class patterns, and attributes — then write a GENERAL
CSS selector that matches ALL similar elements on the page, not just that one instance.
Never copy the exact chip HTML verbatim as a selector. Infer the repeating pattern
(e.g. if the chip shows `<yt-img-shadow class="yt-img-shadow">` inside
`<ytd-rich-item-renderer>`, the correct selector is
`ytd-rich-item-renderer yt-img-shadow`, not a fragile nth-of-type chain).

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

SHADOW DOM WARNING:
12. NEVER target internal class names from YouTube's Web Component shadow trees. \
    Classes like `ytSpecAvatarShapeImageOverlays`, `ytSpecAvatarShapeImage`, or \
    any name prefixed with `ytSpec` live inside closed shadow roots — \
    `document.querySelectorAll` CANNOT reach them. Always select the outermost \
    custom-element tag or a stable light-DOM id/attribute instead.
    Known stable YouTube channel-avatar selectors:
    - Home feed card avatar: `ytd-rich-grid-media ytd-avatar-section`
    - Home feed avatar container: `ytd-rich-grid-media #avatar-container`
    - Search result author: `ytd-video-renderer #author-thumbnail`
    - Watch page sidebar card: `ytd-compact-video-renderer ytd-avatar-section`
    Same principle applies to ALL sites: never use classes that are nested inside \
    a shadow root — use the outer tag, id, or data-* attribute on the light DOM.

Output format: a single JSON object with exactly these keys:
{
  "manifest": { ... full manifest.json object ... },
  "content_js": "...full JS source...",
  "content_css": "...full CSS source..."
}

Output ONLY the JSON object, no prose, no markdown fences.
"""


def _extract_query_and_html(text: str) -> tuple[str, list[str]]:
    """Extract the clean query and the raw HTML from Browser Forge context chips."""
    html_chunks = []
    
    matches = re.finditer(r"<!--EVOLVE_CHIP_START:.*?-->(.*?)<!--EVOLVE_CHIP_END-->", text, flags=re.DOTALL)
    for match in matches:
        chunk = match.group(1).strip()
        if chunk:
            html_chunks.append(chunk)

    cleaned = re.sub(
        r"<!--EVOLVE_CHIP_START:.*?-->.*?<!--EVOLVE_CHIP_END-->",
        "",
        text,
        flags=re.DOTALL,
    )
    return re.sub(r"\s+", " ", cleaned).strip(), html_chunks


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


async def _generate_with_llm(
    query: str,
    target_urls: list[str],
    extension_name: str,
    provider: str,
    quality_feedback: list[str] | None = None,
) -> dict[str, str] | None:
    """Call the LLM to produce manifest/content.js/content.css. Returns None on failure."""
    client = get_secondary_client(provider)
    model = get_provider_config(provider).get("primary_model") or get_provider_config(
        provider
    )["secondary_model"]

    clean_query, html_chunks = _extract_query_and_html(query)
    
    html_context = ""
    if html_chunks:
        html_context = (
            "The user explicitly selected the following elements on their screen. "
            "Here is their exact HTML structure. Use these tags/classes to write perfectly accurate CSS selectors:\n"
            + "\n---\n".join(html_chunks)
            + "\n\n"
        )

    user_prompt = (
        f"User request: {clean_query}\n\n"
        f"Target URLs (use these as manifest content_scripts.matches): "
        f"{json.dumps(target_urls)}\n"
        f"Extension display name: {extension_name}\n\n"
        f"{html_context}"
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
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": CODEGEN_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
        )
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
    clean_query, _ = _extract_query_and_html(str(manifest.get("description", extension_name)))
    manifest["description"] = clean_query[:120]

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


def _quality_issues(files: dict[str, str], target_urls: list[str]) -> list[str]:
    issues: list[str] = []
    manifest_raw = files.get("manifest.json", "")
    content_js = files.get("content.js", "")
    content_css = files.get("content.css", "")

    if len(content_js.strip()) < 80:
        issues.append("content_js is empty or too small; implement meaningful runtime logic.")
    if "content.css" in files and len(content_css.strip()) < 20:
        issues.append("content_css is present but too small; add meaningful CSS rules.")

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

    combined = f"{content_js}\n{content_css}".lower()
    if re.search(r"\[class\*=['\"][^'\"]+['\"]\s+i?\]", combined):
        issues.append("Do not use broad class substring selectors like [class*=...].")
    # Only block destructive body/html hiding, not legitimate style changes (e.g. background color).
    if re.search(r"document\.(body|documentelement)\.style\.(display|visibility)\s*=", combined):
        issues.append("Do not set display or visibility on document.body/documentElement.")
    if "display', 'none" in combined and "document.queryselectorall('*')" in combined:
        issues.append("Do not iterate over every DOM node and hide matches.")
    if "textcontent" in combined and "closest('section, article, nav, aside" in combined:
        issues.append("Do not combine broad textContent matching with generic ancestor hiding.")
    if "closest('section, article" in combined or 'closest("section, article' in combined:
        issues.append("Avoid generic closest('section, article...') ancestors; use site-specific containers.")

    return issues


async def _generate_checked(
    query: str,
    target_urls: list[str],
    extension_name: str,
    provider: str,
) -> dict[str, str] | None:
    feedback: list[str] | None = None
    for attempt in range(3):
        files = await _generate_with_llm(
            query=query,
            target_urls=target_urls,
            extension_name=extension_name,
            provider=provider,
            quality_feedback=feedback,
        )
        if files is None:
            feedback = ["The response was missing valid manifest/content_js/content_css JSON."]
            continue

        issues = _quality_issues(files, target_urls)
        if not issues:
            return files

        logger.warning("Codegen quality check failed on attempt %s: %s", attempt + 1, issues)
        feedback = issues

    return None


async def run_codegen(request: CodegenRequest) -> CodegenResult:
    spec = request.spec
    files = await _generate_checked(
        query=spec.behavior,
        target_urls=spec.target_urls,
        extension_name=spec.name,
        provider=request.build.provider,
    )

    if files is None:
        manifest = {
            "manifest_version": 3,
            "name": spec.name[:45],
            "version": "1.0",
            "description": _extract_query_and_html(spec.description)[0][:120],
            "content_scripts": [
                {
                    "matches": spec.target_urls,
                    "js": ["content.js"],
                    "run_at": "document_idle",
                }
            ],
        }
        files = {
            "manifest.json": json.dumps(manifest, indent=2),
            "content.js": (
                "// Codegen LLM unavailable — placeholder no-op.\n"
                "// Edit this file or retry the build to generate real logic.\n"
                "console.log('Browser Forge: codegen fallback active');\n"
            ),
        }

    response = await backend_client.write_files(spec.project_id, files)
    written = response.get("written_files", list(files))
    return CodegenResult(
        job_id=request.job_id,
        project_id=spec.project_id,
        files=files,
        written_files=written,
        summary=f"Wrote {len(written)} extension file(s): {', '.join(written)}.",
    )
