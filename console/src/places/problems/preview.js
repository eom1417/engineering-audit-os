// C-03 The verb preview (FIX-01..06; G2, G3, G4, G12): Fix, Verify, Explain or Plan over a selection, one sheet for
// the four. It asks the server for the preview (POST /api/actions/<verb>/preview: never changes anything) and shows
// what will happen: the problems in it and those left out with why, the files, the batches, the time, the risk, what
// happens on failure, where a Fix is built and delivered, who runs it; then Start sends exactly that preview's choices
// with its confirm token (POST /api/runs). A choice that changes (the assistant, where, accept by itself) asks for the
// preview again, since the token is bound to it. Address: ?sheet=verb:<verb>[:fixable | :assistant | :<problem> |
// :step:<id>]; without a target, the current selection.
import {
  t, tn, L, num, esc, rich, icon, code, sev, href, assistantPicker, estimate, expiresAt, sheet, act, rerenderSheet, local, parseHash, closeSheetThen, toast, refresh, offline,
  model, selection, store, client, ActionError, contract, prefs,
} from 'eaos';

const enc = encodeURIComponent;

/** The contract's selection of the address. */
function selectionOf(target) {
  // every problem of the group: the server runs the open ones and says why it leaves the others out
  const all = model.problems();
  if (target === 'fixable') return { kind: 'cards', cards: all.filter(p => p.fixable).map(p => p.id).slice(0, 500) };
  if (target === 'assistant') return { kind: 'cards', cards: all.filter(p => p.decision && p.decision.state === 'fixes').map(p => p.id).slice(0, 500) };
  if (target && target.startsWith('step:')) return { kind: 'step', step: target.slice(5) };
  if (target) return { kind: 'card', cards: [target] };
  return selection.toSelection();
}

function body(verb, own) {
  const fix = verb === 'fix', kept = own.preview && own.preview.speed;
  // speed mode as the person set it in this sheet, else as it is kept for the project
  const speed = own.speed != null ? own.speed : kept ? kept.on : null;
  return {
    verb, selection: own.selection, assistant: own.assistant || undefined,
    where: fix ? own.place : undefined,
    inputs: fix ? Object.assign(own.auto ? { auto_accept: true } : {}, speed != null ? { speed } : {}) : undefined,
  };
}

function ask(verb, own) {
  if (own.asking || !client) return;
  if (!own.selection || (own.selection.cards && !own.selection.cards.length)) { own.problem = t('pv.empty'); return; }
  const mine = own.ticket = (own.ticket || 0) + 1; // an answer to an older choice is dropped
  own.asking = true; own.problem = null;
  client.preview(verb, body(verb, own)).then(p => { if (mine !== own.ticket) return; own.preview = p; own.asking = false; rerenderSheet(); },
    e => { if (mine !== own.ticket) return; own.asking = false; own.preview = null; own.problem = e instanceof ActionError ? e.message : String(e); rerenderSheet(); });
}
/** The choice changed: the preview is asked again (the old one's token no longer matches). */
function again(change) {
  Object.assign(local(), { preview: null, asking: false, problem: null, moved: false, refused: null }, change);
  rerenderSheet();
}


function cardsHTML(p) {
  const shown = p.cards.slice(0, 6);
  return `<div><div class="block-title">${t('pv.included')} (${num(p.cards.length)})</div>
    <div class="panel rows">${shown.map(c => `<div class="row" style="min-height:48px">${c.severity ? sev(c.severity, false) : ''}<span class="row__main small">${code(c.id)} ${rich(L(c.title || ''))}</span></div>`).join('')}
    ${p.cards.length > 6 ? `<div class="row small muted" style="min-height:44px">+ ${esc(tn('pl.problem', p.cards.length - 6))}</div>` : ''}</div></div>
    ${p.left_out.length ? `<div><div class="block-title">${t('pv.left')} (${num(p.left_out.length)})</div><div class="panel rows">${p.left_out.slice(0, 8).map(r => `<div class="row small" style="min-height:44px">${code(r.id)}<span class="row__main muted">${esc(prefs.lang === 'ar' && r.why_ar ? r.why_ar : r.why)}</span></div>`).join('')}</div></div>` : ''}`;
}

function radios(name, rows, picked, act) {
  return `<div class="opts" style="margin-top:8px">${rows.map(b => `<label class="opt ${b.blocked ? 'opt--off' : ''}"><input type="radio" name="${name}" value="${esc(b.name)}" data-change="${act}" data-fk="${name}-${esc(b.name)}" ${b.name === picked ? 'checked' : ''} ${b.blocked ? 'disabled' : ''}>
    <span class="opt__dot"></span><span class="opt__text"><span class="opt__line">${code(b.name)}${b.blocked ? icon('lock', 'icon--sm muted') : ''}</span>
    <span class="opt__note">${esc(b.blocked ? L(b.blocked) : b.note || b.short || '')}</span></span></label>`).join('')}</div>`;
}

