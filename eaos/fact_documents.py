"""The documents written straight from the fact sets and the dossier's provenance (eaos/dossier.py assembles them):
FLOWS.md, DOMAIN-AND-DATA.md, CONTRACTS.md, PROVENANCE.md, the sections of ONBOARDING.md, the dossier's one-line
description, and the index's trust grades and file inventory.
"""
from . import claims as ledger
from .compose import Document

INFORMATIVE_STEPS = {'local', 'imported'}
NODE_BUILTINS = {'fs', 'path', 'http', 'https', 'os', 'util', 'events', 'stream', 'crypto', 'url', 'zlib',
                 'child_process', 'net', 'buffer', 'assert', 'querystring', 'tty', 'readline', 'process'}


def semantic_claims(dossier):
    return sum(1 for claim in dossier['claims'] if 'model_inference' in claim.get('method', []))


def trust_grades(dossier, sets, verification):
    """How well each section is sourced, so a reader knows which parts to take at face value."""
    flows = sets.get('flows', {}).get('summary', {})
    history = sets.get('history', {})
    commits = (history.get('summary') or {}).get('commits_analysed', 0) if history.get('available') else 0
    return [
        {'section': 'SYSTEM-MAP.md', 'source': 'deterministic extractors', 'grade': '⬤',
         'note': 'reproducible byte for byte from the same snapshot'},
        {'section': 'CONTRACTS.md', 'source': 'resolved imports and entry points', 'grade': '⬤', 'note': ''},
        {'section': 'FLOWS.md', 'source': 'static trace', 'grade': '◐',
         'note': f"{flows.get('unresolved_steps', 0)} unresolved steps declared"},
        {'section': 'DOMAIN-AND-DATA.md', 'source': 'parsed definitions', 'grade': '⬤', 'note': ''},
        {'section': 'COUPLING-ATLAS.md', 'source': 'graph and metrics', 'grade': '⬤',
         'note': 'attention order is a declared convention, not a measured predictor'},
        {'section': 'EVOLUTION.md', 'source': 'git history', 'grade': '⬤' if commits >= 50 else '◐',
         'note': f'{commits} commits in scope'},
        {'section': 'responsibilities, boundaries, internal contracts',
         'source': 'model inference over facts' if semantic_claims(dossier) else '—',
         'grade': '○',
         'note': (f'{semantic_claims(dossier)} claims, none confirmed by inference alone'
                  if semantic_claims(dossier) else 'not assessed: needs the model path')},
    ]


def inventory_rows(language):
    """Every declared document in reading order, with the reason a reader would open it.

    Generated from the artifact contract, not written by hand, so a document that is added,
    renamed or dropped appears here instead of being discoverable only by listing the directory.
    Whether this particular run produced it is RUN.md's question, not this one's.
    """
    from .compose.artifacts import reading_order
    rows = []
    for position, artifact in enumerate(reading_order(), start=1):
        note = artifact.purpose
        if not artifact.required:
            note += (' — يغيب حين: ' if language == 'ar' else ' — absent when: ') + artifact.absent_when
        rows.append([str(position), f'[{artifact.name}]({artifact.name})', note])
    return rows


def provenance_document(target, dossier, language):
    document = Document(Document('', language).words['provenance'], language, budget_lines=80)
    provenance = dossier['provenance']
    document.table(['key', 'value'], [[key, str(value)] for key, value in sorted(provenance.items())])
    document.section('reproduce')
    document.bullets([f"eaos audit {target} --out <dir>",
                      'Deterministic fact sets are byte-identical for the same snapshot and extractor versions.',
                      'Model-derived claims are not deterministic and carry their provider configuration above.'])
    return document


def describe(sets, records):
    syntax = sets['syntax']['summary']
    entry = sets['entrypoints']['summary']
    languages = ', '.join(f'{name} ({count})' for name, count in sorted(syntax['by_language'].items(), key=lambda kv: -kv[1])[:4])
    surfaces = ', '.join(f'{name} ({count})' for name, count in sorted(entry['by_surface'].items()))
    line = (f"⬤ {syntax['source_files']} source files, {syntax['symbols']} symbols, languages: {languages}. "
            f"Invocation surfaces: {surfaces or 'none detected'}.")
    if not records['findings']:
        line += ' ○ Responsibilities and contracts are not assessed in a facts-only run.'
    return line


def flows_document(dossier, sets, language):
    words = Document('', language).words
    document = Document(words['flows'], language, budget_lines=300)
    document.header([words['flow_note']])
    rows = sorted((f['value'] for f in sets['flows']['facts']),
                  key=lambda flow: (-len({step['to_path'] for step in flow['steps']
                                          if step['resolution'] in INFORMATIVE_STEPS and step['to_path']}),
                                    flow['flow_id']))
    if not rows:
        document.text(words['no_rows'])
        return document
    summary = sets['flows']['summary']
    shallow = [flow for flow in rows if not flow['in_codebase_steps']]
    rows = [flow for flow in rows if flow['in_codebase_steps']]
    document.section(words['coverage'])
    document.table([words['flows'], 'steps', 'unresolved', 'stop at first boundary'],
                   [[len(rows), summary['total_steps'], summary['unresolved_steps'], len(shallow)]])
    if shallow: document.text(_shallow_note(shallow, language))
    for flow in rows[:12]: _flow_section(document, words, flow, language)
    return document


