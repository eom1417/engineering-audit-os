// The selection (SEL-01..04), shared by Problems, the plan and the maps: the problems ticked (at most 500, the
// contract's selection.schema.cards.maxItems), the group picked whole, and the contract's selection the server
// resolves from the latest check (`card`, `cards`, `group` or `step`; docs/studio-actions.json `selection`).
// The groups a person can pick whole come from the report: area, severity, component (the map's owner of a problem's
// first path), gap and operation (the story's gap rows) and plan step (studio/src/command/groups.ts, ported).
import { section } from './source.js';

export const MAX_CARDS = 500;
const SEVERITIES = ['critical', 'high', 'medium', 'low'];

/** The ticked ids (in the order ticked) and the group they were picked as, if any ({by, value, label}). */
export const picked = { ids: new Set(), group: null, anchor: null };

export function clearSelection() { picked.ids.clear(); picked.group = null; picked.anchor = null; }

/** Ticks or unticks `id`; with shift, every id between the last tick and `id` in `order` takes the same state. */
export function toggle(id, on, shift, order) {
  const from = picked.anchor ? order.indexOf(picked.anchor) : -1, to = order.indexOf(id);
  const span = shift && from >= 0 && to >= 0 ? order.slice(Math.min(from, to), Math.max(from, to) + 1) : [id];
  for (const each of span) {
    if (!on) picked.ids.delete(each);
    else if (picked.ids.size < MAX_CARDS) picked.ids.add(each);
  }
  picked.anchor = shift && from >= 0 ? picked.anchor : id;
  picked.group = null;
  return on && picked.ids.size >= MAX_CARDS && !picked.ids.has(id) ? 'max' : 'ok';
}

/** Replaces the selection with these ids (the shown list, a plan step's problems), or a whole group. */
export function pick(ids, group) {
  picked.ids = new Set([...new Set(ids)].slice(0, MAX_CARDS));
  picked.group = group || null;
  picked.anchor = null;
}

/** The contract's selection: the group by name where the server resolves it the same way, else the ids as seen. */
export function toSelection() {
  const ids = [...picked.ids], group = picked.group;
  if (!ids.length) return null;
  if (group && group.by === 'step') return { kind: 'step', step: group.value };
  if (group && (group.by === 'area' || group.by === 'severity')) return { kind: 'group', group: { by: group.by, value: group.value } };
  return ids.length === 1 ? { kind: 'card', cards: ids } : { kind: 'cards', cards: ids };
}

/** The component owning a path: the deepest component of the map (system.json, else the story's) that is a
 *  slash-boundary ancestor of it, else the root. */
export function ownerOf(names) {
  const components = new Set(names.filter(n => n !== '(root)'));
  const root = names.includes('(root)') ? '(root)' : undefined;
  return path => {
    let ancestor = path;
    for (;;) {
      if (components.has(ancestor)) return ancestor;
      const slash = ancestor.lastIndexOf('/');
      if (slash < 0) return root;
      ancestor = ancestor.slice(0, slash);
    }
  };
}

let owners = null, ownersFrom = null;
/** The component of a problem (its first path's owner); '(root)' when the map has none. */
export function componentOf(card) {
  const system = section('system'), story = section('story');
  const from = system || story;
  if (ownersFrom !== from) {
    const names = system ? system.current.nodes.map(n => n.id) : ((story && story.current.components) || []).map(c => c.name);
    owners = ownerOf(names);
    ownersFrom = from;
  }
  return (card.paths[0] && owners(card.paths[0])) || '(root)';
}

function bucket(entries) {
  const out = new Map();
  for (const [key, id] of entries) { if (!out.has(key)) out.set(key, []); out.get(key).push(id); }
  return out;
}

/** Every group of open problems a person can pick whole: {area, severity, component, gap, operation, step}, each a
 *  list of {by, value, label, ids}, the largest first (severities and steps in their own order). */
export function groupsOf(cards) {
  const open = cards.filter(c => c.state === 'open');
  const known = new Set(open.map(c => c.id));
  const sorted = groups => groups.filter(g => g.ids.length).sort((a, b) => b.ids.length - a.ids.length || a.label.localeCompare(b.label));
  const groups = (by, map) => [...map.entries()].filter(([value]) => value).map(([value, ids]) => ({ by, value, label: value, ids }));
  const story = section('story'), plans = section('plans');
  const gaps = ((story && story.gap) || []).filter(row => row.relation !== 'retain');
  const byRelation = new Map();
  for (const row of gaps) {
    if (!byRelation.has(row.relation)) byRelation.set(row.relation, new Set());
    for (const id of row.cards) if (known.has(id)) byRelation.get(row.relation).add(id);
  }
  const milestones = bucket(open.map(c => [c.milestone || '', c.id]));
  const steps = ((plans && plans.plans[0] && plans.plans[0].steps) || []).map(s => ({ by: 'step', value: s.id, label: s.id,
    ids: milestones.get(s.id) || s.tasks.map(t => t.id).filter(id => known.has(id)) }));
  return {
    area: sorted(groups('area', bucket(open.map(c => [c.category, c.id])))),
    severity: SEVERITIES.map(value => ({ by: 'severity', value, label: value, ids: open.filter(c => c.severity === value).map(c => c.id) })).filter(g => g.ids.length),
    component: sorted(groups('component', bucket(open.map(c => [componentOf(c), c.id])))),
    gap: sorted(gaps.map(row => ({ by: 'gap', value: row.component, label: row.component, ids: row.cards.filter(id => known.has(id)) }))),
    operation: sorted([...byRelation.entries()].map(([value, ids]) => ({ by: 'operation', value, label: value, ids: [...ids] }))),
    step: steps.filter(g => g.ids.length),
  };
}
