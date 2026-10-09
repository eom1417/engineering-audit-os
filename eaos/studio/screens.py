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
"""

CAPTURE_STEP = 'NS41.T1'   # capturing the app's screens (needs the app running, with the person's agreement)
INPUTS_STEP = 'NS40.T2'    # the UI extractor: forms, fields and their labels
SRC = {
    'screens': 'studio/journeys.json#screens[kind=page]',
    'shots': 'media.json#images[kind=screen, route set]',
    'issues': 'the screen gate\'s findings on the shots',
}


def _count(value, key):
    return {'value': value, 'src': SRC[key], 'unit': 'count'}


def screens(journeys, media=None, read=True):
    """The body of screens.json, or None when the journeys were not exported or the check did not look for entry
    points (`read` false): nothing to read the screens from, which is not the same as "no screens"."""
    if not isinstance(journeys, dict) or not read: return None
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
    return {'screens': out, 'missing': missing,
            'counts': {'screens': _count(len(out), 'screens'), 'shot': _count(shot, 'shots'),
                       'issues': _count(sum(len(s['issues']) for s in out) if shot else None, 'issues')}}
