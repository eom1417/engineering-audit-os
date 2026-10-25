// S-08 the plan (PLN-02, PLN-04, FIX-15, BLD-03), S-10 waves (PLN-06), S-09 one step (PLN-03, PLN-05, SEL-01): a
// second view of Problems, on the report's plans (plans.json), its cards and the plan's timeline (paths.json
// `timeline`: the waves, and what each task waits for). Fixing a step opens the one Fix preview over that step
// (`verb:fix:step:<id>`, the server resolves its open problems). States: loading, empty (no check), not measured
// (no waves), offline (every action opens "Open it live").
import {
  t, tn, L, num, esc, icon, code, sev, chk, rich, href, screen, act, tickAct, refresh, parseHash, toast, announce, setSelbar, offline,
  model, selection, data,
} from 'eaos';
import { loading, nm, fold, facts, prow, enc, back, empty, ticks, page, opLinks } from '../understand-kit/kit.js';
import { buildPage } from './build.js';

const NEEDS = ['plans', 'cards', 'paths', 'operations', 'history'];
const title = s => ticks(rich(L(s.title || s.id)));
const timeline = () => (data.section('paths') || {}).timeline || null;

/** Step B waits for step A when a task of B waits for a task of A (a prerequisite, or an earlier task on the same
 *  file); `n` counts the waiting tasks of B. */
function stepLinks() {
  const tl = timeline();
  if (!tl) return [];
  const step = new Map(tl.tasks.map(x => [x.id, x.step]));
  const out = new Map();
  for (const task of tl.tasks) {
    for (const w of task.waits) {
      const from = step.get(w.task);
      if (!from || !task.step || from === task.step) continue;
      const key = from + '\u0001' + task.step;
      if (!out.has(key)) out.set(key, new Set());
      out.get(key).add(task.id);
    }
  }
  return [...out].map(([key, ids]) => ({ from: key.split('\u0001')[0], to: key.split('\u0001')[1], n: ids.size }));
}

/** The plan's steps with what each waits for, what holds it (a decision that blocks it, its fix waiting for the
 *  owner's Accept), its tasks as problems and its waves. */
function steps() {
  const links = stepLinks();
  const tl = timeline();
  const decisions = model.waitingDecisions();
  const waiting = model.waitingBranches();
  return model.plan().steps.map(s => {
    const ids = s.tasks.map(x => x.id);
    const span = tl && tl.steps.find(x => x.id === s.id);
    const review = waiting.find(run => (run.cards || []).some(id => ids.includes(id)));
    return Object.assign({}, s, {
      ids, waits: links.filter(l => l.to === s.id).map(l => [l.from, l.n]),
      decision: decisions.find(d => (d.blocks || []).includes(s.id)) || null,
      review: review ? review.id : null,
      first: span ? span.first : null, last: span ? span.last : null,
    });
  });
}
const openIds = s => s.ids.filter(id => { const p = model.problem(id); return p && p.state === 'open'; });

/** The next step (FIX-15): the first step not done, not held, with open problems, whose waited-for steps are done. */
function nextStep(all) {
  const done = new Set(all.filter(s => s.state === 'done').map(s => s.id));
  return all.find(s => !done.has(s.id) && s.state !== 'blocked' && !s.decision && !s.review && openIds(s).length && s.waits.every(w => done.has(w[0])));
}
function stateTag(st) {
  const cls = st === 'done' ? 'tag--ok' : st === 'active' ? 'tag--live' : st === 'blocked' ? 'tag--caution' : st === 'regressed' ? 'tag--danger' : 'tag--state';
  return `<span class="tag ${cls}">${st === 'blocked' ? icon('lock') : st === 'done' ? icon('check') : ''}${t('un.pst.' + (['todo', 'active', 'done', 'blocked', 'regressed'].includes(st) ? st : 'todo'))}</span>`;
}

