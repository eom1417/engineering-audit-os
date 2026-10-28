// S-02 Waiting for you, S-03 one waiting item, and the owner-only confirm sheets for Accept and Reject (DEC-01,
// DEC-06..11, FIX-09, FIX-11..13, SGN-03). Everything that needs the owner's word, and nothing else: the branches EAOS
// delivered (live runs that handed a branch over and wait for a decision), the report's decisions with the answers
// saved in the live console, the sign-in a check waits for and the questions runs ask (their own screens, builder A).
import {
  t, tn, L, num, esc, rich, md, icon, code, diffLines, href, fmtWhen, expiresAt, screen, sheet, act, refresh, toast, closeSheetThen, rerenderSheet, local, offline, parseHash,
  S, live, store, model, client, ActionError, derive, chk, ac, rowWords, smallFold, terminalFold, toggleRow,
} from 'eaos';
import { ownTyped, sendAnswer, sendBlocked, ownBox, whyFold, choice } from './answer.js';

const NEEDS = ['decisions', 'cards'];
const enc = encodeURIComponent;
const decidedRuns = () => live.runs.filter(r => r.outcome && r.result && r.result.branch);
const runOf = id => live.runs.find(r => r.id === id) || null;
const minutes = run => { const s = derive.seconds(run.started, run.ended); return s == null ? null : Math.max(1, Math.round(s / 60)); };

function sourceLine(d) {
  const blocks = d.blocks && d.blocks.length && d.source === 'structure' ? `<span class="tag tag--state">${esc(t('wt.blocks', { steps: d.blocks.join(', ') }))}</span>` : '';
  return `<span class="tag tag--owner">${icon('seal')}${t('owner.only')}</span><span class="muted small">${esc(t('wt.from.' + d.source))}</span>${blocks}`;
}

function savedHTML(d) {
  const saved = d.saved;
  const opt = d.options.find(o => o.id === (saved ? saved.option : d.answer));
  const answer = opt ? L(opt.label) : saved ? saved.text || saved.label : '';
  const queued = saved && ['queued', 'running'].includes(saved.status);
  return `<div class="saved" role="status"><b>${icon('check', 'icon--sm')} ${esc(t('wt.saved', { answer }))}</b><span>${t('wt.saved.note')}</span>
    ${queued ? `<span class="state">${icon('clock', 'icon--sm')}${t('wt.saved.review')}</span>` : ''}</div>`;
}

// a decision's source line and question (a link to its own screen in the list)
function cardHead(d, full) {
  return `<div class="wcard__meta">${sourceLine(d)}</div>
    <h3 class="${full ? 'sr-only' : 'wcard__q'}" id="wq-${esc(d.id)}">${full ? '' : `<a href="${href('/waiting/' + enc(d.id))}" style="color:inherit;text-decoration:none">`}${rich(L(d.question))}${full ? '' : '</a>'}</h3>`;
}
// what EAOS recommends, as an AI block for the screens' and cards' decisions
function recoHTML(d) {
  if (!d.recommendation) return '';
  return d.source === 'screens' || d.source === 'card'
    ? `<div class="ai-block"><span class="ai-block__label">${icon('ai', 'icon--sm')}${t('wt.reco')}</span>${md(L(d.recommendation))}</div>`
    : `<div class="small ink-2"><b class="ink-2">${t('wt.reco')}:</b> ${rich(L(d.recommendation))}</div>`;
}
// Send, the own-words button, and offline the command that answers instead
function cardActions(d, lock, chosen, ownOpen) {
  const recommended = d.recommended;
  const sending = S.sending[d.id];
  const sendOff = sendBlocked(d.id, lock, chosen, ownOpen);
  return `<div class="wcard__actions">
      <button class="btn btn--primary" data-act="send" data-id="${esc(d.id)}" data-fk="send-${esc(d.id)}" ${sendOff ? 'disabled' : ''} aria-describedby="${sendOff ? 'pick-' + esc(d.id) : ''}">${sending ? t('wt.sending') : t('wt.send')}</button>
      ${ownOpen || lock ? '' : `<button class="btn btn--plain" data-act="own-open" data-id="${esc(d.id)}">${t('wt.own')}</button>`}
      ${lock ? `<button class="btn btn--plain" data-act="copy" data-text="${esc(`eaos answer ${d.id} ${recommended || ''}`.trim())}">${icon('copy')}${t('wt.decided.copy')}</button>` : ''}
      <span class="sr-only" id="pick-${esc(d.id)}">${t('wt.pick')}</span>
    </div>`;
}

