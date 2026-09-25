"""The fifteen stages of an engagement as data, and a gate per stage that a command decides.

Each stage names what it produces and the gate that says it is done. A gate is a list of checks read from
the report: an indicator of eaos/indicators.py at a minimum (the same computation the corpus measurement
uses), an artifact that must be present and keep its contract, or a person's recorded approval. Indicators
that compare against a hand-recorded truth (U2, U3, S2, D1, H1, H2) are judged on the corpus, not per
project; a stage lists them under `corpus_only` so the gap is stated, not hidden.

S01-S07 are the assessment contract. S08-S14 are the execution contract: they run the project's own code,
so their gate refuses to open without the owner's authorization.json for that stage. S05 and S15 are mixed: a
static half the assessment delivers, then a run half an execution stage needs.
"""
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

ASSESSMENT, EXECUTION, MIXED = 'assessment', 'execution', 'mixed'
STATIC, RUN = 'static', 'run'


@dataclass(frozen=True)
class Check:
    indicator: str = ''     # an eaos/indicators.py id, at least `minimum`
    minimum: float = 1.0
    artifact: str = ''      # a path under the report, or a contract name in schemas/artifacts/
    approval: bool = False  # a person approved this stage (approvals.json)
    half: str = STATIC      # a mixed stage's run half is required only once an execution stage is gated


@dataclass(frozen=True)
class Stage:
    id: str
    key: str
    contract: str
    artifacts: tuple
    gate: tuple
    corpus_only: tuple = field(default=())


def ind(indicator, minimum=1.0, half=STATIC): return Check(indicator=indicator, minimum=minimum, half=half)
def art(path, half=STATIC): return Check(artifact=path, half=half)


# Ids, keys and gates follow docs/north-star.json -> pipeline; tests/test_engage.py keeps them equal.
STAGES = (
    Stage('S01', 'DISCOVER', ASSESSMENT, ('intake.json', 'facts/index.json', 'sbom.cdx.json', 'facts/external.json'),
          (ind('U6'), ind('U1', 0.95), ind('H3'), ind('R4'))),
    Stage('S02', 'MAP', ASSESSMENT, ('features.json', 'load-model.json', 'architecture/current/workspace.dsl'),
          (ind('U4'), ind('U5', 0.8), art('architecture/current/workspace.dsl')), corpus_only=('U2', 'U3')),
    Stage('S03', 'MEASURE', ASSESSMENT, ('measurements.json', 'baseline/baseline.json'),
          (ind('M1', 0.95), art('baseline/baseline.json'))),
    Stage('S04', 'DIAGNOSE', ASSESSMENT, ('CURRENT-STATE.md', 'debt-register.json', 'SECURITY-SURFACE.md'),
          (ind('S1', 0.8), ind('S3', 0.8), ind('H3'), ind('R3'), art('CURRENT-STATE.md')),
          corpus_only=('S2', 'D1', 'H1', 'H2')),
    Stage('S05', 'LOCK CURRENT BEHAVIOR', MIXED, ('behavior-lock/plan.json', 'nfr/', 'behavior-lock/results.json',
                                                  'runtime/performance.json'),
          (ind('E4'), ind('E5', 0.8, RUN), art('runtime-performance', RUN))),
    Stage('S06', 'DESIGN TARGET ARCHITECTURE', ASSESSMENT, ('TARGET-STATE.md', 'target-architecture.json',
                                                            'architecture/target/workspace.dsl', 'adr/'),
          (ind('T1'), ind('T2'), ind('T3', 0.6), ind('T4'), ind('T5'), ind('T6'), ind('T7'), Check(approval=True))),
    Stage('S07', 'PLAN TRANSFORMATION', ASSESSMENT, ('GAP-AND-STRATEGY.md', 'EXECUTION-PLAN.md', 'plan.json',
                                                     'report-quality.json'),
          (ind('G1'), ind('P1'), ind('P2', 0.5), ind('P3', 0.8), ind('P4'), ind('P5'), ind('P6'), ind('P7'),
           ind('P8'), ind('P9', 0.8))),
    Stage('S08', 'REBUILD / REFACTOR', EXECUTION, ('execution-log.json',), (ind('E1'),)),
    Stage('S09', 'VERIFY', EXECUTION, ('VERIFICATION.md', 'behavior-lock/results-after.json', 'guarantee.json'),
          (ind('E7'), ind('E2', 0.8))),
    Stage('S10', 'SECURE', EXECUTION, ('runtime/security.json',), (ind('E8'),)),
    Stage('S11', 'LOAD TEST', EXECUTION, ('runtime/performance.json', 'PERFORMANCE.md'), (ind('E6', 0.8),)),
    Stage('S12', 'BREAK IT DELIBERATELY', EXECUTION, ('runtime/resilience.json', 'RESILIENCE.md'), (ind('E9', 0.8),)),
    Stage('S13', 'OBSERVE', EXECUTION, ('otel/collector.yaml', 'slo/', 'runtime/telemetry.json'), (ind('E10', 0.9),)),
    Stage('S14', 'PRODUCTION READINESS', EXECUTION, ('PRODUCTION-READINESS.md', 'PRODUCTION-READINESS.json'),
          (ind('E11'),)),
    Stage('S15', 'CONTINUOUS GOVERNANCE', MIXED, ('handover/', 'handover/validation.json', 'GOVERNANCE.md'),
          (ind('K1'), art('baseline/baseline.json'))),
)
BY_ID = {stage.id: stage for stage in STAGES}


