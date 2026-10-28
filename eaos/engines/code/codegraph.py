"""CodeGraph engine: imports, calls, complexity, hot paths across every language the engine parses.

Four tools, all run as one-shot invocations against the pinned CodeGraph binary:

  codegraph_get_dependency_graph  module and file dependency graph
  codegraph_get_call_graph        callers/callees of a symbol
  codegraph_analyze_complexity    per-symbol complexity (lines, branches, etc.)
  codegraph_find_hot_paths        ranked call-paths through the codebase

Each tool returns a JSON payload. codegraph_payloads.py flattens the payload into the engine's
fact shape and emits a `module_edge_external` / `call_edge_external` fact for each
call or import. Tools that return a warning ("unknown tool", "invalid URI", "missing
parameter") are downgraded to `partial` and the reason recorded in the summary.

The wrapper never guesses what the tool would have returned; if the payload is empty
or it failed, the tool is recorded as DECLINED with a measured reason.
"""
import json
import subprocess
from pathlib import Path

from ...core import toolchain
from .codegraph_payloads import CONVERTERS, _complexity_facts, _parse_payload
from ..contract import OBSERVED, Report, SYMBOL, UNAVAILABLE, finding, measurement, subject
from ...core.system.files import read_json

NAME, VERSION, PINNED = 'codegraph', '1', 'v0.20.1'

TOOLS = {
    'codegraph_get_dependency_graph': 'module_edge_external',
    'codegraph_get_call_graph': 'call_edge_external',
    'codegraph_analyze_complexity': 'symbol_metric_external',
    'codegraph_find_hot_paths': 'hot_path_external',
}

BINARY = str(toolchain.home() / 'bin' / 'codegraph-server')


def _run(tool, args, workspace, timeout=600, index_home=None):
    """One tool, one payload. Never raise: return (payload_str_or_None, error_str_or_None).

    `index_home` becomes the process HOME, and the engine keeps its index under it. Left to its
    own default the engine shares one index across every run on the machine, and a single bad
    build poisons it: it persisted zero nodes for this repository, then declined to rebuild
    ("No files changed and no persisted data"), so every tool answered with an empty payload and
    the run recorded an engine that had seen nothing. A per-run home costs one cold index and
    makes the answer depend on the tree instead of on what some earlier run left behind.
    """
    cmd = [BINARY, '--graph-only', '-w', str(workspace),
           '--run-tool', tool, '--tool-args', json.dumps(args or {})]
    environment = None
    if index_home is not None:
        import os
        environment = dict(os.environ, HOME=str(index_home))
    try:
        from ...core.system.process import run_command
        return _outcome(run_command(cmd, timeout=timeout, env=environment))
    except subprocess.TimeoutExpired:
        return None, f'timeout after {timeout}s'
    except FileNotFoundError:
        return None, f'binary missing at {BINARY}'


def _outcome(result):
    """(payload, None), or (what came out, why the tool failed)."""
    out, err = result.stdout.strip(), result.stderr.strip()
    if 'Tool ' in err and ' failed: ' in err:
        return out or None, err.split('Tool ', 1)[-1].split(' failed: ', 1)[-1].strip()
    if result.returncode != 0 and not out:
        return None, err or f'exit {result.returncode}'
    return (out, None) if out else (None, 'empty payload')


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
    index_home = Path(out) / 'index-home'
    index_home.mkdir(parents=True, exist_ok=True)
    summary['index_home'] = str(index_home)

    asked = _asked(target, files, summary)
    if not asked: _nothing_asked(summary, tool_selection)
    context = (target, index_home)
    if asked: facts += _file_facts(summary, asked, context, tool_selection)
    if tool_selection.get('find_hot_paths', True): facts += _hot_path_facts(summary, context)
    if asked and tool_selection.get('get_call_graph', True): facts += _call_graph_facts(summary, asked, context)
    return {'facts': facts, 'summary': summary,
            'available': True, 'input_sha': '', 'reason': None}


