"""CodeGraph engine: imports, calls, complexity, hot paths across every language the engine parses.

Four tools, all run as one-shot invocations against the pinned CodeGraph binary:

  codegraph_get_dependency_graph  module and file dependency graph
  codegraph_get_call_graph        callers/callees of a symbol
  codegraph_analyze_complexity    per-symbol complexity (lines, branches, etc.)
  codegraph_find_hot_paths        ranked call-paths through the codebase

Each tool returns a JSON payload. The wrapper flattens the payload into the engine's
fact shape and emits a `module_edge_external` / `call_edge_external` fact for each
call or import. Tools that return a warning ("unknown tool", "invalid URI", "missing
parameter") are downgraded to `partial` and the reason recorded in the summary.

The wrapper never guesses what the tool would have returned; if the payload is empty
or it failed, the tool is recorded as DECLINED with a measured reason.
"""
import json
import subprocess
from pathlib import Path

from .contract import OBSERVED, Report, SYMBOL, UNAVAILABLE, finding, measurement, subject

NAME, VERSION, PINNED = 'codegraph', '1', 'v0.20.1'

TOOLS = {
    'codegraph_get_dependency_graph': 'module_edge_external',
    'codegraph_get_call_graph': 'call_edge_external',
    'codegraph_analyze_complexity': 'symbol_metric_external',
    'codegraph_find_hot_paths': 'hot_path_external',
}

BINARY = '/workspace/engine-tools/bin/codegraph-server'


def _run(tool, args, workspace, timeout=600):
    """One tool, one payload. Never raise: return (payload_str_or_None, error_str_or_None)."""
    cmd = [BINARY, '--graph-only', '-w', str(workspace),
           '--run-tool', tool, '--tool-args', json.dumps(args or {})]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        out = result.stdout.strip()
        err = result.stderr.strip()
        if 'Tool ' in err and ' failed: ' in err:
            return out or None, err.split('Tool ', 1)[-1].split(' failed: ', 1)[-1].strip()
        if result.returncode != 0 and not out:
            return None, err or f'exit {result.returncode}'
        if not out:
            return None, 'empty payload'
        return out, None
    except subprocess.TimeoutExpired:
        return None, f'timeout after {timeout}s'
    except FileNotFoundError:
        return None, f'binary missing at {BINARY}'


def _parse_payload(text):
    if not text: return None
    text = text.strip()
    if not text.startswith('{'):
        for line in text.splitlines():
            line = line.strip()
            if line.startswith('{'):
                text = line; break
    try: return json.loads(text)
    except ValueError: return None


def _module_edges_from_dep_graph(payload, root):
    """Turn one file's dependency payload into module edges whose ends are named, not numbered.

    The payload numbers its ends: `edges[].from` and `.to` are node ids. Only a node of type
    `codefile` carries a real path; a `module` node carries a name and an empty path. Emitting the
    raw ids would hand the reader a number it cannot resolve, so an edge whose ends we cannot name
    is dropped rather than recorded as an edge between unknowns.
    """
    if not isinstance(payload, dict): return []
    nodes = {str(node.get('id')): node for node in payload.get('nodes') or []}
    facts = []
    for edge in payload.get('edges') or []:
        if edge.get('type') not in (None, 'import'): continue
        source, destination = nodes.get(str(edge.get('from'))), nodes.get(str(edge.get('to')))
        if not source or not destination: continue
        from_path = source.get('path') or ''
        to_name = destination.get('name') or destination.get('path') or ''
        if not from_path or not to_name: continue
        facts.append({'kind': 'module_edge_external',
                      'location': {'path': _relative(from_path, root)},
                      'value': {'from': _relative(from_path, root), 'to': to_name,
                                'to_path': _relative(destination.get('path') or '', root) or None,
                                'to_is_external': bool(destination.get('is_external')),
                                'language': destination.get('language') or source.get('language') or '',
                                'weight': 1, 'tool': 'codegraph_get_dependency_graph'}})
    return facts


