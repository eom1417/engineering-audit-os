// The users' experience (M10.8): <report>/experience/story.json (eaos/report/experience/document.py, from story.py),
// read once as a report file: each persona with its goals reached or stuck, one goal's story step by step with its
// pictures (?goal=, so only the goal opened reads its pictures), the difficulties ranked with their steps to reproduce
// and their fix card, the time per task, the support tickets and the replays. A check that did not try the experience
// says how to run it. Every text from the story is the app's or an assistant's: escaped (esc, rich), never trusted.
import { t, tn, num, esc, rich, code, icon, sev, href, prefs, data, refresh, offline, rowWords, facts } from 'eaos';
import { nm } from '../kit/kit.js';
import { figure } from '../kit/pictures.js';

const STORY = 'experience/story.json';
const STATUS_TAG = { reached: 'ok', stuck: 'danger', stopped: 'caution', blocked: 'caution', not_run: 'state' };
let told;   // undefined: not asked; null: being read; false: not there or unreadable; else the story

function read() {
  if (told === undefined) {
    told = null;
    data.reportFile(STORY).then(s => {
      try { told = s ? JSON.parse(s) : false; } catch { told = false; }
      refresh();
    });
  }
  return told;
}

const said = (o, key) => (prefs.lang === 'ar' && o[key + '_ar']) || o[key] || '';
const status = s => `<span class="tag tag--${STATUS_TAG[s] || 'state'}">${esc(t('rp.ex.status.' + (STATUS_TAG[s] ? s : 'not_run')))}</span>`;
const seconds = n => n == null ? '-' : esc(t('rp.ex.seconds', { n: num(Math.round(n)) }));
const goalHref = (query, name) => href('/report', { part: 'experience', goal: query.goal === name ? null : name });

function howToRun(why) {
  return nm(t('rp.ex.none'), `${t(why)} ${t('rp.ex.run')} ${code('eaos check --path experience')} ${t('rp.ex.run.mcp')} ${code('experience')}`);
}

function overview(s) {
  const reached = s.time.filter(g => g.status === 'reached').length;
  const replays = s.replays.summary || {};
  return facts([
    [t('rp.ex.goals'), esc(t('rp.ex.reached', { n: num(reached), all: num(s.time.length) }))],
    [t('rp.ex.difficulties'), num(s.difficulties.ranked.length)],
    [t('rp.ex.tickets'), num(s.tickets.length)],
    replays.green != null || replays.red != null ? [t('rp.ex.replays'), esc(t('rp.ex.replays.v', { green: num(replays.green || 0), red: num(replays.red || 0) }))] : null,
    s.seconds != null ? [t('rp.ex.total'), `${seconds(s.seconds)}${s.calls != null ? ' · ' + esc(tn('rp.ex.calls', s.calls)) : ''}`] : null,
  ]);
}

function step(st, n) {
  const what = [st.action, st.target, st.value ? `«${st.value}»` : null].filter(Boolean).join(' ');
  const pic = st.picture ? figure({ path: st.picture, width: 1280, height: 720 }, [], t('rp.ex.step', { n: num(n) })) : '';
  return `<li class="panel panel__pad rp-shot"><h4 class="h3">${esc(t('rp.ex.step', { n: num(n) }))}: ${rich(what)}</h4>
    ${st.why ? `<p class="small">${rich(st.why)}</p>` : ''}${st.landed ? `<p class="small muted">${t('rp.ex.landed')} ${rich(st.landed)}</p>` : ''}
    ${st.error ? `<p class="small" role="note">${icon('warn', 'icon--sm')} ${t('rp.ex.error')} ${rich(st.error)}</p>` : ''}${pic}</li>`;
}

function goalStory(g) {
  const friction = (g.friction || []).map(f => `<li class="small">${esc(t('rp.ex.step', { n: num(f.step) }))} · ${esc(t('rp.ex.kind.' + f.kind))}: ${rich(f.note)}</li>`).join('');
  return `<div class="rp-ex-story">${g.wanted ? `<p class="small"><b>${t('rp.ex.wanted')}</b> ${rich(g.wanted)}</p>` : ''}
    ${g.why ? `<p class="small"><b>${t('rp.ex.why')}</b> ${rich(g.why)}</p>` : ''}
    ${g.steps.length ? `<ol class="rp-shots rp-ex-steps">${g.steps.map((st, i) => step(st, i + 1)).join('')}</ol>` : `<p class="small muted">${t('rp.ex.nosteps')}</p>`}
    ${friction ? `<h4 class="h3">${t('rp.ex.friction')}</h4><ul class="rp-ex-list">${friction}</ul>` : ''}</div>`;
}

