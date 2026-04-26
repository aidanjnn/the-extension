"""Deterministic extension generation for known product use-cases.

This module provides template-first generation for curated tasks so the system
can still produce valid, working extensions when LLM capacity is limited.
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable

from agentverse_app.nudges import (
    retrieve_context_entries,
    should_apply_deterministic_template,
)

LOCAL_CLASSIFY_ENDPOINT = "http://localhost:8000/api/classify"


def _manifest(
    *,
    name: str,
    target_urls: list[str],
    description: str,
    host_permissions: list[str] | None = None,
    background_js: bool = False,
) -> dict[str, Any]:
    manifest: dict[str, Any] = {
        "manifest_version": 3,
        "name": name[:45],
        "version": "1.0",
        "description": description[:120],
        "content_scripts": [
            {
                "matches": target_urls,
                "js": ["content.js"],
                "css": ["content.css"],
                "run_at": "document_idle",
            }
        ],
    }
    if background_js:
        manifest["background"] = {"service_worker": "background.js"}
    if host_permissions:
        manifest["host_permissions"] = host_permissions
    return manifest


def _base_css() -> str:
    return """
.bf-hidden { display: none !important; }

.bf-highlight {
  outline: 2px solid #ff8c00 !important;
  outline-offset: 2px !important;
  background: rgba(255, 140, 0, 0.14) !important;
}

.bf-warning {
  margin: 8px 0 !important;
  padding: 8px 10px !important;
  border-radius: 8px !important;
  border: 1px solid #ff9800 !important;
  background: #fff8e1 !important;
  color: #5f4200 !important;
  font-size: 12px !important;
  font-weight: 600 !important;
}

.bf-k-exam { background: rgba(211, 47, 47, 0.22) !important; }
.bf-k-meeting { background: rgba(2, 136, 209, 0.22) !important; }
.bf-k-deadline { background: rgba(245, 124, 0, 0.24) !important; }
""".strip()


def _runtime_wrapper(apply_logic: str, extra_logic: str = "") -> str:
    return f"""
const HIDDEN_CLASS = 'bf-hidden';
const HIGHLIGHT_CLASS = 'bf-highlight';
const WARNING_CLASS = 'bf-warning';
let rafToken = 0;

function hideNode(node) {{
  if (!node || !(node instanceof Element)) return;
  node.classList.add(HIDDEN_CLASS);
}}

function highlightNode(node) {{
  if (!node || !(node instanceof Element)) return;
  node.classList.add(HIGHLIGHT_CLASS);
}}

function safeClosest(node, selector) {{
  try {{
    return node?.closest(selector) || null;
  }} catch {{
    return null;
  }}
}}

{extra_logic}

function applyRules() {{
{apply_logic}
}}

function scheduleApply() {{
  if (rafToken) cancelAnimationFrame(rafToken);
  rafToken = requestAnimationFrame(() => {{
    rafToken = 0;
    try {{
      applyRules();
    }} catch (err) {{
      console.debug('Layer applyRules failed', err);
    }}
  }});
}}

function startObserver() {{
  scheduleApply();
  const root = document.documentElement || document.body;
  if (!root) return;
  const observer = new MutationObserver(() => scheduleApply());
  observer.observe(root, {{ childList: true, subtree: true }});
  window.addEventListener('popstate', scheduleApply);
  window.addEventListener('hashchange', scheduleApply);
}}

if (document.readyState === 'loading') {{
  document.addEventListener('DOMContentLoaded', startObserver, {{ once: true }});
}} else {{
  startObserver();
}}
""".strip()


def _extract_sender_hint(query: str) -> str:
    lowered = query.lower()
    quoted = re.findall(r"['\"]([^'\"]{2,50})['\"]", lowered)
    if quoted:
        return quoted[0].strip()
    match = re.search(r"from\s+(?:my\s+)?([a-z0-9 ._-]{2,50})", lowered)
    if match:
        return match.group(1).strip()
    for hint in ("boss", "professor", "team"):
        if hint in lowered:
            return hint
    return "important"


def _extract_keywords(query: str, defaults: list[str]) -> list[str]:
    lowered = query.lower()
    quoted = [token.strip() for token in re.findall(r"['\"]([^'\"]{2,30})['\"]", lowered)]
    if quoted:
        return quoted[:5]
    if "keywords like" in lowered:
        tail = lowered.split("keywords like", 1)[1]
        raw = re.split(r"[.;\n]", tail)[0]
        parts = [p.strip() for p in re.split(r",| and ", raw) if p.strip()]
        if parts:
            return parts[:5]
    return defaults[:]


def _extract_nav_targets(query: str) -> tuple[list[str], list[str]]:
    lowered = query.lower()
    href_targets: list[str] = []
    text_targets: list[str] = []
    if "reels" in lowered:
        href_targets.append("/reels")
        text_targets.append("reels")
    if "explore" in lowered:
        href_targets.append("/explore")
        text_targets.append("explore")
    if any(term in lowered for term in ("message", "messages", "dm", "direct")):
        href_targets.append("/direct")
        text_targets.extend(["messages", "direct"])
    if not href_targets:
        href_targets = ["/reels", "/explore", "/direct"]
        text_targets = ["reels", "explore", "messages", "direct"]
    return href_targets, text_targets


def _build_classification_template(
    *,
    query: str,
    item_selectors: list[str],
    text_selectors: list[str],
    id_attr_candidates: list[str],
) -> str:
    return f"""
const FILTER_DESCRIPTION = {json.dumps(query.strip())};
const ITEM_SELECTORS = {json.dumps(item_selectors)};
const TEXT_SELECTORS = {json.dumps(text_selectors)};
const ID_ATTRS = {json.dumps(id_attr_candidates)};
const CLASSIFY_ENDPOINT = {json.dumps(LOCAL_CLASSIFY_ENDPOINT)};
const HIDDEN_CLASS = 'bf-hidden';
const cache = new Map();
let timer = null;

function getNodeId(node) {{
  for (const attr of ID_ATTRS) {{
    const value = node.getAttribute?.(attr);
    if (value) return `${{attr}}:${{value}}`;
  }}
  const link = node.querySelector?.('a[href]');
  if (link) {{
    const href = link.getAttribute('href') || '';
    if (href) return `href:${{href}}`;
  }}
  return `idx:${{Array.from(document.querySelectorAll('*')).indexOf(node)}}`;
}}

function getNodeText(node) {{
  const parts = [];
  for (const selector of TEXT_SELECTORS) {{
    node.querySelectorAll(selector).forEach((el) => {{
      const text = (el.textContent || '').trim();
      if (text) parts.push(text);
    }});
  }}
  if (parts.length === 0) {{
    parts.push((node.textContent || '').trim());
  }}
  return parts.join(' ').replace(/\\s+/g, ' ').slice(0, 300);
}}

function collectItems() {{
  const seen = new Set();
  const items = [];
  for (const selector of ITEM_SELECTORS) {{
    document.querySelectorAll(selector).forEach((node) => {{
      if (!(node instanceof Element)) return;
      if (seen.has(node)) return;
      seen.add(node);
      const id = getNodeId(node);
      const text = getNodeText(node);
      if (!id || !text) return;
      items.push({{ id, text, node }});
    }});
  }}
  return items;
}}

function applyCachedVisibility(items) {{
  for (const item of items) {{
    if (!cache.has(item.id)) {{
      item.node.classList.remove(HIDDEN_CLASS);
      continue;
    }}
    const keep = cache.get(item.id) === true;
    item.node.classList.toggle(HIDDEN_CLASS, !keep);
  }}
}}

async function classify(items) {{
  const payload = items
    .filter((item) => !cache.has(item.id))
    .slice(0, 30)
    .map((item) => ({{ id: item.id, text: item.text }}));
  if (payload.length === 0) return;
  try {{
    const data = await classifyInBackground(payload);
    if (!data?.ok) return;
    const matches = new Set(Array.isArray(data?.matches) ? data.matches.map(String) : []);
    for (const item of payload) {{
      cache.set(item.id, matches.has(item.id));
    }}
  }} catch {{
    // Keep items visible on classify failure.
  }}
}}

function classifyInBackground(items) {{
  return new Promise((resolve) => {{
    if (typeof chrome === 'undefined' || !chrome.runtime?.sendMessage) {{
      resolve({{ ok: false, matches: [] }});
      return;
    }}
    chrome.runtime.sendMessage(
      {{
        type: 'LAYER_CLASSIFY_ITEMS',
        endpoint: CLASSIFY_ENDPOINT,
        filter_description: FILTER_DESCRIPTION,
        items,
      }},
      (response) => {{
        if (chrome.runtime.lastError || !response?.ok) {{
          resolve({{ ok: false, matches: [] }});
          return;
        }}
        resolve(response);
      }},
    );
  }});
}}

