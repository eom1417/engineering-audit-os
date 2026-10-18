// The thin adapter between the report's sections (eaos/studio/export.py, schemas/artifacts/studio-*.schema.json) and
// the shapes the screens draw, which are the prototype's (studio-design/prototype/assets/data.js) wherever the report
// carries the same facts. Every getter reads the sections already loaded and is cached on their identity, so a live
// reload (a new section object) recomputes it and nothing else does. A getter whose section is not read returns the
// empty shape; a screen lists the sections it needs (`needs`) and the router reads them before drawing it.
// Report texts are kept as strings and drawn with L() (the report's words, or their translation). The words a
// screen composes from counts come from the dictionary, never from the report's sentences.
import { manifest, section } from './source.js';
import { live, answerOf, awaiting } from './store.js';

const cache = new Map();
/** `make()` once per identity of the sections in `from`. */
function memo(key, from, make) {
  const deps = from.map(section);
  const hit = cache.get(key);
  if (hit && hit.deps.every((d, i) => d === deps[i])) return hit.value;
  const value = make(...deps);
  cache.set(key, { deps, value });
  return value;
}

export const SEV = ['critical', 'high', 'medium', 'low', 'info'];
export const SEV_RANK = { critical: 0, high: 1, medium: 2, low: 3, info: 4 };
const CLOSED = ['done', 'resolved'];
const pct = m => (m && m.value != null ? Math.round(m.value * 100) : null);

/** The project and the check this report is of. */
export function project() {
  const m = manifest() || {}, head = section('head') || {};
  const scanned = head.scanned || m.scanned || {};
  return { name: (m.project && m.project.name) || '', branch: scanned.branch || '', commit: scanned.commit || '', checked_at: scanned.at || null,
    detached: !!scanned.detached, dirty: !!scanned.dirty, eaos_version: (head.eaos && head.eaos.version) || (m.built && m.built.version) || '',
    freshness: head.freshness || 'unknown', freshness_detail: head.freshness_detail || null, next_tool: head.next ? head.next.tool : null };
}

/** One problem as the screens draw it: the card's own fields, and what the assistant decided for it. */
function problemOf(card) {
  const r = card.resolution;
  const decision = !r ? null : r.kind === 'fix' ? { state: 'fixes', text: r.change || r.words, why: r.why, capped: !!r.capped }
    : { state: 'asks', question: r.question, options: r.options || [], recommendation: r.recommendation, decision: `card:${card.id}` };
  return Object.assign({}, card, { decision });
}

/** Every problem of the check, in the plan's order (the cards' order). */
export function problems() {
  return memo('problems', ['cards'], cards => ((cards && cards.cards) || []).map(problemOf));
}
export function problem(id) { return memo('problemIndex', ['cards'], () => new Map(problems().map(p => [p.id, p]))).get(id) || null; }
/** Who acts on a problem: the owner ('you', a decision or a skipped card) or EAOS by itself ('eaos'). */
export const who = p => (p.needs_decision ? 'you' : 'eaos');

/** The counts every page says (eaos/studio/model.py problem_counts): every card of the plan, those EAOS fixes by
 *  itself, those that need the owner, by severity; and the closed of every card seen over the checks (history). */
export function totals() {
  return memo('totals', ['cards', 'history'], (cards, history) => {
    const list = (cards && cards.cards) || [];
    const by_severity = Object.fromEntries(SEV.map(s => [s, 0]));
    list.forEach(c => { by_severity[c.severity] += 1; });
    const fixable = list.filter(c => c.fixable).length;
    const last = history && history.scans && history.scans[history.scans.length - 1];
    return { problems: list.length, fixable, needs_you: list.length - fixable, open: list.filter(c => !CLOSED.includes(c.state)).length,
      by_severity, closed: last ? last.closed : null, all_cards: last ? last.total : null };
  });
}

/** The health score and its areas, 0..100 (null: not measured). */
export function health() {
  return memo('health', ['health'], h => ({
    score: h ? pct(h.score) : null, formula: h ? h.formula : '',
    areas: ((h && h.domains) || []).map(d => ({ id: d.id, score: pct(d.score), cards: d.cards })),
    history: ((h && h.history) || []).map(x => ({ at: x.at, commit: x.commit, score: x.score == null ? null : Math.round(x.score * 100) })),
  }));
}

/** What the check read: files, lines, languages and every stage with its state. */
export function size() {
  return memo('size', ['meta'], m => ({
    files: m ? m.files.value : null, lines: m ? m.lines.value : null, languages: (m && m.languages) || [],
    stages: ((m && m.stages) || []).map(s => ({ id: s.id, title: s.title, state: s.state })),
  }));
}

/** Where a report decision comes from: the target structure, the review of the screens, a disagreement between the
 *  rules and the assistant, one problem's product choice, or the problems that need checking. */
function sourceOf(id) {
  if (id === 'target-architecture') return 'structure';
  if (id.startsWith('node-visual_reviewer')) return 'screens';
  if (id.startsWith('disagree-')) return 'disagreement';
  if (id.startsWith('card:')) return 'card';
  return 'check';
}

/** Every decision of the report, with the owner's answer saved in the live console (GET /api/decisions) folded in:
 *  `answered` then holds the saved response, and the decision no longer waits. */
export function decisions() {
  const base = memo('decisions', ['decisions'], d => ((d && d.decisions) || []).map(x => Object.assign({}, x, {
    source: sourceOf(x.id), recommended: x.recommended_option || null, asked_at: x.asked || null })));
  return base.map(d => {
    const saved = answerOf(d.id);
    return saved ? Object.assign({}, d, { state: 'answered', saved, answer: saved.option || null }) : d;
  });
}
export const waitingDecisions = () => decisions().filter(d => d.state === 'waiting');

/** The fix plan: its steps with their tasks (plans.json `fix`). */
export function plan() {
  return memo('plan', ['plans'], p => {
    const fix = p && (p.plans.find(x => x.kind === 'fix') || p.plans[0]);
    return { steps: (fix && fix.steps) || [], progress: fix ? fix.progress : null };
  });
}

/** One evidence fact by id, with the problems that rest on it. */
export function fact(id) {
  const index = memo('facts', ['evidence', 'cards'], (evidence, cards) => {
    const out = new Map(((evidence && evidence.facts) || []).map(f => [f.id, Object.assign({ cards: [] }, f)]));
    ((cards && cards.cards) || []).forEach(c => (c.evidence || []).forEach(e => { const f = out.get(e); if (f) f.cards.push(c.id); }));
    return out;
  });
  return index.get(id) || null;
}

/** An assistant's name (Claude Code, Codex) from its id, as this computer knows it. */
export function assistantName(id) {
  const found = (live.assistants || []).find(a => a.id === id);
  return found ? found.name : id || '';
}

/** The branches EAOS delivered that wait for the owner's Accept or Reject (live runs). */
export function waitingBranches() { return awaiting(); }

/** The one "waiting for you" count, the same everywhere (DEC-01): decisions not answered, delivered branches not
 *  decided, the sign-in a check waits for, and the questions runs ask. */
export function waitingCount() {
  return waitingDecisions().length + waitingBranches().length + (live.signIn && live.signIn.asked ? 1 : 0) + live.questions.length;
}
