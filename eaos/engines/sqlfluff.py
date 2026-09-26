"""SQLFluff: the project's SQL (migrations, functions, policies) linted in the Postgres dialect.

Most of what it reports is layout and capitalisation (1,762 of 1,790 in finance-os). Those families
(LT, CP, AL, JJ, and RF03/RF05/RF06, which are quoting and consistency) are counted in the coverage by
code, never dropped silently, but only the rest become findings: ambiguity, structure, convention,
references that can break (a keyword used as a name, an unqualified column in a join), and files the
dialect cannot parse. A SQL finding is a fact for the debt register, not a claim.
"""
import json
from pathlib import Path

from . import tool
from .contract import ERROR, OBSERVED, Report, finding, measurement, subject
from .process import run, which

NAME = BINARY = 'sqlfluff'
PINNED = tool.pinned(NAME)
STYLE_FAMILIES = ('LT', 'CP', 'AL', 'JJ')
STYLE_CODES = ('RF03', 'RF05', 'RF06')
SKIPPED = ('node_modules', '.git', 'dist', 'build', 'vendor')


def capabilities():
    from .contract import Capability
    return [Capability('sql_quality', 'AM*,ST*,CV*,RF01,RF02,RF04,PRS')]


def version():
    return tool.version(BINARY)


def style(code):
    return code.startswith(STYLE_FAMILIES) or code in STYLE_CODES


def sql_files(target, exclude=()):
    root = Path(target)
    return sorted(str(p.relative_to(root)) for p in root.rglob('*.sql')
                  if not set(p.relative_to(root).parts) & set(SKIPPED + tuple(exclude)))


def analyze(target, workdir, exclude=(), formats=None):
    declined = tool.declined(NAME, BINARY, target)
    if declined: return declined
    found = version()
    target = Path(target).resolve()
    files = sql_files(target, exclude)
    output = Path(workdir) / NAME / 'sqlfluff.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [which(BINARY), 'lint', '--format', 'json', '--dialect', 'postgres', '--nofail', '--disable-progress-bar',
               '--write-output', str(output), *files]
    code, _, error, seconds = run(command, cwd=target)
    if code or not output.is_file():
        return Report(NAME, found, PINNED, ERROR, seconds=seconds, reason=error.strip()[-300:] or f'exit {code}')
    findings, by_code = [], {}
    for entry in json.loads(output.read_text(encoding='utf-8')):
        path = entry['filepath']
        for violation in entry.get('violations') or []:
            code_ = violation['code']
            by_code[code_] = by_code.get(code_, 0) + 1
            if style(code_): continue
            line = violation.get('start_line_no')
            findings.append(finding(NAME, found, code_, 'sql_quality', subject('file', f'{path}:{line}:{code_}', path, line),
                                    f"{code_} {violation.get('name', '')}: {violation.get('description', '')}".strip(),
                                    measurements=[measurement('severity', 'medium' if code_ == 'PRS' else 'low')],
                                    raw_ref=f'{NAME}/sqlfluff.json'))
    counted_style = {c: n for c, n in sorted(by_code.items()) if style(c)}
    return Report(NAME, found, PINNED, OBSERVED, seconds=seconds, findings=findings, raw=str(output),
                  coverage={'status': 'observed', 'files': len(files), 'dialect': 'postgres',
                            'violations_by_code': dict(sorted(by_code.items())),
                            'style_only_not_findings': sum(counted_style.values())},
                  evaluated={'sql_quality': {'status': 'observed', 'granularity': 'file'}})
