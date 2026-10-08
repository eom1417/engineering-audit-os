// Sets the language, direction and theme before the first paint, so the page never flashes the wrong one.
// Order: ?lang= / ?theme= / ?dev= in the address (kept as the person's choice, then removed from the address so the
// hash routes own the URL), then the last choice, then the system's colour scheme.
(function () {
  var q = new URLSearchParams(location.search), h = document.documentElement, saved = {};
  try { saved = JSON.parse(localStorage.getItem('eaos.studio') || '{}') || {}; } catch (e) { saved = {}; }
  if (q.get('lang')) saved.lang = q.get('lang') === 'en' ? 'en' : 'ar';
  if (q.get('theme')) saved.theme = q.get('theme') === 'dark' ? 'dark' : 'light';
  if (q.get('dev') !== null) saved.dev = q.get('dev') === '1';
  if (location.search) {
    try { localStorage.setItem('eaos.studio', JSON.stringify(saved)); } catch (e) { /* private mode */ }
    window.EAOS_BOOT = saved; // this visit's choice even when storage is refused
    try { history.replaceState(null, '', location.pathname + location.hash); } catch (e) { /* some file:// pages refuse */ }
  }
  // The live server's launch token (#token=…, or #/<route>?…&token=…, eaos/api/launch.py): kept for this tab only,
  // then removed from the address so it is never bookmarked, shared or shown; the route, if any, stays.
  var live = /^#token=([A-Za-z0-9_-]{16,128})$/.exec(location.hash) || /^(#\/[^?]*\?(?:.*&)?)token=([A-Za-z0-9_-]{16,128})$/.exec(location.hash);
  if (live) {
    var key = live[2] || live[1], route = live[2] ? live[1].replace(/[?&]$/, '') : '#/';
    window.EAOS_BOOT_TOKEN = key;
    try { sessionStorage.setItem('eaos.token', key); } catch (e) { /* storage refused: this visit only */ }
    try { history.replaceState(null, '', location.pathname + location.search + route); } catch (e) { location.hash = route; }
  }
  var lang = saved.lang === 'en' ? 'en' : 'ar';
  var theme = saved.theme || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  h.lang = lang; h.dir = lang === 'ar' ? 'rtl' : 'ltr'; h.dataset.theme = theme === 'dark' ? 'dark' : 'light';
})();
