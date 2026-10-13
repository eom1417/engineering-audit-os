"""Assemble the canonical dossier and the artifacts derived from it.

Everything a reader sees is derived from `dossier.json`. Nothing is written into a human artifact
that does not exist in the ledger, and no claim reaches a reader without its confidence and source.
"""
from datetime import datetime, timezone
from pathlib import Path
from . import __version__
from . import claims as ledger
from . import progress
from .compose import Document
from .compose.labels import detail_artifact, impact_of, statement_of
from .compose.rules import validate
from .fact_documents import (contracts_document, describe, domain_document, flows_document, inventory_rows,
                             provenance_document, semantic_claims, trust_grades)
from .facts.store import read_set
from .map import ARTIFACTS, generate
from .workspace import read, write

MARKER = {'CONFIRMED': '⬤', 'LIKELY': '◐', 'HYPOTHESIS': '○', 'REFUTED': '⊘'}


def shorten(text, limit):
    """Cut on a word boundary; a decision artifact should not end a sentence mid-word."""
    text = ' '.join(str(text).split())
    if len(text) <= limit: return text
    cut = text[:limit]
    space = cut.rfind(' ')
    return (cut[:space] if space > limit * 0.6 else cut).rstrip(' ,،') + '…'
BRIEF = 'DECISION-BRIEF.md'
PROVENANCE = 'PROVENANCE.md'
RANK = {'CONFIRMED': 0, 'LIKELY': 1, 'HYPOTHESIS': 2, 'REFUTED': 3}


def legacy_records(run):
    run = Path(run)
    def maybe(name, default):
        path = run / name
        return read(path) if path.is_file() else default
    return {'findings': maybe('findings.json', []), 'architecture': maybe('architecture.json', {}),
            'flows': maybe('flows.json', []), 'coverage': maybe('coverage.json', []),
            'evidence': maybe('evidence.json', []), 'roadmap': maybe('roadmap.json', {}),
            'state': maybe('run.json', {})}


def coverage_of(sets, records, verification=None):
    syntax, resolve, entry = sets['syntax']['summary'], sets['resolve']['summary'], sets['entrypoints']['summary']
    return {'source_files': syntax['source_files'], 'files_parsed': syntax['files_parsed'],
            'parse_coverage': syntax['parse_coverage'],
            'imports_resolved': resolve['by_resolution']['RESOLVED'],
            'imports_total': sum(resolve['by_resolution'].values()),
            'internal_imports_resolved_rate': resolve['internal_resolution_rate'],
            'external_imports': resolve['by_resolution']['EXTERNAL'],
            'entry_points': entry['entry_points'],
            'production_entry_points': entry.get('production_entry_points', entry['entry_points']),
            'history_available': sets['history']['available'],
            'semantic_review': bool(records['findings']),
            'runtime_confirmation': 0,  # replaced below when execution evidence exists
            'not_examined': [
                f"unparsed source files: {syntax['by_status'].get('BLOCKED', 0) + syntax['by_status'].get('UNSUPPORTED', 0)}",
                f"unresolved or ambiguous imports: {resolve['by_resolution']['UNRESOLVED'] + resolve['by_resolution']['AMBIGUOUS']}",
                f"invocation surfaces with no detector: {sum(entry['files_without_any_detector'].values())} files",
                ('runtime behaviour: no execution evidence in this run'
                 if not (verification and verification.get('executed'))
                 else f"runtime behaviour beyond the executed command ({' '.join(verification.get('command') or [])}): unobserved"),
                *( [] if records['findings'] else ['semantic review: not performed in this run (facts only)'] ),
            ]}


def questions_of(records, sets):
    questions = [{'id': 'Q-%03d' % (index + 1), 'question': text, 'source': 'audit run'}
                 for index, text in enumerate(records['state'].get('unknowns', []) or [])]
    offset = len(questions)
    if not sets['history']['available']:
        offset += 1
        questions.append({'id': 'Q-%03d' % offset, 'question': 'History signals are unavailable for this snapshot; co-change coupling cannot be assessed.', 'source': 'facts'})
    elif (sets['history']['summary'].get('commits_analysed') or 0) < 10:
        offset += 1
        questions.append({'id': 'Q-%03d' % offset,
                          'question': 'History is too shallow (%d commits in scope) for co-change coupling to mean anything; no coupling claim was made from it.'
                                      % sets['history']['summary'].get('commits_analysed', 0), 'source': 'facts'})
    if not records['findings']:
        offset += 1
        questions.append({'id': 'Q-%03d' % offset, 'question': 'No semantic review was run: responsibilities, contracts and root causes are unassessed.', 'source': 'facts'})
    return questions