def _relative(path, root):
    """A path the reader can open: relative to the scanned tree, never the engine's absolute path."""
    if not path: return ''
    try: return str(Path(path).resolve().relative_to(Path(root).resolve()))
    except (ValueError, OSError): return str(path)


def _call_edges_from_call_graph(payload, root):
    facts = []
    symbol = payload.get('symbol', {}) if isinstance(payload, dict) else {}
    path = symbol.get('path', root) if isinstance(symbol, dict) else root
    for call in payload.get('callees', []) or []:
        facts.append({'kind': 'call_edge_external',
                      'location': {'path': path},
                      'value': {'caller': symbol.get('name', ''),
                                 'callee': call.get('name', ''),
                                 'callee_path': call.get('path', ''),
                                 'line': call.get('line_start', 0),
                                 'tool': 'codegraph_get_call_graph'}})
    for call in payload.get('callers', []) or []:
        facts.append({'kind': 'call_edge_external',
                      'location': {'path': path},
                      'value': {'caller': call.get('name', ''),
                                 'callee': symbol.get('name', ''),
                                 'caller_path': call.get('path', ''),
                                 'line': call.get('line_start', 0),
                                 'tool': 'codegraph_get_call_graph'}})
    return facts


def _complexity_facts(payload, root, path=None):
    """Per-symbol complexity for one file. The file is the caller's, not the payload's.

    `codegraph_analyze_complexity` answers about the file named in its `uri` and does not repeat
    that path in every function it returns. Recording the scanned root instead would put every
    measurement at `.` and make it unjoinable to a flow, so the caller's path is authoritative.
    """
    if not isinstance(payload, dict): return []
    fns = payload.get('functions', payload.get('symbols', [])) or []
    out = []
    for fn in fns:
        detail = fn.get('details') or {}
        out.append({'kind': 'symbol_metric_external',
                     'location': {'path': path or fn.get('path') or root,
                                  'line': fn.get('line_start', 0)},
                     'value': {'name': fn.get('name', ''),
                                'lines': detail.get('lines_of_code', fn.get('lines', 0)),
                                'branches': detail.get('complexity_branches', fn.get('branches', 0)),
                                'loops': detail.get('complexity_loops', 0),
                                'nesting': detail.get('complexity_nesting', 0),
                                'complexity': fn.get('complexity', 0),
                                'grade': fn.get('grade', ''),
                                'rule': 'performance',
                                'tool': 'codegraph_analyze_complexity'}})
    return out


def _hot_paths(payload, root):
    if not isinstance(payload, dict): return []
    out = []
    for path in payload.get('paths', payload.get('hot_paths', [])) or []:
        out.append({'kind': 'hot_path_external',
                     'location': {'path': root},
                     'value': {'symbol': path.get('symbol', ''),
                                'transitive_callers': path.get('transitive_callers', 0),
                                'score': path.get('score', 0),
                                'tool': 'codegraph_find_hot_paths'}})
    return out


CONVERTERS = {
    'codegraph_get_dependency_graph': _module_edges_from_dep_graph,
    'codegraph_get_call_graph': _call_edges_from_call_graph,
    'codegraph_analyze_complexity': _complexity_facts,
    'codegraph_find_hot_paths': _hot_paths,
}


# One `--run-tool` invocation costs about two seconds against a warm index, so asking about
# every file in a large tree would turn an optional stage into the longest one in the run. We ask
# about the files the report actually speaks about -- entry points and the files their flows
# touch -- and record the cap, so a reader can tell a file we did not ask about from one the
# engine had nothing to say about.
FILE_BUDGET = 60

# Somebody else's samples and fixtures. A hot path through them is a fact about their code.
NOT_THE_READER_S_CODE = ('testdata/', '/testdata/', 'fixtures/', '/fixtures/', 'vendor/', '/vendor/',
                         'node_modules/', 'third_party/', '/examples/', 'generated/')


