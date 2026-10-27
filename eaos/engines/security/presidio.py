"""Presidio: personal values written in the project's string literals (names, phones, national ids, IBANs, e-mails, M12.1).

Presidio is a library, run in its own environment by EAOS's script (eaos/templates/presidio/scan.py) with the patterns
and placeholders of eaos/rules/personal-data.json. Each value is a measurement, not a finding: whether it is real data
in the code is decided with the tables written as code and where the file is reached from
(eaos/analysis/assessments/real_data.py). No value is ever written: only its kind, a mask and a digest.
"""
import json
from pathlib import Path

import eaos

from .. import tool
from ..contract import OBSERVED, Report
from ..process import run
from ...core.toolchain import registry
from ...core.toolchain.pins import venv_of
from ...core.toolchain.versions import found_version

NAME = BINARY = 'presidio'
PINNED = tool.pinned(NAME)
PACKAGE = Path(eaos.__path__[0]).resolve()
SCRIPT, RULES = PACKAGE / 'templates/presidio/scan.py', PACKAGE / 'rules/personal-data.json'
RECORD = 'personal_value'


def _tool():
    return next(t for t in registry()['tools'] if t['name'] == NAME)


def capabilities(): return []


def version(): return found_version(_tool())[0]


def rows(text):
    """The metrics of the scan's lines: one per personal value, at its place."""
    out = []
    for line in text.splitlines():
        if not line.strip(): continue
        hit = json.loads(line)
        out.append({'path': hit.pop('path'), 'line': hit.pop('line'), 'symbol': None, 'granularity': 'symbol',
                    'measurements': {'record': RECORD, **hit}})
    return out


def analyze(target, workdir, exclude=(), formats=None):
    declined, found = tool.started(NAME, BINARY, target, probe=version)
    if declined: return declined
    folder = tool.folder(workdir, NAME, fresh=True)
    output = folder / 'presidio.jsonl'
    python = venv_of(_tool()) / 'bin/python'
    code, out, error, seconds = run([str(python), '-I', str(SCRIPT), str(Path(target).resolve()), str(RULES), str(output),
                                     *exclude], cwd=folder)
    if code or not output.is_file():
        return tool.failed(NAME, found, seconds, code, error)
    metrics = rows(output.read_text(encoding='utf-8'))
    scanned = json.loads(out.strip().splitlines()[-1]).get('files', 0) if out.strip() else 0
    return Report(NAME, found, PINNED, OBSERVED, seconds=seconds, raw=str(output), metrics=metrics,
                  coverage={'status': 'observed', 'files': scanned, 'values': len(metrics),
                            'placeholders': sum(1 for row in metrics if row['measurements']['placeholder']),
                            'read': 'string literals only'})