async function run() {{
  const items = collectItems();
  applyCachedVisibility(items);
  await classify(items);
  applyCachedVisibility(items);
}}

function schedule() {{
  if (timer) clearTimeout(timer);
  timer = setTimeout(() => {{ void run(); }}, 280);
}}

if (document.readyState === 'loading') {{
  document.addEventListener('DOMContentLoaded', () => {{ void run(); }}, {{ once: true }});
}} else {{
  void run();
}}

const root = document.documentElement || document.body;
if (root) {{
  const observer = new MutationObserver(() => schedule());
  observer.observe(root, {{ childList: true, subtree: true }});
}}
window.addEventListener('popstate', () => {{ void run(); }});
window.addEventListener('hashchange', () => {{ void run(); }});
""".strip()


def _classification_background_script() -> str:
    return f"""
chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {{
  if (!message || message.type !== 'LAYER_CLASSIFY_ITEMS') return false;

  const endpoint =
    typeof message.endpoint === 'string'
      ? message.endpoint
      : {json.dumps(LOCAL_CLASSIFY_ENDPOINT)};
  const filterDescription =
    typeof message.filter_description === 'string'
      ? message.filter_description
      : '';
  const items = Array.isArray(message.items) ? message.items : [];

  (async () => {{
    try {{
      const response = await fetch(endpoint, {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{
          filter_description: filterDescription,
          items,
        }}),
      }});
      if (!response.ok) {{
        sendResponse({{ ok: false, matches: [], error: `HTTP ${{response.status}}` }});
        return;
      }}
      const data = await response.json();
      sendResponse({{
        ok: true,
        matches: Array.isArray(data?.matches) ? data.matches.map(String) : [],
      }});
    }} catch (error) {{
      sendResponse({{
        ok: false,
        matches: [],
        error: error instanceof Error ? error.message : String(error),
      }});
    }}
  }})();

  return true;
}});
""".strip()


def _files(
    name: str,
    target_urls: list[str],
    description: str,
    content_js: str,
    content_css: str | None = None,
    host_permissions: list[str] | None = None,
    background_js: str | None = None,
) -> dict[str, str]:
    css = content_css or _base_css()
    files = {
        "manifest.json": json.dumps(
            _manifest(
                name=name,
                target_urls=target_urls,
                description=description,
                host_permissions=host_permissions,
                background_js=bool(background_js),
            ),
            indent=2,
        ),
        "content.js": content_js,
        "content.css": css,
    }
    if background_js:
        files["background.js"] = background_js
    return files


def _youtube_shorts(query: str, target_urls: list[str], name: str) -> dict[str, str]:
    js = _runtime_wrapper(
        """
  const shortsAnchors = document.querySelectorAll("a[href^='/shorts'], a[href*='/shorts/']");
  shortsAnchors.forEach((anchor) => {
    const owner =
      safeClosest(anchor, 'ytd-rich-item-renderer, ytd-video-renderer, ytd-compact-video-renderer, ytd-grid-video-renderer, ytd-guide-entry-renderer, ytd-mini-guide-entry-renderer') ||
      safeClosest(anchor, 'li, article, section, div');
    hideNode(owner || anchor);
  });
  document.querySelectorAll('ytd-reel-shelf-renderer, ytd-rich-section-renderer').forEach((section) => {
    const text = (section.textContent || '').toLowerCase();
    if (text.includes('shorts')) hideNode(section);
  });
""",
    )
    return _files(name, target_urls, "Hide YouTube Shorts UI elements.", js)


def _youtube_comments(query: str, target_urls: list[str], name: str) -> dict[str, str]:
    js = _runtime_wrapper(
        """
  document.querySelectorAll('#comments, ytd-comments, ytd-comment-thread-renderer').forEach((node) => hideNode(node));
""",
    )
    return _files(name, target_urls, "Hide YouTube comments section.", js)


def _youtube_recommendations(query: str, target_urls: list[str], name: str) -> dict[str, str]:
    js = _runtime_wrapper(
        """
  if (!location.pathname.startsWith('/watch')) return;
  document.querySelectorAll('#secondary, ytd-watch-next-secondary-results-renderer').forEach((node) => hideNode(node));
""",
    )
    return _files(name, target_urls, "Hide YouTube recommended sidebar.", js)


def _youtube_keyword_filter(query: str, target_urls: list[str], name: str) -> dict[str, str]:
    js = _build_classification_template(
        query=query,
        item_selectors=[
            "ytd-rich-item-renderer",
            "ytd-video-renderer",
            "ytd-compact-video-renderer",
            "ytd-grid-video-renderer",
        ],
        text_selectors=["#video-title", "#channel-name", "#metadata-line", "#description-text"],
        id_attr_candidates=["data-context-item-id", "data-video-id"],
    )
    return _files(
        name,
        target_urls,
        "Filter YouTube videos by semantic criteria.",
        js,
        host_permissions=["http://localhost:8000/*"],
        background_js=_classification_background_script(),
    )


def _instagram_nav(query: str, target_urls: list[str], name: str) -> dict[str, str]:
    href_targets, text_targets = _extract_nav_targets(query)
    js = _runtime_wrapper(
        f"""
  const hrefTargets = {json.dumps(href_targets)};
  const textTargets = {json.dumps(text_targets)};
  document.querySelectorAll("nav a[href], a[href]").forEach((anchor) => {{
    const href = (anchor.getAttribute('href') || '').toLowerCase();
    const text = (anchor.textContent || '').toLowerCase();
    const aria = (anchor.getAttribute('aria-label') || '').toLowerCase();
    const matchesHref = hrefTargets.some((token) => href.includes(token));
    const matchesText = textTargets.some((token) => text.includes(token) || aria.includes(token));
    if (!matchesHref && !matchesText) return;
    const owner = safeClosest(anchor, 'li, [role=\"listitem\"], a, div');
    hideNode(owner || anchor);
  }});
""",
    )
    return _files(name, target_urls, "Hide selected Instagram sidebar buttons.", js)


def _instagram_suggested_posts(query: str, target_urls: list[str], name: str) -> dict[str, str]:
    js = _runtime_wrapper(
        """
  const patterns = ['suggested for you', 'suggested', 'follow'];
  document.querySelectorAll('article, div[role="article"]').forEach((article) => {
    const text = (article.textContent || '').toLowerCase();
    if (patterns.some((p) => text.includes(p))) hideNode(article);
  });
""",
    )
    return _files(name, target_urls, "Hide Instagram suggested posts cards.", js)


def _instagram_floating_messages(query: str, target_urls: list[str], name: str) -> dict[str, str]:
    js = _runtime_wrapper(
        """
  document.querySelectorAll('div, aside, section').forEach((node) => {
    const style = window.getComputedStyle(node);
    if (style.position !== 'fixed') return;
    const rect = node.getBoundingClientRect();
    if (rect.right < window.innerWidth * 0.55 || rect.top < window.innerHeight * 0.45) return;
    const text = (node.textContent || '').toLowerCase();
    const hasDirectLink = Boolean(node.querySelector('a[href*="/direct"]'));
    if (hasDirectLink || text.includes('messages') || text.includes('direct')) {
      hideNode(node);
    }
  });
""",
    )
    return _files(name, target_urls, "Hide Instagram floating messages drawer.", js)


def _instagram_engagement_counts(query: str, target_urls: list[str], name: str) -> dict[str, str]:
    js = _runtime_wrapper(
        """
  const countPattern = /(liked by|\\d+[\\d,\\.]*\\s+(likes?|comments?))/i;
  document.querySelectorAll('article span, article div').forEach((node) => {
    if (!(node instanceof Element)) return;
    if (node.closest('button')) return;
    const text = (node.textContent || '').trim();
    if (!countPattern.test(text)) return;
    if (text.length > 120) return;
    hideNode(node);
  });
""",
    )
    return _files(name, target_urls, "Hide Instagram likes/comments counts.", js)


def _gmail_tabs(query: str, target_urls: list[str], name: str) -> dict[str, str]:
    js = _runtime_wrapper(
        """
  const tabLabels = ['promotions', 'social'];
  document.querySelectorAll('[role="tab"], [role="tablist"] [aria-label]').forEach((tab) => {
    const text = ((tab.textContent || '') + ' ' + (tab.getAttribute('aria-label') || '')).toLowerCase();
    if (tabLabels.some((label) => text.includes(label))) hideNode(tab);
  });
