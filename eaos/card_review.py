"""How a card is judged and settled (eaos/plan.py builds and orders the cards): its acceptance and verify command, what
to do about its claim and what must still hold after, the assistant's triage verdicts applied to the ledger, the screen
reviewer's findings as design cards, and the resolution that settles each card.
"""
from pathlib import Path
from .compose.labels import falsifier_of
from .remediation_patterns import pattern_for
from .workspace import read, write

# A design finding's share of the top code card's priority, by its severity, times the weight of an unconfirmed
# claim (eaos/ranking.py): on the code claims' scale, never above the most urgent of them.
SEVERITY_SHARE = {'high': 1.0, 'medium': 0.5, 'low': 0.25}
SEVERITY_ORDER = ('high', 'medium', 'low')
RESOLUTIONS = ('fix', 'keep', 'owner')
RESOLUTION_FIELDS = ('resolution', 'change', 'question', 'options', 'recommendation', 'note', 'checks')


def acceptance_for(claim, target, out):
    from .decisions import decide
    decision = decide(claim)
    if decision['kind'] == 'repair' and decision['checks']:
        import shlex
        return [{'command': shlex.join(check['argv']) if check.get('kind') == 'command' else 'human review',
                 'expect': check.get('expected', '')} for check in decision['checks']]
    # An investigation changes no code: it is done when its decision is recorded (eaos decision-review), which
    # `eaos decided` checks. The decision itself stays a person's; the command only shows it was made.
    import shlex, sys
    from .decisions import identity
    uid = claim.get('uid') or identity(claim)
    return [{'command': shlex.join([sys.executable, '-m', 'eaos', 'decided', str(Path(out).resolve()), uid]),
             'expect': claim['id'] + ': a recorded decision (repair with its check, retain with an owner and a reason, or '
                       'the claim refuted) after weighing: ' + claim['falsifier']}]


def verify_command_for(claim, target, out):
    from .decisions import decide
    decision = decide(claim)
    checks = decision['checks']
    return next((check['argv'] for check in checks if check.get('kind') == 'command' and check.get('argv')), [])


def what_to_do(claim, pattern, unproven):
    """(change, options, rollback): proving or refuting an unproven claim first, else its pattern's change."""
    if not unproven:
        return (claim.get('assessment') or {}).get('proposed_change', pattern['change']), pattern['options'], pattern['rollback']
    return (('أثبت هذا الادعاء أو انقضه قبل أي تغيير: ' + falsifier_of(claim, 'ar')),
            [{'option': 'تشغيل مجسّ يحسم الادعاء', 'cost': 'منخفضة', 'verdict': 'مختار: لا تغيير قبل الحسم'},
             {'option': 'قبول الادعاء بلا إثبات', 'cost': 'صفر الآن', 'verdict': 'مرفوض: يخالف قاعدة الإسناد'},
             *pattern['options']],
            'لا تغيير في الكود خلال التحقيق.')


def invariants_of(claim):
    """What must still hold after the change. An empty list is a real answer, not a gap to fill."""
    assessment = claim.get('assessment') or {}
    stated = assessment.get('violated_invariant')
    rows = []
    if stated:
        rows.append({'invariant': stated, 'source': 'assessment', 'must_hold_after': True})
    rows.append({'invariant': claim['falsifier'], 'source': 'falsifier',
                 'must_hold_after': False,
                 'note': 'the observation that would show this claim is wrong; after a repair it should hold'})
    return rows


def page_of(page):
    """One name per page: `http://host/`, `/`, `/#/` and `#/` are the home page; `/#/branches` is `/branches`."""
    from urllib.parse import urlsplit
    text = str(page or '')
    if '://' in text:
        parts = urlsplit(text)
        text = parts.path + ('#' + parts.fragment if parts.fragment else '')
    return '/' + '/'.join(part for part in text.split('?')[0].replace('#', '/').split('/') if part)


def template_of(page):
    """The page as a kind of page: a part of its path that names one record (a digit, an escape or a sign in it, as in
    `/tasks/TASK-001` or `/system/f/eaos%2Fplan.py`) is `*`, so the findings of every task page are the task page's."""
    import re
    return '/' + '/'.join('*' if re.search(r'[^a-z-]', part) else part for part in page_of(page).split('/') if part)


def design_cards(findings, tasks):
    """The visual reviewer's findings as design cards: one per (kind of page, kind of problem), the most severe finding
    standing for them and every picture of them its evidence (`design.findings`); each priority on the code cards'
    scale (SEVERITY_SHARE)."""
    from .ranking import CONFIDENCE_WEIGHT
    top = max((t.get('priority') or 0 for t in tasks if t.get('origin') != 'visual_review'), default=0) or 1.0
    kept = {}
    for finding in sorted(findings, key=lambda f: SEVERITY_ORDER.index(f['severity']) if f.get('severity') in SEVERITY_ORDER else 3):
        kept.setdefault(_design_key(finding), []).append(finding)
    return [_group_card(number, group, (top, CONFIDENCE_WEIGHT['HYPOTHESIS'])) for number, group in enumerate(kept.values(), 1)]


