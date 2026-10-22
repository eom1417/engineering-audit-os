// The free preview of one of Understand's actions before it runs (G3): re-plan the ideal (PLN-12), run the AI nodes
// (SYS-16), adopt a design (SYS-17). It asks the server what will happen (POST /api/actions/<id>/preview, which
// changes nothing), shows it with who runs it, and Start sends exactly those inputs and that assistant with the
// preview's confirm token (POST /api/runs). A choice the person changes asks for the preview again. In the read-only
// copy the sheet explains how to open the console live.
import {
  t, L, num, esc, icon, href, expiresAt, sheet, act, rerenderSheet, local, parseHash, closeSheetThen, toast, offline,
  client, ActionError, contract, store, assistantPicker,
} from 'eaos';
import { facts } from './kit.js';

const defs = {};

function ask(name, own) {
  const def = defs[name];
  if (own.asking || !client) return;
  const mine = own.ticket = (own.ticket || 0) + 1; // an answer to an older choice is dropped
  own.asking = true; own.problem = null;
  client.preview(def.action, { inputs: def.inputs(own), assistant: own.assistant || undefined })
    .then(p => { if (mine !== own.ticket) return; own.preview = p; own.asking = false; rerenderSheet(); },
      e => { if (mine !== own.ticket) return; Object.assign(own, { asking: false, preview: null, problem: e instanceof ActionError ? e.message : String(e) }); rerenderSheet(); });
}
/** A choice changed: the preview is asked again (the old one's token no longer matches). */
export function again(change) {
  Object.assign(local(), { preview: null, asking: false, problem: null, refused: null }, change);
  rerenderSheet();
}

function assistants(p, own) {
  const all = p.assistants || [];
  if (!all.length) return '';
  const picked = own.assistant || (p.assistant && p.assistant.id);
  return `<div>${assistantPicker(all, picked, 'un-')}</div>`;
}

function estimate(p) {
  const lo = p.estimate && p.estimate.minutes_low, hi = p.estimate && p.estimate.minutes_high;
  if (lo == null || hi == null) return t('pv.estimate.none');
  return hi > 180 ? t('pv.estimate.h', { lo: num(Math.round(lo / 60)), hi: num(Math.ceil(hi / 60)) }) : t('pv.estimate.v', { lo: num(lo), hi: num(hi) });
}

/** Registers the preview sheet `name` of `action`: {action, title(own), inputs(own) -> the action's inputs, extra(own)
 *  -> markup of the choices it offers, command(own) -> the terminal line, ready(own) -> false while a choice is
 *  missing, done(run) -> what the toast says}. */
export function actionSheet(name, def) {
  defs[name] = def;
  sheet(name, {
    kind: 'drawer',
    needs: def.needs,
    render(arg, query, own) {
      const a = contract.actionOf(def.action);
      own.arg = arg;
      const title = def.title(own);
      const cmd = def.command(own);
      if (offline() || !client) {
        return { title: esc(title), body: `<p>${esc(L(a.description))}</p><p>${esc(L(contract.SNAPSHOT.text))}</p><div class="code" style="padding:12px 16px">${esc(contract.SNAPSHOT.command)}</div>`,
          foot: `<button class="btn btn--secondary btn--block" data-act="copy" data-text="${esc(contract.SNAPSHOT.command)}">${icon('copy')}${t('copy')}</button>` };
      }
      const ready = !def.ready || def.ready(own);
      if (ready && !own.preview && !own.asking && !own.problem) ask(name, own);
      const p = own.preview;
      const free = `<span class="free-band">${icon('check', 'icon--sm')}${t('free')}</span>`;
      const extra = def.extra ? def.extra(own) : '';
      const terminal = `<details><summary class="link" style="cursor:pointer;min-height:44px;display:inline-flex;align-items:center;gap:6px">${icon('terminal', 'icon--sm')}${t('pv.terminal')}</summary>
        <div class="code" style="padding:12px 16px;margin-top:8px">${esc(cmd)}</div></details>`;
      if (!p) {
        return { title: esc(title), sub: free,
          body: `<p>${esc(L(a.description))}</p>${extra}${own.problem ? `<p class="small" role="alert">${icon('warn', 'icon--sm')} ${esc(own.problem)}</p>` : ready ? `<p class="small muted" role="status" aria-busy="true">${t('pv.updating')}</p>` : ''}`,
          foot: `<button class="btn btn--primary btn--block" disabled>${esc(t('pv.start', { title }))}</button>` };
      }
      const asst = own.assistant || (p.assistant && p.assistant.id);
      const noAssistant = a.needs_assistant && !asst;
      const blocked = own.busy || noAssistant || !ready;
      return {
        title: esc(title), sub: free,
        body: `<p>${esc(L(a.description))}</p>
          ${extra}
          ${facts([
            [t('pv.estimate'), `${esc(estimate(p))}<span class="small muted" style="display:block">${esc(L(p.estimate && p.estimate.basis))}</span>`],
            [t('pv.risk'), `<span class="tag ${p.risk && p.risk.level === 'high' ? 'tag--caution' : 'tag--state'}">${t('pv.risk.' + ((p.risk && p.risk.level) || 'low'))}</span>`],
            [t('pv.fail'), `<span class="small">${esc(L(p.on_failure))}</span>`],
          ])}
          ${assistants(p, own)}
          ${noAssistant ? `<p class="small" role="note">${icon('warn', 'icon--sm')} ${t('un.pv.noasst')} <a class="link" href="${href('/project/assistants')}" data-act="go" data-href="${href('/project/assistants')}">${t('un.pv.assistants')}</a></p>` : ''}
          ${a.needs_assistant ? `<p class="small ink-2">${t('pv.cost')}</p>` : ''}
          ${terminal}`,
        foot: `${own.refused ? `<p class="small" role="alert">${icon('warn', 'icon--sm')} ${esc(own.refused)}</p>` : ''}
          <button class="btn btn--primary btn--block" data-act="un-pv-start" data-fk="un-pv-start" ${blocked ? 'disabled' : ''}>${esc(own.busy ? t('pv.starting') : t('pv.start', { title }))}</button>
          <button class="btn btn--quiet btn--block" data-act="copy" data-text="${esc(p.handoff && p.handoff.request ? L(p.handoff.request) : cmd)}">${icon('copy')}${t('pv.copy')}</button>
          ${p.confirm ? `<p class="sheet__fine">${esc(t('pv.valid', { time: expiresAt(p.confirm.expires) }))}</p>` : ''}`,
      };
    },
  });
}

act('un-pv-asst', el => again({ assistant: el.value }));
act('un-pv-start', async el => {
  const own = local(), name = (parseHash().query.sheet || '').split(':')[0], def = defs[name];
  const p = own.preview;
  if (el.disabled || !p || own.busy || !def) return;
  own.busy = true; rerenderSheet();
  try {
    const run = await client.start({ action: def.action, inputs: def.inputs(own), assistant: own.assistant || (p.assistant && p.assistant.id) || undefined,
      confirm: p.confirm ? p.confirm.token : undefined });
    const title = def.title(own);
    closeSheetThen(() => {
      store.refresh();
      const said = def.done ? def.done(run) : null;
      toast(said || t(run.state === 'queued' ? 'toast.queued' : 'toast.started', { title }),
        said ? undefined : { link: { href: href('/activity/run/' + encodeURIComponent(run.id)), text: t('toast.follow') } });
    });
  } catch (e) {
    if (e instanceof ActionError && e.needs === 'preview') { again({}); return; }
    Object.assign(own, { busy: false, refused: e instanceof ActionError ? e.message : String(e) });
    rerenderSheet();
  }
});