""",
    )
    return _files(name, target_urls, "Hide Gmail Promotions and Social tabs.", js)


def _gmail_sender_highlight(query: str, target_urls: list[str], name: str) -> dict[str, str]:
    sender = _extract_sender_hint(query)
    js = _runtime_wrapper(
        f"""
  const senderHint = {json.dumps(sender)};
  document.querySelectorAll('tr.zA, [role="row"]').forEach((row) => {{
    const text = (row.textContent || '').toLowerCase();
    const unread = row.classList.contains('zE') || row.getAttribute('aria-label')?.toLowerCase().includes('unread');
    if (!unread) return;
    if (text.includes(senderHint)) highlightNode(row);
  }});
""",
    )
    return _files(name, target_urls, f"Highlight unread Gmail rows from sender: {sender}.", js)


def _gmail_focus(query: str, target_urls: list[str], name: str) -> dict[str, str]:
    js = _runtime_wrapper(
        """
  const selectors = [
    'div[role="navigation"]',
    'div[aria-label*="Meet"]',
    'div[aria-label*="Chat"]',
    'div[aria-label*="Side panel"]',
    'div[aria-label*="Advertisement"]',
  ];
  selectors.forEach((selector) => {
    document.querySelectorAll(selector).forEach((node) => hideNode(node));
  });
""",
    )
    return _files(name, target_urls, "Enable Gmail focus mode by hiding side distractions.", js)


def _email_deadlines(query: str, target_urls: list[str], name: str) -> dict[str, str]:
    js = _build_classification_template(
        query=query,
        item_selectors=["tr.zA", '[role="row"]', '[data-convid]'],
        text_selectors=["span[email]", "span", "div", "strong"],
        id_attr_candidates=["data-legacy-thread-id", "data-convid", "id"],
    )
    return _files(
        name,
        target_urls,
        "Highlight deadline/action emails using semantic classification.",
        js,
        host_permissions=["http://localhost:8000/*"],
        background_js=_classification_background_script(),
    )


def _outlook_panels(query: str, target_urls: list[str], name: str) -> dict[str, str]:
    js = _runtime_wrapper(
        """
  const promoWords = ['advertisement', 'premium', 'upgrade', 'suggested', 'promoted'];
  document.querySelectorAll('aside, [role="complementary"], div').forEach((panel) => {
    const text = ((panel.getAttribute('aria-label') || '') + ' ' + (panel.textContent || '')).toLowerCase();
    if (!promoWords.some((word) => text.includes(word))) return;
    hideNode(panel);
  });
""",
    )
    return _files(name, target_urls, "Hide Outlook promotional/ads panels.", js)


def _outlook_highlight_sender(query: str, target_urls: list[str], name: str) -> dict[str, str]:
    sender = _extract_sender_hint(query)
    js = _runtime_wrapper(
        f"""
  const senderHint = {json.dumps(sender)};
  document.querySelectorAll('[role="row"], [data-convid], div[draggable="true"]').forEach((row) => {{
    const text = (row.textContent || '').toLowerCase();
    if (text.includes(senderHint)) highlightNode(row);
  }});
""",
    )
    return _files(name, target_urls, f"Highlight Outlook sender rows for: {sender}.", js)


def _calendar_meeting_prep(query: str, target_urls: list[str], name: str) -> dict[str, str]:
    js = _runtime_wrapper(
        """
  const hosts = document.querySelectorAll('[role="dialog"], [data-eventid], [aria-label*="event"], section');
  hosts.forEach((host) => {
    if (!(host instanceof Element)) return;
    if (host.querySelector('[data-bf-meeting-prep="1"]')) return;
    const text = (host.textContent || '').toLowerCase();
    if (!text.includes('meeting')) return;
    const banner = document.createElement('div');
    banner.className = WARNING_CLASS;
    banner.dataset.bfMeetingPrep = '1';
    banner.textContent = 'Meeting prep: confirm agenda, attendees, link, and action items.';
    host.prepend(banner);
  });
""",
    )
    return _files(name, target_urls, "Inject a meeting prep banner for calendar events.", js)


def _google_calendar_keywords(query: str, target_urls: list[str], name: str) -> dict[str, str]:
    keywords = _extract_keywords(query, ["exam", "meeting", "deadline"])
    js = _runtime_wrapper(
        f"""
  const keywords = {json.dumps(keywords)};
  document.querySelectorAll('[data-eventid], [role="button"], a[href*="event"]').forEach((eventNode) => {{
    const text = ((eventNode.getAttribute('aria-label') || '') + ' ' + (eventNode.textContent || '')).toLowerCase();
    eventNode.classList.remove('bf-k-exam', 'bf-k-meeting', 'bf-k-deadline');
    if (keywords.some((k) => k.includes('exam')) && text.includes('exam')) eventNode.classList.add('bf-k-exam');
    if (keywords.some((k) => k.includes('meeting')) && text.includes('meeting')) eventNode.classList.add('bf-k-meeting');
    if (keywords.some((k) => k.includes('deadline') || k.includes('due')) && (text.includes('deadline') || text.includes('due'))) {{
      eventNode.classList.add('bf-k-deadline');
    }}
  }});
""",
    )
    return _files(name, target_urls, "Color-code calendar events by intent keywords.", js)


def _google_calendar_weekends(query: str, target_urls: list[str], name: str) -> dict[str, str]:
    js = _runtime_wrapper(
        """
  const weekendWords = ['saturday', 'sunday', 'sat', 'sun'];
  document.querySelectorAll('[role="columnheader"], [role="gridcell"], div').forEach((node) => {
    const label = ((node.getAttribute('aria-label') || '') + ' ' + (node.textContent || '')).toLowerCase();
    if (weekendWords.some((word) => label.includes(word))) hideNode(node);
  });
""",
    )
    return _files(name, target_urls, "Hide weekend columns in calendar views.", js)


def _calendar_missing_location(query: str, target_urls: list[str], name: str) -> dict[str, str]:
    js = _runtime_wrapper(
        """
  document.querySelectorAll('[role="dialog"], [data-eventid], section').forEach((panel) => {
    if (!(panel instanceof Element)) return;
    if (panel.querySelector('[data-bf-location-warning="1"]')) return;
    const text = (panel.textContent || '').toLowerCase();
    const hasLocation = text.includes('location') || text.includes('where:');
    const hasLink = text.includes('meet.google.com') || text.includes('zoom') || text.includes('teams');
    if (hasLocation || hasLink) return;
    const warning = document.createElement('div');
    warning.className = WARNING_CLASS;
    warning.dataset.bfLocationWarning = '1';
    warning.textContent = 'Warning: this event appears to have no location or meeting link.';
    panel.prepend(warning);
  });
""",
    )
    return _files(name, target_urls, "Warn on calendar events missing location or link.", js)


def _linkedin_feed(query: str, target_urls: list[str], name: str) -> dict[str, str]:
    js = _runtime_wrapper(
        """
  if (!location.pathname.startsWith('/feed')) return;
  document.querySelectorAll(
    '.scaffold-finite-scroll, .scaffold-finite-scroll__content, .feed-shared-update-v2, div[data-id^="urn:li:activity"]'
  ).forEach((node) => hideNode(node));
""",
    )
    return _files(name, target_urls, "Hide LinkedIn feed while preserving primary navigation.", js)


def _linkedin_promoted(query: str, target_urls: list[str], name: str) -> dict[str, str]:
    js = _runtime_wrapper(
        """
  document.querySelectorAll('.feed-shared-update-v2, div[data-id^="urn:li:activity"], article').forEach((card) => {
    const text = (card.textContent || '').toLowerCase();
    if (text.includes('promoted') || text.includes('sponsored') || text.includes('ad')) hideNode(card);
  });
""",
    )
    return _files(name, target_urls, "Hide LinkedIn promoted/sponsored feed posts.", js)


def _linkedin_page_filter(query: str, target_urls: list[str], name: str) -> dict[str, str]:
    js = _build_classification_template(
        query=query,
        item_selectors=["li.reusable-search__result-container", ".entity-result", ".feed-shared-update-v2"],
        text_selectors=[".entity-result__title-text", ".entity-result__summary", "h3", "span", "p"],
        id_attr_candidates=["data-urn", "id"],
    )
    return _files(
        name,
        target_urls,
        "Filter LinkedIn result/feed cards with semantic matching.",
        js,
        host_permissions=["http://localhost:8000/*"],
        background_js=_classification_background_script(),
    )


def _linkedin_hiring_highlight(query: str, target_urls: list[str], name: str) -> dict[str, str]:
    js = _runtime_wrapper(
        """
  document.querySelectorAll('.feed-shared-update-v2, div[data-id^="urn:li:activity"], article, .occludable-update').forEach((card) => {
    if (!(card instanceof Element)) return;
    const text = (card.textContent || '').toLowerCase().replace(/\\s+/g, ' ');
    const matchesHiring = HIRING_TERMS.some((term) => text.includes(term));
    card.classList.toggle('bf-linkedin-hiring-hit', matchesHiring);
    if (matchesHiring) ensureHiringBadge(card);
  });
