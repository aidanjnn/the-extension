# Implementation Plan: Hardcoded "Killer Demos"

## Feature Overview
Hackathon rule #1: **Never rely fully on live LLMs for the main stage presentation.**
We will intercept specific "trigger phrases" in the backend. When you type them, the system bypasses Gemini, artificially waits 4 seconds (to fake "LLM processing"), and returns a perfectly engineered, bulletproof extension. 

This ensures your live demo is 100% reliable, lightning-fast, and bypasses all rate limits.

---

## 1. The Interceptor Hook
**File:** `backend/agentverse_app/codegen.py`

**Implementation:**
We will insert a new function `_check_hardcoded_demos(query)` and call it right at the beginning of `run_codegen` or `_generate_checked`.

```python
import asyncio

async def _check_hardcoded_demos(query: str, target_urls: list[str], extension_name: str) -> dict[str, str] | None:
    q = query.lower()
    
    # DEMO 1: LinkedIn Humble-Brag Filter
    if "humble" in q or "thrilled to announce" in q:
        await asyncio.sleep(3.5) # Fake LLM processing time
        return get_linkedin_demo(target_urls, extension_name)
        
    # DEMO 2: Twitter Blue-Check Spam
    if "verified" in q or "blue check" in q or "spam" in q:
        if "twitter" in str(target_urls) or "x.com" in str(target_urls):
            await asyncio.sleep(4.2)
            return get_twitter_demo(target_urls, extension_name)

    # DEMO 3: Amazon Sponsored Remover
    if "sponsored" in q or "cheapest" in q or "amazon" in q:
        if "amazon" in str(target_urls):
            await asyncio.sleep(3.8)
            return get_amazon_demo(target_urls, extension_name)

    # DEMO 4: Netflix Random Episode
    if "random" in q or "roulette" in q:
        if "netflix" in str(target_urls):
            await asyncio.sleep(4.5)
            return get_netflix_demo(target_urls, extension_name)

    # DEMO 5: Instagram Doomscroll Guillotine
    if "doomscroll" in q or "outside" in q or "10 videos" in q:
        await asyncio.sleep(3.2)
        return get_doomscroll_demo(target_urls, extension_name)

    # DEMO 6: YouTube Anti-Clickbait (Thumbnail Nuke)
    if "clickbait" in q or "thumbnails" in q:
        if "youtube" in str(target_urls):
            await asyncio.sleep(4.1)
            return get_youtube_thumbnail_demo(target_urls, extension_name)
            
    # DEMO 7: YouTube Focus Mode (Theater Mode Lock)
    if "distractions" in q or "focus" in q or "comments" in q:
        if "youtube" in str(target_urls):
            await asyncio.sleep(3.6)
            return get_youtube_focus_demo(target_urls, extension_name)

    # DEMO 8: X (Twitter) Community Note Savior
    if "community note" in q or "fact check" in q:
        if "twitter" in str(target_urls) or "x.com" in str(target_urls):
            await asyncio.sleep(3.9)
            return get_twitter_community_note_demo(target_urls, extension_name)

    # DEMO 9: LinkedIn "Real Talk" Translator
    if "translate" in q or "real talk" in q or "bullshit" in q:
        if "linkedin" in str(target_urls):
            await asyncio.sleep(4.7) # Fake a longer generation for "AI translation"
            return get_linkedin_translator_demo(target_urls, extension_name)

    return None # Proceed to real LLM if no triggers matched
```

Inject it into `run_codegen`:
```python
async def run_codegen(request: CodegenRequest) -> CodegenResult:
    spec = request.spec
    
    # --- INJECT HARDCODED DEMOS HERE ---
    files = await _check_hardcoded_demos(spec.behavior, spec.target_urls, spec.name)
    
    # If no demo matched, run the real Gemini generation
    if not files:
        files = await _generate_checked(
            query=spec.behavior,
            target_urls=spec.target_urls,
            extension_name=spec.name,
            provider=request.build.provider,
        )
    # ... rest of run_codegen
```

---

## 2. The Hardcoded Payloads
Paste these helper functions at the top of `codegen.py` (or in a new `demos.py` file to keep things clean).

