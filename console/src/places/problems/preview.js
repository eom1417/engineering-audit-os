// C-03 The verb preview (FIX-01..06; G2, G3, G4, G12): Fix, Verify, Explain or Plan over a selection, one sheet for
// the four. It asks the server for the preview (POST /api/actions/<verb>/preview: never changes anything) and shows
// what will happen: the problems in it and those left out with why, the files, the batches, the time, the risk, what
// happens on failure, where a Fix is built and delivered, who runs it; then Start sends exactly that preview's choices
// with its confirm token (POST /api/runs). A choice that changes (the assistant, where, accept by itself) asks for the
// preview again, since the token is bound to it. Address: ?sheet=verb:<verb>[:fixable | :assistant | :<problem> |
// :step:<id>]; without a target, the current selection.
import {
  t, tn, L, num, esc, rich, icon, code, sev, href, assistantPicker, estimate, expiresAt, sheet, act, rerenderSheet, local, parseHash, closeSheetThen,
  toast, refresh, offline, model, selection, store, client, ActionError, contract, prefs, terminalFold, toggleRow, lockLine, radio, facts,
  titledBlock,
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
  return `${titledBlock(`${t('pv.included')} (${num(p.cards.length)})`, `
    <div class="panel rows">${shown.map(c => `<div class="row" style="min-height:48px">${c.severity ? sev(c.severity, false) : ''}<span class="row__main small">${code(c.id)} ${rich(L(c.title || ''))}</span></div>`).join('')}
    ${p.cards.length > 6 ? `<div class="row small muted" style="min-height:44px">+ ${esc(tn('pl.problem', p.cards.length - 6))}</div>` : ''}</div>`)}
    ${p.left_out.length ? titledBlock(`${t('pv.left')} (${num(p.left_out.length)})`, `<div class="panel rows">${p.left_out.slice(0, 8).map(r => `<div class="row small" style="min-height:44px">${code(r.id)}<span class="row__main muted">${esc(prefs.lang === 'ar' && r.why_ar ? r.why_ar : r.why)}</span></div>`).join('')}</div>`) : ''}`;
}

function radios(name, rows, picked, act) {
  return `<div class="opts mt-2">${rows.map(b => radio({ name, value: b.name, 'data-change': act, 'data-fk': `${name}-${b.name}`, checked: b.name === picked, disabled: !!b.blocked },
    lockLine(code(b.name), b.blocked), esc(b.blocked ? L(b.blocked) : b.note || b.short || ''))).join('')}</div>`;
}

/** Where a Fix is built, the branch its fixes arrive on and the branch Accept merges them into (a protected branch is
 *  shown with its reason, never choosable). */
function whereHTML(w, own) {
  const base = w.base ? w.base.branch : '';
  const mode = w.mode || 'new';
  return titledBlock(t('pv.where'), `<div class="panel panel__pad">${facts([
      [t('pv.base'), baseFact(w, base)],
      [t('pv.deliver'), deliverFact(w, mode, base)],
      mode === 'direct' ? '' : mergeFact(w),
    ])}
    ${w.problem ? `<p class="small" role="note">${icon('warn', 'icon--sm')} ${esc(L(w.problem))}</p>` : ''}
    <details class="mt-2" ${own.whereOpen ? 'open' : ''} data-where><summary class="link" style="cursor:pointer;min-height:44px;display:inline-flex;align-items:center">${t('pv.change')}</summary>
      ${changeHTML(w, own, base, mode)}
    </details></div>`);
}

/** The delivery modes this place offers: a new branch, continuing one, or straight onto the base when allowed. */
function modesOf(w, base) {
  return [['new', t('pv.deliver.new')]].concat(w.continuable && w.continuable.length ? [['continue', t('pv.deliver.continue')]] : [])
    .concat(!w.direct_blocked && base ? [['direct', t('pv.deliver.direct', { branch: base })]] : []);
}

function baseFact(w, base) {
  return `${code(base)} ${w.base ? code(w.base.short) : ''}${w.base && !w.base.checked_out ? ` <span class="small muted">${t('pv.base.notopen')}</span>` : ''}`;
}

function deliverFact(w, mode, base) {
  return mode === 'direct' ? esc(t('pv.deliver.direct', { branch: base })) : `${mode === 'new' ? t('pv.deliver.new') : t('pv.deliver.continue')} ${code(w.deliver_as || '')}`;
}

function mergeFact(w) {
  return `<dt>${t('pv.merge')}</dt><dd>${code(w.merge_into || '')} ${w.merge_into && w.base && w.merge_into === w.base.branch ? `<span class="small muted">${t('cf.open_folder')}</span>` : ''}</dd>`;
}

