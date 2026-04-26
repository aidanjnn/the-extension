# Browser Forge: Flagship Features Outline

*Context for Codex: This is the high-level visionary outline for 5 flagship capabilities we need to implement on this new architectural branch. Please read these functional descriptions carefully before translating them into technical implementations.*

---

### 1. X/Twitter Engagement Bait Remover
**The Vision:** The X reply section is completely saturated with verified bot accounts copy-pasting generic statements to farm impressions. We need to physically clean the timeline to protect the user's attention.
**The Behavior:** 
* When the user navigates into a specific tweet thread (not the main timeline, we don't want to break infinite scroll), the extension scans the replies. 
* It needs to visually identify replies that have the blue "Verified" checkmark. 
* If a verified reply has an extremely low ratio of likes (e.g., less than 100), it means it's engagement bait. The extension should completely eradicate that reply block from the DOM so the user never sees it, leaving only high-quality, community-validated replies visible.

### 2. Netflix "TV Roulette"
**The Vision:** Decision paralysis ruins the streaming experience. Users spend 20 minutes scrolling menus instead of watching shows. We want to inject an element of chaotic fun natively into the Netflix UI.
**The Behavior:** 
* The extension must seamlessly inject a brand new "🎲 Random Episode" button directly next to the native Play/More Info controls on a show's page. 
* The button must perfectly mimic Netflix's native design language (fonts, hover states, background colors) so it looks like an official feature. 
* When clicked, the extension invisibly scans the carousel of available episodes and uses RNG to forcefully trigger a click event on a random episode, instantly launching the video player.

### 3. Instagram / TikTok "Doomscroll Guillotine"
**The Vision:** Short-form video is designed to hijack dopamine. We need to introduce a hard, un-bypassable physical friction point to break the user out of the algorithmic trance.
**The Behavior:** 
* As the user scrolls through their feed, the extension silently tracks how many unique videos cross the center of their screen.
* To build anticipation, a visually stark, floating red "Counter" UI must be injected into the top-right corner of the screen, tracking `[Current Video] / 10`. 
* The second the user scrolls to the 10th video, the guillotine drops. A massive, impenetrable pitch-black wall is violently injected over the entire screen with z-index priority. The text *"That's enough for today. Go outside."* is displayed in the center. 
* The user's ability to scroll the browser window must be entirely locked/frozen. The streak is over.

### 4. YouTube "Absolute" Focus Mode
**The Vision:** YouTube's interface is designed to distract the user with sidebars, comments, search bars, and algorithmic recommendations. We want to strip YouTube down to nothing but a brutalist 2D matrix of video content.
**The Behavior:** 
* Every single non-video element must be eradicated from the DOM. 
* The top navigation bar, the left-hand category sidebar, the comments section, the "related" videos, and all header tags must be set to `display: none`.
* What remains must solely be the video thumbnails themselves. The extension should dynamically re-flow the remaining thumbnails to fill the massive amounts of newly emptied whitespace, creating a pure, infinite edge-to-edge 2D array of videos with zero surrounding context or UI chrome.

### 5. Peer-to-Peer "Internet Sync" (Component Marketplace)
**The Vision:** Browser customization feels lonely. If a user spends 5 minutes crafting the perfect "Minimalist Twitter" or "Dark Mode Wikipedia", they should be able to hand that exact version of the internet to their friends natively.
**The Behavior:** 
* Inside the Browser Forge side panel, there needs to be an intuitive "Share Workspace/Extension" button associated with their newly generated code.
* Clicking it packages their injected CSS/JS state and generates a shortlink, string ID, or payload format (`bf.link/minimal-x`).
* When another user pastes that code/URL into *their* Browser Forge instance, the backend instantly resolves it and injects the same configuration into their active tab. Their browser visually morphs in real-time to identically match the original user's creation, achieving multiplayer, peer-to-peer web modification.
