"""Progress never changes a result (live scan map v2, guarantee I6): the same check with progress on and off.

    python tools/progress_determinism.py <project> <workdir> [--engines] [--json out.json]

Runs the whole check of <project> three times, each in its own process and its own fresh report folder under
<workdir>: `on-1` and `on-2` with progress written as usual, `off` with EAOS_PROGRESS=off (no progress file, no
count or step heard, no sampler, no heartbeat). Then compares every file the runs wrote:

- the progress files themselves (run-progress.jsonl and progress/) are left out: they are what is switched;
- each run's own folder is replaced by <OUT>, and every timestamp, duration and run id is masked (TIME_PATTERNS):
  they differ between any two runs, with or without progress;
- every other byte must be equal between `on-1` and `off`. `on-2` shows what differs between two runs that both
  write progress: a file that differs between on-1 and off but also between on-1 and on-2 is the check's own
  variance, not progress, and is reported as such, never hidden.

Exit 0 when on-1 and off are byte-identical after masking; 1 otherwise. The JSON record lists the files compared,
the ones that differ, and the masks used.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SWITCHED = ('run-progress.jsonl', 'progress/')
TIME_PATTERNS = [
    (re.compile(rb'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:?\d{2}| UTC)?'), b'<TIME>'),
    (re.compile(rb'\d{8}T\d{6}(-[0-9a-f]{6})?'), b'<RUN>'),
    (re.compile(rb'"(seconds|duration|duration_ms|elapsed|took|wall_seconds|runtime_seconds)": ?-?[\d.]+(e-?\d+)?'), rb'"\1": <S>'),
    (re.compile(rb'\b\d+(\.\d+)? ?(s|ms|seconds)\b'), b'<S>'),
    (re.compile(r'\b\d+(\.\d+)? ?ثانية'.encode()), b'<S>'),
    (re.compile(rb'\| \d+\.\d+ \|'), b'| <S> |'),                              # RUN.md: a stage's seconds
    (re.compile(rb'D:\d{14}(Z|[+-]\d{2}\'?\d{2}\'?)?'), b'D:<TIME>'),          # a PDF's creation and change dates
    (re.compile(rb'/ID ?\[ ?(<[0-9A-Fa-f]+>|\([^)]*\)) ?(<[0-9A-Fa-f]+>|\([^)]*\)) ?\]'), b'/ID[<ID>]'),  # a PDF's id, from its dates
    (re.compile(rb'"(hash|config_hash)": ?-?\d+'), rb'"\1": <HASH>'),
    (re.compile(rb'<xmpMM:(InstanceID|DocumentID)>[^<]*<'), rb'<xmpMM:\1><ID><'),  # a PDF's XMP ids, from its dates          # mkdocs' cache keys, random per process
]


def run(project, out, progress_on, engines):
    """One whole check in its own process, from a folder outside the project (PYTHONSAFEPATH: this EAOS, not the
    project's code if the project is EAOS itself). Returns (seconds, exit code)."""
    env = {**os.environ, 'PYTHONSAFEPATH': '1'}
    if progress_on: env.pop('EAOS_PROGRESS', None)
    else: env['EAOS_PROGRESS'] = 'off'
    code = ('import sys\nfrom eaos.pipeline import execute\n'
            f'm = execute({str(project)!r}, {str(out)!r}, language="ar", engines={[] if engines else None!r})\n'
            'print(m["status"])\n')
    began = time.monotonic()
    done = subprocess.run([sys.executable, '-c', code], cwd=str(out.parent), env=env)
    return round(time.monotonic() - began, 1), done.returncode


def masked(path, out):
    data = path.read_bytes()
    data = data.replace(str(out).encode(), b'<OUT>')
    for pattern, replacement in TIME_PATTERNS: data = pattern.sub(replacement, data)
    return data


def files(out):
    found = {}
    for path in sorted(out.rglob('*')):
        name = path.relative_to(out).as_posix()
        if path.is_file() and not any(name == s or name.startswith(s) for s in SWITCHED):
            found[name] = path
    return found


def compare(left, right):
    a, b = files(left), files(right)
    differ = [name for name in sorted(set(a) & set(b))
              if hashlib.sha256(masked(a[name], left)).digest() != hashlib.sha256(masked(b[name], right)).digest()]
    return {'only_left': sorted(set(a) - set(b)), 'only_right': sorted(set(b) - set(a)), 'differ': differ, 'compared': len(set(a) & set(b))}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('project')
    parser.add_argument('workdir')
    parser.add_argument('--engines', action='store_true', help='run the external engines too (the guided check does)')
    parser.add_argument('--json', help='write the record here')
    args = parser.parse_args(argv)
    project, work = Path(args.project).resolve(), Path(args.workdir).resolve()
    work.mkdir(parents=True, exist_ok=True)
    runs = {}
    for name, on in (('on-1', True), ('off', False), ('on-2', True)):
        out = work / name
        if out.exists(): subprocess.run(['rm', '-rf', str(out)], check=True)
        seconds, code = run(project, out, on, args.engines)
        runs[name] = {'seconds': seconds, 'exit': code, 'progress_file': (out / 'run-progress.jsonl').is_file()}
    progress_vs_off = compare(work / 'on-1', work / 'off')
    run_vs_run = compare(work / 'on-1', work / 'on-2')
    identical = not (progress_vs_off['only_left'] or progress_vs_off['only_right'] or progress_vs_off['differ'])
    record = {'project': str(project), 'engines': args.engines, 'runs': runs,
              'on_vs_off': progress_vs_off, 'on_vs_on': run_vs_run,
              'differ_also_between_two_on_runs': sorted(set(progress_vs_off['differ']) & set(run_vs_run['differ'])),
              'switched_and_left_out': list(SWITCHED), 'masks': [p.pattern.decode() for p, _ in TIME_PATTERNS],
              'identical': identical and all(r['exit'] == 0 for r in runs.values())
                           and runs['on-1']['progress_file'] and not runs['off']['progress_file']}
    text = json.dumps(record, ensure_ascii=False, indent=1)
    if args.json: Path(args.json).write_text(text + '\n', encoding='utf-8')
    print(text)
    return 0 if record['identical'] else 1


if __name__ == '__main__':
    sys.exit(main())
