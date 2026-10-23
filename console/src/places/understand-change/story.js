// S-18 the story (PLN-01, PLN-10, PLN-13): today, the change and the target in three parts (story.json), the
// indicators, the gaps with the most to do; its Bridge tab draws how today's components flow into the target's
// (system.json), with the list beside it as its twin. A check with no target picture says so (not measured).
import { t, tn, L, num, esc, icon, code, href, rich, screen, data } from 'eaos';
import { tabs, seg, prov, nm, glyph, opTag, opOf, flow, enc, loading, checkBtn, q, notMeasured, opBar, readout, empty } from '../understand-kit/kit.js';
import { storyCounts, targetDecision, components, targets } from '../understand-kit/model.js';
import { gapRow } from './gaps.js';

const NEEDS = ['story', 'system', 'gaps', 'cards', 'coverage'];
const FOLD = 24;

function bridge() {
  const comps = components().filter(c => c.target), all = targets();
  if (!all.length) return nm(t('un.bridge.nm'), t('un.bridge.nm.why'), checkBtn());
  const tOrder = id => all.findIndex(x => x.id === id);
  const sorted = comps.slice().sort((a, b) => (tOrder(a.target) - tOrder(b.target)) || (b.files - a.files));
  // past FOLD rows the smallest gather in one "other" source per target (PLN-10)
  const keep = new Set(comps.slice().sort((a, b) => b.files - a.files).slice(0, FOLD - 1).map(c => c.id));
  const left = [], links = [];
  sorted.forEach(c => {
    if (keep.has(c.id) || comps.length <= FOLD) {
      left.push({ id: c.id, label: c.short || c.id, mono: true, n: c.files, glyph: glyph(c.op, 16), cls: 'flow__node--' + opOf(c.op), tip: `${c.id}: ${t('un.op.' + opOf(c.op))} → ${c.target}, ${tn('pl.file', c.files)}` });
      links.push([c.id, c.target, c.files, opOf(c.op), `${c.id} → ${c.target}: ${t('un.op.' + opOf(c.op))}, ${tn('pl.file', c.files)}`]);
    } else {
      let other = left.find(x => x.id === '\u0000other');
      if (!other) { other = { id: '\u0000other', label: t('un.bridge.other'), n: 0, folded: 0 }; left.push(other); }
      other.n += c.files; other.folded += 1;
      other.tip = t('un.bridge.other.tip', { n: tn('un.pl.comp', other.folded), files: tn('pl.file', other.n) });
      const l = links.find(x => x[0] === other.id && x[1] === c.target);
      if (l) l[2] += c.files; else links.push([other.id, c.target, c.files, null, `${t('un.bridge.other')} → ${c.target}`]);
    }
  });
  const right = all.map(x => ({ id: x.id, label: x.short || x.id, mono: true, n: x.files, cls: (x.sources || []).length ? '' : 'flow__node--new', tip: `${x.id}: ${L(x.responsibility || '')}` }));
  const svg = flow(left, right, links, { leftTitle: t('un.story.today'), rightTitle: t('un.story.target'), label: t('un.bridge.svg') });
  const list = all.map(x => {
    const src = components().filter(c => c.target === x.id).sort((a, b) => b.files - a.files);
    return `<section class="panel un-bt">
      <div class="un-bt__head"><span class="un-bt__title">${code(x.id)}${(x.sources || []).length ? '' : `<span class="tag tag--state">${glyph('introduce')}${t('un.op.introduce')}</span>`}</span><span class="small muted">${x.layer ? esc(t('un.layer', { layer: x.layer })) + t('list.sep') : ''}${esc(tn('pl.file', x.files))}</span></div>
      ${x.responsibility ? `<p class="small ink-2">${rich(L(x.responsibility))}</p>` : ''}
      ${src.length ? `<ul class="rows un-bt__src">${src.map(c => `<li><a class="row" href="${href('/understand/gaps/' + enc(c.id))}">${code(c.id)}<span class="row__main"></span>${opTag(c.op, true)}<span class="small muted num">${esc(tn('pl.file', c.files))}</span></a></li>`).join('')}</ul>`
        : `<p class="small muted">${t('un.bridge.nosrc')}</p>`}
    </section>`;
  }).join('');
  const removed = components().filter(c => !c.target);
  return `${svg}
    <div class="section-head" style="margin-top:24px"><h2>${t('un.bridge.list')}</h2></div>
    <div class="un-bts">${list}</div>
    ${removed.length ? `<div class="panel rows" style="margin-top:12px">${removed.map(c => `<a class="row" href="${href('/understand/gaps/' + enc(c.id))}">${code(c.id)}<span class="row__main small muted">${t('un.bridge.deleted')}</span>${opTag('delete', true)}</a>`).join('')}</div>` : ''}`;
}

