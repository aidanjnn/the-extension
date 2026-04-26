"""Extension Codegen Agent role."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

from agentverse_app import backend_client
from agentverse_app.messages import CodegenRequest, CodegenResult
from utils.config import get_provider_config, get_secondary_client

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Hardcoded "Killer Demo" payloads — bypasses the LLM for reliable live demos
# ---------------------------------------------------------------------------

def _make_manifest(name: str, target_urls: list[str], *, include_css: bool = False) -> str:
    content_script: dict[str, Any] = {
        "matches": target_urls,
        "js": ["content.js"],
        "run_at": "document_idle",
    }
    if include_css:
        content_script["css"] = ["content.css"]

    return json.dumps({
        "manifest_version": 3,
        "name": name[:45],
        "version": "1.0",
        "description": "Browser Forge Demo Extension",
        "content_scripts": [content_script],
    }, indent=2)


def _get_linkedin_demo(target_urls: list[str], name: str) -> dict[str, str]:
    return {
        "manifest.json": _make_manifest(name, ["https://www.linkedin.com/*"], include_css=True),
        "content.js": """\
(() => {
    const hiringPattern = /\\b(hiring|we are hiring|now hiring|join our team|open role|open roles|job opening|job openings|internship|internships|intern\\b|summer intern|fall intern|new grad|new graduate|graduate role|early career|entry level|campus recruiting|software engineer intern|swe intern|recruiting|referrals?|apply now|career opportunity|full[-\\s]?time role|return offer|co[-\\s]?op)\\b/i;

    function highlightHiringPosts(root = document) {
        root.querySelectorAll('.feed-shared-update-v2, [data-urn*="activity"]').forEach(post => {
            if (!(post instanceof HTMLElement) || post.dataset.bfHiringChecked === 'true') return;
            const text = post.innerText || '';
            if (!hiringPattern.test(text)) {
                post.dataset.bfHiringChecked = 'true';
                return;
            }

            post.dataset.bfHiringChecked = 'true';
            post.classList.add('bf-hiring-highlight');
            if (getComputedStyle(post).position === 'static') {
                post.style.position = 'relative';
            }

            if (!post.querySelector(':scope > .bf-hiring-badge')) {
                const badge = document.createElement('div');
                badge.className = 'bf-hiring-badge';
                badge.textContent = '🚨 HIRING 🚨';
                post.appendChild(badge);
            }
        });
    }

    const schedule = (() => {
        let frame = 0;
        return () => {
            if (frame) cancelAnimationFrame(frame);
            frame = requestAnimationFrame(() => {
                frame = 0;
                highlightHiringPosts();
            });
        };
    })();

    highlightHiringPosts();
    new MutationObserver(schedule).observe(document.documentElement, { childList: true, subtree: true });
    setInterval(highlightHiringPosts, 2500);
})();
""",
        "content.css": """\
.bf-hiring-highlight {
  border: 5px solid #ff0000 !important;
  box-shadow: 0 0 22px rgba(255, 0, 0, 0.65) !important;
  border-radius: 10px !important;
  transform: scale(1.015);
  transition: border-color 160ms ease, box-shadow 160ms ease, transform 160ms ease;
  z-index: 2;
}

.bf-hiring-badge {
  position: absolute;
  top: -14px;
  right: -14px;
  z-index: 999999;
  padding: 6px 14px;
  border-radius: 999px;
  background: #e00000;
  color: #fff;
  font: 800 13px/1.2 Arial, sans-serif;
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.35);
  pointer-events: none;
}
""",
    }


def _get_twitter_demo(_target_urls: list[str], name: str) -> dict[str, str]:
    return {
        "manifest.json": _make_manifest(name, ["https://x.com/*", "https://twitter.com/*"]),
        "content.js": """\
