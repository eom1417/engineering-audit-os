"""Spectral: every OpenAPI specification in the project linted against the OpenAPI ruleset.

It applies only where a specification exists; elsewhere it is not applicable.
"""
from pathlib import Path

from . import openapi, sarif, tool
from .contract import ERROR, OBSERVED, Report
from .process import run, which

NAME = BINARY = 'spectral'
PINNED = tool.pinned(NAME)


def capabilities():
    from .contract import Capability
    return [Capability('api_contract', 'spectral:oas')]


def version():
    return tool.version(BINARY)


def analyze(target, workdir, exclude=(), formats=None):
    declined = tool.declined(NAME, BINARY, target)
    if declined: return declined
    found = version()
    target = Path(target).resolve()
    workdir = Path(workdir) / NAME
    workdir.mkdir(parents=True, exist_ok=True)
    ruleset = workdir / 'ruleset.yaml'
    ruleset.write_text('extends: ["spectral:oas"]\n', encoding='utf-8')
    specs = openapi.specifications(target, exclude)
    findings, unmapped, seconds = [], {}, 0.0
    for index, spec in enumerate(specs):
        output = workdir / f'spectral-{index}.sarif'
        # Spectral exits 1 when a rule fails; that is a result, not a failure.
        code, _, error, spent = run([which(BINARY), 'lint', spec, '--ruleset', str(ruleset), '-f', 'sarif', '-o', str(output),
                                     '--quiet'], cwd=target)
        seconds += spent
        if code not in (0, 1) or not output.is_file():
            return Report(NAME, found, PINNED, ERROR, seconds=seconds, reason=f'{spec}: ' + (error.strip()[-300:] or f'exit {code}'))
        sarif.relativise(output, target)
        more, missed = sarif.read(output, NAME, found)
        findings += more
        for rule, count in missed.items(): unmapped[rule] = unmapped.get(rule, 0) + count
    return Report(NAME, found, PINNED, OBSERVED, seconds=seconds, findings=findings, unmapped=unmapped,
                  coverage={'status': 'observed', 'specifications': specs, 'ruleset': 'spectral:oas'},
                  evaluated={'api_contract': {'status': 'observed', 'granularity': 'file'}})