""",
        """
const HIRING_TERMS = [
  'hiring',
  'we are hiring',
  "we're hiring",
  'internship',
  'internships',
  'intern ',
  ' intern,',
  ' intern.',
  'new grad',
  'new graduate',
  'graduate role',
  'entry level',
  'early career',
  'campus recruiting',
  'university recruiting',
  'open role',
  'open roles',
  'job opening',
  'job openings',
  'job opportunity',
  'career opportunity',
  'apply now',
  'applications are open',
  'recruiting',
  'recruiter',
  'referral',
  'software engineer intern',
  'swe intern',
  'summer intern',
  'summer 2026',
  'fall 2026',
  'join our team',
  'careers page',
  'open position',
  'open positions',
];

function ensureHiringBadge(card) {
  if (card.querySelector('.bf-linkedin-hiring-badge')) return;
  const badge = document.createElement('div');
  badge.className = 'bf-linkedin-hiring-badge';
  badge.textContent = 'HIRING';
  card.prepend(badge);
}
""",
    )
    css = """
.bf-linkedin-hiring-hit {
  border: 5px solid #ff1f1f !important;
  border-radius: 12px !important;
  box-shadow: 0 0 0 3px rgba(255, 255, 255, 0.9), 0 0 28px rgba(255, 0, 0, 0.75) !important;
  outline: 2px solid rgba(255, 0, 0, 0.55) !important;
  outline-offset: 4px !important;
  position: relative !important;
}

.bf-linkedin-hiring-badge {
  background: #e50914 !important;
  border: 2px solid #fff !important;
  border-radius: 999px !important;
  box-shadow: 0 8px 26px rgba(0, 0, 0, 0.35) !important;
  color: #fff !important;
  font: 900 13px/1 Arial, Helvetica, sans-serif !important;
  letter-spacing: 0 !important;
  padding: 8px 12px !important;
  position: absolute !important;
  right: 14px !important;
  top: 12px !important;
  z-index: 20 !important;
}
""".strip()
    return _files(name, target_urls, "Highlight LinkedIn hiring and internship posts.", js, css)


def _linkedin_real_talk(query: str, target_urls: list[str], name: str) -> dict[str, str]:
    js = _runtime_wrapper(
        """
  document.querySelectorAll(
    '.feed-shared-update-v2__description-wrapper, .update-components-text, .feed-shared-text, .feed-shared-inline-show-more-text, div[data-id^="urn:li:activity"]'
  ).forEach((node) => translateCorporateSpeak(node));
""",
        """