function decisionCard(d, full) {
  const head = cardHead(d, full);
  if (d.state === 'answered') return `<article class="panel wcard wcard--done" id="w-${esc(d.id)}" aria-labelledby="wq-${esc(d.id)}">${head}${savedHTML(d)}</article>`;
  const lock = offline();
  const recommended = d.recommended;
  const opts = d.options.slice().sort((a, b) => (a.id === recommended ? -1 : b.id === recommended ? 1 : 0));
  const chosen = S.chosen[d.id];
  const reco = recoHTML(d);
  const radios = opts.map(o => choice(d.id, o, chosen, lock, rich(L(o.label)) + (o.id === recommended ? `<span class="tag tag--you">${t('wt.recommended')}</span>` : ''))).join('');
  const ownOpen = S.ownOpen[d.id];
  const own = ownOpen ? ownBox(d.id, 'own', t('wt.own.note')) : '';
  return `<article class="panel wcard" id="w-${esc(d.id)}" aria-labelledby="wq-${esc(d.id)}">
    ${head}${reco}
    <fieldset class="opts" style="border:0;padding:0;margin:0"><legend class="sr-only">${rich(L(d.question))}</legend>${radios}</fieldset>
    ${own}
    ${lock ? `<p class="small muted">${icon('lock', 'icon--sm')} ${t('wt.offline')}</p>` : ''}
    ${cardActions(d, lock, chosen, ownOpen)}
    ${whyFold(t('wt.why.' + d.source) + (d.asked_at ? ' ' + esc(t('wt.asked', { when: fmtWhen(d.asked_at) })) + '.' : ''))}
  </article>`;
}

/** The files a delivered branch changes (GET /api/branches/detail), read when its fold opens; the fold stays open
 *  through the redraws. */
const details = {}, opened = new Set();
function diffHTML(run) {
  const got = details[run.id];
  if (!got) return `<p class="small muted" aria-busy="true">${t('st.loading')}</p>`;
  if (got.error) return `<p class="small muted">${esc(got.error)}</p>`;
  const lines = got.diff ? got.diff.split('\n').slice(0, 400) : [];
  return `<ul class="rows">${got.files.map(f => `<li class="row small" style="min-height:40px">${code(f.status)} ${code(f.path)}</li>`).join('')}</ul>
    ${lines.length ? `<div class="code diff mt-2">${diffLines(lines)}</div>` : ''}
    ${got.diff_cut || (got.diff && got.diff.split('\n').length > 400) ? `<p class="small muted">${t('wt.fix.cut')}</p>` : ''}`;
}

function facts(run) {
  const r = run.result || {}, d = r.diff_stat, tests = r.tests;
  return `<div class="wcard__facts">
    ${tests ? `<div class="wcard__fact ${tests.passed ? 'wcard__fact--ok' : ''}">${icon(tests.passed ? 'check' : 'warn')}<span>${esc(tests.passed ? t('wt.fix.tests.ok') : t('wt.fix.tests.no'))}${tests.summary ? ` <span class="muted">${esc(tests.summary)}</span>` : ''}</span></div>` : ''}
    ${d ? `<div class="wcard__fact">${icon('file')}<span>${esc(tn('pl.file_changed', d.files))} <bdi dir="ltr" class="num">+${num(d.insertions)} −${num(d.deletions)}</bdi></span></div>` : ''}
    ${run.cards && run.cards.length ? `<div class="wcard__fact">${icon('problems')}<span>${esc(t('wt.fix.closes', { problems: tn('pl.problem', run.cards.length) }))} ${run.cards.slice(0, 12).map(c => `<a class="link" href="${href('/problems/' + enc(c))}">${code(c)}</a>`).join(' ')}${run.cards.length > 12 ? ` ${esc(t('wt.fix.more', { n: num(run.cards.length - 12) }))}` : ''}</span></div>` : ''}
  </div>`;
}

