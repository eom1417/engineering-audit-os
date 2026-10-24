"""The loops' runner over one check run (eaos/pipeline/loops.py): the scheduler (schedule.py run_ready) asks it what a
stage sees ended and, as each stage ends, which stages run again. When the last stage of a loop ends its exit is
judged; a loop not met runs the stages it broke again while its rounds last, then settles with its outcome, which the
manifest keeps (`loops`) and the coverage ledger reads (eaos/report/coverage_ledger.py)."""
from .live_app import PAGE_STAGES, close_app
from .loops import BROKEN, BY_NAME, LOOP_OF, LOOPS, NOT_MET, outcome


class Rounds:
    def __init__(self, run):
        self.run, self.rounds, self.settled = run, {}, {}

    def seen(self, name, ended):
        """What stage `name` sees ended: all of `ended` but what a loop of another, which may still run again, broke."""
        mine = LOOP_OF.get(name)
        with self.run['lock']: rows = dict(self.run['results'])
        return ended - {stage for loop in LOOPS if loop.name != mine and loop.max_rounds > 1 and loop.name not in self.settled
                        for stage in loop.stages if (rows.get(stage) or {}).get('status') in BROKEN}

    def ended(self, name, ended):
        """The stages to run again now that `name` ended: its loop's broken ones, when all its stages ended, its exit is
        not met and a round is left; else none, and the loop settles once all its stages ended."""
        loop = BY_NAME.get(LOOP_OF.get(name))
        if loop is None or loop.name in self.settled or not set(loop.stages) <= ended: return []
        with self.run['lock']:
            state, behind = outcome(loop, self.run['results'])
            done = self.rounds.get(loop.name, 1)
            again = self._again(loop, behind) if state == NOT_MET and done < loop.max_rounds else []
            if again:
                self.rounds[loop.name] = done + 1
                return again
            self.settled[loop.name] = {'state': state, 'stages': behind, 'rounds': done,
                                       **({'on_fail': loop.on_fail} if state == NOT_MET else {})}
            if state == NOT_MET and loop.on_fail == 'stop': self.run['stopped_by'] = loop.name
        return []

    def _again(self, loop, failed):
        """The broken stages of `loop`, their rows and what they blocked cleared, when one of them failed itself (`failed`:
        a stage only not reached behind another loop's would not reach it again); the shared app closed when a page
        stage is among them, so the next round starts it afresh."""
        results, blocked = self.run['results'], self.run['blocked']
        if not any(results[name]['status'] == 'failed' for name in failed): return []
        broken = [name for name in loop.stages if results[name]['status'] in BROKEN]
        for name in broken: results.pop(name, None)
        _unblock(blocked, broken)
        if PAGE_STAGES & set(broken) or 'setup' in broken: close_app(self.run['context'])
        return broken

    def record(self):
        """{loop: its outcome} of every loop, in the declared order; a loop that never settled (the run stopped first)
        is left out."""
        return {loop.name: self.settled[loop.name] for loop in LOOPS if loop.name in self.settled}


def _unblock(blocked, broken):
    """What the `broken` stages blocked, and what blocked them but a stage (a stop, missing prerequisites), cleared."""
    for name in [name for name, (_, _, cause) in blocked.items() if cause in broken or (name in broken and cause is None)]:
        del blocked[name]
