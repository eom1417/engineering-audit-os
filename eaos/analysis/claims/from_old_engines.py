"""The claims old engines earn (M13.4), made beside the runtime claims (eaos/analysis/understanding/dossier.py) because
they read what ran (eaos/analysis/assessments/never_run.py) as well as the code (eaos/analysis/assessments/old_engines.py).

Each card says what replaced the old engine and the proof nothing runs it:
- a switched-off branch: the switch, its fixed value, the functions only that branch calls, what runs in its place,
  and whether any run of the tests, the server or the pages ran them; LIKELY (CONFIRMED when the runs measured their
  file and ran none of them), medium;
- two engines doing one job: the old one still called beside the new, their history when the repository has one;
  a HYPOTHESIS the card triage (the judge) reads, medium;
- modules an entry point reaches that no run read, and functions of files that ran that never ran: one card each for
  the whole project, a HYPOTHESIS, low: suspects with what ran around them, never a verdict.
The first two have a probe that reads the code again (ast-grep and the call graph); the suspects only a new run can
close, so they stay an investigation.
"""
from . import ledger
from ..assessments import never_run, old_engines

SUSPECTS = 8


def _ran_none(names, path, found):
    """'none ran' when the runs measured the file and ran none of the names, 'not measured' when no run read the
    file, else the names that ran."""
    files = never_run.ran_files(found)
    if path not in files: return 'not measured'
    ran = sorted(n for n in names if n in files[path]['ran'])
    return 'none ran' if not ran else ran


def _proof(state):
    if state == 'none ran': return ('and no run of the tests, the server or the pages ran it', 'وما شغّله أي تشغيل للاختبارات ولا الخادم ولا الصفحات')
    if state == 'not measured': return ('its file was not measured while the program ran', 'وملفه ما انقاس وقت تشغيل البرنامج')
    return (f"yet a run ran {', '.join(state)}: read it before removing", f"لكن تشغيلًا شغّل {', '.join(state)}: راجعه قبل الحذف")


def _switched(row, found):
    """(statement, render params, confidence) of a switched-off branch."""
    names = [e['name'] for e in row['engines']]
    state = _ran_none(names, row['engines'][0]['path'], found)
    proof, place = _proof(state), f"{row['switch_path']}:{row['switch_line']}"
    value = 'true' if row['value'] else 'false'
    instead = ', '.join(row['replaced_by']) or 'the code after it'
    en = (f"An old engine still wired in: {row['switch']} is fixed to {value} ({place}), so the branch at {row['path']}:"
          f"{row['dead'][0]} never runs; it alone calls {', '.join(names)}, replaced by {instead}; {proof[0]}")
    ar = (f"محرك قديم ما زال موصولًا: {row['switch']} ثابت على {value} ({place})، فالفرع في {row['path']}:{row['dead'][0]} "
          f"ما يشتغل أبدًا؛ وهو وحده يستدعي {'، '.join(names)}، وحلّ محله {instead}؛ {proof[1]}")
    fix_en = (f"Delete {', '.join(names)}, the branch at {row['path']}:{row['dead'][0]} and the switch {row['switch']}; "
              f"keep {instead}. Run the tests and the pages again: nothing changes, since nothing ran them.")
    fix_ar = (f"احذف {'، '.join(names)} والفرع في {row['path']}:{row['dead'][0]} والمفتاح {row['switch']}، وخلّ {instead}. "
              'أعد تشغيل الاختبارات والصفحات: ما يتغير شي، لأن ما أحد كان يشغّلها.')
    confidence = 'CONFIRMED' if state == 'none ran' else 'LIKELY'
    return en, {'kind': 'switched_off', 'en': en, 'ar': ar, 'fix_en': fix_en, 'fix_ar': fix_ar, 'severity': 'medium',
                'place': row['path'], 'line': row['dead'][0], 'switch': row['switch'], 'engines': names,
                'replaced_by': row['replaced_by']}, confidence


def _pair(row, found):
    """(statement, render params, confidence) of two engines doing one job."""
    state = _ran_none([row['old']], row['path_old'], found) if row['kind'] == 'function' else 'not measured'
    when_en = f"; it stopped changing on {row['stopped'][:10]}, {row['new']} began on {row['began'][:10]}" if row['stopped'] and row['began'] and row['stopped'] < row['began'] else ''
    when_ar = f"؛ آخر تغيير له {row['stopped'][:10]} وبدأ {row['new']} في {row['began'][:10]}" if when_en else ''
    en = (f"Two engines doing one job: {row['old']} ({row['path_old']}) and {row['new']} ({row['path_new']}) are one name a "
          f"marker apart and take the same input; {row['old']} is still {'called' if row['kind'] == 'function' else 'imported'}{when_en}")
    ar = (f"محركان لشغلة وحدة: {row['old']} ({row['path_old']}) و{row['new']} ({row['path_new']}) اسم واحد يفرقهما وصف "
          f"(قديم، جديد، نسخة) ويأخذان نفس المدخل؛ و{row['old']} ما زال {'يُستدعى' if row['kind'] == 'function' else 'يُستورد'}{when_ar}")
    fix_en = (f"Move what still calls {row['old']} to {row['new']}, prove it with the tests and the pages, then delete {row['old']}; "
              f"if both are meant, give them names that say how they differ.")
    fix_ar = (f"انقل كل اللي يستدعي {row['old']} إلى {row['new']}، وأثبت ذلك بالاختبارات والصفحات، ثم احذف {row['old']}؛ "
              'وإذا الاثنين مقصودين، سمّهم أسماء تقول وش الفرق بينهم.')
    return en, {'kind': 'two_engines', 'en': en, 'ar': ar, 'fix_en': fix_en, 'fix_ar': fix_ar, 'severity': 'medium',
                'place': row['path_old'], 'line': row['line'], 'old': row['old'], 'new': row['new'], 'ran': state}, 'HYPOTHESIS'


