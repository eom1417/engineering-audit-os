"""eaos/data/engine-quality.json: how good EAOS's own analysis is, packaged so the Studio's quality page (studio/quality.json,
eaos/studio/quality.py) can show it on any machine, where docs/ is not installed.

It is derived, never written by hand, from two records of this repository:
    docs/engine-precision.json   each detector's precision and recall on the labelled set (tools/precision.py score)
    docs/north-star.json         the product plan's indicators of the capabilities that judge the analysis

    python tools/engine_quality.py            # write the packaged file
    python tools/engine_quality.py --check    # exit 1 when it is stale against the two records

The names below are the plain words a person reads on the page, in both languages; a detector or indicator with no name
here keeps its id, and --check names it so it gets one.
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRECISION = ROOT / 'docs/engine-precision.json'
NORTH_STAR = ROOT / 'docs/north-star.json'
OUT = ROOT / 'eaos/data/engine-quality.json'
# The capabilities whose indicators judge the analysis itself (the plan's other capabilities judge the product around it).
CAPABILITIES = ('C2', 'C3', 'C4', 'C5', 'C6', 'C7', 'C8', 'C10')

DETECTORS = {
    'structural_duplicate': ('شيفرة متشابهة البنية', 'Code with the same structure'),
    'sequence_duplicate': ('تسلسل خطوات مكرر', 'Repeated sequence of steps'),
    'duplicated_rule': ('قاعدة عمل مكررة', 'Duplicated business rule'),
    'engine_cluster:literal_duplication': ('نسخ حرفي للكود', 'Literally copied code'),
    'engine_cluster:duplication': ('تكرار تتفق عليه المحركات', 'Duplication engines agree on'),
    'dead_code': ('كود لا يستخدمه أحد', 'Code nothing uses'),
    'dead_code_review': ('كود ميت يحتاج مراجعة', 'Dead code that needs a review'),
    'engine_cluster:dead_code': ('كود ميت تتفق عليه المحركات', 'Dead code engines agree on'),
    'broken_code': ('كود معطوب', 'Broken code'),
    'hotspot': ('ملف معقد كثير التغيير', 'Complex file that changes often'),
    'engine_cluster:complexity': ('تعقيد تتفق عليه المحركات', 'Complexity engines agree on'),
    'mutable_global': ('حالة عامة قابلة للتغيير', 'Shared mutable state'),
    'external_write': ('كتابة من خارج المالك', 'Write from outside the owner'),
    'data_owners': ('بيانات لها أكثر من كاتب', 'Data with more than one writer'),
    'data_model': ('نموذج البيانات', 'Data model'),
    'data_model:runtime': ('نموذج البيانات وقت التشغيل', 'Data model at run time'),
    'data_table': ('جداول البيانات', 'Data tables'),
    'redundant_work': ('عمل مكرر بلا داعٍ', 'Redundant work'),
    'access_gap_no_rls': ('جدول بلا سياسة وصول', 'Table with no access policy'),
    'access_gap_open_write': ('كتابة مفتوحة للجميع', 'Write open to anyone'),
    'engine_cluster:secret': ('سر مكشوف في الكود', 'Secret exposed in the code'),
    'import_cycle': ('دورة استيراد', 'Import cycle'),
    'engine_cluster:cycle': ('دورة تتفق عليها المحركات', 'Cycle engines agree on'),
    'vulnerable_dependency': ('اعتمادية فيها ثغرة', 'Dependency with a known vulnerability'),
    'engine_cluster:coupling': ('ترابط خفي', 'Hidden coupling'),
    'engine_cluster:dataflow': ('تدفق بيانات خطر', 'Risky data flow'),
    'engine_cluster:surface': ('سطح مكشوف', 'Exposed surface'),
    'engine_cluster:test_quality': ('جودة الاختبارات', 'Test quality'),
    'engine_cluster:naming': ('التسمية', 'Naming'),
    'engine_cluster:boundary': ('حدود الطبقات', 'Layer boundaries'),
    'engine_cluster:misconfiguration': ('إعداد خاطئ', 'Misconfiguration'),
    'engine_cluster:sql_quality': ('جودة SQL', 'SQL quality'),
    'engine_cluster:api_contract': ('عقد الواجهة البرمجية', 'API contract'),
    'engine_cluster:unused_dependency': ('اعتمادية غير مستخدمة', 'Unused dependency'),
    'cochange': ('ملفات تتغير معًا', 'Files that change together'),
    'trace_gap': ('مسار انقطع تتبعه', 'Path whose trace stops'),
    'policy': ('مخالفة قانون المشروع', "Breach of the project's rules"),
    'load_blocker': ('عائق تحت الحمل', 'Blocker under load'),
    'untested': ('كود بلا اختبار', 'Untested code'),
    'unattributed': ('ادعاء بلا كاشف معروف', 'Finding with no known detector'),
}

CAPABILITY_NAMES = {
    'C2': 'The current-state report: it sees the whole program', 'C3': 'Signal: every finding is a real problem',
    'C4': 'Dead code and leftovers: found and removed safely', 'C5': 'Basic security hygiene',
    'C6': 'The ideal-picture report', 'C7': 'The gap and the strategic change', 'C8': "The team's execution plan",
    'C10': 'Trust and independent proof',
}

INDICATOR_NAMES = {
    'U1': 'Analysis coverage', 'U2': 'User surfaces found', 'U3': 'Data model read', 'U4': 'Inventory of functions',
    'U5': 'Inputs, outputs and limits', 'U6': 'Intake', 'M1': 'Measures for every source file',
    'A1': 'Detector precision measured', 'A2': 'A sound JS/TS base', 'A3': "The product's real surfaces and components",
    'N1': 'A sound system map', 'N2': 'The ledger replays from its events', 'Q1': 'Tracing reaches the end',
    'Q2': 'One owner for each input', 'Q3': 'Overlapping pages and functions', 'Q4': 'Truthful function cards',
    'Z1': 'Screens captured', 'Z2': 'Usability problems found',
    'S1': 'Findings that are not noise', 'S2': 'Precision of dead-code candidates', 'S3': 'High risk confirmed by two witnesses',
    'S4': 'Every card on its own file and evidence', 'S5': 'Little noise on a real project',
    'D1': 'Known defects found', 'D2': 'Leftovers found', 'D3': 'Safe-removal cards ready', 'D4': 'Archived before removal',
    'H1': 'Committed credentials at their right severity', 'H2': 'Access-policy coverage read', 'H3': 'Supply chain',
    'T1': 'Concrete target components', 'T2': 'Infrastructure decisions', 'T3': 'Decisions that change the structure',
    'T4': 'A decision for every component of today', 'T5': 'The same functions in the ideal picture',
    'T6': 'C4 model of today and the target', 'T7': 'Architecture decisions in MADR form', 'I1': 'A complete system description',
    'I2': 'An ideal picture with nothing invented', 'I3': 'A design the owner accepts',
    'G1': 'Gap tied to the target components', 'G2': 'Sustainability indicators measured', 'G3': 'Initiative before being asked',
    'G4': "The project's rules as gates", 'J1': 'Gaps confirmed by evidence', 'J2': 'Gaps that survive review',
    'P1': 'Tasks with a known size', 'P2': 'Fixes ready to apply', 'P3': 'Runnable acceptance commands',
    'P4': 'Milestones with measured goals', 'P5': 'Proportionality', 'P6': 'Team sections', 'P7': 'The four reports',
    'P8': 'Quality of the four reports', 'P9': 'Mechanical tasks carry a codemod', 'K1': 'Run and handover kit accepted by its tools',
    'V1': 'Determinism', 'V2': 'Evidence and a falsifier for every finding', 'V3': 'Independent human review',
    'V4': 'Size of the real sample', 'Y1': 'Holds a large project', 'Y2': 'Predictions come true after the change',
}


def _load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def build(precision=None, north_star=None):
    """The packaged record from the two documents (their contents, or this repository's files)."""
    precision = _load(PRECISION) if precision is None else precision
    north_star = _load(NORTH_STAR) if north_star is None else north_star
    record = precision.get('precision') or {}
    summary = record.get('summary') or {}
    detectors = []
    for row in record.get('detectors') or []:
        ar, en = DETECTORS.get(row['detector'], (row['detector'], row['detector']))
        projects = {name.split(':', 1)[0]: {'tp': counts.get('tp', 0), 'fp': counts.get('fp', 0), 'unjudged': counts.get('unjudged', 0)}
                    for name, counts in (row.get('by_project') or {}).items() if name.endswith(':original')}
        detectors.append({'id': row['detector'], 'name': {'ar': ar, 'en': en}, 'class': row.get('class'), 'status': row.get('status'),
                          'shown': bool(row.get('shown')), 'why': row.get('why') or '', 'outputs': row.get('outputs'),
                          'judged': row.get('judged'), 'true_positives': row.get('true_positives'),
                          'false_positives': row.get('false_positives'), 'precision': row.get('precision'), 'recall': row.get('recall'),
                          'labelled_positives': row.get('labelled_positives'), 'planted_targets': row.get('planted_targets'),
                          'projects': projects})
    capabilities = []
    for capability in north_star.get('capabilities') or []:
        if capability['id'] not in CAPABILITIES: continue
        capabilities.append({
            'id': capability['id'], 'name': {'ar': capability['name'], 'en': CAPABILITY_NAMES.get(capability['id'], capability['id'])},
            'indicators': [{'id': row['id'], 'name': {'ar': row['name'], 'en': INDICATOR_NAMES.get(row['id'], row['id'])},
                            'value': row.get('value'), 'target': row.get('target'), 'measured': row.get('measured')}
                           for row in capability.get('indicators') or []]})
    return {'source': 'docs/engine-precision.json and docs/north-star.json (tools/engine_quality.py)',
            'digests': {'engine-precision': hashlib.sha256(json.dumps(precision, sort_keys=True).encode()).hexdigest(),
                        'north-star': hashlib.sha256(json.dumps(north_star, sort_keys=True).encode()).hexdigest()},
            'north_star_measured_at': north_star.get('measured_at'),
            'bar': summary.get('bar') or {}, 'labelled_items': summary.get('labelled_items'),
            'labelled_projects': summary.get('projects') or [], 'limits': summary.get('limits') or '',
            'detectors': detectors, 'capabilities': capabilities}


def text(record):
    return json.dumps(record, ensure_ascii=False, indent=1, sort_keys=True) + '\n'


def unnamed(record):
    """Ids that would be shown with no plain name."""
    return sorted({row['id'] for row in record['detectors'] if row['name']['en'] == row['id']}
                  | {row['id'] for cap in record['capabilities'] for row in cap['indicators'] if row['name']['en'] == row['id']})


def main(argv):
    record = build()
    if '--check' in argv:
        problems = []
        if not OUT.is_file() or OUT.read_text(encoding='utf-8') != text(record):
            problems.append(f'{OUT.relative_to(ROOT)} is stale: run python tools/engine_quality.py')
        problems += [f'no plain name for {name} in tools/engine_quality.py' for name in unnamed(record)]
        for line in problems: print(line, file=sys.stderr)
        return 1 if problems else 0
    OUT.write_text(text(record), encoding='utf-8')
    print(f'wrote {OUT.relative_to(ROOT)}: {len(record["detectors"])} detectors, '
          f'{sum(len(c["indicators"]) for c in record["capabilities"])} indicators')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
