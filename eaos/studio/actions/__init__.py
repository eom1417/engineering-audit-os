"""The command centre's action API (docs/studio-actions.json, docs/STUDIO.md D8): run EAOS from the Studio.

Framework-agnostic: `Actions.handle(method, path, headers, body)` answers every endpoint of the contract with
`(status, dict)`, and `Actions.sse(run, last_event_id, follow)` yields a run's events as Server-Sent Events frames. The
local server (NS37.T2) mounts them with `mount(...)` (eaos/studio/actions/serve.py); the tests call them directly.

    actions = Actions(project, port=8765)            # the launch token and the CSRF token are made here
    status, payload = actions.handle('POST', '/api/runs', headers, {'action': 'audit'})
    for frame in actions.sse(run_id, last_event_id=12, follow=True): ...

Every call passes the locks of eaos/studio/actions/security.py first; every accepted action becomes an `action` event
before it runs; reading actions answer at once, the others queue as runs (eaos/studio/actions/runs.py).
"""
import functools
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from . import adapters as adapters_module
from . import handoff, selection as selecting
from .runs import PLANNERS, Manager
from .security import Locks
from .store import ACTIVE, TERMINAL, Scrubber, Store, now

CONTRACT = Path(__file__).resolve().parents[2] / 'data/studio-actions.json'
VERBS = ('fix', 'verify', 'explain', 'plan')
HEARTBEAT = 15


@functools.lru_cache(maxsize=1)
def contract():
    """The packaged contract (a byte-identical copy of docs/studio-actions.json)."""
    return json.loads(CONTRACT.read_text(encoding='utf-8'))


@functools.lru_cache(maxsize=1)
def _server_tools():
    from ... import mcp_server
    return mcp_server.functions()


@functools.lru_cache(maxsize=1)
def reading_tools():
    """The tools the MCP server marks read-only: they answer at once and are not queued."""
    from ... import mcp_server
    return mcp_server.reading()


class Refused(Exception):
    def __init__(self, status, reason, **extra):
        super().__init__(reason)
        self.status, self.reason, self.extra = status, reason, extra


def _run_id():
    return 'r' + datetime.now().strftime('%Y%m%d-%H%M%S-') + os.urandom(3).hex()


