"""What a run came to (eaos/interfaces/studio_actions/runs.py): the batch it handed over as a branch, or landed on its base,
with its diff, checks and cards closed; and the batch accepted by itself when the person chose it in the preview."""
import subprocess

from ...ai.assistant import prompts

from ...core.project import state as project_state
from ...core.system.clock import now


def _fresh_waves(record, state):
    """The batches this run made: those past the count it saw at its start on the same branch, else those on a branch
    that did not exist then."""
    before = set(record.get('branches_before') or [])
    seen, waves = record.get('waves_before'), state.get('waves') or []
    return (waves[seen.get('count') or 0:] if isinstance(seen, dict) and seen.get('branch') == state.get('branch')
            else [w for w in waves if w.get('branch') not in before])


def _diff_stat(project, branch):
    """{files, insertions, deletions} the branch changes since it left HEAD, from git's short stat."""
    shortstat = subprocess.run(['git', '-C', str(project), 'diff', '--shortstat', f"HEAD...{branch}"],
                               capture_output=True, text=True).stdout
    numbers = [int(part.split()[0]) for part in shortstat.split(',') if part.strip()[:1].isdigit()]
    labels = [part.split()[1] for part in shortstat.split(',') if part.strip()[:1].isdigit()]
    stat = {'files': 0, 'insertions': 0, 'deletions': 0}
    for number, label in zip(numbers, labels):
        stat['files' if label.startswith('file') else 'insertions' if label.startswith('insertion') else 'deletions'] = number
    return stat


def _landed(fresh):
    """A direct batch of `fresh`: it landed on the base branch itself and left no branch; None."""
    return next((w for w in reversed(fresh) if w.get('direct') and w.get('status') == 'accepted'), None)


def _landed_outcome(landed):
    """The outcome of a direct batch: where it landed, and the cards it closed with their checks."""
    kept = list(landed.get('kept') or [])
    return {'landed_on': landed.get('merge_into'), 'target': landed.get('merge_into'), 'cards_closed': kept,
            'tests': prompts.batch_tests(kept, landed.get('failed') or {})}


class Outcomes:
    """The run manager's outcomes."""
    def _auto_accept(self, run, payload):
        """Accept this run's own batch when the person chose it in this run's Fix preview (auto_accept, bound to its
        confirm token) and fix_finish kept at least one change: the choice is the person's agreement, for this run
        only. Never into a protected branch, never another run's branch; otherwise the branch waits for the person."""
        record = self.store.load(run)
        branch = payload.get('branch')
        if not self._may_accept_itself(record, payload): return None
        target = self._merge_target(record, payload)
        if not target or not self.branch_control: return None
        reason = self.branch_control.policy()['protected'].get(target)
        if reason:
            self.store.append(run, 'say', {'en': f'Not accepted automatically: {target} is protected ({reason["en"]}); the branch {branch} waits for you',
                                           'ar': f'ما اعتُمد تلقائيًا: {target} محمي ({reason["ar"]})؛ الفرع {branch} ينتظرك'}, {'branch': branch, 'target': target})
            return None
        self.store.append(run, 'action', {'en': f'Accepting {branch} automatically: you chose it in the preview and the checks passed',
                                          'ar': f'أعتمد {branch} تلقائيًا: اخترت هذا في المعاينة والفحوص نجحت'},
                          {'action': 'accept', 'by': 'person', 'arguments': {'branch': branch, 'auto_accept': True}})
        try: result = self.call('accept', {'person_agreed': True})
        except Exception as problem: result = {'error': f'{type(problem).__name__}: {problem}'}
        self._accepted_by_itself(run, branch, result)
        return result

    def _may_accept_itself(self, record, payload):
        """Whether this Fix run's own batch may be accepted by itself: the person chose it, a change was kept, nothing
        decided it yet, and its branch is the newest waiting."""
        branch = payload.get('branch')
        if not (record.get('verb') == 'fix' and record.get('auto_accept') is True and branch and payload.get('cards_closed')): return False
        return not record.get('outcome') and self.newest_waiting() == branch

    def _merge_target(self, record, payload):
        """Where the batch merges: as its wave says, else as the run's preview chose, else the run's target."""
        branch = payload.get('branch')
        wave = next((w for w in reversed((project_state.load(self.project) or {}).get('waves') or []) if w.get('branch') == branch), {})
        return wave.get('merge_into') or (record.get('where') or {}).get('merge_into') or payload.get('target')

    def _accepted_by_itself(self, run, branch, result):
        """What the accept by itself came to, in the run: taken in, or why the branch still waits for the person."""
        ok = isinstance(result, dict) and not result.get('error') and result.get('status') == 'accepted'
        if ok:
            self.store.append(run, 'result', {'en': f'Taken in automatically: {branch}', 'ar': f'اعتُمد تلقائيًا: {branch}'},
                              {'branch': branch, 'outcome': 'accept', 'auto_accept': True, 'answer': result})
            self.store.update(run, outcome='accepted', decided=now('milliseconds'))
        else:
            why = str((result or {}).get('status') or (result or {}).get('error'))
            self.store.append(run, 'say', {'en': f'Not accepted automatically ({why}): the branch {branch} waits for you',
                                           'ar': f'ما اعتُمد تلقائيًا ({why}): الفرع {branch} ينتظرك'}, {'branch': branch, 'reason': why})

    def _waiting_branches(self):
        state = project_state.load(self.project) or {}
        return {wave['branch'] for wave in state.get('waves') or [] if wave.get('status') == 'applied' and wave.get('branch')}

    def newest_waiting(self):
        """The branch accept and undo act on: the newest wave still waiting for the person, or None."""
        return (project_state.waiting_batch(project_state.load(self.project) or {}) or {}).get('branch')

    def _outcome(self, run, answer=None):
        """The result event's data: the new branch, its diff and its checks, the cards it closes, and the assistant's words."""
        record = self.store.load(run)
        state = project_state.load(self.project) or {}
        fresh = [] if record.get('read') else _fresh_waves(record, state)   # a reading run hands no batch over
        wave = next((w for w in reversed(fresh) if w.get('status') == 'applied'), None)
        landed = None if wave else _landed(fresh)
        out = {'branch': None, 'diff_stat': None, 'tests': None, 'cards_closed': [], 'indicators': [], 'answer': answer}
        if landed: out.update(_landed_outcome(landed))
        if wave: self._wave_outcome(run, wave, state, out)
        return out

    def _wave_outcome(self, run, wave, state, out):
        """A batch handed over as a branch: its tip, the branch it merges into, its record, its checks and its diff."""
        out['branch'] = wave['branch']
        out['branch_tip'] = subprocess.run(['git', '-C', str(self.project), 'rev-parse', '--verify', '--quiet', f"refs/heads/{wave['branch']}^{{commit}}"],
                                           capture_output=True, text=True).stdout.strip() or None
        out['target'] = state.get('branch') or state.get('home_branch')
        if self.branch_control:
            self.branch_control.record(wave['branch'], kind='build' if wave.get('via') == 'build' else 'wave', run=run,
                                       tip=out['branch_tip'], base=out['target'], base_commit=wave.get('base'))
        kept = list(wave.get('kept') or [])
        out['cards_closed'] = kept
        out['tests'] = prompts.batch_tests(kept, wave.get('failed') or {})
        out['diff_stat'] = _diff_stat(self.project, wave['branch'])
