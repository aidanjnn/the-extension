"""Retrieval corpus for browser customization implementation patterns.

Entries describe DOM patterns, safety constraints, and implementation strategies
that the Codegen agent adapts to each request.
"""

from __future__ import annotations

import re
from typing import Any


DOM_IMPLEMENTATION_CORPUS: list[dict[str, Any]] = [
    {
        "id": "youtube-shorts",
        "title": "Remove YouTube Shorts",
        "sites": ["youtube"],
        "terms": ["shorts", "reels"],
        "guidance": (
            "YouTube Shorts removal: target structural Shorts containers such as "
            "`ytd-reel-shelf-renderer`, `ytd-rich-section-renderer` with Shorts links, "
            "`ytd-guide-entry-renderer`/`ytd-mini-guide-entry-renderer` anchors whose "
            "`href` starts with `/shorts` (handle both `/shorts` and `/shorts/`), and "
            "video/grid renderers containing Shorts anchors. Use multiple selectors so "
            "home feed, watch recommendations, and nav links are all covered. Do not "
            "hide all rich-grid rows. Use CSS plus a MutationObserver that marks only "
            "the matched container."
        ),
    },
    {
        "id": "youtube-comments",
        "title": "Hide YouTube Comments",
        "sites": ["youtube"],
        "terms": ["comments", "comment section"],
        "guidance": (
            "YouTube comments: hide `ytd-comments`, `#comments`, and comment thread "
            "renderers under the watch page only. Keep the video player, title, and "
            "description visible. Re-run on SPA navigation."
        ),
    },
    {
        "id": "youtube-recommendations",
        "title": "Hide YouTube Recommended Sidebar",
        "sites": ["youtube"],
        "terms": ["recommended", "recommendations", "sidebar", "suggested videos"],
        "guidance": (
            "YouTube recommendations sidebar: on watch pages target `#secondary`, "
            "`ytd-watch-next-secondary-results-renderer`, and compact video lists in "
            "the secondary column. Do not hide the primary video column or search "
            "results. Use a page check for `/watch` where useful."
        ),
    },
    {
        "id": "youtube-keyword-filter",
        "title": "Filter YouTube Videos By Keywords",
        "sites": ["youtube"],
        "terms": ["filter", "keyword", "keywords", "videos with"],
        "guidance": (
            "YouTube semantic filtering: identify each video item using containers "
            "like `ytd-rich-item-renderer`, `ytd-video-renderer`, "
            "`ytd-compact-video-renderer`, or playlist renderers. Extract title, "
            "channel, metadata, and URL. For semantic filters, call "
            "`POST http://localhost:8000/api/classify` and hide only non-matching "
            "items after classification returns. Cache by video URL/id."
        ),
    },
    {
        "id": "youtube-absolute-focus",
        "title": "YouTube Absolute Thumbnail Focus Mode",
        "sites": ["youtube"],
        "terms": [
            "absolute focus",
            "focus mode",
            "distractions",
            "only thumbnails",
            "thumbnail grid",
            "matrix",
            "brutalist",
        ],
        "guidance": (
            "YouTube absolute focus: use a document class plus YouTube-specific "
            "selectors to hide masthead/top navigation, guide/mini-guide, chips, "
            "comments, related/sidebar, rich sections, reels shelves, metadata, "
            "titles, channel names, avatars, and header tags. Preserve only video "
            "cards that contain `ytd-thumbnail a#thumbnail[href*='/watch']`, hide "
            "non-video rich items, and reflow `#contents.ytd-rich-grid-renderer` "
            "or section contents into an edge-to-edge CSS grid. Do not hide "
            "`ytd-app` or the whole page root."
        ),
    },
    {
        "id": "instagram-nav",
        "title": "Remove Instagram Sidebar Items",
        "sites": ["instagram"],
        "terms": ["reels", "explore", "messages", "message", "dm", "sidebar", "nav"],
        "guidance": (
            "Instagram nav/sidebar: prefer link and ARIA signals over generated class "
            "names. Reels usually has anchors with `/reels/`; Explore has `/explore/`; "
            "messages/direct has `/direct/` or labels/text like Messages. Hide the "
            "nearest navigation item such as the anchor, `li`, or role=listitem, not "
            "the whole nav/sidebar. Use MutationObserver for route changes."
        ),
    },
    {
        "id": "instagram-suggested-posts",
        "title": "Hide Instagram Suggested Posts",
        "sites": ["instagram"],
        "terms": ["suggested", "suggestions", "suggested posts", "recommended"],
        "guidance": (
            "Instagram suggested posts: inspect feed articles under `main` and look "
            "for local labels such as Suggested, Suggested for you, or Follow. Hide "
            "only the article/card that owns that label. Avoid broad text scans across "
            "the entire document or hiding `main`."
        ),
    },
    {
        "id": "instagram-floating-messages",
        "title": "Remove Instagram Floating Message Drawer",
        "sites": ["instagram"],
        "terms": ["messages bar", "bottom right", "floating", "drawer"],
        "guidance": (
            "Instagram floating messages drawer: target fixed-position bottom/right "
            "containers with message/direct labels or buttons. Use bounding box style "
            "signals (`position: fixed`, lower half of viewport, right side) plus text "
            "or link signals. Hide only that floating container, not global nav."
        ),
    },
    {
        "id": "instagram-engagement-counts",
        "title": "Hide Instagram Likes And Comment Counts",
        "sites": ["instagram"],
        "terms": ["likes", "comments counts", "like count", "comment count"],
        "guidance": (
            "Instagram engagement counts: target count text near feed article action "
            "bars and links/buttons related to likes/comments. Keep action buttons "
            "usable unless the user asks to remove them. Avoid hiding the full article."
        ),
    },
    {
        "id": "doomscroll-guillotine",
        "title": "Instagram/TikTok Doomscroll Guillotine",
        "sites": ["instagram", "tiktok"],
        "terms": [
            "doomscroll",
            "doom scrolling",
            "10 videos",
            "ten videos",
            "go outside",
            "guillotine",
            "counter",
            "video limit",
        ],
        "guidance": (
            "Short-form doomscroll limiter: observe `video` elements with an "
            "IntersectionObserver plus scroll/resize center-line checks. Count each "
            "unique HTMLVideoElement once when it crosses the center of the viewport. "
            "Inject a fixed red circular counter in the top-right showing `X/10`. "
            "At 10, add a full-screen black overlay with z-index 2147483647 and lock "
            "scroll by adding classes to html/body plus wheel/touch/key event guards. "
            "Do not style document.body directly; use classes and CSS."
        ),
    },
    {
        "id": "gmail-tabs",
        "title": "Hide Gmail Promotions Or Social Tabs",
        "sites": ["gmail"],
        "terms": ["promotions", "social tab", "tabs", "categories"],
        "guidance": (
            "Gmail category tabs: target tab controls with role=tab or aria-label/text "
            "containing Promotions or Social. Hide the tab and associated category "
            "container only; keep the inbox list visible."
        ),
    },
    {
        "id": "gmail-sender-highlight",
        "title": "Highlight Gmail Unread Sender",
        "sites": ["gmail"],
        "terms": ["unread", "sender", "from", "highlight emails"],
        "guidance": (
            "Gmail sender highlighting: scan visible email rows (`tr`, role=row, or "
            "Gmail list item rows) that are unread via bold/ARIA/class signals. Match "
            "sender text from the user's request and add a highlight class to the row. "
            "Do not alter read emails unless requested."
        ),
    },
    {
        "id": "gmail-focus",
        "title": "Gmail Focus Mode",
        "sites": ["gmail"],
        "terms": ["focus mode", "sidebars", "ads"],
        "guidance": (
            "Gmail focus mode: hide side navigation, right add-ons rail, ads, and "
            "promotional panels while preserving the message list, compose button, "
            "search, and open email content."
        ),
    },
    {
        "id": "email-deadlines",
        "title": "Highlight Deadline Or Action Emails",
        "sites": ["gmail", "outlook"],
        "terms": ["deadline", "deadlines", "action items", "action item", "due"],
        "guidance": (
            "Deadline/action email highlighting: identify visible email rows/cards and "
            "extract sender, subject, and snippet. For semantic action/deadline checks, "
            "batch rows through `/api/classify`; then add a highlight class to matching "
            "rows. Keep unmatched rows visible."
        ),
    },
    {
        "id": "outlook-panels",
        "title": "Hide Outlook Promotional Panels",
        "sites": ["outlook"],
        "terms": ["outlook", "ads", "promotional", "promotions", "panels"],
        "guidance": (
            "Outlook ads/promotional panels: prefer ARIA labels, role=complementary, "
            "and local text like Advertisement, Premium, Upgrade, or Suggested. Hide "
            "only ad/promo panels and right rails, not message rows or reading pane."
        ),
    },
    {
        "id": "outlook-highlight-sender",
        "title": "Highlight Outlook Sender",
        "sites": ["outlook"],
        "terms": ["boss", "professor", "team", "sender", "highlight outlook"],
        "guidance": (
            "Outlook sender highlighting: target message list rows/cards using role=row "
            "or message list item containers. Match sender/team text from the request "
            "and apply a highlight class to the row without hiding other mail."
        ),
    },
    {
        "id": "calendar-meeting-prep",
        "title": "Outlook Meeting Prep Banner",
        "sites": ["outlook", "calendar"],
        "terms": ["meeting prep", "banner", "calendar event"],
        "guidance": (
            "Meeting prep banner: on calendar event detail panes/dialogs, detect title, "
            "attendees, time, and body/description. Inject one small banner at the top "
            "of the event panel. Avoid injecting duplicates; mark injected nodes with a "
            "data attribute."
        ),
    },
    {
        "id": "google-calendar-keywords",
        "title": "Color-Code Google Calendar Keywords",
        "sites": ["calendar"],
        "terms": ["color-code", "color code", "exam", "meeting", "deadline"],
        "guidance": (
            "Google Calendar keyword colors: target event chips/buttons by event text "
            "and aria-label/title. Apply CSS classes based on user keywords such as "
            "exam, meeting, or deadline. Do not recolor the whole grid cell."
        ),
    },
    {
        "id": "google-calendar-weekends",
        "title": "Hide Google Calendar Weekends",
        "sites": ["calendar"],
        "terms": ["hide weekends", "weekends", "saturday", "sunday"],
        "guidance": (
            "Google Calendar weekends: hide columns/cells whose column header or aria "
            "label indicates Saturday/Sunday. Preserve weekday columns and event text. "
            "Re-run after view changes."
        ),
    },
    {
        "id": "calendar-missing-location",
        "title": "Warn On Events Missing Location Or Link",
        "sites": ["calendar", "outlook"],
        "terms": ["warning", "no location", "missing location", "no link"],
        "guidance": (
            "Calendar missing location/link warning: inspect event detail panels for "
            "location or meeting-link fields. If missing, inject a compact warning "
            "inside the panel. Do not block editing or navigation."
        ),
    },
    {
        "id": "linkedin-feed",
        "title": "Hide LinkedIn Feed",
        "sites": ["linkedin"],
        "terms": ["feed", "posts", "keep messages", "jobs visible"],
        "guidance": (
            "LinkedIn feed hiding: on the homepage hide feed post containers such as "
            "updates/scaffold feed items while preserving top nav, messaging, jobs, "
            "and profile navigation. Do not hide `/jobs` or `/messaging` pages."
        ),
    },
    {
        "id": "linkedin-promoted",
        "title": "Hide LinkedIn Promoted Posts",
        "sites": ["linkedin"],
        "terms": ["promoted", "ads", "sponsored"],
        "guidance": (
            "LinkedIn promoted posts: identify feed cards with local labels such as "
            "Promoted, Sponsored, or Ad and hide only that feed card. Avoid text scans "
            "that climb to the entire main feed."
        ),
    },
    {
        "id": "linkedin-page-filter",
        "title": "Filter LinkedIn Pages",
        "sites": ["linkedin"],
        "terms": ["filter linkedin", "specific linkedin pages", "company pages"],
        "guidance": (
            "LinkedIn page filtering: identify result/feed cards by company/page title, "
            "URL, and subtitle. For semantic matching, use `/api/classify`; for exact "
            "company names from the user, match normalized visible text and hide or "
            "highlight only the card."
        ),
    },
    {
        "id": "x-for-you",
        "title": "Hide X For You Feed",
        "sites": ["twitter", "x"],
        "terms": ["for you", "following only", "feed"],
        "guidance": (
            "X/Twitter For You: target tab controls with text/aria-label For you and "
            "prefer selecting/keeping Following when possible. If hiding, hide For You "
            "timeline content, not the entire app shell. Use data-testid signals."
        ),
    },
    {
        "id": "x-trending",
        "title": "Hide X Trending Sidebar",
        "sites": ["twitter", "x"],
        "terms": ["trending", "trends", "sidebar"],
        "guidance": (
            "X/Twitter trending sidebar: target complementary/right-column sections "
            "with aria labels or headings like What's happening, Trends, or Trending. "
            "Keep the main timeline and compose controls visible."
        ),
    },
    {
        "id": "x-engagement-bait",
        "title": "Remove Low-Like Verified X Replies",
        "sites": ["twitter", "x"],
        "terms": [
            "verified",
            "blue check",
            "blue checkmark",
            "engagement bait",
            "spam replies",
            "bot replies",
            "low likes",
            "less than 100",
        ],
        "guidance": (
            "X/Twitter engagement bait reply cleanup: only run on tweet thread URLs "
            "matching `/status/<id>` so the home timeline infinite scroll is never "
            "broken. Inside `[data-testid='primaryColumn']`, collect tweet `article` "
            "nodes and skip the first article because it is the original tweet. For "
            "reply articles, detect verified badges via `[data-testid='icon-verified']` "
            "or verified SVG aria labels. Parse like counts from role=group or like "
            "button aria/text, handling commas and K/M suffixes. Remove the owning "
            "`[data-testid='cellInnerDiv']` only when verified and under 100 likes."
        ),
    },
    {
        "id": "netflix-roulette",
        "title": "Netflix TV Roulette",
        "sites": ["netflix"],
        "terms": [
            "random episode",
            "roulette",
            "tv roulette",
            "random show",
            "decision paralysis",
            "first episode",
        ],
        "guidance": (
            "Netflix roulette: inject one visible button into native controls such as "
            "`.button-controls-container`, `[data-uia='button-controls-container']`, "
            "`.jawBoneActions`, or `.billboard-links`, with CSS that mimics Netflix "
            "white play buttons. On click, find visible playable cards from episode "
            "items, title cards, slider items, or `/watch/` anchors. Prefer the first "
            "playable card from each row/section, choose a random row, scroll it into "
            "view, and dispatch pointer/mouse/click events."
        ),
    },
    {
        "id": "reddit-sidebar",
        "title": "Remove Reddit Sidebar And Recent Posts",
        "sites": ["reddit"],
        "terms": ["sidebar", "recent posts", "recent"],
        "guidance": (
            "Reddit sidebar/recent posts: do not rely on only "
            "`div[data-testid='sidebar-widget']`; modern Reddit often uses custom "
            "elements and right-rail containers. Build a multi-signal detector that "
            "checks `aside`, `[role='complementary']`, `shreddit-sidebar`, "
            "`reddit-sidebar`, `[slot*='right']`, `[data-testid*='right']`, "
            "`[data-testid*='sidebar']`, and custom elements/partials whose tag, "
            "id, class, aria-label, heading, or nearby text includes Recent Posts. "
            "Use `getBoundingClientRect()` as a fallback to require the candidate to "
            "sit on the right side of the viewport before hiding it. Hide only the "
            "smallest owning widget/panel, never `main`, the post list, or comments."
        ),
    },
    {
        "id": "reddit-collapse-comments",
        "title": "Collapse Reddit Comment Chains",
        "sites": ["reddit"],
        "terms": ["collapse comments", "comment chains", "comments"],
        "guidance": (
            "Reddit comment chains: target comment containers and use their built-in "
            "collapse buttons when available; otherwise add a compact class that hides "
            "comment bodies/replies while preserving author/header and a visible affordance."
        ),
    },
]

