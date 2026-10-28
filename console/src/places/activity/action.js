// One action's preview with its form (RUN-13, FIX-14, FIX-16): the sheet ?sheet=action:<id> every action of the
// launcher opens (launch.js); a reading tool answers in place, any other starts a run.
import {
  t, L, num, esc, icon, code, href, sheet, act, rerenderSheet, local, parseHash, closeSheetThen, toast, refresh, offline, chk,
  S, store, model, client, contract, ActionError, has, ac,
  terminalFold,
} from 'eaos';
import { metaOf, reading, said, alertLine } from './launch.js';

const enc = encodeURIComponent;
const LONG = ['text', 'content', 'summary', 'reason', 'person_said'];
const typeOf = schema => (Array.isArray(schema.type) ? schema.type.find(x => x !== 'null') : schema.type);
const fieldLabel = (a, name) => (has(`ac.in.${a.id}.${name}`) ? t(`ac.in.${a.id}.${name}`) : has('ac.in.' + name) ? t('ac.in.' + name) : name.replace(/_/g, ' '));
const valText = x => (has('ac.val.' + x) ? t('ac.val.' + x) : x);
/** A field written as JSON: an object, or a list of anything but text and a fixed choice. */
const isJSON = (type, items) => type === 'object' || (type === 'array' && typeOf(items) !== 'string' && !items.enum);

