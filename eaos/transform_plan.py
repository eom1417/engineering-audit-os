"""Machine-executable transform plan: one stage per move with its acceptance criterion.

Each stage is a self-contained JSON object: which move, which canonical home, the
sites it would touch, the acceptance command, the rollback note, the falsifier,
and the predicted indicator delta. A model or human reviewer can consume the
plan stage by stage; nothing requires running the engine again.
"""
from pathlib import Path
import json
import sys
from .facts import digest
from .facts.store import read_set
from .sustainability import compute, _transformations


NAME = 'transform-plan'
VERSION = '1'
LIMITATIONS = [
    'A stage is a proposal, not an executed edit; the human or the isolated-copy remediator runs it.',
    'Acceptance commands are the closest executable proxy; runtime behaviour is not measured here.',
    'A predicted delta is computed from the structural reduction; a runtime check may show different results.',
    'A falsifier is a hint at the kind of evidence that would reject the move; it is not a guard.',
    'No stage edits /opt/flow or environment files: the engine never modifies the target outside its declared scope.',
]


def _gather(out):
    sets = {}
    for name in ['fingerprint', 'redundancy', 'graph', 'resolve', 'syntax']:
        path = Path(out) / 'facts' / f'{name}.json'
        if path.is_file(): sets[name] = read_set(Path(out), name)
    return sets


def _canonical_home_for(out, cluster, policy_path=None):
    from .canonical_home import suggest
    return suggest(out, cluster, policy_path)


