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
  var lang = saved.lang === 'en' ? 'en' : 'ar';
  var theme = saved.theme || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  h.lang = lang; h.dir = lang === 'ar' ? 'rtl' : 'ltr'; h.dataset.theme = theme === 'dark' ? 'dark' : 'light';
})();
