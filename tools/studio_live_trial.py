"""The live Studio trial (indicator F9): events reach an open Studio, on screen, within five seconds.

    python tools/studio_live_trial.py [--data <report>/studio] [--out DIR]

Starts the real server (eaos/api/) on a copy of a report's Studio data (default $EAOS_MEASURE/FleetManageWeb/studio,
else a synthetic one), opens the shipped Studio in Chromium with the launch token (Playwright, from the EAOS
toolchain, driven by studio/scripts/live.mjs), at 390 wide in Arabic and light and at 1440 wide in English and dark.
For each of the four events F9 names (a new scan, a batch, a merge, a decision) the data is rewritten the way the
exporter writes it (eaos/studio/export.py: each section whole and renamed, the manifest last), and the page must show
the change itself (the new verdict on Home, the card's new state in its detail, the new question in Decisions) within
five seconds of the write. It also checks that the server refuses a request without its token and that the token
leaves the address bar.

Writes DIR/trial.json (default $EAOS_MEASURE/studio-live), which `python tools/north_star.py measure --only F9`
reads; a trial counts only when it ran in full on the Studio build shipped in this checkout.

    python tools/studio_live_trial.py mutate DIR KIND N [--plan]

One event on the data folder DIR (scan, batch, merge or decision; N numbers it), printed as {route, scope, text}:
where the page shows it and the words it shows. --plan prints the same without writing.
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tools'))
from eaos import artifact_contracts  # noqa: E402
from eaos.studio import export  # noqa: E402
import dev_paths  # noqa: E402

KINDS = ('scan', 'batch', 'merge', 'decision')
WITHIN = 5000            # milliseconds, F9's definition
# The words the Studio shows for a card's state (studio/src/i18n/catalog.ts: stateInBatch, stateDone).
STATE_WORDS = {'in_batch': {'ar': 'في دفعة', 'en': 'In a batch'}, 'done': {'ar': 'منجزة', 'en': 'Done'}}
MARK = '.live-trial.json'
# The first of these real reports that is there; else a synthetic one.
DEFAULT_DATA = [dev_paths.MEASURE / name / 'studio' for name in ('FleetManageWeb', 'chief-ops', 'finance-os-a0192b7b', 'self-truth')]


def _load(folder, name):
    return json.loads((Path(folder) / f'{name}.json').read_text(encoding='utf-8'))


def publish(folder, changed):
    """Write the changed sections whole, then the manifest with their new digests: what export.export does."""
    folder = Path(folder)
    contracts = artifact_contracts.contracts()
    manifest = _load(folder, 'manifest')
    for name, data in changed.items():
        problems = artifact_contracts.validate(data, contracts[f'studio-{name}'])
        if problems: raise ValueError(f'{name}: {problems[:3]}')
        blob = export._write(folder, name, data)
        entry = next(s for s in manifest['sections'] if s['name'] == name)
        entry.update(sha256=hashlib.sha256(blob).hexdigest(), bytes=len(blob))
    if 'head' in changed: manifest['scanned'] = changed['head']['scanned']
    problems = artifact_contracts.validate(manifest, contracts['studio-manifest'])
    if problems: raise ValueError(f'manifest: {problems[:3]}')
    export._write(folder, 'manifest', manifest)


def mutate(folder, kind, number, plan=False):
    folder = Path(folder)
    mark_path = folder / MARK
    mark = json.loads(mark_path.read_text(encoding='utf-8')) if mark_path.is_file() else {}
    if kind == 'scan':
        head = _load(folder, 'head')
        text = f'Live check {number} landed'
        head['verdict'] = text
        head['scanned'] = {**head['scanned'], 'commit': hashlib.sha1(f'live-{number}'.encode()).hexdigest()}
        out, changed = {'route': '#/', 'scope': 'main', 'text': {'ar': text, 'en': text}}, {'head': head}
    elif kind in ('batch', 'merge'):
        cards = _load(folder, 'cards')
        if kind == 'batch':
            card = sorted((c for c in cards['cards'] if c['state'] == 'open'), key=lambda c: c['id'])[0]
        else:
            card = next(c for c in cards['cards'] if c['id'] == mark.get('batch'))
        state = 'in_batch' if kind == 'batch' else 'done'
        card['state'] = state
        out = {'route': f"#/problems?card={card['id']}", 'scope': 'article[aria-labelledby="card-title"]', 'text': STATE_WORDS[state]}
        changed = {'cards': cards}
        if kind == 'batch' and not plan: mark['batch'] = card['id']
    elif kind == 'decision':
        decisions = _load(folder, 'decisions')
        text = f'Live decision {number}: keep the old login page?'
        decisions['decisions'].insert(0, {'id': f'live-{number}', 'question': text, 'recommendation': 'Keep it until the new one passes.',
                                          'options': [{'id': 'yes', 'label': 'Yes'}, {'id': 'later', 'label': 'Later'}], 'blocks': [],
                                          'state': 'waiting', 'answer': None, 'plan': None, 'asked': '', 'tool': None})
        out, changed = {'route': '#/decisions', 'scope': 'main', 'text': {'ar': text, 'en': text}}, {'decisions': decisions}
    else:
        raise ValueError(f'unknown event {kind}')
    if not plan:
        publish(folder, changed)
        mark_path.write_text(json.dumps(mark), encoding='utf-8')
    return out


def _session(port, token):
    request = urllib.request.Request(f'http://127.0.0.1:{port}/api/session', headers={'X-EAOS-Token': token} if token else {})
    try:
        with urllib.request.urlopen(request, timeout=3) as response: return response.status
    except urllib.error.HTTPError as error: return error.code
    except OSError: return None


def trial(data, out):
    from eaos.api.server import bind, create_app, serve
    out.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix='studio-live-'))
    try:
        folder = work / 'report' / 'studio'
        if data and (Path(data) / 'manifest.json').is_file():
            shutil.copytree(data, folder)
            source = str(data)
        else:
            import studio_synthetic
            studio_synthetic.write(folder, studio_synthetic.build(cards=200, components=40))
            source = 'synthetic (tools/studio_synthetic.py, 200 cards)'
        app = create_app(folder.parent, name='live-trial')
        ctx = app.state.ctx
        sock = bind(0)
        ctx.keys.port = sock.getsockname()[1]
        servers = []
        threading.Thread(target=serve, args=(app, sock, servers.append), daemon=True).start()
        deadline = time.monotonic() + 15
        while _session(ctx.keys.port, ctx.keys.token) != 200 and time.monotonic() < deadline: time.sleep(0.2)
        refused = {'no_token': _session(ctx.keys.port, None), 'wrong_token': _session(ctx.keys.port, 'x' * 43)}
        env = {**os.environ, 'EAOS_LIVE_BASE': f'http://127.0.0.1:{ctx.keys.port}/', 'EAOS_LIVE_TOKEN': ctx.keys.token,
               'EAOS_LIVE_DATA': str(folder), 'EAOS_LIVE_PYTHON': sys.executable, 'EAOS_LIVE_MUTATE': str(Path(__file__).resolve()),
               'EAOS_LIVE_OUT': str(out), 'EAOS_LIVE_WITHIN': str(WITHIN)}
        run = subprocess.run(['node', str(ROOT / 'studio/scripts/live.mjs')], env=env, capture_output=True, text=True, timeout=600)
        if servers: servers[0].should_exit = True
        browser = json.loads((out / 'live.json').read_text(encoding='utf-8')) if (out / 'live.json').is_file() else None
    finally:
        shutil.rmtree(work, ignore_errors=True)
    shipped = json.loads((ROOT / 'eaos/data/studio/SOURCE.json').read_text(encoding='utf-8'))['source_sha256']
    events = (browser or {}).get('events') or []
    shown = [e for e in events if e['shown'] and e['ms'] is not None and e['ms'] <= WITHIN]
    record = {'schema_version': 1, 'kind': 'studio-live', 'at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
              'data': source, 'studio_source_sha256': shipped, 'feed_source': ctx.feed.source, 'within_ms': WITHIN,
              'refused': refused, 'token_left_address': (browser or {}).get('token_left_address'),
              'complete': bool(browser) and run.returncode == 0 and len(events) == len(KINDS) * len((browser or {}).get('variants') or []),
              'events': events, 'shown_in_time': len(shown), 'variants': (browser or {}).get('variants') or [],
              'errors': (browser or {}).get('errors') or [], 'log': (run.stderr or '')[-2000:]}
    (out / 'trial.json').write_text(json.dumps(record, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    return record


def main(argv):
    if argv and argv[0] == 'mutate':
        parser = argparse.ArgumentParser(prog='studio_live_trial.py mutate')
        parser.add_argument('folder'); parser.add_argument('kind', choices=KINDS); parser.add_argument('number', type=int)
        parser.add_argument('--plan', action='store_true')
        args = parser.parse_args(argv[1:])
        print(json.dumps(mutate(args.folder, args.kind, args.number, args.plan), ensure_ascii=False))
        return 0
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--data', default=next((str(p) for p in DEFAULT_DATA if (p / 'manifest.json').is_file()), None))
    parser.add_argument('--out', default=str(dev_paths.MEASURE / 'studio-live'))
    args = parser.parse_args(argv)
    record = trial(args.data, Path(args.out))
    for event in record['events']:
        print(f"{event['variant']:24} {event['kind']:9} {'shown' if event['shown'] else 'NOT SHOWN':9} {event['ms']} ms")
    print(f"refused without the token: {record['refused']}; token left the address: {record['token_left_address']}")
    print(f"F9 trial: {record['shown_in_time']}/{len(record['events'])} events on screen within {WITHIN} ms"
          + ('' if record['complete'] else ' (INCOMPLETE: ' + '; '.join(record['errors'][:3]) + ')'))
    return 0 if record['complete'] and record['shown_in_time'] == len(record['events']) else 1


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