def tasks_of(records):
    rows = []
    for task in (records['roadmap'] or {}).get('tasks', []):
        rows.append({'id': task['id'], 'title': task.get('title', ''), 'kind': task.get('kind'),
                     'status': task.get('status'), 'readiness': 'needs_revalidation',
                     'compatibility': {'source': 'legacy', 'missing': ['typed decision', 'revision-bound checks']}, 'finding_ids': task.get('finding_ids', []),
                     'verify_command': task.get('verify_command'), 'files': task.get('files', [])})
    return rows


def runtime_claims(verification, offset, coverage_facts=None, excluded=None):
    """Execution evidence produces claims that are CONFIRMED because something actually ran."""
    if not verification or not verification.get('executed'): return []
    rows = []
    by_path = {fact['location']['path']: fact['id'] for fact in coverage_facts or []}
    uncovered = [path for path in verification.get('uncovered_entry_reachable_files', [])
                 if not (excluded and excluded(path))]
    if uncovered:
        rows.append(ledger.make(offset + 1,
                                f"{len(uncovered)} files reachable from an entry point were never executed by the test command "
                                f"({', '.join(uncovered[:3])}{'…' if len(uncovered) > 3 else ''})",
                                'risk', 'CONFIRMED', ['test_evidence'], [],
                                'A test run that executes those files, or evidence that they are not reachable in production either.',
                                fact_ids=sorted({by_path[path] for path in uncovered if path in by_path}),
                                render={'key': 'untested', 'params': {'count': len(uncovered)}},
                                impact={'scenario': 'A change in these files can ship without any test exercising it.'},
                                disposition={'kind': 'investigate', 'reason': 'Decide whether each path needs a test or is genuinely dead.'}))
    return rows


PROBLEM_TYPES = {'risk', 'cause', 'business_rule', 'structure', 'capability_gap'}


def needs_a_disposition(claim):
    """Anything that states a consequence, and anything not yet established, has to end somewhere:
    a task, a documented acceptance, or an open investigation."""
    return (claim['claim_type'] in PROBLEM_TYPES
            or bool((claim.get('impact') or {}).get('scenario'))
            or claim.get('confidence') in {'HYPOTHESIS', 'LIKELY'})


def asserts_a_problem(claim):
    return needs_a_disposition(claim)


ARCHIVE_PARTS = {'archive', 'archived', 'attic', '_archive'}


def archived(path):
    """Code the project set aside in an archive folder: kept for reference, not part of the running product."""
    return bool({part.lower() for part in Path(path).parts[:-1]} & ARCHIVE_PARTS)


def origin_of(claim, fact_index):
    """Whether a claim is about product code, test and fixture code, or archived code; a reader must not confuse them."""
    from .vocabulary import classify
    paths = [fact_index[fact_id] for fact_id in claim.get('fact_ids', []) if fact_id in fact_index]
    extra = []
    for fact_id in claim.get('fact_ids', []):
        extra += fact_index.get(fact_id + ':paths', [])
    located = [path for path in paths + extra if path]
    if located and all(archived(path) for path in located): return 'archive'
    categories = {classify(path) for path in located if not archived(path)}
    if not categories: return 'unknown'
    if categories == {'test'}: return 'test'
    return 'test_and_source' if 'test' in categories else 'source'


def fact_index_of(sets):
    """Where each fact lives, including the several paths a single fact can cover."""
    index = {}
    for data in sets.values():
        for fact in data['facts']:
            index[fact['id']] = fact['location'].get('path')
            value = fact.get('value') if isinstance(fact.get('value'), dict) else {}
            definitions = value.get('definitions')
            if definitions: index[fact['id'] + ':paths'] = [row['path'] for row in definitions]
            members = value.get('members')
            if members: index[fact['id'] + ':paths'] = list(members)
            # A cluster spans several files; without them the claim looks like it names none.
            occurrences = value.get('occurrences')
            if isinstance(occurrences, list) and occurrences and isinstance(occurrences[0], dict):
                paths = sorted({row['path'] for row in occurrences if row.get('path')})
                if paths: index[fact['id'] + ':paths'] = paths
    return index


