// What a page looks like, element by element, in every state a person can put it in (M18.7): the style oracle a zero-change
// batch is proved by. Run inside a lock's spec, on the page as the spec left it. Transitions and animations are off first:
// under a transition a forced state's computed value is still the one it starts from, and a hover colour would never differ.
// {sigs: [{property: value}], els: {key: {default, before, after, hover, focus, active: index in sigs}}, roles: {key: role}, text, motion,
// crops: {key: file}}: a key is the element's path from the body, and each distinct look is stored once. The states are compared
// (look_oracle.py); roles, words, motion and crops are read by the inventory (analysis/design/inventory.py).
const fs = require('node:fs');
const path = require('node:path');

const PROPERTIES = ['color', 'background-color', 'background-image', 'border-top-color', 'border-right-color', 'border-bottom-color', 'border-left-color',
  'border-top-width', 'border-right-width', 'border-bottom-width', 'border-left-width', 'border-top-style', 'border-top-left-radius', 'border-top-right-radius',
  'border-bottom-right-radius', 'border-bottom-left-radius', 'box-shadow', 'outline-color', 'outline-width', 'outline-style', 'outline-offset', 'opacity',
  'font-family', 'font-size', 'font-weight', 'font-style', 'line-height', 'letter-spacing', 'text-decoration-line', 'text-transform', 'text-align',
  'padding-top', 'padding-right', 'padding-bottom', 'padding-left', 'margin-top', 'margin-right', 'margin-bottom', 'margin-left', 'row-gap', 'column-gap',
  'display', 'position', 'z-index', 'cursor', 'fill', 'stroke', 'visibility'];
const INTERACTIVE = 'a,button,input,select,textarea,summary,[role=button],[role=tab],[role=menuitem],[role=checkbox],[role=switch],[tabindex]';
const STATES = { hover: ['hover'], focus: ['focus', 'focus-visible'], active: ['active'] };
const MOST_INTERACTIVE = 150;
const MOST_CROPS = 12;
const QUIET = '*,*::before,*::after{transition:none!important;animation:none!important}';

function inPage({ properties, interactive }) {
  const skipped = new Set(['SCRIPT', 'STYLE', 'META', 'LINK', 'TITLE', 'NOSCRIPT', 'TEMPLATE']);
  const keyOf = (el) => {
    const parts = [];
    for (let at = el; at && at !== document.documentElement; at = at.parentElement) {
      const same = at.parentElement ? [...at.parentElement.children].filter((other) => other.tagName === at.tagName) : [at];
      parts.unshift(`${at.tagName.toLowerCase()}:${same.indexOf(at)}`);
    }
    return parts.join('>');
  };
  const read = (el, pseudo) => { const style = getComputedStyle(el, pseudo); return Object.fromEntries(properties.map((name) => [name, style.getPropertyValue(name)])); };
  const inputRole = { checkbox: 'checkbox', radio: 'radio', button: 'button', submit: 'button', reset: 'button' };
  const tagRole = { A: 'link', BUTTON: 'button', SELECT: 'select', TEXTAREA: 'input', TABLE: 'table', DIALOG: 'dialog', SUMMARY: 'button' };
  const isCard = (el, style) => (parseFloat(style.borderTopWidth) > 0 || style.boxShadow !== 'none') && el.querySelector('h1,h2,h3,h4,h5,h6,[role=heading]') !== null && el.children.length > 1;
  const roleOf = (el) => {
    const said = el.getAttribute('role');
    if (said) return said === 'alertdialog' ? 'dialog' : said === 'status' ? 'alert' : said;
    if (el.tagName === 'INPUT') return inputRole[el.type] || 'input';
    if (/^H[1-6]$/.test(el.tagName)) return 'heading';
    return tagRole[el.tagName] || (isCard(el, getComputedStyle(el)) ? 'card' : null);
  };
  const hasPseudo = (el, pseudo) => { const content = getComputedStyle(el, pseudo).content; return content && content !== 'none' && content !== 'normal'; };
  const rows = [], roles = {};
  for (const el of [document.body, ...document.body.querySelectorAll('*')]) {
    if (skipped.has(el.tagName) || getComputedStyle(el).display === 'none') continue;
    const row = { key: keyOf(el), default: read(el) };
    const role = roleOf(el);
    if (role) roles[row.key] = role;
    for (const pseudo of ['before', 'after']) if (hasPseudo(el, `::${pseudo}`)) row[pseudo] = read(el, `::${pseudo}`);
    rows.push(row);
  }
  return { rows, roles, text: document.body.innerText.replace(/\s+/g, ' ').trim(), interactive: [...document.querySelectorAll(interactive)].map(keyOf) };
}

