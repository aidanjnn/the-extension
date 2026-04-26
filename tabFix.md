# Implementation Plan: Browser Awareness, UI Indicator, and Highlighter Fixes

This plan outlines the exact changes needed to make the agent fully aware of the user's active tab, add a "Copilot-style" tab indicator above the chat, and fix the extremely annoying Cmd+Click hijacking bug.

---

## 1. Backend: Active Tab Filtering
**File:** `backend/agentverse_app/architect.py`

**Problem:** `_infer_target_urls` blindly grabs the very first tab in the `active_tabs` array. If you have CNN open on tab 1 and you are browsing YouTube on tab 3, it always targets CNN.
**Fix:** Update `_infer_target_urls` to loop through the tabs and find the one where `"active": True` FIRST, before falling back.

```python
def _infer_target_urls(query: str, active_tabs: list[dict]) -> list[str]:
    # ... existing hardcoded domains ...

    # FIRST PASS: Look for the active tab (the one the user is physically looking at)
    for tab in active_tabs:
        if tab.get("active"):
            url = tab.get("url", "")
            match = re.match(r"https?://([^/]+)/?", url)
            if match:
                host = match.group(1)
                return [f"https://{host}/*"]

    # SECOND PASS: Fallback to the first available tab if active isn't tracked
    for tab in active_tabs:
        url = tab.get("url", "")
        # ... existing fallback code ...
```

---

## 2. Frontend: Copilot-Style Active Tab Context UI
**File:** `browser-agent-console/src/sidepanel/App.tsx`
**File:** `browser-agent-console/src/sidepanel/App.css`

**Problem:** We need the agent to tell the user *what tab it thinks they are on* before they prompt it.
**Fix:** 
1. Use `chrome.tabs.onActivated` and `chrome.tabs.onUpdated` to track the currently focused window tab.
2. Render a UI context indicator directly above the Chat Input form.

**In `App.tsx`:**
Add a new piece of state near the top:
```tsx
const [currentActiveTab, setCurrentActiveTab] = useState<chrome.tabs.Tab | null>(null);

useEffect(() => {
  // Get initial active tab
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    if (tabs[0]) setCurrentActiveTab(tabs[0]);
  });

  // Listen for tab switching
  const handleTabActive = (activeInfo: chrome.tabs.ActiveInfo) => {
    chrome.tabs.get(activeInfo.tabId, (tab) => setCurrentActiveTab(tab));
  };
  
  // Listen for tab URL updates
  const handleTabUpdate = (tabId: number, changeInfo: chrome.tabs.TabChangeInfo, tab: chrome.tabs.Tab) => {
    if (tab.active) setCurrentActiveTab(tab);
  };

  chrome.tabs.onActivated.addListener(handleTabActive);
  chrome.tabs.onUpdated.addListener(handleTabUpdate);

  return () => {
    chrome.tabs.onActivated.removeListener(handleTabActive);
    chrome.tabs.onUpdated.removeListener(handleTabUpdate);
  };
}, []);
```

**Inject the UI Indicator:**
Inside the `form` (or right above the input container), add the Copilot-style indicator:
```tsx
{currentActiveTab && (
  <div className="active-tab-context">
    <img 
      src={currentActiveTab.favIconUrl || 'default-favicon.png'} 
      alt="favicon" 
      className="active-tab-favicon" 
    />
    <span className="active-tab-url">
      {new URL(currentActiveTab.url || '').hostname}
    </span>
  </div>
)}
```

**In `App.css`:**
```css
.active-tab-context {
  display: flex;
  align-items: center;
  gap: 6px;
  background: rgba(255, 255, 255, 0.05); /* Or a sleek glassmorphism color */
  border: 1px solid rgba(255, 255, 255, 0.1);
  padding: 4px 10px;
  border-radius: 12px;
  width: fit-content;
  margin-bottom: 8px; /* Push the chat input down slightly */
  font-size: 11px;
  color: #a1a1aa;
}

.active-tab-favicon {
  width: 14px;
  height: 14px;
  border-radius: 2px;
}
```

**Important Websocket payload fix in App.tsx:**
When sending the `chat` payload in `sendMessage`, ensure `active_tabs` perfectly sets `active: true` for the current tab so the backend catches it correctly:
```tsx
const mappedTabs = activeTabs.map(t => ({
  ...t,
  active: currentActiveTab?.id === t.id ? true : t.active // Guarantee sync
}))
// ... pass mappedTabs to the ws payload
```

---

## 3. Foreground: Change Highlighter Hotkey to Option (Alt)
**File:** `browser-agent-console/src/content/highlighter.ts`

**Problem:** The highlighter forces the user to press `Command + Click` to select elements. The issue is that Chrome intrinsically uses `Command + Click` to *Open in New Tab*, meaning users can no longer open tabs normally while the side panel is open.
**Fix:** Switch the hotkey out. Instead of `metaKey` (Command), listen for `altKey` (Option/Alt). This perfectly preserves OS-level navigation shortcuts.

**Changes required in `highlighter.ts`:**
1. Search and replace all instances of `isMetaKeyDown` with `isAltKeyDown`.
2. Where it checks `event.metaKey`, change it to `event.altKey`.
3. In the keyup/keydown listeners, check `event.key === 'Alt'` instead of `event.key === 'Meta'`.

Example snippet in `handleMouseMove` & `click` listener:
```typescript
  if (!event.altKey && !isAltKeyDown) return
  if (event.altKey && !isAltKeyDown) {
    isAltKeyDown = true
  }
```

---

## 4. Foreground: Fix Content Script Boot Crash (Optional but Recommended)
**File:** `browser-agent-console/src/content/main.tsx`

**Problem:** Currently, the extension forces `main.tsx` to run at `"run_at": "document_start"`. Because it runs before the DOM loads, `document.body` is completely **null**, which causes `document.body.appendChild(container)` to throw a fatal error on initial page load.

**Fix:** Wrap the initialization in a DOMContentLoaded listener so it successfully attaches:
```typescript
function initApp() {
  if (document.getElementById('browser-forge-app')) return
  const container = document.createElement('div')
  container.id = 'browser-forge-app'
  document.body.appendChild(container)
  createRoot(container).render(
    <StrictMode>
      <App />
    </StrictMode>,
  )
}

// Safely boot
if (document.body) {
  initApp()
} else {
  document.addEventListener('DOMContentLoaded', initApp)
}
```
