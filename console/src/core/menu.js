// The project menu (SET-01, SET-02, PJS-01): language and theme, the project's own pages, the projects on this
// computer (live: GET /api/projects); and "Open it live", which any action of the read-only copy opens (OFF-02, OFF-03).
import { t, num } from './i18n.js';
import { esc, icon, fmtWhen } from './format.js';
import { href } from './address.js';
import { sheet, rerenderSheet } from './sheets.js';
import { client } from '../data/actions.js';
import { live } from '../data/store.js';
import { project } from '../data/model.js';
import { rowWords, displayToggles, titledBlock } from './parts.js';

let projects = null;

function row(ic, label, sub, path) {
  return `<a class="row" href="${href(path)}" data-act="go" data-href="${href(path)}">${icon(ic)}${rowWords(esc(label), sub ? esc(sub) : null)}${icon('chev', 'icon--sm icon--dir muted')}</a>`;
}

function assistantsSub() {
  const ready = (live.assistants || []).filter(a => a.installed && a.logged_in).map(a => a.name);
  if (!live.assistants) return t('proj.assistants.sub');
  return ready.length ? t('proj.assistants.ready', { names: ready.join(t('list.sep')) }) : t('proj.assistants.none');
}

function projectRows() {
  const here = project();
  const others = (projects || []).filter(p => !p.current);
  const mark = name => `<span class="project-btn__mark" aria-hidden="true">${esc((name || '?').slice(0, 1).toUpperCase())}</span>`;
  const score = s => (s == null ? t('proj.unchecked') : t('proj.score', { score: num(Math.round(s * 100)) }));
  const current = (projects || []).find(p => p.current);
  return `<div class="row">${mark(here.name)}${rowWords(esc(here.name), esc(t('proj.current')) + (current ? `, ${esc(score(current.score))}` : ''), { title: 'mono' })}${icon('check', 'muted')}</div>
    ${others.map(p => `<a class="row" href="${href('/open', { kind: 'switch', p: p.workspace })}" data-act="go" data-href="${href('/open', { kind: 'switch', p: p.workspace })}">${mark(p.name)}${rowWords(esc(p.name), esc(score(p.score)) + (p.checked ? `, ${esc(t('proj.checked', { when: fmtWhen(p.checked) }))}` : ''), { title: 'mono' })}${icon('chev', 'icon--sm icon--dir muted')}</a>`).join('')}
    ${row('folder', t('proj.new'), '', '/activity?sheet=launcher')}`;
}

sheet('project', {
  kind: 'menu',
  render() {
    return {
      title: esc(t('proj.title')),
      body: `
        <div class="toggles">${displayToggles('')}</div>
        ${titledBlock(t('proj.this'), `
          <div class="panel rows">
            ${row('branch', t('proj.branches'), t('proj.branches.sub', { branch: project().branch }), '/project/branches')}
            ${row('app', t('proj.app'), t('proj.app.sub'), '/project/app')}
            ${row('ai', t('proj.assistants'), assistantsSub(), '/project/assistants')}
            ${row('tool', t('proj.tools'), t('proj.tools.sub'), '/project/tools')}
            ${row('gear', t('proj.settings'), t('proj.settings.sub'), '/project/settings')}
          </div>`)}
        ${titledBlock(t('proj.others'), `<div class="panel rows">${projectRows()}</div>`)}`,
    };
  },
  after() {
    if (client && !projects) client.projects().then(list => { projects = list; rerenderSheet(); }, () => { projects = []; });
  },
});

/** The read-only copy: actions run in the live console only; how to open it, and the request for an assistant. */
sheet('open-live', {
  kind: 'dialog',
  render() {
    return {
      title: esc(t('offline.sheet.title')),
      body: `<p>${t('offline.sheet.body')}</p>
        <div class="code pad-3-4">eaos studio</div>
        <button class="btn btn--secondary" data-act="copy" data-text="eaos studio">${icon('copy')}${t('copy')}</button>
        <p>${t('offline.sheet.or')}</p>
        <div class="code pad-3-4 pre">${esc(t('offline.sheet.request'))}</div>
        <button class="btn btn--secondary" data-act="copy" data-text="${esc(t('offline.sheet.request'))}">${icon('copy')}${t('pv.copy')}</button>`,
    };
  },
});