function indicators(story) {
  const rows = story.indicators || [];
  if (!rows.length) return `<p class="small muted">${t('un.ind.nm')}</p>`;
  const v = x => (x == null ? `<span class="muted">${t('un.ind.none')}</span>` : esc(String(x)));
  return `<div class="panel un-table-wrap"><table class="un-table"><thead><tr><th scope="col">${t('un.ind.what')}</th><th scope="col">${t('un.ind.today')}</th><th scope="col">${t('un.ind.expected')}</th><th scope="col">${t('un.ind.target')}</th></tr></thead>
    <tbody>${rows.map(i => `<tr><th scope="row">${esc(L(i.name || i.title || i.id || ''))}</th><td class="num">${v(i.today)}</td><td class="num">${v(i.expected)}</td><td class="num">${v(i.target)}</td></tr>`).join('')}</tbody></table></div>
    <p class="small muted" style="margin-top:8px">${t('un.ind.note')}</p>`;
}

function storyPage(ctx) {
  if (ctx.state === 'empty') return empty(t('un.story.empty'), t('un.story.empty.guide'), tabs('story'));
  const story = data.section('story');
  if (!story) return notMeasured('story', 'story');
  const c = storyCounts(), d = targetDecision();
  const tab = q().tab === 'bridge' ? 'bridge' : 'story';
  const tabsSeg = seg('tab', [['story', t('un.story.tab.story')], ['bridge', t('un.story.tab.bridge')]], tab, t('un.v.story'), { dflt: 'story', cls: 'un-seg2' });
  const gaps = ((data.section('gaps') || {}).gaps || []).filter(g => opOf(g.operation) !== 'retain').sort((a, b) => b.cards.length - a.cards.length || b.files - a.files);
  const body = tab === 'bridge' ? bridge() : `
    <div class="un-three">
      <div class="un-three__p"><h2 class="un-story__h">${t('un.story.today')}</h2><p>${esc(t('un.story.today.sum', { n: tn('un.pl.comp', c.today) }))}</p>
        ${story.current.summary ? `<p class="small muted">${rich(L(story.current.summary))}</p>` : ''}
        <a class="link small" href="${href('/understand/components')}">${t('un.story.open.today')}</a></div>
      <div class="un-three__p"><h2 class="un-story__h">${t('un.story.change')}</h2>${opBar(c.ops, true)}
        <a class="link small" href="${href('/understand/components', { mode: 'change' })}">${t('un.story.open.change')}</a></div>
      <div class="un-three__p"><h2 class="un-story__h">${t('un.story.target')}</h2><p>${esc(t('un.story.target.sum', { n: tn('un.pl.comp', c.target) }))}</p>
        ${story.target.summary ? `<p class="small muted">${rich(L(story.target.summary))}</p>` : ''}
        <a class="link small" href="${href('/understand/components', { mode: 'target' })}">${t('un.story.open.target')}</a></div>
    </div>
    <section class="section" aria-labelledby="ind-h"><div class="section-head"><h2 id="ind-h">${t('un.ind.title')}</h2></div>${indicators(story)}</section>
    <section class="section" aria-labelledby="gpc-h"><div class="section-head"><h2 id="gpc-h">${t('un.story.gaps')}</h2><a class="link" href="${href('/understand/gaps')}">${esc(t('un.story.gaps.all', { n: num(((data.section('gaps') || {}).gaps || []).length) }))}</a></div>
      ${gaps.length ? `<div class="panel rows">${gaps.slice(0, 8).map(gapRow).join('')}</div>` : `<p class="small muted">${t('un.gaps.nochange')}</p>`}</section>`;
  return `<div class="page page--wide">
    ${tabs('story')}
    <h1 class="lede">${esc(t('un.story.lede', { today: tn('un.pl.comp', c.today), target: num(c.target), change: num(c.change) }))}</h1>
    <p class="guide">${t(d === 'approved' ? 'un.story.guide.ok' : 'un.story.guide')}</p>
    <div class="actions"><a class="btn btn--primary" href="${href('/understand/components', { mode: 'change' })}">${t('un.story.act')}</a>
      ${d === 'waiting' ? `<a class="btn btn--quiet" href="${href('/waiting/target-architecture')}">${icon('seal', 'icon--sm')}${t('un.story.answer')}</a>` : ''}</div>
    ${prov(story.provenance)}
    <div style="margin-top:24px">${tabsSeg}</div>
    <div class="un-body">${body}</div>
  </div>`;
}
screen({ id: 'S-18', path: '/understand/story', place: 'understand', needs: NEEDS, title: () => t('un.v.story'), render: storyPage,
  loading: () => loading(t('un.story.loading')), after: readout });
