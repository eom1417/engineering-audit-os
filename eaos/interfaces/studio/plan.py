"""Build a new project from its plan, or extend this one with a feature, started from the Studio (docs/BUILD-FROM-PLAN.md):
the plan the person gives (its files and the pictures of its screens, or pasted words) is kept in a folder of its own,
and the person's assistant runs blueprint_start for a new project folder beside the one this Studio serves, through to
the drawn blueprint; or, with mode extend, extend_start for this project, through to the feature's cards in its plan."""
import base64
import re
from datetime import datetime, timezone
from pathlib import Path

from ...analysis.plan_source import IMAGE_SUFFIXES, SOURCE_SUFFIXES

MAX_BYTES = 32 * 1024 * 1024        # the whole request: a PDF and a few screen pictures


def start(actions, body):
    """{run}: the plan saved in a folder beside the project's, then the blueprint run for the new project's folder, or
    the extension run for this one."""
    extend = body.get('mode') == 'extend'
    project, name = (actions.project, actions.project.name) if extend else _new(actions, body)
    files, text = body.get('files') or [], str(body.get('text') or '').strip()
    if not files and not text: raise ValueError('give the plan: its files, or paste its text')
    folder = project.parent / f'.{name}-plan-{datetime.now(timezone.utc):%Y%m%d%H%M%S}'
    folder.mkdir(parents=True)
    for row in files:
        kept = Path(str(row.get('name') or '')).name
        if not kept.lower().endswith(SOURCE_SUFFIXES + IMAGE_SUFFIXES): raise ValueError(f'{kept}: not a plan document or a picture')
        (folder / kept).write_bytes(base64.b64decode(str(row.get('data') or ''), validate=True))
    if not extend: _speak(project, actions.lang)
    inputs = {'source': str(folder) if files else None, 'text': text or None}
    action = 'extend_start' if extend else 'blueprint_start'
    seen = actions.preview(action, {'inputs': inputs})      # the person's press is the confirmation
    return {'run': actions.public(actions.create({'action': action, 'inputs': inputs, 'confirm': seen.get('confirm')},
                                                 project=str(project)))}


def _speak(project, lang):
    """The new project starts in the Studio's language: its blueprint, questions and Status speak it."""
    from ...journeys import agent_tools, guided
    state = agent_tools.project_state(str(project), new=True)
    state['lang'] = lang
    guided.save(state)


def _new(actions, body):
    """(the new project's folder, its name): beside this one, empty."""
    name = re.sub(r'[^\w-]+', '-', str(body.get('name') or '').strip()).strip('-').lower()
    if not name: raise ValueError('name the new project')
    project = actions.project.parent / name
    if project.exists() and any(project.iterdir()): raise ValueError(f'the folder {project} is not empty: choose another name')
    return project, name
