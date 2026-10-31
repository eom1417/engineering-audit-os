"""What EAOS promises its outside users holds: the CLI and MCP tools as declared, how they answer, and saved projects still
read. A break is refused unless the maintainers agreed to it; an addition is recorded; words and values are not held here.
The comparison is proved here on every run; tools/public_contract/mutations.py proves it on the real code."""
import copy
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools' / 'public_contract'))
import capture as captured  # noqa: E402  (developer tools, beside the tests' reach)
import lock as contract  # noqa: E402


def _argument(snapshot, command, flag):
    return next(row for row in snapshot['cli'][command] if flag in row['flags'])


def _new_argument(snapshot, required):
    snapshot['cli']['audit'].append({'dest': 'more', 'flags': ['--more'], 'nargs': None, 'default': None, 'choices': None,
                                     'required': required, 'kind': 'StoreAction', 'type': None})


def _new_parameter(snapshot, required):
    tool = snapshot['mcp']['tools']['fix_skip']['input']
    tool['properties']['more'] = {'type': 'string'}
    if required: tool['required'].append('more')


def _set(row, **values):
    row.update(values)


TOOLS = lambda s: s['mcp']['tools']  # noqa: E731
STATUS = lambda s: s['behaviour']['empty:mcp:status']  # noqa: E731
# What takes from a caller who relies on it today, and the words that must say so.
BREAKS = (
    ('a tool removed', lambda s: TOOLS(s).pop('fix_skip'), 'MCP tool fix_skip removed'),
    ('a prompt removed', lambda s: s['mcp']['prompts'].remove('audit'), 'MCP prompt audit removed'),
    ('a parameter removed', lambda s: TOOLS(s)['fix_skip']['input']['properties'].pop('project'), 'fix_skip: parameter project removed'),
    ('a required parameter added', lambda s: _new_parameter(s, True), 'fix_skip: new required parameter more'),
    ('an optional parameter made required', lambda s: TOOLS(s)['status']['input'].setdefault('required', []).append('project'), 'status.project: optional became required'),
    ('a parameter narrowed', lambda s: _set(TOOLS(s)['status']['input']['properties']['project'], anyOf=[{'type': 'string'}]), 'status.project: kind narrowed'),
    ('a parameter default changed', lambda s: _set(TOOLS(s)['status']['input']['properties']['project'], default='.'), 'status.project: default changed'),
    ('values taken from a parameter', lambda s: _set(TOOLS(s)['status']['input']['properties']['project'], anyOf=[{'type': 'string', 'enum': ['one']}, {'type': 'null'}]), 'status.project: fewer values accepted'),
    ('a read-only tool now writes', lambda s: _set(TOOLS(s)['status']['annotations'], read_only_hint=False), 'status: read_only_hint changed'),
    ('a writing tool called read-only', lambda s: _set(TOOLS(s)['fix_skip']['annotations'], read_only_hint=True), 'fix_skip: read_only_hint changed'),
    ('a command removed', lambda s: s['cli'].pop('facts'), 'CLI command facts removed'),
    ('an argument removed', lambda s: s['cli']['audit'].remove(_argument(s, 'audit', '--goal')), 'audit: argument --goal removed'),
    ('a required argument added', lambda s: _new_argument(s, True), 'audit: new required argument --more'),
    ('an argument made required', lambda s: _set(_argument(s, 'audit', '--goal'), required=True), 'audit --goal: became required'),
    ('an argument default changed', lambda s: _set(_argument(s, 'audit', '--lang'), default='en'), 'audit --lang: default changed'),
    ('a choice removed', lambda s: _argument(s, 'audit', '--goal')['choices'].remove('debugging'), 'audit --goal: fewer choices accepted'),
    ('an argument changed its form', lambda s: _set(_argument(s, 'audit', '--goal'), nargs='+'), 'audit --goal: nargs changed'),
    ('a key gone from an answer', lambda s: STATUS(s).pop('next'), 'empty:mcp:status: answer lost next'),
    ('a key of another kind', lambda s: _set(STATUS(s), checked='str'), 'empty:mcp:status.checked: "bool" became "str"'),
    ('an exit code changed', lambda s: _set(s['behaviour']['empty:cli:nosuch'], exit='1'), 'empty:cli:nosuch.exit: "2" became "1"'),
    ('a case no longer answered', lambda s: s['behaviour'].pop('empty:cli:nosuch'), 'empty:cli:nosuch: no longer answered'),
    ('a saved project read and written', lambda s: _set(s['behaviour']['saved-0.0.90:reading-leaves-the-state'], unchanged='no'), 'reading-leaves-the-state.unchanged'),
)
ADDITIONS = (
    ('a tool', lambda s: _set(TOOLS(s), brand_new=copy.deepcopy(TOOLS(s)['status'])), 'MCP tool brand_new added'),
    ('a prompt', lambda s: s['mcp']['prompts'].append('more'), 'MCP prompt more added'),
    ('an optional parameter', lambda s: _new_parameter(s, False), 'fix_skip: new optional parameter more'),
    ('a parameter that now says less', lambda s: TOOLS(s)['fix_skip']['input']['required'].remove('reason'), 'fix_skip.reason: required became optional'),
    ('a command', lambda s: _set(s['cli'], more=[]), 'CLI command more added'),
    ('an optional argument', lambda s: _new_argument(s, False), 'audit: new optional argument --more'),
    ('a choice', lambda s: _argument(s, 'audit', '--goal')['choices'].append('extra'), 'audit --goal: more choices accepted'),
    ('a key in an answer', lambda s: _set(STATUS(s), extra='int'), 'empty:mcp:status: answer gained extra'),
    ('a behaviour case', lambda s: _set(s['behaviour'], another={'exit': '0'}), 'another: new case'),
)


