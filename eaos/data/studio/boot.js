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

// Starts reading the report's data while the Studio's own script is still downloading (src/data/load.ts waits for
// it): the manifest, then every section it lists, each a classic script beside index.html.
window.EAOS_DATA = new Promise(function (done) {
  function add(name, then) {
    var tag = document.createElement('script');
    tag.src = './' + name + '.js';
    tag.onload = tag.onerror = then;
    document.head.appendChild(tag);
  }
  add('manifest', function () {
    var manifest = (window.EAOS_STUDIO || {}).manifest;
    var names = (manifest && manifest.sections || []).map(function (s) { return s.name; }).filter(function (n) { return /^[a-z]+$/.test(n); });
    var left = names.length;
    if (!left) return done();
    names.forEach(function (name) { add(name, function () { if (--left === 0) done(); }); });
  });
});
