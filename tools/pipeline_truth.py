"""The pipeline map against hand-written truth: recall and precision of stages, edges and router branches (F16).

The truth files are evaluations/pipelines/<name>.json, written by reading each project's code, never from the
detector's output: EAOS itself (source null: this repository) and public pipeline projects pinned to a commit and
cloned under $EAOS_DEV_HOME/pipelines (tools/dev_paths.py). apps.json says which product pipelines each app project of
the corpus holds (none): a product pipeline found there and not listed is an invention.

    python tools/pipeline_truth.py fetch             # clone each public project at its pinned commit
    python tools/pipeline_truth.py measure [NAME]    # write $EAOS_MEASURE/pipeline/<name>/measure.json and print it

A truth pipeline matches the detected pipelines whose entry or evidence lies in its anchor file. Stages are compared by
label inside matched pipelines, edges by their two labels, branches by (table, condition) over the whole project;
structural nodes (routers, forks, joins) are not stages. A detected stage or edge in no matched pipeline counts
against precision.
"""
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tools'))
import dev_paths  # noqa: E402

TRUTH = ROOT / 'evaluations/pipelines'
STRUCTURAL = ('router', 'fork', 'join', 'source', 'sink')
RECALL, PRECISION = 0.8, 0.9


def load(name):
    return json.loads((TRUTH / f'{name}.json').read_text(encoding='utf-8'))


def public():
    return [load(path.stem) for path in sorted(TRUTH.glob('*.json')) if path.stem not in ('eaos', 'apps')]


def where(spec):
    return ROOT if not spec.get('source') else dev_paths.PIPELINES / spec['source'].rstrip('/').rsplit('/', 1)[1].removesuffix('.git')


