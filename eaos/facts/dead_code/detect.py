"""Dead code: what no user of the product can reach, and what nothing reads.

Three questions, each answered from facts already collected and the text of the snapshot:

- A module no production entry point imports, directly or through other modules. Tests do not count
  as users: a module imported only by its own test is dead for the product, though it is a review candidate
  (test_only), not a removal, since the tests may pin it on purpose. A program in a scripts/ or tools/ folder that
  nothing on record runs is a review candidate too: programs are run, not imported.
  Entry points include the source a built start script comes from (`node dist-server/main.mjs` runs
  `server/main.mjs`); tool configurations, and programs a CI step, container or make recipe, or document runs,
  are walked from as well.
- A top-level function or class whose name appears nowhere outside its own definition, or only in tests.
- A module-level constant (UPPER_CASE) that nothing reads.

The reference check is textual on purpose. A name held in a registry dictionary, passed to getattr as a
string, or listed in a JSON file is a reference an import graph cannot see; counting any occurrence as a
reference trades a few missed candidates for no false accusation. What survives is dead by two measures:
the graph does not reach it, and no text names it.

`adjudicate` applies the same test to the dead-code candidates an external engine reports, so EAOS asserts
one verdict per candidate whoever raised it: confirmed, or refuted with the reason written down.

What the product reaches (its entry points, roots and the loads an import graph cannot see) is walked by
eaos/facts/dead_code/reach.py.
"""
import re
from collections import Counter
from pathlib import PurePosixPath

from .. import make
from .reach import CONFIG, _is_test, _walk
from ..source import classify, language_of

NAME = 'deadcode'
VERSION = '1'
LIMITATIONS = [
    'A reference is any occurrence of the name in code or configuration text outside its definition; a name '
    'reused for something else keeps a dead symbol alive, so misses are possible and false accusations rare.',
    'Reachability follows resolved imports from production entry points; a module loaded by a computed path '
    'counts as reached only when its dotted or slashed path appears as text somewhere reached, or a path literal '
    'in a reached module names it from the module\'s folder or one above it.',
    'Package data (templates/ and rules/ folders, declared package-data globs) is reached and not judged name by '
    'name; a semgrep rule test (`# ruleid:` lines) is a fixture, never a candidate.',
    'Methods are not judged: a method is called through an object whose type is not resolved here.',
    'A built output named by a script (dist/, build/, out/, dist-<name>/) is traced back to its source by path; a '
    'build that renames or bundles differently leaves that entry unseen.',
]
TOKEN = re.compile(r'[A-Za-z_$][\w$]*')
PY_CONSTANT = re.compile(r'^(_?[A-Z][A-Z0-9_]*[A-Z0-9])\s*(?::[^=]+)?=(?!=)', re.M)
JS_CONSTANT = re.compile(r'^(?:export\s+)?const\s+(_?[A-Z][A-Z0-9_]*[A-Z0-9])\s*[:=]', re.M)
REFERENCE_SUFFIXES = ('.json', '.yaml', '.yml', '.toml', '.cfg', '.ini', '.html')
# Files that are not product code even when parsed: build and tool configuration, package markers,
# type declarations, migrations, examples. They are never candidates.
NOT_CANDIDATES = (CONFIG, re.compile(r'(^|/)(conftest|setup|noxfile|fabfile)\.py$'),
                  re.compile(r'(^|/)__init__\.py$'), re.compile(r'\.d\.ts$'), re.compile(r'(^|/)migrations?/'),
                  re.compile(r'(^|/)(vite-env|next-env)\.d\.ts$'), re.compile(r'(^|/)examples?/'))


def _tokens(text):
    return Counter(TOKEN.findall(text))


# A semgrep rule test marks the lines its rule must flag; the file is a fixture for the rule, not product code.
RULE_FIXTURE = re.compile(r'^[ \t]*(?:#|//)[ \t]*(?:ruleid|todoruleid|ok|todook):', re.M)
PROGRAM_FOLDERS = {'scripts', 'script', 'bin', 'tools', 'tool'}
REVIEW_REASONS = {'test_only': 'only tests name it: delete it with them, or keep it as the contract they pin',
                  'review': 'a program is run, not imported, and a person may run it by hand: nothing in CI, the '
                            'manifests or the docs runs it, so ask whether anyone still does before deleting it'}