function branchCard(run, full) {
  const lock = offline();
  const took = minutes(run);
  return `<article class="panel wcard" id="w-${esc(run.id)}" aria-labelledby="wq-${esc(run.id)}">
    <div class="wcard__meta"><span class="tag tag--owner">${icon('seal')}${t('owner.only')}</span>
      <span class="muted small">${esc(t('wt.fix.by', { who: model.assistantName(run.assistant) || 'EAOS', when: fmtWhen(run.ended || run.created), minutes: took ? tn('pl.minute', took) : '' }))}</span></div>
    <div>
      <h3 class="${full ? 'sr-only' : 'wcard__q'}" id="wq-${esc(run.id)}">${full ? '' : `<a href="${href('/waiting/' + enc(run.id))}" style="color:inherit;text-decoration:none">`}${t('wt.fix.title')}${full ? '' : '</a>'}</h3>
      <div class="mt-0-5">${code(run.result.branch)}</div>
    </div>
    ${facts(run)}
    <p class="small ink-2">${t('wt.fix.unchanged')}</p>
    ${smallFold('code', t('wt.fix.see'), diffHTML(run), { cls: 'bleed line-top line-bottom', attrs: `data-diff="${esc(run.id)}" ${opened.has(run.id) ? 'open' : ''}` })}
    <div class="wcard__actions">
      ${lock ? `<p class="small muted">${icon('lock', 'icon--sm')} ${t('wt.offline')}</p>`
        : `<button class="btn btn--primary" data-act="sheet" data-sheet="accept:${esc(run.id)}">${icon('seal')}${t('wt.accept')}</button>
           <button class="btn btn--secondary" data-act="sheet" data-sheet="reject:${esc(run.id)}">${t('wt.reject')}</button>`}
      <a class="btn btn--plain" href="${href('/activity/run/' + enc(run.id))}">${t('wt.fix.run')}</a>
    </div>
  </article>`;
}

function outcomeLine(run) {
  return t(run.outcome === 'accepted' ? 'wt.done.accepted' : 'wt.done.rejected', { when: fmtWhen(run.decided || run.ended), target: (run.context && run.context.checkout) || '' });
}

function decided() {
  const rows = decidedRuns().slice(0, 10).map(run => `<li class="row">${rowWords(code(run.result.branch), esc(outcomeLine(run)))}</li>`);
  model.decisions().filter(d => d.state === 'answered').forEach(d => {
    const opt = d.options.find(o => o.id === (d.saved ? d.saved.option : d.answer));
    const answer = opt ? L(opt.label) : d.saved ? d.saved.text || '' : '';
    rows.push(`<li class="row">${rowWords(rich(L(d.question)), esc(t('wt.decided.row', { answer })) + (d.saved && d.saved.at ? `. ${esc(t('wt.decided.by', { when: fmtWhen(d.saved.at) }))}` : ''))}
      <button class="btn btn--icon" data-act="copy" data-text="${esc(`"${L(d.question)}" — ${answer} (eaos answer ${d.id} ${opt ? opt.id : ''})`)}" aria-label="${esc(t('wt.decided.copy'))}">${icon('copy')}</button></li>`);
  });
  // nothing decided: a plain row, no arrow promising details that are not there
  if (!rows.length) return `<section class="section"><div class="panel rows" id="decided"><div class="row">${rowWords(t('wt.decided'), t('wt.decided.none'))}</div></div></section>`;
  return `<section class="section"><details class="panel fold" id="decided" ${parseHash().path === '/waiting/decided' ? 'open' : ''}>
    ${ac.foldHead(t('wt.decided'), esc(tn('pl.decided', rows.length)))}
    <ul class="rows bleed bleed--end">${rows.join('')}</ul></details></section>`;
}

function group(id, title, count, body) {
  return `<section class="wgroup" aria-labelledby="g-${id}"><div class="wgroup__head"><h2 id="g-${id}">${title}</h2>${count ? `<span class="count" aria-hidden="true">${num(count)}</span>` : ''}</div>${body}</section>`;
}

