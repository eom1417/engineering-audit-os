// The report for people (REPORT.html) inside the page: the very page EAOS built (eaos/report/human_report), never
// drawn a second time. It is read by a one-use address (/api/report-ticket, then /report/<ticket>) into a frame
// sandboxed to its own scripts, in the person's language (?lang=); the same page also opens in a tab. The read-only
// copy has no server to read it from: it says so.
import { t, esc, icon, prefs, data, offline } from 'eaos';
import { nm } from '../kit/kit.js';

export function humanPart() {
  if (offline()) return nm(t('rp.human.offline'), t('un.files.offline.why'));
  return `<div class="actions"><button class="btn btn--secondary btn--sm" data-act="un-openreport">${icon('external')}${t('un.files.open')}</button></div>
    <div class="rp-frame"><p class="small muted" role="status" aria-busy="true" data-rp-wait>${t('rp.human.reading')}</p>
      <div hidden data-rp-none>${nm(t('rp.human.none'), t('rp.human.none.why'))}</div>
      <iframe title="${esc(t('rp.human.title'))}" sandbox="allow-scripts allow-modals" referrerpolicy="no-referrer" hidden data-rp-frame></iframe></div>`;
}

/** Asks for the page's address once the frame is drawn; a page not built yet says so in its place. */
export function humanAfter(main) {
  const frame = main.querySelector('[data-rp-frame]');
  if (!frame) return;
  data.reportPage().then(url => {
    if (!frame.isConnected) return;
    main.querySelector('[data-rp-wait]').remove();
    if (!url) { main.querySelector('[data-rp-none]').hidden = false; return; }
    frame.src = `${url}?lang=${prefs.lang}`;
    frame.hidden = false;
  });
}
