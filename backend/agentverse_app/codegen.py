"""Extension Codegen Agent role."""

from __future__ import annotations

import json
import re

from agentverse_app import backend_client
from agentverse_app.messages import CodegenRequest, CodegenResult


def _selector_terms(query: str) -> list[str]:
    lowered = query.lower()
    known_terms = [
        "shorts",
        "reels",
        "messages",
        "direct",
        "ads",
        "sponsored",
        "sidebar",
        "notifications",
    ]
    terms = [term for term in known_terms if term in lowered]
    if terms:
        return terms
    words = [w for w in re.findall(r"[a-z0-9]+", lowered) if len(w) > 3]
    return words[:4] or ["browser-forge-hidden"]


def _css_for_terms(terms: list[str]) -> str:
    selectors: list[str] = []
    for term in terms:
        selectors.extend(
            [
                f'a[href*="{term}" i]',
                f'[aria-label*="{term}" i]',
                f'[data-testid*="{term}" i]',
                f'[class*="{term}" i]',
            ]
        )
    return ",\n".join(selectors) + ",\n[data-browser-forge-hidden=\"true\"] {\n  display: none !important;\n}\n"


def _content_script_for_terms(terms: list[str]) -> str:
    terms_json = json.dumps(terms)
    return f"""const EVOLVE_TERMS = {terms_json};

function shouldHide(element) {{
  const text = [
    element.getAttribute('href'),
    element.getAttribute('aria-label'),
    element.getAttribute('data-testid'),
    element.className,
    element.textContent,
  ]
    .filter(Boolean)
    .join(' ')
    .toLowerCase();

  return EVOLVE_TERMS.some((term) => text.includes(term));
}}

function hideElement(element) {{
  if (!element || element.dataset.browserForgeHidden === 'true') {{
    return;
  }}
  element.dataset.browserForgeHidden = 'true';
  element.style.setProperty('display', 'none', 'important');
}}

function applyBrowserForgeChanges() {{
  document
    .querySelectorAll('a, button, [role=\"button\"], section, aside, div')
    .forEach((element) => {{
      if (shouldHide(element)) {{
        const container = element.closest('article, section, nav, aside, li, div[role=\"button\"]');
        hideElement(container || element);
      }}
    }});
}}

applyBrowserForgeChanges();
setInterval(applyBrowserForgeChanges, 1000);

new MutationObserver(applyBrowserForgeChanges).observe(document.documentElement, {{
  childList: true,
  subtree: true,
}});
"""


async def run_codegen(request: CodegenRequest) -> CodegenResult:
    spec = request.spec
    terms = _selector_terms(spec.behavior)
    manifest = {
        "manifest_version": 3,
        "name": spec.name[:45],
        "version": "1.0",
        "description": spec.description[:120],
        "content_scripts": [
            {
                "matches": spec.target_urls,
                "css": ["content.css"],
                "js": ["content.js"],
                "run_at": "document_idle",
            }
        ],
    }
    files = {
        "manifest.json": json.dumps(manifest, indent=2),
        "content.css": _css_for_terms(terms),
        "content.js": _content_script_for_terms(terms),
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
