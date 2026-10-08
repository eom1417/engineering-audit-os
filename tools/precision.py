"""The labelled precision set: how much of what each EAOS detector shows is true, and how much it misses.

Truth is written by hand from the source, before the project's report is read, into $EAOS_TRUTH (default
~/.eaos/dev/truth, outside the repository and the projects): `<project>*.json`, items of a class with
`file:line` sites and a one-line reason, and scopes in which a class was labelled exhaustively. Seeded
mutations (tools/precision_seeds.py) are planted into copies, never into the originals, and carry their own
exact truth. Each detector's output (cards, and the facts shown as data models and data owners) is matched to
the sites; precision and recall are measured against a declared bar, and a detector under its bar is hidden:
eaos/data/detector-verdicts.json is read by the product (eaos/claims.withhold).

    python tools/precision.py seed             # copy the four projects and plant the mutations
    python tools/precision.py seal             # record the digest of every truth file (commit it before scoring)
    python tools/precision.py audit [name ...] # audit originals and seeded copies (long: run it as a unit)
    python tools/precision.py score [--write]  # match, measure, and write docs/engine-precision.json + the verdicts

Matching. A site is (path, first line, last line); a missing line means the whole file. For a class whose items
are groups (duplication, overlap, multiple writers, cycles), an output matches an item when it touches at least
two of the item's sites and at least half of its own sites lie on the item. For the other classes, any overlap.
An output is a true positive when it matches a positive of its detector's class; a false positive when it
matches a negative, or touches a file in which that class was labelled exhaustively without matching a
positive; otherwise it is not judged (and counted as such).
"""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tools'))
import dev_paths  # noqa: E402
import precision_seeds  # noqa: E402

RECORD = ROOT / 'docs/engine-precision.json'
VERDICTS = ROOT / 'eaos/data/detector-verdicts.json'
SEAL = ROOT / 'docs/precision-truth-seal.json'
TRUTH = dev_paths.TRUTH
WORK = dev_paths.MEASURE / 'precision'
ENGINES = ['codegraph', 'enola', 'jscpd', 'reforge', 'syft', 'osv-scanner', 'scc', 'semgrep', 'trivy', 'checkov',
           'dependency-cruiser', 'sqlfluff', 'spectral', 'oasdiff', 'gitnexus']
# The four projects of the set, by the name their truth files carry. Holdout projects are never used.
PROJECTS = {'FleetManageWeb': {'source': dev_paths.CORPUS / 'FleetManageWeb', 'language': 'typescript', 'seed_base': 'src/eaos-seed'},
            'finance-os-a0192b7b': {'source': dev_paths.CORPUS / 'finance-os-a0192b7b', 'language': 'typescript',
                                    'seed_base': 'src/eaos-seed', 'sql': 'supabase/migrations/20990101000000_eaos_seed.sql'},
            'chief-ops': {'source': dev_paths.CORPUS / 'chief-ops', 'language': 'typescript', 'seed_base': 'app/src/eaos-seed'},
            'eaos': {'source': dev_paths.MEASURE / 'self-truth-tree', 'language': 'python', 'seed_base': 'eaos_seed'}}