(() => {
    function isThreadPage() {
        return /\\/status\\/\\d+/.test(window.location.pathname);
    }

    function parseLikeCount(label) {
        if (!label) return 0;
        const match = String(label).match(/([\\d,.]+)\\s*([KMB])?\\s+likes?/i);
        if (!match) return 0;
        const value = parseFloat(match[1].replace(/,/g, ''));
        const suffix = (match[2] || '').toUpperCase();
        const multiplier = suffix === 'K' ? 1000 : suffix === 'M' ? 1000000 : suffix === 'B' ? 1000000000 : 1;
        return Number.isFinite(value) ? value * multiplier : 0;
    }

    function nukeLowEngagementVerifiedReplies(root = document) {
        if (!isThreadPage()) return;
        const articles = Array.from(root.querySelectorAll('article'));
        if (root === document) {
            articles.splice(0, 1);
        }

        articles.forEach(article => {
            if (!(article instanceof HTMLElement) || article.dataset.bfSpamScanned === 'true') return;
            const isVerified = article.querySelector('svg[data-testid="icon-verified"], svg[aria-label="Verified account"]');
            if (!isVerified) {
                article.dataset.bfSpamScanned = 'true';
                return;
            }

            article.dataset.bfSpamScanned = 'true';
            const likeBtn = article.querySelector('[data-testid="like"], [aria-label*="Like"]');
            const likeText = likeBtn ? (likeBtn.getAttribute('aria-label') || likeBtn.textContent || '') : '';
            if (parseLikeCount(likeText) < 100) {
                const cell = article.closest('[data-testid="cellInnerDiv"]');
                (cell || article).remove();
            }
        });
    }

    const schedule = (() => {
        let frame = 0;
        return () => {
            if (frame) return;
            frame = requestAnimationFrame(() => {
                frame = 0;
                nukeLowEngagementVerifiedReplies();
            });
        };
    })();

    nukeLowEngagementVerifiedReplies();
    new MutationObserver(schedule).observe(document.documentElement, { childList: true, subtree: true });
    setInterval(nukeLowEngagementVerifiedReplies, 1200);
})();
""",
        "content.css": "",
    }


def _get_amazon_demo(_target_urls: list[str], name: str) -> dict[str, str]:
    return {
        "manifest.json": _make_manifest(name, ["https://www.amazon.com/*"], include_css=True),
        "content.js": """\
(() => {
    function parsePrice(item) {
        const offscreen = item.querySelector('.a-price .a-offscreen, .a-price[data-a-color] .a-offscreen');
        const raw = offscreen?.textContent || item.querySelector('.a-price-whole')?.textContent || '';
        const match = raw.replace(/,/g, '').match(/\\$?\\s*(\\d+(?:\\.\\d{1,2})?)/);
        return match ? Number.parseFloat(match[1]) : Infinity;
    }

    function isSponsored(item) {
        const text = item.innerText || '';
        return /\\bSponsored\\b/i.test(text) || Boolean(item.querySelector('.puis-sponsored-label-text, [aria-label="Sponsored"]'));
    }

    function scanAmazonResults() {
        let cheapestItem = null;
        let minPrice = Infinity;

        document.querySelectorAll('[data-asin]').forEach(item => {
            if (!(item instanceof HTMLElement) || !item.getAttribute('data-asin')) return;
            item.classList.remove('bf-cheapest-item');

            if (isSponsored(item)) {
                item.classList.add('bf-sponsored-hidden');
                return;
            }

            const price = parsePrice(item);
            if (price > 0 && price < minPrice) {
                minPrice = price;
                cheapestItem = item;
            }
        });

        if (cheapestItem) {
            cheapestItem.classList.add('bf-cheapest-item');
        }
    }

    const schedule = (() => {
        let timer = 0;
        return () => {
            clearTimeout(timer);
            timer = setTimeout(scanAmazonResults, 250);
        };
    })();

    setTimeout(scanAmazonResults, 1200);
    new MutationObserver(schedule).observe(document.documentElement, { childList: true, subtree: true });
})();
""",
        "content.css": """\