function persona(p, query) {
  const goals = p.goals.map(g => {
    const open = query.goal === g.name;
    return `<li><a class="row" href="${goalHref(query, g.name)}" ${open ? 'aria-current="true"' : ''}>${rowWords(code(g.name), `${seconds(g.seconds)} · ${esc(tn('rp.ex.steps', g.steps.length))}`, { title: 'small' })}${status(g.status)}${icon('chev', 'icon--sm icon--dir muted')}</a>
      ${open ? goalStory(g) : ''}</li>`;
  }).join('');
  return `<article class="panel panel__pad"><h3 class="h2">${rich(p.name)}${p.role ? ` <span class="small muted">(${rich(p.role)})</span>` : ''}</h3>
    ${p.about ? `<p class="small ink-2">${rich(p.about)}</p>` : ''}
    ${goals ? `<ul class="rows">${goals}</ul>` : `<p class="small muted">${t('rp.ex.nogoals')}</p>`}</article>`;
}

function difficulty(d) {
  const card = d.card ? `<a class="btn btn--quiet btn--sm" href="${href('/problems/' + encodeURIComponent(d.card))}">${t('rp.ex.card')} ${code(d.card)}</a>` : '';
  const repro = (d.repro || []).map(r => `<li class="small">${rich(r)}</li>`).join('');
  return `<li class="panel panel__pad rp-ex-diff"><h4 class="h3">${code(d.id)} ${rich(said(d, 'title') || d.note)}</h4>
    <p class="small">${sev(d.severity || 'low')} <span class="tag tag--${d.verdict === 'confirm' ? 'danger' : 'caution'}">${esc(t('rp.ex.verdict.' + (d.verdict === 'confirm' ? 'confirm' : 'doubt')))}</span> ${code(d.goal)}</p>
    ${d.why ? `<p class="small ink-2">${rich(d.why)}</p>` : ''}
    ${repro ? `<p class="small"><b>${t('rp.ex.repro')}</b></p><ol class="rp-ex-list">${repro}</ol>` : ''}
    ${said(d, 'fix') ? `<p class="small"><b>${t('rp.ex.fix')}</b> ${rich(said(d, 'fix'))}</p>` : ''}${card}</li>`;
}

function times(s) {
  return `<ul class="panel rows">${s.time.map(g => `<li class="row">${rowWords(code(g.name), `${rich(g.persona)} · ${seconds(g.seconds)}${g.calls != null ? ' · ' + esc(tn('rp.ex.calls', g.calls)) : ''}`, { title: 'small' })}${status(g.status)}</li>`).join('')}</ul>`;
}

function tickets(s) {
  return `<ul class="panel rows">${s.tickets.map(k => `<li class="row">${rowWords(`${code(k.id)} ${code(k.goal)}${k.escalated ? ` <span class="tag tag--caution">${t('rp.ex.escalated')}</span>` : ''}`, `<b>${t('rp.ex.asked')}</b> ${rich(k.asked)}`,
      { title: 'small', more: `<span class="row__meta" style="display:block"><b>${t('rp.ex.answer')}</b> ${k.answer ? rich(k.answer) : '-'}</span>` })}${k.after ? status(k.after) : ''}</li>`).join('')}</ul>`;
}

function replays(s) {
  const sum = s.replays.summary || {};
  const red = s.replays.red.map(r => `<li class="row">${rowWords(code(r.goal), rich(r.error || r.broken_at || ''), { title: 'small' })}<span class="tag tag--danger">${t('rp.ex.red')}</span></li>`).join('');
  return `<p class="small"><span class="tag tag--ok">${esc(t('rp.ex.green.n', { n: num(sum.green || 0) }))}</span> <span class="tag tag--danger">${esc(t('rp.ex.red.n', { n: num(sum.red || 0) }))}</span></p>
    ${red ? `<ul class="panel rows">${red}</ul>` : ''}`;
}

const block = (title, body) => body ? `<section class="section"><h2 class="h2">${t(title)}</h2>${body}</section>` : '';

/** The part from a story (story.py's shape). */
function experienceView(s, query) {
  if (!s || !s.ran) return howToRun('rp.ex.none.why');
  const missing = (s.missing || []).length ? `<p class="small caution-ic">${t('rp.ex.missing')} ${s.missing.map(m => code('experience/' + m)).join(' ')}</p>` : '';
  return `<p class="small ink-2">${t('rp.ex.guide')}</p>${overview(s)}${missing}
    ${block('rp.ex.personas', s.personas.map(p => persona(p, query || {})).join(''))}
    ${block('rp.ex.difficulties', s.difficulties.ranked.length ? `<ol class="rp-ex-diffs">${s.difficulties.ranked.map(difficulty).join('')}</ol>` : `<p class="small muted">${t('rp.ex.nodiff')}</p>`)}
    ${block('rp.ex.time', s.time.length ? times(s) : '')}
    ${block('rp.ex.tickets', s.tickets.length ? tickets(s) : '')}
    ${block('rp.ex.replays', s.replays.summary && Object.keys(s.replays.summary).length ? replays(s) : '')}`;
}

export function experiencePart(ctx) {
  if (offline()) return nm(t('rp.ex.offline'), t('un.files.offline.why'));
  const s = read();
  if (s === null) return `<p class="small muted" role="status" aria-busy="true">${t('rp.ex.reading')}</p>`;
  if (s === false) return howToRun('rp.ex.none.why');
  return experienceView(s, ctx.query);
}
