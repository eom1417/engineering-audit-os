"""Pin every released tool for each computer EAOS supports, from the tool's own GitHub release.

    python tools/platform_assets.py            # fill eaos/data/toolchain.json -> install.platforms

For each `release` tool, the release named by its pinned version is read from the GitHub API; the asset for
each platform (linux-x86_64, darwin-arm64, darwin-x86_64) is chosen by name, downloaded, its sha256 computed,
and, for an archive, the member that is the tool found inside it. A platform with no asset is left out and
eaos/core/toolchain.py says so instead of installing a binary that cannot run. The Linux pin already in the file
stays as it is.
"""
import hashlib
import io
import json
import re
import tarfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / 'eaos/data/toolchain.json'
WORDS = {'darwin-arm64': (r'(darwin|macos|mac|apple)', r'(arm64|aarch64|universal|_all)'),
         'darwin-x86_64': (r'(darwin|macos|mac|apple)', r'(x86_64|amd64|x64|64bit|64-bit|universal|_all)(?!.*arm)')}
NEUTRAL = re.compile(r'(linux|x86|amd64|x64|64bit)', re.I)
SKIP = re.compile(r'\.(sha256|sha512|sig|pem|asc|sbom|json|txt|deb|rpm|apk|msi|pkg|dmg)$|checksums|sbom|provenance', re.I)


def fetch(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'eaos-platform-assets'})
    with urllib.request.urlopen(request, timeout=600) as response: return response.read()


def archive_of(name):
    for suffix, kind in (('.tar.gz', 'tar.gz'), ('.tgz', 'tar.gz'), ('.tar.xz', 'tar.xz'), ('.zip', 'zip')):
        if name.endswith(suffix): return kind
    return 'binary'


def _archive_names(blob, kind):
    """The files of a zip or tar archive."""
    if kind == 'zip':
        return [n for n in zipfile.ZipFile(io.BytesIO(blob)).namelist() if not n.endswith('/')]
    mode = {'tar.gz': 'r:gz', 'tar.xz': 'r:xz'}[kind]
    return [m.name for m in tarfile.open(fileobj=io.BytesIO(blob), mode=mode).getmembers() if m.isfile()]


def _named_like(names, wanted, tree):
    """The files named exactly like the tool (under bin/ for a tree), else the ones named after its release."""
    base = lambda n: n.rsplit('/', 1)[-1]
    found = [n for n in names if base(n) == wanted and (not tree or '/bin/' in n)]
    # A binary named after its release (enola-0.4.21-darwin-arm64) is still the tool.
    return found or [n for n in names if base(n).startswith(wanted + '-') and not re.search(r'\.(txt|md|json|sha256)$', base(n))]


def member(blob, kind, binary, tree_entry=None):
    """The path of the tool inside an archive: the file named like the tool (or, for a tree, like its entry)."""
    found = _named_like(_archive_names(blob, kind), Path(tree_entry).name if tree_entry else binary, tree_entry)
    return min(found, key=len) if found else None


def _asset_for(assets, platform_words, spec, linux_name):
    """The release asset for one platform, of the same family as the Linux pin (the longest common start); None."""
    system, machine = platform_words
    chosen = [a for a in assets if re.search(system, a['name'], re.I) and re.search(machine, a['name'], re.I)]
    if spec.get('tree'): chosen = [a for a in chosen if re.search(r'jre', a['name'], re.I)] or chosen
    if not chosen: return None
    common = lambda name: next((i for i, (a, b) in enumerate(zip(name, linux_name)) if a != b), min(len(name), len(linux_name)))
    return max(chosen, key=lambda a: (common(a['name']), -len(a['name'])))


def _platform_entry(tool, spec, asset):
    """The pinned entry of one platform's asset: its address, sha256, archive kind and the tool inside it; None when
    the archive does not hold the tool."""
    blob = fetch(asset['browser_download_url'])
    kind = archive_of(asset['name'])
    entry = {'url': asset['browser_download_url'], 'sha256': hashlib.sha256(blob).hexdigest(), 'archive': kind}
    if spec.get('tree'):
        entry['tree'] = True
        entry['entry'] = member(blob, kind, tool['binary'], spec['entry'])
    elif kind != 'binary':
        entry['member'] = member(blob, kind, tool['binary'])
        if not entry['member']:
            print(f"{tool['name']}: {tool['binary']} not in {asset['name']}")
            return None
    else:
        entry['member'] = tool['binary']
    return entry


def _pin_tool(tool):
    """Fill one release tool's `platforms` from its GitHub release; any other tool is left as it is."""
    spec = tool['install']
    if spec.get('method') != 'release': return
    match = re.match(r'https://github.com/([^/]+/[^/]+)/releases/download/([^/]+)/', spec['url'])
    if not match:
        print(f"{tool['name']}: not a GitHub release, left as is")
        return
    repo, tag = match.groups()
    release = json.loads(fetch(f'https://api.github.com/repos/{repo}/releases/tags/{tag}'))
    assets = [a for a in release.get('assets') or [] if not SKIP.search(a['name'])]
    platforms = {'linux-x86_64': {k: v for k, v in spec.items() if k != 'platforms'}}
    linux_name = spec['url'].rsplit('/', 1)[-1]
    if not NEUTRAL.search(linux_name):              # one build for every computer (a Java zip)
        spec['platforms'] = {p: platforms['linux-x86_64'] for p in ('linux-x86_64', *WORDS)}
        print(f"{tool['name']}: the same build on every platform")
        return
    for platform, words in WORDS.items():
        asset = _asset_for(assets, words, spec, linux_name)
        if asset is None:
            print(f"{tool['name']}: no {platform} build in {tag}")
            continue
        entry = _platform_entry(tool, spec, asset)
        if entry is None: continue
        platforms[platform] = entry
        print(f"{tool['name']}: {platform} <- {asset['name']}")
    spec['platforms'] = platforms


def main():
    registry = json.loads(REGISTRY.read_text(encoding='utf-8'))
    for tool in registry['tools'] if isinstance(registry, dict) else registry: _pin_tool(tool)
    REGISTRY.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