function listPage(ctx) {
  const wc = ctx.state === 'empty' ? 0 : model.waitingCount();
  const branches = model.waitingBranches();
  const open = model.waitingDecisions();
  const groups = [];
  if (live.signIn && live.signIn.asked) {
    groups.push(group('signin', t('wt.g.signin'), 1, `<article class="panel wcard"><div class="wcard__meta"><span class="tag tag--owner">${icon('seal')}${t('owner.only')}</span></div>
      <h3 class="wcard__q">${t('wt.signin.q')}</h3><p class="small ink-2">${t('wt.signin.sub.live')}</p>
      <div class="wcard__actions"><a class="btn btn--primary" href="${href('/waiting/sign-in')}">${t('wt.signin.act')}</a></div></article>`));
  }
  if (branches.length) groups.push(group('fixes', t('wt.g.fixes'), branches.length, `<div class="stack-3">${branches.map(run => branchCard(run, false)).join('')}</div>`));
  if (open.length) groups.push(group('dec', t('wt.g.decisions'), open.length, `<div class="stack-3">${open.map(d => decisionCard(d, false)).join('')}</div>`));
  const asked = live.questions.length;
  const qRow = `${icon(asked ? 'waiting' : 'info', 'muted')}${rowWords(esc(asked ? tn('pl.question_waits', asked) : t('wt.q.none')), t(asked ? 'wt.q.row.sub.live' : 'wt.q.row.sub'))}`;
  // only a waiting question opens; "no question" is a plain line without an arrow
  const questions = group('q', t('wt.g.questions'), asked, `<div class="panel rows">${asked ? `<a class="row" href="${href('/waiting/questions')}">${qRow}${icon('chev', 'icon--dir muted')}</a>` : `<div class="row">${qRow}</div>`}</div>`);
  return `<div class="page">
    <h1 class="lede">${esc(tn('pl.thing_waits', wc))}.</h1>
    <p class="guide">${t(wc ? 'wt.guide' : 'wt.empty.guide')}</p>
    ${groups.length ? `<div class="mt-8">${groups.join('')}</div>` : ''}
    <div class="mt-8">${questions}</div>
    ${decided()}
  </div>`;
}

function openDiff(main) {
  main.querySelectorAll('details[data-diff]').forEach(el => el.addEventListener('toggle', () => {
    const id = el.dataset.diff, run = runOf(id);
    if (el.open) opened.add(id); else opened.delete(id);
    if (!el.open || details[id] || !run || !client) return;
    client.branches.detail(run.result.branch).then(d => { details[id] = d; refresh(); }, e => { details[id] = { error: e.message }; refresh(); });
  }));
}

screen({ id: 'S-02', path: '/waiting', place: 'waiting', needs: NEEDS, title: () => t('wt.place'), render: listPage, after: openDiff });
screen({ id: 'S-02', path: '/waiting/decided', place: 'waiting', needs: NEEDS, title: () => t('wt.decided'), render: listPage, after: openDiff });

screen({
  id: 'S-03', path: '/waiting/:id', place: 'waiting', needs: NEEDS,
  title: () => t('wt.place'),
  after: openDiff,
  render(ctx) {
    const id = ctx.params.id;
    const run = runOf(id), d = model.decisions().find(x => x.id === id);
    let card = '', lede = esc(t('wt.place')), waits = false;
    if (run && run.result && run.result.branch) {
      lede = esc(t('wt.fix.title'));
      waits = store.awaitsApproval(run);
      card = waits ? branchCard(run, true) : `<div class="panel wcard wcard--done"><h3 class="wcard__q">${code(run.result.branch)}</h3><p class="small">${esc(run.outcome ? outcomeLine(run) : t('wt.fix.notwaiting'))}</p></div>`;
    } else if (d) {
      lede = rich(L(d.question));
      waits = d.state === 'waiting';
      card = decisionCard(d, true);
    }
    if (!card) card = `<div class="empty panel"><p class="empty__title">${esc(t(live.loaded || offline() ? 'pd.notfound' : 'st.loading', { id }))}</p><a class="btn btn--secondary" href="${href('/waiting')}">${t('wt.item.back')}</a></div>`;
    return `<div class="page">
      <a class="back" href="${href('/waiting')}">${icon('back', 'icon--dir')}${t('wt.item.back')}</a>
      <h1 class="lede mt-2">${lede}</h1>
      ${waits ? `<p class="guide">${t(run ? 'wt.item.guide.b' : 'wt.item.guide.q')}</p>` : ''}
      <div class="mt-5">${card}</div></div>`;
  },
});

/* ---------- answering a report decision (DEC-06, DEC-09) ---------- */
act('choose', el => { S.chosen[el.dataset.id] = el.value; refresh(); });
act('own-open', el => { S.ownOpen[el.dataset.id] = true; refresh(); const ta = document.getElementById('own-' + el.dataset.id); if (ta) ta.focus(); });
act('own', el => ownTyped(el, 'send'));
act('send', async el => {
  const id = el.dataset.id;
  const option = S.chosen[id] || null, text = (S.own[id] || '').trim() || null;
  const scope = store.scopeOf(id);
  if ((!option && !text) || !client || S.sending[id]) return;
  if (!scope) { toast(t('wt.send.stale'), { refusal: true }); store.refresh(); return; }
  await sendAnswer(id, async () => store.rememberDecision(await client.answerDecision(id, scope, option, text)));
});