def _gathered_claims(sets, records, load_record, target):
    """Every claim before merging: from the facts, the load model and the legacy records."""
    rows = ledger.from_facts(sets, target=target)
    if load_record:
        rows += ledger.from_load_model({'load_model': load_record}, len(rows))
    if records['findings'] or records['architecture']:
        rows += ledger.from_legacy(records['findings'], records['architecture'] or {}, records['flows'],
                                   records['coverage'], (records['state'] or {}).get('revision'))
    return rows


def _settle_claim(row, fact_index):
    """A numbered claim's origin, the artifact that shows it, and a disposition when it asserts a problem."""
    row['origin'] = origin_of(row, fact_index)
    row.setdefault('artifacts', [BRIEF if asserts_a_problem(row) else (detail_artifact(row) or 'SYSTEM-MAP.md')])
    if asserts_a_problem(row) and (row.get('disposition') or {}).get('kind') in (None, 'none_yet'):
        row['disposition'] = {'kind': 'investigate', 'reason': 'Ranked for review; no owner assigned yet in this run.'}


def _assess_mechanically(rows, sets, target):
    from .mechanical_assessment import build_assessment as mechanical
    for row in rows:
        built = mechanical(row, sets, target)
        if built: row['assessment'], row['checks'] = built['assessment'], built['checks']


def build_claims(sets, records, load_record=None, target=None):
    rows = _gathered_claims(sets, records, load_record, target)
    fact_index = fact_index_of(sets)
    # A claim from a detector under its measured precision bar is set aside before numbering: it is never
    # shown, planned or counted, and the precision set (tools/precision.py) still reads it.
    rows, withheld = ledger.withhold(ledger.merge(rows))
    rows = ledger.renumber(rows)
    for number, row in enumerate(withheld, start=1): row['id'] = 'WHD-%03d' % number
    for row in rows: _settle_claim(row, fact_index)
    # After numbering and origin are settled: a confirmed product observation whose evidence is mechanical
    # carries a ready repair under its family's engagement rule (eaos/mechanical_assessment.py).
    if target is not None: _assess_mechanically(rows, sets, target)
    return rows, fact_index, withheld


def _brief_header(target, dossier, words):
    coverage = dossier['coverage']
    counts = dossier['claim_counts']
    return [
        f"{target}  ·  {dossier['provenance']['generated_at']}  ·  eaos {dossier['provenance']['tool_version']}",
        f"{words['coverage']}: {coverage['files_parsed']}/{coverage['source_files']} "
        f"({round(coverage['parse_coverage'] * 100)}%) · internal imports resolved "
        f"{round(coverage['internal_imports_resolved_rate'] * 100)}% ({coverage['external_imports']} external) · "
        f"entry points {coverage['production_entry_points']}"
        + (f" (+{coverage['entry_points'] - coverage['production_entry_points']} in tests)"
           if coverage['entry_points'] != coverage['production_entry_points'] else '')
        + f" · runtime-confirmed {coverage['runtime_confirmation']}",
        '⬤ %d · ◐ %d · ○ %d · ؟ %d' % (counts.get('CONFIRMED', 0), counts.get('LIKELY', 0), counts.get('HYPOTHESIS', 0), len(dossier['questions'])),
        f"model calls: {dossier['provenance']['model_calls']}",
    ]


ORIGIN_TAGS = {('test', True): ' [كود اختبارات]', ('test', False): ' [test code]',
               ('archive', True): ' [كود مؤرشف]', ('archive', False): ' [archived code]'}


def _brief_row(claim, language):
    return [claim['id'], shorten(statement_of(claim, language), 150) + ORIGIN_TAGS.get((claim.get('origin'), language == 'ar'), ''),
            MARKER[claim['confidence']] + ' ' + claim['confidence'],
            shorten(impact_of(claim, language), 120),
            f"[{detail_artifact(claim) or 'dossier.json'}]({detail_artifact(claim) or 'dossier.json'})"]


def _do_now(dossier, top, language):
    """The first three tasks, else the first three ranked claims with where to read them."""
    return ([f"{task['id']} — {task.get('kind', 'legacy')}: "
             f"{statement_of({'statement': task['title'], 'render': task.get('render')}, language)[:120]}"
             for task in dossier['tasks'][:3]] or
            [claim['id'] + ' — ' + shorten(statement_of(claim, language), 120)
             + f" → [{detail_artifact(claim) or 'PLAN/'}]({detail_artifact(claim) or 'PLAN/WAVES.md'})" for claim in top[:3]])


