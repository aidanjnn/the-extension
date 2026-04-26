# Fix Active Tab Context Bug & Add UI Indicator

## Overview
Currently, the LLM agent often targets the incorrect tab when inferring which website the user wants to augment (e.g. asking "make the background yellow" on YouTube modifies CNN if CNN is the first tab). Additionally, there is no UI indicator telling the user which tab is currently selected as context.

## Root Cause
1. **Frontend**: The Chrome side panel (`App.tsx`) queries `chrome.tabs.query({})` and sends **all** open tabs to the backend as `active_tabs`.
2. **Backend**: In `architect.py`, `_infer_target_urls` blindly grabs the very first tab from the `active_tabs` array without checking if it's the actually active, focused tab.

## Implementation Plan

### 1. Fix the Backend Logic (`backend/agentverse_app/architect.py`)
Update `_infer_target_urls` to prioritize the active tab before falling back.

```python
# In architect.py, inside _infer_target_urls()

def _infer_target_urls(query: str, active_tabs: list[dict]) -> list[str]:
    # ... keep the hardcoded keyword checks at the top ...
    
    # NEW LOGIC: First, try to find an active tab
    for tab in active_tabs:
        if tab.get("active"):
            url = tab.get("url", "")
            match = re.match(r"https?://([^/]+)/?", url)
            if match:
                host = match.group(1)
                return [f"https://{host}/*"]
                
    # Fallback if no active tab found
    for tab in active_tabs:
        url = tab.get("url", "")
        match = re.match(r"https?://([^/]+)/?", url)
        if match:
            host = match.group(1)
            return [f"https://{host}/*"]
            
    return ["<all_urls>"]
```

### 2. Add Active Tab UI Indicator (`browser-agent-console/src/sidepanel/App.tsx` & `App.css`)
Add a Copilot-style active tab indicator rectangle above the chat input box.

1. **State**: Add a new state variable in `App.tsx` to store the active tab:
   ```typescript
   const [currentActiveTab, setCurrentActiveTab] = useState<chrome.tabs.Tab | null>(null)
   ```

2. **Effect**: Fetch and sync the active tab using chrome APIs:
   ```typescript
   useEffect(() => {
     const updateActiveTab = async () => {
       try {
         const tabs = await chrome.tabs.query({ active: true, currentWindow: true })
         setCurrentActiveTab(tabs[0] || null)
       } catch {
         // ignore
       }
     }
     
     updateActiveTab()
     chrome.tabs.onActivated.addListener(updateActiveTab)
     chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
       if (tab.active) updateActiveTab()
     })
     
     // cleanup removal if needed
   }, [])
   ```

3. **Render**: Place the indicator right inside `Messages container` or right above `<form className="chat-input">` (around line 2349):
   ```tsx
   <div className="active-tab-context" title="Active browser context">
     {currentActiveTab?.favIconUrl && <img src={currentActiveTab.favIconUrl} alt="favicon" />}
     <span>{currentActiveTab?.url || 'No active tab'}</span>
   </div>
   <form onSubmit={handleSubmit} className="chat-input">
   ```

4. **Styles (`App.css`)**: Add CSS to make it look like a sleek floating rectangle (like Copilot/Cursor's context chips).
   ```css
   .active-tab-context {
     display: flex;
     align-items: center;
     gap: 6px;
     margin: 0 16px 8px 16px;
     padding: 4px 8px;
     background: var(--bg-hover);
     border: 1px solid var(--border-color);
     border-radius: 6px;
     font-size: 11px;
     color: var(--text-secondary);
     width: fit-content;
     max-width: calc(100% - 32px);
     overflow: hidden;
     white-space: nowrap;
     text-overflow: ellipsis;
   }
   
   .active-tab-context img {
     width: 12px;
     height: 12px;
   }
   ```

## Constraints
- The `architect.py` change MUST keep the previous hardcoded keyword checks at the top (`instagram`, `youtube`, etc).
- Real-time tab sync is critical: `chrome.tabs.onActivated` listener ensures the UI chip updates immediately when the user switches tabs.
