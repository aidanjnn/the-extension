const WS_URL = "ws://localhost:8000/ws";
const RECONNECT_DELAY_MS = 3000;

let ws: WebSocket | null = null;
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
const clickedElements: object[] = [];
const consoleLogs: string[] = [];

// ── WebSocket ──────────────────────────────────────────────────────────────

function connect() {
  if (ws && ws.readyState === WebSocket.OPEN) return;

  ws = new WebSocket(WS_URL);

  ws.onopen = () => {
    console.log("[the-extension] WebSocket connected");
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
  };

  ws.onmessage = async (event) => {
    const msg = JSON.parse(event.data);
    await handleBackendMessage(msg);
  };

  ws.onerror = () => {
    console.warn("[the-extension] WebSocket error");
  };

  ws.onclose = () => {
    console.warn("[the-extension] WebSocket disconnected — reconnecting in 3s");
    reconnectTimer = setTimeout(connect, RECONNECT_DELAY_MS);
  };
}

function send(data: object) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(data));
  }
}

async function handleBackendMessage(msg: Record<string, unknown>) {
  const type = msg.type as string;
  const requestId = msg.request_id as string | undefined;

  if (type === "get_tab_content") {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tab?.id) {
      chrome.tabs.sendMessage(tab.id, { type: "get_page_content" });
    }
    // Response will be forwarded from content script message
    chrome.runtime.onMessage.addListener(function handler(m) {
      if (m.type === "page_content") {
        send({ type: "response", request_id: requestId, data: { content: m.content, url: m.url } });
        chrome.runtime.onMessage.removeListener(handler);
      }
    });

  } else if (type === "get_console_logs") {
    send({ type: "response", request_id: requestId, data: { logs: consoleLogs.slice(-50) } });

  } else if (type === "get_clicked_elements") {
    send({ type: "response", request_id: requestId, data: { elements: clickedElements } });

  } else if (type === "load_extension") {
    // Signal the sidepanel to show install card — actual chrome:// loading requires user action
    chrome.runtime.sendMessage({ type: "show_install_card", path: msg.path });
    send({ type: "response", request_id: requestId, data: { status: "install card shown" } });
  }
}

// ── Message Relay ──────────────────────────────────────────────────────────

chrome.runtime.onMessage.addListener((msg) => {
  if (msg.type === "clicked_element") {
    clickedElements.push(msg.element);
    if (clickedElements.length > 50) clickedElements.shift();
    send({ type: "clicked_element", element: msg.element });
  }

  if (msg.type === "console_log") {
    consoleLogs.push(msg.log);
    if (consoleLogs.length > 200) consoleLogs.shift();
    send({ type: "console_log", log: msg.log });
  }

  if (msg.type === "ws_send") {
    send(msg.data);
  }
});

// ── Side Panel ─────────────────────────────────────────────────────────────

chrome.action.onClicked.addListener((tab) => {
  chrome.sidePanel.open({ windowId: tab.windowId! });
});

// ── Commands ───────────────────────────────────────────────────────────────

chrome.commands.onCommand.addListener(async (command) => {
  if (command === "send_message") {
    chrome.runtime.sendMessage({ type: "command_send_message" });
  } else if (command === "quick_actions") {
    chrome.runtime.sendMessage({ type: "command_quick_actions" });
  }
});

// ── Startup ────────────────────────────────────────────────────────────────

connect();