def _is_the_reader_s_code(path):
    text = str(path).replace('\\', '/')
    return not any(marker in text for marker in NOT_THE_READER_S_CODE)


def run(target, out, tools=None, files=None, **options):
    """Query CodeGraph about files, because that is the only question it answers.

    Every graph tool here takes a `uri`. Given a directory it returns an empty graph, and given
    no `uri` at all it refuses the call outright; the index behind it is the same either way. So
    the unit of work is one file, and `files` names the ones worth asking about. With no list we
    ask about nothing and say so, rather than asking about the root and recording the empty
    answer as a finding of no dependencies.
    """
    target = Path(target).resolve()
    available = Path(BINARY).is_file()
    summary = {'binary': BINARY, 'tools': {}, 'partial': [], 'declined': [],
               'files_asked': 0, 'file_budget': FILE_BUDGET}
    if not available:
        summary['declined'].append({'tool': '*', 'reason': 'binary missing'})
        return {'facts': [], 'summary': summary, 'available': False,
                'input_sha': '', 'reason': f'CodeGraph binary not installed at {BINARY}'}
    facts = []
    tool_selection = tools or {}

    asked = [path for path in (files or []) if (target / path).is_file() and _is_the_reader_s_code(path)]
    summary['files_offered'] = len(files or [])
    asked = sorted(dict.fromkeys(asked))[:FILE_BUDGET]
    summary['files_asked'] = len(asked)
    if not asked:
        # A tool we chose not to run is absent from the record; a tool we wanted to run and could
        # not ask is present and says why. Conflating the two would hide a silent skip.
        for tool, selector in (('codegraph_get_dependency_graph', 'get_dependency_graph'),
                               ('codegraph_analyze_complexity', 'analyze_complexity'),
                               ('codegraph_get_call_graph', 'get_call_graph')):
            if not tool_selection.get(selector, True): continue
            summary['tools'][tool] = 'partial'
            summary['partial'].append({'tool': tool, 'reason': 'no file was named for this run'})

    if asked and tool_selection.get('get_dependency_graph', True):
        errors, produced = [], 0
        for path in asked:
            text, err = _run('codegraph_get_dependency_graph',
                             {'uri': f'file://{target / path}', 'direction': 'both', 'depth': 1}, target)
            if err: errors.append(err); continue
            payload = _parse_payload(text)
            if payload:
                new_facts = CONVERTERS['codegraph_get_dependency_graph'](payload, target)
                produced += len(new_facts)
                facts.extend(new_facts)
        _record_many(summary, 'codegraph_get_dependency_graph', produced, errors, len(asked))

    if asked and tool_selection.get('analyze_complexity', True):
        errors, produced = [], 0
        for path in asked:
            text, err = _run('codegraph_analyze_complexity', {'uri': f'file://{target / path}'}, target)
            if err: errors.append(err); continue
            payload = _parse_payload(text)
            if payload:
                new_facts = _complexity_facts(payload, target, path=path)
                produced += len(new_facts)
                facts.extend(new_facts)
        _record_many(summary, 'codegraph_analyze_complexity', produced, errors, len(asked))

    if tool_selection.get('find_hot_paths', True):
        text, err = _run('codegraph_find_hot_paths', {'limit': 20, 'depth': 3}, target)
        _record(summary, 'codegraph_find_hot_paths', text, err)
        payload = _parse_payload(text)
        if payload:
            hot = CONVERTERS['codegraph_find_hot_paths'](payload, str(target))
            kept = [fact for fact in hot if _is_the_reader_s_code(fact['value'].get('path') or fact['location']['path'])]
            if len(kept) < len(hot):
                summary['hot_paths_in_somebody_elses_code'] = len(hot) - len(kept)
            facts.extend(kept)

    if asked and tool_selection.get('get_call_graph', True):
        # Ask about the symbols the report already names. On Go the engine answers with an empty
        # edge list and a diagnostic saying its parser extracts no call edges; that is a measured
        # limit of the engine, and it is recorded as one rather than retried against more files.
        landed, diagnostics = 0, []
        for path in asked[:10]:
            text, err = _run('codegraph_get_call_graph',
                             {'uri': f'file://{target / path}', 'name': Path(path).stem, 'depth': 2}, target)
            if err: diagnostics.append(err); continue
            payload = _parse_payload(text)
            if not payload: continue
            produced = CONVERTERS['codegraph_get_call_graph'](payload, path)
            if produced:
                facts.extend(produced); landed += 1
            elif isinstance(payload.get('diagnostic'), dict):
                note = payload['diagnostic'].get('note')
                if note and note not in diagnostics: diagnostics.append(note)
        if landed:
            summary['tools']['codegraph_get_call_graph'] = 'ok'
        else:
            summary['tools']['codegraph_get_call_graph'] = 'partial'
            summary['partial'].append({'tool': 'codegraph_get_call_graph',
                                        'reason': diagnostics[0] if diagnostics
                                                  else 'the engine returned no call edge for any file asked'})
    return {'facts': facts, 'summary': summary,
            'available': True, 'input_sha': '', 'reason': None}


