"""Shared by the progress-contract tests: the schema, the fake runners, the clock, and the row checks."""
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests'))
sys.path.insert(0, str(ROOT / 'tools'))
import jsonschema  # noqa: E402
from eaos.core import progress  # noqa: E402
from eaos.pipeline import execute  # noqa: E402
from pipeline.test_run import fake_runners  # noqa: E402
from shared_fixture import scratch  # noqa: E402
FIXTURES = ROOT / 'tests/fixtures/progress'
SCHEMA = json.loads((ROOT / 'eaos/data/schemas/progress.json').read_text(encoding='utf-8'))
VALIDATOR = jsonschema.Draft202012Validator(SCHEMA, format_checker=jsonschema.Draft202012Validator.FORMAT_CHECKER)
GOLDEN = sorted(FIXTURES.glob('*.jsonl'))


FIXTURES = ROOT / 'tests/fixtures/progress'


SCHEMA = json.loads((ROOT / 'eaos/data/schemas/progress.json').read_text(encoding='utf-8'))


VALIDATOR = jsonschema.Draft202012Validator(SCHEMA, format_checker=jsonschema.Draft202012Validator.FORMAT_CHECKER)


GOLDEN = sorted(FIXTURES.glob('*.jsonl'))


def stepping_runners(**behaviour):
    """The fake runners, with `facts` and `engines` reporting steps the way the real ones do."""
    runners = fake_runners(**behaviour)
    plain_facts, plain_engines = runners['facts'], runners['engines']

    def facts(context):
        names = ['syntax', 'resolve', 'graph']
        for name in names: context.step(name, 0, len(names), 'waiting')
        for done, name in enumerate(names):
            context.step(name, done, len(names), 'running')
            context.step(name, done + 1, len(names), 'ok', 0.01)
        return plain_facts(context)

    def engines(context):
        context.step('semgrep', 0, 2, 'waiting')
        context.step('trivy', 0, 2, 'waiting')
        context.step('semgrep', 0, 2, 'running')
        context.step('semgrep', 1, 2, 'observed', 0.2)
        context.step('trivy', 1, 2, 'running')
        context.step('trivy', 2, 2, 'unavailable', 0.0, reason='trivy is not installed')
        return plain_engines(context)

    runners.update(facts=facts, engines=engines)
    return runners


def project():
    folder = Path(scratch(prefix='scanmap-src-'))
    (folder / 'app.py').write_text('print(1)\n', encoding='utf-8')
    return folder


class Clock:
    """Monotonic seconds that move only when the test says so."""

    def __init__(self): self.at = 1000.0
    def __call__(self): return self.at
    def move(self, seconds): self.at += seconds


def invalid(rows):
    return [(row.get('seq'), row.get('event'), error.message) for row in rows for error in VALIDATOR.iter_errors(row)]


def counting_runners(**behaviour):
    """The stepping runners, with `plan` counting a loop through progress.count() the way deep code does."""
    runners = stepping_runners(**behaviour)
    plain = runners['plan']

    def plan(context):
        for done in range(0, 157): progress.count('codemod trial', done, 156)
        progress.count('debt items', 500, 454)             # more than declared: held at total
        progress.count('homes', -3, 642)                   # less than nothing: held at 0
        return plain(context)

    runners['plan'] = plan
    return runners


def check_rows(**options):
    out = Path(scratch(prefix='progress-out-'))
    try: execute(project(), out, **options)
    except BaseException as problem: options['raised'] = problem
    return progress.read(out), options.get('raised'), out


def ends(rows):
    return [r['stage'] for r in rows if r['event'] == 'stage.ended']
