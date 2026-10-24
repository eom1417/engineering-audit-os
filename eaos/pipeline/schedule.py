"""Run the declared stages as soon as they may, several at once.

A stage starts once every stage it waits for has ended (stages.WAITS: what it requires and reads, what it gathers, and
the declared order of an amended artifact), never beside a stage holding what it uses (stages.RESOURCES: the running
app, the memory, the whole machine), never beside more AI stages than the mode allows, and never while this computer
has no room left for it (room(): free memory, processors not saturated); one stage always runs, so a small computer
is slower, never stuck. Every edge of WAITS points
to an earlier stage, so one stage at a time is the declared order itself: there is no second way to run a check.

    normal   every stage that may runs at once, the AI stages one after the other, one assistant at a time
    speed    the AI stages too, and each AI stage's batches on several assistants at once (assistants())
    one      one stage at a time, in the declared order: the proof that the others find exactly the same
"""
import contextvars
import heapq
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait

from .stages import BY_NAME, WAITS
from ..core.resources import RESERVE_MB, STARTING, WAIT, capacity, room
from ..core.process import STOP, check_cancelled

MODES = ('normal', 'speed', 'one')
MOST_ASSISTANTS = 5          # past the card triage's five batches more assistants save a minute and cost a program each
ASSISTANT_MB = 768           # headroom per assistant process and its conversation
NEED_MB = {'memory': 1536, 'app': 1024}   # the most a stage holding it takes: an analyzer; the app and its browser
LIGHT_MB = 256               # a stage reading and writing records


def need(stage):
    """The megabytes a stage may take while it runs."""
    return max([NEED_MB.get(resource, 0) for resource in stage.uses + (('app',) if stage.apart else ())]
               + [ASSISTANT_MB if stage.ai else LIGHT_MB])


class Assistants(threading.BoundedSemaphore):
    """How many assistants answer at once in this check: an AI stage's batches each take one while they are asked, and
    a second one only once there is room() for it."""

    def __init__(self, count):
        super().__init__(count)
        self.count, self.answering, self.began, self._guard = count, 0, [], threading.Lock()

    def __enter__(self):
        super().__enter__()
        try:
            while True:
                with self._guard:
                    # an assistant started in the last seconds holds memory the free memory does not show yet
                    self.began = [at for at in self.began if time.monotonic() - at < STARTING]
                    if not self.answering or room(ASSISTANT_MB * (1 + len(self.began))):
                        self.answering += 1
                        self.began.append(time.monotonic())
                        return self
                check_cancelled()
                time.sleep(WAIT)
        except BaseException:
            self.release()
            raise

    def __exit__(self, *problem):
        with self._guard: self.answering -= 1
        return super().__exit__(*problem)


def assistants(mode):
    """One assistant normally; in speed mode only as many as the container's available memory can safely hold."""
    if mode != 'speed': return Assistants(1)
    _, memory, available = capacity()
    megabytes = min(memory or 0, available or 0) // 2 ** 20
    return Assistants(max(1, min(MOST_ASSISTANTS, (megabytes - RESERVE_MB) // ASSISTANT_MB)))


def width(mode):
    """The stages that may run at once: one, or as many as this computer has processors; room() decides how many do."""
    return 1 if mode == 'one' else max(2, capacity()[0])


class LimitedProvider:
    """The provider's calls share the node launchers' slots, including parallel translation batches."""

    def __init__(self, provider, slots):
        self.provider, self.slots = provider, slots

    def __getattr__(self, name): return getattr(self.provider, name)

    def complete(self, *args, **kwargs):
        with self.slots:
            check_cancelled()
            return self.provider.complete(*args, **kwargs)


def _clashes(stage, taken, mode):
    """Whether `stage` may not start beside the stages `taken`: one holds what it uses or the whole machine, it needs the
    whole machine and one runs, or it would be a second AI stage outside speed mode."""
    held = {resource for other in taken for resource in other.uses}
    return bool(set(stage.uses) & held or 'machine' in held or ('machine' in stage.uses and taken)
                or (stage.ai and mode != 'speed' and any(other.ai for other in taken)))


def ready_stages(left, ended, running, mode, room, quick=()):
    """The stages of `left`, in the declared order, that may start now beside `running`: all they wait for has ended,
    they clash with nothing running (_clashes), and at most `room` of them. A stage of `quick` only settles its row
    (resumed, not requested): it holds nothing."""
    taken, chosen = [BY_NAME[name] for name in running if name not in quick], []
    for name in left:
        if len(chosen) >= room: break
        if not WAITS[name] <= ended: continue
        if name not in quick:
            if _clashes(BY_NAME[name], taken, mode): continue
            taken.append(BY_NAME[name])
        chosen.append(name)
    return chosen


def run_ready(names, start, mode='normal', quick=()):
    """start(name) for every name of `names` (the declared stages, in order), each once ready_stages lets it. A stage
    that raises stops the run: the stages already running end, none starts, and the error goes on."""
    if mode not in MODES: raise ValueError(f'Unknown check mode: {mode}')
    stopped = threading.Event()
    token = STOP.set(stopped)
    try:
        _run_ready(names, start, mode, quick, stopped)
    finally: STOP.reset(token)


def _run_ready(names, start, mode, quick, stopped):
    """One scheduler at any width; on interruption signal every running stage before waiting for it to release."""
    left, ended, running, began = list(names), set(), {}, {}
    with ThreadPoolExecutor(max_workers=width(mode), thread_name_prefix='eaos-stage') as pool:
        try:
            while left or running:
                waiting = False
                for name in ready_stages(left, ended, running.values(), mode, width(mode) - len(running), quick):
                    # no room for it yet: a lighter stage behind it may still start (it never waits for this one)
                    if _no_room(name, running.values(), began, quick):
                        waiting = True
                        continue
                    left.remove(name)
                    began[name] = time.monotonic()
                    running[pool.submit(contextvars.copy_context().run, start, name)] = name
                if not running: raise ValueError('Stages cannot run: their prerequisites are missing')
                done, _ = wait(running, timeout=WAIT if waiting else None, return_when=FIRST_COMPLETED)
                for future in done:
                    ended.add(running.pop(future))
                    future.result()
        except BaseException:
            stopped.set()
            for future in running: future.cancel()
            raise


def _no_room(name, running, began, quick):
    """Whether `name` waits for room: others run, it holds something (not `quick`), and the computer has no room for it
    beside them and what they are starting."""
    return bool(running) and name not in quick and not room(need(BY_NAME[name]) + _starting(running, began))


def _starting(running, began):
    """The megabytes of the stages just started, which the free memory does not show yet."""
    return sum(need(BY_NAME[name]) for name in running if time.monotonic() - began[name] < STARTING)


def forecast(costs, mode='normal'):
    """Seconds until every stage of `costs` ({stage: its seconds}, the others ended) has ended, run as run_ready runs
    them: the longest chain of what waits for what and what holds what, not their sum."""
    left, ended, running, clock = [name for name in WAITS if name in costs], set(WAITS) - set(costs), [], 0.0
    while left or running:
        for name in ready_stages(left, ended, [name for _, name in running], mode, width(mode) - len(running)):
            left.remove(name)
            heapq.heappush(running, (clock + costs[name], name))
        clock, name = heapq.heappop(running)
        ended.add(name)
    return clock
