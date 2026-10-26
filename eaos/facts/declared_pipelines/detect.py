"""Pipelines and flowcharts: whether the project, or a part of it, is a pipeline, and its stages, edges and routers.

A pipeline is found only from what the code declares or does, never guessed from names alone:
  - a declared DAG: a list of stage records whose `requires` name other stages, run through a registry of runners;
  - a declared sequence: a list of steps holding the functions a driver calls one after the other;
  - a registry loop: a loop over stage names dispatching through a table, each stage's inputs taken from what the
    earlier stages put in an accumulator;
  - an orchestrator: a function announcing its phases in order, or one whose calls pass one stage's result to the next;
  - the frameworks' own declarations (Airflow, Prefect, Dagster, Luigi, Celery canvas, LangGraph, Temporal), queue
    topologies (a topic both produced and consumed), and the build and CI chains (GitHub Actions `needs`, Make and just
    targets, npm script chains, n8n / Node-RED / Step Functions exports).
Every stage, edge and branch carries the file and line it was read from. A dispatch EAOS cannot follow is written as an
unresolved step, never as an edge. The project is not run: Python is read with the standard `ast`, the rest as text.
"""

import ast
import json
from collections import defaultdict
from pathlib import Path

from .. import digest, make
from .python_code import declared_lists
from .orchestrators import phases, orchestrators
from .registry import registry_loops
from .python_frameworks import airflow, celery, luigi
from .files import github_actions, make_targets, npm_scripts, json_exports
from .langgraph import langgraph
from .queues import queues
from .read import slug, site, Py, _str, _unparse, KINDS, HOW, DETECTED_AT

NAME = 'pipeline'


VERSION = '1'


LIMITATIONS = [
    'Read from the code, never by running it: a graph built at run time from data is an unresolved step, not an edge.',
    'Python is read with its own parser; JavaScript and other languages only through their build files (package.json, CI).',
    'An orchestrator counts only where the code passes one stage\'s result to the next, or announces its phases in order.',
    'A side channel is found where a stage writes a shared context key, global or environment variable another reads.',
]


def _files(project, source=None):
    """(rel, text) of every file the scan reads: the project's in-scope, non-test files."""
    from ...core.contracts.vocabulary import classify
    if source is None:
        from ..scope import declared_exclusions
        from ..source import Source
        source = Source(project, exclude=list(declared_exclusions(project)) + ['node_modules', '.venv', 'venv', 'dist', 'build'])
    for item in source.readable():
        rel = item['path']
        if classify(rel) == 'test': continue
        name = Path(rel).name
        wanted = rel.endswith('.py') or name in ('package.json', 'Makefile', 'makefile', 'GNUmakefile', 'justfile', 'Justfile') \
            or ('.github/workflows/' in rel and rel.endswith(('.yml', '.yaml'))) or rel.endswith(('.asl.json', '.json'))
        if not wanted: continue
        text = source.text(rel)
        if text is not None: yield rel, text


def scan(project, source=None):
    """The pipelines of a project, as one record (see the module's docstring). Never runs the project."""
    found, flows = [], set()
    python, others = [], []
    for rel, text in _files(project, source):
        (python if rel.endswith('.py') else others).append((rel, text))
    py = Py(python)
    declared_lists(py, found)
    registry_loops(py, found)
    phases(py, found)
    airflow(py, found, flows)
    tasks = celery(py, found) or {}
    langgraph(py, found)
    luigi(py, found)
    queues(py, found)
    covered = {pair for f in found for pair in f.functions}
    orchestrators(py, found, tasks, flows, covered)
    for rel, text in others: _file_pipelines(rel, text, found)
    _link_sub_pipelines(found)
    for f in found:
        if not f.fans: _fans_from_edges(f)
        _globals_and_env(py, f)
    return _record(found, py)


def _file_pipelines(rel, text, found):
    """The pipelines a build, CI or workflow file declares, read by the kind of file it is."""
    name = Path(rel).name
    if '.github/workflows/' in rel: github_actions(rel, text, found)
    elif name.lower() in ('makefile', 'gnumakefile'): make_targets(rel, text, found, 'makefile')
    elif name.lower() == 'justfile': make_targets(rel, text, found, 'justfile')
    elif name == 'package.json': npm_scripts(rel, text, found)
    elif rel.endswith('.json'): json_exports(rel, text, found)


def _link_sub_pipelines(found):
    """A stage whose function is another pipeline's orchestrator opens that pipeline: its sub-pipeline."""
    by_function = {}
    for f in found:
        for path_name in f.functions: by_function.setdefault(path_name, f)
    for f in found:
        for stage in f.stages.values(): _open_sub_pipeline(f, stage, by_function)


def _stage_candidates(stage):
    """The (file, function) pairs a stage may run: its callable, and the function its symbol names."""
    target = stage.pop('callable', None)
    symbol = stage.get('symbol') or ''
    candidates = [target] if target else []
    if symbol and '.' in symbol:
        module, name = symbol.rsplit('.', 1)
        candidates.append((module.replace('.', '/') + '.py', name))
    return candidates


