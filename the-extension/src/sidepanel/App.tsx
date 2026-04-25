import { useState, useEffect, useRef, useCallback } from "react";
import type {
  ChatMessage,
  StreamEvent,
  ToolStatus,
  AgentStatus,
  ClickedElement,
} from "../types/messages";

const WS_URL = "ws://localhost:8000/ws";

const AGENTS: AgentStatus[] = [
  { name: "Orchestrator", status: "idle" },
  { name: "CodeGen", status: "idle" },
  { name: "Validator", status: "idle" },
  { name: "BrowserCtx", status: "idle" },
];

export default function App() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [toolStatuses, setToolStatuses] = useState<ToolStatus[]>([]);
  const [agents, setAgents] = useState<AgentStatus[]>(AGENTS);
  const [selectedElements, setSelectedElements] = useState<ClickedElement[]>([]);
  const [selectMode, setSelectMode] = useState(false);
  const [wsStatus, setWsStatus] = useState<"connecting" | "connected" | "disconnected">("connecting");

  const wsRef = useRef<WebSocket | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const projectIdRef = useRef<string | null>(null);

  const scrollToBottom = () => messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });

  // WebSocket setup
  useEffect(() => {
    function connect() {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => setWsStatus("connected");
      ws.onclose = () => {
        setWsStatus("disconnected");
        setTimeout(connect, 3000);
      };
      ws.onerror = () => setWsStatus("disconnected");

      ws.onmessage = (event) => {
        const data: StreamEvent = JSON.parse(event.data);
        handleStreamEvent(data);
      };
    }
    connect();
    return () => wsRef.current?.close();
  }, []);

  // Chrome runtime messages
  useEffect(() => {
    const handler = (msg: Record<string, unknown>) => {
      if (msg.type === "clicked_element") {
        const el = msg.element as ClickedElement;
        setSelectedElements((prev) => [...prev.slice(-9), el]);
        setSelectMode(false);
      }
      if (msg.type === "command_send_message") {
        sendMessage();
      }
    };
    chrome.runtime.onMessage.addListener(handler);
    return () => chrome.runtime.onMessage.removeListener(handler);
  }, [input]);

  useEffect(() => scrollToBottom(), [messages, toolStatuses]);

  const handleStreamEvent = useCallback((event: StreamEvent) => {
    switch (event.type) {
      case "content":
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          if (last?.role === "assistant") {
            return [...prev.slice(0, -1), { ...last, content: last.content + (event.data ?? "") }];
          }
          return [...prev, {
            id: Date.now().toString(),
            role: "assistant",
            content: event.data ?? "",
            timestamp: Date.now(),
          }];
        });
        break;

      case "tool_start":
        setToolStatuses((prev) => [...prev, {
          tool_name: event.tool_name ?? "",
          status: "running",
          input: event.tool_input,
        }]);
        // Update agent status based on tool name
        if (event.tool_name?.includes("validate")) {
          setAgents((prev) => prev.map((a) => a.name === "Validator" ? { ...a, status: "active" } : a));
        } else if (event.tool_name?.includes("tab") || event.tool_name?.includes("console") || event.tool_name?.includes("click")) {
          setAgents((prev) => prev.map((a) => a.name === "BrowserCtx" ? { ...a, status: "active" } : a));
        } else {
          setAgents((prev) => prev.map((a) => a.name === "CodeGen" ? { ...a, status: "active" } : a));
        }
        break;

      case "tool_end":
        setToolStatuses((prev) =>
          prev.map((t) =>
            t.tool_name === event.tool_name && t.status === "running"
              ? { ...t, status: "done", output: event.tool_output }
              : t
          )
        );
        setAgents((prev) => prev.map((a) => ({ ...a, status: a.status === "active" ? "idle" : a.status })));
        break;

      case "done":
        setIsLoading(false);
        setAgents(AGENTS);
        break;

      case "error":
        setIsLoading(false);
        setMessages((prev) => [...prev, {
          id: Date.now().toString(),
          role: "assistant",
          content: `Error: ${event.data}`,
          timestamp: Date.now(),
        }]);
        break;
    }
  }, []);

  const sendMessage = useCallback(() => {
    const text = input.trim();
    if (!text || isLoading || wsRef.current?.readyState !== WebSocket.OPEN) return;

    const userMsg: ChatMessage = {
      id: Date.now().toString(),
      role: "user",
      content: text,
      timestamp: Date.now(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setIsLoading(true);
    setToolStatuses([]);
    setAgents((prev) => prev.map((a) => a.name === "Orchestrator" ? { ...a, status: "active" } : a));

    const context = selectedElements.length > 0
      ? "Selected elements:\n" + selectedElements.map((e) => `${e.tag}: ${e.selector}`).join("\n")
      : "";

    wsRef.current!.send(JSON.stringify({
      type: "chat",
      prompt: text,
      project_id: projectIdRef.current,
      context,
    }));
  }, [input, isLoading, selectedElements]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
      e.preventDefault();
      sendMessage();
    }
  };

  const toggleSelectMode = () => {
    const next = !selectMode;
    setSelectMode(next);
    chrome.tabs.query({ active: true, currentWindow: true }, ([tab]) => {
      if (tab?.id) {
        chrome.tabs.sendMessage(tab.id, {
          type: next ? "activate_select_mode" : "deactivate_select_mode",
        });
      }
    });
  };

  return (
    <>
      {/* Header */}
      <div className="header">
        <span className="header-title">the extension</span>
        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
          <span className="header-badge">Gemini</span>
          <span className="header-badge" style={{
            color: wsStatus === "connected" ? "var(--success)" : "var(--error)",
            borderColor: wsStatus === "connected" ? "var(--success)" : "var(--error)",
          }}>
            {wsStatus === "connected" ? "●" : "○"} {wsStatus}
          </span>
        </div>
      </div>

      {/* Agent Status Bar */}
      <div className="agent-bar">
        {agents.map((agent) => (
          <div key={agent.name} className={`agent-pill ${agent.status === "active" ? "active" : ""}`}>
            <div className="agent-dot" />
            {agent.name}
          </div>
        ))}
      </div>

      {/* Select Mode Banner */}
      {selectMode && (
        <div className="select-mode-banner" onClick={toggleSelectMode}>
          Click any element to select it — Press ESC or click here to cancel
        </div>
      )}

      {/* Messages */}
      <div className="messages">
        {messages.length === 0 && (
          <div style={{ color: "var(--text-dim)", textAlign: "center", marginTop: 40 }}>
            <div style={{ fontSize: 24, marginBottom: 8 }}>⚡</div>
            <div style={{ fontSize: 13, fontWeight: 600 }}>the extension</div>
            <div style={{ fontSize: 11, marginTop: 4 }}>
              Build Chrome extensions from natural language
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <div key={msg.id} className={`message ${msg.role}`}>
            <div className="message-role">{msg.role === "user" ? "You" : "Agent"}</div>
            <div className="message-content">{msg.content}</div>
          </div>
        ))}

        {/* Tool Status */}
        {toolStatuses.length > 0 && (
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            {toolStatuses.slice(-5).map((t, i) => (
              <div key={i} className={`tool-status ${t.status}`}>
                <span className="tool-status-icon" />
                <span className="tool-name">{t.tool_name}</span>
                {t.status === "running" && <span style={{ color: "var(--text-dim)" }}>running...</span>}
                {t.status === "done" && <span style={{ color: "var(--success)" }}>done</span>}
              </div>
            ))}
          </div>
        )}

        {/* Selected elements preview */}
        {selectedElements.length > 0 && (
          <div style={{ fontSize: 10, color: "var(--text-dim)", fontFamily: "var(--mono)" }}>
            {selectedElements.length} element(s) selected:{" "}
            {selectedElements.map((e) => e.selector).join(", ")}
            <button
              onClick={() => setSelectedElements([])}
              style={{ marginLeft: 6, background: "none", border: "none", color: "var(--error)", cursor: "pointer", fontSize: 10 }}
            >
              clear
            </button>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="input-area">
        <div className="input-row">
          <textarea
            ref={inputRef}
            className="input-box"
            placeholder="Build me a Chrome extension that..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={1}
            disabled={isLoading}
          />
          <button
            className="send-btn"
            onClick={sendMessage}
            disabled={isLoading || !input.trim()}
          >
            {isLoading ? "..." : "Send"}
          </button>
        </div>
        <div className="shortcuts-hint">
          <span><span className="shortcut-key">⌘↵</span> send</span>
          <span><span className="shortcut-key">⌘K</span> actions</span>
          <button
            onClick={toggleSelectMode}
            style={{
              background: selectMode ? "var(--warning)" : "none",
              border: "1px solid var(--border)",
              borderRadius: 4,
              color: selectMode ? "#000" : "var(--text-dim)",
              cursor: "pointer",
              fontSize: 10,
              padding: "1px 6px",
              fontFamily: "var(--font)",
            }}
          >
            {selectMode ? "selecting..." : "select element"}
          </button>
        </div>
      </div>
    </>
  );
}