# Scores combine site (4) + terms (2–5). Site-only ≈4 is too weak to run a
# hard-coded product template: we require a clear intent + site alignment.
DETERMINISTIC_INTENT_MIN_SCORE = 7

# Fused per-site notes for the LLM when the user’s ask is *not* a direct match to a
# single corpus row but the host is one we know well.
SITE_DOM_BOOTSTRAP: dict[str, str] = {
    "youtube": (
        "YouTube (general): heavy custom elements (ytd-*) in Shadow DOM; match "
        "ytd-rich-item-renderer, ytd-video-renderer, ytd-compact-video-renderer, "
        "ytd-reel-shelf-renderer, ytd-guide-* for nav. Watch page has primary column "
        "plus #secondary. SPA navigation — MutationObserver. Prefer href checks for "
        "/shorts, /watch. Avoid hiding ytd-app root or entire rich-grid."
    ),
    "instagram": (
        "Instagram (general): [role=main] feed, article per post, nav links in "
        "header/sidebar. Routes /reels/, /direct/, /explore/. Sticky headers and "
        "infinite scroll; use scoped selectors and re-run on route changes. Avoid "
        "hiding main or every article."
    ),
    "tiktok": (
        "TikTok (general): short-form feed built around `video` elements, dynamic "
        "infinite scroll, and route changes. Prefer IntersectionObserver plus "
        "viewport center checks for video tracking. Use fixed overlays carefully and "
        "lock scroll with classes/event guards rather than direct body styling."
    ),
    "gmail": (
        "Gmail (general): list rows in table-like structures, role=row, tr, category "
        "tabs role=tab. Split panes: list, thread, right rail. Class names are obfuscated; "
        "prefer ARIA, data attributes, and stable list structure, not a single class."
    ),
    "outlook": (
        "Outlook (general): list rows, reading pane, complementary ads rail. Opaque "
        "classnames — use list patterns, ARIA, message cards, and region roles."
    ),
    "calendar": (
        "Google Calendar (general): time grid, event chips, popover detail, keyboard "
        "ARIA. Week/day/month views; re-run on view changes and event loads."
    ),
    "linkedin": (
        "LinkedIn (general): feed cards (feed-shared-update-*, scroller), nav global, "
        "messaging. Promoted/Sponsored labels in-card. Opaque BEM; combine text near "
        "the card, data attributes, and feed structure — never hide entire scaffold."
    ),
    "x": (
        "X / Twitter (general): [data-testid] on tweets, side nav, search, trends; "
        "primary column vs sidebar. Promoted/Ad labels, placement tracking. Popstate + "
        "MutationObserver. Never hide the whole [data-testid=primaryColumn] or root layout."
    ),
    "netflix": (
        "Netflix (general): dynamic React UI with changing generated classes but useful "
        "stable-ish signals like `.button-controls-container`, `.titleCard`, slider rows, "
        "episode items, `[data-uia]`, and `/watch/` anchors. Inject controls idempotently, "
        "style them to match Netflix buttons, and dispatch real pointer/mouse events."
    ),
    "reddit": (
        "Reddit (general): custom elements (shreddit-*), post threads, comment trees, "
        "right rail aside/complementary. New vs old — mix selectors, viewport checks "
        "for right-rail, data-testid. Avoid main post column."
    ),
}