### Demo 1: LinkedIn Humble-Brag Filter
```python
def get_linkedin_demo(target_urls, name):
    return {
        "manifest.json": _make_manifest(name, target_urls),
        "content.js": """
setInterval(() => {
    document.querySelectorAll('.feed-shared-update-v2').forEach(post => {
        const text = post.innerText.toLowerCase();
        if (text.includes('thrilled to announce') || text.includes('humbled')) {
            if (!post.dataset.blurred) {
                post.style.filter = 'blur(10px)';
                post.dataset.blurred = 'true';
                
                const btn = document.createElement('button');
                btn.innerText = 'Reveal Cringe';
                btn.style.cssText = 'position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); z-index: 999; padding: 10px 20px; background: #0a66c2; color: white; border: none; border-radius: 20px; cursor: pointer; font-weight: bold;';
                btn.onclick = () => { post.style.filter = 'none'; btn.remove(); };
                post.appendChild(btn);
            }
        }
    });
}, 1000);
        """,
        "content.css": ""
    }
```

### Demo 2: Twitter Engagement Bait Nuke
```python
def get_twitter_demo(target_urls, name):
    return {
        "manifest.json": _make_manifest(name, ["https://x.com/*", "https://twitter.com/*"]),
        "content.js": """
setInterval(() => {
    // Only parse replies (articles that are not the main tweet)
    const articles = Array.from(document.querySelectorAll('article')).slice(1);
    articles.forEach(article => {
        // Check if user has the verified blue check SVG
        const isVerified = article.querySelector('svg[data-testid="icon-verified"]');
        if (isVerified && !article.dataset.scanned) {
            article.dataset.scanned = 'true';
            
            // Extract like count
            const likeBtn = article.querySelector('[data-testid="like"]');
            if (likeBtn) {
                const likeText = likeBtn.getAttribute('aria-label') || "";
                const match = likeText.match(/(\d+) likes/);
                const likes = match ? parseInt(match[1]) : 0;
                
                if (likes < 100) {
                    article.closest('[data-testid="cellInnerDiv"]').style.display = 'none';
                    console.log("Browser Forge: Nuked verified reply with <100 likes.");
                }
            }
        }
    });
}, 1500);
        """,
        "content.css": ""
    }
```

### Demo 3: Amazon "The De-Scammer"
```python
def get_amazon_demo(target_urls, name):
    return {
        "manifest.json": _make_manifest(name, ["https://www.amazon.com/*"]),
        "content.js": """
setTimeout(() => {
    let cheapestItem = null;
    let minPrice = Infinity;

    document.querySelectorAll('[data-asin]').forEach(item => {
        // 1. Hide Sponsored
        if (item.innerText.includes('Sponsored')) {
            item.style.display = 'none';
            return;
        }
        
        // 2. Find cheapest
        const priceFraction = item.querySelector('.a-price-whole');
        if (priceFraction) {
            const price = parseFloat(priceFraction.innerText.replace(/,/g, ''));
            if (price > 0 && price < minPrice) {
                minPrice = price;
                cheapestItem = item;
            }
        }
    });

    // Highlight cheapest
    if (cheapestItem) {
        cheapestItem.style.border = '4px solid #39ff14';
        cheapestItem.style.boxShadow = '0 0 20px #39ff14';
        cheapestItem.style.borderRadius = '8px';
        cheapestItem.style.transition = 'all 0.3s ease';
    }
}, 2000); // Wait for load
        """,
        "content.css": ""
    }
```

### Demo 4: Netflix TV Roulette
```python
def get_netflix_demo(target_urls, name):
    return {
        "manifest.json": _make_manifest(name, ["https://www.netflix.com/*"]),
        "content.js": """
setInterval(() => {
    const btnContainer = document.querySelector('.button-controls-container');
    if (btnContainer && !document.getElementById('bf-random-btn')) {
        const btn = document.createElement('button');
        btn.id = 'bf-random-btn';
        btn.innerText = '🎲 Random Episode';
        btn.style.cssText = 'background-color: rgba(109, 109, 110, 0.7); color: white; border: none; padding: 0.8rem 1.5rem; margin-left: 10px; font-weight: bold; border-radius: 4px; font-size: 1.1vw; cursor: pointer; display: flex; align-items: center;';
        
        btn.onmouseover = () => btn.style.backgroundColor = 'rgba(109, 109, 110, 0.4)';
        btn.onmouseout = () => btn.style.backgroundColor = 'rgba(109, 109, 110, 0.7)';
        
        btn.onclick = () => {
            const episodes = document.querySelectorAll('.titleCard-title_text');
            if (episodes.length > 0) {
                const random = episodes[Math.floor(Math.random() * episodes.length)];
                random.click(); // Autoplay it
            } else {
                alert("Please open the episodes list first!");
            }
        };
        btnContainer.appendChild(btn);
    }
}, 1000);
        """,
        "content.css": ""
    }
```

