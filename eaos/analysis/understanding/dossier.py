"""Assemble the canonical dossier and the artifacts derived from it.

Everything a reader sees is derived from `dossier.json`. Nothing is written into a human artifact
that does not exist in the ledger, and no claim reaches a reader without its confidence and source (claims: gather.py).
"""
from collections import namedtuple
from datetime import datetime, timezone
from functools import partial
from pathlib import Path
from ... import __version__
from ..claims import from_old_engines, ledger
from ..claims.gather import REGISTER, build_claims, fact_index_of, needs_a_disposition, origin_of, runtime_claims
from ...core import progress
from ...core.contracts.document import Document, say
from ...core.contracts.document_rules import validate
from ...facts.store import read_set
from ...core.project.workspace import read, write

# What the dossier was asked for (assemble's arguments) and what it is built from: each travels whole to every step.
_Request = namedtuple('_Request', 'target out run language version exclude')
_Inputs = namedtuple('_Inputs', 'map_result sets records verification')


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
    questions += _layer_questions(sets, offset)
    offset = len(questions)
    if not records['findings']:
        offset += 1
        questions.append({'id': 'Q-%03d' % offset, 'question': 'No semantic review was run: responsibilities, contracts and root causes are unassessed.', 'source': 'facts'})
    return questions


def _layer_questions(sets, offset):
    """What the layers could not decide (eaos/analysis/layers/), numbered after `offset`."""
    asked = ((sets.get('boundaries') or {}).get('summary') or {}).get('asked') or []
    return [{'id': 'Q-%03d' % (offset + index), 'question': row['question'], 'question_ar': row['question_ar'], 'source': 'layers'}
            for index, row in enumerate(asked, start=1)]


def tasks_of(records):
    rows = []
    for task in (records['roadmap'] or {}).get('tasks', []):
        rows.append({'id': task['id'], 'title': task.get('title', ''), 'kind': task.get('kind'),
                     'status': task.get('status'), 'readiness': 'needs_revalidation',
                     'compatibility': {'source': 'legacy', 'missing': ['typed decision', 'revision-bound checks']}, 'finding_ids': task.get('finding_ids', []),
                     'verify_command': task.get('verify_command'), 'files': task.get('files', [])})
    return rows


def semantic_claims(dossier):
    return sum(1 for claim in dossier['claims'] if 'model_inference' in claim.get('method', []))


def inventory_rows(language):
    """Every declared document in reading order, with the reason a reader would open it.

    Generated from the artifact contract, not written by hand, so a document that is added,
    renamed or dropped appears here instead of being discoverable only by listing the directory.
    Whether this particular run produced it is RUN.md's question, not this one's.
    """
    from ...core.contracts.artifacts import reading_order
    rows = []
    for position, artifact in enumerate(reading_order(), start=1):
        note = artifact.purpose
        if not artifact.required:
            note += (' — يغيب حين: ' if language == 'ar' else ' — absent when: ') + artifact.absent_when
        rows.append([str(position), f'[{artifact.name}]({artifact.name})', note])
    return rows


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


