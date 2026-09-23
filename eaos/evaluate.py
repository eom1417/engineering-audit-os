"""Measured evaluation against known ground truth, plus a baseline to compare against.

Without this, every quality statement about the tool is an opinion. The harness answers three
questions with numbers: what does it find, what does it invent, and what does it cost.
"""
import json
from pathlib import Path
import re
import shutil
import tempfile
import time
from .apidiff import run as api_diff
from .compose import Document
from .dossier import assemble
from .facts.run import collect
from .plan import build as build_plan
from .verify import run as verify_run
from .workspace import write

CONSTANT = re.compile(r'^\s*(?:export\s+)?(?:const\s+)?(?P<name>[A-Z][A-Z0-9_]{2,})\s*=', re.M)


def baseline(repo):
    """What a careful grep gets you without the framework: repeated upper-case names, nothing else."""
    definitions = {}
    for path in sorted(Path(repo).rglob('*')):
        if not path.is_file() or path.suffix not in {'.py', '.ts', '.js', '.go'}: continue
        try: text = path.read_text(encoding='utf-8')
        except (OSError, UnicodeError): continue
        for match in CONSTANT.finditer(text):
            definitions.setdefault(match.group('name'), []).append(path.relative_to(repo).as_posix())
    return [f'{name} is defined in {len(paths)} places ({", ".join(sorted(paths))})'
            for name, paths in sorted(definitions.items()) if len(paths) > 1]


def score(statements, truth):
    planted = truth.get('planted', [])
    detected, missed = [], []
    for item in planted:
        needle = item['match'].lower()
        hit = next((statement for statement in statements if needle in statement.lower()), None)
        (detected if hit else missed).append({**item, 'matched_statement': hit})
    forbidden = [statement for statement in statements
                 if any(pattern.lower() in statement.lower() for pattern in truth.get('must_not_claim', []))]
    true_positives = len(detected)
    adjudications = truth.get('adjudications', {})
    judgments = [{'statement': statement, 'verdict': adjudications.get(statement, 'not_adjudicated')} for statement in statements]
    correct = sum(row['verdict'] == 'correct' for row in judgments)
    incorrect = sum(row['verdict'] == 'incorrect' for row in judgments)
    return {'judgments': judgments, 'not_adjudicated': sum(row['verdict'] == 'not_adjudicated' for row in judgments),
            'adjudicated_precision': round(correct / (correct + incorrect), 3) if correct + incorrect else None,
            'measurement': 'substring detection only; not semantic accuracy', 'planted': len(planted), 'detected': true_positives, 'missed': missed, 'false_positives': forbidden,
            'recall': round(true_positives / len(planted), 3) if planted else None,
            'precision': None}


def plan_quality(out, detected_count):
    """Detection is half the job: was each finding turned into work someone can pick up?"""
    plan_path = Path(out) / 'plan.json'
    if not plan_path.is_file(): return {'cards': 0, 'complete_cards': 0, 'runnable_acceptance': 0}
    tasks = json.loads(plan_path.read_text())['tasks']
    complete = [task for task in tasks
                if task['paths'] is not None and task['options'] and task['acceptance']
                and task['rollback'] and task['effort'] and task['blast_radius']]
    runnable = [task for task in tasks if task.get('decision', {}).get('readiness') == 'ready' and task.get('verify_command')]
    return {'cards': len(tasks), 'complete_cards': len(complete), 'runnable_acceptance': len(runnable),
            'cards_for_detected': min(len(tasks), detected_count or 0)}


def evaluate_api_break(case, workspace, truth):
    outputs = []
    for side in ['before', 'after']:
        repo = Path(workspace) / (case.name + '-' + side)
        shutil.copytree(case / side, repo)
        out = Path(workspace) / (case.name + '-' + side + '-out')
        collect(repo, out, ['syntax'])
        outputs.append(out)
    started = time.monotonic()
    result = api_diff(*outputs)
    statements = [f"{row.split('::')[-1]} broke for consumers of {row.split('::')[0]}" for row in result['breaking']]
    return {'case': case.name, 'seconds': round(time.monotonic() - started, 2), 'model_calls': 0,
            'claims': len(statements), 'framework': score(statements, truth),
            'baseline': score([], truth), 'confirmed_claims': len(statements), 'runtime_confirmed': 0,
            'output_spec_violations': [], 'plan': {'cards': 0, 'complete_cards': 0, 'runnable_acceptance': 0},
            'mode': 'api_break'}


