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
      console.debug('applyRules failed', err);
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
    const res = await fetch(CLASSIFY_ENDPOINT, {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify({{
        filter_description: FILTER_DESCRIPTION,
        items: payload,
      }}),
    }});
    if (!res.ok) return;
    const data = await res.json();
    const matches = new Set(Array.isArray(data?.matches) ? data.matches.map(String) : []);
    for (const item of payload) {{
      cache.set(item.id, matches.has(item.id));
    }}
  }} catch {{
    // Keep items visible on classify failure.
  }}
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


def _files(name: str, target_urls: list[str], description: str, content_js: str, content_css: str | None = None, host_permissions: list[str] | None = None) -> dict[str, str]:
    css = content_css or _base_css()
    return {
        "manifest.json": json.dumps(
            _manifest(
                name=name,
                target_urls=target_urls,
                description=description,
                host_permissions=host_permissions,
            ),
            indent=2,
        ),
        "content.js": content_js,
        "content.css": css,
    }


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
    )


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
    "x-for-you": _x_for_you,
    "x-trending": _x_trending,
    "reddit-sidebar": _reddit_sidebar,
    "reddit-collapse-comments": _reddit_collapse_comments,
}


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
