"""The live trial of branch control (NS46.T18) and scan freshness (NS46.T19) on real git repositories.

    python tools/studio_branch_trial.py [--out DIR]

Builds real temporary repositories (the polyglot fixture as a project with develop, main, an origin, tool-owned and
human branches, a worktree), checks the project with the real EAOS audit, serves it with the real live Studio of this
checkout (eaos/api/server.py with the command centre mounted, the shipped build of eaos/data/studio), and drives every
case of acceptance/test_branch_control.py and acceptance/test_scan_freshness.py through the authenticated HTTP API and
a real Chromium (tools/studio_branch_trial.mjs: the screens, the time zones, the clicks). The one managed EAOS batch is
made by the real fix pipeline (fix_start, fix_finish: EAOS's own codemod and gates) and accepted from the Studio.

No assistant is launched (the run is itself an assistant's; nested delegation is not allowed): the conflict resolution
proposal is queued in handoff mode, which is the Studio's own path when no assistant is chosen.

Writes DIR/branch-control/trial.json and DIR/scan-freshness/trial.json (default $EAOS_MEASURE), with screenshots in
DIR/branch-control/shots/. Every case records what was observed; a case that could not be shown is recorded as failed.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tools'))

OWNER = {'GIT_AUTHOR_NAME': 'Owner', 'GIT_AUTHOR_EMAIL': 'owner@example.com', 'GIT_COMMITTER_NAME': 'Owner', 'GIT_COMMITTER_EMAIL': 'owner@example.com'}
EAOS = {'GIT_AUTHOR_NAME': 'EAOS', 'GIT_AUTHOR_EMAIL': 'eaos@localhost', 'GIT_COMMITTER_NAME': 'EAOS', 'GIT_COMMITTER_EMAIL': 'eaos@localhost'}


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def git(folder, *args, env=None, check=True):
    done = subprocess.run(['git', '-C', str(folder), *args], capture_output=True, text=True, env={**os.environ, **OWNER, **(env or {})})
    if check and done.returncode: raise RuntimeError(f'git {" ".join(args)}: {done.stderr.strip()}')
    return done.stdout.strip()


def commit(folder, path, text, message, env=None):
    target = Path(folder) / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding='utf-8')
    git(folder, 'add', path)
    git(folder, 'commit', '-q', '-m', message, env=env)
    return git(folder, 'rev-parse', 'HEAD')


class Api:
    """The live Studio's API as the Studio page calls it: token on every call, CSRF and Origin on every POST."""

    def __init__(self, port, token):
        self.base, self.token = f'http://127.0.0.1:{port}', token
        self.origin = self.base
        self.csrf = self.get('/api/session')[1]['csrf']

    def call(self, method, path, body=None, headers=None):
        sent = {'X-EAOS-Token': self.token, 'Accept': 'application/json'}
        if method == 'POST':
            sent.update({'Content-Type': 'application/json', 'X-EAOS-CSRF': self.csrf, 'Origin': self.origin})
        sent.update(headers or {})
        sent = {k: v for k, v in sent.items() if v is not None}
        request = urllib.request.Request(self.base + path, method=method, headers=sent,
                                         data=json.dumps(body or {}).encode() if method == 'POST' else None)
        try:
            with urllib.request.urlopen(request, timeout=120) as answer:
                return answer.status, json.loads(answer.read() or b'{}')
        except urllib.error.HTTPError as problem:
            try: payload = json.loads(problem.read() or b'{}')
            except ValueError: payload = {}
            return problem.code, payload

    def get(self, path):
        return self.call('GET', path)

    def post(self, path, body=None, headers=None):
        return self.call('POST', path, body, headers)

    def wait_run(self, run, states=('done', 'failed', 'stopped'), seconds=900):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            status, body = self.get(f'/api/runs/{run}')
            if status == 200 and body['run']['state'] in states: return body['run']
            time.sleep(2)
        raise TimeoutError(f'run {run} did not end')