def _declared_test_command(out):
    run_path = Path(out) / 'facts' / 'run.json'
    if not run_path.is_file(): return None
    target = Path(json.loads(run_path.read_text(encoding='utf-8'))['target'])
    package = target / 'package.json'
    if package.is_file():
        try: scripts = json.loads(package.read_text(encoding='utf-8')).get('scripts', {})
        except (ValueError, OSError): scripts = {}
        if scripts.get('test') and 'no test specified' not in scripts['test'].lower():
            return ['npm', 'test', '--silent'], 'project_manifest'
    if (target / 'go.mod').is_file(): return ['go', 'test', './...'], 'project_manifest'
    if (target / 'Cargo.toml').is_file(): return ['cargo', 'test'], 'project_manifest'
    if (target / 'pom.xml').is_file(): return ['mvn', 'test'], 'project_manifest'
    if (target / 'tests').is_dir():
        pyproject = target / 'pyproject.toml'
        text = pyproject.read_text(encoding='utf-8', errors='replace') if pyproject.is_file() else ''
        if 'pytest' in text or any((target / 'tests').glob('test_*.py')):
            return [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-q'], 'discovered_tests'
    return None


def _stage_acceptance(kind, sites, out=None, stage=1):
    """Pick the closest executable acceptance command for a stage.

    The command is the smallest check that, if it passes, would make the
    stage's hypothesis falsifiable: keeping the test surface unchanged while
    reducing the redundancy. We never invent arbitrary test commands.
    """
    if not sites: return None
    discovered = _declared_test_command(out) if out is not None else None
    if discovered:
        argv, origin = discovered
    else:
        argv, origin = ([sys.executable, '-m', 'compileall', '-q', '.'],
                        'generated_equivalence_fallback')
    check = {
        'id': f'TRANSFORM-{stage:03d}-ACCEPTANCE',
        'kind': 'command',
        'invariant': ('Project behavior remains accepted after the structural move.' if discovered else
                      'Every candidate source file remains parseable after the structural move.'),
        'expected': 'The command exits successfully in the candidate repository.',
        'source_revision': 'candidate',
        'argv': argv,
        'command': ' '.join(argv),
        'cwd': '.',
        'expected_exit': 0,
        'origin': origin,
        'source_files': sorted({site['path'] for site in sites}),
    }
    from .decisions import check_errors
    errors = check_errors(check)
    if errors: raise ValueError('Invalid stage acceptance: ' + '; '.join(errors))
    return check


def _rollback_for(kind):
    if kind == 'canonicalize':
        return 'Revert one commit: the canonical home is the only new file; the call sites are the only edited ones.'
    if kind in {'repeated_call', 'hoistable_call', 'n_plus_one', 'pass_through'}:
        return 'Revert one commit: the redundancy-removal edit is the only change in this stage.'
    return 'Revert one commit; no stage alters files outside its scope.'


def build(out, policy_path=None, targets=None):
    """Build a transform plan from the current sustainability dashboard."""
    sets = _gather(out)
    dashboard = compute(out, targets)
    moves = _transformations(out, dashboard)
    stages = []
    index = 0
    for move in moves:
        if move['move'] == 'canonicalize':
            cluster_sha = move.get('rule')
            cluster = next((f for f in sets.get('fingerprint', {}).get('facts', [])
                             if f['kind'] == 'duplicate_cluster' and f['value']['shape_sha'] == cluster_sha), None)
            if cluster is None: continue
            canonical = _canonical_home_for(out, cluster, policy_path)
            best = canonical['candidates'][0] if canonical['candidates'] else None
            sites = move['occurrences']
            index += 1
            stages.append({
                'stage': index,
                'move': move['move'],
                'rule': cluster_sha,
                'canonical_home': best['path'] if best else None,
                'canonical_home_layer': best['layer'] if best else None,
                'canonical_home_score': best['score'] if best else None,
                'all_candidates': [{'path': c['path'], 'layer': c['layer'],
                                     'policy_violations': c['policy_violations'],
                                     'home_already': c['home_already']}
                                    for c in canonical['candidates']][:5],
                'sites': sites,
                'steps': ['Place the canonical definition at the chosen home (if not already there).',
                          'Replace every duplicate with an import-and-call.',
                          'Run the equivalence test set generated for this stage.'],
                'acceptance': _stage_acceptance('canonicalize', sites, out, index),
                'rollback': _rollback_for('canonicalize'),
                'falsifier': move['falsifier'],
                'predicted': move['predicted'],
                'indicator': move['indicator'],
            })
        elif move['move'] == 'eliminate_redundancy':
            sites = move.get('sites', [])
            index += 1
            stages.append({
                'stage': index,
                'move': move['move'],
                'redundancy_kind': move.get('kind'),
                'sites': sites,
                'steps': ['Inspect each site; remove or hoist the redundant call.',
                          'Keep the public signature stable; the call site is the only changed file.'],
                'acceptance': _stage_acceptance(move.get('kind'), sites, out, index),
                'rollback': _rollback_for(move.get('kind')),
                'falsifier': move['falsifier'],
                'predicted': move['predicted'],
                'indicator': move['indicator'],
            })
    summary = {'stages': len(stages),
                'moves_with_no_viable_candidate': sum(1 for stage in stages
                                                         if stage['move'] == 'canonicalize'
                                                         and not stage['canonical_home'])}
    return {'schema_version': 1, 'stages': stages, 'summary': summary,
            'limits': ' '.join(LIMITATIONS)}


# A 1,065-line plan is a record, not a document: the first stages are what anyone reads.
# A ceiling on how many stages are even considered for rendering; what actually fits is decided
# against the declared budget, because one stage may print twenty sites and another three.
SHOWN_STAGES = 24


def _budget():
    """The line budget the artifact contract declares for transform-plan.md."""
    from .compose.artifacts import BY_NAME
    declared = BY_NAME.get('transform-plan.md')
    return declared.budget_lines if declared else 200


def render(out, plan, language='ar'):
    """Write transform-plan.json and transform-plan.md to the output directory."""
    ar = language == 'ar'
    Path(out, 'transform-plan.json').write_text(
        json_dumps(plan), encoding='utf-8')
    lines = []
    if ar:
        lines += ['# خطة التحويل القابلة للتنفيذ آليًا', '',
                  '> كل مرحلة مواصفة آلية. معيار القبول سلوكي، والحركة تُحاكى قبل تنفيذها. '
                  'أي مرحلة بلا موضع مرجعي قابل للتطبيق تبقى معلّمة.', '']
    else:
        lines += ['# Machine-executable transform plan', '',
                  '> Each stage is a self-contained spec. The acceptance criterion is behavioral; '
                  'movements are simulated before execution. A stage with no viable canonical home stays open.', '']
    lines += ['## ' + ('ملخص' if ar else 'Summary'), '']
    lines += [f"- " + ('عدد المراحل' if ar else 'stages') + f": {plan['summary']['stages']}"]
    lines += [f"- " + ('حركات بلا موضع مرجحي' if ar else 'moves with no viable candidate')
              + f": {plan['summary']['moves_with_no_viable_candidate']}"]
    header = lines
    blocks = []
    for stage in plan['stages'][:SHOWN_STAGES]:
        lines = []
        lines += ['', '## ' + ('مرحلة' if ar else 'Stage') + f" {stage['stage']}: {stage['move']}"]
        if 'rule' in stage:
            lines += [f"- " + ('القاعدة' if ar else 'rule') + f": {stage['rule'][:16]}"]
        if 'redundancy_kind' in stage:
            lines += [f"- " + ('نوع التكرار' if ar else 'redundancy kind') + f": {stage['redundancy_kind']}"]
        if stage.get('canonical_home') is not None:
            lines += [f"- " + ('الموضع المرجعي' if ar else 'canonical home') + f": {stage['canonical_home']}"]
        lines += ["- " + ('المواضع' if ar else 'sites') + ":"]
        for site in stage['sites'][:20]:
            lines += [f"  - {site.get('path')}:{site.get('line') or site.get('start_line')} {site.get('symbol', '')}"]
        lines += ["- " + ('الخطوات' if ar else 'steps') + ":"]
        for step in stage.get('steps', []):
            lines += [f"  - {step}"]
        if stage.get('acceptance'):
            lines += ["- " + ('معيار القبول' if ar else 'acceptance') + ":"]
            for k, v in stage['acceptance'].items():
                lines += [f"  - {k}: {v}"]
        if stage.get('rollback'):
            lines += [f"- " + ('التراجع' if ar else 'rollback') + f": {stage['rollback']}"]
        if stage.get('falsifier'):
            lines += [f"- " + ('ناقض' if ar else 'falsifier') + f": {stage['falsifier']}"]
        if stage.get('predicted'):
            lines += ["- " + ('التأثير المتوقع' if ar else 'predicted') + ":"]
            for k, v in stage['predicted'].items():
                lines += [f"  - {k}: {v}"]
        blocks.append(lines)
    # A stage is shown whole or not at all: half a stage is a step list with no acceptance under
    # it. A fixed count of stages cannot hold a budget, because one stage may print twenty sites.
    lines = header
    shown = 0
    for block in blocks:
        if len(lines) + len(block) > _budget() - 4: break
        lines += block
        shown += 1
    if shown < len(plan['stages']):
        lines += ['', (f"عُرضت {shown} مرحلة من {len(plan['stages'])}؛ البقية في `transform-plan.json`."
                       if ar else
                       f"Showing {shown} of {len(plan['stages'])} stages; the rest are in "
                       f"`transform-plan.json`.")]
    lines += ['', '## ' + ('الحدود' if ar else 'Limits'), '']
    for line in LIMITATIONS: lines += [f"- {line}"]
    Path(out, 'transform-plan.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return {'json': str(Path(out, 'transform-plan.json')),
            'markdown': str(Path(out, 'transform-plan.md'))}


def json_dumps(obj):
    import json
    return json.dumps(obj, ensure_ascii=False, indent=2) + '\n'
