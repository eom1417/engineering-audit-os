"""Files in another tool's own format, written from the facts, and judged by that tool.

EAOS does not rewrite k6, Playwright or an OpenTelemetry Collector; it writes their input (a script, a spec,
a configuration) and asks the tool itself whether it accepts it. Each emitter returns the files it wrote,
relative to the report; each file names the validator that judges it. `emit` runs the emitters that apply,
and with validate=True writes handover/validation.json (schemas/artifacts/handover-validation.schema.json):
one row per file, with the tool's verdict. A validator that is not installed is a failure, not a pass.
"""
from dataclasses import dataclass
from pathlib import Path
from string import Template

TEMPLATES = Path(__file__).resolve().parent.parent / 'templates/emit'


@dataclass(frozen=True)
class Emitted:
    path: str           # relative to the report directory
    tool: str           # the tool that judges it, a name in upstreams/toolchain.json or a schema check
    argv: tuple = ()    # the validator command; '{path}' is replaced by the absolute file path


def render(template, **values):
    """A template from eaos/templates/emit/, filled with string.Template: $name, and $$ for a literal dollar."""
    return Template((TEMPLATES / template).read_text(encoding='utf-8')).substitute(**values)


def handover_readme(report):
    """The index of the handover kit: every file it holds, and the tool that accepted each."""
    target = Path(report) / 'handover/README.md'
    folder = target.parent
    folder.mkdir(parents=True, exist_ok=True)
    files = sorted(p.relative_to(folder).as_posix() for p in folder.rglob('*')
                   if p.is_file() and p.name not in ('README.md', 'validation.json'))
    listing = '\n'.join(f'- `{name}`' for name in files) or '- (no generated file yet)'
    target.write_text(render('handover/README.md', listing=listing), encoding='utf-8')
    return [Emitted('handover/README.md', 'markdownlint-cli2', ('markdownlint-cli2', '{path}'))]


# name -> function(report_dir) -> [Emitted]. An emitter that does not apply returns [].
EMITTERS = {'handover-readme': handover_readme}


def emit(report, only=None, validate=False):
    """Run the emitters (all, or `only`), and with validate=True record each file's verdict."""
    from .validate import record, verdict
    written = []
    # The handover index runs last, so it lists what every other emitter wrote.
    for name in sorted(EMITTERS, key=lambda name: name == 'handover-readme'):
        if only and name not in only: continue
        written += EMITTERS[name](report)
    rows = [verdict(report, item) for item in written] if validate else []
    if validate: record(report, rows)
    return written, rows