def _modules_card(modules, nodes):
    """(statement, params, fact ids) of the modules no run read."""
    listed = '; '.join(m['path'] + (f" (around it ran {', '.join(m['around'])})" if m['around'] else '') for m in modules[:SUSPECTS])
    en = f"{len(modules)} modules an entry point reaches never ran while EAOS ran the tests, the server and the pages: {listed}"
    ar = f"{len(modules)} وحدة يوصل لها مسار من نقطة دخول وما اشتغلت أبدًا وقت ما شغّل EAOS الاختبارات والخادم والصفحات: {listed}"
    return en, {'kind': 'never_run_modules', 'en': en, 'ar': ar, 'place': modules[0]['path'], 'count': len(modules)}, \
        [nodes[m['path']] for m in modules if m['path'] in nodes]


def _functions_card(functions, symbols):
    """(statement, params, fact ids) of the functions that never ran in files that ran."""
    count = sum(len(row['never']) for row in functions.values())
    listed = '; '.join(f"{path}: {', '.join(row['never'][:4])}" + (f" (beside {', '.join(row['around'])}, which ran)" if row['around'] else '')
                       for path, row in list(functions.items())[:SUSPECTS])
    en = f"{count} functions in files that ran never ran themselves while EAOS ran the tests, the server and the pages: {listed}"
    ar = f"{count} دالة في ملفات اشتغلت ما اشتغلت هي نفسها وقت ما شغّل EAOS الاختبارات والخادم والصفحات: {listed}"
    return en, {'kind': 'never_run_functions', 'en': en, 'ar': ar, 'place': next(iter(functions)), 'count': count}, \
        [symbols[(p, n)] for p, row in functions.items() for n in row['never'] if (p, n) in symbols][:50]


def _suspects(found, sets):
    """[(statement, params, fact ids)] of the never-run modules and functions, one card each kind."""
    modules, functions = never_run.never_run_modules(sets, found), never_run.never_run_functions(sets, found)
    nodes = {f['location']['path']: f['id'] for f in (sets.get('graph') or {}).get('facts', []) if f['kind'] == 'graph_node'}
    symbols = {(f['location']['path'], f['value'].get('name')): f['id'] for f in (sets.get('syntax') or {}).get('facts', []) if f['kind'] == 'symbol'}
    return ([_modules_card(modules, nodes)] if modules else []) + ([_functions_card(functions, symbols)] if functions else [])


FIX_SUSPECT = ('Open each one: a screen no page reached, an error no test raised, or code nothing needs any more. Remove what '
               'nothing needs; for the rest, a test or a page that runs it.',
               'افتح كل واحد: شاشة ما وصلت لها صفحة، أو خطأ ما رفعه اختبار، أو كود ما عاد أحد يحتاجه. احذف اللي ما أحد يحتاجه، والباقي '
               'اكتب له اختبار أو صفحة تشغّله.')


def _cards(sets, target, found):
    """[(statement, confidence, params, fact ids, probe or None)] of every old engine and suspect."""
    switched = [row for row in old_engines.switched_off(sets, target) if row['engines']]
    behind = {engine['name'] for row in switched for engine in row['engines']}
    cards = [(*_switched(row, found), row['fact_ids'],
              {'query': 'old_engine_present', 'kind': 'switched_off', 'path': row['path'], 'switch': row['switch'],
               'engines': ['ast-grep'], 'expected': 'The switch still closes the branch that alone calls the old engine.'})
             for row in switched]
    cards += [(*_pair(row, found), row['fact_ids'],
               {'query': 'old_engine_present', 'kind': 'two_engines', 'old': row['old'], 'new': row['new'],
                'expected': 'Both are still there and the old one still used.'})
              for row in old_engines.two_engines(sets) if row['old'] not in behind]     # a switch closing it: one card
    for statement, params, fact_ids in _suspects(found, sets):
        params.update(fix_en=FIX_SUSPECT[0], fix_ar=FIX_SUSPECT[1], severity='low')
        cards.append((statement, params, 'HYPOTHESIS', fact_ids, None))
    return cards


def old_engine_claims(out, sets, target, offset):
    """Every claim of old engines and code never run, numbered after `offset`."""
    rows = []
    for statement, params, confidence, fact_ids, probe in _cards(sets, target, never_run.records(out)):
        if not fact_ids: continue
        rows.append(ledger.make(offset + len(rows) + 1, statement, 'risk', confidence,
                                ['runtime_probe' if confidence == 'CONFIRMED' else 'static_fact'], [],
                                'Nothing calls or names the old code any more, or a run shows it running.',
                                fact_ids=fact_ids, confidence_ceiling=confidence, render={'key': 'old_engine', 'params': params},
                                probe_spec={'probe_type': 'graph_query', 'specification': probe} if probe else None,
                                impact={'scenario': params['fix_en']}))
    return rows


def present(specification, sets):
    """The probe of an old-engine card, over the code read again: CONFIRMED while it still shows the old engine."""
    if specification['kind'] == 'switched_off':
        still = any(r['path'] == specification['path'] and r['switch'] == specification['switch'] and r['engines']
                    for r in old_engines.switched_off(sets))
    else: still = any(r['old'] == specification['old'] and r['new'] == specification['new'] for r in old_engines.two_engines(sets))
    if still: return 'CONFIRMED', 'the old engine is still wired in'
    return 'REFUTED', 'the old engine is no longer wired in'