def evaluate_case(case, workspace, execute=True):
    truth = json.loads((case / 'ground-truth.json').read_text())
    if truth.get('kind') == 'api_break': return evaluate_api_break(case, workspace, truth)
    repo = Path(workspace) / case.name
    shutil.copytree(case, repo)
    (repo / 'ground-truth.json').unlink()
    out = Path(workspace) / (case.name + '-out')
    started = time.monotonic()
    if truth.get('requires_execution') and execute:
        verify_run(repo, out, execute=True, timeout=300)
    result = assemble(repo, out)
    dossier = json.loads((out / 'dossier.json').read_text())
    statements = [claim['statement'] for claim in dossier['claims']]
    build_plan(repo, out)
    elapsed = round(time.monotonic() - started, 2)
    framework = score(statements, truth)
    reference = score(baseline(repo), truth)
    return {'case': case.name, 'seconds': elapsed, 'model_calls': result['model_calls'],
            'claims': len(statements), 'framework': framework, 'baseline': reference,
            'confirmed_claims': sum(1 for claim in dossier['claims'] if claim['confidence'] == 'CONFIRMED'),
            'runtime_confirmed': dossier['coverage'].get('runtime_confirmation', 0),
            'plan': plan_quality(out, framework.get('detected', 0)),
            'output_spec_violations': result['output_spec_violations'], 'mode': 'dossier'}


def document(results, language):
    heading = 'تقييم مُقاس على حالات معروفة' if language == 'ar' else 'Measured evaluation on known cases'
    doc = Document(heading, language, budget_lines=120)
    totals = results['totals']
    doc.header([f"cases {totals['cases']} · planted {totals['planted']} · detected {totals['detected']} · "
                f"false positives {totals['false_positives']} · model calls {totals['model_calls']}",
                'التقييم يغطي المسار الحتمي فقط؛ لم يُشغَّل نموذج حي في هذه الجولة.' if language == 'ar'
                else 'This covers the deterministic path only; no live model was run in this round.'])
    doc.section('النتائج لكل حالة' if language == 'ar' else 'Per case')
    doc.table(['case', 'planted', 'detected', 'missed', 'false positives', 'baseline', 'cards', 'runnable', 'seconds'],
              [[row['case'], row['framework']['planted'], row['framework']['detected'],
                len(row['framework']['missed']), len(row['framework']['false_positives']),
                row['baseline']['detected'], row.get('plan', {}).get('cards', 0),
                row.get('plan', {}).get('runnable_acceptance', 0), row['seconds']] for row in results['cases']])
    doc.section('ما لم يُقس' if language == 'ar' else 'Not measured')
    doc.bullets(results['not_measured'])
    return doc


def run(corpus, out, language='ar', execute=True):
    corpus, out = Path(corpus).resolve(), Path(out).resolve()
    cases = sorted(path for path in corpus.iterdir() if (path / 'ground-truth.json').is_file())
    if not cases: raise ValueError('No benchmark cases with ground-truth.json under ' + str(corpus))
    rows = []
    with tempfile.TemporaryDirectory() as workspace:
        for case in cases: rows.append(evaluate_case(case, workspace, execute))
    totals = {'cases': len(rows), 'planted': sum(row['framework']['planted'] for row in rows),
              'detected': sum(row['framework']['detected'] for row in rows),
              'false_positives': sum(len(row['framework']['false_positives']) for row in rows),
              'baseline_detected': sum(row['baseline']['detected'] for row in rows),
              'baseline_false_positives': sum(len(row['baseline']['false_positives']) for row in rows),
              'model_calls': sum(row['model_calls'] if isinstance(row['model_calls'], int) else 0 for row in rows),
              'cards': sum(row.get('plan', {}).get('cards', 0) for row in rows),
              'complete_cards': sum(row.get('plan', {}).get('complete_cards', 0) for row in rows),
              'runnable_acceptance': sum(row.get('plan', {}).get('runnable_acceptance', 0) for row in rows),
              'seconds': round(sum(row['seconds'] for row in rows), 2)}
    totals['recall'] = round(totals['detected'] / totals['planted'], 3) if totals['planted'] else None
    totals['baseline_recall'] = round(totals['baseline_detected'] / totals['planted'], 3) if totals['planted'] else None
    results = {'corpus': str(corpus), 'cases': rows, 'totals': totals,
               'not_measured': [
                   'Live-model diagnosis quality: no provider was configured in this round.',
                   'Plan usefulness: card completeness is measured mechanically; whether a card is genuinely useful '
                   'to an engineer is not, and needs a blind human rating.',
                   'Large real-world repositories: measured separately for scale, without ground truth.',
                   'False negatives outside the planted set: unknown by construction.']}
    out.mkdir(parents=True, exist_ok=True)
    write(out / 'eval.json', results)
    (out / 'EVAL.md').write_text(document(results, language).render(), encoding='utf-8')
    return {'out': str(out), 'totals': totals,
            'status': 'MEASURED' if totals['planted'] else 'NO_GROUND_TRUTH',
            'limits': 'Measured only on planted cases. A high score here is not evidence of quality on unseen repositories.'}
