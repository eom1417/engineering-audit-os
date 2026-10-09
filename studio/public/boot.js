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

// Starts reading the report's data while the Studio's own script is still downloading (src/data/load.ts waits for
// it): the manifest, then every section it lists, each a classic script beside index.html. A tab holding the live
// server's token (the same test as src/data/live.ts liveToken) reads the server's API instead: nothing to load here.
window.EAOS_DATA = new Promise(function (done) {
  var token = window.EAOS_BOOT_TOKEN;
  try { token = token || sessionStorage.getItem('eaos.token'); } catch (e) { /* storage refused */ }
  if (/^https?:$/.test(location.protocol) && token) return done();
  function add(name, then) {
    var tag = document.createElement('script');
    tag.src = './' + name + '.js';
    tag.onload = tag.onerror = then;
    document.head.appendChild(tag);
  }
  add('manifest', function () {
    var manifest = (window.EAOS_STUDIO || {}).manifest;
    // functions.json is the largest section and only its own pages read it: they load it when they open
    // (pages/functions/model.ts useSection), so no other page waits for it.
    var names = (manifest && manifest.sections || []).map(function (s) { return s.name; }).filter(function (n) { return /^[a-z][a-z_]*$/.test(n) && n !== 'functions'; });
    var left = names.length;
    if (!left) return done();
    names.forEach(function (name) { add(name, function () { if (--left === 0) done(); }); });
  });
});