/** The place's choices, folded: the base, the delivery mode (with the new branch's name) and the branch to merge into. */
function changeHTML(w, own, base, mode) {
  return `<div class="block-title mt-2">${t('pv.base')}</div>${radios('base', w.branches, base, 'pv-base')}
      <div class="block-title mt-3">${t('pv.deliver')}</div>
      <div class="opts">${modesOf(w, base).map(([id, label]) => radio({ name: 'mode', value: id, 'data-change': 'pv-mode', 'data-fk': `mode-${id}`, checked: id === mode }, esc(label))).join('')}</div>
      ${mode === 'new' ? nameHTML(w, own) : ''}
      ${mode === 'continue' ? radios('cont', w.continuable, w.deliver_as, 'pv-continue') : ''}
      ${mode === 'direct' ? `<p class="small ink-2">${esc(t('pv.direct.note', { branch: base }))}</p>` : `<div class="block-title mt-3">${t('pv.merge')}</div>${radios('into', w.branches, w.merge_into, 'pv-into')}`}`;
}

function nameHTML(w, own) {
  return `<label class="field mt-2"><span class="sr-only">${t('pv.deliver.name')}</span><input class="input mono" dir="ltr" id="pv-name" data-fk="pv-name" value="${esc(own.name != null ? own.name : w.deliver_as || '')}" data-input="pv-name"></label>
        ${own.name && own.name !== w.deliver_as ? `<button class="btn btn--secondary btn--sm mt-2" data-act="pv-name-go">${t('pv.update')}</button>` : ''}`;
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
  return `<div>${toggleRow(t('pv.speed'), t(n > 1 ? 'pv.speed.note' : 'pv.speed.one', { n: num(n) }), { 'data-change': 'pv-speed', 'data-fk': 'speed', checked: on }, { cls: 'panel panel__pad' })}
    ${on && n > 1 ? `<p class="ac-note ac-note--caution small mt-2">${icon('warn', 'icon--sm')}<span>${t('pv.speed.warn', { n: num(n) })}</span></p>` : ''}</div>`;
}

function command(verb, sel) {
  const ids = sel && sel.cards ? sel.cards : [];
  const what = sel && sel.kind === 'step' ? `--step ${sel.step}` : ids.slice(0, 3).join(' ') + (ids.length > 3 ? ' …' : '');
  return `eaos ${verb} ${what} --preview`;
}

function snapshotSheet(verb) {
  return {
    title: esc(contract.verbOf(verb) ? L(contract.verbOf(verb).label) : verb),
    body: `<p>${esc(L(contract.SNAPSHOT.text))}</p><div class="code pad-3-4">${esc(contract.SNAPSHOT.command)}</div>
      <button class="btn btn--secondary" data-act="copy" data-text="${esc(contract.SNAPSHOT.command)}">${icon('copy')}${t('copy')}</button>`,
  };
}

/** How many problems the title counts: the preview's, else the selection's while it is asked for. */
function countOf(p, own) {
  return p ? p.cards.length : own.selection && own.selection.cards ? own.selection.cards.length : 0;
}

/** The sheet while its preview is asked for, or after it was refused: Start stays off, the command can be copied. */
function waitingSheet(verb, own, title, cmd) {
  return {
    title: esc(title), sub: `<span class="free-band">${icon('check', 'icon--sm')}${t('free')}</span>`,
    body: `<p>${t('pv.does.' + verb)}</p>${own.problem ? `<p class="small" role="alert">${icon('warn', 'icon--sm')} ${esc(own.problem)}</p>` : `<p class="small muted" role="status" aria-busy="true">${t('pv.updating')}</p>`}`,
    foot: `<button class="btn btn--primary btn--block" disabled>${esc(t('pv.start', { title }))}</button>
          <button class="btn btn--quiet btn--block" data-act="copy" data-text="${esc(cmd)}">${icon('copy')}${t('pv.copy')}</button>`,
  };
}

function factsHTML(p) {
  return facts([
      [t('pv.files'), esc(tn('pl.file', p.files.length))],
      p.batches.length ? [t('pv.batches'), esc(t('pv.batches.v', { batches: tn('pl.batch', p.batches.length) }))] : '',
      [t('pv.estimate'), `${esc(estimate(p))}<span class="small muted" style="display:block">${esc(L(p.estimate.basis))}</span>`],
      [t('pv.risk'), `<span class="tag ${p.risk.level === 'high' ? 'tag--caution' : 'tag--state'}">${t('pv.risk.' + p.risk.level)}</span> <span class="small ink-2">${esc(L(p.risk.why))}</span>`],
      [t('pv.fail'), esc(L(p.on_failure)), 'small'],
    ]);
}