const TRANSLATIONS = [
  [/thrilled to announce/gi, '[bragging that]'],
  [/excited to (?:announce|share)/gi, '[posting for validation that]'],
  [/i(?:'|’)?m happy to share/gi, '[LinkedIn update:]'],
  [/humbled to (?:announce|share|be)/gi, '[weirdly proud to be]'],
  [/honou?red to (?:announce|share|be)/gi, '[name-dropping that I am]'],
  [/after much reflection/gi, '[after PR review]'],
  [/bittersweet/gi, '[trying to sound profound]'],
  [/next chapter/gi, '[new job]'],
  [/incredible journey/gi, '[job]'],
  [/dynamic environment/gi, '[chaos]'],
  [/cross-functional/gi, '[many meetings]'],
  [/synergy/gi, '[meetings]'],
  [/leveraging/gi, '[using]'],
  [/move fast/gi, '[rush]'],
  [/thought leader/gi, '[posting a lot]'],
  [/passionate about/gi, '[paid to care about]'],
];

function translateCorporateSpeak(node) {
  if (!(node instanceof Element)) return;
  if (node.dataset.bfRealTalk === '1') return;
  const original = node.innerHTML;
  let next = original;
  TRANSLATIONS.forEach(([pattern, replacement]) => {
    next = next.replace(pattern, `<span class="bf-real-talk-translation" title="Corporate translator">${replacement}</span>`);
  });
  if (next !== original) {
    node.innerHTML = next;
    node.dataset.bfRealTalk = '1';
  }
}
""",
    )
    css = """
.bf-real-talk-translation {
  background: #ffe45c !important;
  border: 1px solid #b58900 !important;
  border-radius: 4px !important;
  color: #141414 !important;
  display: inline !important;
  font-weight: 800 !important;
  padding: 1px 4px !important;
}
""".strip()
    return _files(name, target_urls, "Translate LinkedIn corporate language into real talk.", js, css)


def _x_for_you(query: str, target_urls: list[str], name: str) -> dict[str, str]:
    js = _runtime_wrapper(
        """
  document.querySelectorAll('[role="tab"]').forEach((tab) => {
    const text = (tab.textContent || '').toLowerCase();
    if (text.includes('following')) {
      const selected = tab.getAttribute('aria-selected') === 'true';
      if (!selected) tab.click();
    }
  });
  document.querySelectorAll('[aria-label*="For you"], [data-testid="primaryColumn"] section').forEach((node) => {
    const text = (node.textContent || '').toLowerCase();
    if (text.includes('for you')) hideNode(node);
  });
""",
    )
    return _files(name, target_urls, "Prefer Following feed and hide For You areas.", js)


def _x_trending(query: str, target_urls: list[str], name: str) -> dict[str, str]:
    js = _runtime_wrapper(
        """
  document.querySelectorAll('aside, [role="complementary"], section').forEach((section) => {
    const text = (section.textContent || '').toLowerCase();
    const aria = (section.getAttribute('aria-label') || '').toLowerCase();
    if (text.includes("what's happening") || text.includes('trending') || text.includes('trends') || aria.includes('trends')) {
      hideNode(section);
    }
  });
""",
    )
    return _files(name, target_urls, "Hide X/Twitter trending sidebar sections.", js)


def _x_community_note_elevator(query: str, target_urls: list[str], name: str) -> dict[str, str]:
    js = _runtime_wrapper(
        """
  document.querySelectorAll('[data-testid="birdwatch-pivot"], [data-testid="birdwatch-pivot"] *, div[aria-label*="Community Note" i]').forEach((node) => {
    if (!(node instanceof Element)) return;
    const note = node.closest('[data-testid="birdwatch-pivot"]') || node;
    elevateCommunityNote(note);
  });
""",
        """
function elevateCommunityNote(note) {
  if (!(note instanceof Element)) return;
  note.classList.add('bf-community-note-elevated');
  if (note.querySelector('.bf-community-note-header')) return;
  const header = document.createElement('div');
  header.className = 'bf-community-note-header';
  header.textContent = 'FACT CHECK';
  note.prepend(header);
}
""",
    )
    css = """
.bf-community-note-elevated {
  background: #b00020 !important;
  border: 3px solid #ffccd5 !important;
  border-radius: 14px !important;
  box-shadow: 0 0 0 3px rgba(176, 0, 32, 0.35), 0 18px 42px rgba(0, 0, 0, 0.28) !important;
  color: #fff !important;
  font-size: 1.08em !important;
  font-weight: 700 !important;
  margin: 12px 0 !important;
  padding: 14px !important;
  transform: scale(1.05) !important;
  transform-origin: center top !important;
  z-index: 5 !important;
}

.bf-community-note-elevated * {
  color: #fff !important;
}

.bf-community-note-header {
  background: #fff !important;
  border-radius: 999px !important;
  color: #b00020 !important;
  display: inline-block !important;
  font: 900 13px/1 Arial, Helvetica, sans-serif !important;
  letter-spacing: 0 !important;
  margin: 0 0 10px !important;
  padding: 8px 12px !important;
}
""".strip()
    return _files(name, target_urls, "Elevate X Community Notes into prominent fact-check banners.", js, css)


def _x_engagement_bait(query: str, target_urls: list[str], name: str) -> dict[str, str]:
    js = _runtime_wrapper(
        """
  if (!/\\/status\\/\\d+/.test(location.pathname)) return;

  const primaryColumn = document.querySelector('[data-testid="primaryColumn"]') || document;
  const articles = Array.from(primaryColumn.querySelectorAll('article[data-testid="tweet"], article'));
  const replies = articles.slice(1);
  replies.forEach((article) => {
    if (!(article instanceof Element)) return;
    if (!hasVerifiedBadge(article)) return;
    const likeCount = getLikeCount(article);
    if (likeCount >= 100) return;
    const cell = article.closest('[data-testid="cellInnerDiv"]') || article;
    cell.setAttribute('data-bf-engagement-bait-removed', '1');
    cell.remove();
  });
""",
        """
function compactNumberToInt(raw, suffix) {
  const value = Number(String(raw || '').replace(/,/g, ''));
  if (!Number.isFinite(value)) return 0;
  const unit = String(suffix || '').toLowerCase();
  if (unit === 'k') return Math.round(value * 1000);
  if (unit === 'm') return Math.round(value * 1000000);
  return Math.round(value);
}

function extractLikeCountFromText(text) {
  const normalized = String(text || '').replace(/\\s+/g, ' ');
  const labeled = normalized.match(/([\\d,.]+)\\s*([km])?\\s+likes?\\b/i);
  if (labeled) return compactNumberToInt(labeled[1], labeled[2]);
  const aria = normalized.match(/likes?\\s*[,·]?\\s*([\\d,.]+)\\s*([km])?/i);
  if (aria) return compactNumberToInt(aria[1], aria[2]);
  return 0;
}

function getLikeCount(article) {
  const groups = article.querySelectorAll('[role="group"], [aria-label*="like" i], [data-testid="like"]');
  let best = 0;
  groups.forEach((node) => {
    const text = `${node.getAttribute?.('aria-label') || ''} ${node.textContent || ''}`;
    best = Math.max(best, extractLikeCountFromText(text));
  });
  return best;
}

function hasVerifiedBadge(article) {
  if (article.querySelector('[data-testid="icon-verified"], svg[aria-label*="verified" i]')) return true;
  return Array.from(article.querySelectorAll('svg')).some((svg) => {
    const label = `${svg.getAttribute('aria-label') || ''} ${svg.getAttribute('data-testid') || ''}`.toLowerCase();
    return label.includes('verified') || label.includes('icon-verified');
  });
}
""",
    )
    return _files(name, target_urls, "Remove low-like verified X replies on tweet threads.", js)


def _amazon_descammer(query: str, target_urls: list[str], name: str) -> dict[str, str]:
    js = _runtime_wrapper(
        """
  const products = Array.from(document.querySelectorAll('[data-asin]')).filter((product) => {
    return product instanceof Element && (product.getAttribute('data-asin') || '').trim().length > 0;
  });
  let cheapest = null;
  products.forEach((product) => {
    product.classList.remove('bf-amazon-cheapest');
    if (isSponsoredProduct(product)) {
      hideNode(product);
      return;
    }
    product.classList.remove(HIDDEN_CLASS);
    const price = readPrice(product);
    if (price === null) return;
    if (!cheapest || price < cheapest.price) cheapest = { node: product, price };
  });
  if (cheapest?.node) cheapest.node.classList.add('bf-amazon-cheapest');
""",
        """
function isSponsoredProduct(product) {
  const text = (product.textContent || '').toLowerCase();
  if (text.includes('sponsored')) return true;
  return Boolean(product.querySelector('[aria-label*="Sponsored" i], [data-component-type*="sp-sponsored" i]'));
}

function readPrice(product) {
  const whole = product.querySelector('.a-price .a-price-whole, .a-price-whole');
  if (!whole) return null;
  const fraction = product.querySelector('.a-price .a-price-fraction, .a-price-fraction');
  const wholeText = (whole.textContent || '').replace(/[^0-9]/g, '');
  const fractionText = (fraction?.textContent || '00').replace(/[^0-9]/g, '').padEnd(2, '0').slice(0, 2);
  if (!wholeText) return null;
  const price = Number(`${wholeText}.${fractionText}`);
  return Number.isFinite(price) ? price : null;
}
""",
    )
    css = """
.bf-hidden {
  display: none !important;
}

.bf-amazon-cheapest {
  border: 5px solid #00d084 !important;
  border-radius: 10px !important;
  box-shadow: 0 0 0 4px rgba(255, 255, 255, 0.9), 0 0 32px rgba(0, 208, 132, 0.82) !important;
  outline: 2px solid #00ff9c !important;
  outline-offset: 4px !important;
  position: relative !important;
}

.bf-amazon-cheapest::before {
  background: #00d084 !important;
  border-radius: 999px !important;
  color: #002417 !important;
  content: "CHEAPEST REAL RESULT" !important;
  display: block !important;
  font: 900 12px/1 Arial, Helvetica, sans-serif !important;
  left: 12px !important;
  letter-spacing: 0 !important;
  padding: 8px 10px !important;
  position: absolute !important;
  top: 12px !important;
  z-index: 30 !important;
}
""".strip()
    return _files(name, target_urls, "Hide sponsored Amazon products and highlight the cheapest result.", js, css)


def _netflix_roulette(query: str, target_urls: list[str], name: str) -> dict[str, str]:
    js = _runtime_wrapper(
        """
  injectRouletteButton();
""",
        """
const ROULETTE_BUTTON_ID = 'bf-netflix-roulette-button';
const ROULETTE_FALLBACK_ID = 'bf-netflix-roulette-fallback';

function findControlsContainer() {
  const selectors = [
    '.button-controls-container',
    '[data-uia="button-controls-container"]',
    '.previewModal--player-titleTreatment-logo + div',
    '.jawBoneActions',
    '.billboard-links',
    '.buttonControls--container',
  ];
  for (const selector of selectors) {
    const node = document.querySelector(selector);
    if (node instanceof Element) return node;
  }
  const playButton = document.querySelector('button[data-uia*="play" i], a[href*="/watch/"]');
  if (playButton?.parentElement) return playButton.parentElement;
  let fallback = document.getElementById(ROULETTE_FALLBACK_ID);
  if (!fallback) {
    fallback = document.createElement('div');
    fallback.id = ROULETTE_FALLBACK_ID;
    document.documentElement.appendChild(fallback);
  }
  return fallback;
}

function visibleElement(el) {
  const rect = el.getBoundingClientRect();
  return rect.width > 20 && rect.height > 20;
}

function playableCardsInside(root) {
  const selectors = [
    '.episode-item',
    '[data-uia*="episode" i]',
    '.titleCard',
    '.slider-item',
    'a[href*="/watch/"]',
    'button[data-uia*="play" i]',
  ].join(',');
  return Array.from(root.querySelectorAll(selectors)).filter((node) => {
    if (!(node instanceof HTMLElement)) return false;
    if (!visibleElement(node)) return false;
    const disabled = node.getAttribute('aria-disabled') === 'true' || node.hasAttribute('disabled');
    return !disabled;
  });
}

function firstEpisodeOptions() {
  const rows = Array.from(document.querySelectorAll(
    '.lolomoRow, .slider, .episodeSelector, [data-list-context], [data-uia*="section" i], [data-uia*="episodes" i]'
  ));
  const rowFirstCards = rows
    .map((row) => playableCardsInside(row)[0])
    .filter(Boolean);
  if (rowFirstCards.length > 0) return rowFirstCards;
  return playableCardsInside(document);
}

function clickLikeHuman(target) {
  target.scrollIntoView({ block: 'center', inline: 'center', behavior: 'smooth' });
  const rect = target.getBoundingClientRect();
  const init = {
    bubbles: true,
    cancelable: true,
    view: window,
    clientX: rect.left + rect.width / 2,
    clientY: rect.top + rect.height / 2,
  };
  target.dispatchEvent(new PointerEvent('pointerdown', init));
  target.dispatchEvent(new MouseEvent('mousedown', init));
  target.dispatchEvent(new PointerEvent('pointerup', init));
  target.dispatchEvent(new MouseEvent('mouseup', init));
  target.dispatchEvent(new MouseEvent('click', init));
  target.click?.();
}

function launchRandomFirstEpisode() {
  const options = firstEpisodeOptions();
  if (options.length === 0) return;
  const index = Math.floor(Math.random() * options.length);
  clickLikeHuman(options[index]);
}

function injectRouletteButton() {
  if (document.getElementById(ROULETTE_BUTTON_ID)) return;
  const host = findControlsContainer();
  if (!host) return;
  const button = document.createElement('button');
  button.id = ROULETTE_BUTTON_ID;
  button.type = 'button';
  button.className = 'bf-netflix-roulette-btn';
  button.setAttribute('aria-label', 'Play a random first episode');
  button.textContent = 'Random Episode';
  button.addEventListener('click', (event) => {
    event.preventDefault();
    event.stopPropagation();
    launchRandomFirstEpisode();
  });
  host.appendChild(button);
}
""",
    )
    css = """
.bf-netflix-roulette-btn {
  align-items: center !important;
  appearance: none !important;
  background: #fff !important;
  border: 0 !important;
  border-radius: 4px !important;
  color: #141414 !important;
  cursor: pointer !important;
  display: inline-flex !important;
  font-family: "Netflix Sans", "Helvetica Neue", Helvetica, Arial, sans-serif !important;
  font-size: clamp(13px, 1.1vw, 18px) !important;
  font-weight: 700 !important;
  gap: 8px !important;
  line-height: 1 !important;
  margin-left: 10px !important;
  min-height: 42px !important;
  padding: 0.8rem 1.45rem !important;
  position: relative !important;
  transition: background 160ms ease, transform 120ms ease !important;
  vertical-align: middle !important;
  z-index: 20 !important;
}

.bf-netflix-roulette-btn::before {
  content: "";
  width: 0;
  height: 0;
  border-top: 7px solid transparent;
  border-bottom: 7px solid transparent;
  border-left: 12px solid currentColor;
}

.bf-netflix-roulette-btn:hover {
  background: rgba(255, 255, 255, 0.78) !important;
}

.bf-netflix-roulette-btn:active {
  transform: scale(0.98) !important;
}

#bf-netflix-roulette-fallback {
  position: fixed !important;
  right: 38px !important;
  top: 86px !important;
  z-index: 2147483646 !important;
}

#bf-netflix-roulette-fallback .bf-netflix-roulette-btn {
  margin-left: 0 !important;
}
""".strip()
    return _files(name, target_urls, "Inject a native-looking Netflix random episode button.", js, css)


def _doomscroll_guillotine(query: str, target_urls: list[str], name: str) -> dict[str, str]:
    js = _runtime_wrapper(
        """
  installDoomscrollGuillotine();