class Comparison(unittest.TestCase):
    """Each deliberate change is called what it is, on the real lock."""

    @classmethod
    def setUpClass(cls):
        cls.lock = contract.load()

    def changed(self, mutate):
        new = copy.deepcopy(self.lock)
        mutate(new)
        return contract.compare(self.lock, new)

    def test_what_takes_from_a_caller_is_a_break(self):
        for name, mutate, words in BREAKS:
            with self.subTest(name):
                self.assertTrue(any(words in line for line in self.changed(mutate)[0]), words)

    def test_what_only_adds_is_an_addition_and_never_a_break(self):
        for name, mutate, words in ADDITIONS:
            with self.subTest(name):
                breaks, additions = self.changed(mutate)
                self.assertEqual(breaks, [])
                self.assertTrue(any(words in line for line in additions), words)

    def test_words_are_not_the_contract(self):
        self.assertEqual(self.changed(lambda s: _set(TOOLS(s)['status']['input']['properties']['project'], title='Another')), ([], []))


class TheLock(unittest.TestCase):
    """The code as it stands against the lock: a break fails, an addition asks to be recorded."""

    def test_the_code_keeps_what_the_lock_promises_and_the_lock_is_current(self):
        breaks, additions = contract.compare(contract.load(), contract.capture())
        self.assertEqual(breaks, [], 'this takes from callers: restore it, or the maintainers agree and tools/public_contract/lock.py --accept-break')
        self.assertEqual(additions, [], 'new and allowed: record it with python tools/public_contract/lock.py --record')

    def test_every_break_accepted_says_why_who_agreed_and_is_in_the_changelog(self):
        changelog = (ROOT / 'CHANGELOG.md').read_text(encoding='utf-8')
        for row in contract.accepted():
            with self.subTest(row['why']):
                self.assertTrue(row['why'] and row['approved_by'] and row['breaks'])
                self.assertIn(row['why'], changelog)

    def test_a_saved_project_is_read_and_its_state_left_as_it_was(self):
        behaviour = contract.load()['behaviour']
        frozen = sorted(path.name for path in captured.SAVED.iterdir() if path.name[0].isdigit())
        self.assertIn('0.0.90', frozen, 'a frozen project stays, so every later version must read it')
        for version in frozen:
            self.assertEqual(behaviour[f'saved-{version}:reading-leaves-the-state'], {'unchanged': 'yes'})
            self.assertIn('findings', behaviour[f'saved-{version}:mcp:findings'], 'the saved check still reads as a check')


