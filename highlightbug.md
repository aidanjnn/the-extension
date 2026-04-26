# Fix Highlighter Blocking Cmd+Click

## Overview
The hover highlighter content script (`browser-agent-console/src/content/highlighter.ts`) intercepts Cmd+Click events to toggle element highlighting. Currently, this unintentionally blocks Chrome's native "Command+Click to open link in a new tab" behavior for *all* links, even when the agent side panel is closed.

## Root Cause
In `highlighter.ts`, both the `mousemove` and `click` event listeners check the side panel state to decide whether to run. 
At line ~520 (and ~393):
```typescript
if (!isSidepanelOpen && sidepanelStateKnown) return
```

Because `sidepanelStateKnown` is `false` when the page first loads (before the side panel is opened), this check fails to exit early when the panel is closed. As a result, the code proceeds to:
```typescript
event.preventDefault()
event.stopImmediatePropagation()
```
This blocks the native link click behavior.

## Implementation Plan

1. **Modify `browser-agent-console/src/content/highlighter.ts`**
2. Locate the early return in the `mousemove` handler (around line 393):
   ```typescript
   // FROM:
   if (!isSidepanelOpen && sidepanelStateKnown) return

   // TO:
   if (!isSidepanelOpen) return
   ```
3. Locate the early return in the `click` handler (around line 520):
   ```typescript
   // FROM:
   if (!isSidepanelOpen && sidepanelStateKnown) return

   // TO:
   if (!isSidepanelOpen) return
   ```

## Constraints
- Do NOT modify any other files for this bug.
- Ensure all other highlighting logic remains exactly as is. The only change is skipping the logic when `isSidepanelOpen` is false, instead of waiting for `sidepanelStateKnown`.
- This ensures the highlighter is completely asleep by default until the side panel tells it to wake up.
