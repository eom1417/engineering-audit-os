"""The `rules` stage (M16.3): every rule of the person's that holds now, its guard run on the checked code; rules.json
says each one held, broken where, or not guarded and why. A detector's guard is read with the claims, from what the
other detectors found (eaos/analysis/claims/from_rules.py)."""
from ..stages import SkipStage
from ...core.project import rules as registry, state as project_state
from ...core.project.workspace import write as write_json


def rules(context):
    folder = (context.get('sign_in') or {}).get('folder')
    if not folder: raise SkipStage('this check was not started for a project of the person', code='no_rules')
    kept = registry.Kept(folder)
    state = project_state.of_workspace(folder)
    if state: registry.settle(kept, state)
    holding = registry.holding(kept, state)
    if not holding: raise SkipStage('the person stated no rule that holds for this project now', code='no_rules')
    from ...analysis.rules.held import RECORD, in_check
    results = in_check(holding, context.target)
    write_json(context.out / RECORD, {'workspace': str(folder), 'rules': results})
    return {'rules': len(results), 'broken': sum(r['status'] == 'broken' for r in results),
            'unguarded': sum(r['status'] == 'unguarded' for r in results)}