def _record_many(summary, tool, produced, errors, asked):
    """Record a per-file tool once: how many files were asked, and why any of them refused."""
    summary.setdefault('per_tool', {})[tool] = {'files_asked': asked, 'facts': produced,
                                                'errors': len(errors)}
    if produced:
        summary['tools'][tool] = 'ok'
    elif errors:
        summary['tools'][tool] = 'partial'
        summary['partial'].append({'tool': tool, 'reason': errors[0]})
    else:
        summary['tools'][tool] = 'partial'
        summary['partial'].append({'tool': tool,
                                    'reason': f'{asked} file(s) asked, none produced a payload'})


def _record(summary, tool, text, err):
    if err:
        summary['tools'][tool] = 'declined' if 'binary missing' in err else 'partial'
        summary['declined'].append({'tool': tool, 'reason': err})
    elif text:
        summary['tools'][tool] = 'ok'
    else:
        summary['tools'][tool] = 'partial'
        summary['partial'].append({'tool': tool, 'reason': 'no payload'})

def version():
    """Return the installed CodeGraph version, or None if missing."""
    import subprocess
    if not Path(BINARY).is_file(): return None
    try:
        result = subprocess.run([BINARY, '--version'], capture_output=True, text=True, timeout=30)
        return (result.stdout + result.stderr).strip().splitlines()[-1].strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None

def capabilities():
    """One Capability per tool the wrapper exposes. The kind is the fact vocabulary each produces."""
    from eaos.engines.contract import Capability
    return [Capability(kind=kind, rule='codegraph:' + tool, granularity='file')
            for tool, kind in TOOLS.items()]


GRAPH_FACTS = 'graph-facts.json'


