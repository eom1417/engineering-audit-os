"""Every aspect of the program, with its evidence and a verdict: keep it as it is, or improve it.

The check's stages each carry information about one side of the project: its structure, its health indicators, its
repeated definitions, its tests, its journeys, its speed under load, its resilience, security and observability, its
screens and its problems. This module puts them side by side in one compact digest per aspect, so the person's
assistant reads all of them when it plans the ideal (eaos/studio/ideal.py `bundle`, eaos/semantic.py), and gives each
aspect a verdict:

    digest(out)        {aspect: {label, source, evidence..., rules: {verdict, why}}}, every list bounded by LIMIT
    rules_verdict(..)  the rules' own verdict from the evidence alone: `keep` (and why it is fine), `improve` (and what
                       the evidence shows) or `unmeasured` (the stage that measures it did not run, and why)
    final(out)         the verdict per aspect the reports show: the assistant's where its ideal plan of this check
                       judged the aspect (ideal/plan.json ideal.aspects), the rules' elsewhere, each saying who decided

Nothing here runs or measures; it only reads the records the stages wrote.
"""
import json
from pathlib import Path

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
    try: return json.loads((Path(out) / name).read_text(encoding='utf-8'))
    except (OSError, ValueError): return default


def _verdict(verdict, why):
    return {'verdict': verdict, 'why': why}


def _structure(out, ran):
    arch = (_load(out, 'architecture/map.json', {}) or {}) if ran.get('architecture') else {}
    digest = arch.get('digest') or {}
    graph = (_load(out, 'facts/graph.json', {}) or {}).get('summary') or {}
    policy = (_load(out, 'facts/policy.json', {}) or {}).get('summary') or {}
    hot = [{k: h.get(k) for k in ('path', 'complexity', 'commits', 'rloc')} for h in (digest.get('hotspots') or [])[:LIMIT['rows']]]
    clusters = [{'id': c.get('id'), 'files': c.get('files'), 'members': (c.get('members') or [])[:LIMIT['members']],
                 'most_depended_on': c.get('most_depended_on')} for c in (digest.get('clusters') or [])[:LIMIT['rows']]]
    row = {'source': 'architecture/map.json, facts/graph.json, facts/policy.json, facts/metrics.json', 'city_hotspots': hot,
           'clusters': clusters, 'large_modules': _large_modules(out), 'modularity': digest.get('modularity'), 'cycles': graph.get('cycles'),
           'policy_violations': policy.get('violations') if policy.get('declared') else None,
           'map': {k: (arch.get(k) or {}).get('status') for k in ('city', 'clusters')} if arch else None}
    row['rules'] = _structure_verdict(graph.get('cycles'), row['policy_violations'], arch, row['large_modules'])
    return row


def _large_modules(out):
    """The production modules past the code laws' line limit, largest first: each holds more than one responsibility."""
    from .code_laws import MAX_LINES
    from .system_map import is_test
    metrics = (_load(out, 'facts/metrics.json', {}) or {}).get('facts') or []
    rows = sorted(({'path': f['location']['path'], 'lines': f['value'].get('lines'), 'definitions': f['value'].get('symbols')}
                   for f in metrics if f.get('kind') == 'metric' and f['value'].get('scope') == 'file'
                   and (f['value'].get('lines') or 0) > MAX_LINES and not is_test(f['location']['path'])), key=lambda r: -r['lines'])
    return {'limit': MAX_LINES, 'count': len(rows), 'largest': rows[:LIMIT['rows']]}


def _structure_verdict(cycles, violations, arch, large=None):
    if cycles is None and not arch:
        return _verdict('unmeasured', 'neither the dependency graph nor the architecture map was drawn in this check')
    oversized = (large or {}).get('count') or 0
    if cycles or violations or oversized:
        return _verdict('improve', f"{cycles or 0} import cycle(s), {violations or 0} breach(es) of the declared layering and "
                                   f"{oversized} module(s) past {(large or {}).get('limit')} lines")
    return _verdict('keep', 'no import cycle, no breach of a declared layering and no module past the line limit')


def _sustainability(out):
    record = _load(out, 'sustainability.json', {}) or {}
    rows = [{'indicator': r.get('indicator'), 'value': r.get('value'), 'target': r.get('target'), 'gap': r.get('gap'),
             'measured': r.get('measured')} for r in record.get('rows') or []]
    row = {'source': 'sustainability.json', 'indicators': rows, 'moves': len(record.get('moves') or [])}
    measured = [r for r in rows if r['measured']]
    gaps = [r['indicator'] for r in measured if (r['gap'] or 0) > 0]
    row['rules'] = (_verdict('unmeasured', 'the sustainability indicators were not measured in this check') if not measured else
                    _verdict('improve', 'indicators above their target: ' + ', '.join(gaps)) if gaps else
                    _verdict('keep', f'all {len(measured)} measured indicators meet their target'))
    return row


