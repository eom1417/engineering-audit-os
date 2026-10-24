"""The project switcher's back end: the projects EAOS knows on this computer, and the address of each one's own Studio.

    GET  /api/projects                       {"projects": [{workspace, name, path, current, score, checked, studio}]}
    POST /api/projects/open  {"workspace"}   {"studio": the address of that project's Studio, started when it is not}

Each project keeps a Studio server of its own (eaos/core/launch.py), itself a boundary between projects: switching opens
the other project's server, never this one on the other's data. Read from each project's state.json, its report's score
and its Studio record; nothing is asked of the other servers.
"""
import json
from pathlib import Path

from ...journeys import guided
from ...core.places import home
from ...core import launch


def _state(record):
    try: return json.loads(record.read_text(encoding='utf-8'))
    except (OSError, ValueError): return None


def _score(state):
    try: return json.loads((guided.report_of(state) / 'studio/health.json').read_text(encoding='utf-8'))['score']['value']
    except (OSError, ValueError, KeyError, TypeError): return None


def _studio_runs(state):
    try: return launch._alive(json.loads(launch.record_path(state).read_text(encoding='utf-8'))['pid'])
    except (OSError, ValueError, KeyError): return False


def known():
    """Every project with a state on this computer, the most recently checked first."""
    states = [state for state in map(_state, sorted((home() / 'projects').glob('*/state.json'))) if state and state.get('project')]
    return sorted(states, key=lambda state: state.get('scanned') or '', reverse=True)


def listing(current):
    current = Path(current).resolve() if current else None
    return {'projects': [{'workspace': Path(state['workspace']).name, 'name': Path(state['project']).name, 'path': state['project'],
                          'current': Path(state['project']).resolve() == current, 'score': _score(state),
                          'checked': state.get('scanned'), 'studio': _studio_runs(state)} for state in known()]}


def open_studio(workspace):
    """(status, answer): the address of that project's own Studio, started in the background when it is not running."""
    state = next((state for state in known() if Path(state['workspace']).name == workspace), None)
    if state is None: return 404, {'error': 'not_found', 'message': f'no project {workspace!r} on this computer'}
    record, _ = launch.start(state)
    if not record: return 503, {'error': 'not_started', 'message': 'its Studio did not start in time; try again'}
    return 200, {'studio': launch.url_of(record), 'name': Path(state['project']).name}


def routes(ctx):
    return [('GET', '/api/projects', lambda request: listing(ctx.project)),
            ('POST', '/api/projects/open', lambda request: open_studio(str((request['body'] or {}).get('workspace') or '')))]
