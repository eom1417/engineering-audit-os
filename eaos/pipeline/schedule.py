"""Run the declared stages as soon as they may, several at once.

A stage starts once every stage it waits for has ended (stages.WAITS: what it requires and reads, what it gathers, and
the declared order of an amended artifact), never beside a stage holding what it uses (stages.RESOURCES: the running
app, the memory, the whole machine), and never beside more AI stages than the mode allows. Every edge of WAITS points
to an earlier stage, so one stage at a time is the declared order itself: there is no second way to run a check.

    normal   every stage that may runs at once, the AI stages one after the other, one assistant at a time
    speed    the AI stages too, and each AI stage's batches on several assistants at once (assistants())
    one      one stage at a time, in the declared order: the proof that the others find exactly the same
"""
import contextvars
import os
import threading
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait

from .stages import BY_NAME, WAITS

MODES = ('normal', 'speed', 'one')
MOST_ASSISTANTS = 5          # past the card triage's five batches more assistants save a minute and cost a program each
ASSISTANT_MB = 1000          # one assistant per GB of memory: it is a separate program, with its conversation in memory


class Assistants(threading.BoundedSemaphore):
    """How many assistants answer at once in this check: an AI stage's batches each take one while they are asked."""

    def __init__(self, count):
        super().__init__(count)
        self.count = count


def assistants(mode):
    """The assistants a check may run at once: one, or in speed mode one per GB of this computer's memory, at most
    MOST_ASSISTANTS."""
    if mode != 'speed': return Assistants(1)
    try: megabytes = os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES') // 2 ** 20
    except (ValueError, OSError, AttributeError): megabytes = ASSISTANT_MB
    return Assistants(max(1, min(MOST_ASSISTANTS, megabytes // ASSISTANT_MB)))


def width(mode):
    """The stages that run at once: one, or as many as this computer has processors (what they use keeps the heavy
    ones apart)."""
    return 1 if mode == 'one' else max(2, os.cpu_count() or 2)


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
    if width(mode) == 1:
        for name in names: start(name)
        return
    left, ended, running = list(names), set(), {}
    with ThreadPoolExecutor(max_workers=width(mode), thread_name_prefix='eaos-stage') as pool:
        while left or running:
            for name in ready_stages(left, ended, running.values(), mode, width(mode) - len(running), quick):
                left.remove(name)
                running[pool.submit(contextvars.copy_context().run, start, name)] = name
            done, _ = wait(running, return_when=FIRST_COMPLETED)
            for future in done:
                ended.add(running.pop(future))
                future.result()
