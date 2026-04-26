import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { setHoverHighlighterEnabled, startHoverHighlighter } from './highlighter'
import { MESSAGE_TYPES } from '../shared/messages'
import App from './views/App.tsx'

console.log('[Browser Forge] content script loaded')

const CONSOLE_LEVELS = ['log', 'info', 'warn', 'error', 'debug'] as const
type ConsoleLevel = (typeof CONSOLE_LEVELS)[number]

const safeStringify = (value: unknown) => {
  const seen = new WeakSet()
  try {
    return JSON.stringify(value, (_key, val) => {
      if (typeof val === 'object' && val !== null) {
        if (seen.has(val)) return '[Circular]'
        seen.add(val)
      }
      if (val instanceof Error) {
        return {
          name: val.name,
          message: val.message,
          stack: val.stack,
        }
      }
      return val
    })
  } catch {
    return String(value)
  }
}

const formatConsoleArgs = (args: unknown[]) =>
  args
    .map((arg) => {
      if (typeof arg === 'string') return arg
      if (arg instanceof Error) return arg.stack ?? arg.message
      return safeStringify(arg)
    })
    .join(' ')

const sendConsoleLog = (level: ConsoleLevel, args: unknown[]) => {
  const message = formatConsoleArgs(args)
  if (!chrome?.runtime?.id) return
  void chrome.runtime
    .sendMessage({
      type: MESSAGE_TYPES.storeConsoleLog,
      payload: {
        level,
        timestamp: Date.now(),
        message,
        url: window.location.href,
      },
    })
    .catch(() => {})
}

const hookConsole = () => {
  const win = window as unknown as { __browserForgeConsoleHooked?: boolean }
  if (win.__browserForgeConsoleHooked) return
  win.__browserForgeConsoleHooked = true

  CONSOLE_LEVELS.forEach((level) => {
    const consoleRef = console as unknown as Record<string, (...args: unknown[]) => void>
    const original = consoleRef[level].bind(console)
    consoleRef[level] = (...args: unknown[]) => {
      sendConsoleLog(level, args)
      original(...args)
    }
  })

  window.addEventListener('error', (event) => {
    sendConsoleLog('error', [event.message, event.error])
  })

  window.addEventListener('unhandledrejection', (event) => {
    sendConsoleLog('error', ['Unhandled promise rejection', event.reason])
  })
}

hookConsole()

startHoverHighlighter()

const MAX_CONTEXT_HTML_CHARS = 1000

const sanitizeElementTree = (root: Element) => {
  const selectors = [
    'script',
    'style',
    'noscript',
    'svg',
    'header',
    'nav',
    'footer',
    'iframe',
    'canvas',
    'template',
  ]

  selectors.forEach((selector) => {
    root.querySelectorAll(selector).forEach((el) => el.remove())
  })

  root.querySelectorAll('[hidden], [aria-hidden="true"]').forEach((el) => el.remove())

  root.querySelectorAll<HTMLElement>('[style]').forEach((el) => {
    const style = el.getAttribute('style')?.toLowerCase() || ''
    if (style.includes('display:none') || style.includes('visibility:hidden')) {
      el.remove()
    }
  })
}

const pruneLargeHtml = (root: Element) => {
  const selectors = [
    'script',
    'style',
    'noscript',
    'svg',
    'header',
    'nav',
    'footer',
    'iframe',
    'canvas',
    'template',
    'meta',
    'link',
    'form',
    'input',
    'textarea',
    'select',
    'button',
    'video',
    'audio',
    'picture',
    'source',
    'object',
    'embed',
  ]

  selectors.forEach((selector) => {
    root.querySelectorAll(selector).forEach((el) => el.remove())
  })

  root.querySelectorAll<HTMLElement>('*').forEach((el) => {
    Array.from(el.attributes).forEach((attr) => {
      const name = attr.name.toLowerCase()
      if (
        name.startsWith('on') ||
        name === 'style' ||
        name === 'srcset' ||
        name === 'src' ||
        name === 'href' ||
        name === 'integrity' ||
        name === 'nonce' ||
        name === 'crossorigin' ||
        name === 'referrerpolicy'
      ) {
        el.removeAttribute(attr.name)
      }
    })
  })
}

// Listen for sidepanel lifecycle messages to toggle the highlighter
chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type === MESSAGE_TYPES.sidepanelOpen) {
    return
  }

  if (message?.type === MESSAGE_TYPES.sidepanelClose) {
    setHoverHighlighterEnabled(false)
    return
  }

  if (message?.type === MESSAGE_TYPES.setDomEditMode) {
    setHoverHighlighterEnabled(Boolean(message?.enabled))
    return
  }

  if (message?.type === MESSAGE_TYPES.getPageContent) {
    // Return full page content — raw HTML or visible text depending on the flag.
    // Pagination / chunking is handled server-side.
    const raw = message.includeHtml
      ? (document.body?.innerHTML ?? '')
      : (document.body?.innerText ?? '')
    sendResponse({ content: raw })
    return // synchronous response
  }

  if (message?.type === MESSAGE_TYPES.getElementHtml) {
    const selector = message?.selector
    const stripHighlighting = (root: Element) => {
      const idsToRemove = [
        'browser-forge-hover-highlight-style',
        'browser-forge-hover-highlight-overlay',
        'browser-forge-hover-highlight-label',
        'browser-forge-click-highlight-overlay',
        'browser-forge-click-highlight-label',
      ]

      if (root.classList.contains('browser-forge-clicked-highlight')) {
        root.classList.remove('browser-forge-clicked-highlight')
      }

      root.querySelectorAll('.browser-forge-clicked-highlight').forEach((el) => {
        el.classList.remove('browser-forge-clicked-highlight')
      })

      idsToRemove.forEach((id) => {
        root.querySelectorAll(`#${id}`).forEach((el) => el.remove())
      })
    }
    if (typeof selector === 'string' && selector.length > 0) {
      const el = document.querySelector(selector)
      if (!el) {
        sendResponse({ html: '' })
        return true
      }
      const clone = el.cloneNode(true) as Element
      stripHighlighting(clone)
      sanitizeElementTree(clone)
      let html = clone.outerHTML
      if (html.length > MAX_CONTEXT_HTML_CHARS) {
        pruneLargeHtml(clone)
        html = clone.outerHTML
        if (html.length > MAX_CONTEXT_HTML_CHARS) {
          html = html.slice(0, MAX_CONTEXT_HTML_CHARS)
        }
      }
      sendResponse({ html })
      return true
    }
    const root = (document.body ?? document.documentElement)?.cloneNode(true) as Element | null
    if (!root) {
      sendResponse({ html: '' })
      return true
    }
    stripHighlighting(root)
    sanitizeElementTree(root)
    sendResponse({ html: root.outerHTML })
    return true
  }
})

function mountBrowserForgeApp() {
  if (document.getElementById('browser-forge-app')) return
  const mountTarget = document.body || document.documentElement
  if (!mountTarget) return
  const container = document.createElement('div')
  container.id = 'browser-forge-app'
  mountTarget.appendChild(container)
  createRoot(container).render(
    <StrictMode>
      <App />
    </StrictMode>,
  )
}

if (document.body) {
  mountBrowserForgeApp()
} else {
  document.addEventListener('DOMContentLoaded', mountBrowserForgeApp, { once: true })
}
