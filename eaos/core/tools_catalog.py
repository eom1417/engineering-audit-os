"""Tools the assistant finds and the person adds (the owner, 2026-10-22: "it can search GitHub and add the tools it
needs"). `find` reads GitHub's search and each candidate's latest release; `add` writes a pinned entry to
<home>/toolchain-added.json, which eaos/core/toolchain/pins.py reads beside its own list, and installs it. Nothing is installed
without the person's agreement, a pinned version and a sha256 (a commit for git), and a license; an entry with
`engine` ({"args": [...], "output": "sarif"}) runs in the engines stage through eaos/engines/sarif.py, with no Python.
"""
import json
import re
import urllib.parse
import urllib.request

from . import toolchain

METHODS = ('release', 'pip', 'npm', 'git')
SHA256, COMMIT = re.compile(r'^[0-9a-f]{64}$'), re.compile(r'^[0-9a-f]{40}$')


def _get(url):
    request = urllib.request.Request(url, headers={'Accept': 'application/vnd.github+json', 'User-Agent': 'eaos'})
    with urllib.request.urlopen(request, timeout=20) as answer: return json.loads(answer.read().decode('utf-8'))


def find(need, limit=5):
    """The candidates GitHub knows for `need`: name, stars, license, description and the latest release's assets."""
    found = _get('https://api.github.com/search/repositories?' + urllib.parse.urlencode({'q': need, 'sort': 'stars', 'per_page': limit}))
    rows = []
    for repo in found.get('items') or []:
        try: release = _get(f"https://api.github.com/repos/{repo['full_name']}/releases/latest")
        except OSError: release = {}
        rows.append({'repository': repo['html_url'], 'stars': repo.get('stargazers_count'), 'license': (repo.get('license') or {}).get('spdx_id'),
                     'description': (repo.get('description') or '')[:200], 'version': release.get('tag_name'),
                     'assets': [{'name': a['name'], 'url': a['browser_download_url']} for a in release.get('assets') or []][:12]})
    return {'candidates': rows, 'what_now': 'Choose one, read its sha256 (a release\'s checksums file), and call tools_add with a pinned entry: '
                                            'the person agrees first.'}


def problems(entry):
    """What makes an entry unsafe to install: never without a pinned version, a sha256 or a commit, and a license."""
    install = entry.get('install') or {}
    found = [f'{key} is missing' for key in ('name', 'version', 'license', 'repository', 'binary') if not entry.get(key)]
    if install.get('method') not in METHODS: found.append(f"install.method must be one of {', '.join(METHODS)}")
    if install.get('method') == 'release' and not SHA256.match(str(install.get('sha256') or '')): found.append('a release needs its sha256')
    if install.get('method') == 'git' and not COMMIT.match(str(entry.get('version') or '')): found.append('a git tool is pinned to a commit')
    if any(t['name'] == entry.get('name') for t in toolchain.registry()['tools']): found.append(f"{entry.get('name')} is already a tool")
    return found


def add(entry, person_agreed=False):
    """The entry kept and installed once safe and agreed; else what is wrong, or the question for the person."""
    if found := problems(entry): return {'status': 'refused', 'problems': found}
    if not person_agreed:
        return {'status': 'needs_agreement', 'ask_the_person': f"Install {entry['name']} {entry['version']} ({entry['license']}) from "
                                                               f"{entry['repository']} for this computer's checks?",
                'what_now': 'Ask the person this. Only if they say yes, call tools_add again with person_agreed=true.'}
    path = toolchain.home() / 'toolchain-added.json'
    kept = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {'tools': []}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'tools': kept['tools'] + [entry]}, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    failed = toolchain.install(names=[entry['name']], echo=lambda *_: None)
    return {'status': 'failed' if failed else 'installed', 'tool': entry['name'], 'failed': failed,
            'what_now': 'Run the check again from the stage that needs it (audit again_from).'}
