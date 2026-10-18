// The report's facts builder B's views share, read from the sections already loaded (each view lists the sections it
// needs): the story's counts (today, the change, the target), the target structure's decision, the components of the
// map and a section's count from the coverage rows (so a door never reads a large section to count it).
import { model, data, selection } from 'eaos';
import { opOf } from './kit.js';

/** Today's components, the operation each takes (story.json gap) and the target's components. */
export function storyCounts() {
  const story = data.section('story'), system = data.section('system');
  const gap = (story && story.gap) || [];
  const ops = {};
  gap.forEach(g => { const o = opOf(g.relation); ops[o] = (ops[o] || 0) + 1; });
  const introduce = system && system.operations && system.operations.introduce ? system.operations.introduce.value : null;
  return {
    today: story ? story.current.components.length : null, target: story ? story.target.components.length : null,
    ops, change: gap.filter(g => opOf(g.relation) !== 'retain').length, introduced: introduce,
  };
}

/** The owner's decision on the target structure: 'approved', 'waiting' (proposed, waiting for the owner) or null. */
export function targetDecision() {
  const d = model.decisions().find(x => x.id === 'target-architecture');
  if (!d) return null;
  return d.state === 'waiting' ? 'waiting' : d.answer === 'approve' ? 'approved' : 'answered';
}

/** A section's count as the coverage rows give it (null: not counted), and its state. */
export function covered(name) {
  const row = ((data.section('coverage') || {}).sections || []).find(r => r.section === name);
  return row ? { n: row.count ? row.count.value : null, state: row.state } : { n: null, state: data.listed(name) ? 'measured' : 'not_measured' };
}

/** Today's components on the map (system.json current), by id. */
export function components() {
  const s = data.section('system');
  return (s && s.current.nodes) || [];
}
export const component = id => components().find(c => c.id === id) || null;
export const targets = () => { const s = data.section('system'); return (s && s.target.nodes) || []; };
export const targetOf = id => targets().find(x => x.id === id) || null;

/** The problems whose component (the map's owner of their first path) is `id`. */
export const problemsOf = id => model.problems().filter(p => selection.componentOf(p) === id);
