// The one dictionary: every visible word in Arabic and English (src/words/*.js, split per language by the build into
// assets/words-<lang>.js, which registers itself in self.EAOS_WORDS). A plural entry is an object of forms; {n} is
// the number, always in Latin digits. Report texts are the report's own words: shown as they are, or through the
// report's translation table when it has one (src/data/source.js reportText).
import { prefs } from './prefs.js';
import { reportText } from '../data/source.js';

const plural = { ar: new Intl.PluralRules('ar'), en: new Intl.PluralRules('en') };
const nf = new Intl.NumberFormat('en-US');
const words = () => (self.EAOS_WORDS || {});

/** Reads the dictionary of `lang` (once); resolves false when its file cannot be read. */
export function loadWords(lang) {
  return words()[lang] ? Promise.resolve(true) : self.EAOS_SCRIPT(`./assets/words-${lang}.js`);
}

export function fill(str, vars) {
  return String(str).replace(/\{(\w+)\}/g, (m, k) => (vars && vars[k] != null ? vars[k] : m));
}

function entry(key) {
  const own = words()[prefs.lang] || {};
  return own[key] != null ? own[key] : (words().ar || {})[key];
}

/** Whether the dictionary has a word for `key` (a name from the report may have none). */
export function has(key) { return entry(key) != null; }

export function t(key, vars) {
  const v = entry(key);
  if (v == null) { console.warn('missing word', key); return key; }
  if (typeof v === 'object') return tn(key, vars && vars.n, vars);
  return fill(v, vars);
}

export function tn(key, n, vars) {
  const forms = entry(key);
  if (forms == null) { console.warn('missing word', key); return key; }
  const cat = plural[prefs.lang].select(n);
  const s = forms[cat] != null ? forms[cat] : (forms.other != null ? forms.other : forms.many);
  return fill(s, Object.assign({}, vars, { n: num(n) }));
}

/** A text in both languages ({ar, en}) in the person's language; a plain string is a report text. */
export function L(o) {
  if (o == null) return '';
  if (typeof o === 'object') return o[prefs.lang] != null ? o[prefs.lang] : (o.ar != null ? o.ar : o.en || '');
  return reportText(String(o));
}

export function num(n) { return n == null ? '' : nf.format(n); }