MIN_ITEMS = 150
GROUPS = {'duplication', 'overlap', 'multiple_writers', 'cycle'}
# Every detector whose output reaches a reader, with the labelled class it is judged against. A detector with
# no class cannot be measured yet, so it is hidden until labels exist for it.
DETECTORS = {
    'structural_duplicate': 'duplication', 'sequence_duplicate': 'duplication', 'duplicated_rule': 'duplication',
    'engine_cluster:literal_duplication': 'duplication', 'engine_cluster:duplication': 'duplication',
    'dead_code': 'dead_code', 'dead_code_review': 'dead_code', 'engine_cluster:dead_code': 'dead_code',
    'broken_code': 'broken_code',
    'hotspot': 'complexity', 'engine_cluster:complexity': 'complexity',
    'mutable_global': 'mutable_state',
    'external_write': 'multiple_writers', 'data_owners': 'multiple_writers',
    'data_model': 'data_model', 'data_model:runtime': 'data_model', 'data_table': 'data_model',
    'redundant_work': 'redundant_work',
    'access_gap_no_rls': 'access_gap', 'access_gap_open_write': 'access_gap', 'engine_cluster:secret': 'access_gap',
    'import_cycle': 'cycle', 'engine_cluster:cycle': 'cycle',
    'vulnerable_dependency': 'vulnerable_dependency',
    'engine_cluster:coupling': None, 'engine_cluster:dataflow': None, 'engine_cluster:surface': None,
    'engine_cluster:test_quality': None, 'engine_cluster:naming': None, 'engine_cluster:boundary': None,
    'engine_cluster:misconfiguration': None, 'engine_cluster:sql_quality': None, 'engine_cluster:api_contract': None,
    'cochange': None, 'trace_gap': None, 'policy': None, 'load_blocker': None, 'untested': None, 'unattributed': None,
}
# The declared bar: precision on judged output, recall on the planted targets (or on the labels when nothing
# was planted for the detector), and enough judged output for the precision to mean something.
BAR = {'precision': 0.8, 'recall': 0.5, 'judged': 5}


# ---------------------------------------------------------------- truth

def truth_files(where=None):
    where = Path(where or TRUTH)
    return sorted(p for p in where.glob('*.json')) if where.is_dir() else []


def load_truth(where=None):
    """{project: {'items': [...], 'scopes': [...], 'files': [...]}} from every truth file of the four projects."""
    out = {}
    for path in truth_files(where):
        data = json.loads(path.read_text(encoding='utf-8'))
        name = data.get('project')
        if name not in PROJECTS: continue
        entry = out.setdefault(name, {'items': [], 'scopes': [], 'files': []})
        entry['items'] += data.get('items') or []
        entry['scopes'] += data.get('scopes') or []
        entry['files'].append({'file': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                               'labelled_at': data.get('labelled_at'), 'commit': data.get('commit'),
                               'report_read_before_labelling': data.get('report_read_before_labelling')})
    return out


def seeded_truth(name):
    path = TRUTH / 'seeded' / f'{name}.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else None


# ---------------------------------------------------------------- seeds

def seed(names=None):
    """Copy each project (without .git and node_modules) and plant the mutations; write the seeded truth."""
    (TRUTH / 'seeded').mkdir(parents=True, exist_ok=True)
    for name, spec in PROJECTS.items():
        if names and name not in names: continue
        copy = WORK / 'seeded' / name
        if copy.exists(): shutil.rmtree(copy)
        shutil.copytree(spec['source'], copy, ignore=shutil.ignore_patterns('.git', 'node_modules'))
        maker = precision_seeds.typescript_files if spec['language'] == 'typescript' else precision_seeds.python_files
        files = maker(spec['seed_base'])
        if spec.get('sql'): files[spec['sql']] = precision_seeds.SQL_SEED
        for rel, text in files.items():
            if (spec['source'] / rel).exists(): raise SystemExit(f'{name}: {rel} exists in the original; refusing to overwrite it')
            (copy / rel).parent.mkdir(parents=True, exist_ok=True)
            (copy / rel).write_text(text, encoding='utf-8')
        planted = {k: v for k, v in files.items() if k != spec.get('sql')}
        items, scopes = precision_seeds.items(planted, spec['language'], spec.get('sql'), files.get(spec.get('sql')))
        for number, item in enumerate(items, start=1): item['id'] = f'SEED-{name}-{number:03d}'
        (TRUTH / 'seeded' / f'{name}.json').write_text(json.dumps(
            {'project': name, 'seeded_copy': str(copy), 'files': sorted(files), 'items': items, 'scopes': scopes},
            indent=2) + '\n', encoding='utf-8')
        print(f'{name}: {len(files)} planted files, {len(items)} seeded items -> {copy}')


def seal():
    rows = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in truth_files()}
    rows.update({'seeded/' + path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                 for path in truth_files(TRUTH / 'seeded')})
    import datetime
    SEAL.write_text(json.dumps({'sealed_at': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'),
                                'why': 'The truth is fixed before any report of the projects is read; score checks it is unchanged.',
                                'files': rows}, indent=2) + '\n', encoding='utf-8')
    print(f'sealed {len(rows)} truth files in {SEAL.relative_to(ROOT)}')


