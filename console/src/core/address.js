// Addresses: every screen and sheet is #/<path>?<query> (the prototype's addresses exactly). Moving to another one
// changes the address; the router (router.js) answers the hashchange, so nothing here depends on it.

export function parseHash() {
  const raw = location.hash.replace(/^#/, '') || '/status';
  const i = raw.indexOf('?');
  const path = (i < 0 ? raw : raw.slice(0, i)) || '/status';
  const query = {};
  new URLSearchParams(i < 0 ? '' : raw.slice(i + 1)).forEach((v, k) => { query[k] = v; });
  return { path: path.replace(/\/+$/, '') || '/status', query };
}

export function href(path, query) {
  const q = new URLSearchParams();
  Object.keys(query || {}).forEach(k => { if (query[k] != null && query[k] !== '') q.set(k, query[k]); });
  const s = q.toString();
  return '#' + path + (s ? '?' + s : '');
}

/** Goes to an address; `replace` keeps it out of the history. The same address draws again. */
export function navigate(path, query, opts) {
  const h = href(path, query);
  if ((opts && opts.replace) || location.hash === h) {
    if (opts && opts.replace) history.replaceState(null, '', h);
    window.dispatchEvent(new HashChangeEvent('hashchange'));
  } else location.hash = h;
}

/** Changes part of the query in place (replace by default). */
export function setQuery(patch, opts) {
  const r = parseHash();
  const q = Object.assign({}, r.query, patch);
  Object.keys(q).forEach(k => { if (q[k] == null || q[k] === '') delete q[k]; });
  navigate(r.path, q, opts || { replace: true });
}
const typing = {};
/** A search box typed into: its words become the address's `q` once typing pauses (`also`: more of the address set
 *  with them), and the redrawn box, found by its data-fk, keeps the cursor at the end of its words. */
export function searchTyped(el, pause = 180, also = {}) {
  const fk = el.dataset.fk, v = el.value;
  clearTimeout(typing[fk]);
  typing[fk] = setTimeout(() => { setQuery({ q: v || null, ...also }); const i = document.querySelector(`[data-fk="${fk}"]`); if (i) { i.focus(); i.setSelectionRange(i.value.length, i.value.length); } }, pause);
}

/** Asks for the screen to be drawn again in place (main.js hands it to the router). */
export function redraw() { window.dispatchEvent(new Event('eaos:redraw')); }