.bf-sponsored-hidden {
  display: none !important;
}

.bf-cheapest-item {
  border: 4px solid #39ff14 !important;
  box-shadow: 0 0 22px #39ff14 !important;
  border-radius: 8px !important;
  transition: border-color 160ms ease, box-shadow 160ms ease;
}
""",
    }


def _get_netflix_demo(_target_urls: list[str], name: str) -> dict[str, str]:
    return {
        "manifest.json": _make_manifest(name, ["https://www.netflix.com/*"], include_css=True),
        "content.js": """\
(() => {
    function injectRouletteButton() {
        const btnContainer = document.querySelector('.button-controls-container, .previewModal--player-titleTreatment-left');
        if (!btnContainer || document.getElementById('bf-random-btn')) return;

        const btn = document.createElement('button');
        btn.id = 'bf-random-btn';
        btn.type = 'button';
        btn.textContent = '🎲 Random Episode';
        btn.className = 'bf-random-episode-btn';
        btn.addEventListener('click', () => {
            const episodes = Array.from(document.querySelectorAll('.titleCard-title_text, [data-uia*="episode-title"], .episodeTitle'));
            if (episodes.length === 0) {
                alert('Open the episodes list first, then hit Random Episode.');
                return;
            }

            const selected = episodes[Math.floor(Math.random() * episodes.length)];
            const clickable = selected.closest('a, button, .titleCard, .episodeSelector') || selected;
            clickable.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
        });

        btnContainer.appendChild(btn);
    }

    injectRouletteButton();
    new MutationObserver(injectRouletteButton).observe(document.documentElement, { childList: true, subtree: true });
})();
""",
        "content.css": """\
.bf-random-episode-btn {
  margin-left: 10px !important;
  padding: 0.8rem 1.5rem !important;
  border: 0 !important;
  border-radius: 4px !important;
  background: rgba(109, 109, 110, 0.75) !important;
  color: #fff !important;
  cursor: pointer !important;
  font: 800 1.1vw/1 Netflix Sans, Helvetica Neue, Segoe UI, Roboto, sans-serif !important;
}

.bf-random-episode-btn:hover {
  background: rgba(109, 109, 110, 0.45) !important;
}
""",
    }


def _get_doomscroll_demo(_target_urls: list[str], name: str) -> dict[str, str]:
    return {
        "manifest.json": _make_manifest(name, ["https://www.instagram.com/*", "https://www.tiktok.com/*"], include_css=True),
        "content.js": """\
(() => {
    let videosScrolled = 0;
    let guillotineDropped = false;
    const countedVideos = new WeakSet();

    function ensureCounter() {
        let counterUI = document.getElementById('bf-doom-counter');
        if (!counterUI) {
            counterUI = document.createElement('div');
            counterUI.id = 'bf-doom-counter';
            document.documentElement.appendChild(counterUI);
        }
        counterUI.textContent = `${Math.min(videosScrolled, 10)}/10`;
        return counterUI;
    }

    function dropGuillotine() {
        if (guillotineDropped) return;
        guillotineDropped = true;
        ensureCounter().textContent = '10/10';

        const wall = document.createElement('div');
        wall.id = 'bf-doom-wall';
        wall.textContent = "KABOOM. That's enough for today. Go outside.";
        document.documentElement.appendChild(wall);
        document.documentElement.style.overflow = 'hidden';
        document.body.style.overflow = 'hidden';
    }

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (!entry.isIntersecting || guillotineDropped || countedVideos.has(entry.target)) return;
            countedVideos.add(entry.target);
            observer.unobserve(entry.target);
            videosScrolled += 1;
            ensureCounter();
            if (videosScrolled >= 10) dropGuillotine();
        });
    }, { threshold: 0.75 });

    function watchVideos() {
        ensureCounter();
        document.querySelectorAll('video').forEach(vid => {
            if (!(vid instanceof HTMLVideoElement) || vid.dataset.bfTracked === 'true') return;
            vid.dataset.bfTracked = 'true';
            observer.observe(vid);
        });
    }

    watchVideos();
    new MutationObserver(watchVideos).observe(document.documentElement, { childList: true, subtree: true });
    setInterval(watchVideos, 1500);
})();
""",
        "content.css": """\
