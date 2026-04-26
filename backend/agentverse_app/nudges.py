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
            "`href` starts with `/shorts`, and video/grid renderers containing "
            "`a[href^='/shorts/']`. Do not hide all rich-grid rows. Use CSS plus a "
            "MutationObserver that marks only the matched container."
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
        "id": "reddit-sidebar",
        "title": "Remove Reddit Sidebar And Recent Posts",
        "sites": ["reddit"],
        "terms": ["sidebar", "recent posts", "recent"],
        "guidance": (
            "Reddit sidebar/recent posts: target right sidebar/complementary panels and "
            "recent-posts widgets by role, heading text, or `data-testid` where "
            "available. Keep the main post list and comments visible."
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


def retrieve_context(query: str, target_urls: list[str], limit: int = 5) -> list[str]:
    """Return the most relevant implementation context for the request."""
    haystack = f"{query} {' '.join(target_urls)}".lower()
    tokens = set(re.findall(r"[a-z0-9]+", haystack))
    scored: list[tuple[int, dict[str, Any]]] = []

    for entry in DOM_IMPLEMENTATION_CORPUS:
        score = 0
        for site in entry["sites"]:
            if site in haystack:
                score += 4
        for term in entry["terms"]:
            term_lower = term.lower()
            if term_lower in haystack:
                score += 5 if " " in term_lower else 3
            elif term_lower in tokens:
                score += 2
        if score:
            scored.append((score, entry))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [
        f"{entry['title']}: {entry['guidance']}"
        for _, entry in scored[:limit]
    ]


def retrieve_nudges(query: str, target_urls: list[str], limit: int = 5) -> list[str]:
    """Backward-compatible wrapper for older imports."""
    return retrieve_context(query, target_urls, limit)