def _shallow_note(shallow, language):
    return (('هذه المداخل لم يصل تتبعها إلى كود آخر داخل المشروع (توزيع ديناميكي أو استدعاءات مكتبة فقط): '
             if language == 'ar' else
             'These entry points reach no further code in the project (dynamic dispatch or library calls only): ')
            + ', '.join(f"{flow['entry']['path']}:{flow['entry']['line']}" for flow in shallow[:8])
            + (' …' if len(shallow) > 8 else ''))


def _flow_section(document, words, flow, language):
    entry = flow['entry']
    document.section(f"{flow['flow_id']} — {entry['surface']} {entry['http_method'] or ''} {entry['route']}".strip(), level=2)
    document.bullets([f"{words['entry']}: {entry['path']}:{entry['line']} [{entry['framework']}]",
                      f"{words['handler']}: {entry['handler']}",
                      f"{words['touched']}: {', '.join(flow['touched_files'])}",
                      (f"{words['env']}: {', '.join(flow['environment_reads'])}" if flow['environment_reads'] else None)])
    # Calls into the codebase carry the behaviour; framework plumbing is counted, not listed.
    traced = [step for step in flow['steps'] if step['resolution'] in INFORMATIVE_STEPS]
    plumbing = len(flow['steps']) - len(traced)
    document.table([words['step'], words['call'], words['location'], words['resolution']],
                   [[step['from'], step['callee'],
                     f"{step['to_path'] or step['from_path']}:{step['line']}", step['resolution']]
                    for step in traced], limit=12)
    if plumbing:
        document.text(f"+{plumbing} library or method calls on this path (in the fact records)"
                      if language != 'ar' else
                      f"+{plumbing} استدعاء مكتبة أو دالة عضو على هذا المسار (في سجلات الحقائق)")


def domain_document(dossier, sets, language):
    words = Document('', language).words
    document = Document(words['domain_data'], language, budget_lines=240)
    domain, config = sets['domain'], sets['config']
    document.header([domain['summary']['interpretation']])
    document.section(words['duplicated_rule'])
    document.table([words['constant'], words['defined_in'], 'values'],
                   [[fact['value']['name'], ', '.join(f"{d['path']}:{d['line']}" for d in fact['value']['definitions']),
                     fact['value']['distinct_values']]
                    for fact in domain['facts'] if fact['kind'] == 'domain_constant' and fact['value']['duplicated']], limit=20)
    document.section(words['data_models'])
    document.table([words['name'], 'kind', words['location']],
                   [[fact['value']['name'], fact['value'].get('kind', 'table'), f"{fact['location']['path']}:{fact['location']['start_line']}"]
                    for fact in domain['facts'] if fact['kind'] in ledger.shown_kinds({'data_model', 'data_table'})], limit=25)
    document.section(words['config_contract'])
    reads = {}
    for fact in config['facts']:
        if fact['kind'] == 'env_read':
            reads.setdefault(fact['value']['name'], []).append(f"{fact['location']['path']}:{fact['location']['start_line']}")
    document.table([words['name'], words['read_in'], 'default'],
                   [[name, ', '.join(sorted(places)[:3]), 'yes' if any(
                       fact['value']['has_default'] for fact in config['facts']
                       if fact['kind'] == 'env_read' and fact['value']['name'] == name) else 'no']
                    for name, places in sorted(reads.items())], limit=25)
    unread = config['summary']['unread_sensitive_config_files']
    if unread: document.bullets([f"sensitive config listed but never read: {', '.join(unread)}"])
    return document


def dependency_kind(module, language):
    """A standard-library import is not a third-party dependency, and mixing them hides the real surface."""
    import sys
    root = module.split('.')[0].split('/')[0]
    if language == 'python': return 'standard library' if root in sys.stdlib_module_names else 'third party'
    if language in {'javascript', 'typescript', 'tsx'}:
        return 'standard library' if root in NODE_BUILTINS or module.startswith('node:') else 'third party'
    if language == 'go': return 'standard library' if '.' not in root else 'third party'
    return 'unknown'


