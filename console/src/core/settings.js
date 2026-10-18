// Changing the language, the theme and the time zone (SET-01..03): applied at once to every screen, and remembered.
import { applyDocument, prefs, remember } from './prefs.js';
import { loadWords } from './i18n.js';
import { onRoute, parseHash, refresh, setQuery } from './router.js';

export function setLang(lang) {
  prefs.lang = lang === 'en' ? 'en' : 'ar';
  remember('lang', prefs.lang);
  // a language the address asked for gives way to the one chosen now
  return loadWords(prefs.lang).then(() => { applyDocument(); if (parseHash().query.lang && parseHash().query.lang !== prefs.lang) setQuery({ lang: null }); else onRoute(); refresh(); });
}

export function setTheme(theme, silent) {
  prefs.theme = theme === 'dark' ? 'dark' : 'light';
  prefs.chosenTheme = true;
  remember('theme', prefs.theme);
  applyDocument();
  if (!silent && parseHash().query.theme && parseHash().query.theme !== prefs.theme) setQuery({ theme: null });
  else if (!silent) refresh();
}

/** `zone`: an IANA time zone, or null to follow the device again. */
export function setTimeZone(zone) {
  prefs.tz = zone || Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
  remember('tz', zone || null);
  refresh();
}
