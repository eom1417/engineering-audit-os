"""A parallel check finds exactly what one stage at a time finds (eaos/pipeline/schedule.py).

That holds only while every stage waits for what it reads: a read of another stage's artifact that its declaration
does not name (stages.WAITS) runs right today only because of the order, and races once stages run side by side. The
fixture's check is run once with every file each stage opens recorded, so a new undeclared read or rewrite fails
here, and once in parallel, which must leave the same claims, cards and files.
"""
import ast
import hashlib
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

from eaos.pipeline import runners as stage_runners
from eaos.pipeline.run import execute
from eaos.pipeline.schedule import forecast, ready_stages
from eaos.pipeline.stages import BY_NAME, ORDER, STAGES, WAITS

FIXTURE = Path(__file__).parent / 'fixtures/polyglot'
STAMPS = ('created_at', 'produced_at', 'ran_at', '"out"', 'generated_at')       # when and where, never what was found


class _Opens:
    """Every file under `out` each stage opens, by the stage that opened it (an audit hook, so nothing is patched)."""

    def __init__(self, out):
        self.out, self.stage, self.read, self.wrote = Path(out).resolve(), threading.local(), {}, {}
        sys.addaudithook(self._hook)

    def _hook(self, event, args):
        stage = getattr(self.stage, 'name', None)
        if event != 'open' or not stage or not isinstance(args[0], (str, Path)): return
        try: relative = Path(args[0]).resolve().relative_to(self.out).as_posix()
        except ValueError: return
        writing = isinstance(args[1], str) and any(mark in args[1] for mark in 'wax+')
        (self.wrote if writing else self.read).setdefault(stage, set()).add(relative.removesuffix('.tmp'))

    def runners(self):
        def watched(name, runner):
            def run(context):
                self.stage.name = name
                try: return runner(context)
                finally: self.stage.name = None
            return run
        return {name: watched(name, runner) for name, runner in stage_runners.RUNNERS.items()}


def _checked(directory, mode, opens=None):
    project = Path(directory) / 'project'
    if not project.exists():
        shutil.copytree(FIXTURE, project)
        subprocess.run('git init -q && git add -A && git -c user.email=t@t -c user.name=t commit -qm fixture', shell=True,
                       cwd=project, check=True)
    out = Path(directory) / mode
    if opens: opens.out = out.resolve()
    manifest = execute(project, out, language='en', mode=mode, **({'runners': opens.runners()} if opens else {}))
    return manifest, out


def _under():
    """{stage: every stage it waits for, and what those wait for}: all of them have ended when it starts."""
    under = {}
    for stage in STAGES: under[stage.name] = {w for name in WAITS[stage.name] for w in (name, *under[name])}
    return under


def _contents(out):
    """{file: digest} of every record of a report, its own folder named alike and the lines that only say when or
    where left out."""
    found = {}
    for path in sorted(Path(out).rglob('*')):
        if path.is_file() and path.suffix in ('.json', '.md') and not path.name.startswith(('run-', 'report-result')):
            text = path.read_text(encoding='utf-8').replace(str(Path(out).resolve()), '<out>')
            kept = [line for line in text.splitlines() if not any(s in line for s in STAMPS)]
            found[path.relative_to(out).as_posix()] = hashlib.sha256('\n'.join(kept).encode()).hexdigest()
    return found


class ParallelCheckTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.opens = _Opens(cls.directory.name)
        cls.one, cls.one_out = _checked(cls.directory.name, 'one', cls.opens)
        cls.parallel, cls.parallel_out = _checked(cls.directory.name, 'normal')

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def test_every_read_and_rewrite_of_another_stage_is_declared(self):
        maker, under = {artifact: stage.name for stage in STAGES for artifact in stage.produces}, _under()
        # a stage may read what a later stage made in the last check (it runs after it either way), never what a stage
        # beside it is making
        undeclared = sorted(f'{stage} reads {path} of {maker[path]}' for stage, paths in self.opens.read.items() for path in paths
                            if maker.get(path, stage) != stage and maker[path] not in under[stage] and stage not in under[maker[path]])
        self.assertEqual(undeclared, [], 'declare each in the reading stage (requires, reads or gathers)')
        rewrites = sorted(f'{stage} rewrites {path} of {maker[path]}' for stage, paths in self.opens.wrote.items() for path in paths
                          if maker.get(path, stage) != stage and path not in BY_NAME[stage].amends)
        self.assertEqual(rewrites, [], "declare each in the rewriting stage's amends")

    def test_a_parallel_check_finds_exactly_what_one_stage_at_a_time_finds(self):
        self.assertEqual({k: v['status'] for k, v in self.parallel['stages'].items()},
                         {k: v['status'] for k, v in self.one['stages'].items()})
        parallel, one = _contents(self.parallel_out), _contents(self.one_out)
        self.assertEqual(sorted(name for name in parallel.keys() | one.keys() if parallel.get(name) != one.get(name)), [])
        self.assertEqual(self.parallel['mode'], 'normal')

    def test_each_stage_asks_of_the_run_only_what_it_waits_for(self):
        """_ran(context, name) reads the run's results while other stages run: only a stage it waits for has surely ended."""
        tree = ast.parse(Path(stage_runners.__file__).read_text(encoding='utf-8'))
        functions = {f.name: f for f in tree.body if isinstance(f, ast.FunctionDef)}
        def asked(function, seen):
            names = set()
            for node in ast.walk(function):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    if node.func.id == '_ran': names.add(node.args[1].value)
                    elif node.func.id in functions and node.func.id not in seen:
                        names |= asked(functions[node.func.id], seen | {node.func.id})
            return names
        under = _under()
        unwaited = {name: sorted(asked(functions[runner.__name__], {runner.__name__}) - under[name])
                    for name, runner in stage_runners.RUNNERS.items() if runner.__name__ in functions}
        self.assertEqual({k: v for k, v in unwaited.items() if v}, {})


class ReadyStagesTests(unittest.TestCase):
    def test_what_a_stage_holds_keeps_the_others_apart(self):
        ended = set(ORDER[:ORDER.index('setup') + 1]) | {'lock', 'intake', 'record'}
        left = [n for n in ORDER if n not in ended]
        ready = ready_stages(left, ended, [], 'normal', 10)
        self.assertEqual(sum('app' in BY_NAME[n].uses for n in ready), 1, 'one stage at a time runs the app')
        self.assertNotIn('baseline', ready_stages(left, ended, ['engines'], 'normal', 10), 'the load test runs alone')
        self.assertEqual(ready_stages(['measure'], ended, ['baseline'], 'normal', 10), [], 'nothing runs beside it')
        thinking = set(ORDER) - {'triage', 'visual', 'ideal'}
        self.assertEqual(ready_stages(['visual'], thinking, ['triage'], 'normal', 10), [])
        self.assertEqual(ready_stages(['visual'], thinking, ['triage'], 'speed', 10), ['visual'])
        self.assertEqual(ready_stages(left, ended, [], 'one', 1), [left[0]] if WAITS[left[0]] <= ended else [])

    def test_the_time_a_check_takes_is_its_longest_chain_not_its_sum(self):
        costs = {name: 10.0 for name in ORDER}
        self.assertEqual(forecast(costs, 'one'), 10.0 * len(ORDER))
        self.assertLess(forecast(costs, 'normal'), 10.0 * len(ORDER))
        self.assertLessEqual(forecast(costs, 'speed'), forecast(costs, 'normal'))
        self.assertEqual(forecast({'facts': 5.0, 'measure': 3.0}, 'normal'), 8.0, 'what waits waits')
