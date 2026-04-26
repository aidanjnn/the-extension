# Implementation Plan: Hacked Demos (Part 2)

## Feature Overview
This plan extends your existing `_check_hardcoded_demos` logic in `backend/agentverse_app/codegen.py` to add 4 new highly-visual demos (YouTube, Twitter Community Notes, and LinkedIn Translator). 

---

## 1. Adding the New Helper Functions
**File:** `backend/agentverse_app/codegen.py`

**Action:** Paste these 4 new helper functions directly below your existing `_get_doomscroll_demo` function.

```python
def _get_youtube_thumbnail_demo(target_urls: list[str], name: str) -> dict[str, str]:
    return {
        "manifest.json": _make_manifest(name, ["https://www.youtube.com/*"]),
        "content.js": """\
setInterval(() => {
    // Hide the main custom thumbnail image inside ytd-thumbnail
    document.querySelectorAll('ytd-thumbnail img.yt-core-image').forEach(img => {
        if (!img.dataset.nuked) {
            img.style.opacity = '0';
            img.dataset.nuked = 'true';
        }
    });
    
    // YouTube actually loads an animated WebP preview in the background. 
    // By hiding the main image, the preview (or default grey box) becomes visible underneath!
    document.querySelectorAll('ytd-thumbnail #mouseover-overlay').forEach(overlay => {
        overlay.style.display = 'block';
        overlay.style.opacity = '1';
    });
}, 1000);
""",
        "content.css": ""
    }

def _get_youtube_focus_demo(target_urls: list[str], name: str) -> dict[str, str]:
    return {
        "manifest.json": _make_manifest(name, ["https://www.youtube.com/*"]),
        "content.js": """\
setInterval(() => {
    if (window.location.pathname === '/watch') {
        const sidebar = document.querySelector('#secondary');
        const comments = document.querySelector('#comments');
        const related = document.querySelector('#related');
        
        if (sidebar) sidebar.style.display = 'none';
        if (comments) comments.style.display = 'none';
        if (related) related.style.display = 'none';
        
        // Force the video player to expand to fill the newly emptied space
        const primary = document.querySelector('#primary');
        if (primary) {
            primary.style.maxWidth = '100% !important';
            primary.style.padding = '0 5% !important';
        }
    }
}, 1000);
""",
        "content.css": "#primary { max-width: 100% !important; padding: 0 5% !important; }"
    }

def _get_twitter_community_note_demo(target_urls: list[str], name: str) -> dict[str, str]:
    return {
        "manifest.json": _make_manifest(name, ["https://x.com/*", "https://twitter.com/*"]),
        "content.js": """\
setInterval(() => {
    // Find Community Notes
    document.querySelectorAll('[data-testid="birdwatch-pivot"]').forEach(note => {
        if (!note.dataset.boosted) {
            note.dataset.boosted = 'true';
            
            note.style.border = '3px solid #ff0000';
            note.style.backgroundColor = 'rgba(255, 0, 0, 0.1)';
            note.style.transform = 'scale(1.05)';
            note.style.padding = '16px';
            note.style.boxShadow = '0 0 15px rgba(255,0,0,0.5)';
            note.style.transition = 'all 0.3s ease';
            
            const textSpans = note.querySelectorAll('span');
            textSpans.forEach(span => {
                span.style.fontSize = '18px';
                span.style.fontWeight = 'bold';
            });
            
            const warning = document.createElement('div');
            warning.innerText = '🚨 FACT CHECK 🚨';
            warning.style.cssText = 'fontSize: 24px; fontWeight: 900; color: red; marginBottom: 8px; textAlign: center;';
            note.insertBefore(warning, note.firstChild);
        }
    });
}, 1500);
""",
        "content.css": ""
    }

def _get_linkedin_translator_demo(target_urls: list[str], name: str) -> dict[str, str]:
    return {
        "manifest.json": _make_manifest(name, ["https://www.linkedin.com/*"]),
        "content.js": """\
const dictionary = {
    "thrilled to announce": "bragging that",
    "humbled and honored": "flexing that",
    "synergy": "meaningless buzzword",
    "deep dive": "long boring meeting about",
    "circle back": "ignore this until later",
    "game changer": "new thing that changes nothing",
    "thought leader": "person who posts too much",
    "fast-paced environment": "we are understaffed and stressed",
    "wear many hats": "do the jobs of 3 people for 1 salary",
    "we\\\\'re like a family": "we have boundary issues"
};

setInterval(() => {
    document.querySelectorAll('.feed-shared-update-v2__description-wrapper span[dir="ltr"]').forEach(postText => {
        if (!postText.dataset.translated) {
            postText.dataset.translated = 'true';
            
            let originalHtml = postText.innerHTML;
            let modified = false;
            
            for (const [bs, real] of Object.entries(dictionary)) {
                const regex = new RegExp(bs, "gi");
                if (regex.test(originalHtml)) {
                    modified = true;
                    originalHtml = originalHtml.replace(regex, 
                        `<span style="background-color: yellow; color: black; font-weight: bold; border-radius: 3px; padding: 0 4px;" title="Translated from: '${bs}'">[${real}]</span>`
                    );
                }
            }
            
            if (modified) {
                postText.innerHTML = originalHtml;
            }
        }
    });
}, 2000);
""",
        "content.css": ""
    }
```

---

## 2. Register Tracking Phrases
**File:** `backend/agentverse_app/codegen.py`

**Action:** Update the `_check_hardcoded_demos` function by inserting these new `if` statements right above the `return None` at the end.

```python
    if ("clickbait" in q or "thumbnails" in q) and ("youtube" in str(target_urls) or "youtube" in q):
        await asyncio.sleep(4.1)
        return _get_youtube_thumbnail_demo(target_urls, extension_name)

    if ("distractions" in q or "focus" in q or "comments" in q) and ("youtube" in str(target_urls) or "youtube" in q):
        await asyncio.sleep(3.6)
        return _get_youtube_focus_demo(target_urls, extension_name)

    if ("community note" in q or "fact check" in q) and ("twitter" in str(target_urls) or "x.com" in str(target_urls) or "twitter" in q or "x.com" in q):
        await asyncio.sleep(3.9)
        return _get_twitter_community_note_demo(target_urls, extension_name)

    if ("translate" in q or "real talk" in q or "bullshit" in q) and ("linkedin" in str(target_urls) or "linkedin" in q):
        await asyncio.sleep(4.7) 
        return _get_linkedin_translator_demo(target_urls, extension_name)
```
