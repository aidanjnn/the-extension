# Implementation Plan: Live Preview Before Install

## Feature Overview
Instead of forcing the user to install the extension via the clunky AppleScript OS macro every time, we will leverage Chrome's `scripting` API from the Side Panel. 

When the LLM finishes generating the extension files, the Side Panel will instantly fetch `content.css` and `content.js` and **hot-inject** them into the user's active tab. The user sees the result immediately and can either converse to fix it, or click "Lock it in / Install" to formalize it.

This turns extension building into a seamless, zero-refresh, visual feedback loop.

---

## 1. Update Frontend API Client to Fetch Extension Files
**File:** `browser-agent-console/src/sidepanel/App.tsx` (or whatever API client you have)

**Context:** When the backend completes generation, it saves `content.js` and `content.css` to the project's folder. We need to fetch these files into the React app.

**Implementation:**
Create an API fetch block for `GET /internal/agentverse/projects/{projectId}/files`.
```typescript
const fetchGeneratedFiles = async (projectId: string) => {
  const res = await fetch(`http://localhost:8000/internal/agentverse/projects/${projectId}/files`);
  const data = await res.json();
  return data.files; // returns { "content.js": "...", "content.css": "..." }
}
```

---

## 2. Implement Hot-Injection Logic via `chrome.scripting`
**File:** `browser-agent-console/src/sidepanel/App.tsx`

**Context:** The side panel already has the `scripting` and `activeTab` permissions in its manifest. We will use these to directly execute the generated strings into the current tab.

**Implementation:**
Add a function to inject the CSS and JS strings into `currentActiveTab.id`.

```typescript
const injectLivePreview = async (tabId: number, contentJs: string, contentCss: string) => {
  // 1. Inject CSS
  if (contentCss) {
    await chrome.scripting.insertCSS({
      target: { tabId },
      css: contentCss,
    });
  }

  // 2. Inject JS
  // Since we can't directly execute arbitrary strings via `file` without writing to disk 
  // (which is blocked in MV3 for external strings), we can use a small trick:
  // Inject a function that safely creates a <script> tag or evaluates the code in the MAIN world.
  if (contentJs) {
    await chrome.scripting.executeScript({
      target: { tabId },
      world: 'MAIN', // Run in the main page context to bypass isolated world CSP weirdness
      func: (code) => {
        // Because of MV3 limitations on eval, it's safer to append a script tag
        const script = document.createElement('script');
        script.textContent = code;
        script.setAttribute('data-browser-forge-preview', 'true');
        document.body.appendChild(script);
      },
      args: [contentJs]
    });
  }
}
```

*Note: For cleanup (when they want to undo), you can store the injected CSS identifier and remove it using `chrome.scripting.removeCSS`, and query `/remove` elements with `data-browser-forge-preview`.*

---

## 3. Hook up the Live Preview to the Generation Flow
**File:** `browser-agent-console/src/sidepanel/App.tsx`

**Context:** Currently, the flow waits for the websocket to say `done`, and then waits for an `extension_ready` WS message to prompt an OS-level install.

**Implementation:**
When the chat generation hits the `done` state (or `extension_ready`), automatically execute the preview.

```typescript
// Inside your websocket handler where you receive "done" or "extension_ready"
const handleGenerationComplete = async (projectId: string) => {
    if (!currentActiveTab?.id) return;
    
    // Fetch the raw code
    const files = await fetchGeneratedFiles(projectId);
    
    // Trigger Live Preview
    await injectLivePreview(currentActiveTab.id, files['content.js'] || '', files['content.css'] || '');
    
    // Update UI State
    setPreviewActive(true);
}
```

---

## 4. UI Updates
**File:** `browser-agent-console/src/sidepanel/App.tsx`

1. Let the user know the preview is active! Instead of just saying "Done", add a banner or a floating modal:
   **"Previewing Live on this Tab ✨"**
2. Add two buttons next to the chat output:
   - **Button 1: "Keep / Install"** -> This pushes the extension through the final `packager` and `load_extension_via_os` macro to finalize the Chrome Extension installation.
   - **Button 2: "Undo"** -> This triggers a fast page reload (`chrome.tabs.reload(currentActiveTab.id)`) to instantly wipe the previewed scripts from the DOM.

This guarantees they can rapidly prototype and visually test the extension 10 times in a row without clogging up their Chrome Extension manager with half-broken builds!
