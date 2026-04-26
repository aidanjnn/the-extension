/**
 * Wrappers around chrome.* APIs that tolerate "extension context invalidated"
 * errors. When a content script is left running on a page after the extension
 * has been reloaded, every call to chrome.runtime / chrome.storage throws.
 * These helpers detect that state and silently no-op so the page doesn't fill
 * with uncaught TypeErrors.
 */

let invalidated = false
const onInvalidatedCallbacks: Array<() => void> = []

export function isExtensionContextValid(): boolean {
  if (invalidated) return false
  try {
    return Boolean(chrome?.runtime?.id)
  } catch {
    return false
  }
}

function markInvalidated() {
  if (invalidated) return
  invalidated = true
  for (const cb of onInvalidatedCallbacks.splice(0)) {
    try {
      cb()
    } catch {
      // ignore
    }
  }
}

export function onContextInvalidated(callback: () => void) {
  if (invalidated) {
    callback()
    return
  }
  onInvalidatedCallbacks.push(callback)
}

function isContextError(err: unknown): boolean {
  if (!err) return false
  const msg = (err as { message?: string }).message || String(err)
  return (
    msg.includes('Extension context invalidated') ||
    msg.includes('Receiving end does not exist') ||
    msg.includes("Cannot read properties of undefined")
  )
}

export async function safeSendMessage<T = unknown>(
  message: unknown,
): Promise<T | null> {
  if (!isExtensionContextValid()) return null
  try {
    return (await chrome.runtime.sendMessage(message)) as T
  } catch (err) {
    if (isContextError(err)) markInvalidated()
    return null
  }
}

export async function safeStorageGet<T = Record<string, unknown>>(
  keys: string | string[],
): Promise<T | null> {
  if (!isExtensionContextValid()) return null
  try {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return (await chrome.storage.local.get(keys as any)) as T
  } catch (err) {
    if (isContextError(err)) markInvalidated()
    return null
  }
}

export async function safeStorageSet(
  items: Record<string, unknown>,
): Promise<boolean> {
  if (!isExtensionContextValid()) return false
  try {
    await chrome.storage.local.set(items)
    return true
  } catch (err) {
    if (isContextError(err)) markInvalidated()
    return false
  }
}

/**
 * Wrap chrome.runtime.onMessage.addListener so that listener registration
 * itself doesn't throw if the context is already invalidated.
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type MessageListener = (message: any, sender: chrome.runtime.MessageSender, sendResponse: (response?: any) => void) => boolean | void

export function safeAddMessageListener(listener: MessageListener): void {
  if (!isExtensionContextValid()) return
  try {
    chrome.runtime.onMessage.addListener(listener)
  } catch (err) {
    if (isContextError(err)) markInvalidated()
  }
}