// The transitions the page declares, before they are turned off: what the library's motion is made of.
function motionInPage() {
  const add = (tally, value) => { tally[value] = (tally[value] || 0) + 1; };
  const durations = {}, easings = {};
  for (const el of document.body.querySelectorAll('*')) {
    const style = getComputedStyle(el);
    style.transitionDuration.split(', ').forEach((duration, index) => {
      if (duration !== '0s') { add(durations, duration); add(easings, style.transitionTimingFunction.split(', ')[index] || 'ease'); }
    });
  }
  return { durations, easings };
}

const selectorOf = (key) => key.split('>').map((part) => { const [tag, index] = part.split(':'); return tag === 'body' ? 'body' : `${tag}:nth-of-type(${Number(index) + 1})`; }).join('>');

// One picture of the first part of each role and look, only when recording: what the report shows side by side.
async function cropsOf(page, rows, roles, folder, prefix) {
  const taken = {}, seen = new Set();
  fs.mkdirSync(folder, { recursive: true });
  for (const row of rows) {
    const role = roles[row.key];
    const look = role && `${role}${JSON.stringify(row.default)}`;
    if (!look || seen.has(look) || seen.size >= MOST_CROPS) continue;
    seen.add(look);
    const file = `${prefix}-${seen.size}.png`;
    try { await page.locator(selectorOf(row.key)).first().screenshot({ path: path.join(folder, file), timeout: 1500 }); taken[row.key] = file; } catch { /* not on screen: no picture */ }
  }
  return taken;
}

async function forced(page, keys) {
  const cdp = await page.context().newCDPSession(page);
  await cdp.send('DOM.enable');
  await cdp.send('CSS.enable');
  const { root } = await cdp.send('DOM.getDocument', { depth: 0 });
  const { nodeIds } = await cdp.send('DOM.querySelectorAll', { nodeId: root.nodeId, selector: INTERACTIVE });
  const wanted = new Set(PROPERTIES), out = [];
  for (const [index, nodeId] of nodeIds.slice(0, MOST_INTERACTIVE).entries()) {
    const states = {};
    for (const [state, classes] of Object.entries(STATES)) {
      await cdp.send('CSS.forcePseudoState', { nodeId, forcedPseudoClasses: classes });
      const { computedStyle } = await cdp.send('CSS.getComputedStyleForNode', { nodeId });
      states[state] = Object.fromEntries(computedStyle.filter((row) => wanted.has(row.name)).map((row) => [row.name, row.value]));
    }
    await cdp.send('CSS.forcePseudoState', { nodeId, forcedPseudoClasses: [] });
    out.push({ key: keys[index], states });
  }
  await cdp.detach();
  return out;
}

function compact(rows, states, more) {
  const sigs = [], seen = new Map();
  const index = (look) => { const text = JSON.stringify(look); if (!seen.has(text)) { seen.set(text, sigs.length); sigs.push(look); } return seen.get(text); };
  const els = {};
  for (const { key, ...looks } of rows) els[key] = Object.fromEntries(Object.entries(looks).map(([name, look]) => [name, index(look)]));
  for (const row of states) if (els[row.key]) for (const [state, look] of Object.entries(row.states)) els[row.key][state] = index(look);
  return { sigs, els, ...more };
}

async function snapshot(page, { crops, name } = {}) {
  const motion = await page.evaluate(motionInPage);
  await page.addStyleTag({ content: QUIET });
  const { rows, roles, text, interactive } = await page.evaluate(inPage, { properties: PROPERTIES, interactive: INTERACTIVE });
  const taken = crops ? await cropsOf(page, rows, roles, crops, name) : {};
  return compact(rows, await forced(page, interactive), { roles, text, motion, crops: taken });
}

module.exports = { snapshot, PROPERTIES };