# ---------------------------------------------------------------- audits

def tool_digest():
    """The audit's input from EAOS: its code, minus the verdict file the scoring writes (it changes no output)."""
    digest = hashlib.sha256()
    for path in sorted((ROOT / 'eaos').rglob('*')):
        if path.is_file() and '__pycache__' not in path.parts and path != VERDICTS:
            digest.update(path.relative_to(ROOT).as_posix().encode()); digest.update(path.read_bytes())
    return digest.hexdigest()


def reports():
    """(name, kind, target, report directory) for every original and seeded copy."""
    for name, spec in PROJECTS.items():
        yield name, 'original', spec['source'], WORK / 'reports' / name
        yield name, 'seeded', WORK / 'seeded' / name, WORK / 'reports' / (name + '.seeded')


def audit(names=None):
    for name, kind, target, out in reports():
        if names and name not in names and f'{name}.{kind}' not in names: continue
        key = {'tool': tool_digest(), 'engines': ENGINES, 'target': str(target),
               'seed': (seeded_truth(name) or {}).get('files') if kind == 'seeded' else None}
        stamp = out / '.precision.json'
        if stamp.is_file() and json.loads(stamp.read_text()).get('key') == key:
            print(f'{name} ({kind}): report is current'); continue
        if out.exists(): shutil.rmtree(out)
        print(f'{name} ({kind}): auditing {target}', flush=True)
        done = subprocess.run([sys.executable, '-m', 'eaos', 'audit', str(target), '--out', str(out), '--skip', 'site',
                               '--lang', 'en', '--engines', *ENGINES], cwd=ROOT, capture_output=True, text=True)
        out.mkdir(parents=True, exist_ok=True)
        (out / '.precision.log').write_text(done.stdout[-20000:] + '\n' + done.stderr[-20000:], encoding='utf-8')
        stamp.write_text(json.dumps({'key': key, 'exit': done.returncode}))
        print(f'{name} ({kind}): exit {done.returncode}', flush=True)


# ---------------------------------------------------------------- outputs

def as_site(raw):
    if isinstance(raw, dict):
        path = raw.get('path') or raw.get('file')
        start = raw.get('start_line') or raw.get('line') or raw.get('start')
        end = raw.get('end_line') or raw.get('end') or start
    elif isinstance(raw, (list, tuple)) and raw and isinstance(raw[0], str):
        path = raw[0]
        start = raw[1] if len(raw) > 1 and isinstance(raw[1], int) else None
        end = raw[2] if len(raw) > 2 and isinstance(raw[2], int) else start
    elif isinstance(raw, str):
        path, start, end = raw, None, None
    else:
        return None
    return (path, start, end) if path else None


def fact_sites(fact):
    value, location = fact.get('value') or {}, fact.get('location') or {}
    sites = [site for key in ('occurrences', 'definitions', 'sites') for raw in (value.get(key) or [])
             for site in [as_site(raw)] if site]
    if isinstance(value.get('members'), list): sites += [site for raw in value['members'] for site in [as_site(raw)] if site]
    if not sites and location.get('path'):
        sites.append((location['path'], location.get('start_line'), location.get('end_line') or location.get('start_line')))
    return sites


class Paths:
    """Report paths made relative to the audited root, whatever form an engine wrote them in."""

    def __init__(self, root):
        self.root, self.cache = Path(root).resolve(), {}

    def __call__(self, path):
        if path in self.cache: return self.cache[path]
        found = str(path).replace('\\', '/').removeprefix('./')
        if found.startswith('/'):
            try: found = Path(found).resolve().relative_to(self.root).as_posix()
            except ValueError:
                parts = Path(found).parts
                found = next((Path(*parts[i:]).as_posix() for i in range(1, len(parts)) if (self.root / Path(*parts[i:])).exists()), found)
        self.cache[path] = found
        return found