def _open_sub_pipeline(f, stage, by_function):
    for candidate in _stage_candidates(stage):
        child = by_function.get(candidate)
        if child is not None and child is not f and child.parent is None:
            stage['sub_pipeline'], child.parent = child.id, stage['id']
            return


KIND_ORDER = [kind for kind, _ in KINDS]
FAN_KINDS = ('declared_dag', 'registry_loop', 'orchestrator', 'airflow', 'langgraph', 'prefect', 'dagster')


def _stage_links(found):
    real = {k for k, s in found.stages.items() if s['kind'] not in ('router', 'fork', 'join')}
    outgoing, incoming = defaultdict(list), defaultdict(set)
    for a, b in found.edges:
        if a in real and b in real: outgoing[a].append(b); incoming[b].add(a)
    return outgoing, incoming


def _fan(found, fork, branches, incoming):
    if len(branches) < 2: return None
    joins = [s for s, sources in incoming.items() if set(branches) <= sources]
    if found.kind not in ('airflow', 'langgraph') and not joins:
        # Elsewhere one value read by two later stages is not a parallel fan-out: only a fork whose branches meet
        # again is drawn as one.
        return None
    return {'id': f'{fork}:fan', 'pipeline': found.id, 'fork': fork, 'join': joins[0] if joins else None,
            'branches': sorted(branches, key=found.order.index), 'matched': bool(joins),
            'kind': 'parallel' if found.kind == 'airflow' else 'collect', 'evidence': found.stages[fork]['entry']}


def _fans_from_edges(found):
    if found.kind not in FAN_KINDS: return
    outgoing, incoming = _stage_links(found)
    for fork, branches in sorted(outgoing.items()):
        fan = _fan(found, fork, branches, incoming)
        if fan: found.fans.append(fan)


def _stage_node(py, stage):
    """(file, function node) a stage's symbol names in its own entry file, or (None, None)."""
    symbol = stage.get('symbol') or ''
    if '.' not in symbol: return None, None
    module, name = symbol.rsplit('.', 1)
    rel = module.replace('.', '/') + '.py'
    node = py.defs.get(rel, {}).get(name)
    if node is None or rel != stage['entry']['path']: return None, None
    return rel, node


def _global_use(sub, declared, py, rel):
    """(writes, channel, located) when the node uses a module global; None otherwise."""
    if not isinstance(sub, ast.Name): return None
    if sub.id in declared: return isinstance(sub.ctx, ast.Store), ('global', sub.id), True
    if isinstance(sub.ctx, ast.Load) and sub.id in py.assigns.get(rel, {}) and sub.id.isupper() is False and sub.id.islower():
        return False, ('global', sub.id), False
    return None


def _env_use(sub):
    """(writes, channel, located) when the node uses an environment variable; None otherwise."""
    if isinstance(sub, ast.Subscript) and _unparse(sub.value) == 'os.environ' and _str(sub.slice):
        return isinstance(sub.ctx, ast.Store), ('env', _str(sub.slice)), True
    if isinstance(sub, ast.Call) and _unparse(sub.func) in ('os.environ.get', 'os.getenv') and sub.args and _str(sub.args[0]):
        return False, ('env', _str(sub.args[0])), False
    return None


def _stage_channels(py, key, stage, channels):
    rel, node = _stage_node(py, stage)
    if node is None: return
    declared = {n for s in ast.walk(node) if isinstance(s, ast.Global) for n in s.names}
    for sub in ast.walk(node):
        use = _global_use(sub, declared, py, rel) or _env_use(sub)
        if use is None: continue
        writes, channel, located = use
        (channels['writes'] if writes else channels['reads'])[channel].add(key)
        if located: channels['where'].setdefault(channel, (rel, sub.lineno))


def _globals_and_env(py, found):
    """Module globals and environment variables one stage writes and another reads, beside the declared flow."""
    channels = {'writes': defaultdict(set), 'reads': defaultdict(set), 'where': {}}
    for key, stage in found.stages.items(): _stage_channels(py, key, stage, channels)
    for (channel, name), writers in channels['writes'].items():
        readers = channels['reads'].get((channel, name), set()) - writers
        if not readers: continue
        rel, line = channels['where'][(channel, name)]
        found.hidden.append({'id': f'{found.id}:{channel}:{slug(name)}', 'pipeline': found.id, 'kind': 'side_channel', 'channel': channel,
                             'name': name, 'stages': sorted(writers | readers, key=found.order.index), 'evidence': site(rel, line, py.line(rel, line))})


def _record(found, py):
    pipelines = [f.record() for f in found if f.stages]
    product = [p for p in pipelines if p['role'] == 'product']
    confidence = max((p['confidence'] for p in product), default=None)
    detected = bool(product) and confidence >= DETECTED_AT
    kinds = sorted({p['kind'] for p in pipelines}, key=KIND_ORDER.index)
    evidence = [p['evidence'][0] if p['evidence'] else p['entry'] for p in product][:8]
    return {'detected': detected, 'confidence': confidence, 'kinds': kinds, 'evidence': evidence,
            'looked_for': _looked_for(pipelines), 'pipelines': pipelines, 'read': {'python_files': len(py.trees)}}