/** Which kind of field a schema asks for. */
function fieldKind(type, enumOf, items) {
  if (type === 'boolean') return 'boolean';
  if (enumOf.length) return 'choice';
  if (type === 'array' && items.enum) return 'picks';
  if (type === 'integer') return 'integer';
  if (isJSON(type, items)) return 'json';
  if (type === 'array') return 'list';
  return 'text';
}
/** Each kind of field drawn; f holds its name, id, value, schema, label and the shared parts. */
const FIELDS = new Map(Object.entries({
  boolean: f => `<div class="toggle-row"><span>${esc(f.label)}</span><span class="switch"><input type="checkbox" id="${f.id}" data-fk="${f.id}" data-change="ac-field" data-f="${esc(f.name)}" ${f.v ? 'checked' : ''} aria-label="${esc(f.label)}"><span class="switch__track"></span><span class="switch__thumb"></span></span></div>`,
  choice: f => `<fieldset class="ac-fs"><legend class="ac-label">${esc(f.label)}</legend><div class="opts">${f.enumOf.map(x => `<label class="opt"><input type="radio" name="${f.id}" value="${esc(x)}" data-change="ac-field" data-f="${esc(f.name)}" data-fk="${f.id}-${esc(x)}" ${f.v === x ? 'checked' : ''}><span class="opt__dot" aria-hidden="true"></span><span class="opt__text">${esc(valText(x))}</span></label>`).join('')}</div></fieldset>`,
  picks: f => `<fieldset class="ac-fs"><legend class="ac-label">${esc(f.label)}</legend><div class="panel rows">${f.items.enum.map(x => `<label class="row row--pick">${chk(`data-change="ac-field" data-f="${esc(f.name)}" value="${esc(x)}" data-fk="${f.id}-${esc(x)}"`, (f.v || []).includes(x), valText(x))}<span class="row__main pick__words">${esc(valText(x))}</span></label>`).join('')}</div></fieldset>`,
  integer: f => `${f.lab}<div class="field"><input type="number" inputmode="numeric" ${f.common} value="${esc(f.v == null ? '' : f.v)}" min="${f.schema.minimum != null ? f.schema.minimum : ''}" max="${f.schema.maximum != null ? f.schema.maximum : ''}"></div>`,
  json: f => `${f.lab}<textarea class="input mono" dir="ltr" ${f.common} placeholder="${f.type === 'object' ? '{ }' : '[ ]'}">${esc(f.v || '')}</textarea><p class="small muted">${t('ac.ax.json')}</p>`,
  list: f => `${f.lab}<textarea class="input mono" dir="ltr" ${f.common}>${esc(f.v || '')}</textarea><p class="small muted">${t('ac.ax.list')}</p>`,
  text: f => (LONG.includes(f.name) ? `${f.lab}<textarea class="input" ${f.common}>${esc(f.v || '')}</textarea>`
    : `${f.lab}<div class="field"><input type="text" dir="auto" ${f.common} value="${esc(f.v || '')}" autocomplete="off"></div>`),
}));
function fieldHTML(a, name, schema, own) {
  const id = `f-${a.id}-${name}`;
  const req = (a.inputs.required || []).includes(name);
  const label = fieldLabel(a, name);
  const f = {
    name, id, schema, label, v: own.values[name], type: typeOf(schema), items: schema.items || {}, enumOf: (schema.enum || []).filter(x => x != null),
    lab: `<label class="ac-label" for="${id}">${esc(label)}${req ? ` <span class="ac-req-mark">${t('ac.ax.required')}</span>` : ''}</label>`,
    common: `id="${id}" data-fk="${id}" data-input="ac-field" data-f="${esc(name)}" ${req ? 'required aria-required="true"' : ''}`,
  };
  return FIELDS.get(fieldKind(f.type, f.enumOf, f.items))(f);
}
const blank = v => v == null || v === '' || (Array.isArray(v) && !v.length);
/** One input as the contract wants it (a number, a list, JSON); a bad JSON throws. */
function inputValue(schema, v) {
  const type = typeOf(schema);
  if (type === 'integer') return Number(v);
  if (isJSON(type, schema.items || {})) return JSON.parse(v);
  if (type === 'array' && !Array.isArray(v)) return String(v).split('\n').map(x => x.trim()).filter(Boolean);
  return v;
}
/** The inputs as the contract wants them (numbers, lists, JSON), or the reason one cannot be read. */
function inputsOf(a, own) {
  const out = {};
  for (const [name, schema] of contract.personInputs(a)) {
    const v = own.values[name];
    if (blank(v)) continue;
    try { out[name] = inputValue(schema, v); } catch (e) { return { problem: t('ac.ax.json.bad', { name: fieldLabel(a, name) }) }; }
  }
  return { inputs: out };
}
const missing = (a, own) => (a.inputs.required || []).filter(n => n !== 'project' && (own.values[n] == null || String(own.values[n]).trim() === '')).length > 0;
function askAction(a, own) {
  if (!client) return;
  const got = inputsOf(a, own);
  if (got.problem) { own.problem = got.problem; own.preview = null; rerenderSheet(); return; }
  const mine = own.ticket = (own.ticket || 0) + 1;
  own.asking = true; own.problem = null;
  client.preview(a.id, { inputs: got.inputs }).then(p => { if (mine !== own.ticket) return; own.preview = p; own.asking = false; rerenderSheet(); },
    e => { if (mine !== own.ticket) return; own.asking = false; own.preview = null; own.problem = said(e); rerenderSheet(); });
}
function flagLine(a) {
  const out = [];
  if (reading(a)) out.push(`<span class="tag tag--free">${icon('check')}${t('ac.ax.free')}</span>`);
  if (a.returns_job) out.push(`<span class="tag tag--state">${t('ac.ax.job')}</span>`);
  if (a.needs_assistant) out.push(`<span class="tag tag--ai">${icon('ai')}${t('ac.ax.asst')}</span>`);
  if (a.changes_code) out.push(`<span class="tag tag--state">${t('ac.ax.code')}</span>`);
  if (a.needs_consent) out.push(`<span class="tag tag--owner">${icon('seal')}${t('ac.ax.consent')}</span>`);
  return out.length ? `<div class="pdetail__tags">${out.join('')}</div>` : '';
}