def _requested_sites_from_haystack(haystack: str, tokens: set[str]) -> set[str]:
    return {
        site
        for entry in DOM_IMPLEMENTATION_CORPUS
        for site in entry["sites"]
        if _site_matches(site, haystack, tokens)
    }


def intent_score_for_entry(
    query: str,
    target_urls: list[str],
    entry: dict[str, Any],
) -> int:
    """Same scoring as retrieve_context ranking, for a single corpus entry."""
    haystack = f"{query} {' '.join(target_urls)}".lower()
    tokens = set(re.findall(r"[a-z0-9]+", haystack))
    requested_sites = _requested_sites_from_haystack(haystack, tokens)
    score = 0
    entry_site_match = False
    for site in entry.get("sites", []):
        if _site_matches(str(site), haystack, tokens):
            score += 4
            entry_site_match = True
    if requested_sites and not entry_site_match:
        return 0
    for term in entry.get("terms", []):
        term_lower = str(term).lower()
        if term_lower in haystack:
            score += 5 if " " in term_lower else 3
        elif term_lower in tokens:
            score += 2
    return score


def should_apply_deterministic_template(
    query: str, target_urls: list[str], entry: dict[str, Any]
) -> bool:
    """True only when the user query clearly matches this curated nudge, not just the host."""
    return intent_score_for_entry(query, target_urls, entry) >= DETERMINISTIC_INTENT_MIN_SCORE