#bf-doom-counter {
  position: fixed !important;
  top: 20px !important;
  right: 20px !important;
  z-index: 2147483646 !important;
  width: 68px !important;
  height: 68px !important;
  border: 3px solid #fff !important;
  border-radius: 50% !important;
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  background: rgba(220, 0, 0, 0.92) !important;
  color: #fff !important;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5) !important;
  font: 900 20px/1 Arial, sans-serif !important;
  pointer-events: none !important;
}

#bf-doom-wall {
  position: fixed !important;
  inset: 0 !important;
  z-index: 2147483647 !important;
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  padding: 2rem !important;
  background: #000 !important;
  color: #fff !important;
  text-align: center !important;
  text-transform: uppercase !important;
  font: 900 clamp(2rem, 7vw, 5rem)/1.05 Arial, sans-serif !important;
}
""",
    }


def _get_youtube_thumbnail_demo(_target_urls: list[str], name: str) -> dict[str, str]:
    return {
        "manifest.json": _make_manifest(name, ["https://www.youtube.com/*"], include_css=True),
        "content.js": """\
(() => {
    function nukeThumbnails() {
        document.querySelectorAll('ytd-thumbnail img.yt-core-image').forEach(img => {
            if (!(img instanceof HTMLElement)) return;
            img.classList.add('bf-thumbnail-nuked');
            img.dataset.bfThumbnailNuked = 'true';
        });

        document.querySelectorAll('ytd-thumbnail #mouseover-overlay').forEach(overlay => {
            if (!(overlay instanceof HTMLElement)) return;
            overlay.classList.add('bf-preview-forced');
        });
    }

    nukeThumbnails();
    new MutationObserver(nukeThumbnails).observe(document.documentElement, { childList: true, subtree: true });
    setInterval(nukeThumbnails, 1800);
})();
""",
        "content.css": """\
ytd-thumbnail img.yt-core-image.bf-thumbnail-nuked {
  opacity: 0 !important;
}

ytd-thumbnail #mouseover-overlay.bf-preview-forced {
  display: block !important;
  opacity: 1 !important;
  visibility: visible !important;
}
""",
    }


def _get_youtube_focus_demo(_target_urls: list[str], name: str) -> dict[str, str]:
    return {
        "manifest.json": _make_manifest(name, ["https://www.youtube.com/*"], include_css=True),
        "content.js": """\
(() => {
    function applyFocusMode() {
        if (window.location.pathname !== '/watch') return;

        ['#secondary', '#comments', '#related'].forEach(selector => {
            const el = document.querySelector(selector);
            if (el instanceof HTMLElement) {
                el.classList.add('bf-youtube-focus-hidden');
            }
        });

        const primary = document.querySelector('#primary');
        if (primary instanceof HTMLElement) {
            primary.classList.add('bf-youtube-focus-primary');
            primary.style.setProperty('max-width', '100%', 'important');
            primary.style.setProperty('padding', '0 5%', 'important');
        }

        const columns = document.querySelector('#columns');
        if (columns instanceof HTMLElement) {
            columns.style.setProperty('justify-content', 'center', 'important');
        }
    }

    applyFocusMode();
    new MutationObserver(applyFocusMode).observe(document.documentElement, { childList: true, subtree: true });
    setInterval(applyFocusMode, 1500);
})();
""",
        "content.css": """\
.bf-youtube-focus-hidden {
  display: none !important;
}

.bf-youtube-focus-primary {
  max-width: 100% !important;
  padding: 0 5% !important;
}
""",
    }


def _get_twitter_community_note_demo(_target_urls: list[str], name: str) -> dict[str, str]:
    return {
        "manifest.json": _make_manifest(name, ["https://x.com/*", "https://twitter.com/*"], include_css=True),
        "content.js": """\
