// Your rules (M16): what the person keeps asking for, each kept in their words and held by a machine guard. The list
// (in scope, pinned, held or broken where, how often it came back), a rule said here or kept from a card's note, pinned
// for every change or unpinned, and the commit hook. Everything through the `rules` action (eaos/interfaces/rules.py).
import { said, t, num, esc, icon, code, screen, act, refresh, toast, fmtWhen, offline, client, ac, skeletonRows, rowWords, titledSection, openLiveButton, pageHead } from 'eaos';
import { projBack } from './git.js';

const kept = { data: null, asking: false, problem: null };
/** The rules as the `rules` action lists them, read once per visit and again after each change. */
function listed(again) {
  if (!client) return null;
  if (!kept.asking && (again || !kept.data)) {
    kept.asking = true;
    client.start({ action: 'rules', inputs: { op: 'list' } }).then(run => { Object.assign(kept, { data: (run.result && run.result.answer) || {}, asking: false }); refresh(); },
      e => { Object.assign(kept, { problem: said(e), asking: false }); refresh(); });
  }
  return kept.data;
}
/** A change of a rule: queued as a run (the person pressed it: their yes), the list read again once it ran. */
async function ask(inputs, done) {
  try {
    await client.start({ action: 'rule', inputs: Object.assign({ person_agreed: true }, inputs) });
    toast(t(done));
    [1500, 4000].forEach(ms => setTimeout(() => listed(true), ms));
  } catch (e) { toast(said(e), { refusal: true }); }
}

const scopeWord = r => (r.scope.kind === 'pinned' ? t('ru.pinned') : r.scope.kind === 'card' ? t('ru.for_card', { id: r.scope.ref }) : t('ru.for_batch'));
function stateOf(r) {
  const brokeLast = r.last_broken && (!r.held || r.held.at < r.last_broken.at);
  if (!r.in_scope) return ac.mark('skipped', t('ru.ended'));
  if (brokeLast) return ac.mark('failed', esc(t('ru.broken', { where: r.last_broken.places.slice(0, 3).join(t('list.sep')) })));
  if (r.guard_kind === 'none') return ac.mark('waiting', t('ru.unguarded'));
  if (!r.guarded) return ac.mark('waiting', t('ru.no_guard'));
  return r.held ? ac.mark('ok', t('ru.held')) : ac.mark('waiting', t('ru.not_yet'));
}
function ruleRow(r) {
  const meta = `${esc(scopeWord(r))} · ${esc(t('ru.said', { when: fmtWhen(r.said_at), n: num(r.said) }))}${r.returns ? ' · ' + esc(t('ru.came_back', { n: num(r.returns) })) : ''}<br>${stateOf(r)}${r.guarded ? ` <span class="small muted">${t('ru.guard.' + r.guard_kind)}</span>` : ''}`;
  const pin = !r.in_scope ? '' : r.scope.kind === 'pinned'
    ? `<button class="btn btn--quiet btn--sm" data-act="ru-unpin" data-id="${esc(r.id)}" data-fk="unpin-${esc(r.id)}">${t('ru.unpin')}</button>`
    : `<button class="btn btn--${r.offer_pin ? 'primary' : 'secondary'} btn--sm" data-act="ru-pin" data-id="${esc(r.id)}" data-fk="pin-${esc(r.id)}">${icon('lock', 'icon--sm')}${t('ru.pin')}</button>`;
  return `<li class="row">${rowWords(`${code(r.id)} ${esc(r.words)}`, meta)}${offline() ? '' : pin}</li>`;
}
const addForm = () => `<div class="panel panel__pad stack-2">
    <label for="ru-words">${t('ru.add.label')}</label>
    <textarea class="input" id="ru-words" data-fk="ru-words" placeholder="${esc(t('ru.add.ph'))}"></textarea>
    <label class="small"><input type="checkbox" id="ru-pin" data-fk="ru-pin"> ${t('ru.add.pin')}</label>
    <div><button class="btn btn--primary btn--sm" data-act="ru-add" data-fk="ru-add">${t('ru.add.do')}</button></div>
    <p class="small muted">${t('ru.add.note')}</p></div>`;
const hookLine = d => `<div class="panel panel__pad">${rowWords(t(d.hook ? 'ru.hook.on' : 'ru.hook.off'), t('ru.hook.what'))}
    <div class="actions mt-2"><button class="btn btn--secondary btn--sm" data-act="ru-hook" data-on="${d.hook ? '' : '1'}" data-fk="ru-hook" ${d.pinned || d.hook ? '' : 'disabled'}>${t(d.hook ? 'ru.hook.stop' : 'ru.hook.start')}</button></div></div>`;

function rulesPage(ctx) {
  if (ctx.offline) return `<div class="page">${projBack()}${pageHead(t('ru.offline'), t('ru.lede.guide'), openLiveButton())}</div>`;
  const d = listed();
  if (!d) return `<div class="page" aria-busy="true">${projBack()}<h1 class="lede">${t('ru.title')}</h1>${kept.problem ? `<p role="alert">${esc(kept.problem)}</p>` : skeletonRows(2, [40, 70], { cls: 'section', tag: 'div' })}</div>`;
  const rules = d.rules || [];
  return `<div class="page">
    ${projBack()}
    ${pageHead(esc(rules.length ? t('ru.lede', { n: num(rules.length), p: num(d.pinned) }) : t('ru.lede.none')), t('ru.lede.guide'))}
    ${rules.length ? titledSection('ru-h', t('ru.title'), `<ul class="panel rows">${rules.map(ruleRow).join('')}</ul>`) : ''}
    ${titledSection('ru-add-h', t('ru.add'), addForm())}
    ${titledSection('ru-hook-h', t('ru.hook'), hookLine(d))}
  </div>`;
}
screen({ id: 'S-53', path: '/project/rules', place: 'project', title: () => t('proj.rules'), render: rulesPage });

act('ru-add', el => {
  const words = (document.getElementById('ru-words') || {}).value || '';
  if (!words.trim() || !client || el.disabled) return;
  const pin = !!(document.getElementById('ru-pin') || {}).checked;
  ask({ op: 'add', words: words.trim(), pin }, 'ru.kept');
});
act('ru-pin', el => ask({ op: 'pin', id: el.dataset.id }, 'ru.pinned.done'));
act('ru-unpin', el => ask({ op: 'unpin', id: el.dataset.id }, 'ru.unpinned.done'));
act('ru-hook', el => ask({ op: 'hook', on: !!el.dataset.on }, el.dataset.on ? 'ru.hook.on' : 'ru.hook.off'));
