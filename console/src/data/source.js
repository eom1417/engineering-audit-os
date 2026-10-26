// The report, read one section at a time from the read API of `eaos studio` (eaos/interfaces/studio_server/read.py), every call carrying
// the launch token as a header (never in a URL, so it reaches no log), with the sign-in cookie of a remote address
// (credentials: same-origin). Without a token (a read-only page) there is nothing to read: the console says so.
// A section is read when a screen first needs it (screen `needs`), once; a live reload re-reads only the sections
// whose sha256 in the manifest changed.
import { prefs } from '../core/prefs.js';

export const CONTRACT = 1;
const TOKEN_KEY = 'eaos.token';

/** The launch token of this tab, or null when the console was opened as a read-only copy. */
function liveToken() {
  if (!/^https?:$/.test(location.protocol)) return null;
  try { return sessionStorage.getItem(TOKEN_KEY) || window.EAOS_BOOT_TOKEN || null; } catch (e) { return window.EAOS_BOOT_TOKEN || null; }
}

export const token = liveToken();
export const mode = token ? 'live' : 'snapshot';

const R = { kind: 'loading', manifest: null, data: {}, reading: {}, missing: new Set(), locale: null, contract: null };
const listeners = new Set();
/** Calls `fn` after sections arrive or change (the router redraws the screen). */
export function onChange(fn) { listeners.add(fn); return () => listeners.delete(fn); }
const changed = names => listeners.forEach(fn => fn(names));

/** A GET of the live API with the launch token. */
export function apiGet(path) {
  return fetch(path, { headers: { 'X-EAOS-Token': token, Accept: 'application/json' }, cache: 'no-store', credentials: 'same-origin' });
}

async function readManifest() {
  if (mode === 'live') {
    const answer = await apiGet('/api/manifest');
    if (answer.status === 404) return null;
    if (!answer.ok) throw new Error(`manifest: ${answer.status}`);
    return answer.json();
  }
  return null;
}

async function readSection(name) {
  if (mode === 'live') {
    try {
      const answer = await apiGet(`/api/sections/${encodeURIComponent(name)}`);
      return answer.ok ? await answer.json() : undefined;
    } catch (e) { return undefined; }
  }
  return undefined;
}

async function readLocale(manifest) {
  if (!(manifest.locales && manifest.locales.en)) return null;
  if (mode === 'live') {
    try { const answer = await apiGet('/api/locales/en'); return answer.ok ? await answer.json() : null; } catch (e) { return null; }
  }
  return null;
}

/** Reads the manifest: 'ready', 'empty' (no check has written the data yet) or 'error' (another contract). */
export async function start() {
  try {
    const manifest = await readManifest();
    if (!manifest) R.kind = 'empty';
    else if (manifest.contract !== CONTRACT) { R.kind = 'error'; R.contract = manifest.contract; }
    else {
      R.manifest = manifest;
      R.kind = 'ready';
      R.locale = await readLocale(manifest);
    }
  } catch (e) { R.kind = 'empty'; }
  return R.kind;
}

export const state = () => R.kind;
export const manifest = () => R.manifest;
export const contractSeen = () => R.contract;
export const listed = name => !!(R.manifest && R.manifest.sections.some(s => s.name === name));
/** A section's data, or undefined while it is not read (or not written by the check). */
export const section = name => R.data[name];
/** Whether the check wrote `name` and it could not be read. */
export const isMissing = name => R.missing.has(name);
/** The sections of `names` still to read: listed by the manifest, neither read nor missing. */
export const pendingOf = names => (names || []).filter(n => listed(n) && R.data[n] === undefined && !R.missing.has(n));

/** Reads every section of `names` not read yet; resolves when each has arrived or is missing. */
export function need(names) {
  const fresh = pendingOf(names);
  if (!fresh.length) return Promise.resolve();
  return Promise.all(fresh.map(name => (R.reading[name] = R.reading[name] || readSection(name).then(data => {
    delete R.reading[name];
    if (data === undefined) R.missing.add(name); else R.data[name] = data;
  })))).then(() => changed(fresh));
}

/** The live report after the server said something changed: the manifest again, and every section already read
 *  whose sha256 changed (or every one, after a reset). Sections not read yet stay unread until a screen needs them. */
export async function reload(all) {
  if (mode !== 'live') return;
  const before = new Map(((R.manifest && R.manifest.sections) || []).map(s => [s.name, s.sha256]));
  const kind = R.kind;
  await start();
  if (R.kind !== 'ready') { if (kind !== R.kind) changed([]); return; }
  const stale = R.manifest.sections.filter(s => (all || before.get(s.name) !== s.sha256) && (R.data[s.name] !== undefined || R.missing.has(s.name))).map(s => s.name);
  stale.forEach(name => { delete R.data[name]; R.missing.delete(name); });
  if (stale.length) await need(stale); else if (kind !== R.kind) changed([]);
}

/** A report text in the person's language: the report's own words, or their translation when the report has one. */
export function reportText(s) {
  const table = R.locale && R.locale.translations && R.locale.translations[prefs.lang];
  return (table && table[s]) || s;
}

/** Part of the library (live: only the documents and images named, eaos/interfaces/studio_server/read.py library_items); the read-only
 *  copy reads it whole. */
export async function libraryItems(ids) {
  if (mode !== 'live') return readSection('library');
  const answer = await apiGet(`/api/sections/library?only=${encodeURIComponent(ids.join(','))}`);
  return answer.ok ? answer.json() : undefined;
}

/** A text file the check produced (live only), or null. */
export async function reportFile(path) {
  if (mode !== 'live') return null;
  const answer = await apiGet(`/api/report-file?path=${encodeURIComponent(path)}`);
  return answer.ok ? answer.text() : null;
}

/** A one-use address of the report for people, opened in a tab of this browser (live only), or null. */
export async function reportPage() {
  if (mode !== 'live') return null;
  const answer = await apiGet('/api/report-ticket');
  return answer.ok ? (await answer.json()).url : null;
}

/** A picture the server gives only with the launch token, as a data: address (the page allows data: images, not
 *  blob:), or null when it cannot be read. */
export async function tokenImage(path) {
  if (mode !== 'live') return null;
  try {
    const answer = await apiGet(path);
    if (!answer.ok) return null;
    const blob = await answer.blob();
    return await new Promise(done => {
      const reader = new FileReader();
      reader.onload = () => done(String(reader.result));
      reader.onerror = () => done(null);
      reader.readAsDataURL(blob);
    });
  } catch (e) { return null; }
}
