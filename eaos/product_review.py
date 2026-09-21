"""The reviewed-project summary, built on the one declared pipeline rather than its own copy of it.

This module used to hold a second ordering of the same work — assemble, then plan, then report —
which is how five subsystems ended up unreachable from the command most people run.
"""
from pathlib import Path

from .workspace import read, write

GOALS = {'onboarding', 'debugging', 'evolution', 'architecture'}
# What a project review does not do: it never executes the target's tests and never shells out to
# an external engine unless the caller asks for those stages by name.
WITHOUT = ('engines', 'verify')


def run(target, out, *, goal='evolution', language='ar', provider=None, exclude=(), audit_run=None):
    if goal not in GOALS:
        raise ValueError('Unknown review goal')
    from .pipeline import execute
    manifest = execute(target, out, skip=WITHOUT, language=language, exclude=exclude, provider=provider,
                       goal=goal, audit_run=audit_run)
    return summarise(Path(out).resolve(), manifest, goal, bool(provider))


def summarise(out, manifest, goal, interpreted):
    dossier = read(out / 'dossier.json') if (out / 'dossier.json').is_file() else {'decisions': [], 'tasks': []}
    result = read(out / 'report-result.json') if (out / 'report-result.json').is_file() else {}
    violations = result.get('output_spec_violations', ['the output contract was never checked'])
    summary = {
        'target': manifest['target'], 'out': str(out), 'goal': goal,
        'mode': 'semantic_review' if interpreted else 'facts_only',
        'report': str(out / 'PRODUCT-REPORT.md'), 'site': str(out / 'index.html'),
        'decision_counts': {kind: sum(row['kind'] == kind for row in dossier.get('decisions', []))
                            for kind in ('repair', 'investigate', 'retain')},
        'executable_repairs': sum(task.get('decision', {}).get('readiness') == 'ready'
                                  for task in dossier.get('tasks', [])),
        'output_spec_violations': violations,
        'stages': {name: row['status'] for name, row in manifest['stages'].items()},
        'not_examined': {name: row['reason'] for name, row in manifest['stages'].items()
                         if row['status'] != 'ok'},
        'status': ('OUTPUT_SPEC_VIOLATED' if violations else
                   'INCOMPLETE' if manifest['status'] != 'COMPLETE' else 'REVIEW_REQUIRED'),
    }
    write(out / 'product-review.json', summary)
    return summary
