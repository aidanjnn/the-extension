export type MessageRole = "user" | "assistant" | "tool";

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: number;
}

export interface TabContent {
  type: "tab_content";
  tab_id: string;
  content: string;
  url: string;
}

export interface ConsoleLogs {
  type: "console_logs";
  tab_id: string;
  logs: string[];
}

export interface ClickedElement {
  selector: string;
  tag: string;
  text: string;
  attributes: Record<string, string>;
}

export type StreamEventType =
  | "content"
  | "tool_start"
  | "tool_end"
  | "thinking"
  | "error"
  | "done";

export interface StreamEvent {
  type: StreamEventType;
  data?: string;
  tool_name?: string;
  tool_input?: Record<string, unknown>;
  tool_output?: string;
}

export interface ToolStatus {
  tool_name: string;
  status: "running" | "done" | "error";
  input?: Record<string, unknown>;
  output?: string;
}

export interface AgentStatus {
  name: string;
  status: "idle" | "active" | "done" | "error";
}

// WebSocket messages from backend → extension
export type BackendMessage = StreamEvent;

// WebSocket messages from extension → backend
export interface WSChatMessage {
  type: "chat";
  prompt: string;
  project_id?: string;
  context?: string;
}

export interface WSClickedElementMessage {
  type: "clicked_element";
  element: ClickedElement;
}

export interface WSConsoleLogMessage {
  type: "console_log";
  log: string;
}

export interface WSResponseMessage {
  type: "response";
  request_id: string;
  data: Record<string, unknown>;
}