def brief(target, dossier, language):
    document = Document(Document('', language).words['decision_brief'], language, budget_lines=120)
    words = document.words
    coverage = dossier['coverage']
    document.header(_brief_header(target, dossier, words))
    document.section('ما هذا النظام' if language == 'ar' else 'What this system is')
    document.text(dossier['description'])
    document.section('ملاحظات تستحق المراجعة' if language == 'ar' else 'Observations for review')
    ranked = sorted(dossier['claims'], key=lambda c: (-c.get('priority', 0), RANK[c['confidence']], c['id']))
    # Anything with a stated consequence competes for the five slots, whatever its record type.
    top = [c for c in ranked if c['claim_type'] in {'risk', 'cause', 'structure'} or (c.get('impact') or {}).get('scenario')][:5]
    document.table(['#', 'الادعاء' if language == 'ar' else 'Claim', 'الثقة' if language == 'ar' else 'Confidence',
                    'الأثر' if language == 'ar' else 'Impact', 'التفصيل' if language == 'ar' else 'Detail'],
                   [_brief_row(claim, language) for claim in top])
    from .decisions import decide
    decisions = [decide(claim) for claim in ranked]
    document.bullets([('القرارات: ' if language == 'ar' else 'Decisions: ') +
                      ', '.join(f"{kind}: {sum(d['kind'] == kind for d in decisions)}" for kind in ('repair', 'investigate', 'retain'))])
    document.section('افعل الآن' if language == 'ar' else 'Do now')
    document.bullets(_do_now(dossier, top, language))
    document.section('لا تفعل (الآن)' if language == 'ar' else 'Do not do (yet)')
    document.bullets(dossier['do_not'])
    document.section('أسئلة مفتوحة' if language == 'ar' else 'Open questions')
    document.table(['#', 'السؤال' if language == 'ar' else 'Question', 'المصدر' if language == 'ar' else 'Source'],
                   [[q['id'], shorten(q['question'], 160), q['source']] for q in dossier['questions']], limit=10)
    document.section(words['not_examined'])
    document.bullets(coverage['not_examined'])
    return document


def onboarding_document(target, dossier, sets, verification, language):
    """What a new engineer needs on day one, assembled from manifests, entry points and the graph."""
    words = Document('', language).words
    document = Document('دليل الانضمام' if language == 'ar' else 'Onboarding runbook', language, budget_lines=200)
    document.header(['مولَّد من الحقائق: الأوامر من الملفات المعلنة، وترتيب القراءة من الرسم.'
                     if language == 'ar' else
                     'Generated from facts: commands come from declared manifests, reading order from the graph.'])
    commands = [fact for fact in sets.get('entrypoints', {}).get('facts', [])
                if fact.get('kind') in {'entry_point', 'tool_command'}
                and fact['value']['framework'] in {'npm_script', 'make', 'console_script', 'docker_cmd', 'docker_entrypoint'}]
    document.section('ابنِ وشغّل' if language == 'ar' else 'Build and run')
    document.table(['الأمر' if language == 'ar' else 'Command', 'المصدر' if language == 'ar' else 'Declared in'],
                   [[fact['value']['route'], f"{fact['location']['path']}:{fact['location'].get('start_line') or 1}"]
                    for fact in commands], limit=15)
    document.section('اختبر' if language == 'ar' else 'Test')
    if verification and verification.get('executed'):
        document.bullets([' '.join(verification['command']),
                          f"{verification.get('overall_percent')}% coverage over {len(verification.get('test_files', []))} test files"])
    else:
        document.bullets([f"{len((verification or {}).get('test_files', []))} test files found; "
                          f"no test command was run by this check"])
    document.section('نقاط الدخول لتجربتها' if language == 'ar' else 'Entry points to try')
    production = [fact for fact in sets.get('entrypoints', {}).get('facts', [])
                  if fact.get('kind') == 'entry_point'
                  and fact['value'].get('category') != 'test' and fact['value']['surface'] in {'http', 'page', 'cli', 'job'}
                  and fact['value']['route'] and fact['value']['handler']]
    document.table([words['surface'], words['route'], words['handler'], words['location']],
                   [[fact['value']['surface'], fact['value']['route'] or '—', fact['value']['handler'] or '—',
                     f"{fact['location']['path']}:{fact['location'].get('start_line') or 1}"]
                    for fact in production], limit=15)
    document.section('أول عشرة ملفات تقرؤها' if language == 'ar' else 'The first ten files to read')
    from .vocabulary import classify
    ordered = [row for row in sets['graph']['summary']['attention_order'] if classify(row['path']) == 'source'][:10]
    document.table([words['path'], words['score'], 'لماذا' if language == 'ar' else 'Why'],
                   [[row['path'], row['score'],
                     'مركزية ' + str(row['factors']['centrality']) + ' · تغيّر ' + str(row['factors']['change'])
                     if language == 'ar' else
                     f"centrality {row['factors']['centrality']} · change {row['factors']['change']}"]
                    for row in ordered], limit=10)
    document.section('مصطلحات المشروع' if language == 'ar' else 'Project vocabulary')
    domain = [fact for fact in sets.get('domain', {}).get('facts', [])
              if fact['kind'] in {'domain_constant'} | ledger.shown_kinds({'data_model', 'data_table'})]
    document.table([words['name'], 'النوع' if language == 'ar' else 'Kind', words['location']],
                   [[fact['value'].get('name'), fact['kind'],
                     f"{fact['location']['path']}:{fact['location'].get('start_line') or 1}"]
                    for fact in domain], limit=20)
    document.section('مصائد معروفة' if language == 'ar' else 'Known traps')
    document.bullets([
        f"{sum(1 for fact in sets['entrypoints']['facts'] if fact.get('kind') == 'entry_point' and fact.get('resolution') == 'UNRESOLVED')} نقطة دخول تُسجَّل ديناميكيًا ولا يمكن تتبعها ساكنًا"
        if language == 'ar' else
        f"{sum(1 for fact in sets['entrypoints']['facts'] if fact.get('kind') == 'entry_point' and fact.get('resolution') == 'UNRESOLVED')} entry points are registered dynamically and cannot be traced statically",
        f"{len(sets['config']['summary']['unread_sensitive_config_files'])} sensitive config files are listed but never read",
        f"{sets['flows']['summary'].get('unresolved_steps', 0)} steps in the traced flows stop at calls the resolver cannot follow",
    ])
    return document