/** The same action from a terminal, with the inputs given so far. */
const actionCmd = (a, own) => `eaos act ${a.id}${Object.entries(inputsOf(a, own).inputs || {}).map(([k, v]) => ` --${k} ${Array.isArray(v) ? v.join(',') : typeof v === 'object' ? "'…'" : String(v).replace(/\s+/g, ' ').slice(0, 40)}`).join('')}`;
function consentHTML(a) {
  if (!a.needs_consent) return '';
  return `<div class="owner-band">${icon('seal')}<span><b>${t(has('ac.ax.consent.title.' + a.id) ? 'ac.ax.consent.title.' + a.id : 'ac.ax.consent.title')}</b>${t('ac.ax.consent.how')}</span></div>`;
}
/** The preview's time, risk, failure and who runs it; none for a reading tool. */
function actionFacts(a, p) {
  if (!p || reading(a)) return '';
  const estimate = p.estimate && p.estimate.minutes_high > 1 ? `<dt>${t('pv.estimate')}</dt><dd>${esc(t('pv.estimate.v', { lo: num(p.estimate.minutes_low), hi: num(p.estimate.minutes_high) }))}<span class="small muted" style="display:block">${esc(L(p.estimate.basis))}</span></dd>` : '';
  return `<dl class="facts">${estimate}
      <dt>${t('pv.risk')}</dt><dd><span class="tag ${p.risk.level === 'high' ? 'tag--caution' : 'tag--state'}">${t('pv.risk.' + p.risk.level)}</span></dd>
      <dt>${t('pv.fail')}</dt><dd class="small">${esc(L(p.on_failure))}</dd>
      ${a.needs_assistant ? `<dt>${t('pv.who')}</dt><dd>${p.assistant ? esc(p.assistant.name) : esc(t('pv.handoff'))}</dd>` : ''}</dl>`;
}
const answerHTML = own => (own.answer !== undefined ? `<div class="ac-answer" role="status"><div class="block-title">${t('ac.ax.answer')}</div>${ac.answerHTML(own.answer) || `<p class="small muted">${t('ac.ax.answer.none')}</p>`}</div>` : '');
function actionBody(a, own) {
  const m = metaOf(a), p = own.preview;
  const fields = contract.personInputs(a).map(([name, schema]) => `<div class="ac-fieldwrap">${fieldHTML(a, name, schema, own)}</div>`).join('');
  const expert = m.group === 'expert' ? `<p class="ac-note small">${icon('info', 'icon--sm')}<span>${t('ac.ax.expert')}</span></p>` : '';
  const link = m.link ? `<p class="small"><a class="link" href="${href(m.link)}" data-act="go" data-href="${href(m.link)}">${t('ac.ax.go')}</a></p>` : '';
  return `<p>${esc(L(a.description))}</p>${flagLine(a)}${expert}${consentHTML(a)}${link}
        ${fields ? `<div class="ac-stack">${fields}</div>` : ''}
        <p class="small muted">${t('ac.ax.project', { name: code(model.project().name) })}</p>
        ${actionFacts(a, p)}${p && a.needs_assistant && p.assistant ? `<p class="small ink-2">${t('pv.cost')}</p>` : ''}${answerHTML(own)}
        ${terminalFold(esc(actionCmd(a, own)), true)}`;
}
const blocked = (a, own, p) => missing(a, own) || !p || own.busy || (a.needs_assistant && !p.assistant && !(p.handoff && p.handoff.available));
function startLabel(a, own) {
  if (own.busy) return t('pv.starting');
  if (reading(a)) return t('ac.ax.answer.do');
  return !!ac.liveRun() && a.returns_job ? t('ac.ax.queue', { label: L(a.label) }) : t('pv.start', { title: L(a.label) });
}
function whyLine(a, own, p) {
  if (missing(a, own)) return t('ac.ax.fill');
  if (!p && own.asking) return t('pv.updating');
  return a.returns_job ? t('ac.ax.queue.note') : '';
}
const handoffCopy = p => (p && p.handoff && p.handoff.request ? `<button class="btn btn--quiet btn--block" data-act="copy" data-text="${esc(L(p.handoff.request))}">${icon('copy')}${t('pv.copy')}</button>` : '');
function actionFoot(a, own) {
  const p = own.preview;
  return `${alertLine(own.problem || own.refused)}
        <button class="btn btn--primary btn--block" data-act="ac-action-start" data-fk="ax-start" ${blocked(a, own, p) ? 'disabled' : ''} aria-describedby="ax-why">${esc(startLabel(a, own))}</button>
        <p class="sheet__fine" id="ax-why">${whyLine(a, own, p)}</p>
        ${handoffCopy(p)}`;
}
const needsAsk = (a, own) => !own.preview && !own.asking && !own.problem && !missing(a, own) && !own.answer;

