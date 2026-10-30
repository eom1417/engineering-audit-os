"""Every aspect of the program, with its evidence and a verdict: keep it as it is, or improve it.

The check's stages each carry information about one side of the project: its structure, its health indicators, its
repeated definitions, its tests, its journeys, its speed under load, its resilience, security and observability, its
screens and its problems. This module puts them side by side in one compact digest per aspect, so the person's
assistant reads all of them when it plans the ideal (eaos/ai/ideal/planner.py `bundle`, eaos/ai/semantic.py), and gives each
aspect a verdict:

    digest(out)        {aspect: {label, source, evidence..., rules: {verdict, why}}}, every list bounded by LIMIT
    rules_verdict(..)  the rules' own verdict from the evidence alone: `keep` (and why it is fine), `improve` (and what
                       the evidence shows) or `unmeasured` (the stage that measures it did not run, and why)
    final(out)         the verdict per aspect the reports show: the assistant's where its ideal plan of this check
                       judged the aspect (ideal/plan.json ideal.aspects), the rules' elsewhere, each saying who decided

Nothing here runs or measures; it only reads the records the stages wrote.
"""
from pathlib import Path
from ...core.system.files import read_json

ASPECTS = ('structure', 'sustainability', 'canonical_homes', 'tests', 'journeys', 'performance', 'resilience',
           'security', 'observability', 'screens', 'findings')
VERDICTS = ('keep', 'improve')
LABELS = {
    'structure': ('Structure and architecture', 'البنية والمعمار'),
    'sustainability': ('Sustainability indicators', 'مؤشرات الاستدامة'),
    'canonical_homes': ('One home per repeated definition', 'مكان واحد لكل تعريف مكرر'),
    'tests': ('Tests and coverage', 'الاختبارات وتغطيتها'),
    'journeys': ("Users' journeys through the app", 'رحلات المستخدم في البرنامج'),
    'performance': ('Speed under load', 'السرعة تحت الضغط'),
    'resilience': ('Resilience when a dependency fails', 'الصمود عند تعطل خدمة خارجية'),
    'security': ('Security', 'الأمان'),
    'observability': ('Observability in production', 'المراقبة في التشغيل الفعلي'),
    'screens': ('Screens and accessibility', 'الشاشات وسهولة الوصول'),
    'findings': ('Problems found in the code', 'المشاكل المكتشفة في الكود'),
}
LIMIT = {'rows': 8, 'members': 6}


def _load(out, name, default=None):
    return read_json(Path(out) / name, default)


def _verdict(verdict, why):
    return {'verdict': verdict, 'why': why}


def _summary(out, name):
    """The summary of one fact set, {} when it is missing."""
    return (_load(out, f'facts/{name}.json', {}) or {}).get('summary') or {}


def _hotspots(digest):
    return [{k: h.get(k) for k in ('path', 'complexity', 'commits', 'rloc')} for h in (digest.get('hotspots') or [])[:LIMIT['rows']]]


def _clusters(digest):
    return [{'id': c.get('id'), 'files': c.get('files'), 'members': (c.get('members') or [])[:LIMIT['members']],
             'most_depended_on': c.get('most_depended_on')} for c in (digest.get('clusters') or [])[:LIMIT['rows']]]


def _structure(out, ran):
    arch = (_load(out, 'architecture/map.json', {}) or {}) if ran.get('architecture') else {}
    digest = arch.get('digest') or {}
    graph, policy = _summary(out, 'graph'), _summary(out, 'policy')
    row = {'source': 'architecture/map.json, facts/graph.json, facts/policy.json, facts/metrics.json', 'city_hotspots': _hotspots(digest),
           'clusters': _clusters(digest), 'large_modules': _large_modules(out), 'modularity': digest.get('modularity'), 'cycles': graph.get('cycles'),
           'policy_violations': policy.get('violations') if policy.get('declared') else None,
           'map': {k: len(digest.get(k) or []) for k in ('hotspots', 'clusters')} if arch else None}
    row['rules'] = _structure_verdict(graph.get('cycles'), row['policy_violations'], arch, row['large_modules'])
    return row