def index_document(target, dossier, sets, verification, language):
    words = Document('', language).words
    document = Document('الفهرس وترتيب القراءة' if language == 'ar' else 'Index and reading order',
                        language, budget_lines=120)
    provenance = dossier['provenance']
    coverage = dossier['coverage']
    semantic = sum(1 for claim in dossier['claims'] if 'model_inference' in claim.get('method', []))
    document.header([f"{target} · eaos {provenance['tool_version']} · {provenance['generated_at']} · "
                     f"model calls {provenance['model_calls']}",
                     f"{words['coverage']}: {coverage['files_parsed']}/{coverage['source_files']} · "
                     f"claims {len(dossier['claims'])} ({semantic} من طبقة دلالية)" if language == 'ar' else
                     f"{words['coverage']}: {coverage['files_parsed']}/{coverage['source_files']} · "
                     f"claims {len(dossier['claims'])} ({semantic} semantic)",
                     f"tasks {len(dossier.get('tasks', []))} · waves {len(dossier.get('waves', []))}"])
    document.section('اقرأ بهذا الترتيب' if language == 'ar' else 'Read in this order')
    rows = [
        ('تريد الصورة كاملة: التقارير الأربعة، وبقية الوثائق ملاحق لها' if language == 'ar' else
         'wanting the whole picture: the four reports; every other document is an appendix to them',
         '[CURRENT-STATE.md](CURRENT-STATE.md) → [TARGET-STATE.md](TARGET-STATE.md) → '
         '[GAP-AND-STRATEGY.md](GAP-AND-STRATEGY.md) → [EXECUTION-PLAN.md](EXECUTION-PLAN.md)', '20 min'),
        ('تقرّر أين يذهب الجهد' if language == 'ar' else 'deciding where effort goes',
         '[DECISION-BRIEF.md](DECISION-BRIEF.md) → [RISK-REGISTER.md](RISK-REGISTER.md) → [PLAN/WAVES.md](PLAN/WAVES.md)', '5 min'),
        ('تنضم للمشروع اليوم' if language == 'ar' else 'joining the project today',
         '[ONBOARDING.md](ONBOARDING.md) → [SYSTEM-MAP.md](SYSTEM-MAP.md) → [FLOWS.md](FLOWS.md)', '45 min'),
        ('تراجع البنية' if language == 'ar' else 'reviewing the architecture',
         '[POLICY.md](POLICY.md) → [COUPLING-ATLAS.md](COUPLING-ATLAS.md) → [CONTRACTS.md](CONTRACTS.md)', '30 min'),
        ('ستغيّر ملفًا محددًا' if language == 'ar' else 'about to change one file',
         "the assistant's `impact` tool (/eaos)", '1 min'),
    ]
    document.table(['إن كنت…' if language == 'ar' else 'If you are…', 'ابدأ بـ' if language == 'ar' else 'Start with',
                    'الوقت' if language == 'ar' else 'Time'], [list(row) for row in rows])
    document.section('درجة الإسناد لكل قسم' if language == 'ar' else 'How well each section is sourced')
    document.table(['القسم' if language == 'ar' else 'Section', 'المصدر' if language == 'ar' else 'Source',
                    'الدرجة' if language == 'ar' else 'Grade', 'ملاحظة' if language == 'ar' else 'Note'],
                   [[row['section'], row['source'], row['grade'], row['note']]
                    for row in trust_grades(dossier, sets, verification)])
    document.section(words['not_examined'])
    document.bullets(coverage['not_examined'])
    document.section('كل الملفات' if language == 'ar' else 'Every file')
    document.table(['#', 'الملف' if language == 'ar' else 'File', 'لماذا' if language == 'ar' else 'Why'],
                   inventory_rows(language))
    document.section('إعادة الإنتاج' if language == 'ar' else 'Reproduce')
    document.bullets([f'eaos audit {target} --out <dir> --engines',
                      f'eaos audit {target} --out <dir> --resume'])
    return document