def _present(root, path):
    target = Path(root) / path
    return target.is_dir() and any(target.iterdir()) if path.endswith('/') else target.is_file()


def _approved(report, stage):
    from .artifact_contracts import load_valid
    return any(row['stage'] == stage for row in (load_valid('approvals', report) or {}).get('approvals', []))


class Context:
    """One report and its runtime directory, with every indicator computed once, lazily."""

    def __init__(self, report, runtime=None):
        self.report, self.runtime = Path(report), Path(runtime) if runtime else Path(report)
        self._values = None

    def values(self):
        if self._values is None:
            from . import indicators, toolchain
            registry = toolchain.registry()['tools']
            adapters = [{'name': t['name'], 'applies': t['applies']} for t in registry if t.get('applies')]
            self._values = indicators.values([indicators.Report(self.report, self.runtime)], adapters)
            self._values['R4'] = indicators.toolchain(toolchain.doctor(stage='assessment')['tools'])
        return self._values


def judge(check, context):
    """(ok, reason); the reason says what is missing, in terms a reader can act on."""
    if check.indicator:
        value, evidence = context.values().get(check.indicator, (None, 'not computed'))
        ok = value is not None and value >= check.minimum
        return ok, f'{check.indicator} = {value}, needs >= {check.minimum}: {evidence}'
    from .artifact_contracts import contracts, load_valid, location
    if check.artifact in contracts():
        where = location(check.artifact, context.report, context.runtime)
        if load_valid(check.artifact, context.report, context.runtime) is not None: return True, ''
        return False, f'{where} is missing or breaks schemas/artifacts/{check.artifact}.schema.json'
    return _present(context.report, check.artifact), f'{check.artifact} is missing'


def gate(stage, context, run_half=False):
    """{'passed', 'reasons', 'checks'}: the stage's checks, with a mixed stage's run half only if asked."""
    checks, reasons = [], []
    for check in stage.gate:
        if check.half == RUN and not run_half: continue
        if check.approval:
            ok, reason = _approved(context.report, stage.id), 'no recorded approval: eaos engage approve ' + stage.id
        else:
            ok, reason = judge(check, context)
        checks.append({'check': check.indicator or check.artifact or 'approval', 'half': check.half, 'ok': ok})
        if not ok: reasons.append(reason)
    return {'passed': not reasons, 'reasons': reasons, 'checks': checks}


def authorization(stage_id, runtime):
    """Why the owner's authorization does not open this stage, or '' when it does; the same check the
    sandbox makes before it runs anything (eaos/sandbox.py), which also holds the project to the commit."""
    from .sandbox import refusal
    return refusal(Path(runtime) / 'authorization.json', stage_id)


def status(report, runtime=None):
    context = Context(report, runtime)
    rows = []
    for stage in STAGES:
        row = {'id': stage.id, 'key': stage.key, 'contract': stage.contract,
               'artifacts': [{'path': path, 'present': _present(context.report, path)} for path in stage.artifacts],
               'gate': gate(stage, context), 'corpus_only': list(stage.corpus_only)}
        if stage.contract == MIXED: row['run'] = gate(stage, context, run_half=True)
        if stage.contract == EXECUTION:
            refused = authorization(stage.id, context.runtime)
            if refused: row['gate'] = {**row['gate'], 'passed': False, 'reasons': [refused] + row['gate']['reasons']}
        rows.append(row)
    return {'stages': rows}


def check_gate(stage_id, report, runtime=None):
    """(exit code, message). 0: this stage and every earlier one pass; 1: the first one that does not;
    3: an execution stage without a valid authorization for it."""
    context = Context(report, runtime)
    target = BY_ID[stage_id]
    if target.contract == EXECUTION:
        refused = authorization(stage_id, context.runtime)
        if refused: return 3, refused
    executing = target.contract == EXECUTION
    for stage in STAGES[:STAGES.index(target) + 1]:
        verdict = gate(stage, context, run_half=executing and stage.contract == MIXED)
        if not verdict['passed']:
            return 1, f'{stage.id} {stage.key} does not pass:\n  ' + '\n  '.join(verdict['reasons'])
    return 0, f'{stage_id} and every stage before it pass'


def approve(stage_id, report, by, note=''):
    """Record a person's approval of a stage. Only a person runs this; EAOS never approves its own work."""
    path = Path(report) / 'approvals.json'
    record = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {'schema_version': 1, 'approvals': []}
    row = {'stage': stage_id, 'by': by, 'at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}
    if note: row['note'] = note
    record['approvals'].append(row)
    path.write_text(json.dumps(record, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    return row


def main(args):
    if args.action == 'status':
        result = status(args.report, args.runtime)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=1))
        else:
            for row in result['stages']:
                present = sum(a['present'] for a in row['artifacts'])
                print(f"{'PASS' if row['gate']['passed'] else 'OPEN'} {row['id']} {row['key']:28} "
                      f"{row['contract']:10} artifacts {present}/{len(row['artifacts'])}")
                for reason in row['gate']['reasons']: print(f'       {reason}')
        return 0
    if args.stage not in BY_ID:
        print(f'unknown stage {args.stage}; one of {", ".join(BY_ID)}')
        return 2
    if args.action == 'approve':
        if not args.by:
            print('--by NAME is required: an approval names the person who gives it')
            return 2
        print(json.dumps(approve(args.stage, args.report, args.by, args.note or ''), ensure_ascii=False))
        return 0
    code, message = check_gate(args.stage, args.report, args.runtime)
    print(message)
    return code