sheet('action', {
  kind: 'drawer',
  render(id, query, own) {
    const a = contract.actionOf(id);
    if (!a) return { title: esc(t('ac.ax.notfound', { id })), body: '' };
    const title = esc(L(a.label));
    if (!own.values) { own.values = Object.assign({}, S.ac.prefill[id] || {}); delete S.ac.prefill[id]; }
    if (offline()) return { title, body: `<p>${esc(L(a.description))}</p>${flagLine(a)}`, foot: `<button class="btn btn--primary btn--block" data-act="sheet" data-sheet="open-live">${t('offline.how')}</button>` };
    if (needsAsk(a, own)) askAction(a, own);
    return {
      title,
      sub: `<span class="free-band">${icon('check', 'icon--sm')}${t(reading(a) ? 'ac.ax.free.band' : 'free')}</span>`,
      body: actionBody(a, own),
      foot: actionFoot(a, own),
    };
  },
});
/** The action of the open sheet (?sheet=action:<id>). */
const sheetAction = () => contract.actionOf((parseHash().query.sheet || '').split(':')[1]);
/** A field's new value: a list ticked or unticked, a switch, or what was typed. */
function fieldValue(el, cur) {
  if (el.type === 'checkbox' && el.value && el.value !== 'on') {
    const list = cur || [];
    return el.checked ? [...new Set(list.concat([el.value]))] : list.filter(x => x !== el.value);
  }
  return el.type === 'checkbox' ? el.checked : el.value;
}
let fieldTimer = null;
act('ac-field', el => {
  const own = local(), name = el.dataset.f;
  const a = sheetAction();
  if (!a) return;
  own.values[name] = fieldValue(el, own.values[name]);
  own.answer = undefined; own.refused = null;
  clearTimeout(fieldTimer);
  const typing = el.tagName === 'TEXTAREA' || el.type === 'text' || el.type === 'number';
  fieldTimer = setTimeout(() => { own.preview = null; own.problem = null; if (!missing(a, own)) askAction(a, own); else rerenderSheet(); }, typing ? 600 : 0);
});
function answered(own, run) {
  Object.assign(own, { busy: false, answer: run.result ? run.result.answer : null, preview: null });
  store.refresh(); rerenderSheet();
}
act('ac-action-start', async el => {
  const own = local(), a = sheetAction(), p = own.preview;
  if (el.disabled || !a || !p || own.busy) return;
  own.busy = true; rerenderSheet();
  try {
    const run = await client.start({ action: a.id, inputs: inputsOf(a, own).inputs, confirm: p.confirm ? p.confirm.token : undefined });
    if (run.read) { answered(own, run); return; }
    closeSheetThen(() => {
      store.refresh(); refresh();
      toast(t(run.state === 'queued' && ac.liveRun() ? 'ac.ax.queued' : 'toast.started', { title: L(a.label), n: num(run.position || 1) }), { link: { href: href('/activity/run/' + enc(run.id)), text: t('toast.follow') } });
    });
  } catch (e) {
    if (e instanceof ActionError && e.needs === 'preview') { Object.assign(own, { busy: false, preview: null }); askAction(a, own); return; }
    Object.assign(own, { busy: false, refused: said(e) }); rerenderSheet();
  }
});