class Actions:
    def __init__(self, project, home=None, port=8765, adapters=None, studio=None, lang='ar', token=None):
        from ... import guided
        if home: os.environ['EAOS_HOME'] = str(home)
        self.project = Path(project).expanduser().resolve()
        self.locks = Locks(port, token)
        self.token, self.csrf = self.locks.token, self.locks.csrf
        self.studio = Path(studio) if studio else None
        self.lang = lang
        self.adapters = adapters_module.installed() if adapters is None else dict(adapters)
        self.contract = contract()
        self.actions = {action['id']: action for action in self.contract['actions']}
        self.verbs = {verb['id']: verb for verb in self.contract['verbs']}
        self.store = Store(guided.workspace(self.project) / 'runs', Scrubber(self.project, [self.token, self.csrf]))
        self.manager = Manager(self.project, self.store, self.adapters, self.contract, _server_tools, lang)

    def close(self):
        self.manager.close()

    # the one entry
    def handle(self, method, path, headers, body=None):
        method = str(method).upper()
        refused = self.locks.check(method, path, headers or {})
        if refused:
            self.store.refused(method, urlsplit(path).path, refused[1])
            return refused[0], {'error': refused[1]}
        route = urlsplit(path).path.rstrip('/')
        query = {key: values[-1] for key, values in parse_qs(urlsplit(path).query).items()}
        body = body if isinstance(body, dict) else {}
        try:
            return 200, self._route(method, route, query, body)
        except Refused as problem:
            return problem.status, {'error': problem.reason, **problem.extra}
        except selecting.SelectionError as problem:
            return 400, {'error': str(problem)}
        except KeyError as problem:
            return 404, {'error': f'not found: {problem}'}
        except LookupError as problem:
            return 409, {'error': str(problem)}
        except ValueError as problem:
            return 400, {'error': str(problem)}

    def _route(self, method, route, query, body):
        parts = route.strip('/').split('/')
        if parts[:1] != ['api']: raise KeyError(route)
        rest = parts[1:]
        if method == 'GET':
            if rest == ['session']: return self.session()
            if rest == ['actions']: return self.contract
            if rest == ['assistants']: return {'assistants': self.assistants()}
            if rest == ['runs']: return self.runs(query)
            if rest == ['questions']: return {'questions': self.questions()}
            if len(rest) == 2 and rest[0] == 'runs': return {'run': self.public(self.store.load(rest[1]))}
            if len(rest) == 3 and rest[0] == 'runs' and rest[2] == 'events':
                self.store.load(rest[1])
                return {'events': self.store.events(rest[1], int(query.get('after') or 0))}
            raise KeyError(route)
        if len(rest) == 3 and rest[0] == 'actions' and rest[2] == 'preview': return self.preview(rest[1], body)
        if rest == ['runs']: return {'run': self.public(self.create(body))}
        if rest == ['runs', 'reorder']: return {'queue': self.manager.reorder(body.get('order'))}
        if len(rest) == 3 and rest[0] == 'questions' and rest[2] == 'answer':
            return {'run': self.public(self.manager.answer(rest[1], body.get('option'), body.get('text')))}
        if len(rest) == 3 and rest[0] == 'runs':
            run, operation = rest[1], rest[2]
            self.store.load(run)
            if operation in ('pause', 'resume', 'stop', 'retry'):
                self.store.append(run, 'action', {'en': f'You pressed {operation}', 'ar': f'ضغطت {operation}'}, {'action': operation, 'by': 'person', 'arguments': {}})
                return {'run': self.public(getattr(self.manager, operation)(run))}
            if operation in ('accept', 'undo'): return self.decide(run, operation, body)
        raise KeyError(route)

    # reading
    def session(self):
        return {'csrf': self.csrf, 'mode': 'live', 'project': self.project.name, 'contract': self.contract['revision'],
                'assistants': self.assistants(), 'lang': self.lang}

    def assistants(self):
        return [adapter.detect() for adapter in self.adapters.values()]

    def public(self, record):
        hidden = ('offset', 'pid', 'paused_pid', 'inputs_secret', 'branches_before')
        out = {key: value for key, value in record.items() if key not in hidden}
        queue = self.store.queue()
        if record['id'] in queue: out['position'] = queue.index(record['id']) + 1
        return out

    def runs(self, query):
        rows = [row for row in self.store.all() if query.get('all') or not row.get('read')]
        if query.get('state'): rows = [row for row in rows if row.get('state') == query['state']]
        if query.get('q'):
            needle = query['q'].lower()
            rows = [row for row in rows if needle in json.dumps([row.get('label'), row.get('cards'), row.get('result'), row.get('action'), row.get('verb')],
                                                                ensure_ascii=False).lower()]
        return {'runs': [self.public(row) for row in rows], 'queue': self.store.queue()}

    def questions(self):
        return [row['question'] for row in self.store.all() if row.get('state') == 'waiting_for_person' and row.get('question')]

    # what a run would be
    def _kind(self, name, body):
        """(verb or None, action id) of a preview or a run: a verb when the body selects cards."""
        verb = body.get('verb') or (name if name in VERBS and name not in self.actions else None)
        if verb is None and name in VERBS and body.get('selection'): verb = name
        if verb:
            if verb not in self.verbs: raise ValueError(f'no verb named {verb}')
            return verb, verb
        if name not in self.actions: raise KeyError(name)
        return None, name

    def _inputs(self, action, inputs):
        from ...artifact_contracts import validate
        inputs = {key: value for key, value in (inputs or {}).items() if key != 'project'}
        problems = validate(inputs, self.actions[action]['inputs'])
        if problems: raise ValueError('; '.join(problems[:5]))
        return inputs

    def _assistant(self, wanted, needed):
        if not needed: return None
        if wanted == 'handoff': return 'handoff'
        if wanted:
            if wanted not in self.adapters: raise ValueError(f'no assistant named {wanted}')
            return wanted
        return next((key for key, adapter in self.adapters.items() if adapter.available()), 'handoff')

    def _needs_confirm(self, verb, action, inputs):
        if verb: return self.verbs[verb]['changes_code']
        spec = self.actions[action]
        return spec['irreversible'] or spec['changes_code'] or (spec['needs_consent'] and bool(inputs.get('person_agreed')))

    def _past(self, verb):
        rows = []
        for row in self.store.all():
            if row.get('verb') == verb and row.get('state') == 'done' and row.get('started') and row.get('ended') and row.get('cards'):
                minutes = (datetime.fromisoformat(row['ended']) - datetime.fromisoformat(row['started'])).total_seconds() / 60
                rows.append((minutes, len(row['cards'])))
        return rows

    def preview(self, name, body):
        verb, action = self._kind(name, body)
        inputs = {} if verb else self._inputs(action, body.get('inputs'))
        needed = self.verbs[verb]['needs_assistant'] if verb else self.actions[action]['needs_assistant']
        assistant = self._assistant(body.get('assistant'), needed)
        chosen = self.adapters.get(assistant).detect() if assistant and assistant != 'handoff' else None
        out = {'action': action, 'verb': verb, 'selection': body.get('selection') if verb else None,
               'cards': [], 'left_out': [], 'files': [], 'batches': [],
               'assistant': chosen, 'assistants': self.assistants() if needed else [],
               'irreversible': bool(not verb and self.actions[action]['irreversible']),
               'needs_consent': bool(not verb and self.actions[action]['needs_consent']) or verb == 'fix'}
        if verb:
            cards, left = selecting.resolve(body.get('selection'), self._studio())
            out.update(selecting.preview_of(verb, cards, left, self._past(verb)))
        else:
            spec = self.actions[action]
            low, high = (5, 30) if action == 'audit' else (10, 40) if action in ('run_setup', 'run_try', 'safety_net', 'fix_finish', 'build_finish') else (0, 1)
            out.update(estimate={'minutes_low': low, 'minutes_high': high, 'basis': {'en': 'a rough rule for this step', 'ar': 'تقدير تقريبي لهذه الخطوة'}},
                       risk={'level': 'high' if spec['irreversible'] else 'medium' if spec['changes_code'] else 'low',
                             'why': spec['description'] if spec['description']['en'] else spec['label']},
                       on_failure=selecting.ON_FAILURE['fix' if spec['changes_code'] else 'read'])
        from .prompts import build
        cards_detail = out['cards']
        prompt = build(verb, cards_detail, self.project, self.lang, action=action, inputs=inputs, labels={k: v['label'] for k, v in self.actions.items()})
        # The planner asks the assistant itself: there is no request a chat assistant could take over.
        handed = bool(needed) and action not in PLANNERS
        out['handoff'] = {'available': handed, 'request': handoff.request_text(prompt, '<run>') if handed else None}
        out['confirm'] = self.locks.confirm(action, out['selection'], self.project) if self._needs_confirm(verb, action, inputs) else None
        return out

    def _studio(self):
        return self.studio if self.studio else selecting.studio_folder(self.project)

    # running
    def create(self, body):
        if not (body.get('action') or body.get('verb')): raise ValueError('say which action to run (action) or which verb (verb)')
        verb, action = self._kind(str(body.get('action') or body.get('verb')), body)
        inputs = {} if verb else self._inputs(action, body.get('inputs'))
        selection = body.get('selection') if verb else None
        if self._needs_confirm(verb, action, inputs) and not self.locks.spend(body.get('confirm'), action, selection, self.project):
            raise Refused(403, 'this needs your explicit confirmation: open its preview and confirm', needs='confirm')
        needed = self.verbs[verb]['needs_assistant'] if verb else self.actions[action]['needs_assistant']
        cards, left = selecting.resolve(selection, self._studio()) if verb else ([], [])
        label = self.verbs[verb]['label'] if verb else self.actions[action]['label']
        if verb: label = {lang: f"{label[lang]}: {', '.join(c['id'] for c in cards[:3])}{' …' if len(cards) > 3 else ''}" for lang in ('en', 'ar')}
        assistant = self._assistant(body.get('assistant'), needed)
        run = _run_id()
        reading = not verb and action in reading_tools()
        record = {'id': run, 'action': action, 'verb': verb, 'label': label, 'selection': selection, 'inputs': inputs,
                  'cards': [c['id'] for c in cards], 'cards_detail': [{'id': c['id'], 'title': c.get('title'), 'paths': selecting._paths(c)} for c in cards],
                  'left_out': left, 'assistant': assistant if assistant != 'handoff' else None,
                  'mode': 'planner' if action in PLANNERS else 'direct' if not needed else ('handoff' if assistant == 'handoff' else 'assistant'),
                  'state': 'running' if reading else 'queued', 'attempt': 1, 'created': now(), 'queued_at': now(), 'read': reading,
                  **({'started': now()} if reading else {})}
        self.store.save(record, new=True)
        shown = {k: v for k, v in inputs.items() if k not in ('edits', 'spec', 'proposal', 'text')}
        self.store.append(run, 'action', {'en': f"You asked: {label['en']}", 'ar': f"طلبت: {label['ar']}"},
                          {'action': action, 'by': 'person', 'arguments': {**shown, **({'cards': record['cards']} if verb else {})}})
        if reading:
            if 'seconds' in inputs: self.store.update(run, inputs={**inputs, 'seconds': 0})
            self.manager._direct(run, follow=False)                 # never queued: it answers now, in this call
            return self.store.load(run)
        self.store.set_queue(self.store.queue())
        return self.store.load(run)

    def decide(self, run, operation, body):
        """Accept or undo the branch a run handed over: only with the confirm token of that preview."""
        if not self.locks.spend(body.get('confirm'), operation, None, self.project):
            raise Refused(403, f'{operation} needs your explicit confirmation: open its preview and confirm', needs='confirm')
        record = self.store.load(run)
        branch = (record.get('result') or {}).get('branch')
        if not branch: raise LookupError('this run handed no branch over')
        self.store.append(run, 'action', {'en': f'You chose to {operation} {branch}', 'ar': f"اخترت {'اعتماد' if operation == 'accept' else 'رمي'} {branch}"},
                          {'action': operation, 'by': 'person', 'arguments': {'branch': branch}})
        result = self.manager.call(operation, {'person_agreed': True} if operation == 'accept' else {})
        ok = isinstance(result, dict) and not result.get('error') and result.get('status') not in ('needs_agreement', 'unsaved_changes', 'conflict', 'nothing_waiting')
        words = {'en': f"{'Taken in' if operation == 'accept' else 'Thrown away'}: {branch}" if ok else f"{operation} did not happen: {result.get('status') or result.get('error')}",
                 'ar': f"{'اعتُمد' if operation == 'accept' else 'رُمي'}: {branch}" if ok else f"ما تم: {result.get('status') or result.get('error')}"}
        self.store.append(run, 'result' if ok else 'error', words,
                          {'branch': branch, 'outcome': operation if ok else None, 'answer': result} if ok else
                          {'reason': str(result.get('status') or result.get('error')), 'recoverable': True,
                           'what_now': {'en': str(result.get('what_now') or ''), 'ar': str(result.get('what_now') or '')}})
        if ok: self.store.update(run, outcome={'accept': 'accepted', 'undo': 'undone'}[operation], decided=now())
        return {'run': self.public(self.store.load(run)), 'result': result}

    # following
    def sse(self, run, last_event_id=None, follow=False, heartbeat=HEARTBEAT):
        """The run's events after `last_event_id` as SSE frames; with `follow`, then live until the run ends."""
        self.store.load(run)
        after = int(last_event_id or 0)
        beat = time.monotonic()
        while True:
            for event in self.store.events(run, after):
                after = event['seq']
                yield f"id: {event['seq']}\nevent: {event['kind']}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
            if not follow: return
            if self.store.load(run).get('state') in TERMINAL and not self.store.events(run, after): return
            if time.monotonic() - beat >= heartbeat:
                beat = time.monotonic()
                yield ': ping\n\n'
            self.store.wait_change(1.0)

    def wait(self, run, states, timeout=60):
        """The run once its state is one of `states` (or as it is when the time runs out)."""
        end = time.monotonic() + timeout
        while True:
            record = self.store.load(run)
            if record.get('state') in states or time.monotonic() > end: return record
            time.sleep(0.1)


def mount(router, actions, prefix=''):
    """The action API on an existing Starlette app or router (NS37.T2's read server): see eaos/studio/actions/serve.py."""
    from .serve import starlette_routes
    for route in starlette_routes(actions, prefix):
        router.routes.append(route)
    return router