def index_document(target, dossier, language):
    tr = partial(say, language)
    document = Document(tr('الفهرس وترتيب القراءة', 'Index and reading order'), language, budget_lines=120)
    words = document.words
    provenance = dossier['provenance']
    coverage = dossier['coverage']
    semantic = semantic_claims(dossier)
    document.header([f"{target} · eaos {provenance['tool_version']} · {provenance['generated_at']} · "
                     f"model calls {provenance['model_calls']}",
                     f"{words['coverage']}: {coverage['files_parsed']}/{coverage['source_files']} · "
                     f"claims {len(dossier['claims'])} ({semantic} {tr('من طبقة دلالية', 'semantic')})",
                     f"tasks {len(dossier.get('tasks', []))} · waves {len(dossier.get('waves', []))}"])
    document.section(tr('اقرأ بهذا الترتيب', 'Read in this order'))
    rows = [
        [tr('تريد الصورة كاملة: التقارير الأربعة، وبقية الوثائق ملاحق لها',
            'wanting the whole picture: the four reports; every other document is an appendix to them'),
         '[CURRENT-STATE.md](CURRENT-STATE.md) → [TARGET-STATE.md](TARGET-STATE.md) → '
         '[GAP-AND-STRATEGY.md](GAP-AND-STRATEGY.md) → [EXECUTION-PLAN.md](EXECUTION-PLAN.md)', '20 min'],
        [tr('تقرّر أين يذهب الجهد', 'deciding where effort goes'),
         '[START-HERE.md](START-HERE.md) → [PLAN/STEPS.md](PLAN/STEPS.md) → [PLAN/WAVES.md](PLAN/WAVES.md)', '5 min'],
        [tr('تراجع البنية', 'reviewing the architecture'),
         '[TARGET-ARCHITECTURE.md](TARGET-ARCHITECTURE.md) → [GAP-AND-STRATEGY.md](GAP-AND-STRATEGY.md)', '30 min'],
        [tr('تريد أن تعرف كيف جرى الفحص', 'checking how this check ran'), '[RUN.md](RUN.md)', '2 min'],
        [tr('ستغيّر ملفًا محددًا', 'about to change one file'), "the assistant's `impact` tool (/eaos)", '1 min'],
    ]
    document.table([tr('إن كنت…', 'If you are…'), tr('ابدأ بـ', 'Start with'), tr('الوقت', 'Time')], rows)
    document.section(words['not_examined'])
    document.bullets(coverage['not_examined'])
    document.section(tr('كل الملفات', 'Every file'))
    document.table(['#', tr('الملف', 'File'), tr('لماذا', 'Why')], inventory_rows(language))
    document.section(tr('إعادة الإنتاج', 'Reproduce'))
    document.bullets([f'eaos audit {target} --out <dir> --engines',
                      f'eaos audit {target} --out <dir> --resume'])
    return document


def write_register(out, dossier):
    """debt-register.json: one register (eaos/analysis/assessments/debt_register.py)."""
    from ..assessments.debt_register import build
    write(Path(out) / REGISTER, build(out, dossier))


def refresh_views(out, language='ar'):
    """Re-render the views the ledger owns: the debt register and the index.

    Rebuilding the plan or the product report belongs to eaos.report.views, one layer up. Doing it here
    made dossier, plan and product_review import each other in a cycle.
    """
    out = Path(out)
    dossier_path = out / 'dossier.json'
    if not dossier_path.is_file(): raise ValueError('No dossier to refresh in ' + str(out))
    dossier = read(dossier_path)
    from ...facts.run import read_available
    sets = read_available(out)
    verification = read(out / 'verification.json') if (out / 'verification.json').is_file() else None
    target = dossier['provenance']['target']
    # A claim added after assembly — by the semantic pass or by a later probe — must be ranked too,
    # or it sorts at zero and lands wherever the list happens to put it.
    from ..planning.ranking import rank
    for claim in dossier['claims']: _settle_disposition(claim)
    dossier['claims'] = rank(dossier['claims'], sets, fact_index_of(sets))
    dossier['claim_counts'] = _counts(dossier['claims'])
    if verification and verification.get('executed'):
        dossier['coverage']['runtime_confirmation'] = sum(
            1 for claim in dossier['claims'] if {'test_evidence', 'runtime_probe'} & set(claim.get('method', [])))
    _note_semantic(dossier)
    _decide(dossier)
    write(dossier_path, dossier)
    _write_views(out, target, dossier, language)
    return {'out': str(out), 'claims': len(dossier['claims']), 'tasks': len(dossier.get('tasks', [])),
            'refreshed': [REGISTER, 'README.md']}


