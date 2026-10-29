"""The person's own rules as MCP tools (M16): `rules` (read them: answered at once), `rule` (every change to them, by
`op`) and `check_changed` (the diff-scoped check), thin callers of eaos/interfaces/rules.py like `eaos rules`; on the server the Studio's actions call
too (server.build), so its "Your rules", its chat and a card's comment use the same ones.

What only the person decides: pinning, unpinning, changing a rule and the commit hook take `person_agreed`, given
only after their yes; inside a Studio run each is refused (person.PERSON_ONLY). Saying a rule is the person's words:
`words` as they said them, never the assistant's summary of them.
"""
from .. import rules as person_rules
from .person import STUDIO, refuse_in_studio_run

DECIDED = ('pin', 'unpin', 'change', 'hook', 'approve')        # the person's: their yes first


def _door(door):
    from ...journeys.handover import assistant
    return door if door in ('chat', 'card') else 'studio' if assistant() == STUDIO else 'mcp'


def rules(op: str = 'list', id: str | None = None, project: str | None = None) -> str:
    if op == 'list': return person_rules.listing(project)
    if op == 'touches': return person_rules.touches(project, id)
    raise ValueError('op is one of list, touches (a change is the rule tool)')


OPS = {
    'add': lambda project, g: person_rules.add(project, g['words'] or '', g['door'], card=g['card'], pin=g['pin']),
    'guard': lambda project, g: person_rules.guard(project, g['id'], g['guard'], g['write'], 'assistant' if g['guard'] else 'person', g['door']),
    'pin': lambda project, g: person_rules.pin(project, g['id'], door=g['door'], why=g['why']),
    'unpin': lambda project, g: person_rules.unpin(project, g['id'], door=g['door'], why=g['why']),
    'change': lambda project, g: person_rules.change(project, g['id'], g['words'], door=g['door'], why=g['why']),
    'hook': lambda project, g: person_rules.hook(project, g['on'], agreed=True),
    'approve': lambda project, g: person_rules.approve(project, g['id'], door=g['door']),
}


def rule(op: str, id: str | None = None, words: str | None = None, card: str | None = None, pin: bool = False,
         guard: dict | None = None, write: bool = False, on: bool = True, person_agreed: bool = False, door: str | None = None,
         why: str | None = None, project: str | None = None) -> str:  # limits: parameters -- the MCP tool's schema: each parameter is an argument the assistant passes
    if op not in OPS: raise ValueError(f"op is one of {', '.join(OPS)}")
    decided = 'pin' if op == 'add' and pin else op if op in DECIDED else None
    if decided:
        refuse_in_studio_run(f'rule {decided}')
        if not person_agreed: return _ask(decided, project, id)
    return OPS[op](project, {'id': id, 'words': words, 'card': card, 'pin': pin, 'guard': guard, 'write': write, 'on': on,
                             'door': _door(door), 'why': why})


def _ask(op, project, ident):
    """What the assistant does before the person's yes: show what it touches, ask, end its turn."""
    return {'status': 'needs_the_person', 'touches': person_rules.touches(project, ident) if ident else None,
            'what_now': f'This is the person\'s decision: show them what it touches, ask whether to {op} it in their language and '
                        'end your turn; only after their yes call again with person_agreed=true.'}


def check_changed(base: str | None = None, staged: bool = False, project: str | None = None) -> str:
    return person_rules.changed(project, base, staged)


def register(server, reading, working, answer):
    doc = ' project: the project folder (default: the folder the assistant was opened in).'
    server.tool(annotations=reading, description='The person\'s own rules for this project (what they keep asking for: "the data lives '
                'only in the database"): op=list (each rule: in scope, pinned, held or broken where, how often it came back, '
                'the commit hook); op=touches (id: what changing or unpinning it touches: its guard, its tests, the context '
                'files and the hook).' + doc)(answer(rules))
    server.tool(annotations=working, description='Keep or change one of the person\'s rules. op=add (words: the person\'s own words, '
                'as they said them, whenever they state a requirement that must hold; card: it holds for that card only; '
                'otherwise for the batch of fixes now; the same rule said again is counted, and the answer offers to pin it); '
                'op=guard (id, and guard: {"kind": "pattern", "language", "rule": an ast-grep rule object, "message", "files", '
                '"examples": {"broken": [code that breaks it], "kept": [code that keeps it]}}, or {"kind": "test", "command": '
                '[...]}, {"kind": "detector", "detectors": [...]}, {"kind": "none", "why"} when no machine can check it; '
                'write=true asks your assistant once instead): it is proved on its examples, then runs free on every check, fix '
                'and commit (a test command you propose waits for the person\'s approval before it ever runs); op=pin, unpin, '
                'change (words: its guard then waits until one is written for them, or the person keeps it), hook (on: the '
                'pinned rules on every commit), approve (id: the person approves a waiting guard): the person\'s decision, '
                'person_agreed=true only after their yes.' + doc)(answer(rule))
    server.tool(annotations=working, description='Check only what changed, now, before it lands: the person\'s rules and the code laws '
                'on the changed files and the files that depend on them (no AI, seconds). base: what the change is measured from '
                '(default HEAD; the working tree and new files included); staged=true: what is staged for a commit. Answers each '
                'rule broken with its places (only what the change brought) and what the change adds against the code laws.' + doc)(answer(check_changed))
