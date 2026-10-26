// The person's choices, kept on this computer (localStorage 'eaos.report.studio', the key boot.js reads before the first
// paint): the language, the theme and the time zone every time is shown in. The theme follows the system until the
// person chooses one; the time zone is the device's until the person chooses another (SET-03).
const KEY = 'eaos.report.studio';

function read() {
  try { return JSON.parse(localStorage.getItem(KEY) || '{}') || {}; } catch (e) { return {}; }
}

const device = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
const saved = read();
const root = document.documentElement;

export const prefs = {
  lang: root.lang === 'en' ? 'en' : 'ar',
  theme: root.dataset.theme === 'dark' ? 'dark' : 'light',
  tz: saved.tz || device,
  chosenTheme: !!saved.theme,
};

/** Keeps one choice (`null` forgets it, so it follows the device again). */
export function remember(name, value) {
  const all = read();
  if (value == null) delete all[name]; else all[name] = value;
  try { localStorage.setItem(KEY, JSON.stringify(all)); } catch (e) { /* private mode: this visit only */ }
}

export function applyDocument() {
  root.lang = prefs.lang;
  root.dir = prefs.lang === 'ar' ? 'rtl' : 'ltr';
  root.dataset.theme = prefs.theme;
}