def _finding(rule, path, line, symbol, message, subject_kind, evidence, sha, tests=(), program=False):
    # A name or module only tests read is either dead with its tests, or a contract the tests pin on purpose (a
    # test harness kept outside tests/); the text cannot tell which, so it is a review candidate (test_only), not an
    # asserted defect. A program in a scripts/ or tools/ folder is never imported: that nothing imports it says
    # nothing about whether anyone runs it, so it is a review candidate too.
    verdict = 'review' if program else 'test_only' if tests else 'confirmed'
    return make('engine_finding', NAME, VERSION, sha,
                {'path': path, 'start_line': line, 'symbol': symbol},
                {'engine': 'eaos', 'engine_version': VERSION, 'rule': rule, 'kind': 'dead_code', 'method': 'deterministic',
                 'message': message, 'subject_kind': subject_kind, 'measurements': [], 'engine_confidence': None,
                 'sites': [{'path': path, 'line': line}], 'evidence': evidence, 'tests': list(tests),
                 'adjudication': {'verdict': verdict, 'reason': REVIEW_REASONS.get(verdict, evidence)}},
                limitations=LIMITATIONS)


class References:
    """Where each name is written, split into product text and test text, per file."""

    def __init__(self, source):
        self.texts, self.product, self.tests = {}, {}, {}
        for item in source.readable():
            path = item['path']
            if language_of(path) is None and not path.endswith(REFERENCE_SUFFIXES): continue
            # A file under docs/ is documentation whatever its extension: naming a symbol there is not using it.
            if 'docs' in PurePosixPath(path).parts[:-1]: continue
            text = source.text(path)
            if text is None: continue
            self.texts[path] = text
            (self.tests if _is_test(path) else self.product)[path] = _tokens(text)

    def texts_of(self, paths):
        """{path: text} of the given paths it holds the text of."""
        return {p: self.texts[p] for p in paths if p in self.texts}

    def outside(self, name, path, span=None):
        """(product occurrences outside the definition, test files naming it)."""
        count = sum(tokens.get(name, 0) for other, tokens in self.product.items() if other != path)
        own = self.product.get(path, Counter()).get(name, 0)
        if own:
            lines = (self.texts.get(path) or '').split('\n')
            start, end = span or (1, 0)
            inside = Counter(TOKEN.findall('\n'.join(lines[start - 1:end]))).get(name, 0) if end >= start else 0
            count += max(own - inside, 0)
        tests = sorted(other for other, tokens in self.tests.items() if tokens.get(name))
        return count, tests


GLOBAL_OBJECTS = {'window', 'globalThis', 'self', 'global', 'document', 'navigator', 'console', 'process'}



def _candidate_file(path):
    return not _is_test(path) and classify(path) == 'source' and not any(rule.search(path) for rule in NOT_CANDIDATES)


def _module_finding(path, test_importers, seeds, sha):
    tests = sorted(test_importers.get(path, ()))
    why = f'imported only by tests ({", ".join(tests[:3])})' if tests else 'no production entry point imports it'
    program = bool(PROGRAM_FOLDERS & set(PurePosixPath(path).parts[:-1]))
    if program and not tests: why = 'a program nothing in CI, the manifests or the docs runs'
    return _finding('unreachable-module', path, 1, path, f'unreachable module `{path}`: {why}', 'module',
                    f'{len(seeds)} production entry points and the resolved import graph do not reach it', sha,
                    tests, program)


def _judgeable_name(name, judged):
    if not name or name.startswith('__') or name in ('main', 'default') or not judged(name): return False
    # `{'past-empty': (m) => ...}` names a function by a quoted key: it is reached by a computed lookup
    # (`MESSAGES[state]`), never by its name, so no text search can say it is unused.
    if not TOKEN.fullmatch(name.rsplit('.', 1)[-1]): return False
    # `window.alert = ...` replaces a platform global: every bare `alert()` reaches it, and none names it.
    return not (name.split('.', 1)[0] in GLOBAL_OBJECTS and '.' in name)