def outputs(out, root):
    """Every output a reader sees, by detector: cards (shown or withheld) and the data-model and data-owner facts."""
    from eaos.claims import detector_of
    from eaos.indicators import facts, load
    from eaos.facts.run import read_available
    from eaos.sustainability import writers
    rel = Paths(root)
    fix = lambda sites: [(rel(p), s, e) for p, s, e in sites]
    index = {row['id']: row for row in facts(out) if row.get('id')}
    dossier = load(out, 'dossier.json', {}) or {}
    rows = []
    for claim in (dossier.get('claims') or []) + (dossier.get('withheld_claims') or []):
        sites = [site for fid in claim.get('fact_ids') or [] if fid in index for site in fact_sites(index[fid])]
        params = (claim.get('render') or {}).get('params') or {}
        if not sites and params.get('path'): sites = [(params['path'], params.get('line'), params.get('line'))]
        row = {'detector': detector_of(claim), 'ref': claim['id'], 'statement': claim['statement'][:200], 'sites': fix(sites)}
        if row['detector'] == 'vulnerable_dependency': row['subject'] = f"{params.get('package')}@{params.get('installed')}"
        rows.append(row)
    for name, detector in (('domain', None), ('runtime', 'data_model:runtime')):
        for fact in (load(out, f'facts/{name}.json', {}) or {}).get('facts') or []:
            if fact.get('kind') not in ('data_model', 'data_table'): continue
            kind = detector or fact['kind']
            rows.append({'detector': kind, 'ref': fact['id'], 'statement': str((fact.get('value') or {}).get('name')),
                         'sites': fix(fact_sites({'location': fact.get('location')}))})
    for key, paths in writers(read_available(out)).items():
        rows.append({'detector': 'data_owners', 'ref': str(key), 'statement': f'{key} written from {len(paths)} files',
                     'sites': fix([(p, None, None) for p in paths])})
    return rows


# ---------------------------------------------------------------- matching

def touches(a, b):
    if a[0] != b[0]: return False
    if a[1] is None or b[1] is None: return True
    return a[1] <= (b[2] or b[1]) and b[1] <= (a[2] or a[1])


def item_sites(item):
    return [(s['path'], s.get('start'), s.get('end')) for s in item.get('sites') or []]


def matches(output, item, cls):
    if cls == 'vulnerable_dependency' and output.get('subject'):
        return output['subject'].lower() in str(item.get('subject', '')).lower()
    sites, mine = item_sites(item), output['sites']
    if cls in GROUPS:
        hit = {i for i, site in enumerate(sites) if any(touches(o, site) for o in mine)}
        on = sum(1 for o in mine if any(touches(o, site) for site in sites))
        return len(hit) >= 2 and 2 * on >= len(mine)
    return any(touches(o, site) for o in mine for site in sites)


def in_scope(output, cls, scopes):
    paths = [p for scope in scopes if scope.get('class') == cls for p in scope.get('paths') or []]
    return any(o[0] == p or (p.endswith('/') and o[0].startswith(p)) for o in output['sites'] for p in paths)


def judge(output, items, scopes):
    """('tp' | 'fp' | None, matched positive ids)."""
    cls = DETECTORS.get(output['detector'])
    if cls is None: return None, []
    mine = [item for item in items if item['class'] == cls]
    hit = [item['id'] for item in mine if item['label'] == 'positive' and matches(output, item, cls)]
    if hit: return 'tp', hit
    if any(item['label'] == 'negative' and matches(output, item, cls) for item in mine): return 'fp', []
    if in_scope(output, cls, scopes): return 'fp', []
    return None, []


# ---------------------------------------------------------------- scoring

def ratio(a, b): return round(a / b, 3) if b else None


