"""Run each emitted file past its own tool and record the verdict in handover/validation.json."""
import json
import os
import subprocess
from pathlib import Path

from ..engines.process import which


def verdict(report, emitted):
    """One row of handover/validation.json for one emitted file."""
    path = Path(report) / emitted.path
    row = {'path': emitted.path, 'tool': emitted.tool}
    if not emitted.argv:
        return {**row, 'ok': path.is_file(), 'reason': 'no validator: the file exists'}
    binary = which(emitted.argv[0])
    if not binary:
        return {**row, 'ok': False, 'reason': f'validator unavailable: {emitted.argv[0]}'}
    argv = [binary] + [str(path) if part == '{path}' else part for part in emitted.argv[1:]]
    try:
        # Node validators load their packages (@playwright/test) from the pinned tools prefix, not the project.
        from ..toolchain import home
        node = str(home() / 'node/node_modules')
        done = subprocess.run(argv, cwd=path.parent, capture_output=True, text=True, timeout=300,
                              env={**os.environ, 'NO_COLOR': '1',
                                   'NODE_PATH': os.pathsep.join(p for p in (node, os.environ.get('NODE_PATH')) if p)})
    except (OSError, subprocess.TimeoutExpired) as problem:
        return {**row, 'command': ' '.join(argv), 'ok': False, 'reason': str(problem)}
    return {**row, 'command': ' '.join(argv), 'ok': done.returncode == 0,
            'output': (done.stdout + done.stderr).strip()[-2000:]}


def record(report, rows):
    """Merge the new verdicts into handover/validation.json, replacing earlier rows for the same files."""
    target = Path(report) / 'handover/validation.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    kept = []
    if target.is_file():
        new = {row['path'] for row in rows}
        kept = [row for row in json.loads(target.read_text(encoding='utf-8')).get('files', []) if row['path'] not in new]
    files = sorted(kept + rows, key=lambda row: row['path'])
    target.write_text(json.dumps({'schema_version': 1, 'files': files}, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    return files