/** What a task waits for (PLN-05): another task that must be fixed first, or an earlier one on the same file. */
function waitText(id, plain) {
  const tl = timeline();
  const task = tl && tl.tasks.find(x => x.id === id);
  const w = task && task.waits[0];
  if (!w) return esc(t(task ? 'un.task.free' : 'un.task.nowave'));
  const link = plain ? code(w.task) : `<a class="link" href="${href('/problems/' + enc(w.task))}">${code(w.task)}</a>`;
  const more = task.waits.length > 1 ? ` ${esc(t('un.comp.andmore', { n: num(task.waits.length - 1) }))}` : '';
  return (w.why === 'same_file' ? t('un.task.file', { id: link, file: code(w.detail || '') }) : t('un.task.prereq', { id: link })) + more;
}
function fixBtn(s, cls, label) {
  if (offline()) return `<button class="btn ${cls}" data-act="sheet" data-sheet="open-live">${esc(label)}</button>`;
  if (!openIds(s).length) return `<button class="btn ${cls}" disabled title="${esc(t('un.step.noopen'))}">${esc(label)}</button>`;
  return `<button class="btn ${cls}" data-act="sheet" data-sheet="verb:fix:step:${esc(s.id)}">${esc(label)}</button>`;
}
const planSeg = () => `<div class="context"><div class="seg" role="group" aria-label="${esc(t('pb.place'))}" style="min-width:200px">
    <a href="${href('/problems')}">${t('pb.view.list')}</a><a href="${href('/problems/plan')}" aria-current="true">${t('pb.view.plan')}</a></div></div>`;

