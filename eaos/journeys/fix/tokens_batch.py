"""A batch of the look (M18.18, M18.19): raw values named as tokens (eaos/analysis/design/tokens_codemod.py) on a branch of their own, no model asked, kept only when the
lock and the style oracle say so: with nothing agreed, nothing may look different; with what the person agreed to merge, only that may.

    proposal(target)    what it would do, nothing written: how many values, in how many files, where the tokens file goes
    make(batch)         made and proved in a clone of the authorised commit: the summary, `kept` the files, empty when refused
"""
from ...analysis.design import tokens_codemod
from ...analysis.repair.project_guide import tracked
from ...live.behavior.lock import LockPass, verify_lock
from ...live.behavior.look_oracle import look_changed
from .execute import commit_all, git, original_checks, own_batch, record_batch
from .waves.batch import gates


def proposal(target, agreed=None):
    drawn = tokens_codemod.plan(target, tracked(target), agreed)
    return {'tokens': len(drawn['tokens']), 'uses': drawn['uses'], 'files': sorted(drawn['files']), 'home': drawn['home'], 'refused': drawn['refused'],
            'merges': list(agreed or ())}


def _rules(agreed):
    """What the oracle lets differ: what the person agreed to, as the browser reads a colour."""
    from ...analysis.assessments.one_source_look import rgb
    def said(value):
        colour = rgb(value)
        return f'rgb({colour[0]}, {colour[1]}, {colour[2]})' if colour else value
    return [{'property': None, 'from': said(rule['from']), 'to': said(rule['to'])} for rule in agreed or ()]


def _proved(batch, root, base, rules):
    """Why the batch is refused, '' when it stands. The look refused it: the same pass on the code as it was tells what on those pages moves by itself."""
    name = f"design-{batch['number']}"
    why = gates({'before': original_checks(batch['target'], batch['runtime']), 'root': root, 'runtime': batch['runtime'], 'report': batch['report'], 'lock': True,
                 'declared': (), 'known': (), 'intended': None, 'look': rules}, name)
    if 'of the look' not in why: return why
    head = git(root, 'rev-parse', 'HEAD').stdout.strip()
    git(root, 'reset', '--hard', '--quiet', base)
    try: verify_lock(batch['report'], root, batch['runtime'], LockPass(f'{name}-control'))
    finally: git(root, 'reset', '--hard', '--quiet', head)
    return look_changed(batch['runtime'], name, rules, control=f'{name}-control')


def make(batch):
    agreed = batch.get('agreed') or []
    batch = {**batch, 'kind': 'design', 'items': agreed}
    root, base = own_batch(batch['target'], batch['runtime'], f"DESIGN-{batch['number']}")
    drawn = tokens_codemod.plan(root, tracked(root), agreed)
    if drawn['refused']: return record_batch(batch, root, base, [], [drawn['refused']])
    written = tokens_codemod.apply(root, drawn)
    commit_all(root, f"Name the look's values: {len(drawn['tokens'])} tokens in {drawn['home']}, {len(written)} files\n\nExecuted by EAOS (design batch), no assistant.", written)
    try: why = _proved(batch, root, base, _rules(agreed))
    except RuntimeError as problem: why = f'nothing proves it, so it is not kept: {str(problem)[:300]}'
    if why: return record_batch(batch, root, base, [], [why])
    batch['extra'] = {'tokens': len(drawn['tokens']), 'uses': drawn['uses'], 'home': drawn['home']}
    return record_batch(batch, root, base, written, [])
