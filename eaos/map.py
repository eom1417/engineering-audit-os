"""`eaos map`: a full structural picture of an unknown codebase without a single model call."""
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from .compose import Document, safe
from .facts.run import collect
from .facts.store import read_set

ARTIFACTS = ['SYSTEM-MAP.md', 'COUPLING-ATLAS.md', 'EVOLUTION.md']


def by_kind(facts, kind): return [f for f in facts if f['kind'] == kind]


def provenance(target, sets, language):
    stamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    available = ', '.join(sorted(name for name, data in sets.items() if data['available']))
    return [f'{target}  ·  {stamp}', f'facts: {available}']


def coverage_rows(sets, words):
    syntax, resolve, entry = sets['syntax']['summary'], sets['resolve']['summary'], sets['entrypoints']['summary']
    rows = [f"{words['coverage']}: {syntax['files_parsed']}/{syntax['source_files']} "
            f"({round(syntax['parse_coverage'] * 100)}%) · imports resolved {resolve['by_resolution']['RESOLVED']}"
            f"/{sum(resolve['by_resolution'].values())} · entry points {entry['entry_points']}"]
    if not sets['history']['available']: rows.append('history: unavailable (' + (sets['history'].get('reason') or '') + ')')
    return rows


def _totals(facts, group_of):
    """[name, files, lines] per group of source files, the most lines first."""
    groups = defaultdict(lambda: [0, 0])
    for fact in by_kind(facts, 'source_file'):
        row = groups[group_of(fact)]
        row[0] += 1
        row[1] += fact['value']['lines']
    return groups, sorted(([name, count, lines] for name, (count, lines) in groups.items()), key=lambda r: -r[2])


def _languages(document, words, syntax):
    document.section(words['languages'])
    _, rows = _totals(syntax['facts'], lambda fact: fact['value']['language'] or 'other')
    document.table([words['language'], words['files'], words['lines']], rows, limit=12)


def _entry_points(document, words, entry, language):
    document.section(words['entry_points'])
    production = [fact for fact in by_kind(entry['facts'], 'entry_point') if fact['value'].get('category') != 'test']
    in_tests = len(by_kind(entry['facts'], 'entry_point')) - len(production)
    rows = [[fact['value']['surface'], fact['value']['http_method'] or '—', fact['value']['route'] or '—',
             fact['value']['handler'] or '—', f"{fact['location']['path']}:{fact['location'].get('start_line') or 1}",
             fact['value']['framework']] for fact in production]
    document.table([words['surface'], words['method'], words['route'], words['handler'], words['location'], words['framework']], rows, limit=40)
    if in_tests:
        document.text(f'+{in_tests} entry points declared inside test code, listed in the fact records only.'
                      if language != 'ar' else
                      f'+{in_tests} نقطة دخول معرّفة داخل كود الاختبارات، مذكورة في سجلات الحقائق فقط.')


def _group_edges(graph):
    """{(from top folder, to top folder): imports} across top folders."""
    edges = defaultdict(int)
    for fact in by_kind(graph['facts'], 'graph_node'):
        source_group = PurePosixPath(fact['location']['path']).parts[0]
        for target_group in (PurePosixPath(other).parts[0] for other in fact['value']['depends_on']):
            if source_group != target_group: edges[(source_group, target_group)] += 1
    return edges


def _components(document, words, syntax, graph):
    document.section(words['components'])
    top = lambda fact: PurePosixPath(fact['location']['path']).parts[0] if '/' in fact['location']['path'] else '.'
    groups, rows = _totals(syntax['facts'], top)
    document.table([words['directory'], words['files'], words['lines']], rows, limit=20)
    edges = _group_edges(graph)
    if not edges: return
    identifiers = {name: 'g%d' % index for index, name in enumerate(sorted(groups))}
    lines = ['flowchart LR'] + [f'  {identifiers[name]}["{safe(name)}"]' for name in sorted(groups) if name in identifiers]
    lines += [f'  {identifiers[a]} -->|{count}| {identifiers[b]}' for (a, b), count in sorted(edges.items()) if a in identifiers and b in identifiers]
    document.mermaid(lines)


def _most_depended(document, words, graph):
    document.section(words['most_depended'])
    nodes = {fact['location']['path']: fact['value'] for fact in by_kind(graph['facts'], 'graph_node')}
    document.table([words['path'], words['fan_in'], words['fan_out']],
                   [[path, value['fan_in'], value['fan_out']] for path, value in
                    sorted(nodes.items(), key=lambda kv: (-kv[1]['fan_in'], kv[0]))[:15] if value['fan_in']], limit=15)


def system_map(target, sets, language):
    words = Document('', language).words
    syntax, graph, entry = sets['syntax'], sets['graph'], sets['entrypoints']
    document = Document(words['system_map'], language, budget_lines=260)
    document.header(provenance(target, sets, language) + coverage_rows(sets, words) + [words['generated']])
    _languages(document, words, syntax)
    _entry_points(document, words, entry, language)
    _components(document, words, syntax, graph)
    _most_depended(document, words, graph)
    _not_examined(document, words, sets)
    return document