def _asked(target, files, summary):
    """The files to ask about: the reader's own that exist, each once, at most FILE_BUDGET; both counts in `summary`."""
    asked = [path for path in (files or []) if (target / path).is_file() and _is_the_reader_s_code(path)]
    summary['files_offered'] = len(files or [])
    asked = sorted(dict.fromkeys(asked))[:FILE_BUDGET]
    summary['files_asked'] = len(asked)
    return asked


def _file_facts(summary, asked, context, tool_selection):
    """What the tools asked file by file say, as selected: each file's dependencies, then its symbols' complexity."""
    target, facts = context[0], []
    if tool_selection.get('get_dependency_graph', True):
        facts += _per_file(summary, 'codegraph_get_dependency_graph', asked, context,
                           ({'direction': 'both', 'depth': 1}, lambda payload, path: CONVERTERS['codegraph_get_dependency_graph'](payload, target)))
    if tool_selection.get('analyze_complexity', True):
        facts += _per_file(summary, 'codegraph_analyze_complexity', asked, context,
                           ({}, lambda payload, path: _complexity_facts(payload, target, path=path)))
    return facts


def _nothing_asked(summary, tool_selection):
    # A tool we chose not to run is absent from the record; a tool we wanted to run and could
    # not ask is present and says why. Conflating the two would hide a silent skip.
    for tool, selector in (('codegraph_get_dependency_graph', 'get_dependency_graph'),
                           ('codegraph_analyze_complexity', 'analyze_complexity'),
                           ('codegraph_get_call_graph', 'get_call_graph')):
        if not tool_selection.get(selector, True): continue
        summary['tools'][tool] = 'partial'
        summary['partial'].append({'tool': tool, 'reason': 'no file was named for this run'})


def _per_file(summary, tool, asked, context, how):
    """One tool asked about each file, recorded once. `how`: (its arguments besides the file, payload -> facts)."""
    (target, index_home), (arguments, convert) = context, how
    facts, errors = [], []
    for path in asked:
        text, err = _run(tool, {'uri': f'file://{target / path}', **arguments}, target, index_home=index_home)
        if err: errors.append(err); continue
        payload = _parse_payload(text)
        if payload: facts.extend(convert(payload, path))
    _record_many(summary, tool, len(facts), errors, len(asked))
    return facts


def _hot_path_facts(summary, context):
    """The hot paths through the reader's own code; those through somebody else's are only counted."""
    target, index_home = context
    text, err = _run('codegraph_find_hot_paths', {'limit': 20, 'depth': 3}, target, index_home=index_home)
    _record(summary, 'codegraph_find_hot_paths', text, err)
    payload = _parse_payload(text)
    if not payload: return []
    hot = CONVERTERS['codegraph_find_hot_paths'](payload, str(target))
    kept = [fact for fact in hot if _is_the_reader_s_code(fact['value'].get('path') or fact['location']['path'])]
    if len(kept) < len(hot):
        summary['hot_paths_in_somebody_elses_code'] = len(hot) - len(kept)
    return kept


def _call_graph_facts(summary, asked, context):
    # Ask about the symbols the report already names. On Go the engine answers with an empty
    # edge list and a diagnostic saying its parser extracts no call edges; that is a measured
    # limit of the engine, and it is recorded as one rather than retried against more files.
    target, index_home = context
    facts, landed, diagnostics = [], 0, []
    for path in asked[:10]:
        text, err = _run('codegraph_get_call_graph',
                         {'uri': f'file://{target / path}', 'name': Path(path).stem, 'depth': 2}, target,
                         index_home=index_home)
        if err: diagnostics.append(err); continue
        payload = _parse_payload(text)
        if not payload: continue
        produced = CONVERTERS['codegraph_get_call_graph'](payload, path)
        if produced:
            facts.extend(produced); landed += 1
        else: _note_diagnostic(payload, diagnostics)
    _record_calls(summary, landed, diagnostics)
    return facts


def _note_diagnostic(payload, diagnostics):
    note = payload['diagnostic'].get('note') if isinstance(payload.get('diagnostic'), dict) else None
    if note and note not in diagnostics: diagnostics.append(note)