(() => {
    function elevateCommunityNotes() {
        document.querySelectorAll('[data-testid="birdwatch-pivot"]').forEach(note => {
            if (!(note instanceof HTMLElement) || note.dataset.bfFactCheckBoosted === 'true') return;
            note.dataset.bfFactCheckBoosted = 'true';
            note.classList.add('bf-fact-check-note');

            note.querySelectorAll('span').forEach(span => {
                if (span instanceof HTMLElement) span.classList.add('bf-fact-check-text');
            });

            const warning = document.createElement('div');
            warning.className = 'bf-fact-check-label';
            warning.textContent = '🚨 FACT CHECK 🚨';
            note.insertBefore(warning, note.firstChild);
        });
    }

    elevateCommunityNotes();
    new MutationObserver(elevateCommunityNotes).observe(document.documentElement, { childList: true, subtree: true });
    setInterval(elevateCommunityNotes, 1500);
})();
""",
        "content.css": """\
.bf-fact-check-note {
  border: 3px solid #ff0000 !important;
  border-radius: 12px !important;
  background: rgba(255, 0, 0, 0.12) !important;
  box-shadow: 0 0 18px rgba(255, 0, 0, 0.55) !important;
  padding: 16px !important;
  transform: scale(1.03);
  transform-origin: center top;
  transition: transform 160ms ease, box-shadow 160ms ease;
}

.bf-fact-check-label {
  margin-bottom: 8px !important;
  color: #ff0000 !important;
  font: 900 22px/1.15 Arial, sans-serif !important;
  text-align: center !important;
}

.bf-fact-check-text {
  font-size: 18px !important;
  font-weight: 800 !important;
}
""",
    }


def _get_linkedin_translator_demo(_target_urls: list[str], name: str) -> dict[str, str]:
    return {
        "manifest.json": _make_manifest(name, ["https://www.linkedin.com/*"], include_css=True),
        "content.js": """\
(() => {
    const dictionary = [
        ['thrilled to announce', 'bragging that'],
        ['excited to announce', 'bragging that'],
        ['humbled and honored', 'flexing that'],
        ['synergy', 'meaningless buzzword'],
        ['deep dive', 'long meeting about'],
        ['circle back', 'ignore this until later'],
        ['game changer', 'new thing that changes little'],
        ['thought leader', 'person who posts too much'],
        ['fast-paced environment', 'we are understaffed'],
        ['wear many hats', 'do three jobs'],
        ["we're like a family", 'we have boundary issues'],
    ];

    const escapeRegExp = value => value.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&');
    const patterns = dictionary.map(([phrase, translation]) => ({
        phrase,
        translation,
        regex: new RegExp(escapeRegExp(phrase), 'i'),
    }));
    const visited = new WeakSet();

    function translateTextNode(node) {
        if (visited.has(node) || !node.nodeValue || !node.parentElement) return;
        if (node.parentElement.closest('.bf-realtalk-translation')) return;

        let text = node.nodeValue;
        const pieces = [];
        while (text.length > 0) {
            let best = null;
            for (const pattern of patterns) {
                const match = text.match(pattern.regex);
                if (match && (best === null || match.index < best.match.index)) {
                    best = { pattern, match };
                }
            }

            if (!best) {
                pieces.push(document.createTextNode(text));
                break;
            }

            const before = text.slice(0, best.match.index);
            if (before) pieces.push(document.createTextNode(before));

            const span = document.createElement('span');
            span.className = 'bf-realtalk-translation';
            span.title = `Translated from: ${best.pattern.phrase}`;
            span.textContent = `[${best.pattern.translation}]`;
            pieces.push(span);

            text = text.slice(best.match.index + best.match[0].length);
        }

        visited.add(node);
        if (pieces.length === 1 && pieces[0].nodeType === Node.TEXT_NODE) return;
        node.replaceWith(...pieces);
    }

    function translateCorporateSpeak() {
        document.querySelectorAll('.feed-shared-update-v2__description-wrapper, .feed-shared-inline-show-more-text').forEach(container => {
            const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
            const nodes = [];
            while (walker.nextNode()) nodes.push(walker.currentNode);
            nodes.forEach(translateTextNode);
        });
    }

    translateCorporateSpeak();
    new MutationObserver(translateCorporateSpeak).observe(document.documentElement, { childList: true, subtree: true });
    setInterval(translateCorporateSpeak, 2200);
})();
""",
        "content.css": """\