def _not_examined(document, words, sets):
    syntax, graph, entry = sets['syntax'], sets['graph'], sets['entrypoints']
    document.section(words['not_examined'])
    unparsed = [f['location']['path'] for f in by_kind(syntax['facts'], 'source_file') if f['value']['parse_status'] not in {'OBSERVED', 'NOT_SOURCE'}]
    unresolved = [f"{f['location']['path']} → {f['value']['module']}" for f in by_kind(sets['resolve']['facts'], 'module_edge')
                  if f['resolution'] in {'UNRESOLVED', 'AMBIGUOUS'}]
    document.bullets(
        [f"unparsed files: {len(unparsed)} ({', '.join(unparsed[:5])})" if unparsed else None,
         f"unresolved or ambiguous imports: {len(unresolved)}" if unresolved else None,
         f"dynamic or undetected invocation surfaces: {sum(1 for f in by_kind(entry['facts'], 'entry_point') if f['resolution'] == 'UNRESOLVED')}",
         f"sensitive config files listed but never read: {len(sets['config']['summary']['unread_sensitive_config_files'])}",
         f"{words['unreachable']}: {graph['summary']['unreachable_from_entry']}",
         (f"excluded by request: {', '.join(sets['syntax'].get('exclude_patterns', []))}" if sets['syntax'].get('exclude_patterns') else None)])


def coupling_atlas(target, sets, language):
    words = Document('', language).words
    graph, metrics = sets['graph'], sets['metrics']
    document = Document(words['coupling_atlas'], language, budget_lines=220)
    document.header(provenance(target, sets, language) + [words['signal_note']])
    document.section(words['attention'])
    document.text(words['attention_note'] + ' ' + str(graph['summary']['weights']))
    document.table([words['path'], words['score'], words['factors']],
                   [[row['path'], row['score'], ', '.join(f'{k}={v}' for k, v in row['factors'].items())]
                    for row in graph['summary']['attention_order']], limit=20)
    document.section(words['cycles'])
    document.table([words['members']], [[' → '.join(f['value']['members'])] for f in by_kind(graph['facts'], 'graph_cycle')], limit=15)
    document.section(words['clones'])
    document.table([words['occurrences']],
                   [[' | '.join(f"{o['path']}:{o['start_line']}-{o['end_line']}" for o in f['value']['occurrences'][:4])]
                    for f in by_kind(metrics['facts'], 'clone_cluster')], limit=15)
    document.section(words['most_depended'])
    document.table([words['path'], words['fan_in']], [[row['path'], row['fan_in']] for row in graph['summary']['most_depended_on']], limit=15)
    return document


def evolution(target, sets, language):
    words = Document('', language).words
    history, graph = sets['history'], sets['graph']
    document = Document(words['evolution'], language, budget_lines=220)
    document.header(provenance(target, sets, language) + [words['signal_note']])
    if not history['available']:
        document.text(history.get('reason') or 'History is unavailable for this snapshot.')
        return document
    summary = history['summary']
    document.section(words['hotspots'])
    document.table([words['path'], words['commits'], words['fixes'], words['lines'], words['authors']],
                   [[row['path'], row['commits'], row['fix_commits'], row['lines_changed'], row['authors']] for row in summary['hotspots']], limit=20)
    document.section(words['cochange'])
    rows = _cochange_rows(history, graph)
    document.table([words['path'], words['path'], words['support'], words['confidence'], words['hidden_coupling']], rows, limit=20)
    document.section(words['ownership'])
    owners = [[f['location']['path'], f['value']['top_author'], f['value']['top_author_share'], f['value']['authors']]
              for f in by_kind(history['facts'], 'history_ownership') if f['value']['single_author'] and f['value']['commits'] > 1]
    document.table([words['path'], words['top_author'], words['share'], words['authors']], sorted(owners), limit=20)
    document.section(words['stale'])
    stale = [[f['location']['path'], f['value']['days_since_last_change'], f['value']['commits']]
             for f in by_kind(history['facts'], 'history_churn') if (f['value']['days_since_last_change'] or 0) > 0]
    document.table([words['path'], words['days'], words['commits']], sorted(stale, key=lambda row: -row[1]), limit=15)
    return document


def _cochange_rows(history, graph):
    """Files that change together, the ones with no import between them (hidden coupling) first."""
    dependencies = {fact['location']['path']: set(fact['value']['depends_on']) for fact in by_kind(graph['facts'], 'graph_node')}
    rows = []
    for fact in by_kind(history['facts'], 'history_cochange'):
        left, right = fact['location']['path'], fact['location']['paired_path']
        linked = right in dependencies.get(left, set()) or left in dependencies.get(right, set())
        rows.append([left, right, fact['value']['support'], fact['value']['confidence'], '—' if linked else '⚠'])
    rows.sort(key=lambda row: (row[4] != '⚠', -row[2], row[0]))
    return rows


def generate(target, out, language='ar', **options):
    """Collect facts, render the structural artifacts, and hand the fact sets back to the caller. `options`, by name:
    max_files, max_bytes, exclude, engines, and collected (the facts a pipeline already collected)."""
    target, out = Path(target).resolve(), Path(out).resolve()
    # A pipeline that already collected the facts must not pay for them twice.
    result = options.get('collected') or collect(target, out, None, max_files=options.get('max_files', 100000),
                                                 max_bytes=options.get('max_bytes', 2_000_000),
                                                 exclude=options.get('exclude', ()), engines=options.get('engines'))
    sets = {entry['set']: read_set(out, entry['set']) for entry in result['sets']}
    written = []
    for name, builder in zip(ARTIFACTS, [system_map, coupling_atlas, evolution]):
        (out / name).write_text(builder(str(target), sets, language).render(), encoding='utf-8')
        written.append(str(out / name))
    result['effective_exclude'] = result.get('exclude_patterns', [])
    return {'target': str(target), 'out': str(out), 'artifacts': written, 'facts': result['facts'],
            'exclude_patterns': result.get('exclude_patterns', []),
            'sets': result['sets'], 'model_calls': 0,
            'limits': 'Deterministic structural map only. No responsibility, contract or defect is asserted; those require the audit path.'}, sets


def build(target, out, language='ar', **options):
    """generate's result alone; `options` as generate's."""
    return generate(target, out, language, **options)[0]