def _record_calls(summary, landed, diagnostics):
    if landed:
        summary['tools']['codegraph_get_call_graph'] = 'ok'
        return
    summary['tools']['codegraph_get_call_graph'] = 'partial'
    summary['partial'].append({'tool': 'codegraph_get_call_graph',
                                'reason': diagnostics[0] if diagnostics
                                          else 'the engine returned no call edge for any file asked'})


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
        result = subprocess.run([BINARY, '--version'], capture_output=True, text=True, timeout=30)  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit -- the pinned binary asked its version, fixed arguments, no shell
        return (result.stdout + result.stderr).strip().splitlines()[-1].strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None

def capabilities():
    """One Capability per tool the wrapper exposes. The kind is the fact vocabulary each produces."""
    from ..contract import Capability
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
    findings, unmapped = _findings(produced['facts'], found)
    # An engine we asked nothing of has not observed anything. Saying otherwise would let an empty
    # answer read as a clean result.
    if not summary.get('files_asked'):
        return Report(NAME, found, PINNED, UNAVAILABLE,
                      reason='no file in this report was named for CodeGraph to answer about',
                      coverage={'status': 'unavailable'}, raw=str(workdir / GRAPH_FACTS))
    evaluated = {'coupling': {'status': 'observed', 'granularity': SYMBOL}}
    coverage = {'status': 'observed', 'scanned_files': summary.get('files_asked'),
                'tools': summary.get('tools', {}), 'partial': summary.get('partial', []),
                'file_budget': summary.get('file_budget'),
                'files_offered': summary.get('files_offered')}
    return Report(NAME, found, PINNED, OBSERVED, findings=findings, coverage=coverage,
                  raw=str(workdir / GRAPH_FACTS), unmapped=unmapped, evaluated=evaluated,
                  provenance={'binary': BINARY, 'pinned': PINNED})


def _findings(facts, found):
    """(the hot paths as coupling findings, {kind: count} of the facts of a kind no finding or fact set reads)."""
    findings, unmapped = [], {}
    for fact in facts:
        value = fact['value']
        # A per-symbol metric carries no threshold: it stays a symbol metric (facts/engine_findings.py), never a finding.
        if fact['kind'] == 'symbol_metric_external':
            continue
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
    return findings, unmapped


def files_of_interest(workdir):
    """The files the report already speaks about, read from the fact sets written before this stage.

    `workdir` is `<report>/engines/codegraph`, so the fact sets sit two levels up. Reading them
    here keeps the adapter's contract signature intact while still letting it ask about the files
    that matter rather than about every file in the tree.
    """
    facts_dir = Path(workdir).parent.parent / 'facts'
    paths = []
    for name, kind in (('entrypoints', 'entry_point'), ('flows', 'flow')):
        for fact in _facts_in(facts_dir / f'{name}.json'):
            if fact.get('kind') == kind: paths += _paths_of(fact, kind)
    return list(dict.fromkeys(path for path in paths if path))


def _facts_in(source):
    if not source.is_file(): return []
    try: payload = json.loads(source.read_text(encoding='utf-8'))
    except (ValueError, OSError): return []
    return payload.get('facts', [])


def _paths_of(fact, kind):
    """An entry point's file (none for one in the tests), or the files a flow touches and its entry's."""
    if kind == 'entry_point':
        return [] if fact['value'].get('category') == 'test' else [fact['location']['path']]
    # The flow fact names its path set `touched_files`. Reading `files` here returned
    # an empty list on every project, so the engine was only ever asked about entry
    # points -- the same producer/reader name mismatch this module was fixed for.
    return list(fact['value'].get('touched_files') or []) + [((fact['value'].get('entry') or {}).get('path')) or '']


def read_graph_facts(workdir):
    """The edges and metrics this adapter already produced, so nothing runs the tools twice."""
    source = Path(workdir) / 'codegraph' / GRAPH_FACTS
    if not source.is_file(): return {'facts': [], 'summary': {}}
    return read_json(source, {'facts': [], 'summary': {}})
