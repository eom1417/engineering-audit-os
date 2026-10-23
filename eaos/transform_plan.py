"""Machine-executable transform plan: one stage per move with its acceptance criterion.

Each stage is a self-contained JSON object: which move, which canonical home, the
sites it would touch, the acceptance command, the rollback note, the falsifier,
and the predicted indicator delta. A model or human reviewer can consume the
plan stage by stage; nothing requires running the engine again.
"""
from pathlib import Path
import json
import sys
from . import progress
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


# A manifest that declares the project's tests, and the command that runs them.
MANIFEST_TESTS = (('go.mod', ['go', 'test', './...']), ('Cargo.toml', ['cargo', 'test']), ('pom.xml', ['mvn', 'test']))


def _npm_test(target):
    """True when package.json declares a real test script, not npm's placeholder."""
    package = target / 'package.json'
    if not package.is_file(): return False
    try: scripts = json.loads(package.read_text(encoding='utf-8')).get('scripts', {})
    except (ValueError, OSError): scripts = {}
    return bool(scripts.get('test')) and 'no test specified' not in scripts['test'].lower()


def _declared_test_command(out):
    run_path = Path(out) / 'facts' / 'run.json'
    if not run_path.is_file(): return None
    target = Path(json.loads(run_path.read_text(encoding='utf-8'))['target'])
    if _npm_test(target): return ['npm', 'test', '--silent'], 'project_manifest'
    declared = next((argv for name, argv in MANIFEST_TESTS if (target / name).is_file()), None)
    if declared: return declared, 'project_manifest'
    from .verify import python_tests
    found = python_tests(target)
    if found: return found[0], 'discovered_tests'
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


def _canonicalize_stage(out, sets, move, index, policy_path):
    """The stage that gives a duplicated rule one home, the best candidate first; None when its cluster is gone."""
    cluster_sha = move.get('rule')
    cluster = next((f for f in sets.get('fingerprint', {}).get('facts', [])
                    if f['kind'] == 'duplicate_cluster' and f['value']['shape_sha'] == cluster_sha), None)
    if cluster is None: return None
    canonical = _canonical_home_for(out, cluster, policy_path)
    best = canonical['candidates'][0] if canonical['candidates'] else None
    sites = move['occurrences']
    return {
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
    }


def _redundancy_stage(out, move, index):
    sites = move.get('sites', [])
    return {
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
    }


def build(out, policy_path=None, targets=None):
    """Build a transform plan from the current sustainability dashboard."""
    sets = _gather(out)
    dashboard = compute(out, targets)
    moves = _transformations(out, dashboard)
    stages = []
    homes = sum(1 for move in moves if move['move'] == 'canonicalize')
    sought = 0
    for move in moves:
        stage = None
        if move['move'] == 'canonicalize':
            progress.count('canonical homes', sought, homes)
            sought += 1
            stage = _canonicalize_stage(out, sets, move, len(stages) + 1, policy_path)
        elif move['move'] == 'eliminate_redundancy':
            stage = _redundancy_stage(out, move, len(stages) + 1)
        if stage: stages.append(stage)
    progress.count('canonical homes', homes, homes)
    summary = {'stages': len(stages),
                'moves_with_no_viable_candidate': sum(1 for stage in stages
                                                         if stage['move'] == 'canonicalize'
                                                         and not stage['canonical_home'])}
    return {'schema_version': 1, 'stages': stages, 'summary': summary,
            'limits': ' '.join(LIMITATIONS)}


def write(out, plan):
    """Write transform-plan.json to the output directory."""
    Path(out, 'transform-plan.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