.bf-realtalk-translation {
  display: inline-block;
  padding: 0 4px;
  border-radius: 4px;
  background: #fff200 !important;
  color: #111 !important;
  font-weight: 800 !important;
}
""",
    }


DEMO_PATTERN_MEMORY = {
    "linkedin": (
        "LinkedIn feed posts are usually `.feed-shared-update-v2` or elements with "
        "`data-urn*=\"activity\"`. For visual callouts, add a class to the post, ensure "
        "relative positioning, and append one absolute badge guarded by a data flag."
    ),
    "twitter": (
        "X/Twitter dynamic content should be watched with MutationObserver. Use "
        "`article`, `[data-testid=\"cellInnerDiv\"]`, `[data-testid=\"like\"]`, "
        "`svg[data-testid=\"icon-verified\"]`, and `/status/<id>` guards for thread-only work."
    ),
    "amazon": (
        "Amazon search products expose `[data-asin]`; sponsored labels often appear as "
        "visible `Sponsored` text or `.puis-sponsored-label-text`; prices are more reliable "
        "from `.a-price .a-offscreen` than only `.a-price-whole`."
    ),
    "netflix": (
        "Netflix controls can be enhanced by injecting a native-looking button near "
        "`.button-controls-container`; episode rows/titles may appear as `.titleCard-title_text`, "
        "`[data-uia*=\"episode-title\"]`, or `.episodeTitle`."
    ),
    "instagram": (
        "Instagram/TikTok video demos should track `video` elements with IntersectionObserver, "
        "count each element once with a WeakSet/data flag, and render fixed overlay UI at a very high z-index."
    ),
    "youtube": (
        "YouTube light-DOM selectors include `ytd-thumbnail img.yt-core-image`, "
        "`ytd-thumbnail #mouseover-overlay`, `#secondary`, `#comments`, `#related`, and `#primary`. "
        "Use `style.setProperty(..., 'important')` when JS must apply important layout overrides."
    ),
    "general": (
        "Reliable demo extensions use content scripts only, site-specific selectors, class-based CSS, "
        "idempotent data flags, MutationObserver plus a slow interval fallback, and minimal manifest fields."
    ),
}


def _context_text(query: str, target_urls: list[str]) -> str:
    return f"{query} {' '.join(target_urls)}".lower()


def _has_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def _demo_pattern_context(query: str, target_urls: list[str]) -> str:
    """Return compact implementation memory for non-exact demo prompts."""
    context = _context_text(query, target_urls)
    selected = ["general"]
    site_terms = {
        "linkedin": ("linkedin", "linkedin.com"),
        "twitter": ("twitter", "x.com"),
        "amazon": ("amazon", "amazon.com"),
        "netflix": ("netflix", "netflix.com"),
        "instagram": ("instagram", "tiktok", "instagram.com", "tiktok.com"),
        "youtube": ("youtube", "youtube.com"),
    }
    for site, terms in site_terms.items():
        if _has_any(context, terms):
            selected.append(site)

    return "\n".join(
        f"- {site.title()}: {DEMO_PATTERN_MEMORY[site]}"
        for site in dict.fromkeys(selected)
    )


async def _check_hardcoded_demos(
    query: str,
    target_urls: list[str],
    extension_name: str,
) -> dict[str, str] | None:
    q = query.lower()
    context = _context_text(query, target_urls)

    if _has_any(context, ("linkedin", "linkedin.com")) and _has_any(q, ("translate", "real talk", "bullshit", "corporate speak", "buzzword")):
        await asyncio.sleep(4.7)
        return _get_linkedin_translator_demo(target_urls, extension_name)

    linkedin_hiring_terms = (
        "hiring", "intern", "internship", "new grad", "new graduate", "open role",
        "open roles", "job opening", "career opportunity", "recruiting",
    )
    if _has_any(context, ("linkedin", "linkedin.com")) and _has_any(q, linkedin_hiring_terms):
        await asyncio.sleep(3.5)
        return _get_linkedin_demo(target_urls, extension_name)

    if _has_any(context, ("linkedin", "linkedin.com")) and _has_any(q, ("humble", "thrilled to announce", "cringe")):
        await asyncio.sleep(3.5)
        return _get_linkedin_demo(target_urls, extension_name)

    if _has_any(context, ("twitter", "x.com")) and _has_any(q, ("community note", "community notes", "fact check", "fact-check")):
        await asyncio.sleep(3.9)
        return _get_twitter_community_note_demo(target_urls, extension_name)

    if ("verified" in q or "blue check" in q or "spam" in q) and (
        "twitter" in str(target_urls) or "x.com" in str(target_urls) or "twitter" in q or "x.com" in q
    ):
        await asyncio.sleep(4.2)
        return _get_twitter_demo(target_urls, extension_name)

    amazon_short_demo = bool(re.fullmatch(r"\s*(amazon|amazon demo|amazon de-?scammer)\s*", q))
    if (
        _has_any(context, ("amazon", "amazon.com"))
        and (_has_any(q, ("sponsored", "cheapest", "de-scam", "descam", "scam", "scammer")) or amazon_short_demo)
    ):
        await asyncio.sleep(3.8)
        return _get_amazon_demo(target_urls, extension_name)

    netflix_short_demo = bool(re.fullmatch(r"\s*(netflix|netflix demo)\s*", q))
    if (
        _has_any(context, ("netflix", "netflix.com"))
        and (_has_any(q, ("random", "roulette")) or netflix_short_demo)
    ):
        await asyncio.sleep(4.5)
        return _get_netflix_demo(target_urls, extension_name)

    if "doomscroll" in q or ("outside" in q and ("instagram" in q or "tiktok" in q)) or "10 videos" in q:
        await asyncio.sleep(3.2)
        return _get_doomscroll_demo(target_urls, extension_name)

    if _has_any(context, ("youtube", "youtube.com")) and _has_any(q, ("clickbait", "thumbnail", "thumbnails")):
        await asyncio.sleep(4.1)
        return _get_youtube_thumbnail_demo(target_urls, extension_name)

    if _has_any(context, ("youtube", "youtube.com")) and _has_any(q, ("distraction", "distractions", "focus", "comments", "related videos")):
        await asyncio.sleep(3.6)
        return _get_youtube_focus_demo(target_urls, extension_name)

    return None


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

    user_prompt = (
        f"User request: {_strip_chip_html(query)}\n\n"
        f"Target URLs (use these as manifest content_scripts.matches): "
        f"{json.dumps(target_urls)}\n"
        f"Extension display name: {extension_name}\n\n"
        "Reusable hardcoded-demo knowledge for this request:\n"
        f"{_demo_pattern_context(query, target_urls)}\n\n"
        "Use that knowledge as implementation memory for selectors, DOM timing, and "
        "site-specific patterns. Do not copy an exact hardcoded demo unless the user "
        "asked for that exact behavior.\n\n"
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


def _quality_issues(files: dict[str, str], target_urls: list[str]) -> list[str]:
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

    # Check for hardcoded demo triggers first (bypasses LLM for reliable live demos)
    files = await _check_hardcoded_demos(spec.behavior, spec.target_urls, spec.name)

    if files is None:
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
