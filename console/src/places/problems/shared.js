// What the Problems list, one problem and their sheets share: the facets the address carries (who, sev, area,
// pstate, step, comp, q, group), the filtering and the derived fields of a problem.
import { t, L, has, model, selection, normalize } from 'eaos';

export const SEV = model.SEV;
export const AREAS = ['security', 'structure', 'quality', 'performance', 'ux', 'maintainability'];
export const STATES = ['open', 'in_batch', 'on_branch', 'done', 'resolved', 'skipped'];
/** pstate: the problem's state (the address keeps state= for the page's own state) */
export const FACETS = ['sev', 'area', 'pstate', 'step', 'comp'];
export const NEEDS = ['cards', 'plans', 'story', 'system'];

export const component = p => selection.componentOf(p);
export const who = model.who;
export const steps = () => model.plan().steps.map(s => s.id);

export function value(p, facet) {
  if (facet === 'sev') return p.severity;
  if (facet === 'area') return p.category || 'none';
  if (facet === 'pstate') return p.state;
  if (facet === 'step') return p.milestone || 'notplan';
  if (facet === 'comp') return component(p);
  return null;
}
export function list(q, key) { return (q[key] || '').split(',').filter(Boolean); }
/** A problem's kind in words, or its own name when the dictionary has none for it. */
export const kindWord = kind => (has('kind.' + kind) ? t('kind.' + kind) : kind);

export function filterProblems(all, q, except) {
  return all.filter(p => {
    if (q.who && q.who !== 'all' && who(p) !== q.who) return false;
    for (const f of FACETS) {
      if (f === except) continue;
      const vals = list(q, f);
      if (vals.length && !vals.includes(value(p, f))) return false;
    }
    if (q.q && !normalize.matches([p.id, L(p.title), p.paths.join(' '), p.kind, kindWord(p.kind), t('area.' + p.category), p.why ? L(p.why) : ''].join(' '), q.q)) return false;
    return true;
  });
}
export function activeFilters(q) {
  const out = [];
  FACETS.forEach(f => list(q, f).forEach(v => out.push({ f, v })));
  return out;
}
export function facetLabel(f, v) {
  if (f === 'sev') return t('sev.' + v);
  if (f === 'area') return t('area.' + v);
  if (f === 'pstate') return t('state.' + v);
  if (f === 'step') return v === 'notplan' ? t('facet.notplan') : v;
  return v;
}
export function keepQuery(q, extra) {
  const o = {};
  ['who', 'q', 'group', 'n'].concat(FACETS).forEach(k => { if (q[k]) o[k] = q[k]; });
  return Object.assign(o, extra || {});
}
