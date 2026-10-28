// S-17 The report (M8.2): what a check found, on one page in four parts, each its own address (?part=): the report
// for people (REPORT.html, eaos/report/human_report: summary, gaps, layers, structure, system, target, plan) as EAOS
// built it, in a frame of its own; the pictures of the app's screens the check took, with their findings on them;
// the report's files, each read as text or downloaded; and the users' experience (M10.8, experience/story.json).
// Understand's old addresses land here (core/router.js landOld).
import { t, screen, prefs, pageHead } from 'eaos';
import { seg, empty, loading } from '../kit/kit.js';
import { humanPart, humanAfter } from './human.js';
import { screensPart, SCREENS_NEEDS } from './screens.js';
import { filesPart } from './files.js';
import { experiencePart } from './experience.js';

const PARTS = {
  report: { draw: humanPart, needs: [] },
  screens: { draw: screensPart, needs: SCREENS_NEEDS },
  files: { draw: filesPart, needs: [] },
  experience: { draw: experiencePart, needs: [] },
};
const partOf = query => (PARTS[query.part] ? query.part : 'report');

function reportPage(ctx) {
  if (ctx.state === 'empty') return empty(t('rp.empty'), t('rp.empty.guide'));
  const part = partOf(ctx.query);
  return `<div class="page page--wide rp">
    ${pageHead(t('rp.lede'), t('rp.guide'))}
    <div class="section">${seg('part', Object.keys(PARTS).map(p => [p, t('rp.part.' + p)]), part, t('rp.parts'), { dflt: 'report' })}</div>
    <section class="section" aria-label="${t('rp.part.' + part)}">${PARTS[part].draw(ctx)}</section>
  </div>`;
}

screen({
  id: 'S-17', path: '/report', place: 'report', needs: ctx => PARTS[partOf(ctx.query)].needs, title: () => t('nav.report'),
  render: reportPage, after: (main, ctx) => { if (partOf(ctx.query) === 'report') humanAfter(main); },
  steady: ctx => partOf(ctx.query) === 'report' ? `report:${prefs.lang}` : '',   // the frame is not read again on each live update
  loading: () => loading(t('rp.lede'), 4),
});
