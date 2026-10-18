// S-17 Understand (PLN-01): the story card on top (today, the change, the target), then the four groups with each
// view and its count. The counts come from the coverage rows, so the door never reads a large section to count it; a
// section the check did not write says "not measured".
import { t, num, esc, icon, href, screen, data } from 'eaos';
import { GROUPS, vkey, row, loading, empty, opBar } from '../understand-kit/kit.js';
import { storyCounts, targetDecision, covered } from '../understand-kit/model.js';

const NEEDS = ['coverage', 'story', 'system'];
const SECTION = { gaps: 'gaps', operations: 'operations', ideal: 'ideal', 'ai-decisions': 'nodes', components: 'system', paths: 'paths', functions: 'functions',
  data: 'data_paths', unseen: 'hidden', infra: 'infra', pipelines: 'pipeline', screens: 'screens', 'screens/all': 'journeys', journeys: 'journeys',
  library: 'docs', 'report-files': null, history: 'history', story: 'story', architecture: null };
const VICON = { story: 'book', gaps: 'layers', operations: 'layers', ideal: 'ai', 'ai-decisions': 'ai', components: 'map', paths: 'code', functions: 'code', data: 'folder',
  unseen: 'screen', infra: 'app', pipelines: 'activity', architecture: 'layers', screens: 'screen', 'screens/all': 'screen', journeys: 'map', library: 'book', 'report-files': 'file', history: 'history' };
function storyCard() {
  const c = storyCounts(), d = targetDecision();
  if (c.today == null) return '';
  return `<div class="panel un-story">
    <div class="un-story__part"><h3 class="un-story__h">${t('un.story.today')}</h3><p><b class="num">${num(c.today)}</b> ${esc(t('un.story.today.n'))}</p></div>
    <div class="un-story__part un-story__part--change"><h3 class="un-story__h">${t('un.story.change')}</h3>${opBar(c.ops, true)}</div>
    <div class="un-story__part"><h3 class="un-story__h">${t('un.story.target')}</h3><p><b class="num">${num(c.target)}</b> ${esc(c.introduced ? t('un.story.target.v', { n: num(c.introduced) }) : t('un.story.target.n'))}</p>
      ${d === 'approved' ? `<span class="tag tag--ok">${icon('check')}${t('un.story.approved')}</span>` : d === 'waiting' ? `<a class="tag tag--you" href="${href('/waiting/target-architecture')}">${icon('seal')}${t('un.story.proposed')}</a>` : ''}</div>
  </div>`;
}

function indexPage(ctx) {
  if (ctx.state === 'empty') return empty(t('un.idx.empty'), t('un.idx.empty.guide'));
  const groups = GROUPS.map(g => `<section class="un-group" aria-labelledby="ug-${g.id}">
      <h2 class="un-group__h" id="ug-${g.id}">${t('nav.u.' + g.id)}</h2>
      <div class="panel rows">${g.views.map(v => {
        const c = SECTION[v] ? covered(SECTION[v]) : null;
        const n = v === 'components' ? ((data.section('system') || {}).counts || {}).components : null;
        if (c && n) c.n = n.value;
        const end = !c ? '' : c.state === 'not_measured' || c.state === 'failed' ? `<span class="tag tag--nm">${t('nm')}</span>` : c.n != null && v !== 'story' ? `<span class="num">${num(c.n)}</span>` : '';
        return row(href('/understand/' + v), VICON[v], t('un.v.' + vkey(v)), t('un.vs.' + vkey(v)), end);
      }).join('')}</div></section>`).join('');
  return `<div class="page page--wide un-index">
    <h1 class="lede">${t('un.idx.lede')}</h1>
    <p class="guide">${t('un.idx.guide')}</p>
    <div class="actions"><a class="btn btn--primary" href="${href('/understand/story')}">${t('un.idx.start')}</a></div>
    <section class="section" aria-label="${esc(t('un.v.story'))}">${storyCard()}</section>
    <div class="un-groups">${groups}</div>
  </div>`;
}
screen({ id: 'S-17', path: '/understand', place: 'understand', needs: NEEDS, title: () => t('nav.understand'), render: indexPage,
  loading: () => loading(t('un.idx.loading'), 6) });
