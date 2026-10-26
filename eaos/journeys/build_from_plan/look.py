"""The finished product's acceptance, on its copy (docs/BUILD-FROM-PLAN.md): the check's own stages picture and review
its screens against DESIGN.md, and, for the last milestone, measure its load on the production build; what they find
holds the last milestone back (`unusable`), or is fixed first by the next milestone."""
import json
import shutil
from pathlib import Path

from .. import guided
from ...core.project import state as project_state


def read(path, default=None):
    """A JSON file of the build, `default` when it is not there (the one reader of eaos/journeys/build_from_plan/steps.py too)."""
    path = Path(path)
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else default


def unusable(look):
    """What stops the finished product's delivery: its screens (axe's serious problems, small targets, clipped text,
    script errors; Lighthouse accessibility or best practices under 90 of 100), a design departure of high severity, and
    a load scenario over its threshold on the production build. Lighthouse speed is not held to: the copy's screens run
    in development mode, slower than any delivered app; the load is measured on the production build instead."""
    look = look or {}
    return _bad_screens(look) + _departures(look) + _overloaded(look.get('load') or []) + _unproven(look)


def _bad_screens(look):
    """The screens' problems, and Lighthouse accessibility or best practices under 90 of 100."""
    scores = look.get('speed') or {}
    return [{'gate': 'screens', 'where': row['page'], 'what': '; '.join(row['problems'])} for row in look.get('screen_problems') or []] + \
        [{'gate': 'screens', 'where': 'the entry page', 'what': f'Lighthouse {name} is {scores[name]}, under 90'}
         for name in ('accessibility', 'best-practices') if isinstance(scores.get(name), (int, float)) and scores[name] < 90]


def _departures(look):
    """The design departures of high or critical severity."""
    return [{'gate': 'design', 'where': str(d.get('part') or 'page'), 'what': f"{d.get('title')}: {d.get('why')}"}
            for d in look.get('departures') or [] if d.get('severity') in ('high', 'critical')]


def _unproven(look):
    """The evidence stages (PROOF) that did not run on the finished product: a measurement that did not happen is no
    pass (a real build: k6 failed and the milestone was delivered as if measured)."""
    return [{'gate': 'proof', 'where': stage, 'what': f'{stage} did not run, so the product is not proven there: {why}'}
            for stage, why in (look.get('not_done') or {}).items() if stage in PROOF and str(why)]


def _overloaded(scenarios):
    """The load scenarios (k6 on the production build) whose p95 or error rate is over their threshold."""
    over = lambda row, key: (row.get('threshold') or {}).get(key) and (row.get(key) or 0) > row['threshold'][key]
    return [{'gate': 'load', 'where': row['id'], 'what': f"under load, p95 {row.get('p95_ms')} ms and errors {row.get('error_rate')}, "
             f"over the threshold {row['threshold']}"} for row in scenarios if over(row, 'p95_ms') or over(row, 'error_rate')]


PROOF = ('setup', 'screens', 'baseline')      # the finished product's evidence: without it the last milestone is not delivered
LOOK = ('facts', 'features', 'setup', 'screens', 'visual')      # the check's own stages that picture and review the screens
FINAL = ('intake', 'baseline')      # the finished product's load too: k6 on its production build, at the plan's expected users


def look(state, root, progress, final=False):
    """The delivered milestone's screens, pictured and reviewed against DESIGN.md by the check's own stages (LOOK), on its
    copy, in look/ beside the report (so the review reads the same DESIGN.md): what departs from the look, for the next
    milestone to fix first. A stage that could not run says why; the milestone stays delivered."""
    from ...pipeline import execute
    out = guided.report_of(state).parent / 'look'
    shutil.rmtree(out, ignore_errors=True)
    progress(4, 5, 'picturing the screens and reviewing them against DESIGN.md')
    try:
        stages = execute(str(root), out, only=LOOK + (FINAL if final else ()), language=state.get('lang') or 'en', runtime=project_state.runtime_of(state) / 'look',
                         provider=guided.check_provider(state))['stages']
    except Exception as problem:              # the review is a help to the build, never a reason it fails
        return {'not_done': f'{type(problem).__name__}: {problem}'[:300]}
    return {**_found(out), 'not_done': {name: stages[name].get('reason') for name in LOOK + (FINAL if final else ()) if stages[name]['status'] != 'ok'}}


def _found(out):
    """What the look's stages found in `out`: the design departures, the screens' problems, Lighthouse and the load."""
    findings = (read(out / 'nodes/visual_reviewer/findings.json') or {}).get('findings') or []
    pictured = read(out / 'live/screens.json') or {}
    return {'screens': len(pictured.get('rows') or []), 'departures': findings[:25],
            # what axe, the touch targets and Lighthouse found on the running screens: fixed like the departures
            'screen_problems': [{'page': r.get('url'), 'width': r.get('width'), 'problems': r['failures']}
                                for r in pictured.get('rows') or [] if r.get('failures')][:25],
            'speed': (pictured.get('lighthouse') or {}).get('scores'),
            'load': _load(out),}


def _load(out):
    """The load scenarios measured on the production build, each with its numbers and threshold."""
    return [{'id': row['id'], **(row.get('before') or {}), 'threshold': row.get('threshold')}
            for row in (read(out / 'live/baseline.json') or {}).get('scenarios') or []]