""",
        """
const DOOM_LIMIT = 10;
const DOOM_COUNTER_ID = 'bf-doomscroll-counter';
const DOOM_WALL_ID = 'bf-doomscroll-wall';
const seenVideos = new WeakSet();
const observedVideos = new WeakSet();
let doomCount = 0;
let doomLocked = false;
let centerCheckToken = 0;
const doomObserver = new IntersectionObserver((entries) => {
  entries.forEach((entry) => {
    if (!entry.isIntersecting || doomLocked) return;
    if (videoCrossesCenter(entry.target)) countVideo(entry.target);
  });
}, { threshold: [0.25, 0.5, 0.75, 1] });

function ensureCounter() {
  let counter = document.getElementById(DOOM_COUNTER_ID);
  if (!counter) {
    counter = document.createElement('div');
    counter.id = DOOM_COUNTER_ID;
    counter.setAttribute('aria-live', 'polite');
    counter.setAttribute('role', 'status');
    document.documentElement.appendChild(counter);
  }
  counter.textContent = `${Math.min(doomCount, DOOM_LIMIT)}/${DOOM_LIMIT}`;
  counter.classList.toggle('bf-doomscroll-counter-danger', doomCount >= DOOM_LIMIT - 2);
}

function videoCrossesCenter(video) {
  if (!(video instanceof Element)) return false;
  const rect = video.getBoundingClientRect();
  if (rect.width < 120 || rect.height < 160) return false;
  const centerY = window.innerHeight / 2;
  const centerX = window.innerWidth / 2;
  const crossesY = rect.top <= centerY && rect.bottom >= centerY;
  const broadlyCentered = rect.left <= centerX + window.innerWidth * 0.36 && rect.right >= centerX - window.innerWidth * 0.36;
  return crossesY && broadlyCentered;
}

function countVideo(video) {
  if (!(video instanceof HTMLVideoElement)) return;
  if (seenVideos.has(video)) return;
  seenVideos.add(video);
  doomCount += 1;
  ensureCounter();
  if (doomCount >= DOOM_LIMIT) dropGuillotine();
}

function blockScroll(event) {
  if (!doomLocked) return;
  event.preventDefault();
  event.stopImmediatePropagation();
}

function blockScrollKeys(event) {
  if (!doomLocked) return;
  const keys = ['ArrowDown', 'ArrowUp', 'PageDown', 'PageUp', 'Home', 'End', ' ', 'Spacebar'];
  if (!keys.includes(event.key)) return;
  event.preventDefault();
  event.stopImmediatePropagation();
}

function dropGuillotine() {
  if (doomLocked) return;
  doomLocked = true;
  ensureCounter();
  document.documentElement.classList.add('bf-doomscroll-locked');
  document.body?.classList.add('bf-doomscroll-locked');

  let wall = document.getElementById(DOOM_WALL_ID);
  if (!wall) {
    wall = document.createElement('div');
    wall.id = DOOM_WALL_ID;
    wall.innerHTML = '<div class="bf-doomscroll-wall-card"><div class="bf-doomscroll-wall-count">10/10</div><div class="bf-doomscroll-wall-text">That\\'s enough for today. Go outside.</div></div>';
    document.documentElement.appendChild(wall);
  }

  window.addEventListener('wheel', blockScroll, { passive: false, capture: true });
  window.addEventListener('touchmove', blockScroll, { passive: false, capture: true });
  window.addEventListener('keydown', blockScrollKeys, { passive: false, capture: true });
}

function scheduleCenterCheck() {
  if (centerCheckToken) return;
  centerCheckToken = requestAnimationFrame(() => {
    centerCheckToken = 0;
    if (doomLocked) return;
    document.querySelectorAll('video').forEach((video) => {
      if (videoCrossesCenter(video)) countVideo(video);
    });
  });
}

function installDoomscrollGuillotine() {
  ensureCounter();
  document.querySelectorAll('video').forEach((video) => {
    if (observedVideos.has(video)) return;
    observedVideos.add(video);
    doomObserver.observe(video);
  });
  scheduleCenterCheck();
}

window.addEventListener('scroll', scheduleCenterCheck, { passive: true });
window.addEventListener('resize', scheduleCenterCheck, { passive: true });
""",
    )
    css = """
#bf-doomscroll-counter {
  align-items: center !important;
  background: #e50914 !important;
  border: 3px solid #fff !important;
  border-radius: 999px !important;
  box-shadow: 0 12px 36px rgba(0, 0, 0, 0.35), 0 0 0 5px rgba(229, 9, 20, 0.28) !important;
  color: #fff !important;
  display: flex !important;
  font: 900 21px/1 Arial, Helvetica, sans-serif !important;
  height: 74px !important;
  justify-content: center !important;
  letter-spacing: 0 !important;
  position: fixed !important;
  right: 22px !important;
  text-align: center !important;
  top: 22px !important;
  width: 74px !important;
  z-index: 2147483646 !important;
}

#bf-doomscroll-counter.bf-doomscroll-counter-danger {
  animation: bf-doom-pulse 700ms ease-in-out infinite alternate !important;
}

#bf-doomscroll-wall {
  align-items: center !important;
  background: #000 !important;
  color: #fff !important;
  display: flex !important;
  font-family: Arial, Helvetica, sans-serif !important;
  inset: 0 !important;
  justify-content: center !important;
  position: fixed !important;
  z-index: 2147483647 !important;
}

.bf-doomscroll-wall-card {
  display: grid !important;
  gap: 18px !important;
  max-width: min(680px, calc(100vw - 40px)) !important;
  text-align: center !important;
}

.bf-doomscroll-wall-count {
  color: #e50914 !important;
  font: 900 72px/0.95 Arial, Helvetica, sans-serif !important;
}

.bf-doomscroll-wall-text {
  color: #fff !important;
  font: 800 clamp(26px, 6vw, 56px)/1.05 Arial, Helvetica, sans-serif !important;
  letter-spacing: 0 !important;
}

html.bf-doomscroll-locked,
body.bf-doomscroll-locked {
  overflow: hidden !important;
  overscroll-behavior: none !important;
}

@keyframes bf-doom-pulse {
  from { transform: scale(1); }
  to { transform: scale(1.08); }
}
""".strip()
    return _files(name, target_urls, "Stop doomscrolling after ten centered videos.", js, css)


def _youtube_clickbait_nuke(query: str, target_urls: list[str], name: str) -> dict[str, str]:
    js = _runtime_wrapper(
        """
  document.documentElement.classList.add('bf-youtube-clickbait-nuke');
  document.querySelectorAll('ytd-thumbnail').forEach((thumbnail) => {
    thumbnail.classList.add('bf-youtube-clickbait-thumbnail');
    thumbnail.querySelectorAll('#mouseover-overlay, ytd-moving-thumbnail-renderer, #hover-overlays').forEach((preview) => {
      preview.classList.add('bf-youtube-preview-forced');
    });
  });
