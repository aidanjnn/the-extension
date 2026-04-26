# Implementation Plan: Visual Region Capture (The "Snipping Tool")

## Feature Overview
Allows the user to press `Cmd+Shift+E`, turning their cursor into a crosshair. They drag a box over any part of the page (like a YouTube video thumbnail or a Twitter ad). The extension captures:
1. A **visually cropped screenshot** of exactly what they selected.
2. The **DOM Subtree (HTML)** of the elements inside that bounding box.

This gets dropped into the Chat Input as a multimedia context chip, allowing Gemini (which is wildly good at vision) to literally *see* what the user wants to remove, pair it with the HTML, and generate bulletproof code.

---

## 1. Content Script: The Selection Overlay
**File:** `browser-agent-console/src/content/snipper.ts` (New File)

**Implementation:**
Create an overlay that intercepts all mouse events to draw a selection box.

```typescript
export function startSnippingTool() {
  const overlay = document.createElement('div');
  overlay.id = 'bf-snipping-overlay';
  Object.assign(overlay.style, {
    position: 'fixed', top: 0, left: 0, width: '100vw', height: '100vh',
    background: 'rgba(0,0,0,0.3)', zIndex: 2147483647, cursor: 'crosshair'
  });
  
  const selectionBox = document.createElement('div');
  Object.assign(selectionBox.style, {
    position: 'absolute', border: '2px solid #ff6b00', background: 'rgba(255,107,0,0.1)', display: 'none'
  });
  overlay.appendChild(selectionBox);
  document.body.appendChild(overlay);

  let startX = 0, startY = 0, isDragging = false;

  overlay.addEventListener('mousedown', (e) => {
    isDragging = true;
    startX = e.clientX; startY = e.clientY;
    selectionBox.style.display = 'block';
    selectionBox.style.left = `${startX}px`;
    selectionBox.style.top = `${startY}px`;
    selectionBox.style.width = '0px'; selectionBox.style.height = '0px';
  });

  overlay.addEventListener('mousemove', (e) => {
    if (!isDragging) return;
    const width = Math.abs(e.clientX - startX);
    const height = Math.abs(e.clientY - startY);
    selectionBox.style.left = `${Math.min(e.clientX, startX)}px`;
    selectionBox.style.top = `${Math.min(e.clientY, startY)}px`;
    selectionBox.style.width = `${width}px`;
    selectionBox.style.height = `${height}px`;
  });

  overlay.addEventListener('mouseup', async (e) => {
    isDragging = false;
    const rect = selectionBox.getBoundingClientRect();
    overlay.remove(); // Cleanup overlay instantly so we can screenshot underneath it
    
    // Step 2: Trigger Capture
    await captureRegion(rect);
  });
}

// Add shortcut listener
document.addEventListener('keydown', (e) => {
  if (e.metaKey && e.shiftKey && e.key.toLowerCase() === 'e') startSnippingTool();
});
```

---

## 2. Background Script: Capturing the Screenshot
**File:** `browser-agent-console/src/background.ts`

**Context:** Only the background script is allowed to take a screenshot of the active tab.
**Implementation:**
Add a message listener that uses `chrome.tabs.captureVisibleTab`.

```typescript
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'CAPTURE_VISIBLE_TAB') {
    chrome.tabs.captureVisibleTab(sender.tab!.windowId, { format: 'png' }, (dataUrl) => {
      sendResponse({ dataUrl });
    });
    return true; // Keep channel open for async response
  }
});
```

---

## 3. Cropping the Image & Extracting the DOM
**File:** `browser-agent-console/src/content/snipper.ts`

**Implementation:**
When the user releases their mouse, we get the fullscreen screenshot, draw it to an offscreen canvas, crop it to their bounding box, and find the HTML.

```typescript
async function captureRegion(rect: DOMRect) {
  // 1. Get fullscreen screenshot from background
  const response = await chrome.runtime.sendMessage({ type: 'CAPTURE_VISIBLE_TAB' });
  
  // 2. Crop Image via Canvas
  const img = new Image();
  img.src = response.dataUrl;
  await new Promise(resolve => img.onload = resolve);
  
  const canvas = document.createElement('canvas');
  // Handle device pixel ratio (Retina displays)
  const dpr = window.devicePixelRatio || 1;
  canvas.width = rect.width * dpr;
  canvas.height = rect.height * dpr;
  
  const ctx = canvas.getContext('2d')!;
  ctx.drawImage(img, 
    rect.left * dpr, rect.top * dpr, rect.width * dpr, rect.height * dpr, // Source Crop
    0, 0, canvas.width, canvas.height // Destination
  );
  const croppedBase64 = canvas.toDataURL('image/png');

  // 3. Find DOM Elements within the bounding box
  // Find the deepest element right in the center of their box
  const centerX = rect.left + (rect.width / 2);
  const centerY = rect.top + (rect.height / 2);
  const targetElement = document.elementFromPoint(centerX, centerY);
  
  // Climb up to find a meaningful container constraint
  const container = targetElement?.closest('div, section, article, ytd-rich-item-renderer') || targetElement;
  const domHtml = container?.outerHTML || '';

  // 4. Send the Image + HTML to the Side Panel
  chrome.runtime.sendMessage({ 
    type: 'REGION_CAPTURED', 
    payload: { imageBase64: croppedBase64, html: domHtml } 
  });
}
```

---

## 4. Frontend & Backend Updates

**In `App.tsx` (Side Panel):**
- Listen for the `REGION_CAPTURED` message.
- Map the `imageBase64` into an `<img>` tag and append it to the chat input UI alongside the raw HTML snippet mapping.
- Pass the base64 string + HTML string up through the WebSocket.

**In `architect.py` & `codegen.py` (Backend):**
- Gemini Pro natively natively supports Multimodal inputs. Instead of just passing `[{"role": "user", "content": prompt }]`, pass the image blob in the `messages` structure:
```python
"messages": [{
    "role": "user",
    "content": [
        {"type": "text", "text": "Hide this specific type of component, here is its HTML structure: " + domHtml},
        {"type": "image_url", "image_url": {"url": imageBase64}}
    ]
}]
```