/** The choices and notes under the facts: a Fix's place, the assistant, a Fix's speed and accept-by-itself. */
function choicesHTML(fix, p, own) {
  return `${fix && p.where ? whereHTML(p.where, own) : ''}
        ${assistantsHTML(p, own)}
        ${fix && p.speed ? speedHTML(p.speed, own) : ''}
        ${fix ? autoHTML(own) : ''}
        ${p.needs_consent ? `<p class="small ink-2">${icon('app', 'icon--sm')} ${t('pv.consent')}</p>` : ''}
        ${p.assistant ? `<p class="small ink-2">${t('pv.cost')}</p>` : ''}
        ${p.irreversible ? `<p class="small" role="note">${icon('warn', 'icon--sm')} ${t('pv.irreversible')}</p>` : ''}`;
}

function autoHTML(own) {
  return toggleRow(t('pv.auto'), t('pv.auto.note'), { 'data-change': 'pv-auto', 'data-fk': 'auto', checked: own.auto }, { icon: 'seal', cls: 'panel panel__pad' });
}

/** Start is off without a token or problems, while the place has a problem, while starting, or without an assistant
 *  the verb needs. */
function blockedOf(verb, p, own) {
  return !p.confirm || !p.cards.length || (p.where && p.where.problem) || own.busy || (!p.assistant && contract.verbOf(verb).needs_assistant);
}

function footHTML(verb, p, own, title, cmd) {
  const request = p.handoff && p.handoff.request ? L(p.handoff.request) : cmd;
  return `${own.refused ? `<p class="small" role="alert">${icon('warn', 'icon--sm')} ${esc(own.refused)}</p>` : ''}
        <button class="btn btn--primary btn--block" data-act="verb-start" data-fk="verb-start" ${blockedOf(verb, p, own) ? 'disabled' : ''}>${esc(own.busy ? t('pv.starting') : t('pv.start', { title }))}</button>
        <button class="btn btn--quiet btn--block" data-act="copy" data-text="${esc(request)}">${icon('copy')}${t('pv.copy')}</button>
        ${p.confirm ? `<p class="sheet__fine">${esc(t('pv.valid', { time: expiresAt(p.confirm.expires) }))}</p>` : ''}`;
}

sheet('verb', {
  needs: ['cards'],
  kind: 'drawer',
  render(arg, query, own) {
    const [verb, ...rest] = arg.split(':');
    if (offline()) return snapshotSheet(verb);
    if (!own.selection) { own.selection = selectionOf(rest.join(':')); own.place = {}; }
    if (!own.preview && !own.asking && !own.problem) ask(verb, own);
    const p = own.preview;
    const title = t('pv.title.' + verb, { problems: tn('pl.problem', countOf(p, own)) });
    const cmd = command(verb, own.selection);
    if (!p) return waitingSheet(verb, own, title, cmd);
    return {
      title: esc(title),
      sub: `<span class="free-band">${icon('check', 'icon--sm')}${t('free')}</span>`,
      body: `
        <p>${t('pv.does.' + verb)}</p>
        ${own.moved ? `<p class="small" role="status">${icon('warn', 'icon--sm')} ${t('pv.moved')}</p>` : ''}
        ${cardsHTML(p)}
        ${factsHTML(p)}
        ${choicesHTML(verb === 'fix', p, own)}
        ${terminalFold(esc(cmd))}`,
      foot: footHTML(verb, p, own, title, cmd),
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

/** What Start sends: the preview's choices with its confirm token. */
function startOf(verb, own, p) {
  const w = p.where;
  return Object.assign(body(verb, own), {
    action: verb, confirm: p.confirm.token, assistant: own.assistant || (p.assistant && p.assistant.id) || undefined,
    where: w && w.base ? placeOf(w, own) : undefined,
  });
}

/** The place the preview showed, its base commit pinned: a branch that moved since is refused, never built on. */
function placeOf(w, own) {
  return Object.assign({}, own.place, { base: w.base.branch, base_commit: w.base.commit, deliver_as: w.deliver_as || undefined, merge_into: w.merge_into || undefined });
}

function started(run, verb, p) {
  const title = t('pv.title.' + verb, { problems: tn('pl.problem', p.cards.length) });
  if (!parseHash().query.sheet.includes(':TASK-')) selection.clearSelection();
  closeSheetThen(() => {
    store.refresh();
    refresh();
    toast(t(run.state === 'queued' ? 'toast.queued' : 'toast.started', { title }), { link: { href: href('/activity/run/' + enc(run.id)), text: t('toast.follow') } });
  });
}

function startRefused(e, own) {
  if (e instanceof ActionError && e.needs === 'preview') { again({ moved: true }); return; }
  Object.assign(own, { busy: false, refused: e instanceof ActionError ? e.message : String(e) });
  rerenderSheet();
}

act('verb-start', async el => {
  const own = local(), [, verb] = (parseHash().query.sheet || '').split(':');
  const p = own.preview;
  if (el.disabled || !p || !p.confirm || own.busy || !verb) return;
  own.busy = true; rerenderSheet();
  const start = startOf(verb, own, p);
  try {
    started(await client.start(start), verb, p);
  } catch (e) {
    startRefused(e, own);
  }
});