""",
    )
    css = """
html.bf-youtube-clickbait-nuke ytd-thumbnail img.yt-core-image,
html.bf-youtube-clickbait-nuke ytd-thumbnail yt-image img,
html.bf-youtube-clickbait-nuke ytd-thumbnail #img {
  opacity: 0 !important;
}

html.bf-youtube-clickbait-nuke ytd-thumbnail #mouseover-overlay,
html.bf-youtube-clickbait-nuke ytd-thumbnail ytd-moving-thumbnail-renderer,
html.bf-youtube-clickbait-nuke ytd-thumbnail #hover-overlays,
html.bf-youtube-clickbait-nuke ytd-thumbnail .bf-youtube-preview-forced {
  display: block !important;
  opacity: 1 !important;
  visibility: visible !important;
}

html.bf-youtube-clickbait-nuke ytd-thumbnail {
  background: #000 !important;
}
""".strip()
    return _files(name, target_urls, "Replace YouTube clickbait thumbnails with preview frames.", js, css)


def _youtube_absolute_focus(query: str, target_urls: list[str], name: str) -> dict[str, str]:
    js = _runtime_wrapper(
        """
  document.documentElement.classList.add('bf-youtube-absolute-focus');
  const videoCards = document.querySelectorAll(
    'ytd-rich-item-renderer, ytd-video-renderer, ytd-grid-video-renderer, ytd-compact-video-renderer'
  );
  videoCards.forEach((card) => {
    const thumbnail = card.querySelector('ytd-thumbnail a#thumbnail[href*="/watch"], a#thumbnail[href*="/watch"]');
    if (thumbnail) {
      card.classList.add('bf-video-card');
    } else {
      hideNode(card);
    }
  });

  document.querySelectorAll(
    '#masthead-container, ytd-masthead, ytd-guide-renderer, ytd-mini-guide-renderer, #guide, #chips-wrapper, ytd-feed-filter-chip-bar-renderer, ytd-reel-shelf-renderer, ytd-rich-section-renderer, ytd-comments, #comments, ytd-watch-next-secondary-results-renderer, #secondary, ytd-merch-shelf-renderer'
  ).forEach((node) => hideNode(node));
""",
    )
    css = """
html.bf-youtube-absolute-focus,
html.bf-youtube-absolute-focus body {
  background: #000 !important;
}

html.bf-youtube-absolute-focus #masthead-container,
html.bf-youtube-absolute-focus ytd-masthead,
html.bf-youtube-absolute-focus ytd-guide-renderer,
html.bf-youtube-absolute-focus ytd-mini-guide-renderer,
html.bf-youtube-absolute-focus #guide,
html.bf-youtube-absolute-focus #chips-wrapper,
html.bf-youtube-absolute-focus ytd-feed-filter-chip-bar-renderer,
html.bf-youtube-absolute-focus ytd-rich-section-renderer,
html.bf-youtube-absolute-focus ytd-reel-shelf-renderer,
html.bf-youtube-absolute-focus ytd-comments,
html.bf-youtube-absolute-focus #comments,
html.bf-youtube-absolute-focus #secondary,
html.bf-youtube-absolute-focus ytd-watch-next-secondary-results-renderer,
html.bf-youtube-absolute-focus ytd-merch-shelf-renderer,
html.bf-youtube-absolute-focus ytd-continuation-item-renderer,
html.bf-youtube-absolute-focus tp-yt-app-drawer,
html.bf-youtube-absolute-focus ytd-mini-guide-renderer,
html.bf-youtube-absolute-focus #header,
html.bf-youtube-absolute-focus h1,
html.bf-youtube-absolute-focus h2,
html.bf-youtube-absolute-focus h3 {
  display: none !important;
}

html.bf-youtube-absolute-focus ytd-page-manager,
html.bf-youtube-absolute-focus ytd-browse,
html.bf-youtube-absolute-focus ytd-two-column-browse-results-renderer,
html.bf-youtube-absolute-focus ytd-rich-grid-renderer,
html.bf-youtube-absolute-focus #contents.ytd-rich-grid-renderer,
html.bf-youtube-absolute-focus ytd-section-list-renderer,
html.bf-youtube-absolute-focus ytd-item-section-renderer,
html.bf-youtube-absolute-focus ytd-search {
  margin: 0 !important;
  max-width: none !important;
  padding: 0 !important;
  width: 100% !important;
}

html.bf-youtube-absolute-focus ytd-rich-grid-renderer {
  --ytd-rich-grid-items-per-row: 6 !important;
  --ytd-rich-grid-item-margin: 0 !important;
}

html.bf-youtube-absolute-focus #contents.ytd-rich-grid-renderer,
html.bf-youtube-absolute-focus ytd-rich-grid-row,
html.bf-youtube-absolute-focus ytd-section-list-renderer #contents,
html.bf-youtube-absolute-focus ytd-item-section-renderer #contents {
  display: grid !important;
  gap: 0 !important;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)) !important;
  align-items: start !important;
}

html.bf-youtube-absolute-focus ytd-rich-item-renderer.bf-video-card,
html.bf-youtube-absolute-focus ytd-video-renderer.bf-video-card,
html.bf-youtube-absolute-focus ytd-grid-video-renderer.bf-video-card,
html.bf-youtube-absolute-focus ytd-compact-video-renderer.bf-video-card {
  display: block !important;
  margin: 0 !important;
  max-width: none !important;
  padding: 0 !important;
  width: 100% !important;
}

html.bf-youtube-absolute-focus ytd-rich-item-renderer.bf-video-card #details,
html.bf-youtube-absolute-focus ytd-video-renderer.bf-video-card #details,
html.bf-youtube-absolute-focus ytd-grid-video-renderer.bf-video-card #details,
html.bf-youtube-absolute-focus ytd-compact-video-renderer.bf-video-card #details,
html.bf-youtube-absolute-focus ytd-rich-item-renderer.bf-video-card #metadata,
html.bf-youtube-absolute-focus ytd-video-renderer.bf-video-card #metadata,
html.bf-youtube-absolute-focus ytd-grid-video-renderer.bf-video-card #metadata,
html.bf-youtube-absolute-focus ytd-compact-video-renderer.bf-video-card #metadata,
html.bf-youtube-absolute-focus ytd-rich-item-renderer.bf-video-card #dismissible > #avatar,
html.bf-youtube-absolute-focus ytd-rich-item-renderer.bf-video-card ytd-channel-name,
html.bf-youtube-absolute-focus ytd-rich-item-renderer.bf-video-card #video-title,
html.bf-youtube-absolute-focus ytd-rich-item-renderer.bf-video-card #metadata-line {
  display: none !important;
}

html.bf-youtube-absolute-focus ytd-thumbnail,
html.bf-youtube-absolute-focus ytd-thumbnail a#thumbnail,
html.bf-youtube-absolute-focus ytd-thumbnail img,
html.bf-youtube-absolute-focus ytd-thumbnail yt-image,
html.bf-youtube-absolute-focus ytd-thumbnail .yt-core-image {
  border-radius: 0 !important;
  display: block !important;
  height: auto !important;
  margin: 0 !important;
  object-fit: cover !important;
  padding: 0 !important;
  width: 100% !important;
}

html.bf-youtube-absolute-focus ytd-thumbnail a#thumbnail {
  aspect-ratio: 16 / 9 !important;
  background: #000 !important;
  overflow: hidden !important;
}

html.bf-youtube-absolute-focus ytd-watch-flexy #primary {
  margin: 0 !important;
  max-width: 100% !important;
  padding: 0 !important;
}
""".strip()
    return _files(name, target_urls, "Turn YouTube into a thumbnail-only focus grid.", js, css)


def _reddit_sidebar(query: str, target_urls: list[str], name: str) -> dict[str, str]:
    js = _runtime_wrapper(
        """
  const recentPattern = /(recent\\s+posts?|recent)/i;
  const rightRailHints = ['right', 'sidebar', 'complementary'];
  document.querySelectorAll(
    "aside, [role='complementary'], shreddit-sidebar, reddit-sidebar, [slot*='right'], [data-testid*='right'], [data-testid*='sidebar'], div"
  ).forEach((node) => {
    const text = ((node.getAttribute('aria-label') || '') + ' ' + (node.textContent || '')).toLowerCase();
    const rect = node.getBoundingClientRect();
    const rightSide = rect.left >= window.innerWidth * 0.55;
    const hasRailHint = rightRailHints.some((hint) => text.includes(hint) || (node.id || '').toLowerCase().includes(hint) || (node.className || '').toString().toLowerCase().includes(hint));
    const hasRecent = recentPattern.test(text);
    if ((rightSide && hasRailHint) || hasRecent) {
      const owner = safeClosest(node, "aside, [role='complementary'], shreddit-sidebar, reddit-sidebar, [data-testid*='sidebar'], [data-testid*='right'], div");
      hideNode(owner || node);
    }
  });