class Recording(unittest.TestCase):
    """The lock is the one thing that could hide a break, so writing it is what is refused."""

    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.lock = Path(scratch.name) / 'lock'
        self.old = contract.load()
        contract.write(self.old, self.lock)
        self.broken = copy.deepcopy(self.old)
        self.broken['mcp']['tools'].pop('fix_skip')

    def test_record_refuses_a_break_and_leaves_the_lock_as_it_was(self):
        with self.assertRaises(contract.Refused):
            contract.record(self.broken, self.lock)
        self.assertIn('fix_skip', contract.load(self.lock)['mcp']['tools'])

    def test_record_takes_an_addition(self):
        added = copy.deepcopy(self.old)
        added['mcp']['prompts'].append('more')
        contract.record(added, self.lock)
        self.assertIn('more', contract.load(self.lock)['mcp']['prompts'])

    def test_a_break_needs_its_reason_and_who_approved_it_and_is_kept_with_them(self):
        for why, approved_by in (('', 'someone'), ('a reason', ''), (None, None), ('  ', '  ')):
            with self.assertRaises(contract.Refused):
                contract.accept_break(self.broken, why, approved_by, self.lock)
        self.assertEqual(contract.accepted(self.lock), [])
        contract.accept_break(self.broken, 'a reason', 'someone', self.lock)
        kept = contract.accepted(self.lock)[0]
        self.assertEqual((kept['why'], kept['approved_by']), ('a reason', 'someone'))
        self.assertIn('MCP tool fix_skip removed', kept['breaks'])
        self.assertNotIn('fix_skip', contract.load(self.lock)['mcp']['tools'])

    def test_nothing_to_accept_when_nothing_breaks(self):
        with self.assertRaises(contract.Refused):
            contract.accept_break(self.old, 'a reason', 'someone', self.lock)


class EveryToolAccountedFor(unittest.TestCase):
    """A new tool cannot slip past the lock: it is called, or the reason it is not is written, and a named test is real."""

    def setUp(self):
        self.lock = contract.load()

    def test_every_tool_says_how_it_is_held_and_a_called_one_is_in_the_lock(self):
        self.assertEqual(set(self.lock['accounting']), set(self.lock['mcp']['tools']))
        for name, how in self.lock['accounting'].items():
            with self.subTest(name):
                self.assertFalse(how.startswith('UNACCOUNTED'), how)
                if how.startswith('called'): self.assertTrue({f'empty:mcp:{name}', f'empty:writing:{name}'} & set(self.lock['behaviour']))

    def test_a_tool_that_says_nothing_cannot_be_recorded(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        contract.write(self.lock, Path(scratch.name))
        new = copy.deepcopy(self.lock)
        new['accounting']['brand_new'] = captured.UNACCOUNTED
        with self.assertRaises(contract.Refused):
            contract.record(new, Path(scratch.name))

    def test_an_accepted_break_cannot_bring_in_a_tool_that_says_nothing(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        lock = Path(scratch.name)
        contract.write(self.lock, lock)
        new = copy.deepcopy(self.lock)
        new['mcp']['tools'].pop('fix_skip')
        new['mcp']['tools']['brand_new'] = copy.deepcopy(new['mcp']['tools']['status'])
        new['accounting']['brand_new'] = captured.UNACCOUNTED
        with self.assertRaises(contract.Refused):
            contract.accept_break(new, 'a reason', 'someone', lock)
        self.assertIn('fix_skip', contract.load(lock)['mcp']['tools'])
        self.assertNotIn('brand_new', contract.load(lock)['accounting'])
        self.assertEqual(contract.accepted(lock), [])

    def test_a_test_named_for_a_writing_tool_exists_and_drives_it(self):
        for name, how in self.lock['accounting'].items():
            if not how.startswith('tests/'): continue
            with self.subTest(name):
                self.assertIn(name, (ROOT / how).read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
