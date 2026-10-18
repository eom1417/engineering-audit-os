// Changing the language, the theme and the time zone (SET-01..03): applied at once to every screen, and remembered.
import { applyDocument, prefs, remember } from './prefs.js';
import { loadWords } from './i18n.js';
import { onRoute, refresh } from './router.js';

export function setLang(lang) {
  prefs.lang = lang === 'en' ? 'en' : 'ar';
  remember('lang', prefs.lang);
  return loadWords(prefs.lang).then(() => { applyDocument(); onRoute(); refresh(); });
}

export function setTheme(theme, silent) {
  prefs.theme = theme === 'dark' ? 'dark' : 'light';
  prefs.chosenTheme = true;
  remember('theme', prefs.theme);
  applyDocument();
  if (!silent) refresh();
}

/** `zone`: an IANA time zone, or null to follow the device again. */
export function setTimeZone(zone) {
  prefs.tz = zone || Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
  remember('tz', zone || null);
  refresh();
}
