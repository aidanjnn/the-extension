import { ElementHighlighter } from "./highlighter";
import type { ClickedElement } from "../types/messages";

const highlighter = new ElementHighlighter((element: ClickedElement) => {
  chrome.runtime.sendMessage({ type: "clicked_element", element });
});

function getPageContent(): string {
  const clone = document.documentElement.cloneNode(true) as HTMLElement;
  // Remove script/style tags for cleaner content
  clone.querySelectorAll("script, style, noscript").forEach((el) => el.remove());
  return clone.innerText.slice(0, 10000);
}

chrome.runtime.onMessage.addListener((msg) => {
  if (msg.type === "activate_select_mode") {
    highlighter.activate();
  } else if (msg.type === "deactivate_select_mode") {
    highlighter.deactivate();
  } else if (msg.type === "get_page_content") {
    chrome.runtime.sendMessage({
      type: "page_content",
      content: getPageContent(),
      url: window.location.href,
    });
  }
});