def _score_entries(query: str, target_urls: list[str]) -> list[dict[str, Any]]:
    scored: list[tuple[int, dict[str, Any]]] = []
    for entry in DOM_IMPLEMENTATION_CORPUS:
        score = intent_score_for_entry(query, target_urls, entry)
        if score:
            scored.append((score, entry))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [entry for _, entry in scored]


def retrieve_context_entries(
    query: str,
    target_urls: list[str],
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Return the highest scoring corpus entries for this request."""
    return _score_entries(query, target_urls)[:limit]


def retrieve_context(query: str, target_urls: list[str], limit: int = 5) -> list[str]:
    """Return the most relevant implementation context for the request."""
    return [
        f"{entry['title']}: {entry['guidance']}"
        for entry in retrieve_context_entries(query, target_urls, limit=limit)
    ]


def canonical_sites_in_target_urls(target_urls: list[str]) -> list[str]:
    """Resolve manifest URL patterns to known site keys for DOM bootstrap hints."""
    found: list[str] = []
    for raw in target_urls:
        h = (raw or "").lower()
        if not h:
            continue
        for key, needle in (
            ("youtube", "youtube"),
            ("youtube", "youtu.be"),
            ("reddit", "reddit.com"),
            ("reddit", "old.reddit"),
            ("instagram", "instagram.com"),
            ("tiktok", "tiktok.com"),
            ("gmail", "mail.google.com"),
            ("gmail", "mail.google"),
            ("outlook", "outlook."),
            ("outlook", "outlook.com"),
            ("outlook", "office.com"),
            ("calendar", "calendar.google.com"),
            ("calendar", "google.com/calendar"),
            ("linkedin", "linkedin.com"),
            ("x", "x.com"),
            ("x", "twitter.com"),
            ("netflix", "netflix.com"),
        ):
            if needle in h and key not in found:
                found.append(key)
    return found


def site_bootstrap_for_urls(target_urls: list[str]) -> list[str]:
    """LLM context lines for *novel* per-site work using shared DOM knowledge."""
    lines: list[str] = []
    for key in canonical_sites_in_target_urls(target_urls):
        text = SITE_DOM_BOOTSTRAP.get(key)
        if text:
            label = "X (Twitter)" if key == "x" else key.replace("-", " ").title()
            lines.append(f"Site overview ({label}): {text}")
    return lines


def _site_matches(site: str, haystack: str, tokens: set[str]) -> bool:
    if site == "x":
        return "x.com" in haystack or "twitter.com" in haystack or "twitter" in tokens or "x" in tokens
    if site == "youtube":
        return (
            site in tokens
            or f"{site}.com" in haystack
            or f"www.{site}.com" in haystack
            or "youtu.be" in haystack
        )
    return site in tokens or f"{site}.com" in haystack or f"www.{site}.com" in haystack


def retrieve_nudges(query: str, target_urls: list[str], limit: int = 5) -> list[str]:
    """Backward-compatible wrapper for older imports."""
    return retrieve_context(query, target_urls, limit)