def write_register(out, dossier, language):
    """debt-register.json, and RISK-REGISTER.md rendered from it: one register (eaos/debt_register.py)."""
    from .debt_register import build, render
    record = build(out, dossier)
    write(Path(out) / 'debt-register.json', record)
    (Path(out) / 'RISK-REGISTER.md').write_text(render(record, language).render(), encoding='utf-8')


def refresh_views(out, language='ar'):
    """Re-render the views the ledger owns: the brief, the risk register and the index.

    Rebuilding the plan or the product report belongs to eaos.views, one layer up. Doing it here
    made dossier, plan and product_review import each other in a cycle.
    """
    out = Path(out)
    dossier_path = out / 'dossier.json'
    if not dossier_path.is_file(): raise ValueError('No dossier to refresh in ' + str(out))
    dossier = read(dossier_path)
    from .facts.run import read_available
    sets = read_available(out)
    verification = read(out / 'verification.json') if (out / 'verification.json').is_file() else None
    target = dossier['provenance']['target']
    # A claim added after assembly — by the semantic pass or by a later probe — must be ranked too,
    # or it sorts at zero and lands wherever the list happens to put it.
    from .ranking import rank
    for claim in dossier['claims']: _settle_disposition(claim)
    dossier['claims'] = rank(dossier['claims'], sets, fact_index_of(sets))
    counts = {}
    for claim in dossier['claims']: counts[claim['confidence']] = counts.get(claim['confidence'], 0) + 1
    dossier['claim_counts'] = counts
    if verification and verification.get('executed'):
        dossier['coverage']['runtime_confirmation'] = sum(
            1 for claim in dossier['claims'] if {'test_evidence', 'runtime_probe'} & set(claim.get('method', [])))
    _note_semantic(dossier)
    from .decisions import decide, identity
    for claim in dossier['claims']: claim.setdefault('uid', identity(claim))
    dossier['decisions'] = [decide(claim) for claim in dossier['claims']]
    write(dossier_path, dossier)
    (out / BRIEF).write_text(brief(target, dossier, language).render(), encoding='utf-8')
    write_register(out, dossier, language)
    (out / 'README.md').write_text(index_document(target, dossier, sets, verification, language).render(), encoding='utf-8')
    return {'out': str(out), 'claims': len(dossier['claims']), 'tasks': len(dossier.get('tasks', [])),
            'refreshed': [BRIEF, 'RISK-REGISTER.md', 'README.md']}


def _settle_disposition(claim):
    """A claim added after assembly gets the artifact that shows it and, when it needs one, a disposition."""
    claim.setdefault('artifacts', [BRIEF if asserts_a_problem(claim) else (detail_artifact(claim) or 'SYSTEM-MAP.md')])
    if needs_a_disposition(claim) and (claim.get('disposition') or {}).get('kind') in (None, 'none_yet'):
        claim['disposition'] = {'kind': 'investigate',
                                'reason': ('Not established yet; decide it before acting on it.'
                                           if claim.get('confidence') in {'HYPOTHESIS', 'LIKELY'}
                                           else 'Ranked for review; no owner assigned yet in this run.')}


