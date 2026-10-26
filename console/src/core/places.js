// The code of each place is its own file (assets/<bundle>.js, from src/places/<bundle>/index.js), read the first time
// one of its addresses or sheets opens; the core holds only the shell, the data layer and the shared sheets.
// Which bundle holds an address is fixed by the IA (the longest prefix wins); which bundle holds a sheet the build
// finds in the sources (every `sheet('<name>'` of a place, scripts/build.mjs), so a builder never edits this table to
// add a sheet.

/* global __EAOS_SHEETS__ */
const SHEETS = __EAOS_SHEETS__;

const PREFIXES = [
  ['/status', 'status'], ['/waiting', 'waiting'], ['/problems/plan', 'plan'], ['/problems', 'problems'], ['/activity', 'activity'],
  ['/project', 'project'], ['/ask', 'ask'], ['/open', 'open'], ['/report', 'report'],
];

/** The bundle that holds the screen at `path`. */
export function bundleOfPath(path) {
  const hit = PREFIXES.filter(([prefix]) => path === prefix || path.startsWith(prefix + '/')).sort((a, b) => b[0].length - a[0].length)[0];
  return hit ? hit[1] : 'status';
}
export const bundleOfSheet = name => SHEETS[name] || null;

const loaded = new Set();
/** Reads a bundle once; resolves true when it registered itself. */
export function loadBundle(name) {
  if (loaded.has(name)) return Promise.resolve(true);
  return self.EAOS_SCRIPT(`./assets/${name}.js`).then(ok => { if (ok) loaded.add(name); return ok; });
}
export const isLoaded = name => loaded.has(name);