/* ---------------- S-08 the plan ---------------- */
/** Layers of the step graph: a step sits one layer after the latest step it waits for, in the plan's order. */
function layers(all) {
  const memo = new Map();
  const depth = (s, seen) => {
    if (memo.has(s.id)) return memo.get(s.id);
    if (seen.has(s.id)) return 0;
    const next = new Set(seen).add(s.id);
    const d = Math.max(-1, ...s.waits.map(w => { const o = all.find(x => x.id === w[0]); return o ? depth(o, next) : -1; })) + 1;
    memo.set(s.id, d);
    return d;
  };
  const out = [];
  all.forEach(s => { const d = depth(s, new Set()); (out[d] = out[d] || []).push(s.id); });
  return out.filter(Boolean);
}
function depsSVG(all) {
  const cols = layers(all), pos = {};
  cols.forEach((c, ci) => c.forEach((id, ri) => { pos[id] = { x: 20 + ci * 150, y: 30 + ri * 74 }; }));
  const w = Math.max(760, 40 + cols.length * 150), h = 40 + Math.max(...cols.map(c => c.length)) * 74;
  const links = all.flatMap(s => s.waits.filter(wt => pos[wt[0]]).map(wt => {
    const a = pos[wt[0]], b = pos[s.id];
    const x1 = a.x + 110, y1 = a.y + 22, x2 = b.x, y2 = b.y + 22;
    return `<path d="M${x1} ${y1}C${(x1 + x2) / 2} ${y1} ${(x1 + x2) / 2} ${y2} ${x2} ${y2}" class="un-dep__link" marker-end="url(#dep-arrow)"/>
      <text x="${(x1 + x2) / 2}" y="${(y1 + y2) / 2 - 6}" class="un-dep__n">${num(wt[1])}</text>`;
  })).join('');
  const nodes = all.map(s => `<a href="${href('/problems/plan/' + enc(s.id))}" class="un-dep__node un-dep__node--${esc(s.state)}" aria-label="${esc(s.id + ': ' + t('un.pst.' + s.state))}">
    <rect x="${pos[s.id].x}" y="${pos[s.id].y}" width="110" height="44" rx="8"/><text x="${pos[s.id].x + 12}" y="${pos[s.id].y + 20}" class="un-dep__id">${esc(s.id)}</text>
    <text x="${pos[s.id].x + 12}" y="${pos[s.id].y + 36}" class="un-dep__s">${esc(t('un.pst.' + s.state))}</text><title>${esc(s.id + ': ' + L(s.title))}</title></a>`).join('');
  return `<div class="panel un-deps only-desk"><svg viewBox="0 0 ${w} ${h}" role="group" aria-label="${esc(t('un.plan.deps.svg'))}"><defs><marker id="dep-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0L10 5L0 10z" class="un-dg__arrow"/></marker></defs>${links}${nodes}</svg>
    <p class="small muted">${t('un.plan.deps.hint')}</p></div>`;
}
function stepRow(s, next) {
  let waits;
  if (s.review) waits = `<a class="link" href="${href('/waiting/' + enc(s.review))}">${t('un.step.review')}</a>`;
  else if (s.decision) waits = `${t('un.step.waitsdecision')} <a class="link" href="${href('/waiting/' + enc(s.decision.id))}">${rich(L(s.decision.question))}</a>`;
  else waits = s.waits.length ? esc(t('un.step.waits', { list: s.waits.map(w => t('un.step.waits.one', { id: w[0], n: tn('pl.problem', w[1]) })).join(t('list.sep')) })) : t('un.step.free');
  const open = openIds(s).length;
  return `<li class="un-steprow ${s === next ? 'un-steprow--next' : ''}">
    <span class="un-num num" aria-hidden="true">${esc(s.id)}</span>
    <div class="row__main">
      <a class="un-steprow__title" href="${href('/problems/plan/' + enc(s.id))}">${title(s)}</a>
      <div class="un-steprow__meta">${stateTag(s.state)}${s === next ? `<span class="tag tag--you">${t('un.plan.nexttag')}</span>` : ''}${s.sub_plan ? `<span class="tag tag--state">${t('un.plan.sub')}</span>` : ''}<span class="small muted">${esc(tn('pl.problem', s.ids.length))}${t('list.sep')}${esc(t('un.plan.open', { n: num(open) }))}</span></div>
      <p class="small ink-2" style="margin-top:4px">${waits}</p>
    </div>
    <div class="un-steprow__end">${s.state === 'blocked' || s.review || s.decision ? '' : fixBtn(s, 'btn--secondary btn--sm', t('verb.fix'))}</div>
  </li>`;
}
function plansFold() {
  const plans = (data.section('plans') || {}).plans || [];
  const kind = k => t(['fix', 'build', 'product', 'owner', 'extend'].includes(k) ? 'un.plan.kind.' + k : 'un.plan.kind.other', { kind: k });
  const life = s => t(PLAN_STATES.includes(s) ? 'un.plan.life.' + s : 'un.plan.life.other', { state: s });
  const build = plans.some(p => p.kind === 'build' || p.kind === 'extend');
  return fold(t('un.plan.plans'), esc(tn('un.pl.plan', plans.length)), `<ul class="rows">${plans.map(p => `<li class="row" style="padding-inline:0;align-items:flex-start"><span class="row__main">
      <span class="row__title">${rich(L(p.title || p.id))}</span>
      <span class="row__meta" style="display:block">${esc(kind(p.kind))}${t('list.sep')}${esc(life(p.state))}${t('list.sep')}${esc(tn('un.pl.step', p.steps.length))}${p.parent ? `${t('list.sep')}${esc(t('un.plan.under', { id: p.parent }))}` : ''}</span>
      ${p.goal ? `<span class="small ink-2" style="display:block;margin-top:4px">${rich(L(p.goal))}</span>` : ''}</span></li>`).join('')}</ul>
    ${build ? `<a class="btn btn--secondary btn--sm" style="margin-top:8px" href="${href('/activity', { sheet: offline() ? 'open-live' : 'launcher' })}">${t('un.plan.buildnext')}</a>
      <p class="small muted" style="margin-top:4px">${t('un.plan.buildnext.note')}</p>` : ''}`);
}
const PLAN_STATES = ['draft', 'registered', 'approved', 'rejected', 'active', 'review', 'merged', 'closed', 'regressed', 'archived'];