def _large_modules(out):
    """The production modules past the code laws' line limit, largest first: each holds more than one responsibility."""
    from ...core.contracts.code_laws import MAX_LINES
    from ..maps.system import is_test
    metrics = (_load(out, 'facts/metrics.json', {}) or {}).get('facts') or []
    rows = sorted(({'path': f['location']['path'], 'lines': f['value'].get('lines'), 'definitions': f['value'].get('symbols')}
                   for f in metrics if f.get('kind') == 'metric' and f['value'].get('scope') == 'file'
                   and (f['value'].get('lines') or 0) > MAX_LINES and not is_test(f['location']['path'])), key=lambda r: -r['lines'])
    return {'limit': MAX_LINES, 'count': len(rows), 'largest': rows[:LIMIT['rows']]}


def _structure_verdict(cycles, violations, arch, large=None):
    if cycles is None and not arch:
        return _verdict('unmeasured', 'neither the dependency graph nor the architecture map was drawn in this check')
    large = large or {}
    oversized = large.get('count') or 0
    if cycles or violations or oversized:
        return _verdict('improve', f"{cycles or 0} import cycle(s), {violations or 0} breach(es) of the declared layering and "
                                   f"{oversized} module(s) past {large.get('limit')} lines")
    return _verdict('keep', 'no import cycle, no breach of a declared layering and no module past the line limit')


def _indicators(record):
    return [{'indicator': r.get('indicator'), 'value': r.get('value'), 'target': r.get('target'), 'gap': r.get('gap'),
             'measured': r.get('measured')} for r in record.get('rows') or []]


def _sustainability(out):
    record = _load(out, 'sustainability.json', {}) or {}
    rows = _indicators(record)
    row = {'source': 'sustainability.json', 'indicators': rows, 'moves': len(record.get('moves') or [])}
    measured = [r for r in rows if r['measured']]
    gaps = [r['indicator'] for r in measured if (r['gap'] or 0) > 0]
    row['rules'] = (_verdict('unmeasured', 'the sustainability indicators were not measured in this check') if not measured else
                    _verdict('improve', 'indicators above their target: ' + ', '.join(gaps)) if gaps else
                    _verdict('keep', f'all {len(measured)} measured indicators meet their target'))
    return row


def _home_row(stage):
    """A repeated definition: its rule, the home it should live in, how many places define it and their files."""
    return {'rule': str(stage.get('rule'))[:16], 'canonical_home': stage.get('canonical_home'), 'sites': len(stage.get('sites') or []),
            'files': sorted({x.get('path') for x in stage.get('sites') or [] if x.get('path')})[:LIMIT['members']]}


def _canonical_homes(out):
    plan = _load(out, 'transform-plan.json', None)
    stages = [s for s in (plan or {}).get('stages') or [] if s.get('move') == 'canonicalize']
    row = {'source': 'transform-plan.json',
           'homes': [_home_row(s) for s in stages[:LIMIT['rows']]],
           'repeated_definitions': len(stages),
           'without_a_viable_home': sum(1 for s in stages if not s.get('canonical_home'))}
    row['rules'] = (_verdict('unmeasured', 'no transform plan was written in this check') if plan is None else
                    _verdict('improve', f'{len(stages)} definition(s) repeated in several files, each with the home it should live in')
                    if stages else _verdict('keep', 'no definition is repeated across files'))
    return row


def _risky(out):
    """The measured files of complexity 10 or more, the most complex and then the most changed first."""
    measured = (_load(out, 'measurements.json', {}) or {}).get('files') or []
    return sorted((r for r in measured if (r.get('complexity_max') or 0) >= 10),
                  key=lambda r: (-(r.get('complexity_max') or 0), -(r.get('churn') or 0)))


def _tested(coverage, record):
    """Whether a test reaches a file: one of its lines ran when coverage was measured, else a test imports it."""
    declared = record.get('declared_coverage') or {}
    return (lambda p: (coverage.get(p) or {}).get('percent', 0) > 0) if coverage else (lambda p: p in declared)