/** Where a Fix is built, the branch its fixes arrive on and the branch Accept merges them into (a protected branch is
 *  shown with its reason, never choosable). */
function whereHTML(w, own) {
  const base = w.base ? w.base.branch : '';
  const mode = w.mode || 'new';
  const modes = [['new', t('pv.deliver.new')]].concat(w.continuable && w.continuable.length ? [['continue', t('pv.deliver.continue')]] : [])
    .concat(!w.direct_blocked && base ? [['direct', t('pv.deliver.direct', { branch: base })]] : []);
  return `<div><div class="block-title">${t('pv.where')}</div><div class="panel panel__pad"><dl class="facts">
      <dt>${t('pv.base')}</dt><dd>${code(base)} ${w.base ? code(w.base.short) : ''}${w.base && !w.base.checked_out ? ` <span class="small muted">${t('pv.base.notopen')}</span>` : ''}</dd>
      <dt>${t('pv.deliver')}</dt><dd>${mode === 'direct' ? esc(t('pv.deliver.direct', { branch: base })) : `${mode === 'new' ? t('pv.deliver.new') : t('pv.deliver.continue')} ${code(w.deliver_as || '')}`}</dd>
      ${mode === 'direct' ? '' : `<dt>${t('pv.merge')}</dt><dd>${code(w.merge_into || '')} ${w.merge_into && w.base && w.merge_into === w.base.branch ? `<span class="small muted">${t('cf.open_folder')}</span>` : ''}</dd>`}</dl>
    ${w.problem ? `<p class="small" role="note">${icon('warn', 'icon--sm')} ${esc(L(w.problem))}</p>` : ''}
    <details style="margin-top:8px" ${own.whereOpen ? 'open' : ''} data-where><summary class="link" style="cursor:pointer;min-height:44px;display:inline-flex;align-items:center">${t('pv.change')}</summary>
      <div class="block-title" style="margin-top:8px">${t('pv.base')}</div>${radios('base', w.branches, base, 'pv-base')}
      <div class="block-title" style="margin-top:12px">${t('pv.deliver')}</div>
      <div class="opts">${modes.map(([id, label]) => `<label class="opt"><input type="radio" name="mode" value="${id}" data-change="pv-mode" data-fk="mode-${id}" ${id === mode ? 'checked' : ''}><span class="opt__dot"></span><span class="opt__text">${esc(label)}</span></label>`).join('')}</div>
      ${mode === 'new' ? `<label class="field" style="margin-top:8px"><span class="sr-only">${t('pv.deliver.name')}</span><input class="input mono" dir="ltr" id="pv-name" data-fk="pv-name" value="${esc(own.name != null ? own.name : w.deliver_as || '')}" data-input="pv-name"></label>
        ${own.name && own.name !== w.deliver_as ? `<button class="btn btn--secondary btn--sm" data-act="pv-name-go" style="margin-top:8px">${t('pv.update')}</button>` : ''}` : ''}
      ${mode === 'continue' ? radios('cont', w.continuable, w.deliver_as, 'pv-continue') : ''}
      ${mode === 'direct' ? `<p class="small ink-2">${esc(t('pv.direct.note', { branch: base }))}</p>` : `<div class="block-title" style="margin-top:12px">${t('pv.merge')}</div>${radios('into', w.branches, w.merge_into, 'pv-into')}`}
    </details></div></div>`;
}

function assistantsHTML(p, own) {
  const all = p.assistants || (p.assistant ? [p.assistant] : []);
  if (!all.length) return '';
  const picked = own.assistant || (p.assistant && p.assistant.id);
  return `<div>${assistantPicker(all, picked, '')}
  ${!p.assistant && p.handoff && p.handoff.available ? `<p class="small ink-2">${t('pv.handoff')}</p>` : ''}</div>`;
}

/** A Fix's speed mode: several assistants at once, as many as the lanes of its cards and this computer allow, and what
 *  it costs. Its switch keeps the preview (the token is not bound to it). */