// how far the fix plan is: the closed cards of all, else the plan's own progress
function progressHTML(tot, share) {
  return share == null ? `<p class="small muted">${t('un.plan.progress.nm')}</p>` : `<div class="un-progress" role="img" aria-label="${esc(tot.all_cards ? t('un.plan.progress', { k: num(tot.closed), n: num(tot.all_cards) }) : Math.round(share * 100) + '%')}"><span style="transform:scaleX(${share.toFixed(3)})"></span></div>
      ${tot.all_cards ? `<p class="small"><b class="num">${num(tot.closed)}</b> ${esc(t('un.plan.progress.v', { n: num(tot.all_cards), p: Math.round(share * 100) + '%' }))}</p>` : ''}`;
}
// the fix plan's card: its goal, progress and indicators
function planCard(fix) {
  const tot = model.totals();
  const share = tot.all_cards ? tot.closed / tot.all_cards : fix.progress ? fix.progress.value : null;
  const indicators = fix.indicators || [];
  return `<section class="section panel panel__pad un-plancard" aria-labelledby="pc-h">
      <div class="un-plancard__head"><h2 class="h2" id="pc-h">${rich(L(fix.title || ''))}</h2>${stateTag(fix.state)}<span class="small muted">${t('un.plan.kind.fix')}</span></div>
      ${fix.goal ? `<p class="small ink-2">${rich(L(fix.goal))}</p>` : ''}
      ${progressHTML(tot, share)}
      ${indicators.length ? `<dl class="facts">${indicators.map(i => `<dt>${esc(L(i.name || i.id || ''))}</dt><dd class="un-arrowval"><span class="num">${esc(i.today == null ? '—' : String(i.today))}</span>${icon('chev', 'icon--sm icon--dir muted')}<span class="num">${esc(i.target == null ? '—' : String(i.target))}</span><span class="small muted">${t('un.plan.target')}</span></dd>`).join('')}</dl>` : `<p class="small muted">${t('un.plan.noind')}</p>`}
      <p class="small muted">${t('un.plan.rule')}</p>
    </section>`;
}
// the steps that wait for others: the drawing and its rows
function depsHTML(all) {
  const deps = all.filter(s => s.waits.length);
  return deps.length ? `${depsSVG(all)}
      <ul class="panel rows un-deplist">${deps.map(s => s.waits.map(w => `<li class="row"><span class="row__main small">${esc(t('un.plan.dep.row', { a: s.id, b: w[0], n: tn('pl.problem', w[1]) }))}</span></li>`).join('')).join('')}</ul>`
        : `<p class="small muted">${t(timeline() ? 'un.plan.nodeps' : 'un.plan.deps.nm')}</p>`;
}

function planPage(ctx) {
  const build = model.buildPlan();
  if (build && !model.plan().steps.length) return buildPage(build);
  if (ctx.state === 'empty' || (!ctx.state && !model.plan().steps.length)) {
    return empty(t('un.plan.empty'), t('un.plan.empty.guide'), planSeg());
  }
  const all = steps(), next = nextStep(all);
  const fix = ((data.section('plans') || {}).plans || []).find(p => p.kind === 'fix') || {};
  return `<div class="page page--wide">
    ${planSeg()}
    <h1 class="lede">${esc(next ? t('un.plan.lede', { n: tn('un.pl.step', all.length), next: next.id }) : t('un.plan.lede.none', { n: tn('un.pl.step', all.length) }))}</h1>
    <p class="guide">${t('un.plan.guide')}</p>
    <div class="actions">${next ? fixBtn(next, 'btn--primary', t('un.plan.fixnext', { id: next.id })) : ''}
      <a class="btn btn--quiet" href="${href('/problems/plan/waves')}">${icon('layers', 'icon--sm')}${t('un.plan.waves')}</a>
      <p class="actions__note">${t('st.next.note')}</p></div>
    ${planCard(fix)}
    <section class="section" aria-labelledby="st-h"><div class="section-head"><h2 id="st-h">${t('un.plan.steps')}</h2><span class="small muted">${t('un.plan.order')}</span></div>
      <ol class="panel un-steps">${all.map(s => stepRow(s, next)).join('')}</ol></section>
    <section class="section" aria-labelledby="dp-h"><div class="section-head"><h2 id="dp-h">${t('un.plan.deps')}</h2></div>
      ${depsHTML(all)}</section>
    <div class="panel section">${plansFold()}</div>
  </div>`;
}
screen({ id: 'S-08', path: '/problems/plan', place: 'problems', needs: NEEDS, title: () => t('pb.view.plan'), render: planPage,
  loading: () => loading(t('un.plan.loading')) });