def _design_key(finding):
    """(kind of page, kind of problem) of a design finding; a problem of a shared part (the top bar, the language)
    is one card for every page that shows it."""
    if finding.get('part') not in (None, '', 'page'): return ('shared', finding['part'])
    return (finding.get('template') or template_of(finding.get('page')),
            finding.get('kind') or ' '.join(str(finding.get('title') or '').lower().split()))


def _also_shown(card, group, finding):
    """Every picture of the group as the card's evidence, and the other problems seen on the page in its change."""
    # A finding of the page reviewer (eaos/studio/nodes/visual_reviewer.py) lists every picture it shows on.
    shown = [show for f in group for show in f.get('pictures') or [f]]
    images = list(dict.fromkeys(show['image'] for show in shown))
    if len(images) <= 1: return
    card['design']['also_in'] = images[1:]
    card['finding_ids'] = images
    card['evidence']['evidence_ids'] = images
    card['evidence']['images'] = list(dict.fromkeys(show['file'] for show in shown))
    titles = list(dict.fromkeys(f['title'] for f in group[1:] if f['title'] != finding['title']))
    if titles: card['change'] += ' Also on this page: ' + '; '.join(titles[:6]) + (f' (+{len(titles) - 6})' if len(titles) > 6 else '') + '.'


def _group_card(number, group, scale):
    """The card of one group of design findings, its most severe finding standing for them; `scale`: (the code cards'
    top priority, a hypothesis's confidence weight)."""
    top, weight = scale
    finding = group[0]
    card = design_card(number, finding)
    card['priority'] = round(top * SEVERITY_SHARE.get(finding.get('severity'), 0.25) * weight, 4)
    card['design']['page'] = finding.get('template') or template_of(finding.get('page'))
    card['design']['findings'] = [{k: f.get(k) for k in ('image', 'file', 'page', 'viewport', 'theme', 'title', 'severity', 'region', 'why',
                                                         'pictures')}
                                  for f in group]
    _also_shown(card, group, finding)
    if finding.get('resolution') in RESOLUTIONS:
        card['design']['resolution'] = {k: finding.get(k) for k in ('resolution', 'question', 'options', 'recommendation')}
    return card


def design_card(number, finding):
    """A card for one finding of the visual reviewer: an investigation, done when its decision is recorded, citing its
    picture and the region of it."""
    region = finding['region']
    where = f"{finding['file']} ({region['x']:.2f}, {region['y']:.2f}, {region['width']:.2f} x {region['height']:.2f})"
    return {'id': f'TASK-V{number:03d}', 'claim_id': None, 'title': finding['title'][:120], 'render': None, 'kind': 'investigate',
            'contract_version': 1,
            'decision': {'contract_version': 1, 'kind': 'investigate', 'readiness': 'needs_review', 'blockers': [], 'checks': [],
                         'reason': 'A design finding of the visual reviewer: confirm it on the screen before changing it.',
                         'allowed_outcomes': ['repair', 'retain', 'blocked_missing_requirement']},
            'prerequisites': [], 'before': None, 'after': None, 'requirement_refs': [], 'status': 'planned',
            'priority': SEVERITY_SHARE.get(finding['severity'], 0.25), 'pattern': 'design_review', 'paths': [], 'origin': 'visual_review',
            'impact': finding['why'], 'impact_render': None,
            'evidence': {'fact_ids': [], 'evidence_ids': [finding['image']], 'probe_ids': [], 'images': [finding['file']],
                         'region': region, 'falsifier': f"The picture {where} does not show it."},
            'blast_radius': {'direct_dependents': [], 'transitive_dependents': [], 'flows': [], 'entry_points': [],
                             'covering_tests': [], 'coverage': {}, 'change_partners': [], 'total': 0},
            'change': f"{finding['why']} ({finding['page']}, {finding['viewport']}, {finding['theme']}: {where})",
            'options': [], 'rollback': 'No code changes while the finding is confirmed.', 'acceptance': [{'command': 'human review',
            'expect': f'The screen no longer shows it: {where}'}], 'verify_command': [], 'effort': 'S', 'effort_basis': {'files': 0, 'dependents': 0},
            'effort_confidence': 'Not measured: a design change on one screen.', 'invariants': [], 'harm': {},
            'finding_ids': [finding['image']], 'section': 'frontend', 'design': {k: finding.get(k) for k in ('kind', 'severity', 'page', 'viewport', 'theme')}}


def apply_verdicts(out, tasks, verdicts, language='ar'):
    """The one place the assistant's triage reaches the ledger, before anything ranks, plans or reports: the claims of
    a card it rejected are refuted (confidence REFUTED, `refuted_by` the card, its why kept in `triage`), the claims of
    a card it doubted carry the doubt (eaos/decisions.py: needs_review, never fixed automatically), those of a card it
    confirmed carry its resolution (fix, keep or owner, eaos/decisions.py decide), and the ledger's ranking, decisions,
    brief and debt register are drawn again (dossier.refresh_views), so the risks, the reports and the plan all read the
    same verdicts. Returns {claim id: claim}."""
    from .dossier import refresh_views
    out = Path(out)
    dossier = read(out / 'dossier.json')
    claims = {c['id']: c for c in dossier['claims']}
    for task in tasks:
        verdict = verdicts.get(task['id'])
        if not verdict or verdict.get('decision') not in ('confirm', 'doubt', 'reject'): continue
        for claim in filter(None, (claims.get(c) for c in task.get('claim_ids') or [task.get('claim_id')])):
            _triage(claim, task['id'], verdict)
    write(out / 'dossier.json', dossier)
    refresh_views(out, language)
    return {c['id']: c for c in read(out / 'dossier.json')['claims']}