def _judgeable_symbol(path, value, name, scope):
    if not path or path in scope['dead_modules'] or path in scope['skipped'] or path not in scope['code']: return False
    if not _candidate_file(path): return False
    if value.get('kind') not in ('function', 'class') or value.get('parent') or value.get('decorators'): return False
    return _judgeable_name(name, scope['judged'])


def _declares(text, start):
    # `declare global { interface Window {...} }` extends a type the platform owns; nothing names it to use it.
    return 'declare ' in '\n'.join(text.split('\n')[max(0, start - 4):start])


def _noun(text, start, kind):
    # TypeScript's `type`, `interface` and `enum` are parsed as classes; the reader is told what it is.
    declared = (text.split('\n')[start - 1:start] or [''])[0]
    word = re.match(r'\s*(?:export\s+)?(?:declare\s+)?(?:const\s+)?(type|interface|enum)\b', declared)
    return word.group(1) if word and kind == 'class' else kind


def _symbol_finding(fact, scope):
    value, location = fact.get('value') or {}, fact.get('location') or {}
    path, name = location.get('path'), value.get('name')
    if not _judgeable_symbol(path, value, name, scope): return None
    text = scope['refs'].texts.get(path) or ''
    start = location.get('start_line') or 1
    if _declares(text, start): return None
    count, tests = scope['refs'].outside(name, path, (start, location.get('end_line') or 0))
    if count: return None
    module = str(PurePosixPath(path).with_suffix(''))
    how = f'referenced only by tests ({", ".join(tests[:3])})' if tests else 'no reference outside its definition'
    return _finding('unused-symbol', path, start, name,
                    f'unused {_noun(text, start, value["kind"])} `{module}.{name}`: {how}', 'symbol',
                    f'the name occurs nowhere in product code or configuration outside lines '
                    f'{location.get("start_line")}-{location.get("end_line")}', scope['sha'], tests)


def _constant_findings(path, scope):
    text = scope['refs'].texts.get(path) or ''
    pattern = PY_CONSTANT if language_of(path) == 'python' else JS_CONSTANT
    module = str(PurePosixPath(path).with_suffix(''))
    out = []
    for match in pattern.finditer(text):
        name, line = match.group(1), text.count('\n', 0, match.start()) + 1
        if not scope['judged'](name): continue
        count, tests = scope['refs'].outside(name, path, (line, line))
        if count: continue
        out.append(_finding('unread-constant', path, line, name,
                            f'constant `{module}.{name}` is never read' + (f' outside tests ({", ".join(tests[:3])})' if tests else ''),
                            'symbol', f'the name occurs nowhere in product code or configuration except line {line}', scope['sha'], tests))
    return out



def _symbol_findings(symbols, scope):
    """Unused functions and classes, then unread constants, outside dead modules and the files read whole."""
    facts = [found for fact in symbols if fact.get('kind') == 'symbol' and (found := _symbol_finding(fact, scope))]
    for path in sorted(scope['code'] - scope['dead_modules'] - scope['skipped']):
        if _candidate_file(path): facts += _constant_findings(path, scope)
    return facts


def run(target, source, symbols=None, resolved=None, entry_points=None, **options):
    known = {item['path'] for item in source.readable()}
    code = {path for path in known if language_of(path) in ('python', 'javascript', 'typescript', 'tsx')}
    refs = References(source)
    texts = refs.texts_of(code)
    seeds, reached, whole, test_importers = _walk(source, known, texts, resolved or [], entry_points or [])
    fixtures = _rule_fixtures(code, texts)
    sha = source.content_fingerprint
    # With no production entry point, nothing says who uses the code: a library's public names serve callers
    # outside the snapshot. Then only what is private by convention (`_name`) is judged, and no module is.
    judged = (lambda name: True) if seeds else (lambda name: name.startswith('_'))
    unreachable = _unreachable(code, seeds, reached, fixtures)
    scope = {'code': code, 'dead_modules': set(unreachable), 'skipped': whole | fixtures, 'judged': judged, 'refs': refs, 'sha': sha}
    facts = [_module_finding(path, test_importers, seeds, sha) for path in unreachable] + _symbol_findings(symbols or [], scope)
    summary = {'production_entry_points': len(seeds), 'modules_reached': len(reached & code), 'code_modules': len(code),
               'unreachable_modules': len(unreachable), **_symbol_counts(facts),
               'evaluated_kinds': {'eaos': {'dead_code': {'status': 'observed', 'granularity': 'symbol'}}}}
    return {'facts': facts, 'summary': summary, 'available': True, 'input_sha': sha, 'reason': None}