def checkout(spec):
    """The project's folder when it is at the pinned commit, else None (EAOS: this repository)."""
    folder = where(spec)
    if not spec.get('source'): return folder
    if not (folder / '.git').exists(): return None
    head = subprocess.run(['git', '-C', str(folder), 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
    return folder if head == spec['commit'] else None


def fetch():
    for spec in public():
        folder = where(spec)
        if not (folder / '.git').exists():
            folder.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(['git', 'clone', '--quiet', spec['source'], str(folder)], check=True)
        subprocess.run(['git', '-C', str(folder), 'fetch', '--quiet', 'origin', spec['commit']], check=False)
        subprocess.run(['git', '-C', str(folder), 'checkout', '--quiet', '--force', spec['commit']], check=True)
        print(f"{spec['name']}: {spec['commit'][:10]} in {folder}")


def apps():
    """(name, folder) of every app project of the corpus checked out on this machine."""
    record = json.loads((ROOT / 'docs/north-star.json').read_text(encoding='utf-8'))
    names = [spec['name'] for spec in record['corpus']] + [spec['name'] for spec in record.get('live_corpus') or []]
    return [(name, dev_paths.CORPUS / name) for name in names if (dev_paths.CORPUS / name).is_dir()]


def _norm(label):
    return ' '.join(str(label).lower().split())


def _anchors(pipeline):
    paths = {pipeline['entry'].get('path')} | {e.get('path') for e in pipeline.get('evidence') or []}
    paths |= {s['entry'].get('path') for s in pipeline['stages'][:1]}
    return {p for p in paths if p}


def _score(truth, found):
    hit = len(truth & found)
    return {'recall': round(hit / len(truth), 4) if truth else (1.0 if not found else 1.0),
            'precision': round(hit / len(found), 4) if found else (1.0 if not truth else 0.0),
            'truth': len(truth), 'found': len(found), 'matched': hit,
            'missed': sorted(map(str, truth - found))[:20], 'extra': sorted(map(str, found - truth))[:20]}


def compare(spec, record):
    """{stages, edges, branches: {recall, precision, truth, found, matched, missed, extra}} of one truth file."""
    truth_stages, truth_edges, truth_branches = set(), set(), set()
    found_stages, found_edges, found_branches = set(), set(), set()
    claimed = set()
    for pipe in spec['pipelines']:
        anchor = pipe['anchor']
        truth_stages |= {(anchor, _norm(s)) for s in pipe['stages']}
        truth_edges |= {(anchor, _norm(a), _norm(b)) for a, b in pipe['edges']}
        truth_branches |= {(router['table'], _norm(b)) for router in pipe.get('routers') or [] for b in router['branches']}
        for detected in record['pipelines']:
            if anchor not in _anchors(detected): continue
            claimed.add(detected['id'])
            labels = {s['id']: s['label'] for s in detected['stages']}
            real = {s['id'] for s in detected['stages'] if s['kind'] not in STRUCTURAL}
            found_stages |= {(anchor, _norm(labels[i])) for i in real}
            found_edges |= {(anchor, _norm(labels[e['from']]), _norm(labels[e['to']])) for e in detected['edges']
                            if e['from'] in real and e['to'] in real}
    for detected in record['pipelines']:
        found_branches |= {(router.get('table') or router['on'], _norm(b['condition'])) for router in detected['routers'] for b in router['branches']}
        if detected['id'] in claimed: continue
        labels = {s['id']: s['label'] for s in detected['stages']}
        real = {s['id'] for s in detected['stages'] if s['kind'] not in STRUCTURAL}
        found_stages |= {(f"unmatched:{detected['id']}", _norm(labels[i])) for i in real}
        found_edges |= {(f"unmatched:{detected['id']}", _norm(labels[e['from']]), _norm(labels[e['to']])) for e in detected['edges']
                        if e['from'] in real and e['to'] in real}
    return {'stages': _score(truth_stages, found_stages), 'edges': _score(truth_edges, found_edges),
            'branches': _score(truth_branches, found_branches)}


def _says(line, words):
    line = line.lower()
    return any(word and word.lower() in line for word in words)


def verify(project, record):
    """Every stage, edge and branch points at a line of the project that names it: [problems] (empty when all hold)."""
    project, problems, cache = Path(project), [], {}

    def text(path, line):
        if path not in cache:
            try: cache[path] = (project / path).read_text(encoding='utf-8', errors='replace').splitlines()
            except OSError: cache[path] = None
        lines = cache[path]
        if lines is None: return None
        return lines[line - 1] if isinstance(line, int) and 0 < line <= len(lines) else None

    for pipeline in record['pipelines']:
        labels = {s['id']: s['label'] for s in pipeline['stages']}
        for stage in pipeline['stages']:
            line = text(stage['entry'].get('path'), stage['entry'].get('line'))
            symbol = (stage.get('symbol') or '').rsplit('.', 1)[-1]
            words = [stage['label'], symbol, stage['label'].replace(' ', '_'), stage['label'].split()[0] if stage['label'].split() else '']
            words += {'source': ['entry', 'start'], 'sink': ['finish', 'end']}.get(stage['kind'], [])
            if line is None or not _says(line, words):
                problems.append(f"{pipeline['id']}: stage {stage['label']} at {stage['entry']} does not name it")
        for edge in pipeline['edges']:
            line = text(edge['evidence'].get('path'), edge['evidence'].get('line'))
            ends = [s for s in pipeline['stages'] if s['id'] in (edge['from'], edge['to'])]
            words = [labels.get(edge['from'], ''), labels.get(edge['to'], ''), *edge['data']['names'], *[s.get('variable') or '' for s in ends]]
            words += [w.split('[')[-1].strip("']\"") for w in edge['data']['names']]
            if line is None or not _says(line, [w for w in words if w] + [w.split()[0] for w in words if w and w.split()]):
                problems.append(f"{pipeline['id']}: edge {edge['id']} at {edge['evidence']} names neither end")
        for router in pipeline['routers']:
            for branch in router['branches']:
                line = text(branch['evidence'].get('path'), branch['evidence'].get('line'))
                condition = branch['condition'].replace('returns ', '').strip("'\"")
                if branch['condition'] != 'else' and (line is None or not _says(line, [condition, condition.rsplit('.', 1)[-1]])):
                    problems.append(f"{pipeline['id']}: branch {branch['condition']} at {branch['evidence']} does not name it")
    return problems


def measure(name):
    """Measure one truth file (or the apps) and write $EAOS_MEASURE/pipeline/<name>/measure.json."""
    from eaos.facts import pipeline
    out = {'name': name, 'at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
           'eaos_commit': subprocess.run(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()}
    if name == 'apps':
        expected = load('apps')['projects']
        rows = {}
        for app, folder in apps():
            began = time.monotonic()
            record = pipeline.scan(folder)
            product = sorted(p['title'] for p in record['pipelines'] if p['role'] == 'product')
            problems = verify(folder, record)
            rows[app] = {'product': product, 'expected': expected.get(app, {}).get('product', []),
                         'tooling': sorted(p['title'] for p in record['pipelines'] if p['role'] == 'tooling'),
                         'detected': record['detected'], 'evidence_problems': problems[:20],
                         'holds': product == sorted(expected.get(app, {}).get('product', [])) and not problems,
                         'seconds': round(time.monotonic() - began, 2)}
        out.update(kind='apps', projects=rows, checks=[{'id': f'{app}: no invented pipeline', 'holds': row['holds']} for app, row in rows.items()])
    else:
        spec = load(name)
        folder = checkout(spec)
        out.update(kind=spec['kind'], source=spec.get('source'), commit=spec.get('commit'))
        if folder is None:
            out.update(error=f'not cloned at {spec["commit"]}: python tools/pipeline_truth.py fetch', checks=[])
        else:
            began = time.monotonic()
            record = pipeline.scan(folder)
            scores = compare(spec, record)
            problems = verify(folder, record)
            out.update(scores=scores, evidence_problems=problems[:20], seconds=round(time.monotonic() - began, 2),
                       detected=record['detected'], pipelines=[{'id': p['id'], 'kind': p['kind'], 'role': p['role'],
                                                                 'stages': len(p['stages']), 'edges': len(p['edges'])} for p in record['pipelines']],
                       checks=[{'id': f'{part} {metric}', 'value': scores[part][metric], 'min': floor,
                                'holds': scores[part][metric] >= floor}
                               for part in ('stages', 'edges', 'branches') for metric, floor in (('recall', RECALL), ('precision', PRECISION))]
                       + [{'id': 'evidence names every element', 'holds': not problems}])
    folder = dev_paths.MEASURE / 'pipeline' / name
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'measure.json').write_text(json.dumps(out, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    return out


def f16_value(reports=None):
    """F16: the truth checks that hold ÷ the checks, over every truth file and the apps; None until measured."""
    folder = Path(reports or dev_paths.MEASURE) / 'pipeline'
    names = ['eaos', *[spec['name'] for spec in public()], 'apps']
    rows, missing = [], []
    for name in names:
        path = folder / name / 'measure.json'
        if not path.is_file(): missing.append(name); continue
        data = json.loads(path.read_text(encoding='utf-8'))
        if data.get('error') or not data.get('checks'): missing.append(name); continue
        rows += [(name, check) for check in data['checks']]
    if not rows: return None, 'not measured yet: python tools/pipeline_truth.py measure'
    if missing: return 0.0, f"pipeline truth not measured for {', '.join(missing)} (python tools/pipeline_truth.py measure)"
    held = [row for row in rows if row[1]['holds']]
    failing = [f"{name}: {check['id']}" + (f" {check['value']}" if 'value' in check else '') for name, check in rows if not check['holds']]
    return (round(len(held) / len(rows), 3),
            f'pipeline map truth checks holding: {len(held)}/{len(rows)} over {len(names)} truth files'
            + (f"; failing: {'; '.join(failing[:6])}" if failing else ''))


def main(argv):
    if argv[:1] == ['fetch']: fetch(); return 0
    if argv[:1] == ['measure']:
        names = argv[1:] or ['eaos', *[spec['name'] for spec in public()], 'apps']
        for name in names:
            data = measure(name)
            if 'scores' in data:
                print(name, {part: (s['recall'], s['precision']) for part, s in data['scores'].items()},
                      f"evidence problems: {len(data['evidence_problems'])}", f"{data['seconds']} s")
            else:
                print(name, data.get('error') or {app: row['holds'] for app, row in data.get('projects', {}).items()})
        print('F16', f16_value())
        return 0
    print(__doc__)
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