def _tests(out):
    record = _load(out, 'verification.json', None)
    risky = _risky(out)
    if record is None:
        return {'source': 'verification.json', 'rules': _verdict('unmeasured', 'the tests were not looked at in this check')}
    coverage = record.get('coverage') or {}
    tested = _tested(coverage, record)
    untested = [{'path': r['path'], 'complexity': r.get('complexity_max'), 'commits': r.get('churn')}
                for r in risky if not tested(r['path'])][:LIMIT['rows']]
    failing = [a for a in record.get('attempts') or [] if a.get('exit_code') not in (0, None)]
    row = _tests_row(record, failing, untested)
    row['rules'] = _tests_verdict(row, record, failing, (untested, coverage))
    return row


def _tests_row(record, failing, untested):
    return {'source': 'verification.json, measurements.json', 'executed': bool(record.get('executed')),
           'why_not_executed': None if record.get('executed') else record.get('reason'),
           'command': record.get('command'), 'passed': record.get('passed'), 'overall_percent': record.get('overall_percent'),
           'test_files': len(record.get('test_files') or []), 'failing_commands': [' '.join(a.get('argv') or []) for a in failing][:4],
           'risky_code_without_tests': untested,
           'uncovered_entry_reachable_files': (record.get('uncovered_entry_reachable_files') or [])[:LIMIT['rows']],
           'suite': _suite(record)}


def _suite(record):
    """The suite itself: its time, its slowest tests, and the tests that run no line no other test runs."""
    return {k: v for k, v in (record.get('suite') or {}).items() if k != 'redundant'} | (
        {'redundant': (record.get('suite') or {}).get('redundant', [])[:LIMIT['rows']]} if record.get('suite') else {})


def _tests_verdict(row, record, failing, reach):
    """`reach`: (the complex files no test reaches, the measured coverage)."""
    untested, coverage = reach
    suite = record.get('suite') or {}
    if not row['test_files']: return _verdict('improve', 'the project has no test file')
    if failing: return _verdict('improve', f'{len(failing)} test command(s) fail on the code as it is')
    if (suite.get('redundant_share') or 0) > 0.2:
        return _verdict('improve', f"{suite['redundant_count']} of {suite['tests']} tests run no line another test does not "
                                   'run too: merge or delete them')
    if untested:
        return _verdict('improve', f"{len(untested)} complex file(s) no test {'runs' if coverage else 'imports'}: "
                                   + ', '.join(u['path'] for u in untested[:3]))
    return _verdict('keep', 'the tests ' + ('ran and passed, and ' if record.get('executed') else '') + 'reach every complex file')


def _journeys(out, ran):
    record = _load(out, 'live/journeys.json', None) if ran.get('journeys') else None
    lock = _load(out, 'live/lock.json', None) if ran.get('record') else None
    if record: return _walked(record)
    if lock: return _locked(lock)
    return {'source': 'live/journeys.json', 'rules': _verdict('unmeasured', 'the app was not run in an isolated copy in this check, '
                                                                          'so no journey was walked')}


def _walked(record):
    walked = record.get('walked') or []
    failed = [w for w in walked if w.get('status') == 'failed']
    row = {'source': 'live/journeys.json', 'walked': [{'spec': w.get('spec'), 'pages': (w.get('pages') or [])[:LIMIT['members']],
                                                       'status': w.get('status')} for w in walked[:LIMIT['rows']]],
           'failures': [{'spec': w.get('spec'), 'reason': w.get('reason')} for w in failed[:LIMIT['rows']]],
           'recordings': len(record.get('recordings') or [])}
    if failed: row['rules'] = _verdict('improve', f'{len(failed)} journey(s) fail on the app as it is today')
    elif walked: row['rules'] = _verdict('keep', f'all {len(walked)} journey(s) walked without a failure')
    else: row['rules'] = _verdict('unmeasured', 'no journey was walked')
    return row


def _locked(lock):
    failed = [r for r in lock.get('results') or [] if r.get('status') in ('failed', 'error')]
    rules = (_verdict('improve', f'{len(failed)} recorded screen(s) fail on the app as it is today') if failed else
             _verdict('keep', f"the {lock.get('specs')} recorded spec(s) pass twice on today's code"))
    return {'source': 'live/lock.json', 'specs': lock.get('specs'), 'passed': lock.get('passed'),
            'failures': [{'spec': r.get('path'), 'reason': r.get('reason')} for r in failed[:LIMIT['rows']]], 'rules': rules}


