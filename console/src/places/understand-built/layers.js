// S-36 the system in layers (M6.11), on layers.json: the broken critical boundaries in red first, then each boundary
// (what ships to the browser, endpoints and their guards, the data rules, where the business rules live, the
// boundaries between layers, operations, tests) with its findings and the reference's fix, the questions EAOS could not
// decide, the layers of the reference type with their files, and the endpoint table.
import { t, num, esc, code, sev, L, screen, data } from 'eaos';
import { tabs, facts, fold, loading, notMeasured, emptyView, where } from '../understand-kit/kit.js';

const NEEDS = ['layers', 'coverage'];
const said = f => L({ ar: f.ar, en: f.en });
const fixOf = f => L({ ar: f.fix_ar, en: f.fix_en });

const findingHTML = f => `<li class="row"><span class="row__main"><span class="row__title">${sev(f.severity, true)} ${esc(said(f))}</span>
  <span class="row__meta" style="display:block">${esc(t('un.layers.fix', { fix: fixOf(f) }))}</span>
  ${f.path && f.path !== '*' ? `<span class="small muted" style="display:block">${code(where(f.path, f.line))}${f.live ? ` <span class="tag tag--ok">${t('un.layers.tried')}</span>` : ''}</span>` : ''}</span></li>`;

const boundaryHTML = b => `<section class="panel un-area" data-boundary="${esc(b.id)}"><div class="un-area__head"><h2 class="h2">${esc(L(b.name))}</h2>
  ${b.findings.length ? `<span class="tag tag--you">${esc(t('un.layers.n', { n: num(b.findings.length) }))}</span>` : `<span class="tag tag--ok">${t('un.layers.sound')}</span>`}</div>
  ${b.findings.length ? `<ul class="rows">${b.findings.map(findingHTML).join('')}</ul>` : ''}</section>`;

function criticalHTML(d) {
  const high = d.boundaries.flatMap(b => b.findings).filter(f => f.severity === 'high');
  if (!high.length) return '';
  return `<div class="panel panel__pad un-critical" role="alert"><h2 class="h2">${t('un.layers.critical')}</h2>
    <ul class="un-doc__ul">${high.slice(0, 10).map(f => `<li>${sev('high')} ${esc(said(f))}</li>`).join('')}</ul></div>`;
}

const layersHTML = d => fold(t('un.layers.map'), esc(t('un.layers.map.sum', { placed: num(d.counts.placed.value), files: num(d.counts.files.value), gaps: num(d.counts.gaps.value) })),
  `<ul class="rows">${d.layers.map(l => `<li class="row"><span class="row__main"><span class="row__title">${code(l.name)} ${num(l.files)}</span>
    <span class="row__meta" style="display:block">${esc(l.responsibility || '')}</span></span></li>`).join('')}</ul>`);

const yes = v => (v ? esc(v) : `<span class="tag tag--you">${t('un.layers.none')}</span>`);
const endpointsHTML = d => fold(t('un.layers.endpoints'), esc(t('un.layers.endpoints.sum', { n: num(d.counts.endpoints.value) })),
  `<ul class="rows">${d.endpoints.map(e => `<li class="row"><span class="row__main"><span class="row__title">${code(`${e.method} ${e.route}`)}</span>
    <span class="row__meta" style="display:block">${t('un.layers.authn')}: ${yes(e.authentication)} · ${t('un.layers.authz')}: ${yes(e.authorisation)} · ${t('un.layers.valid')}: ${yes(e.validation)}</span>
    <span class="small muted" style="display:block">${code(where(e.path, e.line))}</span></span></li>`).join('')}</ul>`);

const questionsHTML = d => (d.questions.length ? `<section class="section"><h2 class="h2">${t('un.layers.questions')}</h2><ul class="un-doc__ul">${d.questions.map(q => `<li>${esc(L(q))}</li>`).join('')}</ul></section>` : '');

function layersPage(ctx) {
  if (ctx.state === 'empty') return emptyView('layers');
  const d = data.section('layers');
  if (!d) return notMeasured('layers', 'layers');
  return `<div class="page page--wide">
    ${tabs('layers')}
    <h1 class="lede">${t('un.layers.lede')}</h1>
    <p class="guide">${t(d.live ? 'un.layers.live' : 'un.layers.notlive')}</p>
    ${criticalHTML(d)}
    <div class="panel panel__pad">${facts([[t('un.layers.type'), code(d.type || '—')], [t('un.layers.findings'), num(d.counts.findings.value)], [t('un.layers.tables'), num(d.counts.tables.value)]])}</div>
    <div class="un-areas section" style="margin-top:20px">${d.boundaries.map(boundaryHTML).join('')}</div>
    ${questionsHTML(d)}
    <section class="section">${layersHTML(d)}${endpointsHTML(d)}</section>
  </div>`;
}
screen({ id: 'S-36', path: '/understand/layers', place: 'understand', needs: NEEDS, title: () => t('un.v.layers'), render: layersPage, loading: () => loading(t('un.layers.loading')) });
