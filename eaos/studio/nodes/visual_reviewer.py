"""The visual reviewer: the person's assistant looks at the app's screens and judges their design and behaviour.

It reads the pictures the check took of the running app (live/screens.json: each page in its light and dark states at
phone and desktop width, with what axe and the page checks found there) and, for each picture, decides "cards" (it
shows problems a person would notice: crowding, a weak visual hierarchy, inconsistency, unclear text or actions, an
accessibility or behaviour problem), "clean" (nothing to change) or, without an assistant, "rules only" (the axe and
Lighthouse numbers stand alone). Every finding names its picture and the region of it, as fractions of its width and
height; a decision with a finding outside its picture, or without a region, is dropped. The assistant may open the
listed pictures and nothing else. The findings are written to nodes/visual_reviewer/findings.json, where the cards
stage turns each into a design card.
"""
import json
import sys
from pathlib import Path

from . import core

VERSION = '1'
BATCH = 6
KINDS = ('crowding', 'hierarchy', 'consistency', 'clarity', 'accessibility', 'behaviour')
SEVERITIES = ('high', 'medium', 'low')
_REGION = {'type': 'object', 'additionalProperties': False, 'required': ['x', 'y', 'width', 'height'],
           'properties': {name: {'type': 'number'} for name in ('x', 'y', 'width', 'height')}}
_FINDING = {'type': 'object', 'additionalProperties': False, 'required': ['title', 'kind', 'severity', 'region', 'why'],
            'properties': {'title': {'type': 'string'}, 'kind': {'type': 'string', 'enum': list(KINDS)},
                           'severity': {'type': 'string', 'enum': list(SEVERITIES)}, 'region': _REGION, 'why': {'type': 'string'}}}
DETAIL = {'type': 'object', 'additionalProperties': False, 'required': ['findings'],
          'properties': {'findings': {'type': 'array', 'items': _FINDING}}}
TASK = '''GOAL
You are the visual reviewer of EAOS, an engineering audit. Look at each picture of this app's screens and judge what a
person using it would notice: crowding, a weak visual hierarchy, inconsistency between screens, unclear text or
actions, accessibility or behaviour problems.

WHAT YOU ARE GIVEN
`images`: each picture with its id, its `path`, the page, the viewport (phone or desktop) and the theme, and what the
deterministic checks found on that page (`axe`: accessibility violations; `failures`: overflow, small targets, clipped
text and the like). An exception to rule 6: you have the Read tool, for the files listed in `images` and nothing else.
Open each picture with it before you judge it.

WHAT TO RETURN
One decision per picture, subject = its id: "cards" with `detail.findings` (each a short title, its kind, its
severity, the region of the picture it is about as fractions 0 to 1 of the picture's width and height, x and y its
top-left corner, and why a person would notice it), or "clean" when nothing should change (`detail.findings` empty).
`evidence`: the picture's id.

A GOOD ANSWER
Every picture decided once. A finding is specific to what is drawn in its region and says what to change there. A
finding the checks already state (an axe violation) is kept only if the picture shows how it hurts the person.

DO NOT
Judge a picture you did not open; describe a region the picture does not have; write a generic design rule without
pointing at where the picture breaks it.'''


def inputs(report, project=None, lang='en', **_):
    report = Path(report)
    body = core.load(report / 'live/screens.json', {}) or {}
    images = []
    for row in body.get('rows') or []:
        if not isinstance(row, dict) or not row.get('screenshot') or not (report / row['screenshot']).is_file(): continue
        images.append({'id': f'IMG-{len(images) + 1:03d}', 'path': str((report / row['screenshot']).resolve()), 'file': row['screenshot'],
                       'page': row.get('url'), 'viewport': row.get('viewport'), 'theme': row.get('variant'),
                       'axe': [core.short(f"{v.get('id')}: {v.get('help')}", 120) for v in (row.get('axe') or {}).get('violations') or []
                               if isinstance(v, dict)][:8],
                       'failures': [core.short(f, 120) for f in row.get('failures') or []][:8]})
    if not images: return None
    return {'lang': lang, 'project': {'name': (project and Path(project).name) or report.name}, 'images': images}


def batches(data):
    return [{**data, 'images': data['images'][i:i + BATCH]} for i in range(0, len(data['images']), BATCH)]


def images(data):
    return [image['path'] for image in data['images']]


def subjects(data):
    return [image['id'] for image in data['images']]


def known(report, data):
    return {image['id'] for image in data['images']}


def rules(data):
    return {image['id']: ([image['id']], 'No assistant looked at this picture: only what axe and the page checks found stands.',
                          0.5, {'findings': []}) for image in data['images']}


def check(data, decision):
    """Every finding names a region inside its picture."""
    for finding in (decision.get('detail') or {}).get('findings') or []:
        region = finding.get('region') or {}
        x, y, width, height = (region.get(k) for k in ('x', 'y', 'width', 'height'))
        if not all(isinstance(v, (int, float)) for v in (x, y, width, height)): return 'a finding names no region of its picture'
        if width <= 0 or height <= 0 or x < 0 or y < 0 or x + width > 1.0001 or y + height > 1.0001:
            return 'a finding names a region outside its picture'
    if decision['decision'] == 'cards' and not (decision.get('detail') or {}).get('findings'): return 'cards without a finding'
    return None


def prompt(data):
    return core.prompt(TASK, data)


def finish(report, record, data):
    pictures = {image['id']: image for image in data['images']}
    findings = [{'image': d['subject'], 'file': pictures[d['subject']]['file'], 'page': pictures[d['subject']]['page'],
                 'viewport': pictures[d['subject']]['viewport'], 'theme': pictures[d['subject']]['theme'], **finding}
                for d in record['decisions'] if d['source'] == 'model' for finding in (d.get('detail') or {}).get('findings') or []]
    folder = core.folder_of(report, record['node'])
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'findings.json').write_text(json.dumps({'schema_version': 1, 'at': record['at'], 'method': record['method'],
                                                      'assistant': record['assistant'], 'model': record['model'],
                                                      'images': len(pictures), 'findings': findings}, ensure_ascii=False, indent=1) + '\n',
                                          encoding='utf-8')


def run(node, report, **options):
    return core.run_node(node, sys.modules[__name__], report, **options)