function speedHTML(s, own) {
  const on = own.speed != null ? own.speed : s.on, n = Math.min(s.assistants, s.lanes);
  return `<div><div class="toggle-row panel panel__pad"><span><span style="display:block">${t('pv.speed')}</span><span class="small muted">${t(n > 1 ? 'pv.speed.note' : 'pv.speed.one', { n: num(n) })}</span></span>
      <span class="switch"><input type="checkbox" data-change="pv-speed" data-fk="speed" ${on ? 'checked' : ''} aria-label="${esc(t('pv.speed'))}"><span class="switch__track"></span><span class="switch__thumb"></span></span></div>
    ${on && n > 1 ? `<p class="ac-note ac-note--caution small" style="margin-top:8px">${icon('warn', 'icon--sm')}<span>${t('pv.speed.warn', { n: num(n) })}</span></p>` : ''}</div>`;
}

function command(verb, sel) {
  const ids = sel && sel.cards ? sel.cards : [];
  const what = sel && sel.kind === 'step' ? `--step ${sel.step}` : ids.slice(0, 3).join(' ') + (ids.length > 3 ? ' …' : '');
  return `eaos ${verb} ${what} --preview`;
}

function snapshotSheet(verb) {
  return {
    title: esc(contract.verbOf(verb) ? L(contract.verbOf(verb).label) : verb),
    body: `<p>${esc(L(contract.SNAPSHOT.text))}</p><div class="code" style="padding:12px 16px">${esc(contract.SNAPSHOT.command)}</div>
      <button class="btn btn--secondary" data-act="copy" data-text="${esc(contract.SNAPSHOT.command)}">${icon('copy')}${t('copy')}</button>`,
  };
}

sheet('verb', {
  needs: ['cards'],
  kind: 'drawer',
  render(arg, query, own) {
    const [verb, ...rest] = arg.split(':');
    if (offline()) return snapshotSheet(verb);
    if (!own.selection) { own.selection = selectionOf(rest.join(':')); own.place = {}; }
    if (!own.preview && !own.asking && !own.problem) ask(verb, own);
    const p = own.preview, fix = verb === 'fix';
    const count = p ? p.cards.length : own.selection && own.selection.cards ? own.selection.cards.length : 0;
    const title = t('pv.title.' + verb, { problems: tn('pl.problem', count) });
    const cmd = command(verb, own.selection);
    const request = p && p.handoff && p.handoff.request ? L(p.handoff.request) : cmd;
    if (!p) {
      return {
        title: esc(title), sub: `<span class="free-band">${icon('check', 'icon--sm')}${t('free')}</span>`,
        body: `<p>${t('pv.does.' + verb)}</p>${own.problem ? `<p class="small" role="alert">${icon('warn', 'icon--sm')} ${esc(own.problem)}</p>` : `<p class="small muted" role="status" aria-busy="true">${t('pv.updating')}</p>`}`,
        foot: `<button class="btn btn--primary btn--block" disabled>${esc(t('pv.start', { title }))}</button>
          <button class="btn btn--quiet btn--block" data-act="copy" data-text="${esc(cmd)}">${icon('copy')}${t('pv.copy')}</button>`,
      };
    }
    const blocked = !p.confirm || !p.cards.length || (p.where && p.where.problem) || own.busy || (!p.assistant && contract.verbOf(verb).needs_assistant);
    return {
      title: esc(title),
      sub: `<span class="free-band">${icon('check', 'icon--sm')}${t('free')}</span>`,
      body: `
        <p>${t('pv.does.' + verb)}</p>
        ${own.moved ? `<p class="small" role="status">${icon('warn', 'icon--sm')} ${t('pv.moved')}</p>` : ''}
        ${cardsHTML(p)}
        <dl class="facts">
          <dt>${t('pv.files')}</dt><dd>${esc(tn('pl.file', p.files.length))}</dd>
          ${p.batches.length ? `<dt>${t('pv.batches')}</dt><dd>${esc(t('pv.batches.v', { batches: tn('pl.batch', p.batches.length) }))}</dd>` : ''}
          <dt>${t('pv.estimate')}</dt><dd>${esc(estimate(p))}<span class="small muted" style="display:block">${esc(L(p.estimate.basis))}</span></dd>
          <dt>${t('pv.risk')}</dt><dd><span class="tag ${p.risk.level === 'high' ? 'tag--caution' : 'tag--state'}">${t('pv.risk.' + p.risk.level)}</span> <span class="small ink-2">${esc(L(p.risk.why))}</span></dd>
          <dt>${t('pv.fail')}</dt><dd class="small">${esc(L(p.on_failure))}</dd>
        </dl>
        ${fix && p.where ? whereHTML(p.where, own) : ''}
        ${assistantsHTML(p, own)}
        ${fix && p.speed ? speedHTML(p.speed, own) : ''}
        ${fix ? `<div class="toggle-row panel panel__pad"><span><span style="display:flex;gap:8px;align-items:center">${icon('seal', 'icon--sm')}${t('pv.auto')}</span><span class="small muted">${t('pv.auto.note')}</span></span>
            <span class="switch"><input type="checkbox" data-change="pv-auto" data-fk="auto" ${own.auto ? 'checked' : ''} aria-label="${esc(t('pv.auto'))}"><span class="switch__track"></span><span class="switch__thumb"></span></span></div>` : ''}
        ${p.needs_consent ? `<p class="small ink-2">${icon('app', 'icon--sm')} ${t('pv.consent')}</p>` : ''}
        ${p.assistant ? `<p class="small ink-2">${t('pv.cost')}</p>` : ''}
        ${p.irreversible ? `<p class="small" role="note">${icon('warn', 'icon--sm')} ${t('pv.irreversible')}</p>` : ''}
        <details><summary class="link" style="cursor:pointer;min-height:44px;display:inline-flex;align-items:center;gap:6px">${icon('terminal', 'icon--sm')}${t('pv.terminal')}</summary>
          <div class="code" style="padding:12px 16px;margin-top:8px">${esc(cmd)}</div></details>`,
      foot: `${own.refused ? `<p class="small" role="alert">${icon('warn', 'icon--sm')} ${esc(own.refused)}</p>` : ''}
        <button class="btn btn--primary btn--block" data-act="verb-start" data-fk="verb-start" ${blocked ? 'disabled' : ''}>${esc(own.busy ? t('pv.starting') : t('pv.start', { title }))}</button>
        <button class="btn btn--quiet btn--block" data-act="copy" data-text="${esc(request)}">${icon('copy')}${t('pv.copy')}</button>
        ${p.confirm ? `<p class="sheet__fine">${esc(t('pv.valid', { time: expiresAt(p.confirm.expires) }))}</p>` : ''}`,
    };
  },
  after(el, arg, own) {
    const d = el.querySelector('details[data-where]');
    if (d) d.addEventListener('toggle', () => { own.whereOpen = d.open; });
  },
});

