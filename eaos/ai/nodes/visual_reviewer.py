"""The visual reviewer: the person's assistant looks at the app's screens and judges their design and behaviour.

It reads the pictures the check took of the running app (live/screens.json: each distinct page once, in the app's own
theme, at phone and desktop width, with what axe and the page checks found there) page by page: each page is one
subject, with its pictures. For each page it decides "cards" (it shows problems a person would notice: crowding, a
weak visual hierarchy, inconsistency, unclear text or actions, an accessibility or behaviour problem), "clean" (nothing
to change) or, without an assistant, "rules only" (the axe and Lighthouse numbers stand alone). A problem is one
finding per page, whatever the number of its pictures it shows on: the finding lists each picture it shows on with
the region of it, as fractions of its width and height (one finding per picture made 1030 findings of EAOS's own
Studio). A decision with a finding on a picture of another page, or outside its picture, or without a region, is
dropped. The assistant may open the listed pictures and nothing else. The findings are written to
nodes/visual_reviewer/findings.json, where the cards stage turns them into design cards.
"""
import json
from pathlib import Path

from . import framework as core

VERSION = '3'
BATCH = 4                       # pages per question: their phone and desktop pictures, 8 at most
KINDS = ('crowding', 'hierarchy', 'consistency', 'clarity', 'accessibility', 'behaviour')
SEVERITIES = ('high', 'medium', 'low')
_REGION = {'type': 'object', 'additionalProperties': False, 'required': ['x', 'y', 'width', 'height'],
           'properties': {name: {'type': 'number'} for name in ('x', 'y', 'width', 'height')}}
_SHOWS = {'type': 'object', 'additionalProperties': False, 'required': ['picture', 'region'],
          'properties': {'picture': {'type': 'string'}, 'region': _REGION}}
_FINDING = {'type': 'object', 'additionalProperties': False, 'required': ['title', 'kind', 'part', 'severity', 'shows', 'why'],
            'properties': {'title': {'type': 'string'}, 'kind': {'type': 'string', 'enum': list(KINDS)}, 'part': {'type': 'string'},
                           'severity': {'type': 'string', 'enum': list(SEVERITIES)},
                           'shows': {'type': 'array', 'items': _SHOWS}, 'why': {'type': 'string'}}}
DETAIL = {'type': 'object', 'additionalProperties': False, 'required': ['findings'],
          'properties': {'findings': {'type': 'array', 'items': _FINDING}}}
TASK = '''GOAL
You are the visual reviewer of EAOS, an engineering audit. Look at each page of this app, in its pictures, and judge
what a person using it would notice: crowding, a weak visual hierarchy, inconsistency between screens, unclear text or
actions, accessibility or behaviour problems.

WHAT YOU ARE GIVEN
`pages`: each distinct page once, with its id, its address, the other addresses it stands for (`same_as`: the same
template with other data), its `pictures` (each with its id, its `path` and its viewport: phone or desktop) and what the
deterministic checks found there (`axe`: accessibility violations; `failures`: overflow, small targets, clipped text and
the like). An exception to rule 6: you have the Read tool, for the files listed in `pages` and nothing else. Open each
picture with it before you judge its page.

WHAT TO RETURN
One decision per page, subject = its id: "cards" with `detail.findings`, or "clean" when nothing should change
(`detail.findings` empty). A finding is one problem of the page, written once even when it shows on several of its
pictures: a short title, its kind, its severity, why a person would notice it, and in `shows` each picture of this page
it shows on (its id) with the region of that picture it is about, as fractions 0 to 1 of the picture's width and height,
x and y its top-left corner. `part`: where the cause lives, so one cause is one card however many pages show it:
`page` when only this page has it; else the shared part every page draws, one lowercase word from: top-bar,
navigation, sidebar, footer, language (text in the wrong language or direction), typography, colours, buttons, cards,
forms, tables, charts, icons, layout; another such word only when none fits. `evidence`: the ids of the pictures you
opened.

A GOOD ANSWER
Every page decided once. A finding is specific to what is drawn in its regions and says what to change there. A
finding the checks already state (an axe violation) is kept only if the pictures show how it hurts the person.

When `design` is given, it is the look the person chose (a DESIGN.md): judge every page against it too. A colour,
font, spacing, radius, component or layout that departs from it is a finding, and its why names the DESIGN.md rule.

A PAGE NOT SEEN
A picture of the app's "not found" page, of a refusal ("no access", "not allowed") or of its sign-in, at an address
that is not the sign-in's, is a page this session could not see: most often a page of another view, profile, program
or workspace than the session's. It is never a finding: decide that page "clean", and never say the page is missing,
old, broken or to redirect.

DO NOT
Judge a page whose pictures you did not open; repeat one problem as several findings of the page; point at a picture
of another page; describe a region the picture does not have; write a generic design rule without pointing at where
the picture breaks it.'''