def score(truth=None, report_dirs=None):
    """The per-detector table. `report_dirs` maps (name, kind) to a report directory (tests pass their own)."""
    truth = truth if truth is not None else load_truth()
    blank = lambda: {'tp': 0, 'fp': 0, 'unjudged': 0, 'outputs': 0, 'targets': 0, 'targets_found': 0,
                     'positives': 0, 'positives_found': 0, 'false_examples': [], 'by_project': {}}
    stats = {d: blank() for d in DETECTORS}
    found_by_class = {}
    for name, kind, target, out in reports():
        out = (report_dirs or {}).get((name, kind), out)
        if not (Path(out) / 'dossier.json').is_file(): continue
        rows = outputs(out, target)
        if kind == 'original':
            items, scopes = (truth.get(name) or {}).get('items', []), (truth.get(name) or {}).get('scopes', [])
        else:
            seeded = seeded_truth(name) or {}
            items, scopes, planted = seeded.get('items', []), seeded.get('scopes', []), set(seeded.get('files') or [])
            rows = [row for row in rows if any(site[0] in planted for site in row['sites'])]
        found = {}
        for row in rows:
            entry = stats.setdefault(row['detector'], blank())
            entry['outputs'] += 1
            verdict, hit = judge(row, items, scopes)
            entry['tp' if verdict == 'tp' else 'fp' if verdict == 'fp' else 'unjudged'] += 1
            per = entry['by_project'].setdefault(f'{name}:{kind}', {'tp': 0, 'fp': 0, 'unjudged': 0})
            per['tp' if verdict == 'tp' else 'fp' if verdict == 'fp' else 'unjudged'] += 1
            if verdict == 'fp' and len(entry['false_examples']) < 5:
                entry['false_examples'].append(f"{name}: {row['statement'][:140]}")
            for item_id in hit: found.setdefault(row['detector'], set()).add(item_id)
        for detector, cls in DETECTORS.items():
            if cls is None: continue
            positives = [item for item in items if item['class'] == cls and item['label'] == 'positive']
            got = found.get(detector, set())
            if kind == 'seeded':
                targets = [item for item in positives if detector in (item.get('detectors') or [])]
                stats[detector]['targets'] += len(targets)
                stats[detector]['targets_found'] += sum(item['id'] in got for item in targets)
            else:
                stats[detector]['positives'] += len(positives)
                stats[detector]['positives_found'] += sum(item['id'] in got for item in positives)
                found_by_class.setdefault(cls, set()).update(got)
    rows = []
    for detector, entry in stats.items():
        cls = DETECTORS.get(detector)
        judged = entry['tp'] + entry['fp']
        precision = ratio(entry['tp'], judged)
        recall_targets, recall_labels = ratio(entry['targets_found'], entry['targets']), ratio(entry['positives_found'], entry['positives'])
        recall = recall_targets if entry['targets'] else recall_labels
        if cls is None:
            status, why = 'not_measured', 'no labelled class for this detector yet'
        elif not entry['outputs']:
            status, why = 'not_measured', 'it produced no output on the set'
        elif judged < BAR['judged']:
            status, why = 'not_measured', f"only {judged} judged outputs (bar {BAR['judged']})"
        elif precision < BAR['precision']:
            status, why = 'below_bar', f"precision {precision} < {BAR['precision']} on {judged} judged outputs"
        elif recall is None or recall < BAR['recall']:
            status, why = 'below_bar', f"recall {recall} < {BAR['recall']}"
        else:
            status, why = 'meets_bar', f"precision {precision} on {judged} judged, recall {recall}"
        rows.append({'detector': detector, 'class': cls, 'status': status, 'shown': status == 'meets_bar', 'why': why,
                     'outputs': entry['outputs'], 'judged': judged, 'true_positives': entry['tp'], 'false_positives': entry['fp'],
                     'unjudged': entry['unjudged'], 'precision': precision,
                     'recall': recall, 'recall_on_planted': recall_targets, 'planted_targets': entry['targets'],
                     'recall_on_labels': recall_labels, 'labelled_positives': entry['positives'],
                     'by_project': entry['by_project'], 'false_examples': entry['false_examples']})
    classes = {}
    for name, entry in truth.items():
        for item in entry['items']:
            row = classes.setdefault(item['class'], {'positive': 0, 'negative': 0, 'projects': {}})
            row[item['label']] = row.get(item['label'], 0) + 1
            row['projects'][name] = row['projects'].get(name, 0) + 1
    for cls, row in classes.items():
        positives = row['positive']
        row['recall_of_all_detectors'] = ratio(len(found_by_class.get(cls, set())), positives)
        row['detectors'] = sorted(d for d, c in DETECTORS.items() if c == cls)
    return rows, classes