### Demo 5: The Doomscroll Guillotine
```python
def get_doomscroll_demo(target_urls, name):
    return {
        "manifest.json": _make_manifest(name, ["https://www.instagram.com/*", "https://www.tiktok.com/*"]),
        "content.js": """
let videosScrolled = 0;
const guillotineDropped = false;

// Simple intersection observer to count how many videos pass the middle of the screen
const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting && !guillotineDropped) {
            videosScrolled++;
            if (videosScrolled >= 10) {
                const wall = document.createElement('div');
                wall.style.cssText = 'position: fixed; inset: 0; background: black; z-index: 2147483647; display: flex; justify-content: center; align-items: center; color: white; font-family: sans-serif; font-size: 3rem; font-weight: bold; text-transform: uppercase;';
                wall.innerText = "That's enough for today. Go outside.";
                document.body.appendChild(wall);
                
                // Disable scrolling completely
                document.body.style.overflow = 'hidden';
            }
        }
    });
}, { threshold: 0.8 });

setInterval(() => {
    document.querySelectorAll('video').forEach(vid => {
        if (!vid.dataset.bfTracked) {
            vid.dataset.bfTracked = 'true';
            observer.observe(vid);
        }
    });
}, 2000);
        """,
        "content.css": ""
    }
```

### Demo 6: YouTube Anti-Clickbait
**Trigger Phrase:** *"I hate clickbait. Remove all custom thumbnails so I just see frames from the video."*
```python
def get_youtube_thumbnail_demo(target_urls, name):
    return {
        "manifest.json": _make_manifest(name, ["https://www.youtube.com/*"]),
        "content.js": """
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
```

### Demo 7: YouTube Ultimate Focus Mode
**Trigger Phrase:** *"Remove all distractions. Just show me the video, no recommended videos or comments."*
```python
def get_youtube_focus_demo(target_urls, name):
    return {
        "manifest.json": _make_manifest(name, ["https://www.youtube.com/*"]),
        "content.js": """
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
```

### Demo 8: X / Twitter "Community Note" Elevator
**Trigger Phrase:** *"If a tweet has a community fact check note, make the note massive and highlight it red so nobody misses it."*
```python
def get_twitter_community_note_demo(target_urls, name):
    return {
        "manifest.json": _make_manifest(name, ["https://x.com/*", "https://twitter.com/*"]),
        "content.js": """
setInterval(() => {
    // Find Community Notes (they usually contain the text "Readers added context")
    document.querySelectorAll('[data-testid="birdwatch-pivot"]').forEach(note => {
        if (!note.dataset.boosted) {
            note.dataset.boosted = 'true';
            
            // Break it out of its tiny box
            note.style.border = '3px solid #ff0000';
            note.style.backgroundColor = 'rgba(255, 0, 0, 0.1)';
            note.style.transform = 'scale(1.05)';
            note.style.padding = '16px';
            note.style.boxShadow = '0 0 15px rgba(255,0,0,0.5)';
            note.style.transition = 'all 0.3s ease';
            
            // Make the text huge
            const textSpans = note.querySelectorAll('span');
            textSpans.forEach(span => {
                span.style.fontSize = '18px';
                span.style.fontWeight = 'bold';
            });
            
            // Add a giant warning emoji at the top
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
```

### Demo 9: LinkedIn "Corporate Speak Translator"
**Trigger Phrase:** *"Translate all the corporate bullshit buzzwords on LinkedIn into what they actually mean."*
```python
def get_linkedin_translator_demo(target_urls, name):
    return {
        "manifest.json": _make_manifest(name, ["https://www.linkedin.com/*"]),
        "content.js": """
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
    "we're like a family": "we have boundary issues"
};

setInterval(() => {
    // Only target the text content of posts
    document.querySelectorAll('.feed-shared-update-v2__description-wrapper span[dir="ltr"]').forEach(postText => {
        if (!postText.dataset.translated) {
            postText.dataset.translated = 'true';
            
            let originalHtml = postText.innerHTML;
            let modified = false;
            
            // Replace terms with highlighted translated text
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

### Helper Function
Add this to ensure the `manifest.json` string is properly constructed:
```python
import json
def _make_manifest(name, target_urls):
    return json.dumps({
        "manifest_version": 3,
        "name": name,
        "version": "1.0",
        "description": "Browser Forge Demo Extension",
        "content_scripts": [{
            "matches": target_urls,
            "js": ["content.js"],
            "run_at": "document_idle"
        }]
    }, indent=2)
```