def inputs(report, project=None, lang='en', **_):
    """{lang, project, pages}: the pictured rows of live/screens.json grouped by page (its URL), each picture with an id;
    never a page that did not open as itself (`unseen`: a sign-in, a refusal, the app's page for an address it does not
    have), which is a page not seen, never one to judge."""
    report = Path(report)
    body = core.load(report / 'live/screens.json', {}) or {}
    same = {row.get('path'): row for row in body.get('pages') or [] if isinstance(row, dict)}
    pages, count = {}, 0
    for row in _pictured(report, body):
        count += 1
        if row.get('url') not in pages: pages[row.get('url')] = _new_page(row, same, len(pages) + 1)
        page = pages[row.get('url')]
        page['pictures'].append(_picture(report, row, count))
        _add_found(page, row)
    if not pages: return None
    from ...analysis.target_state.look import target
    # `design`: the person's chosen look, or None; a redesign's departures from it are findings (eaos/analysis/target_state/look.py).
    return {'lang': lang, 'project': {'name': (project and Path(project).name) or report.name}, 'pages': list(pages.values()),
            'design': target(report)}


def _pictured(report, body):
    """The rows of `body` (live/screens.json) with their picture, of the pages that opened as themselves."""
    return [row for row in body.get('rows') or [] if isinstance(row, dict) and not row.get('unseen')
            and row.get('screenshot') and (report / row['screenshot']).is_file()]


def _new_page(row, same, number):
    """A page met for the first time, with the template and the same-looking pages the crawl named for its URL."""
    known = next((p for path, p in same.items() if path and str(row.get('url') or '').endswith(path)), {})
    return {'id': f'PAGE-{number:03d}', 'page': row.get('url'), 'template': known.get('template'),
            'same_as': list(known.get('same_as') or [])[:20], 'pictures': [], 'axe': [], 'failures': []}


def _picture(report, row, count):
    return {'id': f'IMG-{count:03d}', 'path': str((report / row['screenshot']).resolve()), 'file': row['screenshot'],
            'viewport': row.get('viewport'), 'theme': row.get('variant')}


def _add_found(page, row):
    """A row's axe violations and page-check failures joined to its page's, each once, eight at most."""
    axe = [core.short(f"{v.get('id')}: {v.get('help')}", 120) for v in (row.get('axe') or {}).get('violations') or [] if isinstance(v, dict)]
    failures = [core.short(f, 120) for f in row.get('failures') or []]
    for key, found in (('axe', axe), ('failures', failures)):
        page[key] = list(dict.fromkeys(page[key] + found))[:8]


def batches(data):
    return [{**data, 'pages': data['pages'][i:i + BATCH]} for i in range(0, len(data['pages']), BATCH)]


def _pictures(data):
    return {picture['id']: (page, picture) for page in data['pages'] for picture in page['pictures']}


def images(data):
    return [picture['path'] for page in data['pages'] for picture in page['pictures']]


def subjects(data):
    return [page['id'] for page in data['pages']]


def known(report, data):
    return {page['id'] for page in data['pages']} | set(_pictures(data))


