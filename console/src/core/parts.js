// The parts every screen draws the same way, written once (one source per pattern, docs/STANDARDS.md): a row's words,
// a switch and its row, a radio option, a list of facts, a section's head, the rows of a list still loading, the
// command for the terminal, a refusal, a place not found and the language and theme choices. Each returns markup; what
// differs is a parameter.
import { esc, icon } from './format.js';
import { t } from './i18n.js';
import { prefs } from './prefs.js';

const attrs = o => Object.entries(o).filter(([, v]) => v != null && v !== false).map(([k, v]) => (v === true ? k : `${k}="${esc(v)}"`)).join(' ');

/** A row's words: its title and, when given, the meta line under it. `o.title`: the title's extra classes; `o.meta`:
 *  the meta's own classes (a laid-out meta, ac-meta), else a meta line of its own; `o.more`: markup after them. */
export function rowWords(title, meta, o = {}) {
  const line = o.meta ? `<span class="row__meta ${o.meta}">` : '<span class="row__meta" style="display:block">';
  return `<span class="row__main"><span class="row__title${o.title ? ' ' + o.title : ''}">${title}</span>${meta ? `${line}${meta}</span>` : ''}${o.more || ''}</span>`;
}

/** A switch (a checkbox drawn as one): `input` its attributes ({name: value}, true for a bare one), `label` its name. */
export const switchBox = (input, label) => `<span class="switch"><input type="checkbox" ${attrs(input)} aria-label="${esc(label)}"><span class="switch__track"></span><span class="switch__thumb"></span></span>`;

/** A switch's row: its words (and the note under them), then the switch. `o.icon`: an icon before the words; `o.cls`:
 *  the row's extra classes. */
export function toggleRow(words, note, input, o = {}) {
  const head = o.icon ? `<span class="toggle-row__icon">${icon(o.icon, 'icon--sm')}${words}</span>` : note ? `<span style="display:block">${words}</span>` : words;
  return `<div class="toggle-row${o.cls ? ' ' + o.cls : ''}"><span>${head}${note ? `<span class="small muted">${note}</span>` : ''}</span>${switchBox(input, o.label || words)}</div>`;
}

/** One radio option: `input` its attributes ({name, value, 'data-change', ...; checked, disabled}), `text` its words,
 *  `note` the line under them. A disabled option is drawn off unless `off` says otherwise. */
export function radio(input, text, note, off) {
  const isOff = off != null ? off : input.disabled;
  return `<label class="opt${isOff ? ' opt--off' : ''}"><input type="radio" ${attrs(input)}><span class="opt__dot" aria-hidden="true"></span><span class="opt__text">${text}${note != null ? `<span class="opt__note">${note}</span>` : ''}</span></label>`;
}
/** An option's first line: a name, and a lock when it cannot be chosen. */
export const lockLine = (name, locked) => `<span class="opt__line">${name}${locked ? icon('lock', 'icon--sm muted') : ''}</span>`;

/** A list of facts: [term, value, the value's class] pairs (falsy ones left out); `cls` the list's extra classes. */
export const facts = (pairs, cls) => `<dl class="facts${cls ? ' ' + cls : ''}">${pairs.filter(Boolean).map(([k, v, c]) => `<dt>${k}</dt><dd${c ? ` class="${c}"` : ''}>${v}</dd>`).join('')}</dl>`;

/** A section: its head (a title, with `id` for the section to be named by, and a note beside it) and its body. */
export const titledSection = (id, title, body, note) => `<section class="section" aria-labelledby="${id}"><div class="section-head"><h2 id="${id}">${title}</h2>${note ? `<span class="small muted">${note}</span>` : ''}</div>${body}</section>`;

/** The rows of a list still being read: `n` rows of grey lines as wide as `widths` (%), each after a grey mark when
 *  `o.mark` names its kind (dot, square); `o.cls` the list's extra classes, `o.row` the row's class, `o.tag` the list's. */
export function skeletonRows(n, widths, o = {}) {
  const tag = o.tag || 'ul', row = tag === 'ul' ? 'li' : 'div';
  const lines = `<span class="skel-lines">${widths.map(w => `<span class="skel-line" style="width:${w}%"></span>`).join('')}</span>`;
  return `<${tag} class="panel rows${o.cls ? ' ' + o.cls : ''}">${Array.from({ length: n }, () => `<${row} class="${o.row || 'row'}">${o.mark ? `<span class="skel skel--${o.mark}"></span>` : ''}${lines}</${row}>`).join('')}</${tag}>`;
}

/** The command that does the same in a terminal, one press away. `pre`: its lines kept as they are. */
export const terminalFold = (command, pre) => `<details><summary class="link fold-link fold-link--icon">${icon('terminal', 'icon--sm')}${t('pv.terminal')}</summary><div class="code pad-3-4 mt-2${pre ? ' pre' : ''}">${command}</div></details>`;

/** A refusal: why it cannot be done (bold), then each reason on its own line (`cls` their classes, `small` alone). */
export const refusal = (why, lines, cls) => `<div class="ac-refuse" role="alert"><p><b>${why}</b></p>${lines.filter(Boolean).map(l => `<p class="${cls || 'small'}">${l}</p>`).join('')}</div>`;

/** A place that is not there (an old link, a name gone): its title, the guide, and where to go instead. */
export const notFound = (title, guide, go) => `<div class="panel empty mt-3"><h1 class="empty__title">${title}</h1><p class="small ink-2">${guide}</p>${go || ''}</div>`;

/** The language and the theme, each a segmented choice in its row (the project menu and Settings); `fk` keeps each
 *  one's focus keys its own. */
const prefSeg = (label, buttons) => `<div class="toggle-row"><span>${label}</span><div class="seg" role="group" aria-label="${esc(label)}" style="min-width:180px">${buttons}</div></div>`;
export const displayToggles = fk => `${prefSeg(t('lang.label'), ['ar', 'en'].map(l => `<button type="button" data-act="lang" data-lang="${l}" data-fk="${fk}lang-${l}" aria-pressed="${prefs.lang === l}" lang="${l}">${t('lang.' + l)}</button>`).join(''))}
  <p class="muted small">${t('lang.note')}</p>
  ${prefSeg(t('theme.label'), [['light', 'l', 'sun'], ['dark', 'd', 'moon']].map(([th, k, ic]) => `<button type="button" data-act="theme-set" data-theme="${th}" data-fk="${fk}th-${k}" aria-pressed="${prefs.theme === th}">${icon(ic, 'icon--sm')}${t('theme.' + th)}</button>`).join(''))}`;

/** A small fold inside a card or a panel: an icon, its title, and its body. `o.cls`: the fold's extra classes, `o.body`:
 *  the body's, `o.attrs`: its own attributes (open, data-*). */
export const smallFold = (ic, title, body, o = {}) => `<details class="fold${o.cls ? ' ' + o.cls : ''}"${o.attrs ? ' ' + o.attrs : ''}><summary>${icon(ic, 'muted')}<span class="row__main small">${title}</span>${icon('chev', 'chev icon--sm')}</summary>
    <div class="fold__body${o.body ? ' ' + o.body : ''}">${body}</div></details>`;