def _decide(dossier):
    """Each claim's stable identity, and the decision on every claim."""
    from ...core.contracts.decisions import decide, identity
    for claim in dossier['claims']: claim.setdefault('uid', identity(claim))
    dossier['decisions'] = [decide(claim) for claim in dossier['claims']]


def _write_views(out, target, dossier, language):
    """The views the ledger owns: the debt register and the index."""
    write_register(out, dossier)
    (out / 'README.md').write_text(index_document(target, dossier, language).render(), encoding='utf-8')


def _settle_disposition(claim):
    """A claim added after assembly gets the artifact that shows it and, when it needs one, a disposition."""
    claim.setdefault('artifacts', [REGISTER])
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


# The counted steps of assemble(): the facts, the claims, their ranking, the dossier, the index and the verdict.
CLAIM_STEPS = 5


def _collected(target, out, exclude, engines, collected):
    """(collection result, fact sets): the facts a pipeline already collected, else collected now."""
    from ...facts.run import collect
    result = collected or collect(target, out, None, exclude=exclude, engines=engines)
    return result, {entry['set']: read_set(out, entry['set']) for entry in result['sets']}


def assemble(target, out, run=None, language='ar', version=None, exclude=(), engines=None, collected=None):  # limits: parameters -- the project and report, then the check's options by name (_Request)
    target, out = Path(target).resolve(), Path(out).resolve()
    progress.count('claim steps', 0, CLAIM_STEPS)
    map_result, sets = _collected(target, out, exclude, engines, collected)
    progress.count('claim steps', 1, CLAIM_STEPS)
    # A project that declares a policy gets it enforced as part of the dossier, not as a separate step.
    from ..target_state.policy import FILENAME as POLICY_FILE, check as check_policy
    if (target / POLICY_FILE).is_file():
        check_policy(target, out)
        sets['policy'] = read_set(out, 'policy')
    # The layers (eaos/analysis/layers/) write their findings beside the collected sets: their claims and questions.
    if (out / 'facts' / 'boundaries.json').is_file(): sets['boundaries'] = read_set(out, 'boundaries')
    records = legacy_records(run) if run else {'findings': [], 'architecture': {}, 'flows': [], 'coverage': [],
                                               'evidence': [], 'roadmap': {}, 'state': {}}
    verification = read(out / 'verification.json') if (out / 'verification.json').is_file() else None
    request, inputs = _Request(target, out, run, language, version, exclude), _Inputs(map_result, sets, records, verification)
    rows, withheld = _claims(request, inputs)
    progress.count('claim steps', 3, CLAIM_STEPS)
    problems = ledger.errors(rows, {e['id'] for e in records['evidence']} if records['evidence'] else (),
                             {f['id'] for data in sets.values() for f in data['facts']})
    if problems: raise ValueError('Claim ledger rejected: ' + '; '.join(problems[:5]))
    dossier = _dossier(request, inputs, rows, withheld)
    _decide(dossier)
    write(out / 'dossier.json', dossier)
    progress.count('claim steps', 4, CLAIM_STEPS)
    _write_views(out, str(target), dossier, language)
    violations = validate(out, dossier)
    result = write_verdict(out, dossier, violations, target=str(target), facts=map_result['facts'])
    progress.count('claim steps', CLAIM_STEPS, CLAIM_STEPS)
    return result


def _excluded(exclude):
    """excluded(path): whether a path is under one of the excluded patterns."""
    from fnmatch import fnmatch
    patterns = [p.strip('/') for p in (exclude or []) if p.strip('/')]
    def source_filter(path): return any(path == p or path.startswith(p + '/') or fnmatch(path, p) for p in patterns)
    return source_filter


def _more_sets(out, sets):
    """The fact sets the runtime claims and the ranking read beside the collected ones, into `sets`; the coverage set,
    or None when the tests were not run."""
    for extra in ['fingerprint', 'sequences', 'redundancy', 'structure']:
        if (out / 'facts' / (extra + '.json')).is_file(): sets[extra] = read_set(out, extra)
    coverage_set = read_set(out, 'verification') if (out / 'facts/verification.json').is_file() else None
    if coverage_set: sets['verification'] = coverage_set
    return coverage_set


