"""oasdiff: what the last change to each OpenAPI specification broke for the clients that call it.

The specification is compared with its own previous version in the project's history (the commit
before the last one that changed the file), read with `git show`; nothing in the project is written.
A specification with no earlier version is examined and has nothing to compare, which the coverage says.
"""
import json
from pathlib import Path

from . import openapi, tool
from .contract import ERROR, OBSERVED, Report, finding, measurement, subject
from .process import run, which

NAME = BINARY = 'oasdiff'
PINNED = tool.pinned(NAME)
LEVELS = {3: 'high', 2: 'medium', 1: 'low'}


def capabilities():
    from .contract import Capability
    return [Capability('api_contract', 'oasdiff.breaking')]


def version():
    return tool.version(BINARY)


def analyze(target, workdir, exclude=(), formats=None):
    declined = tool.declined(NAME, BINARY, target)
    if declined: return declined
    found = version()
    target = Path(target).resolve()
    workdir = Path(workdir) / NAME
    workdir.mkdir(parents=True, exist_ok=True)
    findings, compared, seconds = [], {}, 0.0
    for index, spec in enumerate(openapi.specifications(target, exclude)):
        commit, text = openapi.previous(target, spec)
        if commit is None:
            compared[spec] = 'no earlier version in history'
            continue
        base = workdir / f'base-{index}{Path(spec).suffix}'
        base.write_text(text, encoding='utf-8')
        code, out, error, spent = run([which(BINARY), 'breaking', str(base), str(target / spec), '-f', 'json'])
        seconds += spent
        if code:
            return Report(NAME, found, PINNED, ERROR, seconds=seconds, reason=f'{spec}: ' + (error.strip()[-300:] or f'exit {code}'))
        changes = json.loads(out or '[]') or []
        compared[spec] = f'against {commit[:12]}: {len(changes)} breaking change(s)'
        for change in changes:
            where = f"{change.get('operation', '')} {change.get('path', '')}".strip()
            findings.append(finding(NAME, found, change['id'], 'api_contract', subject('operation', f'{spec}:{where}:{change["id"]}', spec),
                                    f"{where}: {change.get('text', change['id'])} (since {commit[:12]})",
                                    measurements=[measurement('severity', LEVELS.get(change.get('level'), 'medium'))],
                                    raw_ref=f'{NAME}/base-{index}'))
    return Report(NAME, found, PINNED, OBSERVED, seconds=seconds, findings=findings,
                  coverage={'status': 'observed', 'specifications': compared},
                  evaluated={'api_contract': {'status': 'observed', 'granularity': 'file'}})