/* ---------------- S-10 waves (registered before the step: the same number of parameters) ---------------- */
function cellClass(n, max) { if (!n) return 'un-wcell--0'; const r = n / max; return 'un-wcell--' + (r > 0.8 ? 5 : r > 0.55 ? 4 : r > 0.33 ? 3 : r > 0.15 ? 2 : 1); }
function wavesPage(ctx) {
  const q = ctx.query;
  const backLink = back('/problems/plan', t('pb.view.plan'));
  const tl = timeline();
  if (!tl || !tl.waves.length) return `<div class="page">${backLink}<h1 class="lede un-lede-sm">${t('un.waves.nm.lede')}</h1>${nm(t('un.waves.nm'), t('un.waves.nm.why'))}</div>`;
  const all = model.plan().steps.map(s => s.id);
  const G = {}; all.forEach(id => { G[id] = tl.waves.map(w => { const x = w.steps.find(y => y.step === id); return x ? x.tasks : 0; }); });
  const W = tl.waves.length;
  const max = Math.max(1, ...Object.values(G).flat());
  const totals = tl.waves.map(w => w.tasks);
  const wave = q.wave ? parseInt(q.wave, 10) : null, step = q.step || null;
  const r = parseHash();
  const cellHref = (w, s) => href(r.path, Object.assign({}, q, { wave: w, step: s }));
  const span = id => { const s = tl.steps.find(x => x.id === id); return !s || s.first == null ? '—' : s.first === s.last ? t('un.waves.one', { w: s.first }) : t('un.waves.span', { a: s.first, b: s.last }); };
  const grid = `<div class="panel un-wgrid-wrap only-desk"><table class="un-wgrid">
    <caption class="sr-only">${t('un.waves.grid')}</caption>
    <thead><tr><th scope="col">${t('un.waves.step')}</th>${totals.map((_, i) => `<th scope="col"><a href="${cellHref(i + 1, null)}" ${wave === i + 1 && !step ? 'aria-current="true"' : ''}>${esc(t('un.waves.wn', { w: i + 1 }))}</a></th>`).join('')}<th scope="col">${t('un.waves.first')}</th></tr></thead>
    <tbody>${all.map(id => `<tr><th scope="row"><a href="${cellHref(null, id)}" ${step === id && !wave ? 'aria-current="true"' : ''}>${code(id)}</a></th>${G[id].map((n, i) => `<td>${n ? `<a class="un-wcell ${cellClass(n, max)} ${wave === i + 1 && step === id ? 'is-on' : ''}" href="${cellHref(i + 1, id)}" aria-label="${esc(t('un.waves.cell', { w: i + 1, s: id, n: tn('pl.problem', n) }))}">${num(n)}</a>` : `<span class="un-wcell un-wcell--0" aria-hidden="true"></span>`}</td>`).join('')}<td class="small muted">${esc(span(id))}</td></tr>`).join('')}</tbody>
    <tfoot><tr><th scope="row">${t('un.waves.total')}</th>${totals.map(n => `<td class="num">${num(n)}</td>`).join('')}<td></td></tr></tfoot></table>
    <p class="small muted">${t('un.waves.key')}</p></div>`;
  const phone = `<ul class="panel rows only-phone">${totals.map((n, i) => `<li class="un-wrow"><a class="un-wrow__head ${wave === i + 1 && !step ? 'is-on' : ''}" href="${cellHref(i + 1, null)}"><b>${esc(t('un.waves.w', { w: i + 1 }))}</b><span class="small muted">${esc(tn('pl.problem', n))}</span></a>
    <div class="un-wrow__steps">${all.filter(id => G[id][i]).map(id => `<a class="fchip ${wave === i + 1 && step === id ? 'is-on' : ''}" href="${cellHref(i + 1, id)}"><bdi class="mono">${esc(id)}</bdi> ${num(G[id][i])}</a>`).join('')}</div></li>`).join('')}</ul>`;
  let picked = '';
  if (wave || step) {
    const list = tl.tasks.filter(x => (!wave || x.wave === wave) && (!step || x.step === step));
    const heading = wave && step ? t('un.waves.pick.both', { w: wave, s: step }) : wave ? t('un.waves.w', { w: wave }) : t('un.step.group', { id: step });
    const rows = list.slice(0, 12).map(x => { const p = model.problem(x.id); return p ? prow(p, waitText(x.id, true)) : ''; }).join('');
    picked = `<section class="section" aria-labelledby="wp-h"><div class="section-head"><h2 id="wp-h">${esc(heading)}</h2><a class="link" href="${href(r.path)}">${t('flt.clear')}</a></div>
      ${list.length ? `<div class="panel rows">${rows}</div>` : `<p class="small muted">${t('un.waves.none')}</p>`}
      ${list.length > 12 ? `<p class="small muted" style="margin-top:8px">${esc(t('un.comp.andmore', { n: num(list.length - 12) }))}</p>` : ''}</section>`;
  }
  return `<div class="page page--wide">
    ${backLink}
    <h1 class="lede">${esc(t('un.waves.lede', { n: tn('un.pl.wave', W) }))}</h1>
    <p class="guide">${t('un.waves.guide')}</p>
    <div class="section" style="margin-top:24px">${grid}${phone}</div>
    ${picked}
  </div>`;
}
screen({ id: 'S-10', path: '/problems/plan/waves', place: 'problems', needs: NEEDS, title: () => t('un.waves.title'), render: wavesPage, loading: () => loading(t('un.plan.loading')) });