def _claims(request, inputs):
    """(ranked claims, withheld claims): the facts' claims and the runtime ones, outside the excluded paths."""
    # The load record lives beside the fact sets, not among them: it has a different shape, so it
    # is handed over separately rather than pushed into a map every consumer expects to be uniform.
    load_record = read(request.out / 'load-model.json') if (request.out / 'load-model.json').is_file() else None
    rows, fact_index, withheld = build_claims(inputs.sets, inputs.records, load_record=load_record, target=request.target)
    progress.count('claim steps', 2, CLAIM_STEPS)
    coverage_set = _more_sets(request.out, inputs.sets)
    runtime = runtime_claims(inputs.verification, len(rows), (coverage_set or {}).get('facts'), excluded=_excluded(request.exclude))
    runtime += from_old_engines.old_engine_claims(request.out, inputs.sets, request.target, len(rows) + len(runtime))   # they read what ran (M13)
    for fact in (coverage_set or {}).get('facts', []): fact_index.setdefault(fact['id'], fact['location'].get('path'))
    for row in runtime:
        row['origin'] = origin_of(row, fact_index)
        row.setdefault('artifacts', [REGISTER])
        row.setdefault('disposition', {'kind': 'investigate', 'reason': 'Ranked for review; no owner assigned yet in this run.'})
    from ..planning.ranking import rank
    return rank(rows + runtime, inputs.sets, fact_index), withheld


def _dossier(request, inputs, rows, withheld):
    target, run, (_, sets, records, verification) = request.target, request.run, inputs
    tasks = tasks_of(records)
    return {
        'schema_version': 1,
        'provenance': {'target': str(target), 'tool_version': request.version or __version__,
                       'generated_at': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'), 'snapshot_fingerprint': sets['syntax']['input_sha'],
                       'audit_run': str(run) if run else None,
                       'model_calls': 0 if not run else (records['state'] or {}).get('model_calls', 'see engine-state.json'),
                       'extractors': {name: data['extractor_version'] for name, data in sorted(sets.items())},
                       'excluded_patterns': inputs.map_result.get('exclude_patterns', list(request.exclude or []))},
        'coverage': _dossier_coverage(sets, records, verification, rows),
        'description': describe(sets, records),
        'claim_counts': _counts(rows),
        'claims': rows,
        'withheld_claims': withheld,
        'questions': questions_of(records, sets),
        'tasks': tasks,
        'legacy_tasks': tasks,
        'compatibility': {'source': 'legacy' if run else 'native', 'legacy_tasks_require_revalidation': bool(tasks)},
        'do_not': ['لا تعتمد هذا المخرج كمراجعة أمنية أو شهادة جاهزية إنتاج.',
                   'لا تقرأ ترتيب الانتباه كترتيب خطورة؛ هو اصطلاح معلن للأولوية في القراءة.',
                   'لا تعتبر غياب نتيجة دليلًا على سلامة؛ الغياب يعني عدم الفحص ما لم يُصرَّح ببحث عن الغياب.']
        if request.language == 'ar' else
        ['Do not treat this as a security review or a production-readiness certificate.',
         'Do not read the attention order as a severity order; it is a declared reading convention.',
         'Do not read an absent finding as safety; absence means unexamined unless an absence search is declared.'],
        'artifacts': ['README.md'],
    }


def _dossier_coverage(sets, records, verification, rows):
    """What was examined, with how many claims execution confirmed and how much of the code the tests ran."""
    return {**coverage_of(sets, records, verification),
            'runtime_confirmation': sum(1 for row in rows if 'test_evidence' in row['method'] or 'runtime_probe' in row['method']),
            'executed_verification': bool(verification and verification.get('executed')),
            'executed_coverage_percent': (verification or {}).get('overall_percent')}


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
