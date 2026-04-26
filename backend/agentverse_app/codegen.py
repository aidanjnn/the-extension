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
output a complete Chrome extension as JSON with three files: manifest.json, \
content.js, and content.css.

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
5. Use CSS `:has()` selectors where supported for clean hide rules.
6. Keep permissions minimal. content_scripts only — no service worker unless needed.
7. The manifest description must be a plain string, no HTML.

7. NEVER add `icons`, `web_accessible_resources`, `action`, `background`, or any \
   field that references files you are not generating. You only generate three \
   files: manifest.json, content.js, content.css. The manifest MUST NOT reference \
   any other file. No PNG icons, no popup HTML, no service worker.
8. NEVER include `permissions` unless the content script genuinely needs them. \
   Most hide-this-element tasks need none. Use `host_permissions` ONLY when you \
   need to fetch the local classification backend (see rule 9).

CONTENT CLASSIFICATION TASKS:
9. If the user's request requires deciding whether each item on the page matches \
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

10. For SIMPLE STRUCTURAL tasks (hide the Shorts shelf, remove the sidebar), use \
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


async def _generate_with_llm(
    query: str,
    target_urls: list[str],
    extension_name: str,
    provider: str,
) -> dict[str, str] | None:
    """Call the LLM to produce manifest/content.js/content.css. Returns None on failure."""
    client = get_secondary_client(provider)
    model = get_provider_config(provider).get("primary_model") or get_provider_config(
        provider
    )["secondary_model"]

    user_prompt = (
        f"User request: {_strip_chip_html(query)}\n\n"
        f"Target URLs (use these as manifest content_scripts.matches): "
        f"{json.dumps(target_urls)}\n"
        f"Extension display name: {extension_name}\n\n"
        "Produce the JSON object now."
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


async def run_codegen(request: CodegenRequest) -> CodegenResult:
    spec = request.spec
    files = await _generate_with_llm(
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
            "description": _strip_chip_html(spec.description)[:120],
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