""",
    )
    return _files(name, target_urls, "Hide Reddit right sidebar recent-posts widgets.", js)


def _reddit_collapse_comments(query: str, target_urls: list[str], name: str) -> dict[str, str]:
    js = _runtime_wrapper(
        """
  document.querySelectorAll('button[aria-expanded], button').forEach((btn) => {
    const label = ((btn.getAttribute('aria-label') || '') + ' ' + (btn.textContent || '')).toLowerCase();
    if (!(label.includes('collapse') || label.includes('minimize') || label.includes('hide thread'))) return;
    const expanded = btn.getAttribute('aria-expanded');
    if (expanded === null || expanded === 'true') btn.click();
  });
  document.querySelectorAll('[data-testid*="comment"], shreddit-comment').forEach((comment) => {
    const body = comment.querySelector('div[data-testid*="comment-content"], [slot="comment"], p, div');
    if (body) body.classList.add(HIDDEN_CLASS);
  });
""",
    )
    return _files(name, target_urls, "Collapse Reddit comment chains by default.", js)


BUILDERS: dict[str, Callable[[str, list[str], str], dict[str, str]]] = {
    "youtube-shorts": _youtube_shorts,
    "youtube-comments": _youtube_comments,
    "youtube-recommendations": _youtube_recommendations,
    "youtube-keyword-filter": _youtube_keyword_filter,
    "youtube-clickbait-nuke": _youtube_clickbait_nuke,
    "instagram-nav": _instagram_nav,
    "instagram-suggested-posts": _instagram_suggested_posts,
    "instagram-floating-messages": _instagram_floating_messages,
    "instagram-engagement-counts": _instagram_engagement_counts,
    "gmail-tabs": _gmail_tabs,
    "gmail-sender-highlight": _gmail_sender_highlight,
    "gmail-focus": _gmail_focus,
    "email-deadlines": _email_deadlines,
    "outlook-panels": _outlook_panels,
    "outlook-highlight-sender": _outlook_highlight_sender,
    "calendar-meeting-prep": _calendar_meeting_prep,
    "google-calendar-keywords": _google_calendar_keywords,
    "google-calendar-weekends": _google_calendar_weekends,
    "calendar-missing-location": _calendar_missing_location,
    "linkedin-feed": _linkedin_feed,
    "linkedin-promoted": _linkedin_promoted,
    "linkedin-page-filter": _linkedin_page_filter,
    "linkedin-hiring-highlight": _linkedin_hiring_highlight,
    "linkedin-real-talk": _linkedin_real_talk,
    "x-for-you": _x_for_you,
    "x-trending": _x_trending,
    "x-community-note-elevator": _x_community_note_elevator,
    "x-engagement-bait": _x_engagement_bait,
    "amazon-descammer": _amazon_descammer,
    "netflix-roulette": _netflix_roulette,
    "doomscroll-guillotine": _doomscroll_guillotine,
    "youtube-absolute-focus": _youtube_absolute_focus,
    "reddit-sidebar": _reddit_sidebar,
    "reddit-collapse-comments": _reddit_collapse_comments,
}


def _site_requested(query_lower: str, target_urls: list[str], aliases: tuple[str, ...]) -> bool:
    haystack = f"{query_lower} {' '.join(target_urls)}".lower()
    tokens = set(re.findall(r"[a-z0-9]+", haystack))
    for alias in aliases:
        alias_lower = alias.lower()
        if "." in alias_lower:
            if alias_lower in haystack:
                return True
            continue
        if alias_lower in tokens:
            return True
    return False


def _has_any_phrase(query_lower: str, phrases: tuple[str, ...]) -> bool:
    normalized = re.sub(r"\s+", " ", query_lower)
    return any(phrase in normalized for phrase in phrases)


def build_hardcoded_demo_files(
    query: str,
    target_urls: list[str],
    extension_name: str,
) -> tuple[dict[str, str], str] | None:
    """Return the hackathon-grade offline demo payload for known trigger phrases.

    This direct layer intentionally runs before RAG scoring and the LLM. The
    broader deterministic builder below remains available for teammate-added
    architecture and classification use-cases.
    """
    query_lower = query.lower()
    is_linkedin = _site_requested(query_lower, target_urls, ("linkedin", "linkedin.com"))
    is_x = _site_requested(query_lower, target_urls, ("x", "x.com", "twitter", "twitter.com"))
    is_amazon = _site_requested(query_lower, target_urls, ("amazon", "amazon.com"))
    is_netflix = _site_requested(query_lower, target_urls, ("netflix", "netflix.com"))
    is_youtube = _site_requested(query_lower, target_urls, ("youtube", "youtube.com", "youtu.be"))
    is_instagram = _site_requested(query_lower, target_urls, ("instagram", "instagram.com"))
    is_tiktok = _site_requested(query_lower, target_urls, ("tiktok", "tiktok.com"))

    if is_linkedin and _has_any_phrase(
        query_lower,
        ("translate", "real talk", "bullshit", "corporate translator", "corporate speak"),
    ):
        return _linkedin_real_talk(query, target_urls, extension_name), "linkedin-real-talk"

    if is_linkedin and _has_any_phrase(
        query_lower,
        (
            "hiring",
            "internship",
            "intern",
            "new grad",
            "new graduate",
            "entry level",
            "open role",
            "job opening",
            "recruiting",
        ),
    ):
        return _linkedin_hiring_highlight(query, target_urls, extension_name), "linkedin-hiring-highlight"

    if is_x and _has_any_phrase(query_lower, ("community note", "community notes", "fact check", "birdwatch")):
        return _x_community_note_elevator(query, target_urls, extension_name), "x-community-note-elevator"

    if is_x and _has_any_phrase(
        query_lower,
        ("verified", "blue check", "bluecheck", "spam", "engagement bait", "bot replies", "reply bait"),
    ):
        return _x_engagement_bait(query, target_urls, extension_name), "x-engagement-bait"

    if is_amazon and _has_any_phrase(
        query_lower,
        ("sponsored", "cheapest", "amazon", "de-scam", "descam", "scammer", "ads"),
    ):
        return _amazon_descammer(query, target_urls, extension_name), "amazon-descammer"

    if is_netflix and _has_any_phrase(query_lower, ("random", "roulette", "random episode", "tv roulette", "episode")):
        return _netflix_roulette(query, target_urls, extension_name), "netflix-roulette"

    if (is_instagram or is_tiktok) and _has_any_phrase(
        query_lower,
        ("doomscroll", "10 videos", "ten videos", "go outside", "guillotine"),
    ):
        return _doomscroll_guillotine(query, target_urls, extension_name), "doomscroll-guillotine"

    if is_youtube and _has_any_phrase(query_lower, ("clickbait", "thumbnail", "thumbnails", "anti-clickbait")):
        return _youtube_clickbait_nuke(query, target_urls, extension_name), "youtube-clickbait-nuke"

    if is_youtube and _has_any_phrase(query_lower, ("absolute focus", "distractions", "focus", "comments")):
        return _youtube_absolute_focus(query, target_urls, extension_name), "youtube-absolute-focus"

    return None


def build_deterministic_files(
    query: str,
    target_urls: list[str],
    extension_name: str,
) -> tuple[dict[str, str], str] | None:
    """Generate deterministic files for known use-cases.

    Returns:
        (files, use_case_id) on success, else None.
    """
    entries = retrieve_context_entries(query, target_urls, limit=12)
    for entry in entries:
        if not should_apply_deterministic_template(query, target_urls, entry):
            # Host alone is not enough: novel asks fall through to the LLM, which
            # still receives nudge RAG + site DOM bootstrap in rag.py.
            continue
        use_case_id = str(entry.get("id", ""))
        builder = BUILDERS.get(use_case_id)
        if not builder:
            continue
        files = builder(query, target_urls, extension_name)
        return files, use_case_id
    return None
