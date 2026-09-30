/* 
 * AuScope Tools: rewrite href to external & open in new tab.
 * Currently used to navigate to AVRE app store from header.
 */
(function () {
  'use strict';

  // Debug marker
  window.__AUSCOPE_TOOLS_DEBUG__ = { loaded: true, patchedNow: 0, cfg: null };

  function readConfig() {
    var el = document.getElementById('auscope-tools-config');
    if (!el) return null;
    return {
      toolsHref: el.getAttribute('data-tools-href') || '/tools',
      externalUrl: el.getAttribute('data-tools-external') || null
    };
  }

  function toAbs(href) {
    try { return new URL(href, window.location.origin).href; }
    catch (_) { return href; }
  }

  // Match both relative (/tools) and absolute (https://host/tools) forms
  function isToolsHref(href, cfg) {
    if (!href) return false;
    var rel = cfg.toolsHref;
    var abs = toAbs(rel);
    return href === rel || href === abs || href.endsWith(rel) || href.endsWith(rel + '/');
  }

  function rewrite(a, externalUrl) {
    a.setAttribute('href', externalUrl);
    a.setAttribute('target', '_blank');
    a.setAttribute('rel', 'noopener noreferrer');
  }

  function patchAll(cfg) {
    var count = 0;
    document.querySelectorAll('a[href]').forEach(function (a) {
      if (isToolsHref(a.getAttribute('href'), cfg)) {
        rewrite(a, cfg.externalUrl || toAbs(cfg.toolsHref));
        count++;
      }
    });
    return count;
  }

  function observe(cfg) {
    var obs = new MutationObserver(function (muts) {
      muts.forEach(function (m) {
        m.addedNodes && m.addedNodes.forEach(function (n) {
          if (n.nodeType !== 1) return;
          if (n.matches && n.matches('a[href]') && isToolsHref(n.getAttribute('href'), cfg)) {
            rewrite(n, cfg.externalUrl || toAbs(cfg.toolsHref));
          }
          if (n.querySelectorAll) {
            n.querySelectorAll('a[href]').forEach(function (a) {
              if (isToolsHref(a.getAttribute('href'), cfg)) {
                rewrite(a, cfg.externalUrl || toAbs(cfg.toolsHref));
              }
            });
          }
        });
      });
    });
    obs.observe(document.documentElement || document.body, { childList: true, subtree: true });
  }

  function init() {
    var cfg = readConfig();
    window.__AUSCOPE_TOOLS_DEBUG__.cfg = cfg;
    // If the span isn't present, nothing to do.
    if (!cfg) return;

    window.__AUSCOPE_TOOLS_DEBUG__.patchedNow = patchAll(cfg);
    // Keep future re-renders patched too
    observe(cfg);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();