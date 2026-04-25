import type { ClickedElement } from "../types/messages";

export class ElementHighlighter {
  private overlay: HTMLDivElement | null = null;
  private label: HTMLDivElement | null = null;
  private active = false;
  private onSelect: (el: ClickedElement) => void;

  constructor(onSelect: (el: ClickedElement) => void) {
    this.onSelect = onSelect;
  }

  activate() {
    if (this.active) return;
    this.active = true;
    document.body.classList.add("te-select-mode-active");

    this.overlay = document.createElement("div");
    this.overlay.className = "te-highlight-overlay";
    document.body.appendChild(this.overlay);

    this.label = document.createElement("div");
    this.label.className = "te-highlight-label";
    document.body.appendChild(this.label);

    document.addEventListener("mouseover", this.handleMouseOver, true);
    document.addEventListener("click", this.handleClick, true);
    document.addEventListener("keydown", this.handleKeyDown, true);
  }

  deactivate() {
    if (!this.active) return;
    this.active = false;
    document.body.classList.remove("te-select-mode-active");
    this.overlay?.remove();
    this.label?.remove();
    this.overlay = null;
    this.label = null;
    document.removeEventListener("mouseover", this.handleMouseOver, true);
    document.removeEventListener("click", this.handleClick, true);
    document.removeEventListener("keydown", this.handleKeyDown, true);
  }

  private handleMouseOver = (e: MouseEvent) => {
    const target = e.target as HTMLElement;
    if (!target || target === this.overlay || target === this.label) return;

    const rect = target.getBoundingClientRect();
    const selector = this.getSelector(target);

    if (this.overlay) {
      Object.assign(this.overlay.style, {
        top: `${rect.top + window.scrollY}px`,
        left: `${rect.left + window.scrollX}px`,
        width: `${rect.width}px`,
        height: `${rect.height}px`,
      });
    }

    if (this.label) {
      this.label.textContent = selector;
      Object.assign(this.label.style, {
        top: `${rect.top + window.scrollY - 22}px`,
        left: `${rect.left + window.scrollX}px`,
      });
    }
  };

  private handleClick = (e: MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();

    const target = e.target as HTMLElement;
    if (!target || target === this.overlay || target === this.label) return;

    const element: ClickedElement = {
      selector: this.getSelector(target),
      tag: target.tagName.toLowerCase(),
      text: target.innerText?.slice(0, 200) ?? "",
      attributes: this.getAttributes(target),
    };

    this.onSelect(element);
    this.deactivate();
  };

  private handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === "Escape") {
      this.deactivate();
    }
  };

  private getSelector(el: HTMLElement): string {
    if (el.id) return `#${el.id}`;

    const parts: string[] = [];
    let current: HTMLElement | null = el;

    while (current && current !== document.body) {
      let selector = current.tagName.toLowerCase();
      if (current.className) {
        const classes = Array.from(current.classList)
          .filter((c) => !c.startsWith("te-"))
          .slice(0, 2)
          .join(".");
        if (classes) selector += `.${classes}`;
      }
      parts.unshift(selector);
      current = current.parentElement;
    }

    return parts.slice(-3).join(" > ");
  }

  private getAttributes(el: HTMLElement): Record<string, string> {
    const attrs: Record<string, string> = {};
    for (const attr of Array.from(el.attributes).slice(0, 10)) {
      attrs[attr.name] = attr.value.slice(0, 100);
    }
    return attrs;
  }
}