def rules(data):
    return {page['id']: ([page['id']], 'No assistant looked at this page: only what axe and the page checks found stands.',
                         0.5, {'findings': []}) for page in data['pages']}


def check(data, decision):
    """Every finding shows on a picture of its own page, each picture once, with a region inside it."""
    pictures = _pictures(data)
    for finding in (decision.get('detail') or {}).get('findings') or []:
        problem = _finding_problem(finding, pictures, decision['subject'])
        if problem: return problem
    if decision['decision'] == 'cards' and not (decision.get('detail') or {}).get('findings'): return 'cards without a finding'
    return None


def _finding_problem(finding, pictures, subject):
    """What is wrong with one finding's pictures and regions, or None."""
    shows = finding.get('shows') or []
    if not shows: return 'a finding names no picture of its page'
    named = [show.get('picture') for show in shows]
    if any(pictures.get(name, ({},))[0].get('id') != subject for name in named):
        return 'a finding names a picture of another page'
    if len(set(named)) < len(named): return 'a finding names one picture twice'
    return next(filter(None, (_region_problem(show.get('region') or {}) for show in shows)), None)


def _region_problem(region):
    """A region must be given as fractions of its picture, inside it."""
    x, y, width, height = (region.get(k) for k in ('x', 'y', 'width', 'height'))
    if not all(isinstance(v, (int, float)) for v in (x, y, width, height)): return 'a finding names no region of its picture'
    if width <= 0 or height <= 0 or x < 0 or y < 0 or x + width > 1.0001 or y + height > 1.0001:
        return 'a finding names a region outside its picture'
    return None


def prompt(data):
    bundle = {**data, 'pages': [{**page, 'pictures': [{k: v for k, v in p.items() if k != 'file'} for p in page['pictures']]}
                                for page in data['pages']]}
    return core.prompt(TASK, bundle)


def findings_of(record, data):
    """One row per problem per page: the page, its first picture's id, file, viewport and region (the fields a design
    card cites), and `pictures`, every picture it shows on with its region; `viewports` lists them."""
    pictures, rows = _pictures(data), []
    for decision in record['decisions']:
        if decision['source'] != 'model': continue
        page = next(p for p in data['pages'] if p['id'] == decision['subject'])
        for finding in (decision.get('detail') or {}).get('findings') or []:
            rows.append(_finding_row(f'VF-{len(rows) + 1:03d}', page, finding, pictures))
    return rows


def _finding_row(row_id, page, finding, pictures):
    """A finding on its page: its first picture's fields, and every picture it shows on with its region."""
    shows = [{'image': show['picture'], 'file': pictures[show['picture']][1]['file'],
              'viewport': pictures[show['picture']][1]['viewport'], 'region': show['region']} for show in finding['shows']]
    first = shows[0]
    return {'id': row_id, 'page_id': page['id'], 'page': page['page'], 'template': page['template'],
            'image': first['image'], 'file': first['file'], 'viewport': first['viewport'], 'region': first['region'],
            'viewports': list(dict.fromkeys(s['viewport'] for s in shows)),
            'theme': pictures[first['image']][1]['theme'], 'pictures': shows,
            **{k: finding[k] for k in ('title', 'kind', 'severity', 'why')}, 'part': finding.get('part') or 'page'}


def finish(report, record, data):
    findings = findings_of(record, data)
    folder = core.folder_of(report, record['node'])
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'findings.json').write_text(json.dumps({'schema_version': 2, 'at': record['at'], 'method': record['method'],
                                                      'assistant': record['assistant'], 'model': record['model'],
                                                      'pages': len(data['pages']), 'images': len(_pictures(data)),
                                                      'clean': [page['page'] for page in data['pages'] for d in record['decisions']
                                                                if d['subject'] == page['id'] and d['source'] == 'model' and d['decision'] == 'clean'],
                                                      'findings': findings}, ensure_ascii=False, indent=1) + '\n',
                                          encoding='utf-8')