def _readiness(out, aspect):
    record = _load(out, 'readiness.json', None)
    rows = [f for f in (record or {}).get('findings') or [] if f.get('aspect') == aspect]
    row = {'source': 'readiness.json', 'findings': [{k: f.get(k) for k in ('id', 'status', 'title', 'detail', 'evidence')}
                                                     for f in rows[:LIMIT['rows']]]}
    row['rules'] = _readiness_verdict(record, rows)
    return row


def _readiness_verdict(record, rows):
    """improve with the gaps, else keep with what is ready, else unmeasured with what was found."""
    if record is None: return _verdict('unmeasured', 'readiness was not computed in this check')
    gaps = [f for f in rows if f.get('status') == 'gap']
    if gaps: return _verdict('improve', _titles(gaps[:3]))
    ok = [f for f in rows if f.get('status') == 'ok']
    if ok: return _verdict('keep', _titles(ok[:3]))
    return _verdict('unmeasured', _titles(rows[:2]) or 'nothing to judge')


def _titles(findings):
    return '; '.join(f['title'] for f in findings)


def _projected(load):
    """The entry points the load model projects, the costliest first."""
    return sorted((e for e in load.get('entry_points') or [] if e.get('projection')),
                  key=lambda e: -((e.get('projection') or {}).get('cost_score') or 0))


def _performance(out):
    row = _readiness(out, 'performance')
    ranked = _projected(_load(out, 'load-model.json', {}) or {})
    row['source'] += ', load-model.json'
    row['projected_at_1000x'] = [{'entry': e.get('label'), 'cost_score': e['projection'].get('cost_score'),
                                  'bottlenecks': e['projection'].get('bottlenecks')} for e in ranked[:LIMIT['rows']]]
    if row['rules']['verdict'] == 'unmeasured' and any(e['bottlenecks'] for e in row['projected_at_1000x']):
        row['rules'] = _verdict('improve', 'not measured under load in this check, and the projection at 1000x names bottlenecks: '
                                + ', '.join(sorted({b for e in row['projected_at_1000x'] for b in e['bottlenecks'] or []})))
    return row


def _screens(out, ran):
    screens = _load(out, 'live/screens.json', None) if ran.get('screens') else None
    visual = ((_load(out, 'nodes/visual_reviewer/findings.json', {}) or {}).get('findings') or []) if ran.get('visual') else []
    if not screens:
        return {'source': 'live/screens.json', 'rules': _verdict('unmeasured', 'no screen was pictured in this check')}
    return _pictured(screens, visual)


def _failing_screen(row):
    return {'page': row.get('page') or row.get('url'), 'failures': len(row.get('failures') or [])}


def _not_seen(row, screens):
    """The pages that did not open as themselves, listed, and the verdict made improve on them."""
    from ...live.access.roles import unseen
    if (missed := unseen(screens)):
        row['not_seen'] = [page['page'] for page in missed][:LIMIT['rows']]
        row['rules'] = _verdict('improve', f"{len(missed)} page(s) did not open as themselves (another view's, a sign-in or the "
                                f"app's not-found page): what they show is unknown, never a page missing; {row['rules']['why']}")


def _pictured(screens, visual):
    failing = [r for r in screens.get('rows') or [] if r.get('failures')]
    row = {'source': 'live/screens.json, nodes/visual_reviewer/findings.json', 'screens': len(screens.get('rows') or []),
           'with_accessibility_failures': [_failing_screen(r) for r in failing[:LIMIT['rows']]],
           'lighthouse': (screens.get('lighthouse') or {}).get('scores'), 'visual_findings': len(visual)}
    row['rules'] = (_verdict('improve', f'{len(failing)} screen(s) fail an accessibility check, {len(visual)} visual finding(s)')
                    if failing or visual else _verdict('keep', 'every pictured screen passes its accessibility checks'))
    _not_seen(row, screens)
    if screens.get('unreachable'): row['unreachable'] = screens['unreachable'][:LIMIT['rows']]     # proved from the code
    return _kinds(row, screens.get('coverage'))


