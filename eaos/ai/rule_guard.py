"""A rule's guard written once by the person's assistant (M16.2): asked one question with the rule's words and the
project's languages, its answer proved on its own examples (eaos/analysis/rules/guards.py checked) before it is kept;
one answer that fails its proof is asked again with the reason, and a rule no answer could guard is said so, never
pretended. After this one ask, the guard runs free: no token is spent on it again."""
import json
from collections import Counter
from pathlib import Path

from ..analysis.rules import guards

SCHEMA = {'type': 'object', 'additionalProperties': False, 'required': ['kind', 'why'],
          'properties': {'kind': {'enum': list(guards.KINDS)}, 'why': {'type': 'string'},
                         'language': {'type': 'string'}, 'rule': {'type': 'string', 'description': "ast-grep's rule object, as JSON"},
                         'message': {'type': 'string'}, 'files': {'type': 'array', 'items': {'type': 'string'}},
                         'broken': {'type': 'array', 'items': {'type': 'string'}}, 'kept': {'type': 'array', 'items': {'type': 'string'}},
                         'command': {'type': 'array', 'items': {'type': 'string'}},
                         'detectors': {'type': 'array', 'items': {'type': 'string'}}}}
PROMPT = """A person gave this rule for their software project, in their own words:

  {words}

Write the one machine check that finds where the code breaks it, so that no AI has to remember the rule again.
The project's code is mostly: {languages}. Answer with one of:
- kind "pattern": an ast-grep rule. `language` (one of {extensions}), `rule`: ast-grep's rule object as JSON text
  (for example {{"pattern": "localStorage.setItem($K, $V)"}}, or {{"any": [...]}}, {{"kind": ..., "has": ...}}),
  `message`, `files` (globs where the rule applies, or none), `broken`: two or three short snippets that break the
  rule (each must be found) and `kept`: two or three that keep it (none may be found). Prefer this.
- kind "test": `command`, a command of the project's own that fails when the rule is broken (only one it already has).
- kind "detector": `detectors`, EAOS's own detectors that already check this: {detectors}.
- kind "none": when no machine check can tell (a matter of taste or of a person's judgement); `why` says it.
`why`: one sentence, in the rule's language, on what the check finds.{again}"""
DETECTORS = ('copy (code copied word for word)', 'complex', 'size', 'security', 'dead (code nothing uses)',
             'real_data (personal or business data written in the code)', 'data_keeping (how data is saved and kept)',
             'one_source (near copies, the look outside its tokens, screen patterns, ways of working)', 'layers (a boundary of the system)')


def languages(project):
    """The project's three most common kinds of code file, by extension."""
    count = Counter(p.suffix.lower() for p in Path(project).rglob('*')
                    if p.is_file() and p.suffix and not set(p.parts) & {'node_modules', '.git', '.venv', 'dist', 'build'})
    known = {ext: lang for lang, ext in guards.EXTENSIONS.items()}
    return ', '.join(f'{known[ext]} ({n} files)' for ext, n in count.most_common(20) if ext in known) or 'unknown'


def _guard(answer):
    """The answer as a guard to check: the rule's JSON text read."""
    guard = {key: value for key, value in answer.items() if key not in ('broken', 'kept')}
    if answer.get('kind') == 'pattern':
        try: guard['rule'] = json.loads(answer.get('rule') or '')
        except ValueError as problem: raise ValueError(f'the rule is not JSON: {problem}') from None
        guard['examples'] = {'broken': answer.get('broken') or [], 'kept': answer.get('kept') or []}
    return guard


def write(rule, project, folder, adapters=None):
    """(the guard, proved; what the asks cost in dollars or None). No assistant here: ValueError."""
    from .assistant import tiers
    from .assistant.headless import ask
    from .nodes.framework import pick
    adapter = pick(adapters)
    if adapter is None: raise ValueError('no AI assistant is ready here to write the guard: write it yourself (eaos rules guard --help)')
    again, cost = '', None
    for attempt in (1, 2):
        prompt = PROMPT.format(words=rule['words'], languages=languages(project), extensions=', '.join(guards.EXTENSIONS),
                               detectors='; '.join(DETECTORS), again=again)
        answer = ask(adapter, prompt, SCHEMA, Path(folder) / f'ask-{attempt}', tier=tiers.tier_of('rule_guard'))
        cost = (cost or 0) + answer['cost_usd'] if answer.get('cost_usd') is not None else cost
        try: return guards.checked(_guard(answer['answer'])), cost
        except ValueError as problem:
            again = f'\n\nYour last answer was refused: {problem}. Answer again.'
            failed = str(problem)
    return guards.checked({'kind': 'none', 'why': f'two guards written for it failed their own examples ({failed})'}), cost
