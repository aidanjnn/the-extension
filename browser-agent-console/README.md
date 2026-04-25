# Browser Agent Console

This is the Chrome-side UI for Browser Forge. It opens the side panel, captures page context, records console output from the active tab, and sends chat requests to the local backend.

## Run it

```bash
npm install
npm run dev
```

Then open `chrome://extensions`, enable Developer mode, choose Load unpacked, and select this package's `dist` directory.

## What lives here

- `src/sidepanel/`: chat UI, project list, provider selector, install cards
- `src/background.ts`: side panel lifecycle, stored element metadata, console log relay
- `src/content/`: page scripts for DOM extraction, console capture, and element highlighting
- `manifest.config.ts`: Manifest V3 config generated through CRXJS

The console does not talk to ASI:One directly. It sends browser context to the backend, and the backend routes extension-building requests through the Agentverse Orchestrator.