act('pv-auto', el => again({ auto: el.checked }));
act('pv-speed', el => { local().speed = el.checked; rerenderSheet(); });
act('pv-asst', el => again({ assistant: el.value }));
act('pv-base', el => again({ place: { base: el.value, deliver_as: '' }, name: null }));
act('pv-into', el => again({ place: Object.assign({}, local().place, { merge_into: el.value }) }));
act('pv-continue', el => again({ place: Object.assign({}, local().place, { deliver_as: el.value }) }));
act('pv-mode', el => {
  const w = local().preview && local().preview.where;
  if (!w) return;
  const deliver = el.value === 'direct' ? (w.base ? w.base.branch : '') : el.value === 'continue' ? (w.continuable[0] ? w.continuable[0].name : '') : '';
  again({ place: Object.assign({}, local().place, { deliver_as: deliver }), name: null });
});
act('pv-name', el => { local().name = el.value.trim(); rerenderSheet(); });
act('pv-name-go', () => { const own = local(); again({ place: Object.assign({}, own.place, { deliver_as: own.name }) }); });

act('verb-start', async el => {
  const own = local(), [, verb] = (parseHash().query.sheet || '').split(':');
  const p = own.preview;
  if (el.disabled || !p || !p.confirm || own.busy || !verb) return;
  own.busy = true; rerenderSheet();
  const w = p.where;
  const start = Object.assign(body(verb, own), {
    action: verb, confirm: p.confirm.token, assistant: own.assistant || (p.assistant && p.assistant.id) || undefined,
    // the place the preview showed, its base commit pinned: a branch that moved since is refused, never built on
    where: w && w.base ? Object.assign({}, own.place, { base: w.base.branch, base_commit: w.base.commit, deliver_as: w.deliver_as || undefined, merge_into: w.merge_into || undefined }) : undefined,
  });
  try {
    const run = await client.start(start);
    const title = t('pv.title.' + verb, { problems: tn('pl.problem', p.cards.length) });
    if (!parseHash().query.sheet.includes(':TASK-')) selection.clearSelection();
    closeSheetThen(() => {
      store.refresh();
      refresh();
      toast(t(run.state === 'queued' ? 'toast.queued' : 'toast.started', { title }), { link: { href: href('/activity/run/' + enc(run.id)), text: t('toast.follow') } });
    });
  } catch (e) {
    if (e instanceof ActionError && e.needs === 'preview') { again({ moved: true }); return; }
    Object.assign(own, { busy: false, refused: e instanceof ActionError ? e.message : String(e) });
    rerenderSheet();
  }
});
