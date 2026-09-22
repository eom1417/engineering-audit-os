"""What each engine actually finds on cases where the answer is known.

Corroboration weights were chosen, not measured. This runs every engine over labelled cases and
reports, per engine and kind, whether the planted finding was found and how much else came with
it. It measures detection and volume; it does not claim the extra findings are wrong.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
CORPUS = ROOT / 'tests/fixtures/benchmarks/engines'
LOAD_CORPUS = ROOT / 'tests/fixtures/benchmarks/load'


def cases(corpus=None):
    corpus = Path(corpus or CORPUS)
    for path in sorted(corpus.iterdir()):
        truth = path / 'ground-truth.json'
        if truth.is_file():
            yield path, json.loads(truth.read_text(encoding='utf-8'))


def measure(workdir, corpus=None):
    from eaos.engines import analyze
    rows = []
    for path, truth in cases(corpus):
        manifest = analyze(path, Path(workdir) / path.name, exclude=['ground-truth.json'], formats=['python'])
        findings = manifest['findings']
        for planted in truth['planted']:
            engine, kind = planted['engine'], planted['kind']
            matched = [f for f in findings if f['engine'] == engine and f['kind'] == kind
                       and (planted.get('path') is None
                            or any(planted['path'] in str(site[0]) for site in f['sites']))]
            same_kind = [f for f in findings if f['kind'] == kind]
            rows.append({'case': truth['name'], 'planted': planted['id'], 'engine': engine, 'kind': kind,
                         'found': bool(matched),
                         'found_by_any_engine': sorted({f['engine'] for f in same_kind}),
                         'findings_of_this_kind': len(same_kind),
                         'findings_in_total': len(findings),
                         'why': planted['why']})
    return rows


def load_rows(workdir, corpus=None):
    """Each load case, run end to end: is the planted question answered, and how?"""
    from eaos.audit import run as run_audit
    from eaos.load_model import blockers
    rows = []
    for path, truth in cases(corpus or LOAD_CORPUS):
        out = Path(workdir) / ('load-' + path.name)
        # complexity_class is answered by an engine; without one the question is honestly
        # undetectable, and the case records that rather than being dropped.
        run_audit(path, out, language='en', engines=[])
        record = json.loads((out / 'load-model.json').read_text(encoding='utf-8'))
        found = {row['question'] for row in blockers(record)}
        for planted in truth['planted']:
            question = planted['question']
            answered = [entry for entry in record.get('entry_points', [])
                        if (entry.get('answers') or {}).get(question, {}).get('status') == 'answered']
            rows.append({'case': truth['name'], 'planted': planted['id'], 'question': question,
                         'answered': bool(answered),
                         'value': (answered[0]['answers'][question].get('value') if answered else None),
                         'became_a_blocker': question in found,
                         'entry_points': len(record.get('entry_points', [])),
                         'why': planted['why']})
    return rows


def summarise_load(rows):
    return {'cases': len({row['case'] for row in rows}), 'planted': len(rows),
            'answered': sum(1 for row in rows if row['answered']),
            'questions_covered': sorted({row['question'] for row in rows if row['answered']}),
            'limits': 'Answered means the question produced a value with evidence on a planted case. '
                      'It does not mean the value is right on code nobody planted.'}


def summarise(rows):
    by_engine = {}
    for row in rows:
        entry = by_engine.setdefault(row['engine'], {'planted': 0, 'found': 0, 'kinds': set()})
        entry['planted'] += 1
        entry['found'] += int(row['found'])
        entry['kinds'].add(row['kind'])
    return {'cases': len({row['case'] for row in rows}), 'planted': len(rows),
            'found': sum(1 for row in rows if row['found']),
            'by_engine': {name: {'planted': v['planted'], 'found': v['found'], 'kinds': sorted(v['kinds'])}
                          for name, v in sorted(by_engine.items())},
            'limits': 'Detection on planted cases, measured. The volume column is not a false-positive '
                      'count: an extra finding may be correct and simply unplanted.'}


def main(argv):
    import tempfile
    with tempfile.TemporaryDirectory() as workdir:
        rows = measure(workdir)
        load = load_rows(workdir) if LOAD_CORPUS.is_dir() else []
    result = {'rows': rows, 'summary': summarise(rows),
              'load_rows': load, 'load_summary': summarise_load(load) if load else None}
    if '--write' in argv:
        (ROOT / 'docs/engine-precision.json').write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result['summary'], ensure_ascii=False, indent=2))
    for row in rows:
        mark = 'found' if row['found'] else 'MISSED'
        print(f"  {mark:6s} {row['case']:18s} {row['engine']:10s} {row['kind']:20s} "
              f"of-this-kind={row['findings_of_this_kind']:3d} total={row['findings_in_total']:3d}")
    if result['load_summary']:
        print(json.dumps(result['load_summary'], ensure_ascii=False, indent=2))
        for row in result['load_rows']:
            mark = 'answered' if row['answered'] else 'UNANSWERED'
            print(f"  {mark:10s} {row['case']:28s} {row['question']:26s} "
                  f"value={row['value']} blocker={row['became_a_blocker']}")
    engines_ok = result['summary']['found'] == result['summary']['planted']
    load_ok = not result['load_summary'] or (result['load_summary']['answered']
                                             == result['load_summary']['planted'])
    return 0 if engines_ok and load_ok else 1


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