class Trial:
    def __init__(self, out):
        self.out = Path(out)
        self.work = Path(tempfile.mkdtemp(prefix='branch-trial-'))
        os.environ.update(EAOS_HOME=str(self.work / 'home'), EAOS_OUTPUT=str(self.work / 'out'))
        self.cases = {'branch-control': {}, 'scan-freshness': {}}
        self.notes = []

    # ------------------------------------------------------------------ recording
    def case(self, kind, name, ok, evidence):
        self.cases[kind][name] = {'id': name, 'pass': bool(ok), 'kind': 'live', 'evidence': str(evidence)[:1500]}
        print(f"{'PASS' if ok else 'FAIL'} {kind} {name}: {str(evidence)[:300]}", flush=True)

    def guard(self, kind, name, fn):
        try: fn()
        except Exception as problem:
            self.case(kind, name, False, f'{type(problem).__name__}: {problem} {traceback.format_exc()[-600:]}')

    # ------------------------------------------------------------------ the repositories
    def build(self):
        from eaos import agent_tools
        self.origin = self.work / 'origin.git'
        git(self.work, 'init', '-q', '--bare', '-b', 'main', str(self.origin))
        self.project = self.work / 'shop'
        shutil.copytree(ROOT / 'tests/fixtures/polyglot', self.project)
        runnable(self.project)
        git(self.project, 'init', '-q', '-b', 'main')
        git(self.project, 'add', '-A')
        git(self.project, 'commit', '-q', '-m', 'first')
        git(self.project, 'branch', 'develop')
        git(self.project, 'remote', 'add', 'origin', str(self.origin))
        git(self.project, 'push', '-q', 'origin', 'main', 'develop')
        git(self.project, 'remote', 'set-head', 'origin', 'main')
        git(self.project, 'switch', '-q', '--detach', 'develop')     # the first scan reads a detached HEAD
        found = self._wait(agent_tools.audit(str(self.project)))
        self.notes.append(f"initial audit: {found.get('status')} {found.get('checked_commit')}")

    def _wait(self, answer):
        from eaos import agent_tools
        while isinstance(answer, dict) and answer.get('job') and answer.get('status') in ('running', 'busy', 'started'):
            answer = agent_tools.wait(answer['job'], 60)
        return answer

    # ------------------------------------------------------------------ the live Studio
    def serve(self):
        from eaos.api import launch
        from eaos.api.server import Keys, bind, create_app, serve
        state, report = launch.prepare(str(self.project))
        sock = bind(0)
        self.app = create_app(report, project=state['project'], keys=Keys(port=sock.getsockname()[1]))
        self.ctx = self.app.state.ctx
        self.servers = []
        threading.Thread(target=serve, args=(self.app, sock, self.servers.append), daemon=True).start()
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            try:
                self.api = Api(self.ctx.keys.port, self.ctx.keys.token)
                break
            except Exception:
                time.sleep(0.3)
        self.engine = self.ctx.session_extra.__self__            # the command centre's Actions this server mounted

    def browser(self, phase, extra=None):
        """The browser half for one phase; its JSON answer."""
        from eaos import toolchain
        env = {**os.environ, 'TRIAL_BASE': self.api.base + '/', 'TRIAL_TOKEN': self.ctx.keys.token, 'TRIAL_PHASE': phase,
               'TRIAL_OUT': str(self.out / 'branch-control'), 'TRIAL_EXTRA': json.dumps(extra or {}),
               'TRIAL_AXE': str(toolchain.node_modules('axe-core')), 'TRIAL_PLAYWRIGHT': str(toolchain.home() / 'node/node_modules')}
        done = subprocess.run(['node', str(ROOT / 'tools/studio_branch_trial.mjs')], env=env, capture_output=True, text=True, timeout=1800)
        try: return json.loads(done.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError): return {'error': (done.stderr or done.stdout)[-3000:]}

    def stop(self):
        if getattr(self, 'servers', None): self.servers[0].should_exit = True

    # ------------------------------------------------------------------ helpers over the live API
    def state(self):
        from eaos import guided
        return guided.load(self.project)

    def fresh(self):
        return self.api.get('/api/freshness')[1]['freshness']

    def take(self, kind, phase, mapping, extra=None):
        """Run one browser phase and record its checks under the acceptance case names."""
        answer = self.browser(phase, {'project': str(self.project), **(extra or {})})
        got = answer.get('checks') or {}
        for check, case in mapping.items():
            row = got.get(check)
            self.case(kind, case, bool(row and row['pass']), (row or {}).get('evidence') or f"browser phase {phase}: {answer.get('error') or answer.get('errors')}")
        if answer.get('errors'): self.notes.append(f"browser {phase}: {answer['errors'][:3]}")
        return answer

    def preview(self, source, target):
        return self.api.post('/api/branches/merge/preview', {'source': source, 'target': target})[1]

    def merge(self, p, ack=True):
        return self.api.post('/api/branches/merge', {'source': p['source'], 'target': p['target'], 'source_head': p['source_head'], 'target_head': p['target_head'],
                                                     'unchecked': p['needs_unchecked_ack'], 'unchecked_ack': ack, 'confirm': (p.get('confirm') or {}).get('token')})

    def row(self, name, kind='local'):
        inventory = self.api.get('/api/branches?base=develop')[1]
        return next((r for r in inventory['branches'] if r['name'] == name and r['kind'] == kind), None), inventory

    # ------------------------------------------------------------------ phases
    def detached_first(self):
        """The first scan is made on a detached HEAD, which is named as such with its commit."""
        F, B = 'scan-freshness', 'branch-control'
        state = self.state()
        context = self.api.get('/api/context')[1]['context']
        inventory = self.api.get('/api/branches')[1]
        manifest = self.api.get('/api/manifest')[1]
        self.case(F, 'scan_records_branch_full_commit_dirty_and_times',
                  state.get('scanned_detached') is True and len(state.get('scanned_commit') or '') == 40 and state.get('scanned_dirty') is False
                  and state.get('scanned', '').endswith('+00:00') and manifest['scanned'].get('recorded') is True and manifest['built']['built'],
                  f"state: branch {state.get('scanned_branch')} detached {state.get('scanned_detached')} commit {state.get('scanned_commit')} dirty "
                  f"{state.get('scanned_dirty')} at {state.get('scanned')}; manifest scanned {manifest['scanned']}; built {manifest['built']['built']}")
        answer = self.take(F, 'detached', {'detached_scan_named': 'detached_head'})
        ok = context['checkout']['detached'] and context['checkout']['branch'] is None and not any(r['name'] == 'HEAD' for r in inventory['branches'])
        chip = (answer.get('checks') or {}).get('detached_chip') or {}
        self.case(B, 'detached_head_named_state', ok and chip.get('pass'), f"context checkout {context['checkout']}; no synthetic HEAD branch: "
                  f"{not any(r['name'] == 'HEAD' for r in inventory['branches'])}; UI {chip.get('evidence')}")

    def rescan(self):
        F = 'scan-freshness'
        git(self.project, 'switch', '-q', 'develop')
        commit(self.project, 'NOTES.md', '# Notes\n\nThe owner keeps working after the scan.\n', 'owner notes after the scan')
        before = self.state().get('scanned')
        self.take(F, 'rescan', {'rescan_roundtrip': 'rescan_roundtrip_live_command_centre'})
        state = self.state()
        self.case(F, 'fresh_state', self.fresh()['state'] == 'fresh' and state.get('scanned_branch') == 'develop' and state.get('scanned_detached') is False,
                  f"after the Studio's re-scan on develop: {self.fresh()['state']}; scanned {before} -> {state.get('scanned')}, branch {state.get('scanned_branch')}")

    def freshness_cases(self):
        F = 'scan-freshness'
        scanned = self.state()['scanned_commit']
        answer = self.take(F, 'freshness', {'behind_without_reload': 'behind_commits_files_listed_without_reload', 'dirty_tree': 'dirty_tree',
                                            'rewritten': 'rewritten_branch', 'branch_switch': 'branch_switch', 'copy_fallback': 'copy_fallback_complete'},
                           {'scanned': scanned})
        got = answer.get('checks') or {}
        parts = [got.get(k) or {} for k in ('focus_refresh', 'interval_refresh', 'run_completion_refresh')]
        self.case(F, 'refresh_on_focus_interval_and_run_completion', all(p.get('pass') for p in parts), ' / '.join(str(p.get('evidence')) for p in parts))

    def legacy(self):
        from eaos import guided
        F = 'scan-freshness'
        saved = self.state()
        legacy = {k: v for k, v in saved.items() if k not in ('scanned_commit', 'scanned_branch', 'scanned_detached', 'scanned_dirty')}
        guided.save(legacy)
        guided.publish(legacy)
        try:
            found = self.fresh()
            answer = self.take(F, 'legacy', {'legacy': 'legacy_report_labelled_with_rescan'})
            self.notes.append(f"legacy: api {found['state']}/{found['reason']}")
        finally:
            guided.save(saved)
            guided.publish(saved)

    def inventory_cases(self):
        B = 'branch-control'
        api, project = self.api, self.project
        # branches: a tool-owned task branch with its provenance, a human one under a tool-like name, a stale remote one
        git(project, 'switch', '-q', '-c', 'eaos/task-1', 'develop')
        self.task_tip = commit(project, 'feature.js', 'export const feature = 1\n', 'task work', env=EAOS)
        git(project, 'switch', '-q', '-c', 'eaos/not-ours', 'develop')
        commit(project, 'human.js', 'export const human = 1\n', 'human work under a tool-like name')
        git(project, 'switch', '-q', 'develop')
        self.engine.branches.record('eaos/task-1', kind='task', base='develop', base_commit=git(project, 'rev-parse', 'develop'), tip=self.task_tip)
        git(project, 'push', '-q', 'origin', 'develop:old-feature')
        git(project, 'fetch', '-q', 'origin')
        git(self.origin, 'branch', '-D', 'old-feature')
        rows = api.get('/api/branches?base=develop')[1]
        names = {(r['kind'], r['name']) for r in rows['branches']}
        self.case(B, 'inventory_local_remote_refs', {('local', 'main'), ('local', 'develop'), ('local', 'eaos/task-1'), ('remote', 'main'), ('remote', 'develop')} <= names
                  and rows['default'] == {'name': 'main', 'source': 'origin/HEAD'},
                  f"{sorted(names)}; default {rows['default']}; remotes {rows['remotes']}")
        stale, _ = self.row('old-feature', 'remote')
        fetched = api.post('/api/branches/fetch', {'remote': 'origin'})[1]['run']
        gone, after = self.row('old-feature', 'remote')
        self.case(B, 'stale_remote_refs_last_known_until_fetch', stale is not None and stale['remote_as_of'] and gone is None and fetched['state'] == 'done',
                  f"deleted on origin, still shown as last known (as of {stale and stale['remote_as_of']}); after the Studio's refresh run {fetched['id']} "
                  f"({fetched['state']}): gone={gone is None}; last fetch {after['last_fetch']}")
        mine, _ = self.row('eaos/task-1')
        human, _ = self.row('eaos/not-ours')
        self.case(B, 'ownership_known_and_unknown_by_provenance', mine['ownership']['owner'] == 'eaos' and human['ownership']['owner'] == 'unknown',
                  f"eaos/task-1: {mine['ownership']['owner']} ({mine['ownership']['evidence']}); eaos/not-ours: {human['ownership']['owner']} (same prefix, no record)")
        git(project, 'branch', 'eaos/task-2', 'develop')
        self.engine.branches.record('eaos/task-2', kind='task', base='develop', base_commit=git(project, 'rev-parse', 'develop'))
        tree = self.work / 'wt-task-2'
        git(project, 'worktree', 'add', '-q', str(tree), 'eaos/task-2')
        (tree / 'scratch.txt').write_text('unsaved\n')
        held, _ = self.row('eaos/task-2')
        blocked = api.post('/api/branches/delete/preview', {'branch': 'eaos/task-2'})[1]['blocked']
        self.case(B, 'worktree_status', held['worktree'] and not held['worktree']['current'] and held['worktree']['dirty'] == {'tracked': 0, 'untracked': 1}
                  and 'checked_out' in [r['code'] for r in blocked],
                  f"worktree {held['worktree']}; deletion blocked: {[r['code'] for r in blocked]}")
        (self.project / 'package.json').write_text((self.project / 'package.json').read_text() + '\n')
        context = api.get('/api/context')[1]['context']
        dirty_preview = self.preview('eaos/task-1', 'develop')
        git(project, 'checkout', '--', 'package.json')
        self.case(B, 'dirty_checkout_reported', context['dirty'] == {'tracked': 1, 'untracked': 0}, f"context dirty {context['dirty']}")
        self.case(B, 'dirty_target_refused', 'dirty_target' in [r['code'] for r in dirty_preview['blocked']] and dirty_preview['confirm'] is None,
                  f"merge preview into the dirty checked-out develop: {[r['code'] for r in dirty_preview['blocked']]}; confirm token {dirty_preview['confirm']}")
        git(project, 'remote', 'remove', 'origin')
        try:
            lone = api.get('/api/branches')[1]
            self.case(B, 'no_origin_valid_state', lone['git'] and not lone['has_origin'] and lone['remotes'] == [] and lone['default'] == {'name': None, 'source': None}
                      and lone['branches'] and all(r['kind'] == 'local' for r in lone['branches']),
                      f"no remote at all: has_origin {lone['has_origin']}, remotes {lone['remotes']}, default {lone['default']} (unknown, not guessed); "
                      f"{len(lone['branches'])} local branches listed")
        finally:
            git(project, 'remote', 'add', 'origin', str(self.origin))
            git(project, 'fetch', '-q', 'origin')
            git(project, 'remote', 'set-head', 'origin', 'main')

    def selection_cases(self):
        B = 'branch-control'
        api, project = self.api, self.project
        before = git(project, 'rev-parse', 'HEAD'), git(project, 'symbolic-ref', '--short', 'HEAD')
        status, chosen = api.post('/api/branches/analysis', {'branch': 'eaos/not-ours'})
        after = git(project, 'rev-parse', 'HEAD'), git(project, 'symbolic-ref', '--short', 'HEAD')
        api.post('/api/branches/analysis', {'branch': 'develop'})
        analysis = (chosen.get('context') or {}).get('analysis', {}).get('branch')
        self.case(B, 'select_analysis_without_checkout_change', status == 200 and before == after and analysis == 'eaos/not-ours',
                  f"analysis -> {analysis}; checkout {before} == {after}; run {(chosen.get('run') or {}).get('id')} {(chosen.get('run') or {}).get('state')}; "
                  f"{chosen.get('error') or ''} back to develop")
        # an in-flight run: a real scan started from the Studio (the code moved since the last one)
        commit(project, 'IN-FLIGHT.md', 'a change so the scan has work to do\n', 'owner change before a scan')
        made = api.post('/api/runs', {'action': 'audit', 'inputs': {}})
        run = made[1].get('run')
        if not run: self.notes.append(f'in-flight run not created: {made}')
        time.sleep(1)
        refused = api.post('/api/branches/analysis', {'branch': 'main'})
        if refused[0] == 200: api.post('/api/branches/analysis', {'branch': 'develop'})
        kept = api.get(f"/api/runs/{run['id']}")[1]['run'] if run else {}
        if run: api.wait_run(run['id'])
        self.case(B, 'in_flight_runs_not_retargeted', run and refused[0] == 409 and refused[1].get('needs') == 'in_flight' and kept['context']['analysis_branch'] == 'develop'
                  and self.state().get('branch') in (None, 'develop'),
                  f"run {run and run['id']} {kept.get('state')} on {kept.get('context', {}).get('analysis_branch')}; choosing main: {refused[0]} {refused[1].get('needs')}")

    def merge_cases(self):
        B = 'branch-control'
        api, project = self.api, self.project
        develop = git(project, 'rev-parse', 'develop')
        p = self.preview('eaos/task-1', 'develop')
        self.case(B, 'isolated_merge_preview_expected_heads', p['blocked'] == [] and p['confirm'] and p['target_head'] == develop == git(project, 'rev-parse', 'develop')
                  and p['source_head'] == self.task_tip and [f['path'] for f in p['files']] == ['feature.js'],
                  f"preview {p['path']} ff={p['fast_forward']} files {[f['path'] for f in p['files']]}; heads {p['source_head'][:12]} -> {p['target_head'][:12]}; develop unchanged")
        # stale: the source moves after the preview
        git(project, 'update-ref', 'refs/heads/eaos/task-1', commit_tree(project, self.task_tip, 'feature.js', 'export const feature = 2\n'))
        status, body = self.merge(p)
        self.case(B, 'stale_head_invalidates_preview', status == 409 and body.get('needs') == 'refresh' and git(project, 'rev-parse', 'develop') == develop,
                  f"merge with the old preview: {status} {body.get('needs')} ({body.get('error')}); develop still {develop[:12]}")
        self.task_tip = git(project, 'rev-parse', 'eaos/task-1')
        self.engine.branches.record('eaos/task-1', tip=self.task_tip)
        # one change at a time
        held = self.engine.branches._locked()
        try:
            status, body = self.merge(self.preview('eaos/task-1', 'develop'))
        finally:
            held.close()
        self.case(B, 'concurrent_mutation_locked', status == 409 and any(r['code'] == 'locked' for r in body.get('reasons') or []) and git(project, 'rev-parse', 'develop') == develop,
                  f"while another change holds the project's branch lock: {status} {[r['code'] for r in body.get('reasons') or []]}")
        # failed checks of this exact commit block
        self.engine.branches.record('eaos/task-1', checks={'commit': self.task_tip, 'status': 'failed', 'at': now(), 'summary': 'unit tests failed (recorded by the trial)'})
        failed = self.preview('eaos/task-1', 'develop')
        self.case(B, 'failed_checks_block_merge', 'checks_failed' in [r['code'] for r in failed['blocked']] and failed['confirm'] is None,
                  f"recorded failed checks on {self.task_tip[:12]}: {[r['code'] for r in failed['blocked']]}")
        self.engine.branches.record('eaos/task-1', checks={'commit': self.task_tip, 'status': 'passed', 'at': now(), 'summary': 'unit tests passed (recorded by the trial)'})
        # protected destination, even with a forged token
        guarded = self.preview('eaos/task-1', 'main')
        forged = {**guarded, 'confirm': self.engine.locks.confirm('branch_merge', {'source': 'eaos/task-1', 'target': 'main', 'source_head': guarded['source_head'],
                                                                                  'target_head': guarded['target_head'], 'unchecked': guarded['needs_unchecked_ack']}, self.engine.project)}
        main = git(project, 'rev-parse', 'main')
        status, body = self.merge(forged)
        self.case(B, 'protected_destination_refused_by_backend', 'protected_target' in [r['code'] for r in guarded['blocked']] and status == 409 and git(project, 'rev-parse', 'main') == main,
                  f"preview into main: {[r['code'] for r in guarded['blocked']]}; a correctly signed token still refused by the backend: {status} {[r['code'] for r in body.get('reasons') or []]}")
        # conflict: nothing changes, a read-only proposal is queued
        git(project, 'switch', '-q', '-c', 'eaos/task-3', 'develop')
        clash = commit(project, 'app.js', 'export const app = "branch"\n', 'task 3', env=EAOS)
        git(project, 'switch', '-q', 'develop')
        self.engine.branches.record('eaos/task-3', kind='task', base='develop', base_commit=develop, tip=clash)
        mainline = commit(project, 'app.js', 'export const app = "develop"\n', 'develop changes the same place')
        c = self.preview('eaos/task-3', 'develop')
        status, proposal = api.post('/api/branches/conflict', {'source': 'eaos/task-3', 'target': 'develop', 'assistant': 'handoff'})
        self.case(B, 'conflict_kept_and_resolution_proposal', c['conflicts'] == ['app.js'] and status == 200 and proposal['run']['action'] == 'branch_conflict'
                  and git(project, 'rev-parse', 'eaos/task-3') == clash and git(project, 'rev-parse', 'develop') == mainline,
                  f"conflicts {c['conflicts']}; proposal run {proposal.get('run', {}).get('id')} ({proposal.get('run', {}).get('mode')}); both heads unchanged")
        if status == 200: api.post(f"/api/runs/{proposal['run']['id']}/stop")
        # the real merge of the tool-owned task branch
        p = self.preview('eaos/task-1', 'develop')
        status, done = self.merge(p)
        self.merged_run = (done.get('run') or {}).get('id')
        self.notes.append(f"task merge: {status} {(done.get('run') or {}).get('outcome')} via {(done.get('run') or {}).get('result', {}).get('answer', {}).get('via')}")

    def guard_cases(self):
        B = 'branch-control'
        api, project = self.api, self.project
        refs = git(project, 'for-each-ref')
        tries = []
        for headers in ({'X-EAOS-CSRF': 'wrong'}, {'Origin': 'http://evil.example'}, {'X-EAOS-Token': 'x' * 43}, {'X-EAOS-CSRF': None}):
            tries.append(api.post('/api/branches/analysis', {'branch': 'main'}, headers=headers)[0])
            tries.append(api.post('/api/branches/delete', {'branch': 'eaos/task-2', 'tip': 'x', 'confirm': 'x'}, headers=headers)[0])
        self.case(B, 'auth_csrf_origin_failures_mutate_nothing', all(s in (401, 403) for s in tries) and git(project, 'for-each-ref') == refs and self.state().get('branch') in (None, 'develop'),
                  f"statuses {tries}; refs unchanged; analysis branch {self.state().get('branch')}")
        marker = self.work / 'pwned'
        statuses = []
        for name in (f'x;touch {marker}', '$(touch {marker})', '--output=/tmp/x', '../../etc/passwd', 'a..b', 'refs/heads/../x', '-x', ''):
            statuses.append(api.post('/api/branches/merge/preview', {'source': name, 'target': 'develop'})[0])
            statuses.append(api.post('/api/branches/delete/preview', {'branch': name})[0])
        other = self.work / 'other'
        other.mkdir()
        git(other, 'init', '-q', '-b', 'main')
        commit(other, 'a.txt', 'a\n', 'a')
        cross = api.post('/api/branches/analysis', {'branch': 'develop', 'project': str(other)})
        detail = api.get('/api/branches/detail?name=develop&kind=local&path=../../etc/passwd')
        from eaos import guided
        self.case(B, 'invalid_names_and_cross_project_refused', all(s in (400, 404, 409) for s in statuses) and not marker.exists() and guided.load(other) is None
                  and git(other, 'for-each-ref') and detail[0] in (400, 404),
                  f"bad names -> {sorted(set(statuses))}; no file written by a name: {not marker.exists()}; a body naming another project acted on this one only "
                  f"({cross[0]}, the other project has no EAOS state); a path outside the branch -> {detail[0]}")

    def delete_cases(self):
        B = 'branch-control'
        api, project = self.api, self.project
        p = api.post('/api/branches/delete/preview', {'branch': 'eaos/task-1'})[1]
        status, done = api.post('/api/branches/delete', {'branch': 'eaos/task-1', 'tip': p['tip'], 'unmerged': p['unmerged'], 'confirm': (p['confirm'] or {}).get('token')})
        recovery = (done.get('run') or {}).get('result', {}).get('answer', {}).get('recovery')
        kept = git(project, 'rev-parse', f'refs/eaos-recovery/{recovery}', check=False) if recovery else ''
        self.case(B, 'merged_branch_deleted_with_recovery_ref', p['unmerged'] is False and status == 200 and kept == p['tip']
                  and not git(project, 'rev-parse', '--verify', '--quiet', 'refs/heads/eaos/task-1', check=False),
                  f"merged into {p['merged_into']}; deleted by run {(done.get('run') or {}).get('id')}; recovery ref refs/eaos-recovery/{recovery} -> {kept[:12]}")
        status, back = api.post('/api/branches/restore', {'recovery': recovery})
        self.case(B, 'recovery_restores_branch', status == 200 and git(project, 'rev-parse', 'eaos/task-1') == p['tip'],
                  f"restore run {(back.get('run') or {}).get('id')}: eaos/task-1 back at {p['tip'][:12]}")
        # unmerged: a second confirmation
        git(project, 'switch', '-q', '-c', 'eaos/task-4', 'develop')
        lone = commit(project, 'only.js', 'export const only = 1\n', 'work only on task 4', env=EAOS)
        git(project, 'switch', '-q', 'develop')
        self.engine.branches.record('eaos/task-4', kind='task', base='develop', base_commit=git(project, 'rev-parse', 'develop'), tip=lone)
        p = api.post('/api/branches/delete/preview', {'branch': 'eaos/task-4'})[1]
        body = {'branch': 'eaos/task-4', 'tip': p['tip'], 'unmerged': True, 'confirm': (p['confirm'] or {}).get('token')}
        first = api.post('/api/branches/delete', body)
        still = git(project, 'rev-parse', 'eaos/task-4')
        p = api.post('/api/branches/delete/preview', {'branch': 'eaos/task-4'})[1]
        second = api.post('/api/branches/delete', {**body, 'confirm': p['confirm']['token'], 'confirm_unmerged': p['confirm_unmerged']['token']})
        self.case(B, 'unmerged_delete_needs_extra_confirmation', p['unmerged'] and [c['commit'] for c in p['lost_commits']] == [lone] and first[0] == 403
                  and first[1].get('needs') == 'confirm_unmerged' and still == lone and second[0] == 200,
                  f"lost-commit preview {[c['commit'][:12] for c in p['lost_commits']]}; one confirmation: {first[0]} {first[1].get('needs')} (branch kept); "
                  f"with the second: {second[0]}, recovery {(second[1].get('run') or {}).get('result', {}).get('answer', {}).get('recovery')}")
        # remote deletion: its own consent
        git(project, 'branch', 'eaos/task-5', 'develop')
        git(project, 'switch', '-q', 'eaos/task-5')
        five = commit(project, 'five.js', 'export const five = 5\n', 'task 5', env=EAOS)
        git(project, 'switch', '-q', 'develop')
        self.engine.branches.record('eaos/task-5', kind='task', base='develop', base_commit=git(project, 'rev-parse', 'develop'), tip=five)
        git(project, 'push', '-q', 'origin', 'eaos/task-5')
        git(project, 'fetch', '-q', 'origin')
        local = api.post('/api/branches/delete/preview', {'branch': 'eaos/task-5'})[1]
        wrong = api.post('/api/branches/delete', {'branch': 'eaos/task-5', 'where': 'remote', 'remote': 'origin', 'tip': five, 'confirm': local['confirm']['token']})
        on_origin = git(self.origin, 'rev-parse', '--verify', '--quiet', 'refs/heads/eaos/task-5', check=False)
        remote = api.post('/api/branches/delete/preview', {'branch': 'eaos/task-5', 'where': 'remote', 'remote': 'origin'})[1]
        right = api.post('/api/branches/delete', {'branch': 'eaos/task-5', 'where': 'remote', 'remote': 'origin', 'tip': remote['tip'], 'confirm': remote['confirm']['token']})
        gone = not git(self.origin, 'rev-parse', '--verify', '--quiet', 'refs/heads/eaos/task-5', check=False)
        self.case(B, 'remote_delete_separate_consent', wrong[0] == 403 and on_origin == five and right[0] == 200 and gone and git(project, 'rev-parse', 'eaos/task-5') == five,
                  f"the local deletion's consent used for the remote: {wrong[0]} {wrong[1].get('needs')} (origin kept); the remote's own consent: {right[0]}, "
                  f"gone on origin {gone}, local branch kept, recovery {(right[1].get('run') or {}).get('result', {}).get('answer', {}).get('recovery')}")

    def wave_cases(self):
        """One real managed EAOS batch, started and finished from the Studio's command centre, accepted from Branches."""
        from eaos import guided
        from eaos.ledger import load as ledger
        B = 'branch-control'
        api = self.api
        from eaos import agent_tools
        started = []
        for action, inputs in (('run_setup', {'person_agreed': True}), ('safety_net', {}), ('fix_start', {}), ('fix_finish', {})):
            preview = api.post(f'/api/actions/{action}/preview', {'inputs': inputs})[1]
            status, made = api.post('/api/runs', {'action': action, 'inputs': inputs, 'confirm': (preview.get('confirm') or {}).get('token')})
            run = api.wait_run(made['run']['id']) if status == 200 else {'state': f'refused {status} {made}'}
            started.append(run)
        finish = started[-1]
        self.wave_run = finish.get('id')
        wave = next((w for w in reversed(self.state().get('waves') or []) if w.get('status') == 'applied'), None)
        if not wave:
            self.case(B, 'managed_wave_accept_report_ledger_exactly_once', False, f"no applied batch: {[(r.get('action'), r.get('state'), (r.get('result') or {}).get('answer')) for r in started]}")
            self.case(B, 'run_branch_relation_restart_and_deleted_ref', False, 'no batch branch to follow')
            return
        branch = wave['branch']
        linked = api.get(f'/api/runs/{self.wave_run}')[1]['run']['work_branch']
        # restart: a new live server on the same project reads the same relation
        self.stop()
        time.sleep(1)
        self.serve()
        relinked = self.api.get(f'/api/runs/{self.wave_run}')[1]['run']['work_branch']
        api = self.api
        totals = (ledger(self.state()) or {}).get('totals')
        built = guided.report_stamp(self.state()).get('built')
        studio_data = Path(self.ctx.report) / 'studio'
        card_state = lambda: {c['id']: c.get('state') for c in json.loads((studio_data / 'cards.json').read_text()).get('cards') or [] if c['id'] in (wave.get('kept') or [])}
        sections = lambda: {e['name']: e['sha256'] for e in json.loads((studio_data / 'manifest.json').read_text())['sections']}
        cards_before, sections_before = card_state(), sections()
        p = self.preview(branch, 'develop')
        status, done = self.merge(p)
        after_totals = (ledger(self.state()) or {}).get('totals')
        after_built = guided.report_stamp(self.state()).get('built')
        cards_after = card_state()
        changed = sorted(name for name, sha in sections().items() if sections_before.get(name) != sha)
        again = api.post('/api/branches/merge/preview', {'source': branch, 'target': 'develop'})
        accept_again = agent_tools.accept(str(self.project), person_agreed=True)
        once_totals = (ledger(self.state()) or {}).get('totals')
        gone = api.get(f'/api/runs/{self.wave_run}')[1]['run']['work_branch']
        history = [w for w in self.state().get('waves') or [] if w.get('branch') == branch]
        self.case(B, 'managed_wave_accept_report_ledger_exactly_once',
                  p['path'] == 'accept' and status == 200 and (done.get('run') or {}).get('outcome') == 'accepted' and (after_totals or {}).get('done', 0) == (totals or {}).get('done', 0) + len(wave.get('kept') or [])
                  and all(v == 'done' for v in cards_after.values()) and cards_after != cards_before and changed and again[0] in (404, 409, 400) and accept_again.get('status') == 'nothing_waiting' and once_totals == after_totals
                  and len(history) == 1 and history[0].get('status') == 'accepted',
                  f"batch {wave['number']} on {branch} made by Studio runs {[r.get('id') for r in started]}; preview path {p['path']}; merge {status} outcome "
                  f"{(done.get('run') or {}).get('outcome')}; ledger done {(totals or {}).get('done')} -> {(after_totals or {}).get('done')}; report built {built} -> {after_built}, "
                  f"cards in the report {cards_before} -> {cards_after}, report sections rewritten {changed}; "
                  f"a second merge {again[0]}, a second accept {accept_again.get('status')}, ledger then {once_totals}; wave records {len(history)} ({history[0].get('status') if history else None})")
        self.case(B, 'run_branch_relation_restart_and_deleted_ref', linked.get('name') == branch and linked.get('state') == 'exists' and relinked == linked
                  and gone.get('state') in ('merged_and_deleted', 'deleted') and gone.get('recorded_tip') == linked.get('recorded_tip'),
                  f"run {self.wave_run}: during {linked}; after a server restart {relinked}; after accept deleted the branch {gone}")
        self.work_branch = branch

    def rescan_branch(self):
        F, B = 'scan-freshness', 'branch-control'
        answer = self.take(F, 'rescan_branch', {'rescan_branch': 'rescan_this_branch'}, {'branch': 'main', 'back': 'develop'})
        row = (answer.get('checks') or {}).get('ui_selected_branch_report_consistency') or {}
        self.case(B, 'ui_selected_branch_report_consistency', bool(row.get('pass')), row.get('evidence') or answer.get('errors'))

    def zones(self):
        F = 'scan-freshness'
        before = self.state().get('scanned')
        run = (self.api.get('/api/runs?all=1')[1]['runs'] or [{}])[0].get('id')
        self.take(F, 'zones', {'device_time_zone_non_utc': 'device_time_zone_non_utc', 'half_hour_offset_time_zone': 'half_hour_offset_time_zone',
                               'time_zone_override_persisted': 'time_zone_override_persisted',
                               'relative_and_exact_zoned_times_everywhere': 'relative_and_exact_zoned_times_everywhere'}, {'run': run})
        runs = self.api.get('/api/runs?all=1')[1]['runs']
        state = self.state()
        stored = [state.get('scanned')] + [r.get('created') for r in runs[:5]]
        self.case(F, 'utc_storage_unchanged', all(str(v).endswith('+00:00') for v in stored if v) and state.get('scanned') == before,
                  f"stored after browsing in Asia/Dubai, Asia/Kolkata and America/St_Johns: {stored}")

    def snapshot(self):
        F = 'scan-freshness'
        site = self.work / 'snapshot'
        shutil.copytree(ROOT / 'eaos/data/studio', site, dirs_exist_ok=True)
        for script in (Path(self.ctx.report) / 'studio').glob('*.js'): shutil.copy(script, site / script.name)
        self.take(F, 'snapshot', {'static_snapshot': 'static_snapshot_read_only_open_live'}, {'snapshot': str(site / 'index.html')})

    def ui(self):
        F, B = 'scan-freshness', 'branch-control'
        plans = json.loads((Path(self.ctx.report) / 'studio' / 'plans.json').read_text()) if (Path(self.ctx.report) / 'studio' / 'plans.json').is_file() else {}
        plan = (plans.get('plans') or [{}])[0]
        step = (plan.get('steps') or [{}])[0]
        cards = json.loads((Path(self.ctx.report) / 'studio' / 'cards.json').read_text()).get('cards') or []
        routes = [r for r in ([f"/plans/{plan['id']}/{step['id']}"] if plan.get('id') and step.get('id') else []) + ([f"/problems?card={cards[0]['id']}"] if cards else [])]
        # the drawer's merge on a tool-owned branch whose head moves under the open preview
        git(self.project, 'branch', '-f', 'eaos/task-6', 'develop')
        six = commit_tree(self.project, git(self.project, 'rev-parse', 'develop'), 'six.js', 'export const six = 6\n')
        git(self.project, 'update-ref', 'refs/heads/eaos/task-6', six)
        self.engine.branches.record('eaos/task-6', kind='task', base='develop', base_commit=git(self.project, 'rev-parse', 'develop'), tip=six)
        moved = commit_tree(self.project, six, 'six.js', 'export const six = 66\n')
        answer = self.take(B, 'ui', {'ui_task_run_branch_links': 'ui_task_run_branch_links', 'ui_error_recovery': 'ui_error_recovery'},
                           {'run': getattr(self, 'wave_run', None), 'workBranch': getattr(self, 'work_branch', 'eaos/wave-1'),
                            'stale': {'branch': 'eaos/task-6', 'moveTo': moved}, 'directRoutes': routes})
        got = answer.get('checks') or {}
        keyboard = got.get('keyboard') or {}
        governance = got.get('governance') or {}
        self.keyboard = keyboard
        self.case(F, 'governance_current_actionable_direct', bool(governance.get('pass')), governance.get('evidence') or answer.get('errors'))

    def realtime(self):
        self.take('branch-control', 'realtime_branches', {'ui_realtime_state': 'ui_realtime_state'}, {'newBranch': 'feature/made-outside'})

    def views(self):
        answer = self.browser('views', {'project': str(self.project)})
        self.views = answer.get('views') or []
        keyboard = getattr(self, 'keyboard', {}) or {}
        small = sum(v.get('small_targets', 1) for v in self.views)
        self.case('branch-control', 'keyboard_and_44px_targets', bool(keyboard.get('pass')) and len(self.views) == 12 and small == 0,
                  f"keyboard: {keyboard.get('evidence')}; targets under 44px across {len(self.views)} views (page, drawer, scan sheet): {small} "
                  f"{[v.get('small') for v in self.views if v.get('small_targets')][:3]}")
        if answer.get('errors'): self.notes.append(f"views: {answer['errors'][:3]}")