/* ---------------- S-09 one step ---------------- */
const BUCKET = { open: 'todo', in_batch: 'active', on_branch: 'active', done: 'done', resolved: 'done', skipped: 'left' };
/** A task's wave in the plan's timeline, null when it has none. */
function waveOf(id) { const tl = timeline(); const x = tl && tl.tasks.find(y => y.id === id); return x ? x.wave : null; }
function taskRow(p) {
  const on = selection.picked.ids.has(p.id);
  const w = waveOf(p.id);
  return `<li class="prow ${on ? 'is-selected' : ''}">
      ${chk(`data-change="un-sel" value="${esc(p.id)}" data-fk="sel-${esc(p.id)}" ${p.state !== 'open' ? 'disabled' : ''}`, on, `${t('pd.select')}: ${p.id}`)}
      <a class="prow__link" href="${href('/problems/' + enc(p.id))}"><span class="prow__top">${sev(p.severity)}${p.state !== 'open' ? `<span class="tag tag--state">${t('state.' + p.state)}</span>` : ''}<span class="prow__end small muted">${esc(w ? t('un.waves.w', { w }) : t('un.waves.nowave'))}</span></span>
        <span class="prow__title">${rich(L(p.title || p.id))}</span>
        <span class="prow__meta">${code(p.id)}<span>${waitText(p.id, true)}</span></span></a></li>`;
}
/** What a step asks of the person first: the decision that holds it, its branch to decide, or its fix. */
function stepPrimary(s) {
  if (s.decision) return `<a class="btn btn--primary" href="${href('/waiting/' + enc(s.decision.id))}">${icon('seal', 'icon--sm')}${t('un.step.answer')}</a>`;
  if (s.review) return `<a class="btn btn--primary" href="${href('/waiting/' + enc(s.review))}">${icon('seal', 'icon--sm')}${t('un.step.decide')}</a>`;
  return fixBtn(s, 'btn--primary', t('un.step.fix'));
}
/** A step's tasks by state: one bar and its legend. */
function shareHTML(tasks) {
  const states = { todo: 0, active: 0, done: 0, left: 0 };
  tasks.forEach(p => { states[BUCKET[p.state] || 'todo'] += 1; });
  return `<div class="un-share" role="img" aria-label="${esc(t('un.step.share', { todo: states.todo, active: states.active, done: states.done, left: states.left }))}">
          ${['done', 'active', 'todo', 'left'].filter(k => states[k]).map(k => `<span class="un-share__s un-share__s--${k}" style="flex:${states[k]}"></span>`).join('')}</div>
        <div class="legend">${['todo', 'active', 'done', 'left'].map(k => `<span class="${states[k] ? '' : 'zero'}"><i class="un-share__dot un-share__dot--${k}" aria-hidden="true"></i>${t('un.tst.' + k)} <b>${num(states[k])}</b></span>`).join('')}</div>`;
}
function stepFacts(s, all, before, tasks) {
  const ops = ((data.section('operations') || {}).operations || []).filter(o => o.step === s.id);
  const waitsLine = s.waits.length ? s.waits.map(w => `<a class="link" href="${href('/problems/plan/' + enc(w[0]))}">${code(w[0])}</a> <span class="small muted">${esc(tn('pl.problem', w[1]))}</span>`).join(t('list.sep')) : t('un.step.free');
  const weights = all.reduce((sum, x) => sum + (x.weight || 0), 0);
  return `<section class="panel panel__pad un-stepfacts" aria-label="${esc(t('un.gap.props'))}">
        ${shareHTML(tasks)}
        ${facts([
          [t('un.step.gate'), s.gate ? rich(L(s.gate)) : `<span class="muted">${t('un.none')}</span>`],
          [t('un.step.weight'), weights ? Math.round((s.weight || 0) / weights * 100) + '%' : '—'],
          [t('un.step.waves'), s.first == null ? `<span class="muted">${t('un.waves.nowave')}</span>` : `<a class="link" href="${href('/problems/plan/waves', { step: s.id })}">${esc(s.first === s.last ? t('un.waves.one', { w: s.first }) : t('un.waves.span', { a: s.first, b: s.last }))}</a>`],
          [t('un.step.waitsfor'), waitsLine],
          [t('un.step.comesbefore'), before.length ? before.map(x => `<a class="link" href="${href('/problems/plan/' + enc(x.id))}">${code(x.id)}</a>`).join(' ') : t('un.none')],
          [t('un.step.subplan'), s.sub_plan ? code(s.sub_plan) : t('un.none')],
          [t('un.gap.ops'), opLinks(ops) || t('un.none')],
        ])}
      </section>`;
}
function stepPage(ctx) {
  const all = steps();
  const s = all.find(x => x.id === ctx.params.step);
  const backLink = back('/problems/plan', t('pb.view.plan'));
  if (!s) return `<div class="page">${backLink}<div class="empty panel" style="margin-top:12px"><h1 class="empty__title">${esc(t('pd.notfound', { id: ctx.params.step }))}</h1><p class="small ink-2">${t('un.notfound.guide')}</p></div></div>`;
  const tasks = s.ids.map(id => model.problem(id) || Object.assign({ id, severity: 'info', paths: [] }, s.tasks.find(x => x.id === id), { state: 'open' }));
  const before = all.filter(x => x.waits.some(w => w[0] === s.id));
  const guide = t('un.step.guide', { n: tn('pl.problem', s.ids.length), waits: s.waits.length ? t('un.step.guide.waits', { list: s.waits.map(w => w[0]).join(t('list.sep')) }) : t('un.step.guide.free'), before: before.length ? t('un.step.guide.before', { list: before.map(x => x.id).join(t('list.sep')) }) : '' });
  const open = openIds(s);
  const pg = page(tasks, taskRow);
  return `<div class="page page--wide">
    ${backLink}
    <div class="un-itemtags">${code(s.id)}${stateTag(s.state)}${s.sub_plan ? `<span class="tag tag--state">${t('un.plan.sub')}</span>` : ''}</div>
    <h1 class="lede un-lede-sm">${title(s)}</h1>
    <p class="guide">${esc(guide)}</p>
    <div class="actions">${stepPrimary(s)}
      ${open.length ? `<button class="btn btn--quiet" data-act="un-sel-step" data-ids="${esc(open.join(','))}" data-step="${esc(s.id)}">${icon('select', 'icon--sm')}${t('un.step.selectall')}</button>` : ''}
      <p class="actions__note">${t(s.decision ? 'un.step.blocked.note' : 'st.next.note')}</p></div>
    <div class="un-stepgrid">
      ${stepFacts(s, all, before, tasks)}
      <section aria-labelledby="tk-h">
        <div class="listhead"><h2 class="h2" id="tk-h">${t('un.step.tasks')}</h2><span class="listhead__count">${esc(t('un.showing', { shown: num(pg.shown), total: num(tasks.length) }))}</span></div>
        ${tasks.length ? `<ul class="panel rows plist un-tasklist">${pg.html}</ul>${pg.more}` : `<div class="panel empty"><p class="empty__title">${t('un.step.none')}</p></div>`}
      </section>
    </div>
  </div>`;
}
screen({ id: 'S-09', path: '/problems/plan/:step', place: 'problems', needs: NEEDS, title: ctx => ctx.params.step + ' - ' + t('pb.view.plan'), render: stepPage,
  loading: () => loading(t('un.plan.loading')) });

/* ---------------- the selection over a step's problems (SEL-01): ticks, shift for a range, the bar's verbs ---------------- */
tickAct('un-sel', '.un-tasklist', '.un-tasklist input[type=checkbox]');
act('un-sel-step', el => {
  selection.pick(el.dataset.ids.split(',').filter(Boolean), { by: 'step', value: el.dataset.step, label: t('un.step.group', { id: el.dataset.step }) });
  refresh();
  announce(tn('pl.selected', selection.picked.ids.size));
});
act('un-sel-clear', () => { selection.clearSelection(); refresh(); });
setSelbar('un-sel-clear');
