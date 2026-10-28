// The report's files (LIB-07): the report's text files (up to 400, the report_file action), each read as text in its
// sheet (?sheet=file:<path>: at most 2 MB, never rendered) and downloaded from there; the report for people
// (REPORT.html) opened in a tab of this browser through the open_report action.
import { said, t, num, esc, icon, code, sheet, act, data, refresh, client, toast, closeSheetThen, offline } from 'eaos';
import { search, count, nm, enc, matches, page } from '../kit/kit.js';
import { read } from '../kit/reads.js';

const texts = new Map();
/** A report file's text: read once (GET /api/report-file), null while it is read, false when it cannot be. */
function text(path) {
  if (!texts.has(path)) {
    texts.set(path, null);
    data.reportFile(path).then(s => { texts.set(path, s == null ? false : s); refresh(); });
  }
  return texts.get(path);
}

function fileList(got, q) {
  if (got.state === 'offline') return nm(t('un.files.offline'), t('un.files.offline.why'));
  if (got.state === 'loading') return `<p class="small muted" role="status" aria-busy="true">${t('un.files.reading')}</p>`;
  if (got.state === 'failed') return `<p class="small" role="alert">${icon('warn', 'icon--sm')} ${esc(got.error || '')}</p>`;
  const all = (got.answer || {}).files || [];
  const files = q.q ? all.filter(f => matches(f, q.q)) : all;
  const pg = page(files, f => `<button class="row" data-act="sheet" data-sheet="file:${esc(enc(f))}" style="width:100%">${icon('file', 'muted')}<span class="row__main">${code(f)}</span>${icon('chev', 'icon--sm icon--dir muted')}</button>`);
  return `<p class="small ink-2">${esc(t('un.files.lede.v', { n: num(all.length) }))} ${t('un.files.guide')}</p>
    <div class="ptools">${search(q.q, t('un.files.search'))}</div>
    <div class="listhead">${count(pg.shown, files.length)}</div>${files.length ? `<div class="panel rows">${pg.html}</div>${pg.more}` : `<div class="panel empty"><p class="empty__title">${t('un.files.none')}</p></div>`}`;
}

export const filesPart = ctx => fileList(read('report_file', {}), ctx.query);

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
    const save = typeof s === 'string' ? `<button class="btn btn--secondary btn--block" data-act="rp-download" data-name="${esc(name)}">${icon('file')}${t('rp.files.download')}</button>` : '';
    return { title: code(name), body, foot: `${save}<button class="btn btn--quiet btn--block" data-act="copy" data-text="${esc(name)}">${icon('copy')}${t('un.files.copypath')}</button>` };
  },
});
// the text already read, saved under the file's own name: nothing is asked of the server again
act('rp-download', el => {
  const name = el.dataset.name, s = texts.get(name);
  if (typeof s !== 'string') return;
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([s], { type: 'text/plain;charset=utf-8' }));
  a.download = name.split('/').pop();
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
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
  } catch (e) { if (tab) tab.close(); el.disabled = false; toast(said(e), { refusal: true }); }
});
