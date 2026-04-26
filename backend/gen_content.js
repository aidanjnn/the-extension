function applyYellowBackgroundClass() {
  // Apply class to html and body elements for general background
  document.documentElement.classList.add('bf-yellow-background');
  document.body.classList.add('bf-yellow-background');

  // Apply class to YouTube's main app containers
  const ytdApp = document.querySelector('ytd-app');
  if (ytdApp) {
    ytdApp.classList.add('bf-yellow-background');
  }

  const pageManager = document.querySelector('ytd-page-manager');
  if (pageManager) {
    pageManager.classList.add('bf-yellow-background');
  }
}

// Apply the background class initially when the script loads
applyYellowBackgroundClass();

// Use a MutationObserver to ensure the class persists in dynamic single-page applications
const observer = new MutationObserver((mutations) => {
  let needsUpdate = false;
  for (const mutation of mutations) {
    // Check if relevant elements (html, body, ytd-app, ytd-page-manager) were modified
    // or if their class attributes changed, which might remove our injected class.
    if (
      (mutation.type === 'childList' && (mutation.target === document.body || mutation.target === document.documentElement)) ||
      (mutation.type === 'attributes' && mutation.attributeName === 'class' &&
       (mutation.target === document.body || mutation.target === document.documentElement ||
        mutation.target.tagName === 'YTD-APP' || mutation.target.tagName === 'YTD-PAGE-MANAGER'))
    ) {
      needsUpdate = true;
      break;
    }
  }
  if (needsUpdate) {
    // Debounce the update with requestAnimationFrame to avoid excessive DOM manipulations
    requestAnimationFrame(applyYellowBackgroundClass);
  }
});

// Observe the html and body elements for changes in their children (subtree) and attributes
observer.observe(document.documentElement, { childList: true, subtree: true, attributes: true, attributeFilter: ['class'] });
observer.observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ['class'] });

// Also observe ytd-app and ytd-page-manager if they are already present in the DOM
const ytdApp = document.querySelector('ytd-app');
if (ytdApp) {
  observer.observe(ytdApp, { attributes: true, attributeFilter: ['class'] });
}
const pageManager = document.querySelector('ytd-page-manager');
if (pageManager) {
  observer.observe(pageManager, { attributes: true, attributeFilter: ['class'] });
}