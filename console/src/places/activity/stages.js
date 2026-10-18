// The check's stages (CHK-08..11): the stages of the last check as /api/progress tells them (eaos/progress.py: each
// with its layer, needs, state, reason, steps, programs, files and what it reported), drawn by layer; one stage's
// sheet (S-16, CHK-09); "Redo from here" with its free preview (CHK-10, POST /api/actions/audit/preview with
// again_from); and the replay of a finished check from its own start and end times (CHK-11).
import {
  t, tn, L, num, esc, rich, icon, code, has, sheet, act, rerenderSheet, local, parseHash, closeSheetThen, toast, refresh, href, offline,
  data, client, store, model, ActionError, ac,
} from 'eaos';

/** A stage's name and what it does: the dictionary's words, else its own description. */
export const stageTitle = id => (has('ac.stage.' + id) ? t('ac.stage.' + id) : id);
export const stageDoes = s => (has('ac.stage.' + s.id + '.does') ? t('ac.stage.' + s.id + '.does') : s.description || '');

/** The state the board draws for one stage of the flow: the run's pause, a sign-in it waits for and a stop shown. */
function shownState(s, run) {
  const st = { not_reached: 'notreached', skipped: s.reason_code === 'outside_paths' ? 'notin' : 'skipped' }[s.state] || s.state;
  if (run && run.state === 'paused' && st === 'running') return 'paused';
  if (s.id === 'session' && st === 'running' && store.live.signIn && store.live.signIn.asked) return 'you';
  if (run && run.state === 'stopped' && (st === 'running' || st === 'waiting')) return st === 'running' ? 'stopped' : 'notreached';
  return st;
}

/** The stages of `flow` as the screens draw them; `at` (seconds since the check started) replays it. */
export function stagesOf(flow, run, at) {
  if (!flow || !flow.stages) return [];
  const start = Date.parse(flow.started_at);
  return flow.stages.map(s => {
    const out = { id: s.name, layer: s.layer || 0, needs: s.requires || [], ai: !!s.ai, optional: s.necessity !== 'required', requested: s.requested !== false, raw: s };
    out.state = shownState(Object.assign({ id: s.name }, s), run);
    if (at != null && s.started_at) {
      const from = (Date.parse(s.started_at) - start) / 1000, to = s.ended_at ? (Date.parse(s.ended_at) - start) / 1000 : Infinity;
      out.state = at >= to ? out.state : at >= from ? 'running' : 'waiting';
    }
    return out;
  });
}
export function counts(list) { const c = {}; list.forEach(s => { c[s.state] = (c[s.state] || 0) + 1; }); return c; }
const DONE = ['ok', 'skipped', 'notin', 'unavailable', 'failed', 'partial'];
export const finished = list => list.filter(s => DONE.includes(s.state)).length;
export function summary(c) {
  return ['ok', 'running', 'you', 'paused', 'partial', 'waiting', 'stopped', 'notreached', 'skipped', 'notin', 'unavailable', 'failed']
    .filter(k => c[k]).map(k => t(has('ac.sum.' + k) ? 'ac.sum.' + k : 'ac.sum.skipped', { n: num(c[k]) })).join(t('list.sep')) + '.';
}
function focusOf(list) {
  return (list.find(s => s.state === 'running' || s.state === 'you') || list.find(s => s.state === 'failed') || list.slice().reverse().find(s => s.state === 'ok') || {}).id;
}
export function stageButton(s, focus) {
  const dim = ['skipped', 'notin', 'unavailable'].includes(s.state) || !s.requested;
  return `<li><button class="ac-stg ac-stg--${esc(s.state)} ${focus ? 'is-focus' : ''} ${dim ? 'is-dim' : ''}" data-act="sheet" data-sheet="stage:${esc(s.id)}" data-fk="stg-${esc(s.id)}">
    ${ac.glyph(s.state)}<span class="ac-stg__name">${esc(stageTitle(s.id))}<span class="sr-only">, ${esc(ac.stateWord(s.state))}</span></span>
    ${s.ai ? `<span class="ac-stg__ai" title="${esc(t('ac.stg.ai'))}">${icon('ai', 'icon--sm')}<span class="sr-only">${t('ac.stg.ai')}</span></span>` : ''}</button></li>`;
}
/** Every stage in its dependency layer; the running stage (else the failed one, else the last ended) in focus. */
export function board(list, follow) {
  const focus = follow === false ? null : focusOf(list);
  const layers = [];
  list.forEach(s => { (layers[s.layer] = layers[s.layer] || []).push(s); });
  return `<div class="ac-board">${layers.filter(Boolean).map((row, i) => `<section class="ac-layer" aria-label="${esc(t('ac.run.layer', { n: num(i + 1) }))}">
      <h3 class="ac-layer__h"><span class="ac-layer__n num">${num(i + 1)}</span>${t('ac.run.layer', { n: num(i + 1) })}</h3>
      <ul class="ac-layer__list">${row.map(s => stageButton(s, s.id === focus)).join('')}</ul></section>`).join('')}</div>`;
}
/** The whole check's length, from its stages' own times (for the replay). */
export function span(flow) {
  const start = Date.parse(flow.started_at);
  return Math.max(1, ...flow.stages.filter(s => s.ended_at).map(s => (Date.parse(s.ended_at) - start) / 1000));
}