def _triage(claim, card, verdict):
    """The triage's verdict on a claim; a rejected claim is refuted by its card."""
    claim['triage'] = {'decision': verdict['decision'], 'card': card, 'why': verdict.get('why'),
                       'evidence': list(verdict.get('evidence') or []), 'rejudged': bool(verdict.get('rejudged')),
                       **{k: verdict[k] for k in RESOLUTION_FIELDS if verdict.get(k) is not None}}
    if verdict['decision'] == 'reject':
        claim['confidence'] = 'REFUTED'
        claim['refuted_by'] = sorted(set(claim.get('refuted_by') or []) | {'card_triage:' + card})


def _design_resolution(card):
    """A design card is the change it named, unless its finding asked the person or kept it."""
    asked = card['design'].get('resolution') or {}
    pictures = len(card['finding_ids']) or 1
    resolution = asked if asked.get('resolution') in ('keep', 'owner') and (asked['resolution'] == 'keep' or asked.get('question')) else {
        'resolution': 'fix', 'change': card['change'],
        'note': f'the screen reviewer saw it on {pictures} picture{"s" if pictures > 1 else ""} of this page and named the change'}
    return {**{k: v for k, v in resolution.items() if v is not None}, 'why': card['impact'],
            'severity': card['design'].get('severity'), 'reach': pictures}


def resolutions(tasks, verdicts, design):
    """{card: resolution} the assistant gave: the triage's for the code cards it confirmed (nodes/card_triage), the
    screen reviewer's for the design cards (a design card is the change it named, unless its finding asked the
    person or kept it). A card the triage doubted is kept as not proven, never fixed blind nor handed to the person:
    the next check judges it again on its new evidence."""
    out = {}
    for task in tasks:
        verdict = verdicts.get(task['id']) or {}
        reach = (task.get('blast_radius') or {}).get('total') or 0
        if verdict.get('decision') == 'confirm' and verdict.get('resolution') in RESOLUTIONS:
            out[task['id']] = {**{k: verdict.get(k) for k in RESOLUTION_FIELDS if verdict.get(k) is not None}, 'why': verdict.get('why'),
                               'severity': verdict.get('severity'), 'reach': reach}
        elif verdict.get('decision') == 'doubt':
            out[task['id']] = {'resolution': 'keep', 'severity': verdict.get('severity'), 'reach': reach,
                               'why': f"Not proven by its evidence ({verdict.get('why') or 'no reason given'}); the next check judges it again."}
    for card in design: out[card['id']] = _design_resolution(card)
    return out


def fix_check(card, change, revision):
    """The check of a change the assistant decided: the project's own checks gate it (eaos/waves.py: a card with no
    command of its own is kept on the gates) and the next check tells whether it is gone."""
    return {'id': 'TRIAGE-' + card, 'kind': 'human', 'invariant': 'The problem this card names is gone and nothing else changed.',
            'expected': change, 'cwd': '.', 'source_revision': revision,
            'rubric': "The change your assistant decided is made, the project's own checks pass, and the next check no longer finds it."}


def resolve(task, resolution, claim, target, out, revision):
    """The card as the assistant resolved it: `fix` makes it remediate and ready with the change and its check, `owner`
    keeps it an investigation carrying the question, `keep` closes it (the caller sets it aside)."""
    from .decisions import decide
    words = 'decided by your assistant: ' + (resolution.get('note') or resolution.get('why') or '')
    task['resolution'] = {**{k: v for k, v in resolution.items() if k not in ('checks', 'severity', 'reach')}, 'by': 'assistant', 'words': words}
    if claim is not None:
        task['decision'] = decide(claim)
        task['acceptance'], task['verify_command'] = acceptance_for(claim, target, out), verify_command_for(claim, target, out)
        task['kind'] = 'remediate' if task['decision']['kind'] == 'repair' else 'investigate'
    if resolution['resolution'] != 'fix': return task
    task['change'] = resolution['change']
    if claim is not None:
        task['rollback'] = pattern_for(claim)['rollback']
    else:
        check = fix_check(task['id'], resolution['change'], revision)
        task['decision'] = {**task['decision'], 'kind': 'repair', 'readiness': 'ready', 'blockers': [], 'checks': [check],
                            'reason': words, 'allowed_outcomes': []}
        task['acceptance'] = [{'command': 'human review', 'expect': check['rubric']}]
        task['rollback'] = 'One commit on the fix branch; reverting it restores the screen.'
        task['kind'] = 'remediate'
    return task
