"""Record what actually happened for one task, so the execution can be audited afterwards.

Usage: python tools/log_task.py <task-id> <acceptance-exit-code> [--note "..."]

Writes an append-only entry to docs/execution-log.json: the task, the commit, the acceptance
result, the gate result, and the scorecard at that moment. A task marked done in the plan with no
entry here, or with a nonzero acceptance, is an unproven claim.
"""
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / 'docs/execution-log.json'


def run(command):
    return subprocess.run(command, cwd=ROOT, capture_output=True, text=True, shell=isinstance(command, str))


def main(argv):
    if len(argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    task, exit_code = argv[0], int(argv[1])
    note = argv[argv.index('--note') + 1] if '--note' in argv else ''
    plan = json.loads((ROOT / 'docs/capability-plan.json').read_text(encoding='utf-8'))
    known = {row['id']: row for milestone in plan['milestones'] for row in milestone['tasks']}
    if task not in known:
        print(f'unknown task {task}', file=sys.stderr)
        return 2
    score = ROOT / 'docs/capability-score.json'
    card = json.loads(score.read_text(encoding='utf-8')) if score.is_file() else {}
    entry = {
        'task': task,
        'title': known[task]['title'],
        'recorded_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'commit': run(['git', 'rev-parse', '--short', 'HEAD']).stdout.strip(),
        'acceptance_command': known[task]['acceptance'],
        'acceptance_exit_code': exit_code,
        'acceptance_passed': exit_code == 0,
        'status_recorded_in_plan': known[task]['status'],
        'moves': known[task].get('moves'),
        'scores_at_this_point': {name: row['score'] for name, row in (card.get('domains') or {}).items()},
        'overall_at_this_point': card.get('overall'),
        'note': note,
    }
    existing = json.loads(LOG.read_text(encoding='utf-8')) if LOG.is_file() else {'schema_version': 1,
                                                                                  'entries': []}
    existing['entries'].append(entry)
    LOG.write_text(json.dumps(existing, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f"logged {task}: acceptance exit {exit_code}, overall {entry['overall_at_this_point']}")
    return 0 if exit_code == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