/* ---------- S-16 one stage (CHK-09) ---------- */
const flow = () => ac.checkFlow();
const stepGlyph = st => (['ok', 'observed', 'done'].includes(st) ? 'ok' : ['error', 'failed'].includes(st) ? 'failed' : st === 'running' ? 'running' : st === 'waiting' ? 'waiting' : 'skipped');
const stepWord = st => (has('ac.step.' + st) ? t('ac.step.' + st) : st);
function stepRow(x) {
  const prog = x.total ? t('ac.stg.of', { done: num(x.done || 0), total: num(x.total) }) : '';
  return `<li class="row" style="min-height:48px">${ac.glyph(stepGlyph(x.status))}<span class="row__main"><bdi class="mono">${esc(x.name)}</bdi>
    <span class="row__meta" style="display:block">${esc(stepWord(x.status))}${x.reason ? `: ${rich(x.reason)}` : ''}</span></span><span class="num small muted">${esc(x.seconds ? ac.secs(x.seconds) : prog)}</span></li>`;
}
/** A reported value a person reads: numbers and words, never a path of this computer. */
const shown = v => (v != null && typeof v !== 'object' && !/^\//.test(String(v)));
function why(s) {
  const code = s.raw.reason_code;
  if (code && has('ac.why.' + code)) return t('ac.why.' + code);
  return s.raw.reason || null;
}
/** The stages that read from `id`, however far (redo runs them again). */
export function dependents(list, id) {
  const out = new Set();
  const walk = x => list.forEach(s => { if (s.needs.includes(x) && !out.has(s.id)) { out.add(s.id); walk(s.id); } });
  walk(id);
  return [...out];
}
const failedTools = s => (s.raw.steps || []).filter(x => ['error', 'failed'].includes(x.status)).map(x => x.name);

function fileRow(path, own) {
  const got = own.files && own.files[path];
  return `<li><details class="ac-ev-fold" data-file="${esc(path)}" ${got ? 'open' : ''}><summary><bdi class="mono">${esc(path)}</bdi>${icon('chev-down', 'icon--sm muted')}</summary>
    ${got ? `<div class="code" style="padding:8px 12px;white-space:pre-wrap;margin-top:6px;max-height:320px;overflow:auto">${esc(got.slice(0, 20000))}</div><p class="small muted">${t('ac.stg.file.note')}</p>` : ''}</details></li>`;
}

sheet('stage', {
  kind: 'drawer',
  render(id, query, own) {
    const f = flow();
    const run = ac.lastCheck();
    const list = stagesOf(f, run);
    const s = list.find(x => x.id === id);
    if (!s) return { title: esc(t('ac.stg.notfound', { id })), body: `<p class="small ink-2">${t('ac.stg.noflow')}</p>` };
    const raw = s.raw, st = s.state;
    const reason = why(s);
    const needs = s.needs.length ? s.needs.map(n => `<button class="link ac-inline" data-act="sheet" data-sheet="stage:${esc(n)}">${esc(stageTitle(n))}</button>`).join(t('list.sep')) : t('ac.stg.needs.none');
    const last = f.previous && f.previous[id];
    const steps = (raw.steps || []).length ? `<ul class="panel rows">${raw.steps.map(stepRow).join('')}</ul>` : `<p class="small muted">${t(st === 'waiting' ? 'ac.stg.steps.none' : 'ac.stg.steps.one')}</p>`;
    const files = (raw.artifacts || []).length ? `<ul class="ac-files">${raw.artifacts.map(p => fileRow(p, own)).join('')}</ul>`
      : `<p class="small muted">${t(['ok', 'partial'].includes(st) ? 'ac.stg.files.none' : 'ac.stg.files.later')}</p>`;
    const reported = Object.entries(raw.detail || {}).filter(([, v]) => shown(v));
    const programs = (raw.programs || []).length ? `<div class="panel row" style="min-height:48px">${ac.glyph('running')}<span class="row__main small">${raw.programs.map(p => `${code(p.name || p)}${p.seconds ? ' ' + esc(t('ac.stg.prog', { t: ac.secs(p.seconds) })) : ''}`).join(', ')}</span></div>`
      : raw.activity_note ? `<p class="small ink-2">${rich(raw.activity_note)}</p>` : '';
    const ended = run && ac.ended(run) && f.state !== 'running';
    const tools = failedTools(s);
    let redo;
    if (offline()) redo = `<button class="btn btn--primary btn--block" data-act="sheet" data-sheet="open-live">${t('ac.stg.redo')}</button>`;
    else if (query.replay) redo = `<button class="btn btn--primary btn--block" disabled aria-describedby="redo-why">${t('ac.stg.redo')}</button><p class="sheet__fine" id="redo-why">${t('ac.stg.redo.replay')}</p>`;
    else if (!ended) redo = `<button class="btn btn--primary btn--block" disabled aria-describedby="redo-why">${t('ac.stg.redo')}</button><p class="sheet__fine" id="redo-why">${t('ac.stg.redo.running')}</p>`;
    else if (!['ok', 'failed', 'partial'].includes(st)) redo = `<button class="btn btn--primary btn--block" disabled aria-describedby="redo-why">${t('ac.stg.redo')}</button><p class="sheet__fine" id="redo-why">${t('ac.stg.redo.didnt')}</p>`;
    else redo = `<button class="btn btn--primary btn--block" data-act="sheet" data-sheet="redo:${esc(id)}" data-autofocus>${t('ac.stg.redo')}</button>
      ${tools.length ? `<button class="btn btn--secondary btn--block" data-act="sheet" data-sheet="redo:${esc(id)}:failed">${t('ac.stg.redo.failed')}</button>` : ''}`;
    return {
      title: esc(stageTitle(id)),
      sub: `${ac.mark(st)} <bdi class="mono muted">${esc(id)}</bdi>${run ? ` <span class="muted">${esc(ac.runLabel(run))}</span>` : ''}`,
      body: `<p>${esc(stageDoes(Object.assign({ description: raw.description }, s)))}</p>
        ${reason ? `<div class="${st === 'failed' ? 'ac-note ac-note--caution' : 'ac-note'}">${ac.glyph(st)}<span class="small">${rich(reason)}</span></div>` : ''}
        ${s.ai ? `<div class="ai-block"><span class="ai-block__label">${icon('ai', 'icon--sm')}${t('ac.stg.ai')}</span><p class="small" style="margin-top:4px">${t('ac.stg.ai.note')}</p></div>` : ''}
        ${programs}
        <dl class="facts">
          <dt>${t('ac.stg.needs')}</dt><dd>${needs}</dd>
          <dt>${t('ac.stg.required')}</dt><dd>${t(s.optional ? 'ac.stg.optional' : 'ac.stg.required.v')}</dd>
          <dt>${t('ac.stg.time')}</dt><dd>${raw.seconds != null && st !== 'running' ? esc(ac.secs(raw.seconds)) : st === 'running' && raw.started_at ? esc(t('ac.stg.time.running', { t: ac.secs((Date.now() - Date.parse(raw.started_at)) / 1000) })) : '—'} <span class="muted">${esc(t('ac.stg.last', { t: last ? ac.secs(last) : t('ac.stg.last.none') }))}</span></dd>
          <dt>${t('ac.stg.kept')}</dt><dd>${t(raw.resumed ? 'ac.stg.kept.yes' : 'ac.stg.kept.no')}</dd>
        </dl>
        <div><div class="block-title">${t('ac.stg.steps')}</div>${steps}</div>
        <div><div class="block-title">${t('ac.stg.files')}</div>${files}</div>
        ${reported.length ? `<div><div class="block-title">${t('ac.stg.reported')}</div><dl class="facts">${reported.map(([k, v]) => `<dt>${esc(k.replace(/_/g, ' '))}</dt><dd class="num">${esc(typeof v === 'number' ? num(v) : v)}</dd>`).join('')}</dl></div>` : ''}`,
      foot: redo,
    };
  },
  after(el, id, own) {
    el.querySelectorAll('details[data-file]').forEach(d => d.addEventListener('toggle', () => {
      const path = d.dataset.file;
      own.files = own.files || {};
      if (!d.open || own.files[path] != null) return;
      data.reportFile(path).then(text => { own.files[path] = text == null ? t('ac.stg.file.unread') : text; rerenderSheet(); });
    }));
  },
});

/* ---------- Redo from a stage (CHK-10) ---------- */
/* Pick the stage to go on from, straight from Activity: the stages the last check finished, layer by layer */
sheet('redo-pick', {
  kind: 'drawer',
  render() {
    const run = ac.lastCheck();
    const list = stagesOf(flow(), run).filter(x => ['ok', 'failed', 'partial'].includes(x.state)).sort((a, b) => a.layer - b.layer);
    const ended = run && ac.ended(run) && flow() && flow().state !== 'running';
    return {
      title: esc(t('ac.pick.title')),
      sub: run ? `<span class="muted">${esc(ac.runLabel(run))}</span>` : '',
      body: !ended || !list.length ? `<p class="small ink-2">${t(ended ? 'ac.pick.none' : 'ac.stg.redo.running')}</p>`
        : `<p class="small ink-2">${t('ac.pick.guide')}</p><ul class="panel rows">${list.map(x => `<li><button class="row" data-act="sheet" data-sheet="redo:${esc(x.id)}">${ac.glyph(x.state)}<span class="row__main"><span class="row__title">${esc(stageTitle(x.id))}</span><span class="row__meta" style="display:block">${esc(t('ac.pick.layer', { n: num(x.layer + 1) }))}</span></span>${icon('chev', 'icon--dir muted')}</button></li>`).join('')}</ul>`,
    };
  },
});
function redoInputs(id, variant) {
  const s = stagesOf(flow()).find(x => x.id === id);
  return Object.assign({ again_from: id }, variant === 'failed' && s ? { engines: failedTools(s) } : {});
}
sheet('redo', {
  kind: 'drawer',
  render(arg, query, own) {
    const [id, variant] = arg.split(':');
    const list = stagesOf(flow());
    const s = list.find(x => x.id === id);
    if (!s) return { title: esc(t('ac.stg.notfound', { id })), body: '' };
    const failed = variant === 'failed';
    const inputs = redoInputs(id, variant);
    if (!own.preview && !own.asking && !own.problem && client) {
      own.asking = true;
      client.preview('audit', { inputs }).then(p => { own.preview = p; own.asking = false; rerenderSheet(); },
        e => { own.asking = false; own.problem = e instanceof ActionError ? e.message : String(e); rerenderSheet(); });
    }
    const rerun = [id].concat(dependents(list, id)).filter(x => { const y = list.find(z => z.id === x); return y && y.requested; });
    const kept = list.length - rerun.length;
    const p = own.preview;
    const est = p && p.estimate && p.estimate.minutes_low != null ? t('pv.estimate.v', { lo: num(p.estimate.minutes_low), hi: num(p.estimate.minutes_high) }) : t('ac.chk.est.none');
    const title = t(failed ? 'ac.redo.title.failed' : 'ac.redo.title', { stage: stageTitle(id) });
    const cmd = `eaos check --again-from ${id}${failed ? ' --failed-tools' : ''}`;
    const busy = !!ac.liveRun();
    return {
      title: esc(title),
      sub: `<span class="free-band">${icon('check', 'icon--sm')}${t('free')}</span>`,
      body: `<p>${esc(failed ? t('ac.redo.does.failed', { tools: (inputs.engines || []).join(t('list.sep')) }) : t('ac.redo.does', { n: num(rerun.length - 1) }))}</p>
        <dl class="facts">
          <dt>${t('ac.redo.code')}</dt><dd>${t('ac.redo.code.v', { branch: code(model.project().branch), commit: code((model.project().commit || '').slice(0, 7)) })}</dd>
          <dt>${t('ac.redo.runs')}</dt><dd>${esc(tn('pl.stage', rerun.length))}</dd>
          <dt>${t('ac.redo.kept')}</dt><dd>${esc(tn('pl.stage', kept))}</dd>
          <dt>${t('pv.estimate')}</dt><dd>${p ? esc(est) : `<span class="muted" aria-busy="${own.problem ? 'false' : 'true'}">${t('pv.updating')}</span>`}${p && p.estimate ? `<span class="small muted" style="display:block">${esc(L(p.estimate.basis))}</span>` : ''}</dd>
          <dt>${t('pv.risk')}</dt><dd><span class="tag tag--state">${t('pv.risk.low')}</span> <span class="small ink-2">${t('ac.redo.risk')}</span></dd>
          <dt>${t('pv.fail')}</dt><dd class="small">${t('ac.redo.fail')}</dd>
        </dl>
        <div><div class="block-title">${t('ac.redo.list')}</div><ul class="ac-chiplist">${rerun.map(x => `<li><span class="tag tag--state">${esc(stageTitle(x))}</span></li>`).join('')}</ul></div>
        <p class="small ink-2">${t('ac.redo.never')}</p>
        <details><summary class="link" style="cursor:pointer;min-height:44px;display:inline-flex;align-items:center;gap:6px">${icon('terminal', 'icon--sm')}${t('pv.terminal')}</summary>
          <div class="code" style="padding:12px 16px;margin-top:8px">${esc(cmd)}</div></details>`,
      foot: `${own.problem || own.refused ? `<p class="small" role="alert">${icon('warn', 'icon--sm')} ${esc(own.problem || own.refused)}</p>` : ''}
        ${busy ? `<p class="small ink-2">${t('ac.redo.busy')}</p>` : ''}
        <button class="btn btn--primary btn--block" data-act="ac-redo-start" data-fk="redo-start" ${p && !own.busy ? '' : 'disabled'}>${esc(own.busy ? t('pv.starting') : busy ? t('ac.chk.queue') : t('ac.redo.start'))}</button>
        <button class="btn btn--quiet btn--block" data-act="copy" data-text="${esc(cmd)}">${icon('copy')}${t('pv.copy')}</button>`,
    };
  },
});

act('ac-redo-start', async el => {
  const own = local(), arg = (parseHash().query.sheet || '').split(':').slice(1).join(':');
  if (el.disabled || own.busy || !client) return;
  const [id, variant] = arg.split(':');
  own.busy = true; rerenderSheet();
  try {
    const run = await client.start({ action: 'audit', inputs: redoInputs(id, variant) });
    closeSheetThen(() => {
      store.refresh(); refresh();
      toast(t(run.state === 'queued' ? 'toast.queued' : 'toast.started', { title: t('ac.redo.title', { stage: stageTitle(id) }) }),
        { link: { href: href('/activity/run/' + encodeURIComponent(run.id)), text: t('toast.follow') } });
    });
  } catch (e) { Object.assign(own, { busy: false, refused: e instanceof ActionError ? e.message : String(e) }); rerenderSheet(); }
});