def _looked_for(pipelines):
    """Each kind of pipeline looked for, how it is read, and how many were found."""
    counts = defaultdict(int)
    for p in pipelines: counts[p['kind']] += 1
    return [{'kind': kind, 'label': label, 'found': counts.get(kind, 0),
             'how': HOW.get(kind, 'read from the code without running it')} for kind, label in KINDS]


def run(target, source, **_):
    """The extractor: one fact per pipeline element, each located at its evidence, so a card or a page can cite it."""
    record = scan(target, source)
    facts = facts_of(record, source.content_fingerprint if hasattr(source, 'content_fingerprint') else '')
    return {'facts': facts, 'input_sha': digest(json.dumps(record, sort_keys=True, default=str).encode('utf-8')),
            'summary': {'detected': record['detected'], 'pipelines': len(record['pipelines']),
                        'stages': sum(len(p['stages']) for p in record['pipelines']), 'kinds': record['kinds']},
            'available': True, 'reason': None}


ELEMENTS = (('stages', 'pipeline_stage', 'entry'), ('edges', 'pipeline_edge', 'evidence'), ('routers', 'pipeline_router', 'entry'),
            ('fans', 'pipeline_fan', 'evidence'), ('control', 'pipeline_control', 'evidence'), ('error_lanes', 'pipeline_error', 'evidence'),
            ('hidden', 'pipeline_hidden', 'evidence'), ('unresolved', 'pipeline_unresolved', 'evidence'))


ELEMENT_FIELDS = {field for field, _, _ in ELEMENTS}


def _located(where):
    return {'path': where.get('path'), 'start_line': where.get('line')}


def _pipeline_facts(pipeline, sha):
    head = {k: v for k, v in pipeline.items() if k not in ELEMENT_FIELDS}
    rows = [make('pipeline', NAME, VERSION, sha, _located(pipeline['entry']), head)]
    rows += [make(kind, NAME, VERSION, sha, _located(item.get(at) or {}), {**item, 'index': index})
             for field, kind, at in ELEMENTS for index, item in enumerate(pipeline[field])]
    return rows


def facts_of(record, sha=''):
    rows = [make('pipeline_scan', NAME, VERSION, sha, {'path': '.', 'start_line': None},
                 {k: record[k] for k in ('detected', 'confidence', 'kinds', 'evidence', 'looked_for', 'read')})]
    for pipeline in record['pipelines']: rows += _pipeline_facts(pipeline, sha)
    return rows


def _pipelines_of(facts, record):
    """Fill `record` from the scan and pipeline facts; {pipeline id: its record}."""
    by_id = {}
    for row in facts:
        if row.get('kind') == 'pipeline_scan': record.update(row['value'])
        elif row.get('kind') == 'pipeline':
            pipeline = {**row['value'], 'fact': row['id'], **{field: [] for field, _, _ in ELEMENTS}}
            by_id[pipeline['id']] = pipeline
            record['pipelines'].append(pipeline)
    return by_id


def _attach_elements(facts, by_id):
    kinds = {kind: field for field, kind, _ in ELEMENTS}
    for row in facts:
        field = kinds.get(row.get('kind'))
        if not field: continue
        item = {k: v for k, v in row['value'].items() if k != 'index'}
        pipeline = by_id.get(item.get('pipeline'))
        if pipeline is None: continue
        item['fact'] = row['id']
        pipeline[field].append((row['value'].get('index', 0), item))


def _order_elements(pipeline):
    for field, _, _ in ELEMENTS:
        pipeline[field] = [item for _, item in sorted(pipeline[field], key=lambda pair: pair[0])]


def record_of(facts):
    """The record back from facts/pipeline.json's facts, each element with the id of its fact."""
    record = {'detected': False, 'confidence': None, 'kinds': [], 'evidence': [], 'looked_for': [], 'pipelines': []}
    _attach_elements(facts, _pipelines_of(facts, record))
    for pipeline in record['pipelines']: _order_elements(pipeline)
    return record


def write(report, record):
    """facts/pipeline.json of a report, as the facts stage writes it; returns its index entry."""
    from ..store import facts_dir, write_set
    facts_dir(report)
    rows = facts_of(record)
    return write_set(report, NAME, NAME, VERSION, LIMITATIONS,
                     {'facts': rows, 'input_sha': digest(json.dumps(record, sort_keys=True, default=str).encode('utf-8')),
                      'summary': {'detected': record['detected'], 'pipelines': len(record['pipelines'])}})


def read(report):
    """The record of a report's facts/pipeline.json, or None when the check did not write it."""
    path = Path(report) / 'facts' / 'pipeline.json'
    if not path.is_file(): return None
    try: return record_of(json.loads(path.read_text(encoding='utf-8')).get('facts') or [])
    except (OSError, ValueError): return None