def _note_semantic(dossier):
    """Once the semantic review ran, the notes saying it did not are taken out of the dossier."""
    semantic_ran = any('model_inference' in claim.get('method', []) for claim in dossier['claims'])
    dossier['coverage']['not_examined'] = [note for note in dossier['coverage']['not_examined']
                                           if not (semantic_ran and note.startswith('semantic review'))]
    if not semantic_ran: return
    dossier['questions'] = [question for question in dossier['questions']
                            if not question['question'].startswith('No semantic review was run')]
    # The one-line description also claimed nothing had been interpreted.
    dossier['description'] = dossier['description'].replace(
        '○ Responsibilities and contracts are not assessed in a facts-only run.',
        f'○ {semantic_claims(dossier)} responsibility and contract claims come from model inference '
        'and none is confirmed by inference alone.')


# The counted steps of assemble(): the structural map, the claims, their ranking, the dossier, the documents.
CLAIM_STEPS = 5


def assemble(target, out, run=None, language='ar', version=None, exclude=(), engines=None, collected=None):
    target, out = Path(target).resolve(), Path(out).resolve()
    progress.count('claim steps', 0, CLAIM_STEPS)
    map_result, sets = generate(target, out, language, exclude=exclude, engines=engines, collected=collected)
    progress.count('claim steps', 1, CLAIM_STEPS)
    # A project that declares a policy gets it enforced as part of the dossier, not as a separate step.
    from .policy import FILENAME as POLICY_FILE, check as check_policy
    if (target / POLICY_FILE).is_file():
        check_policy(target, out, language=language)
        sets['policy'] = read_set(out, 'policy')
    records = legacy_records(run) if run else {'findings': [], 'architecture': {}, 'flows': [], 'coverage': [],
                                               'evidence': [], 'roadmap': {}, 'state': {}}
    verification = read(out / 'verification.json') if (out / 'verification.json').is_file() else None
    # The load record lives beside the fact sets, not among them: it has a different shape, so it
    # is handed over separately rather than pushed into a map every consumer expects to be uniform.
    load_record = read(out / 'load-model.json') if (out / 'load-model.json').is_file() else None
    rows, fact_index, withheld = build_claims(sets, records, load_record=load_record, target=target)
    progress.count('claim steps', 2, CLAIM_STEPS)
    from fnmatch import fnmatch
    patterns = [p.strip('/') for p in (exclude or []) if p.strip('/')]
    def source_filter(path): return any(path == p or path.startswith(p + '/') or fnmatch(path, p) for p in patterns)
    for extra in ['fingerprint', 'sequences', 'redundancy', 'structure']:
        if (out / 'facts' / (extra + '.json')).is_file(): sets[extra] = read_set(out, extra)
    coverage_set = read_set(out, 'verification') if (out / 'facts/verification.json').is_file() else None
    if coverage_set: sets['verification'] = coverage_set
    runtime = runtime_claims(verification, len(rows), (coverage_set or {}).get('facts'), excluded=source_filter)
    for fact in (coverage_set or {}).get('facts', []): fact_index.setdefault(fact['id'], fact['location'].get('path'))
    for row in runtime:
        row['origin'] = origin_of(row, fact_index)
        row.setdefault('artifacts', [BRIEF])
        row.setdefault('disposition', {'kind': 'investigate', 'reason': 'Ranked for review; no owner assigned yet in this run.'})
    rows += runtime
    from .ranking import rank
    rows = rank(rows, sets, fact_index)
    progress.count('claim steps', 3, CLAIM_STEPS)
    problems = ledger.errors(rows, {e['id'] for e in records['evidence']} if records['evidence'] else (),
                             {f['id'] for data in sets.values() for f in data['facts']})
    if problems: raise ValueError('Claim ledger rejected: ' + '; '.join(problems[:5]))
    counts = {}
    for row in rows: counts[row['confidence']] = counts.get(row['confidence'], 0) + 1
    dossier = {
        'schema_version': 1,
        'provenance': {'target': str(target), 'tool_version': version or __version__,
                       'generated_at': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),
                       'snapshot_fingerprint': sets['syntax']['input_sha'],
                       'audit_run': str(run) if run else None,
                       'model_calls': 0 if not run else (records['state'] or {}).get('model_calls', 'see engine-state.json'),
                       'extractors': {name: data['extractor_version'] for name, data in sorted(sets.items())},
                       'excluded_patterns': map_result.get('exclude_patterns', list(exclude or []))},
        'coverage': {**coverage_of(sets, records, verification),
                     'runtime_confirmation': sum(1 for row in rows if 'test_evidence' in row['method'] or 'runtime_probe' in row['method']),
                     'executed_verification': bool(verification and verification.get('executed')),
                     'executed_coverage_percent': (verification or {}).get('overall_percent')},
        'description': describe(sets, records),
        'claim_counts': counts,
        'claims': rows,
        'withheld_claims': withheld,
        'questions': questions_of(records, sets),
        'tasks': tasks_of(records),
        'legacy_tasks': tasks_of(records),
        'compatibility': {'source': 'legacy' if run else 'native',
                          'legacy_tasks_require_revalidation': bool(tasks_of(records))},
        'do_not': ['لا تعتمد هذا المخرج كمراجعة أمنية أو شهادة جاهزية إنتاج.',
                   'لا تقرأ ترتيب الانتباه كترتيب خطورة؛ هو اصطلاح معلن للأولوية في القراءة.',
                   'لا تعتبر غياب نتيجة دليلًا على سلامة؛ الغياب يعني عدم الفحص ما لم يُصرَّح ببحث عن الغياب.']
        if language == 'ar' else
        ['Do not treat this as a security review or a production-readiness certificate.',
         'Do not read the attention order as a severity order; it is a declared reading convention.',
         'Do not read an absent finding as safety; absence means unexamined unless an absence search is declared.'],
        'artifacts': sorted([BRIEF, PROVENANCE, 'FLOWS.md', 'DOMAIN-AND-DATA.md', 'CONTRACTS.md',
                             'RISK-REGISTER.md', 'README.md', 'ONBOARDING.md', *ARTIFACTS]
                            + (['POLICY.md'] if (target / 'eaos.policy.json').is_file() else [])
                            + (['ENGINES.md'] if (out / 'facts/external.json').is_file() else [])),
    }
    from .decisions import decide, identity
    for claim in dossier['claims']: claim.setdefault('uid', identity(claim))
    dossier['decisions'] = [decide(claim) for claim in dossier['claims']]
    write(out / 'dossier.json', dossier)
    progress.count('claim steps', 4, CLAIM_STEPS)
    (out / BRIEF).write_text(brief(str(target), dossier, language).render(), encoding='utf-8')
    for name, builder in [('FLOWS.md', flows_document), ('DOMAIN-AND-DATA.md', domain_document), ('CONTRACTS.md', contracts_document)]:
        (out / name).write_text(builder(dossier, sets, language).render(), encoding='utf-8')
    write_register(out, dossier, language)
    (out / 'README.md').write_text(index_document(str(target), dossier, sets, verification, language).render(), encoding='utf-8')
    (out / 'ONBOARDING.md').write_text(onboarding_document(str(target), dossier, sets, verification, language).render(), encoding='utf-8')
    (out / PROVENANCE).write_text(provenance_document(str(target), dossier, language).render(), encoding='utf-8')
    violations = validate(out, dossier)
    result = write_verdict(out, dossier, violations, target=str(target), facts=map_result['facts'])
    progress.count('claim steps', CLAIM_STEPS, CLAIM_STEPS)
    return result


