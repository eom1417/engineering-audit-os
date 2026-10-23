// S-42 the report files (LIB-07): the report's text files (up to 400, the report_file action) and one read as text
// (?sheet=file:<path>: at most 2 MB, never rendered); the full report for people (REPORT.html) opened on this computer
// through the open_report action.
import { t, num, esc, icon, code, href, screen, sheet, act, data, refresh, client, toast, closeSheetThen, offline, ActionError } from 'eaos';
import { tabs, search, count, nm, enc, loading, emptyView, matches, page } from '../understand-kit/kit.js';
import { read } from '../understand-kit/reads.js';

const texts = new Map();
/** A report file's text: read once (GET /api/report-file), null while it is read, false when it cannot be. */
function text(path) {
  if (!texts.has(path)) {
    texts.set(path, null);
    data.reportFile(path).then(s => { texts.set(path, s == null ? false : s); refresh(); });
  }
  return texts.get(path);
}

function filesPage(ctx) {
  if (ctx.state === 'empty') return emptyView('report-files');
  const q = ctx.query;
  const got = read('report_file', {});
  const all = got.state === 'ready' ? (got.answer || {}).files || [] : [];
  const files = q.q ? all.filter(f => matches(f, q.q)) : all;
  const pg = page(files, f => `<button class="row" data-act="sheet" data-sheet="file:${esc(enc(f))}" style="width:100%">${icon('file', 'muted')}<span class="row__main">${code(f)}</span>${icon('chev', 'icon--sm icon--dir muted')}</button>`);
  const list = got.state === 'offline' ? nm(t('un.files.offline'), t('un.files.offline.why'))
    : got.state === 'loading' ? `<p class="small muted" role="status" aria-busy="true">${t('un.files.reading')}</p>`
      : got.state === 'failed' ? `<p class="small" role="alert">${icon('warn', 'icon--sm')} ${esc(got.error || '')}</p>`
        : `<div class="listhead">${count(pg.shown, files.length)}</div>${files.length ? `<div class="panel rows">${pg.html}</div>${pg.more}` : `<div class="panel empty"><p class="empty__title">${t('un.files.none')}</p></div>`}`;
  return `<div class="page">
    ${tabs('report-files')}
    <h1 class="lede">${esc(got.state === 'ready' ? t('un.files.lede.v', { n: num(all.length) }) : t('un.v.report-files'))}</h1>
    <p class="guide">${t('un.files.guide')}</p>
    <div class="actions"><button class="btn btn--primary" data-act="sheet" data-sheet="${offline() ? 'open-live' : 'file:REPORT.html'}">${icon('external')}${t('un.files.full')}</button>
      <a class="btn btn--quiet" href="${href('/status')}">${t('un.files.live')}</a></div>
    <div class="ptools">${search(q.q, t('un.files.search'))}</div>
    ${list}
  </div>`;
}
screen({ id: 'S-42', path: '/understand/report-files', place: 'understand', title: () => t('un.v.report-files'), render: filesPage, loading: () => loading(t('un.files.reading')) });

sheet('file', {
  kind: 'drawer',
  render(arg) {
    const name = decodeURIComponent(arg);
    if (name === 'REPORT.html') {
      return { title: esc(t('un.files.full')), body: `<p>${t('un.files.full.does')}</p>`,
        foot: `<button class="btn btn--primary btn--block" data-act="un-openreport" ${offline() ? 'disabled' : ''}>${icon('external')}${t('un.files.open')}</button>` };
    }
    const s = offline() ? false : text(name);
    const body = s === null ? `<p class="small muted" aria-busy="true">${t('un.files.reading')}</p>`
      : s === false ? nm(t('un.files.unread'), t(offline() ? 'un.files.offline.why' : 'un.files.unread.why'))
        : `<p class="small ink-2">${t('un.files.astext')}</p><pre class="code un-pre" tabindex="0">${esc(s.length > 200000 ? s.slice(0, 200000) : s)}</pre>${s.length > 200000 ? `<p class="small caution-ic">${t('un.files.cut')}</p>` : ''}`;
    return { title: code(name), body, foot: `<button class="btn btn--quiet btn--block" data-act="copy" data-text="${esc(name)}">${icon('copy')}${t('un.files.copypath')}</button>` };
  },
});
act('un-openreport', async el => {
  if (!client) return;
  el.disabled = true;
  const tab = window.open('', '_blank');        // in the click itself: a tab opened after an await is a blocked pop-up
  try {
    await client.start({ action: 'open_report', inputs: { show: false } });   // rebuilt with the fixes so far; opened here, never on the server
    const url = await data.reportPage();
    if (!url) throw new Error(t('un.files.unread'));
    tab.location = url;
    closeSheetThen(() => toast(t('un.files.opened')));
  } catch (e) { if (tab) tab.close(); el.disabled = false; toast(e instanceof ActionError ? e.message : String(e), { refusal: true }); }
});
