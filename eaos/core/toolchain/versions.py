"""The version of each pinned tool installed now (`found_version`), and `doctor`: per tool, whether it is there at
its pinned version, and why not."""
import json
import os
import re
import subprocess

from .pins import Unavailable, binary_path, browsers, checkout, home, npm_prefix, release_spec, selected, tool_env, venv_of

VERSION = re.compile(r'(\d+\.\d+\.\d+)')


def _git_version(tool):
    # A pinned repository of data (rules), not a program: its version is the commit it is at.
    done = subprocess.run(['git', '-C', str(checkout(tool)), 'rev-parse', 'HEAD'], capture_output=True, text=True)
    return (done.stdout.strip(), '') if done.returncode == 0 else (None, 'not installed')


def _library_version(tool):
    # A Node library EAOS's own helper scripts import (axe, the CSS analyzer): it has no executable, and its
    # version is the one its package.json declares in the tool's own prefix.
    found = package_version(tool, tool['install']['package'])
    if not found: return None, 'not installed'
    missing = _companions_missing(tool)
    return (None, missing) if missing else (found, '')


def _version_output(tool, path):
    """(what `path --version` printed, None), or (None, why it could not run)."""
    try:
        # A tool that runs on another (the Structurizr CLI on the JRE) finds it in the pinned bin first.
        done = subprocess.run([path, *tool.get('version_args', ['--version'])], capture_output=True, text=True, timeout=120,  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit -- a list argv of a tool EAOS installs at its pin, no shell
                              env={**tool_env(), 'NO_COLOR': '1', 'PATH': str(home() / 'bin') + os.pathsep + os.environ.get('PATH', '')})
    except (OSError, subprocess.TimeoutExpired) as problem:
        return None, f'{path} --version failed: {problem}'
    return done.stdout + done.stderr, None


def _version_match(tool, output):
    # A tool may print another program's version first (dependency-cruiser names the Node.js it refuses):
    # the pinned version anywhere in the output is the tool's own; a refusal of Node.js is said as such.
    if tool['version'] in VERSION.findall(output) and not tool.get('version_reports'):
        return re.search('(' + re.escape(tool['version']) + ')', output)
    return VERSION.search(output)


def _refuses_node(tool, output):
    return (tool['version'] not in output and re.search(r'node', output, re.I)
            and re.search(r'not supported|unsupported|requires|engine', output, re.I))


def _reported_version(tool, path, output):
    match = _version_match(tool, output)
    if _refuses_node(tool, output):
        return None, f"{tool['name']} needs a newer Node.js than this computer has ({output.strip()[:160]})"
    if not match: return None, f'{path} --version printed no version'
    missing = _companions_missing(tool)
    if missing: return None, missing
    # A release numbered one way may report another (the Structurizr CLI reports its parser's version):
    # `version_reports` names what the pinned release prints, and the pinned version stands for it.
    if tool.get('version_reports'):
        return (tool['version'], '') if match.group(1) == tool['version_reports'] else (match.group(1), '')
    return match.group(1), ''


def _binary_version(tool, path):
    if tool.get('version_from') == 'package':
        # A command with no --version (the react-docgen CLI): the version is the one its npm package records.
        found = package_version(tool)
        return (found, '') if found else (None, f"{tool['install']['package']} is not installed in {npm_prefix(tool)}")
    output, failure = _version_output(tool, path)
    if failure: return None, failure
    return _reported_version(tool, path, output)


def found_version(tool):
    if tool['install']['method'] == 'git': return _git_version(tool)
    if tool['install'].get('library'): return _library_version(tool)
    path = binary_path(tool)
    if not path: return None, 'not installed'
    return _binary_version(tool, path)


def package_version(tool, name=None):
    """The version of the npm package `name` (default: the tool's own package) installed in the tool's prefix, or
    None."""
    manifest = npm_prefix(tool) / 'node_modules' / (name or tool['install']['package']) / 'package.json'
    try: return json.loads(manifest.read_text(encoding='utf-8')).get('version')
    except (OSError, ValueError): return None


def _companions_missing(tool):
    """A tool's companion packages (install.with: npm `name@version`, pip `name==version`) at their pinned versions,
    or what is not."""
    pip = tool['install']['method'] == 'pip'
    for spec in tool['install'].get('with', []):
        name, _, wanted = spec.partition('==') if pip else spec.rpartition('@')
        found = pip_version(name, venv_of(tool)) if pip else package_version(tool, name)
        if found != wanted: return f'{name} {wanted} is not installed beside it (found {found})'
    return ''


def pip_version(name, venv=None):
    """The version of the Python package `name` installed in the tools' virtualenv (or `venv`), or None."""
    for record in ((venv or home() / 'venv') / 'lib').glob(f"python*/site-packages/{name.replace('-', '_')}-*.dist-info"):
        return record.name[len(name) + 1:-len('.dist-info')]
    return None


def browser_missing():
    """'' when the pinned Playwright's Chromium is in browsers(), else what is missing."""
    manifest = home() / 'node/node_modules/playwright-core/browsers.json'
    try: wanted = {b['name']: b['revision'] for b in json.loads(manifest.read_text(encoding='utf-8'))['browsers']}
    except (OSError, ValueError, KeyError): return 'Playwright is not installed'
    for name, folder in (('chromium', 'chromium'), ('chromium-headless-shell', 'chromium_headless_shell')):
        if name in wanted and not (browsers() / f'{folder}-{wanted[name]}').is_dir(): return f'{name} {wanted[name]} is not installed'
    return ''


def _with_browsers(tool, ok, reason):
    """Playwright counts as ready only with its browsers."""
    if not (ok and tool['name'] == 'playwright'): return ok, reason
    missing = browser_missing()
    return (False, missing) if missing else (ok, reason)


def _release_unavailable(tool, reason):
    try: release_spec(tool)
    except Unavailable as problem: return str(problem), True
    return reason, False


def _doctor_row(tool):
    found, reason = found_version(tool)
    ok = found == tool['version']
    if found and not ok: reason = f'found {found}, pinned {tool["version"]}'
    ok, reason = _with_browsers(tool, ok, reason)
    reason, unavailable = _release_unavailable(tool, reason) if not ok and tool['install']['method'] == 'release' else (reason, False)
    row = {'name': tool['name'], 'role': tool['role'], 'stages': tool['stages'], 'pinned': tool['version'],
           'found': found, 'ok': ok, 'reason': reason, 'unavailable': unavailable}
    if tool.get('license_note'): row['license_note'] = tool['license_note']
    return row


def doctor(names=None, stage=None, skip=()):
    return {'tools': [_doctor_row(tool) for tool in selected(names, stage, skip)]}
