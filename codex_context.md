# Codex/Claude Verification Context: The "Hacked Demos"

## What We Just Did
We strategically bypassed the Live Gemini LLM inside our FastApi backend (`backend/agentverse_app/codegen.py`) to hardcode 9 flawless, lightning-fast "Killer Demos" for a hackathon presentation. 

When a user types a specific Trigger Phrase on the frontend, the Python `run_codegen` pipeline intercepts it using `_check_hardcoded_demos()`. If there is a match, it does an `await asyncio.sleep(4)` to simulate AI processing, and returns a perfectly hardcoded Javascript/CSS Extension payload instantly.

## The Goal Now
Your goal is to parse `codegen.py`, verify there are no syntax errors in our new Javascript/Python string injections, and implement/test the final remaining components if necessary.

---

## Technical Architecture

### 1. The Interceptor Hook
Inside `codegen.py` at `run_codegen()`, we intercept the incoming `request.spec.behavior` (the user's prompt) and `target_urls` (the active tab's URL). We check the trigger substrings against it:

```python
    files = await _check_hardcoded_demos(spec.behavior, spec.target_urls, spec.name)
    if files is None:
        files = await _generate_checked(...) # Bypassed if demo hit
```

### 2. The 9 Hardcoded Payloads (What to Check)

**Demo 1: LinkedIn Hiring Nuke**
- *Trigger:* `"hiring"`, `"intern"`, `"internship"`, `"new grad"`
- *Effect:* Finds posts with those keywords, puts a massive 5px red glowing border around them, and pins a `🚨 HIRING 🚨` absolute-positioned badge on the corner so no job opportunity is missed.

**Demo 2: Twitter Engagement Bait Remover**
- *Trigger:* `"verified"`, `"blue check"`, `"spam"`
- *Effect:* Checks if we are on a `/status/` URL (we do not want this triggering on the `/home` timeline so we don't break scrolling). Runs `Array.from(document.querySelectorAll('article')).slice(1)` to skip the main tweet, identifies replies with the blue checkmark SVG, and hides them if they have `< 100` likes.

**Demo 3: Amazon "De-Scammer"**
- *Trigger:* `"sponsored"`, `"cheapest"`, `"amazon"`
- *Effect:* Loops through all `[data-asin]` products. Immediately `display: none`s any product containing "Sponsored" text. Reads the remaining `.a-price-whole` floats, finds the cheapest item in the array, and highlights it with a radiant neon green border.

**Demo 4: Netflix "TV Roulette"**
- *Trigger:* `"random"`, `"roulette"`, `"netflix"`
- *Effect:* Builds a custom button element natively matching Netflix's CSS and injects it into `.button-controls-container`. When clicked, it finds all `.titleCard-title_text` elements and uses `Math.random()` to programmatically click a random episode.

**Demo 5: Instagram/TikTok "Doomscroll Guillotine"**
- *Trigger:* `"doomscroll"`, `"10 videos"`
- *Effect:* Uses an `IntersectionObserver` to track videos passing the center of the screen. Injects a fixed Red Circle UI counter in the top-right corner tracking `X/10`. At 10 videos, it injects a Z-Index 2147483647 black wall over the browser explicitly telling the user to "Go outside", locking scroll.

**Demo 6: YouTube Anti-Clickbait (Thumbnail Nuke)**
- *Trigger:* `"clickbait"`, `"thumbnails"`
- *Effect:* Sets `opacity: 0` on `ytd-thumbnail img.yt-core-image` (the custom creator thumbnail), but forces `ytd-thumbnail #mouseover-overlay` to `display: block; opacity: 1;`. This exploits YouTube's hidden webp animation preview layer, physically reverting all clickbait on the homepage into raw video frames.

**Demo 7: YouTube Focus Mode**
- *Trigger:* `"distractions"`, `"focus"`, `"comments"`
- *Effect:* Finds `#secondary`, `#comments`, `#related` sidebars and sets to `display: none`. Modifies `#primary` (the main video player wrapper) to `max-width: 100% !important; padding: 0 5%` so the video beautifully expands the entire freed space natively.

**Demo 8: Twitter Community Note Elevator**
- *Trigger:* `"community note"`, `"fact check"`
- *Effect:* Finds the `[data-testid="birdwatch-pivot"]` wrapper, strips it out of its tiny box using `transform: scale(1.05)`, turns the background red, expands the font, and prepends a `🚨 FACT CHECK 🚨` header.

**Demo 9: LinkedIn "Real Talk" Corporate Translator**
- *Trigger:* `"translate"`, `"real talk"`, `"bullshit"`
- *Effect:* Runs an `Object.entries` regex replacement dictionary over the HTML text contents of `.feed-shared-update-v2__description-wrapper`, converting words like "thrilled to announce" into a highlighted yellow `[bragging that]` tooltip span.

---

### Action Items for Codex/Claude
1. Review the JavaScript syntax injected inside the Python multi-line strings in `codegen.py` to ensure all DOM selectors and intervals won't throw silent exceptions.
2. Note that the Python multi-line strings often require double escaping for Javascript RegEx (e.g. `match(/\\\\d+/)`). Make sure the string interpolations haven't broken.
