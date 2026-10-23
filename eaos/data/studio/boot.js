// Runs first, before the first paint: the language, direction and theme, the launch token, and the start of every
// download the first view needs, so nothing waits for the console's own script to arrive.
// Order of the choices: ?lang= / ?theme= in the address (search or route), then the last choice (localStorage
// 'eaos.studio'), then the system's colour scheme. The search part is removed from the address once read, so the hash
// routes own the URL.
(function () {
  var q = new URLSearchParams(location.search), h = document.documentElement, saved = {};
  var route = new URLSearchParams((location.hash.split('?')[1] || ''));
  try { saved = JSON.parse(localStorage.getItem('eaos.studio') || '{}') || {}; } catch (e) { saved = {}; }
  var lang = q.get('lang') || route.get('lang'), theme = q.get('theme') || route.get('theme');
  if (lang) saved.lang = lang === 'en' ? 'en' : 'ar';
  if (theme) saved.theme = theme === 'dark' ? 'dark' : 'light';
  // ?token=… is the remote address's form of the launch token: a sign-in in front of the server keeps the query
  // through its redirects, where the #token=… fragment is lost. Kept for this tab only, like the fragment below.
  var asked = /^[A-Za-z0-9_-]{16,128}$/.test(q.get('token') || '') ? q.get('token') : null;
  if (asked && /^https?:$/.test(location.protocol)) {
    window.EAOS_BOOT_TOKEN = asked;
    try { sessionStorage.setItem('eaos.token', asked); } catch (e) { /* storage refused: this visit only */ }
  }
  if (lang || theme) { try { localStorage.setItem('eaos.studio', JSON.stringify(saved)); } catch (e) { /* private mode */ } }
  if (location.search) {
    try { history.replaceState(null, '', location.pathname + location.hash); } catch (e) { /* some file:// pages refuse */ }
  }
  // The live server's launch token (#token=…, or #/<route>?…&token=…, eaos/api/launch.py): kept for this tab only,
  // then removed from the address so it is never bookmarked, shared or shown; the route, if any, stays.
  var live = /^#token=([A-Za-z0-9_-]{16,128})$/.exec(location.hash) || /^(#\/[^?]*\?(?:.*&)?)token=([A-Za-z0-9_-]{16,128})$/.exec(location.hash);
  if (live) {
    var key = live[2] || live[1], route = live[2] ? live[1].replace(/[?&]$/, '') : '#/status';
    window.EAOS_BOOT_TOKEN = key;
    try { sessionStorage.setItem('eaos.token', key); } catch (e) { /* storage refused: this visit only */ }
    try { history.replaceState(null, '', location.pathname + location.search + route); } catch (e) { location.hash = route; }
  }
  lang = saved.lang === 'en' ? 'en' : 'ar';
  theme = saved.theme || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  h.lang = lang; h.dir = lang === 'ar' ? 'rtl' : 'ltr'; h.dataset.theme = theme === 'dark' ? 'dark' : 'light';

  // One loader of classic scripts beside index.html (a page opened from a file refuses fetch() but runs a script from
  // its own folder): each address is read once, and every later caller gets the same promise.
  var loading = {};
  window.EAOS_SCRIPT = function (src) {
    return loading[src] || (loading[src] = new Promise(function (done) {
      var tag = document.createElement('script');
      tag.src = src;
      tag.onload = function () { done(true); };
      tag.onerror = function () { delete loading[src]; done(false); };
      document.head.appendChild(tag);
    }));
  };
  window.EAOS_SCRIPT('./assets/words-' + lang + '.js');

  var token = window.EAOS_BOOT_TOKEN;
  try { token = token || sessionStorage.getItem('eaos.token'); } catch (e) { /* storage refused */ }
  var served = /^https?:$/.test(location.protocol);
  if (served) {
    // The fonts the first view draws with start beside the console's script rather than after it has drawn (a font
    // preload on a page opened from a file is never used).
    var fonts = ['ibm-plex-sans-arabic-latin-400-normal', 'ibm-plex-sans-arabic-latin-600-normal', 'ibm-plex-mono-latin-400-normal'];
    if (lang === 'ar') fonts = fonts.concat(['ibm-plex-sans-arabic-arabic-400-normal', 'ibm-plex-sans-arabic-arabic-600-normal']);
    fonts.forEach(function (name) {
      var link = document.createElement('link');
      link.rel = 'preload'; link.as = 'font'; link.type = 'font/woff2'; link.crossOrigin = 'anonymous'; link.href = './assets/' + name + '.woff2';
      document.head.appendChild(link);
    });
  }
})();