def commit_tree(project, parent, path, text):
    """A new EAOS commit on top of `parent` changing one file, without touching any checkout: its id."""
    blob = subprocess.run(['git', '-C', str(project), 'hash-object', '-w', '--stdin'], input=text, capture_output=True, text=True, check=True).stdout.strip()
    env = {**os.environ, 'GIT_INDEX_FILE': str(Path(tempfile.mkdtemp()) / 'index'), **EAOS}
    subprocess.run(['git', '-C', str(project), 'read-tree', parent], env=env, check=True)
    subprocess.run(['git', '-C', str(project), 'update-index', '--add', '--cacheinfo', f'100644,{blob},{path}'], env=env, check=True)
    tree = subprocess.run(['git', '-C', str(project), 'write-tree'], env=env, capture_output=True, text=True, check=True).stdout.strip()
    return subprocess.run(['git', '-C', str(project), 'commit-tree', tree, '-p', parent, '-m', 'task work moves on'], env=env, capture_output=True, text=True, check=True).stdout.strip()


def runnable(project):
    """The fixture's start script names api/server.js, which it does not ship: a tiny real HTTP server there, so the
    app answers and EAOS can record its screens (run_setup, then the batch's gates)."""
    (project / 'package.json').write_text(json.dumps({'name': 'shop', 'version': '1.0.0', 'private': True, 'scripts': {'start': 'node api/server.js'}}, indent=1) + '\n')
    (project / '.env.example').write_text('PORT=3000\n')
    (project / 'api/server.js').write_text(
        "const http = require('http')\nconst port = Number(process.env.PORT || 3000)\n"
        "http.createServer((req, res) => { res.setHeader('content-type', 'text/html; charset=utf-8'); "
        "res.end('<!doctype html><html lang=\"en\"><head><title>Shop</title></head><body><main><h1>Shop</h1><p>Open.</p></main></body></html>') })"
        ".listen(port, '127.0.0.1')\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    import north_star_measure as measure
    parser.add_argument('--out', default=str(measure.REPORTS))
    args = parser.parse_args(argv)
    import north_star_studio as studio
    trial = Trial(args.out)
    started = now()
    steps = []
    try:
        trial.build()
        trial.serve()
        for name in ('detached_first', 'rescan', 'freshness_cases', 'legacy', 'wave_cases', 'rescan_branch', 'zones', 'snapshot',
                     'inventory_cases', 'selection_cases', 'merge_cases', 'guard_cases', 'delete_cases', 'ui', 'realtime', 'views'):
            t = time.monotonic()
            try: getattr(trial, name)()
            except Exception as problem:
                trial.notes.append(f'{name}: {type(problem).__name__}: {problem} {traceback.format_exc()[-800:]}')
                print(f'STEP FAILED {name}: {problem}', flush=True)
            steps.append({'step': name, 'seconds': round(time.monotonic() - t, 1)})
    finally:
        trial.stop()
    import importlib
    sys.path.insert(0, str(ROOT / 'acceptance'))
    for kind, module in (('branch-control', 'test_branch_control'), ('scan-freshness', 'test_scan_freshness')):
        accepted = importlib.import_module(module)
        rows = [trial.cases[kind].get(case) or {'id': case, 'pass': False, 'kind': 'live', 'evidence': 'not reached in this run'} for case in accepted.CASES]
        record = {'schema_version': 1, 'kind': 'live', 'mocked': False, 'task': 'NS46.T18' if kind == 'branch-control' else 'NS46.T19',
                  'tool': 'tools/studio_branch_trial.py', 'started_at': started, 'completed_at': now(), 'studio_source_sha256': studio.shipped(),
                  'eaos_commit': git(ROOT, 'rev-parse', 'HEAD'), 'repositories': str(trial.work), 'assistant': None,
                  'about': 'Real temporary git repositories, the real EAOS audit and fix pipeline, the live Studio server of this checkout and its '
                           'shipped build in Chromium. No assistant was launched; scripted git changes stand for the person working in their folder.',
                  'cases': rows, 'views': trial.views, 'steps': steps, 'notes': trial.notes,
                  'passed': sum(1 for r in rows if r['pass']), 'total': len(rows)}
        folder = Path(args.out) / kind
        folder.mkdir(parents=True, exist_ok=True)
        (folder / 'trial.json').write_text(json.dumps(record, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
        missing = accepted.judge(folder / 'trial.json', accepted.CASES)
        print(f'{kind}: {record["passed"]}/{record["total"]} cases; acceptance missing {len(missing)}: {missing[:8]}', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