/* ---------- the confirm sheets: owner-only, irreversible (FIX-11, FIX-12; G1, G2, G4, G8, G10) ----------
   Each asks the server for its preview first (POST /api/actions/accept|undo/preview: the confirm token, and for
   Accept where it merges); the act button unlocks only after "I understand", and sends the run's decision with that
   token (POST /api/runs/<id>/accept|undo). The server refuses a stale or missing token, a protected target and a
   branch that is not the newest waiting one, and the sheet says why. */
function ask(op, local) {
  if (local.asked || !client) return;
  local.asked = true;
  client.preview(op, { inputs: {} }).then(p => {
    local.preview = p;
    if (p.merge) { local.target = p.merge.target || ''; local.remove = p.merge.delete_after !== false; }
    rerenderSheet();
  }, e => { local.problem = e instanceof ActionError ? e.message : String(e); rerenderSheet(); });
}

function ackRow(kind, local) {
  return `<label class="ack">${chk(`data-change="ack" data-fk="ack-${kind}"`, !!local.ack, t('cf.ack.' + kind))}<span class="ack__text">${t('cf.ack.' + kind)}</span></label>`;
}

function validLine(local) {
  const c = local.preview && local.preview.confirm;
  return c ? `<p class="sheet__fine">${esc(t('cf.valid', { time: expiresAt(c.expires) }))}</p>` : '';
}

function blockedOf(local) {
  const merge = local.preview && local.preview.merge;
  const row = merge && merge.targets.find(x => x.name === local.target);
  return row && row.blocked ? row.blocked : null;
}

function foot(kind, local, danger) {
  const ready = local.preview && local.preview.confirm && !blockedOf(local);
  const said = local.refused || local.problem;
  const label = kind === 'accept' ? t('cf.do.accept', { target: local.target || '' }) : t('cf.do.reject');
  return `${said ? `<p class="small" role="alert" style="color:var(--danger)">${icon('warn', 'icon--sm')} ${esc(said)}</p>` : ''}
    ${ackRow(kind, local)}<div class="sheet__foot-row">
      <button class="btn btn--secondary" data-act="sheet-close" data-autofocus>${t('cancel')}</button>
      <button class="btn ${danger ? 'btn--danger' : 'btn--primary'}" data-act="do-decide" data-needs-ack data-op="${kind === 'accept' ? 'accept' : 'undo'}" data-fk="do-${kind}" ${ready && local.ack && !local.busy ? '' : 'disabled'} title="${esc(local.ack ? '' : t('cf.need_ack'))}">${kind === 'accept' ? icon('seal') : ''}${esc(local.busy ? t('cf.doing') : label)}</button></div>
    ${validLine(local)}`;
}

function missingRun(id) {
  return { title: esc(t('pd.notfound', { id })), body: `<p class="small ink-2">${t('wt.fix.notwaiting')}</p>` };
}
/** The run a confirm sheet decides and its preview asked, or what the sheet says instead (gone, or still loading). */
function deciding(id, op, local) {
  const run = runOf(id);
  if (!run || !store.awaitsApproval(run)) return { instead: live.loaded ? missingRun(id) : { title: esc(t('st.loading')), body: '' } };
  ask(op, local);
  return { run };
}

