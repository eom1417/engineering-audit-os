"""`eaos rules` and `eaos check --changed`: the person's own rules from a terminal (eaos/interfaces/rules.py, the one
interface every door shares). What they print comes from govern_words.WORDS, in both languages.

    eaos rules                                   every rule: in scope, pinned, held or broken where
    eaos rules add "<words>" [--card ID] [--pin] a rule said (for a card, for the batch now, or pinned)
    eaos rules pin|unpin ID                      pinned for every change, or no longer held (what it touches shown first)
    eaos rules change ID "<words>" [--yes]       its words changed, what it touches shown first
    eaos rules guard ID (--write | --pattern JSON --language L --broken CODE --kept CODE | --test CMD | --detectors D…)
    eaos rules hook on|off [--yes]               the pinned rules on every commit (git's pre-commit hook)
    eaos check --changed [--base REF] [--staged] the diff-scoped check: the rules and the code laws on what changed
"""
import json
import shlex
import sys

from .. import rules
from ...journeys import guided
from ..govern_words import words
from .commands import agreed, command, say


def _scope(rule, lang):
    kind = rule['scope']['kind']
    return words('pinned', lang) if kind == 'pinned' else words(f'{kind}_scope', lang, ref=rule['scope'].get('ref') or '')


def _show(row, lang):
    mark = '📌' if row['scope']['kind'] == 'pinned' else '  '
    state = ('❌ ' + ', '.join(row['last_broken']['places'][:3]) if row['last_broken'] and row['broken'] and
             (not row['held'] or row['held']['at'] < row['last_broken']['at']) else '✅' if row['held'] else '·')
    say(f"{mark} {row['id']:<4} {'' if row['in_scope'] else '(ended) '}{row['words'][:90]}")
    say(f"        {_scope(row, lang)} · {row['said_on']} · {row['guard'][:70]} · {state}")


@command
def rules_command(args, lang):
    action = args.action
    if action == 'list': return _list(args, lang)
    if action == 'add': return _add(args, lang)
    if action in ('pin', 'unpin', 'change'): return _change(args, lang)
    if action == 'guard': return _guard(args, lang)
    if action == 'hook': return _hook(args, lang)
    raise ValueError(f'unknown action {action}')


def _list(args, lang):
    found = rules.listing(args.project)
    for row in found['rules']: _show(row, lang)
    guided.box(lang, words('rules', lang, count=len(found['rules']), pinned=found['pinned']) if found['rules'] else words('no_rules', lang),
               commands=['eaos rules add "<…>"', 'eaos rules pin R1', 'eaos check --changed'])


def _add(args, lang):
    said = ' '.join([args.id or '', *(args.said or [])]).strip()        # `add` has no id: its words come first
    done = rules.add(args.project, said, 'terminal', card=args.card, pin=args.pin)
    row = done['rule']
    notes = [words('rule_again', lang, date=row['said_on'], times=row['said'])] if done['repeat'] else []
    if row['offer_pin']: notes.append(words('rule_offer_pin', lang))
    guided.box(lang, words('rule_kept', lang, id=row['id'], words=row['words'][:120], scope=_scope(row, lang)), note=notes,
               commands=[f"eaos rules pin {row['id']}"] if row['offer_pin'] else [f"eaos rules guard {row['id']} --write"])


def _change(args, lang):
    ident = args.id
    shown = rules.touches(args.project, ident)
    say(words('rule_touches', lang, guard=shown['guard'], tests=', '.join(shown['tests']) or '-',
              files=', '.join(shown['context_files']) or '-', hook='✓' if shown['hook'] else '-'))
    if args.action == 'pin':
        done = rules.pin(args.project, ident, door='terminal')
        return guided.box(lang, f"📌 {ident}: {done['rule']['words'][:100]}", note=', '.join(done['written_into']),
                          commands=['eaos rules hook on', 'eaos rules'])
    if args.action == 'unpin':
        done = rules.unpin(args.project, ident, door='terminal')
        return guided.box(lang, words('rule_unpinned', lang, id=ident, files=', '.join(done['removed_from']) or '-'), commands=['eaos rules'])
    agreed(rules._state(args.project)['project'], f'rule_change_{ident}', words('go_ahead', lang), args.yes)
    done = rules.change(args.project, ident, ' '.join(args.said or []), door='terminal')
    guided.box(lang, words('rule_kept', lang, id=ident, words=done['rule']['words'][:120], scope=_scope(done['rule'], lang)),
               commands=[f'eaos rules guard {ident} --write'])


# The guard a person writes on the command line: the first of these options given makes it.
GIVEN = (('test', lambda a: {'kind': 'test', 'command': shlex.split(a.test)}),
         ('detectors', lambda a: {'kind': 'detector', 'detectors': a.detectors}),
         ('pattern', lambda a: {'kind': 'pattern', 'language': a.language, 'rule': json.loads(a.pattern), 'message': a.message or '',
                                'examples': {'broken': a.broken or [], 'kept': a.kept or []}}),
         ('none', lambda a: {'kind': 'none', 'why': a.none}))


def _guard(args, lang):
    given = next(({**make(args), 'files': args.files or []} for name, make in GIVEN if getattr(args, name)), None)
    if not given and not args.write: raise ValueError('say the guard (--pattern, --test, --detectors or --none), or --write to have your assistant write it')
    done = rules.guard(args.project, args.id, given, write=not given, door='terminal')
    now = done['now']
    guided.box(lang, words('rule_guarded', lang, id=args.id, guard=done['rule']['guard'], status=words(f"status_{now['status']}", lang),
                           places=', '.join(now['places'][:5])), commands=['eaos rules', 'eaos check --changed'])


def _hook(args, lang):
    on = args.id != 'off'
    if on: agreed(rules._state(args.project)['project'], 'rules_hook', rules.hook(args.project, True)['ask_the_person'], args.yes)
    done = rules.hook(args.project, on, agreed=True)
    guided.box(lang, words('hook_on', lang, hook=done['hook']) if on else words('hook_off', lang), commands=['eaos rules'])


def changed(args, lang):
    """`eaos check --changed`: the diff-scoped check; exit 1 when a rule is broken (the hook refuses the commit). From
    the hook, EAOS's own failure never stops the person's commit: it is said, and the commit goes on."""
    try: found = rules.changed(args.project, args.base, args.staged, args.hook)
    except Exception as problem:
        if not args.hook: raise
        print(f'EAOS could not check your rules on this commit ({type(problem).__name__}: {problem}); it goes on.', file=sys.stderr)
        return 0
    from ...analysis.rules.held import refusal
    for line in refusal(found['rules'], lang): say(f'❌ {line}')
    for problem in found['laws'][:20] if not args.hook else []: say(f"⚠️  {problem['what']}")
    if found['refused']: print(words('changed_broken', lang, count=len(found['rules'])), file=sys.stderr)
    if not args.hook: _changed_box(found, lang)        # git shows what a hook prints: no box, no next command
    return 1 if found['refused'] else 0


def _changed_box(found, lang):
    held = words('changed_ok', lang, files=len(found['changed']), reached=len(found['reached']), rules=len(found['results']), seconds=found['seconds'])
    guided.box(lang, held if not found['refused'] else words('changed_broken', lang, count=len(found['rules'])),
               status='warn' if found['refused'] or found['laws'] else 'ok',
               note=words('changed_laws', lang, count=len(found['laws'])) if found['laws'] else None, commands=['eaos rules'])