def _rule_fixtures(code, texts):
    """The semgrep rule tests: each a fixture for its rule, never a candidate."""
    return {path for path in code if RULE_FIXTURE.search(texts.get(path) or '')}


def _unreachable(code, seeds, reached, fixtures):
    """The candidate modules no production entry point reaches; none when there is no entry point to judge from."""
    return sorted(path for path in code if seeds and path not in reached and path not in fixtures and _candidate_file(path))


def _symbol_counts(facts):
    """How many unused symbols and unread constants the findings hold."""
    return {'unused_symbols': sum(f['value']['rule'] == 'unused-symbol' for f in facts),
            'unread_constants': sum(f['value']['rule'] == 'unread-constant' for f in facts)}


def adjudicate(findings, source, own=()):
    """One verdict per dead-code candidate from any engine, written into value.adjudication.

    confirmed    EAOS's own detector reports the same file and name
    refuted      the name is referenced outside its definition in product text, or held in a registry
    not_a_symbol the finding names no function, class, constant or module (a marker, a comment)
    unconfirmed  none of the above: the engine's word alone
    The engine's own fields are left as it wrote them.
    """
    refs = References(source)
    ours = {((f.get('location') or {}).get('path'), (f.get('location') or {}).get('symbol')) for f in own}
    for fact in findings:
        value = fact.get('value') or {}
        if fact.get('kind') != 'engine_finding' or value.get('kind') != 'dead_code' or value.get('engine') == 'eaos': continue
        location = fact.get('location') or {}
        value['adjudication'] = _verdict(value, location, _candidate_name(value, location), ours, refs)
    return findings


def _candidate_name(value, location):
    """The bare name an engine's dead-code finding is about: its symbol, else the first name its message quotes; a
    module's is its path. Engines write a symbol their own way (vulture `a/b.py:act`, knip `a/b.js:name`, enola
    `a/b.name`): read as one dotted name, `py:act` named nothing and every vulture finding was thrown away (M2.3)."""
    path, symbol = location.get('path'), location.get('symbol')
    name = (symbol if symbol and symbol != path else None) or _quoted_name(value.get('message') or '')
    if not name or name == path: return name
    if name.startswith(f'{path}:'): name = name[len(path):].lstrip(':')
    return name.rsplit('.', 1)[-1].rsplit('/', 1)[-1]


def _quoted_name(message):
    """The first name a message quotes: after function, method or class, or between backquotes; None otherwise."""
    qualified = re.search(r'(?:function|method|class)\s+`?([\w./$-]+)`?|`([\w./$-]+)`', message)
    return next(g for g in qualified.groups() if g) if qualified else None


def _span(location):
    """(first, last) line a finding's location covers; the last is the first when it gives none."""
    return location.get('start_line') or 1, location.get('end_line') or location.get('start_line') or 0


def _verdict(value, location, name, ours, refs):
    path = location.get('path')
    if name and name == path:
        # A module: EAOS's own reachability (unreachable-module) is the second witness, or there is none.
        return ({'verdict': 'confirmed', 'reason': 'EAOS finds no production entry point that reaches it either'} if (path, path) in ours
                else {'verdict': 'unconfirmed', 'reason': 'the engine alone reports it'})
    if not name or not TOKEN.fullmatch(name):
        return {'verdict': 'not_a_symbol', 'reason': 'the finding names no symbol or module'}
    if value.get('referenced_by_registry'):
        return {'verdict': 'refuted', 'reason': 'held in a registry the import graph cannot see'}
    if (path, name) in ours:
        return {'verdict': 'confirmed', 'reason': 'EAOS finds no reference outside its definition either'}
    count, _ = refs.outside(name, path, _span(location))
    if count: return {'verdict': 'refuted', 'reason': f'the name occurs {count} time(s) in product text outside its definition'}
    return {'verdict': 'unconfirmed', 'reason': 'the engine alone reports it'}