sheet('accept', {
  kind: 'dialog', confirm: true,
  render(id, query, local) {
    const { run, instead } = deciding(id, 'accept', local);
    if (instead) return instead;
    const merge = local.preview && local.preview.merge;
    const target = local.target || (merge && merge.target) || '';
    const blocked = blockedOf(local);
    const d = run.result.diff_stat;
    const into = merge && merge.targets.length > 1
      ? `<div class="opts">${merge.targets.map(x => `<label class="opt ${x.blocked ? 'opt--off' : ''}"><input type="radio" name="into" value="${esc(x.name)}" data-change="accept-into" data-fk="into-${esc(x.name)}" ${x.name === target ? 'checked' : ''} ${x.blocked ? 'disabled' : ''}>
          <span class="opt__dot"></span><span class="opt__text"><span class="opt__line">${code(x.name)}${x.blocked ? icon('lock', 'icon--sm muted') : ''}</span>
          <span class="opt__note">${esc(x.blocked ? L(x.blocked) : x.name === merge.target ? t('cf.into.own') : x.short)}</span></span></label>`).join('')}</div>`
      : `<div class="panel panel__pad"><span class="opt__line">${code(target)}${icon('lock', 'icon--sm muted')}</span><span class="opt__note">${t('cf.into.own')}</span></div>`;
    return {
      title: t('cf.accept.title', { target: code(target) }),
      body: `<div class="owner-band">${icon('seal')}<span><b>${t('owner.only')}</b>${t('cf.band')}</span></div>
        <p>${t('cf.accept.lede', { branch: code(run.result.branch), target: code(target) })}</p>
        ${local.preview ? `<div><div class="block-title">${t('cf.into')}</div>${into}</div>
        ${blocked ? `<p class="small" role="note">${icon('lock', 'icon--sm')} ${esc(L(blocked))}</p>` : ''}
        ${toggleRow(t('cf.delete'), t('cf.delete.note'), { 'data-change': 'accept-remove', checked: local.remove, 'data-fk': 'del-after' })}`
          : local.problem ? '' : `<p class="small muted" aria-busy="true">${t('cf.previewing')}</p>`}
        ${d ? `<div><div class="block-title">${t('cf.files')}</div><div class="wcard__fact">${icon('file')}<span>${esc(tn('pl.file_changed', d.files))} <bdi dir="ltr" class="num">+${num(d.insertions)} −${num(d.deletions)}</bdi></span></div></div>` : ''}
        ${run.result.tests ? `<div><div class="block-title">${t('cf.checks')}</div><div class="wcard__fact ${run.result.tests.passed ? 'wcard__fact--ok' : ''}">${icon(run.result.tests.passed ? 'check' : 'warn')}<span>${esc(run.result.tests.passed ? t('wt.fix.tests.ok') : t('wt.fix.tests.no'))}</span></div></div>` : ''}
        ${terminalFold('eaos accept' + (target ? ` --into ${esc(target)}` : ''))}`,
      foot: foot('accept', local, false),
    };
  },
});

sheet('reject', {
  kind: 'dialog', confirm: true,
  render(id, query, local) {
    const { run, instead } = deciding(id, 'undo', local);
    if (instead) return instead;
    const d = run.result.diff_stat;
    return {
      title: esc(t('cf.reject.title')),
      body: `<div class="owner-band">${icon('seal')}<span><b>${t('owner.only')}</b>${t('cf.band')}</span></div>
        <p>${t('cf.reject.lede', { branch: code(run.result.branch), files: esc(tn('pl.file', d ? d.files : 0)) })}</p>
        <p class="small ink-2">${t('cf.reject.kept')}</p>
        ${local.preview || local.problem ? '' : `<p class="small muted" aria-busy="true">${t('cf.previewing')}</p>`}
        ${terminalFold('eaos undo')}`,
      foot: foot('reject', local, true),
    };
  },
});

act('ack', el => { local().ack = el.checked; rerenderSheet(); });
act('accept-into', el => { local().target = el.value; rerenderSheet(); });
act('accept-remove', el => { local().remove = el.checked; rerenderSheet(); });
act('do-decide', async el => {
  const own = local(), id = parseHash().query.sheet.split(':').slice(1).join(':');
  const op = el.dataset.op, run = runOf(id);
  if (el.disabled || !run || !own.preview || !own.preview.confirm || own.busy) return;
  own.busy = true; rerenderSheet();
  try {
    const choice = op === 'accept' ? Object.assign(own.target ? { merge_into: own.target } : {}, { delete_after: !!own.remove }) : undefined;
    const next = await client.decide(run.id, op, own.preview.confirm.token, choice);
    store.patchRun(run.id, next);
    const branch = run.result.branch, target = own.target;
    closeSheetThen(() => {
      toast(op === 'accept' ? t('wt.accepted.toast', { branch, target }) : t('wt.rejected.toast', { branch }));
      store.refresh();
    });
  } catch (e) {
    // a used or stale token is spent: the next try asks for a new preview
    Object.assign(own, { busy: false, asked: false, preview: null, refused: e instanceof ActionError ? e.message : String(e) });
    rerenderSheet();
  }
});