def contracts_document(dossier, sets, language):
    words = Document('', language).words
    document = Document(words['contracts_doc'], language, budget_lines=200)
    document.header([words['signal_note']])
    external, languages = {}, {}
    for fact in sets['resolve']['facts']:
        if fact['resolution'] == 'EXTERNAL':
            external.setdefault(fact['value']['module'], set()).add(fact['location']['path'])
            languages[fact['value']['module']] = fact['value'].get('language')
    grouped = {}
    for module, paths in external.items():
        grouped.setdefault(dependency_kind(module, languages.get(module)), []).append((module, len(paths)))
    document.section(words['external_deps'])
    document.table([words['name'], words['language'], 'kind', 'used in'],
                   [[module, languages.get(module) or '', kind, count]
                    for kind in ['third party', 'unknown', 'standard library']
                    for module, count in sorted(grouped.get(kind, []), key=lambda row: (-row[1], row[0]))], limit=30)
    document.bullets([f"third party: {len(grouped.get('third party', []))} · "
                      f"standard library: {len(grouped.get('standard library', []))}"])
    document.section(words['entry_points'])
    document.table([words['surface'], words['method'], words['route'], words['location']],
                   [[f['value']['surface'], f['value']['http_method'] or '—', f['value']['route'] or '—', _at(f)]
                    for f in sets['entrypoints']['facts'] if f.get('kind') == 'entry_point'], limit=30)
    return document


def _at(fact):
    return f"{fact['location']['path']}:{fact['location'].get('start_line') or 1}"


def _onboarding_run(document, sets, verification, ar):
    commands = [fact for fact in sets.get('entrypoints', {}).get('facts', [])
                if fact.get('kind') in {'entry_point', 'tool_command'}
                and fact['value']['framework'] in {'npm_script', 'make', 'console_script', 'docker_cmd', 'docker_entrypoint'}]
    document.section('ابنِ وشغّل' if ar else 'Build and run')
    document.table(['الأمر' if ar else 'Command', 'المصدر' if ar else 'Declared in'],
                   [[fact['value']['route'], _at(fact)] for fact in commands], limit=15)
    document.section('اختبر' if ar else 'Test')
    if verification and verification.get('executed'):
        document.bullets([' '.join(verification['command']),
                          f"{verification.get('overall_percent')}% coverage over {len(verification.get('test_files', []))} test files"])
    else:
        document.bullets([f"{len((verification or {}).get('test_files', []))} test files found; "
                          f"no test command was run by this check"])


def _onboarding_entries(document, sets, verification, ar):
    words = document.words
    document.section('نقاط الدخول لتجربتها' if ar else 'Entry points to try')
    production = [fact for fact in sets.get('entrypoints', {}).get('facts', [])
                  if fact.get('kind') == 'entry_point'
                  and fact['value'].get('category') != 'test' and fact['value']['surface'] in {'http', 'page', 'cli', 'job'}
                  and fact['value']['route'] and fact['value']['handler']]
    document.table([words['surface'], words['route'], words['handler'], words['location']],
                   [[fact['value']['surface'], fact['value']['route'] or '—', fact['value']['handler'] or '—', _at(fact)]
                    for fact in production], limit=15)


def _onboarding_reading(document, sets, verification, ar):
    words = document.words
    document.section('أول عشرة ملفات تقرؤها' if ar else 'The first ten files to read')
    from .vocabulary import classify
    ordered = [row for row in sets['graph']['summary']['attention_order'] if classify(row['path']) == 'source'][:10]
    document.table([words['path'], words['score'], 'لماذا' if ar else 'Why'],
                   [[row['path'], row['score'],
                     'مركزية ' + str(row['factors']['centrality']) + ' · تغيّر ' + str(row['factors']['change'])
                     if ar else
                     f"centrality {row['factors']['centrality']} · change {row['factors']['change']}"]
                    for row in ordered], limit=10)


def _onboarding_vocabulary(document, sets, verification, ar):
    words = document.words
    document.section('مصطلحات المشروع' if ar else 'Project vocabulary')
    domain = [fact for fact in sets.get('domain', {}).get('facts', [])
              if fact['kind'] in {'domain_constant'} | ledger.shown_kinds({'data_model', 'data_table'})]
    document.table([words['name'], 'النوع' if ar else 'Kind', words['location']],
                   [[fact['value'].get('name'), fact['kind'], _at(fact)] for fact in domain], limit=20)


def _onboarding_traps(document, sets, verification, ar):
    dynamic = sum(1 for fact in sets['entrypoints']['facts'] if fact.get('kind') == 'entry_point' and fact.get('resolution') == 'UNRESOLVED')
    document.section('مصائد معروفة' if ar else 'Known traps')
    document.bullets([
        f"{dynamic} نقطة دخول تُسجَّل ديناميكيًا ولا يمكن تتبعها ساكنًا" if ar else
        f"{dynamic} entry points are registered dynamically and cannot be traced statically",
        f"{len(sets['config']['summary']['unread_sensitive_config_files'])} sensitive config files are listed but never read",
        f"{sets['flows']['summary'].get('unresolved_steps', 0)} steps in the traced flows stop at calls the resolver cannot follow",
    ])


# The sections of ONBOARDING.md, in reading order; each is called (document, sets, verification, ar).
ONBOARDING_SECTIONS = (_onboarding_run, _onboarding_entries, _onboarding_reading, _onboarding_vocabulary, _onboarding_traps)
