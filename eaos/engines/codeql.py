"""CodeQL: security weaknesses found by following data from where it enters the program to where it does harm.

The third reader of code security, and the deepest: Semgrep matches patterns, Bandit walks one file's syntax tree,
CodeQL builds a database of the whole program and traces untrusted input across functions and files. Its default
query suites (code-scanning) keep only the queries GitHub rates precise, so a finding is rarely noise.

CodeQL's terms (github/codeql-cli-binaries LICENSE.md) allow it on an open-source codebase only: one released under an
OSI-approved license, and, for automated analysis like a check, hosted and maintained on GitHub.com. So it runs only
when the project has an open-source license file and its `origin` is a public GitHub repository, asked of GitHub's
API; anywhere else, including when that cannot be asked, it declines and says why, and the check goes on with the
other engines. It builds one database per language (Python, JavaScript and TypeScript), within MEMORY megabytes.
"""
import json
import re
import shutil
import subprocess
import urllib.request
from pathlib import Path

from . import sarif, tool
from .contract import ERROR, NOT_APPLICABLE, OBSERVED, Capability, Report
from .process import run, which

NAME = BINARY = 'codeql'
PINNED = tool.pinned(NAME)
MEMORY = 2048
LANGUAGES = {'python': ('.py',), 'javascript-typescript': ('.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs')}
SUITES = {'python': 'codeql/python-queries', 'javascript-typescript': 'codeql/javascript-queries'}
EXCLUDED = ('.git', 'node_modules', '.venv', 'venv', '__pycache__', 'dist', 'build', 'vendor')
LICENSE_FILES = ('LICENSE', 'LICENSE.md', 'LICENSE.txt', 'LICENCE', 'COPYING', 'COPYING.md')
# The opening words of the OSI-approved licenses projects use most; the file is read, never guessed from its name.
OPEN_SOURCE = {'MIT': 'Permission is hereby granted, free of charge', 'Apache-2.0': 'Apache License',
               'GPL': 'GNU GENERAL PUBLIC LICENSE', 'LGPL': 'GNU LESSER GENERAL PUBLIC LICENSE',
               'AGPL': 'GNU AFFERO GENERAL PUBLIC LICENSE', 'MPL-2.0': 'Mozilla Public License',
               'BSD': 'Redistribution and use in source and binary forms', 'ISC': 'Permission to use, copy, modify, and/or distribute',
               'Unlicense': 'This is free and unencumbered software'}
GITHUB = re.compile(r'github\.com[:/](?P<repo>[^/\s]+/[^/\s]+?)(?:\.git)?/?$')


def capabilities():
    return [Capability('vulnerability', '*/security/*'), Capability('secret', '*/credentials*')]


def version():
    return tool.version(BINARY)


def license_of(target):
    """The open-source license the project's license file declares, or None."""
    for name in LICENSE_FILES:
        path = Path(target) / name
        if path.is_file():
            text = ' '.join(path.read_text(encoding='utf-8', errors='replace')[:4000].split())
            return next((spdx for spdx, words in OPEN_SOURCE.items() if words.lower() in text.lower()), None)
    return None


def public_repository(target):
    """`owner/name` when the project's origin is a public repository on GitHub.com, else None."""
    done = subprocess.run(['git', '-C', str(target), 'remote', 'get-url', 'origin'], capture_output=True, text=True)
    url = done.stdout.strip() if done.returncode == 0 else ''
    # EAOS's own copy of the project (eaos/journeys/guided.py source) has the project's folder as origin: the project's own counts.
    if url and Path(url).is_dir() and Path(url).resolve() != Path(target).resolve(): return public_repository(url)
    found = GITHUB.search(url)
    if not found: return None
    try:
        with urllib.request.urlopen(f"https://api.github.com/repos/{found.group('repo')}", timeout=20) as response:  # nosec B310: GitHub's https API
            data = json.loads(response.read())
    except (OSError, ValueError):
        return None                     # a private repository answers 404 to a visitor; no answer is no permission
    return found.group('repo') if data.get('private') is False else None


def allowed(target):
    """(True, why) when CodeQL's terms allow it on this project, else (False, why)."""
    spdx = license_of(target)
    if spdx is None:
        return False, 'CodeQL may only check open-source code, and this project has no open-source license file'
    repo = public_repository(target)
    if repo is None:
        return False, ('CodeQL may only check open-source code hosted publicly on GitHub.com, and this project\'s origin '
                       'is not a public GitHub repository (or GitHub could not be asked)')
    return True, f'{spdx} license, public on GitHub.com as {repo}'


def analyze(target, workdir, exclude=(), formats=None):
    declined = tool.declined(NAME, BINARY, target)
    if declined: return declined
    found = version()
    permitted, why = allowed(target)
    if not permitted: return Report(NAME, found, PINNED, NOT_APPLICABLE, reason=why)
    workdir = Path(workdir) / NAME
    if workdir.exists(): shutil.rmtree(workdir)
    workdir.mkdir(parents=True)
    config, ignored = _config(workdir, exclude)
    files = _files(target, ignored)
    findings, unmapped, seconds, outputs = [], {}, 0.0, {}
    for language, suffixes in LANGUAGES.items():
        if not any(path.endswith(suffixes) for path in files): continue
        output, spent, problem = _language(target, workdir, config, language)
        seconds += spent
        if problem: return Report(NAME, found, PINNED, ERROR, seconds=seconds, reason=f'{language}: {problem}')
        sarif.relativise(output, target)
        more, missed = sarif.read(output, NAME, found)
        findings += more
        for rule, count in missed.items(): unmapped[rule] = unmapped.get(rule, 0) + count
        outputs[language] = str(output)
    return Report(NAME, found, PINNED, OBSERVED, seconds=seconds, findings=findings, unmapped=unmapped,
                  raw=json.dumps(outputs), coverage={'status': 'observed', 'permitted': why, 'languages': sorted(outputs)},
                  evaluated={'vulnerability': {'status': 'observed', 'granularity': 'file'}})


def _config(workdir, exclude):
    """(codeql-config.yml written in `workdir`, the folders it leaves out: EXCLUDED and the check's own)."""
    config = workdir / 'codeql-config.yml'
    ignored = [name.strip('/') for name in EXCLUDED + tuple(exclude) if name.strip('/')]
    config.write_text('paths-ignore:\n' + ''.join(f"  - '{name}'\n  - '**/{name}'\n" for name in ignored), encoding='utf-8')
    return config, ignored


def _files(target, ignored):
    from ..core.toolchain import project_files
    return [path for path in project_files(target) if not tool.excluded(path, ignored)]


def _language(target, workdir, config, language):
    """(the SARIF of one language, seconds, the failure or None): its database built, then its default suite run."""
    database, output = workdir / f'db-{language}', workdir / f'{language}.sarif'
    code, _, error, built = run([which(BINARY), 'database', 'create', str(database), f'--language={language}',
                                 f'--source-root={Path(target).resolve()}', f'--codescanning-config={config}',
                                 '--build-mode=none', f'--ram={MEMORY}', '--threads=0', '--overwrite'], cwd=workdir, timeout=1800)
    if code != 0: return output, built, error.strip()[-300:] or f'database create exit {code}'
    code, _, error, ran = run([which(BINARY), 'database', 'analyze', str(database), SUITES[language], '--format=sarif-latest',
                               f'--output={output}', f'--ram={MEMORY}', '--threads=0'], cwd=workdir, timeout=1800)
    shutil.rmtree(database, ignore_errors=True)
    if code != 0 or not output.is_file(): return output, built + ran, error.strip()[-300:] or f'database analyze exit {code}'
    return output, built + ran, None
