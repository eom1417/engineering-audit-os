"""What the ideal planner's bundle (eaos/ai/ideal/planner.py `bundle`) reads from a report besides the rules' target: the
project's own documents, the facts a plan needs, the features, the intake answers, the decisions waiting for the person
and the semantic hypotheses."""
import json
from pathlib import Path

from .base import EVIDENCE, LIMIT, _facts, _load
from ..nodes.framework import short, UNTRUSTED

DOCS = ('README.md', 'README', 'readme.md', 'ARCHITECTURE.md', 'CONTRIBUTING.md', 'docs/**/*.md', '*.md')


def docs(project):
    """The project's own documents, cut to size, marked as untrusted data."""
    if not project or not Path(project).is_dir(): return []
    project, seen, out, total = Path(project), set(), [], 0
    for pattern in DOCS:
        for path in sorted(project.glob(pattern)):
            rel = path.relative_to(project).as_posix()
            if rel in seen or not path.is_file() or 'node_modules/' in rel or rel.startswith('.'): continue
            seen.add(rel)
            text = path.read_text(encoding='utf-8', errors='replace')[:LIMIT['doc_chars']]
            if total + len(text) > LIMIT['docs_chars']: return out
            total += len(text)
            out.append({'id': f'DOC:{rel}', 'path': rel, 'trust': UNTRUSTED, 'text': text})
    return out


def facts_digest(report):
    """The facts a plan needs, each with its id: entries, flows, tables, runtime, cycles, dead code, config names."""
    report = Path(report)
    take = lambda rows, make: [make(f) for f in rows[:LIMIT['facts']]]
    where = lambda f: (f.get('location') or {}).get('path')
    entry = _of_kind(_facts(report, 'entrypoints'), 'entry_point')
    access = _of_kind(_facts(report, 'entrypoints'), 'data_access')
    domain = [f for f in _facts(report, 'domain') if f.get('kind') != 'data_model' or (f.get('value') or {}).get('kind') in ('table', 'sql_table')]
    graph = _of_kind(_facts(report, 'graph'), 'graph_node')
    graph.sort(key=lambda f: (f.get('value') or {}).get('attention_rank', 999))
    return {
        'entry_points': take(entry, lambda f: {'id': f['id'], 'surface': (f['value'] or {}).get('surface'),
                                               'route': (f['value'] or {}).get('route'), 'path': where(f)}),
        'data_access': take(access, lambda f: {'id': f['id'], 'path': where(f), **{k: (f['value'] or {}).get(k) for k in
                                                                                  ('operation', 'table', 'route', 'http_method', 'client') if (f['value'] or {}).get(k)}}),
        'flows': take(_facts(report, 'flows'), lambda f: {'id': f['id'], 'entry': ((f['value'] or {}).get('entry') or {}).get('route'),
                                                          'files': ((f['value'] or {}).get('touched_files') or [])[:6],
                                                          'unresolved': len((f['value'] or {}).get('unresolved') or [])}),
        'domain': take(domain, lambda f: {'id': f['id'], 'kind': f.get('kind'), 'name': (f['value'] or {}).get('name'), 'path': where(f)}),
        'runtime': take(_facts(report, 'runtime') + _facts(report, 'config'),
                        lambda f: {'id': f['id'], 'kind': f.get('kind'), 'path': where(f),
                                   'what': short(json.dumps({k: v for k, v in (f.get('value') or {}).items() if k != 'snippet'}), 120)}),
        'hubs': take(graph, lambda f: {'id': f['id'], 'path': where(f), 'fan_in': (f['value'] or {}).get('fan_in'),
                                       'fan_out': (f['value'] or {}).get('fan_out')}),
        'cycles': take(_of_kind(_facts(report, 'graph'), 'graph_cycle'),
                       lambda f: {'id': f['id'], 'members': (f['value'] or {}).get('members')}),
        'dead_code': take(_facts(report, 'deadcode'), lambda f: {'id': f['id'], 'path': where(f), 'rule': (f['value'] or {}).get('rule')}),
    }


def _of_kind(facts, kind):
    """The facts of one kind."""
    return [f for f in facts if f.get('kind') == kind]


def cited(row, most):
    """A record's evidence ids a citation may resolve to, at most `most`."""
    return [e for e in row.get('evidence') or [] if isinstance(e, str) and EVIDENCE.match(e)][:most]


def features(report):
    return [{'name': f.get('name'), 'surfaces': (f.get('surfaces') or [])[:6], 'tables': (f.get('tables') or [])[:6], 'evidence': cited(f, 3)}
            for f in (_load(Path(report) / 'features.json', {}) or {}).get('features') or [] if isinstance(f, dict)][:40]


def intake(report):
    return [{'question': short(q.get('question'), 160), 'answer': short(q.get('answer'), 160), 'status': q.get('status')}
            for q in (_load(Path(report) / 'intake.json', {}) or {}).get('questions') or [] if isinstance(q, dict)][:30]


def waiting(report, project):
    """The decisions waiting for the person, each with the answer they saved in the Studio, if any."""
    rows = (_load(Path(report) / 'studio/decisions.json', {}) or {}).get('decisions') or []
    out = [{'id': d.get('id'), 'question': short(d.get('question'), 200), 'state': d.get('state')} for d in rows if isinstance(d, dict)]
    if not project: return out
    from ...core.project.places import workspace
    from ...core.project.runs import _read_json, decision_scope
    responses = _read_json(workspace(Path(project).resolve()) / 'runs/decisions.json', {}) or {}
    for item, source in zip(out, rows):
        response = responses.get(decision_scope(Path(report) / 'studio', source))
        if response: item.update(owner_answer=response, state='owner_answer_saved')
    return out


def semantic(report):
    """The semantic stage's hypotheses with the facts each stands on, and its open questions."""
    found = _load(Path(report) / 'semantic.json', {}) or {}
    return {'hypotheses': [{'id': c.get('id'), 'statement': short(c.get('statement'), 300), 'facts': (c.get('fact_ids') or [])[:4]}
                           for c in found.get('claims') or [] if isinstance(c, dict)][:30],
            'questions': [short(q.get('question'), 200) for q in found.get('questions') or [] if isinstance(q, dict)][:20]}