VERDICT = 'report-result.json'


def write_verdict(out, dossier, violations, target=None, facts=None):
    """The one place report-result.json is written.

    The validate stage used to write a thinner copy of this record over the dossier's, dropping the
    claim and fact counts a reader needs beside the verdict.
    """
    out = Path(out)
    provenance = dossier.get('provenance') or {}
    result = {'target': target or provenance.get('target'), 'out': str(out),
              'artifacts': dossier.get('artifacts', []),
              'claims': len(dossier.get('claims', [])),
              'claim_counts': dossier.get('claim_counts') or _counts(dossier.get('claims', [])),
              'questions': len(dossier.get('questions', [])),
              'facts': facts if facts is not None else _fact_count(out),
              'model_calls': provenance.get('model_calls', 0),
              'output_spec_violations': list(violations),
              'status': 'READY' if not violations else 'OUTPUT_SPEC_VIOLATED',
              'limits': 'A dossier reports what was examined. Claims carry their confidence and their '
                        'refutation; unexamined scope is listed, not implied.'}
    write(out / VERDICT, result)
    return result


def _fact_count(out):
    """How many facts the report rests on, read from the index rather than guessed."""
    index = Path(out) / 'facts' / 'index.json'
    if not index.is_file():
        return None
    try:
        return sum(entry.get('facts', 0) for entry in read(index)['sets'])
    except (ValueError, KeyError, OSError):
        return None


def _counts(claims):
    tally = {}
    for claim in claims:
        tally[claim.get('confidence', '?')] = tally.get(claim.get('confidence', '?'), 0) + 1
    return tally