def analyze(target, workdir, exclude=(), formats=None):
    """The adapter entry every other engine implements, and this one did not.

    Without it `engines.analyze` raised AttributeError on every run, the error was recorded as a
    status nobody reads, and the engine was absent from `engines_observed` -- so its output never
    reached the fact set even when the binary was installed and indexing tens of thousands of
    edges. The edges and metrics are written beside the report here, because the fact layer reads
    a file rather than invoking the tools a second time: one pass over the files, not two.
    """
    found = version()
    if found is None:
        return Report(NAME, None, PINNED, UNAVAILABLE, reason=f'CodeGraph is not installed at {BINARY}')
    workdir = Path(workdir) / 'codegraph'
    workdir.mkdir(parents=True, exist_ok=True)
    produced = run(target, workdir, files=files_of_interest(workdir))
    (workdir / GRAPH_FACTS).write_text(
        json.dumps({'facts': produced['facts'], 'summary': produced['summary']},
                   ensure_ascii=False, sort_keys=True, indent=2), encoding='utf-8')
    summary = produced['summary']
    findings, unmapped = [], {}
    for fact in produced['facts']:
        value = fact['value']
        if fact['kind'] == 'symbol_metric_external':
            findings.append(finding(
                NAME, found, 'codegraph:analyze_complexity', 'complexity',
                subject('symbol', value.get('name') or fact['location']['path'],
                        fact['location']['path'], fact['location'].get('line')),
                f"{value.get('name', 'symbol')}: cyclomatic complexity {value.get('complexity')} "
                f"(grade {value.get('grade') or 'n/a'})",
                measurements=[measurement('complexity', value.get('complexity')),
                              measurement('lines_of_code', value.get('lines')),
                              measurement('branches', value.get('branches')),
                              measurement('loops', value.get('loops')),
                              measurement('nesting', value.get('nesting'))],
                method='measured', raw_ref=f'codegraph/{GRAPH_FACTS}'))
        elif fact['kind'] == 'hot_path_external':
            findings.append(finding(
                NAME, found, 'codegraph:find_hot_paths', 'coupling',
                subject('symbol', value.get('symbol') or fact['location']['path'],
                        value.get('path') or fact['location']['path'], None),
                f"{value.get('symbol', 'symbol')} is reached by {value.get('transitive_callers', 0)} "
                f"transitive caller(s)",
                measurements=[measurement('transitive_callers', value.get('transitive_callers')),
                              measurement('direct_callers', value.get('direct_callers'))],
                raw_ref=f'codegraph/{GRAPH_FACTS}'))
        elif fact['kind'] not in ('module_edge_external', 'call_edge_external'):
            unmapped[fact['kind']] = unmapped.get(fact['kind'], 0) + 1
    # An engine we asked nothing of has not observed anything. Saying otherwise would let an empty
    # answer read as a clean result.
    if not summary.get('files_asked'):
        return Report(NAME, found, PINNED, UNAVAILABLE,
                      reason='no file in this report was named for CodeGraph to answer about',
                      coverage={'status': 'unavailable'}, raw=str(workdir / GRAPH_FACTS))
    evaluated = {'complexity': {'status': 'observed', 'granularity': SYMBOL},
                 'coupling': {'status': 'observed', 'granularity': SYMBOL}}
    coverage = {'status': 'observed', 'scanned_files': summary.get('files_asked'),
                'tools': summary.get('tools', {}), 'partial': summary.get('partial', []),
                'file_budget': summary.get('file_budget'),
                'files_offered': summary.get('files_offered')}
    return Report(NAME, found, PINNED, OBSERVED, findings=findings, coverage=coverage,
                  raw=str(workdir / GRAPH_FACTS), unmapped=unmapped, evaluated=evaluated,
                  provenance={'binary': BINARY, 'pinned': PINNED})


def files_of_interest(workdir):
    """The files the report already speaks about, read from the fact sets written before this stage.

    `workdir` is `<report>/engines/codegraph`, so the fact sets sit two levels up. Reading them
    here keeps the adapter's contract signature intact while still letting it ask about the files
    that matter rather than about every file in the tree.
    """
    facts_dir = Path(workdir).parent.parent / 'facts'
    paths = []
    for name, kind in (('entrypoints', 'entry_point'), ('flows', 'flow')):
        source = facts_dir / f'{name}.json'
        if not source.is_file(): continue
        try: payload = json.loads(source.read_text(encoding='utf-8'))
        except (ValueError, OSError): continue
        for fact in payload.get('facts', []):
            if fact.get('kind') != kind: continue
            if kind == 'entry_point':
                if fact['value'].get('category') == 'test': continue
                paths.append(fact['location']['path'])
            else:
                paths.extend(fact['value'].get('files') or [])
    return list(dict.fromkeys(path for path in paths if path))


def read_graph_facts(workdir):
    """The edges and metrics this adapter already produced, so nothing runs the tools twice."""
    source = Path(workdir) / 'codegraph' / GRAPH_FACTS
    if not source.is_file(): return {'facts': [], 'summary': {}}
    try: return json.loads(source.read_text(encoding='utf-8'))
    except (ValueError, OSError): return {'facts': [], 'summary': {}}
