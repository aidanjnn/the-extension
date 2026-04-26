// Shared message types and payload shapes between background/content/sidepanel.
export const CLICKED_ELEMENTS_KEY = 'hoverHighlighterClickedElements'
export const DOM_EDIT_ELEMENTS_KEY = 'browserForgeDomEditElements'
export const DOM_EDIT_MODE_KEY = 'browserForgeDomEditMode'

export const MESSAGE_TYPES = {
  getClicked: 'get-clicked-elements',
  getAllClicked: 'get-all-clicked-elements',
  storeClicked: 'store-clicked-element',
  removeClicked: 'remove-clicked-element',
  removeClickedBulk: 'remove-clicked-elements-bulk',
  toggleClicked: 'toggle-clicked-element',
  getElementHtml: 'get-element-html',
  clearClicked: 'clear-clicked-elements',
  clearAllClicked: 'clear-all-clicked-elements',
  sidepanelOpen: 'sidepanel-open',
  sidepanelClose: 'sidepanel-close',
  getSidepanelState: 'get-sidepanel-state',
  highlightSelector: 'highlight-selector',
  unhighlightSelector: 'unhighlight-selector',
  clearHighlightsDom: 'clear-clicked-dom',
  clickedElementsUpdated: 'clicked-elements-updated',
  setDomEditMode: 'set-dom-edit-mode',
  getDomEditMode: 'get-dom-edit-mode',
  applyDomEdit: 'apply-dom-edit',
  clearDomEdits: 'clear-dom-edits',
  domEditsUpdated: 'dom-edits-updated',
  getPageContent: 'get-page-content',
  storeConsoleLog: 'store-console-log',
  getConsoleLogs: 'get-console-logs',
  clearConsoleLogs: 'clear-console-logs',
} as const

export type MessageType = (typeof MESSAGE_TYPES)[keyof typeof MESSAGE_TYPES]

export type ClickedElementPayload = {
  tag: string
  id: string | null
  classes: string[]
  selector: string
  url: string
  timestamp: number
  tabTitle?: string
  text?: string
  html?: string
  rect?: {
    x: number
    y: number
    width: number
    height: number
  }
  selectionOrder?: number
}

export type ClickedElementStored = ClickedElementPayload & {
  tabId: number
}

export type DomEditKind =
  | 'hide'
  | 'resize'
  | 'style'
  | 'move'
  | 'emphasize'
  | 'text'

export type DomEditOperation = {
  id: string
  kind: DomEditKind
  selector: string
  url: string
  tabId?: number
  label?: string
  order: number
  createdAt: number
  styles?: Record<string, string>
  text?: string
  description: string
}