def summary(truth, rows, classes):
    items = sum(len(entry['items']) for entry in truth.values())
    shown = [row for row in rows if row['shown']]
    return {'labelled_items': items, 'projects': sorted(truth), 'bar': BAR,
            'items_per_project': {name: len(entry['items']) for name, entry in sorted(truth.items())},
            'detectors': len(rows), 'shown': len(shown), 'hidden': len(rows) - len(shown),
            'limits': ('Precision is measured on judged outputs only: those that touch a labelled item or a file in which '
                       'the class was labelled exhaustively. Recall is measured on the planted mutations a detector was '
                       'built to find, and on the hand labels. Labels are one reviewer\'s reading of the source.')}


def write(truth, rows, classes):
    record = json.loads(RECORD.read_text(encoding='utf-8')) if RECORD.is_file() else {}
    record['precision'] = {'summary': summary(truth, rows, classes), 'classes': classes, 'detectors': rows,
                           'truth': {name: entry['files'] for name, entry in sorted(truth.items())}}
    RECORD.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    VERDICTS.write_text(json.dumps({'source': 'docs/engine-precision.json (tools/precision.py score --write)', 'bar': BAR,
                                    'hidden': {row['detector']: row['why'] for row in rows if not row['shown']},
                                    'shown': sorted(row['detector'] for row in rows if row['shown'])},
                                   ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def unsealed(truth):
    """Truth files whose content differs from the seal: labels edited after the reports were read."""
    if not SEAL.is_file(): return ['no seal recorded']
    sealed = json.loads(SEAL.read_text(encoding='utf-8'))['files']
    return [f['file'] for entry in truth.values() for f in entry['files'] if sealed.get(f['file']) != f['sha256']]


def a1_value(record=None, hidden=None):
    """A1: shown detectors whose precision and recall are measured and meet their bar ÷ detectors the product shows."""
    if record is None:
        record = json.loads(RECORD.read_text(encoding='utf-8')).get('precision') if RECORD.is_file() else None
    if not record: return None, 'no precision measured yet (tools/precision.py score --write)'
    if hidden is None:
        from eaos.claims import hidden_detectors
        hidden = hidden_detectors()
    items = record['summary']['labelled_items']
    if items < MIN_ITEMS or len(record['summary']['projects']) < len(PROJECTS):
        return 0.0, f"{items} labelled items on {len(record['summary']['projects'])} projects (needs {MIN_ITEMS} on {len(PROJECTS)})"
    rows = {row['detector']: row for row in record['detectors']}
    shown = sorted(d for d in DETECTORS if d not in hidden)
    good = [d for d in shown if (rows.get(d) or {}).get('status') == 'meets_bar']
    bad = sorted(set(shown) - set(good))
    return ratio(len(good), len(shown)) or (0.0 if shown else None), (
        f"shown detectors measured at their bar: {len(good)}/{len(shown)} ({', '.join(good)})"
        + (f"; shown without meeting it: {', '.join(bad)}" if bad else '')
        + f"; hidden: {len(hidden)}; {items} labelled items on {len(record['summary']['projects'])} projects")


def main(argv):
    command = argv[0] if argv else None
    if command == 'seed': seed(argv[1:]); return 0
    if command == 'seal': seal(); return 0
    if command == 'audit': audit(argv[1:]); return 0
    if command == 'score':
        truth = load_truth()
        changed = unsealed(truth)
        if changed:
            print('truth changed since it was sealed: ' + ', '.join(changed), file=sys.stderr)
            return 1
        rows, classes = score(truth)
        if '--write' in argv: write(truth, rows, classes)
        print(json.dumps(summary(truth, rows, classes), indent=2))
        print(f"{'detector':38s} {'class':18s} {'out':>4s} {'tp':>4s} {'fp':>4s} {'prec':>6s} {'recall':>6s}  status")
        for row in sorted(rows, key=lambda r: (r['class'] or 'zz', r['detector'])):
            print(f"{row['detector']:38s} {str(row['class']):18s} {row['outputs']:4d} {row['true_positives']:4d} "
                  f"{row['false_positives']:4d} {str(row['precision']):>6s} {str(row['recall']):>6s}  {row['status']}: {row['why']}")
        return 0
    print(__doc__)
    return 2


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
