"""studio/screens.json: what users see, every screen with its shots, inputs and usability issues (NS46.T5).

The screens are the pages of the user's journeys (studio/journeys.json, kind page: one per full route, with its
component file and the evidence of its declaration). For each:

    shots   media.json images of kind screen with this screen's route (the screen gate's captures of the app), each
            with its viewport width, phase and batch. Only an image tied to a route counts: a logo or an icon in the
            project is not a screen
    inputs  not measured yet: no extractor reads a screen's fields and their labels (data_paths: no_ui_extractor)
    issues  the screen gate's findings pinned to a shot; none can exist before the screens are captured

What is not measured is written in `missing` (counted in coverage.json, shown on the page), never as an empty list
that would read as "no issues". A project with no pages has no screens: measured, and empty.

`pages` is the gallery of what the check pictured (gallery): each distinct page of the running app once, with the
pictures of it and, on each picture, the visual reviewer's findings with their region:

    {path, template, same_as: [the other addresses it stands for], state: findings | clean | not_reviewed,
     findings: count, pictures: [{path (report-relative png), viewport, width, height, checks: [what the page checks
     found], findings: [{id, title, kind, severity, why, region: {x, y, width, height} as fractions 0-1 of the
     picture}]}]}

A page the reviewer looked at and found nothing on is kept, marked clean; one it did not decide (no assistant, or its
answer was dropped) is not_reviewed.
"""
import json
from pathlib import Path
from urllib.parse import urlsplit

CAPTURE_STEP = 'NS41.T1'   # capturing the app's screens (needs the app running, with the person's agreement)
INPUTS_STEP = 'NS40.T2'    # the UI extractor: forms, fields and their labels
SRC = {
    'screens': 'studio/journeys.json#screens[kind=page]',
    'shots': 'media.json#images[kind=screen, route set]',
    'issues': 'the screen gate\'s findings on the shots',
}


def _count(value, key):
    return {'value': value, 'src': SRC[key], 'unit': 'count'}


def _load(path):
    try: return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError): return None


def _address(url):
    """A page's address without the app's host: /#/tasks/TASK-001."""
    parts = urlsplit(str(url or ''))
    return (parts.path or '/') + (f'?{parts.query}' if parts.query else '') + (f'#{parts.fragment}' if parts.fragment else '')


def gallery(report):
    """The pictured pages of this check (live/screens.json) with the visual reviewer's findings on each picture
    (nodes/visual_reviewer/findings.json); [] when nothing was pictured."""
    report = Path(report)
    body = _load(report / 'live/screens.json') or {}
    review = _load(report / 'nodes/visual_reviewer/findings.json') or {}
    reviewed = review.get('method') == 'model'
    clean = {_address(page) for page in review.get('clean') or []} if reviewed else set()
    on = {}
    for finding in review.get('findings') or [] if reviewed else []:
        for shown in finding.get('pictures') or [{'file': finding.get('file'), 'region': finding.get('region')}]:
            on.setdefault(shown.get('file'), []).append({'id': finding.get('id') or finding.get('image'), 'region': shown.get('region'),
                                                         **{k: finding.get(k) for k in ('title', 'kind', 'severity', 'why')}})
    known = {row.get('path'): row for row in body.get('pages') or [] if isinstance(row, dict)}
    pages = {}
    for row in body.get('rows') or []:
        if not isinstance(row, dict) or not row.get('screenshot') or not (report / row['screenshot']).is_file(): continue
        address = _address(row.get('url'))
        page = pages.get(address)
        if page is None:
            given = known.get(address) or {}
            page = pages[address] = {'path': address, 'template': given.get('template') or address,
                                     'same_as': list(given.get('same_as') or []), 'state': 'not_reviewed', 'findings': 0, 'pictures': []}
        found = on.get(row['screenshot'], [])
        page['pictures'].append({'path': row['screenshot'], 'viewport': row.get('viewport'), 'width': row.get('width'),
                                 'height': row.get('height'), 'checks': list(row.get('failures') or []), 'findings': found})
        page['findings'] += len(found)
        page['state'] = 'findings' if page['findings'] else 'clean' if address in clean else 'not_reviewed'
    return list(pages.values())


def screens(journeys, media=None, read=True, report=None):
    """The body of screens.json, or None when the journeys were not exported or the check did not look for entry
    points (`read` false) and the check pictured no page: nothing to read the screens from, which is not the same as
    "no screens". `report` given, `pages` is the gallery of the pictured pages (gallery)."""
    pages = gallery(report) if report else []
    if not isinstance(journeys, dict) or not read:
        if not pages: return None
        journeys = {}
    images = [i for i in media or [] if isinstance(i, dict) and i.get('kind') == 'screen' and i.get('route')]
    out = []
    for s in journeys.get('screens') or []:
        if s.get('kind') != 'page': continue
        shots = [{'path': i['path'], 'width': i['viewport'] if isinstance(i.get('viewport'), int) and i['viewport'] > 0 else 390,
                  'phase': i.get('phase') if i.get('phase') in ('before', 'after', 'baseline') else None, 'batch': i.get('batch')}
                 for i in images if i['route'] == s['route']]
        out.append({'id': s['id'], 'route': s['route'], 'title': s.get('title') or s['route'], 'component': s.get('component'),
                    'file': s.get('file'), 'router': s.get('router'), 'line': s.get('line'), 'fact': s.get('fact'),
                    'flags': list(s.get('flags') or []), 'shots': shots, 'inputs': [], 'issues': []})
    shot = sum(1 for s in out if s['shots'])
    missing = []
    if out and shot < len(out):
        missing.append({'id': 'shots', 'state': 'not_measured' if not shot else 'partial', 'step': CAPTURE_STEP,
                        'count': _count(shot, 'shots'),
                        'detail': {'ar': f'{len(out) - shot} من {len(out)} شاشة لم تُصوَّر بعد: التصوير يحتاج تشغيل التطبيق بموافقتك',
                                   'en': f'{len(out) - shot} of {len(out)} screens not captured yet: capturing needs the app running, with your agreement'}})
        missing.append({'id': 'issues', 'state': 'not_measured', 'step': CAPTURE_STEP, 'count': _count(None, 'issues'),
                        'detail': {'ar': 'مشاكل الاستخدام تُفحص على صور الشاشات، فلم تُفحص بعد',
                                   'en': 'Usability issues are checked on the screen shots, so they are not checked yet'}})
    if out:
        missing.append({'id': 'inputs', 'state': 'not_measured', 'step': INPUTS_STEP, 'count': {'value': None, 'src': 'no UI extractor yet', 'unit': 'count'},
                        'detail': {'ar': 'حقول الإدخال وتسمياتها لا يقرؤها EAOS بعد', 'en': 'EAOS does not read input fields and their labels yet'}})
    return {'screens': out, 'missing': missing, 'pages': pages,
            'counts': {'screens': _count(len(out), 'screens'), 'shot': _count(shot, 'shots'),
                       'issues': _count(sum(len(s['issues']) for s in out) if shot else None, 'issues')}}
