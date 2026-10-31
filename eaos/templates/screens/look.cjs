// What a page looks like, element by element, in every state a person can put it in (M18.7): the style oracle a zero-change
// batch is proved by. Run inside a lock's spec, on the page as the spec left it. Transitions and animations are off first:
// under a transition a forced state's computed value is still the one it starts from, and a hover colour would never differ.
// {sigs: [{property: value}], els: {key: {default, before, after, hover, focus, active: index in sigs}}}: a key is the
// element's path from the body, and each distinct look is stored once.
const PROPERTIES = ['color', 'background-color', 'background-image', 'border-top-color', 'border-right-color', 'border-bottom-color', 'border-left-color',
  'border-top-width', 'border-right-width', 'border-bottom-width', 'border-left-width', 'border-top-style', 'border-top-left-radius', 'border-top-right-radius',
  'border-bottom-right-radius', 'border-bottom-left-radius', 'box-shadow', 'outline-color', 'outline-width', 'outline-style', 'outline-offset', 'opacity',
  'font-family', 'font-size', 'font-weight', 'font-style', 'line-height', 'letter-spacing', 'text-decoration-line', 'text-transform', 'text-align',
  'padding-top', 'padding-right', 'padding-bottom', 'padding-left', 'margin-top', 'margin-right', 'margin-bottom', 'margin-left', 'row-gap', 'column-gap',
  'display', 'position', 'z-index', 'cursor', 'fill', 'stroke', 'visibility'];
const INTERACTIVE = 'a,button,input,select,textarea,summary,[role=button],[role=tab],[role=menuitem],[role=checkbox],[role=switch],[tabindex]';
const STATES = { hover: ['hover'], focus: ['focus', 'focus-visible'], active: ['active'] };
const MOST_INTERACTIVE = 150;
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
  const hasPseudo = (el, pseudo) => { const content = getComputedStyle(el, pseudo).content; return content && content !== 'none' && content !== 'normal'; };
  const rows = [];
  for (const el of [document.body, ...document.body.querySelectorAll('*')]) {
    if (skipped.has(el.tagName) || getComputedStyle(el).display === 'none') continue;
    const row = { key: keyOf(el), default: read(el) };
    for (const pseudo of ['before', 'after']) if (hasPseudo(el, `::${pseudo}`)) row[pseudo] = read(el, `::${pseudo}`);
    rows.push(row);
  }
  return { rows, interactive: [...document.querySelectorAll(interactive)].map(keyOf) };
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

function compact(rows, states) {
  const sigs = [], seen = new Map();
  const index = (look) => { const text = JSON.stringify(look); if (!seen.has(text)) { seen.set(text, sigs.length); sigs.push(look); } return seen.get(text); };
  const els = {};
  for (const { key, ...looks } of rows) els[key] = Object.fromEntries(Object.entries(looks).map(([name, look]) => [name, index(look)]));
  for (const row of states) if (els[row.key]) for (const [state, look] of Object.entries(row.states)) els[row.key][state] = index(look);
  return { sigs, els };
}

async function snapshot(page) {
  await page.addStyleTag({ content: QUIET });
  const { rows, interactive } = await page.evaluate(inPage, { properties: PROPERTIES, interactive: INTERACTIVE });
  return compact(rows, await forced(page, interactive));
}

module.exports = { snapshot, PROPERTIES };
