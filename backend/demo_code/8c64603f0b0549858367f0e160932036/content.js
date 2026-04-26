const EVOLVE_TERMS = ["shorts"];

function shouldHide(element) {
  const text = [
    element.getAttribute('href'),
    element.getAttribute('aria-label'),
    element.getAttribute('data-testid'),
    element.className,
    element.textContent,
  ]
    .filter(Boolean)
    .join(' ')
    .toLowerCase();

  return EVOLVE_TERMS.some((term) => text.includes(term));
}

function hideElement(element) {
  if (!element || element.dataset.browserForgeHidden === 'true') {
    return;
  }
  element.dataset.browserForgeHidden = 'true';
  element.style.setProperty('display', 'none', 'important');
}

function applyBrowserForgeChanges() {
  document
    .querySelectorAll('a, button, [role="button"], section, aside, div')
    .forEach((element) => {
      if (shouldHide(element)) {
        const container = element.closest('article, section, nav, aside, li, div[role="button"]');
        hideElement(container || element);
      }
    });
}

applyBrowserForgeChanges();
setInterval(applyBrowserForgeChanges, 1000);

new MutationObserver(applyBrowserForgeChanges).observe(document.documentElement, {
  childList: true,
  subtree: true,
});