def _canonical_homes(out):
    plan = _load(out, 'transform-plan.json', None)
    stages = [s for s in (plan or {}).get('stages') or [] if s.get('move') == 'canonicalize']
    row = {'source': 'transform-plan.json',
           'homes': [{'rule': str(s.get('rule'))[:16], 'canonical_home': s.get('canonical_home'), 'sites': len(s.get('sites') or []),
                      'files': sorted({x.get('path') for x in s.get('sites') or [] if x.get('path')})[:LIMIT['members']]}
                     for s in stages[:LIMIT['rows']]],
           'repeated_definitions': len(stages),
           'without_a_viable_home': sum(1 for s in stages if not s.get('canonical_home'))}
    row['rules'] = (_verdict('unmeasured', 'no transform plan was written in this check') if plan is None else
                    _verdict('improve', f'{len(stages)} definition(s) repeated in several files, each with the home it should live in')
                    if stages else _verdict('keep', 'no definition is repeated across files'))
    return row


def _tests(out):
    record = _load(out, 'verification.json', None)
    measured = (_load(out, 'measurements.json', {}) or {}).get('files') or []
    risky = sorted((r for r in measured if (r.get('complexity_max') or 0) >= 10),
                   key=lambda r: (-(r.get('complexity_max') or 0), -(r.get('churn') or 0)))
    if record is None:
        return {'source': 'verification.json', 'rules': _verdict('unmeasured', 'the tests were not looked at in this check')}
    coverage = record.get('coverage') or {}
    declared = record.get('declared_coverage') or {}
    tested = (lambda p: (coverage.get(p) or {}).get('percent', 0) > 0) if coverage else (lambda p: p in declared)
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
           # The suite itself: its time, its slowest tests, and the tests that run no line no other test runs.
           'suite': {k: v for k, v in (record.get('suite') or {}).items() if k != 'redundant'} | (
               {'redundant': (record.get('suite') or {}).get('redundant', [])[:LIMIT['rows']]} if record.get('suite') else {})}


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
    gaps = [f for f in rows if f.get('status') == 'gap']
    ok = [f for f in rows if f.get('status') == 'ok']
    row['rules'] = (_verdict('unmeasured', 'readiness was not computed in this check') if record is None else
                    _verdict('improve', '; '.join(f['title'] for f in gaps[:3])) if gaps else
                    _verdict('keep', '; '.join(f['title'] for f in ok[:3])) if ok else
                    _verdict('unmeasured', '; '.join(f['title'] for f in rows[:2]) or 'nothing to judge'))
    return row


def _performance(out):
    row = _readiness(out, 'performance')
    load = _load(out, 'load-model.json', {}) or {}
    ranked = sorted((e for e in load.get('entry_points') or [] if e.get('projection')),
                    key=lambda e: -((e.get('projection') or {}).get('cost_score') or 0))
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


def _pictured(screens, visual):
    failing = [r for r in screens.get('rows') or [] if r.get('failures')]
    row = {'source': 'live/screens.json, nodes/visual_reviewer/findings.json', 'screens': len(screens.get('rows') or []),
           'with_accessibility_failures': [{'page': r.get('page') or r.get('url'), 'failures': len(r.get('failures') or [])}
                                           for r in failing[:LIMIT['rows']]],
           'lighthouse': (screens.get('lighthouse') or {}).get('scores'), 'visual_findings': len(visual)}
    row['rules'] = (_verdict('improve', f'{len(failing)} screen(s) fail an accessibility check, {len(visual)} visual finding(s)')
                    if failing or visual else _verdict('keep', 'every pictured screen passes its accessibility checks'))
    return row


def _findings(out):
    plan = _load(out, 'plan.json', {}) or {}
    cards = _load(out, 'cards.json', {}) or {}
    tasks = [t for t in plan.get('tasks') or [] if t.get('state', 'open') not in ('done', 'resolved')]
    from .studio.model import classify          # the card's severity, as the Studio shows it
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
    `plan`, the ideal it planned for this check (ideal/plan.json, eaos/studio/ideal.py current), judged the aspect,
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