def _kinds(row, covered):
    """The kinds of users of the code (eaos/live/access/roles.py): which the check saw, and who opened a page of another kind."""
    if not covered: return row
    said = [f"{b['kind']} opened {b['page']}, a page of {b['of']} only" for b in covered['breaches'][:3]] + \
           [f"{k['name']['en']} ({k['pages']} page(s)) was not seen: {UNSEEN[k['why']]}" for k in covered['kinds'] if not k['reached']]
    return {**row, 'kinds_of_users': covered, **({'rules': _verdict('improve', '; '.join(said) + '; ' + row['rules']['why'])} if said else {})}


UNSEEN = {'no_access': 'the account signed in with cannot open its pages', 'no_test_user': 'no session in it could be made',
          'not_opened': 'its pages did not open'}


def _findings(out):
    plan = _load(out, 'plan.json', {}) or {}
    cards = _load(out, 'cards.json', {}) or {}
    tasks = [t for t in plan.get('tasks') or [] if t.get('state', 'open') not in ('done', 'resolved')]
    from ..presentation.model import classify          # the card's severity, as the Studio shows it
    severity = {}
    for t in tasks: severity[classify(t)[1]] = severity.get(classify(t)[1], 0) + 1
    row = {'source': 'plan.json, cards.json', 'open_cards': len(tasks), 'by_severity': severity,
           'set_aside_by_the_triage': len(cards.get('set_aside') or []), 'doubted': len(cards.get('doubted') or [])}
    row['rules'] = (_verdict('improve', f'{len(tasks)} open card(s) with their evidence') if tasks else
                    _verdict('keep', 'no problem with enough evidence was found'))
    return row


# The stages whose record stays on disk when a later check does not run them (the report folder is the branch's, kept
# from one check to the next): their record is read only when they ended ok in this check.
OWN_RUN = ('architecture', 'journeys', 'record', 'screens', 'visual')


def ran_here(out):
    """{stage: True} for the stages that ended ok in this check: the checkpoint of the run in progress, else the
    manifest of the last run; None when the folder holds neither (every record on disk is then taken as this check's)."""
    for name in ('run-checkpoint.json', 'run-manifest.json'):
        record = _load(out, name, None)
        if isinstance(record, dict):
            return {stage: row.get('status') == 'ok' for stage, row in (record.get('stages') or {}).items() if isinstance(row, dict)}
    return None


def digest(out, ran=None):
    """{aspect: compact evidence and the rules' verdict}. `ran`: {stage: True} for the stages that ran in this check
    (ran_here when not given); the record of a stage in OWN_RUN is read only when it ran."""
    out = Path(out)
    ran = ran if ran is not None else ran_here(out)
    if ran is None: ran = {name: True for name in OWN_RUN}
    rows = {'structure': _structure(out, ran), 'sustainability': _sustainability(out), 'canonical_homes': _canonical_homes(out),
            'tests': _tests(out), 'journeys': _journeys(out, ran), 'performance': _performance(out),
            'resilience': _readiness(out, 'resilience'), 'security': _readiness(out, 'security'),
            'observability': _readiness(out, 'observability'), 'screens': _screens(out, ran), 'findings': _findings(out)}
    return {name: {'label': LABELS[name][0], **rows[name]} for name in ASPECTS}


def rules_verdict(out, ran=None):
    """{aspect: {verdict, why}}: the rules' verdict of every aspect."""
    return {name: row['rules'] for name, row in digest(out, ran).items()}


def final(out, plan=None, ran=None):
    """[{aspect, label, verdict, why, plan, cards, decided_by, rules}] for every aspect: the assistant's verdict where
    `plan`, the ideal it planned for this check (ideal/plan.json, eaos/ai/ideal/planner.py current), judged the aspect,
    the rules' elsewhere."""
    said = {row['aspect']: row for row in ((plan or {}).get('ideal') or {}).get('aspects') or []}
    rows = []
    for name, rule in rules_verdict(out, ran).items():
        mine = said.get(name)
        if mine:
            rows.append({'aspect': name, 'label': LABELS[name], 'verdict': mine['verdict'], 'why': mine['why'],
                         'plan': mine.get('plan') or '', 'cards': mine.get('cards') or [], 'decided_by': 'assistant',
                         'rules': rule['verdict']})
        else:
            rows.append({'aspect': name, 'label': LABELS[name], 'verdict': rule['verdict'], 'why': rule['why'], 'plan': '',
                         'cards': [], 'decided_by': 'rules', 'rules': rule['verdict']})
    return rows
