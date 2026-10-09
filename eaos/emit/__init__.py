"""Files in another tool's own format, written from the facts, and judged by that tool.

EAOS does not rewrite k6, Playwright or an OpenTelemetry Collector; it writes their input (a script, a spec,
a configuration) and asks the tool itself whether it accepts it. Each emitter returns the files it wrote,
relative to the report; each file names the validator that judges it. `emit` runs the emitters that apply,
and with validate=True writes handover/validation.json (schemas/artifacts/handover-validation.schema.json):
one row per file, with the tool's verdict. A validator that is not installed is a failure, not a pass.
"""
from pathlib import Path

from .. import progress

from .base import TEMPLATES, Emitted, render  # noqa: F401  (the emitters' shared vocabulary)


def handover_readme(report):
    """The index of the handover kit: every file it holds, and the tool that accepted each."""
    target = Path(report) / 'handover/README.md'
    folder = target.parent
    folder.mkdir(parents=True, exist_ok=True)
    # site/ is the built handover site (zensical build), not a file of the kit
    files = sorted(p.relative_to(folder).as_posix() for p in folder.rglob('*')
                   if p.is_file() and p.name not in ('README.md', 'validation.json') and not p.relative_to(folder).as_posix().startswith('site/'))
    listing = '\n'.join(f'- `{name}`' for name in files) or '- (no generated file yet)'
    target.write_text(render('handover/README.md', listing=listing), encoding='utf-8')
    return [Emitted('handover/README.md', 'markdownlint-cli2', ('markdownlint-cli2', '{path}'))]


def behavior_lock(report):
    """The lock stage's specs, each put to its own tool: Playwright loads every spec (`test --list`, no browser),
    and Python compiles every approval test. This emitter writes nothing; eaos/behavior_lock.py did."""
    import sys
    root = Path(report) / 'behavior-lock'
    items = []
    if (root / 'playwright.config.ts').is_file():
        items.append(Emitted('behavior-lock/playwright.config.ts', 'playwright', ('playwright', 'test', '--list', '--reporter=list', '--config', '{path}')))
    for path in sorted((root / 'approvals').glob('test_*.py')) if (root / 'approvals').is_dir() else []:
        items.append(Emitted(path.relative_to(report).as_posix(), 'python', (sys.executable, '-m', 'py_compile', '{path}')))
    return items


# name -> function(report_dir) -> [Emitted]. An emitter that does not apply returns [].
def adr_files(report):
    """The MADR files the target stage wrote (eaos/adr.py), each put to markdownlint; this writes nothing."""
    folder = Path(report) / 'adr'
    return [Emitted(path.relative_to(report).as_posix(), 'markdownlint-cli2', ('markdownlint-cli2', '{path}'))
            for path in sorted(folder.glob('ADR-*.md'))] if folder.is_dir() else []


def c4_models(report):
    from ..c4 import write
    return write(report)


def nfr_plans(report):
    from .nfr import write
    return write(report)


def governance_kit(report):
    from .governance import write
    return write(report)


def observability_kit(report):
    from .observability import write
    return write(report)


def readiness_kit(report):
    from .readiness import write
    return write(report)


def handover_site_kit(report):
    from .handover_site import write
    return write(report)


EMITTERS = {'handover-readme': handover_readme, 'behavior-lock': behavior_lock, 'nfr': nfr_plans, 'c4': c4_models, 'adr': adr_files,
            'governance': governance_kit, 'observability': observability_kit, 'readiness': readiness_kit, 'site': handover_site_kit}


def emit(report, only=None, validate=False):
    """Run the emitters (all, or `only`), and with validate=True record each file's verdict."""
    from .validate import record, verdict
    written = []
    # The handover index runs last, so it lists what every other emitter wrote.
    names = [name for name in sorted(EMITTERS, key=lambda name: (name == 'handover-readme', name == 'site'))
             if not only or name in only]
    for done, name in enumerate(names):
        progress.count('emitters', done, len(names))
        written += EMITTERS[name](report)
    progress.count('emitters', len(names), len(names))
    rows = []
    for done, item in enumerate(written if validate else []):
        progress.count('files judged', done, len(written))
        rows.append(verdict(report, item))
    if validate: progress.count('files judged', len(written), len(written))
    if validate: record(report, rows)
    return written, rows
