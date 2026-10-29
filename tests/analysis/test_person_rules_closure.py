"""M16's closure (2026-10-29): four cases an owner's review named, each reproduced before its fix. A rule and its
contradiction are never one rule; new words never keep an old guard as their protection; a commit is judged on what it
holds (the index, deletions included); an assistant's test command never runs before the person approves it."""
import os
import subprocess
import sys
from pathlib import Path
from unittest import mock

from tests.shared_fixture import Workspace

from eaos.analysis.rules import changed, guards, held
from eaos.core.project import rules as registry

SOUND, BROKEN = 'module.exports = a => Number(a).toFixed(2);\n', 'module.exports = a => String(a);\n'
CHECK = "const t = require('./total'); if (t(3) !== '3.00') { console.log('total.js:1 wrong'); process.exit(1); }\n"


def git(folder, *args):
    return subprocess.run(['git', '-C', str(folder), *args], capture_output=True, text=True)


class Closure(Workspace):
    def setUp(self):
        super().setUp()
        patcher = mock.patch.dict(os.environ, {'EAOS_HOME': str(Path(self.tmp) / 'home')})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.project = Path(self.tmp) / 'app'
        self.project.mkdir()
        (self.project / 'total.js').write_text(SOUND)
        (self.project / 'check.js').write_text(CHECK)
        git(self.tmp, 'init', '-q', str(self.project))
        for key, value in (('user.name', 't'), ('user.email', 't@t')): git(self.project, 'config', key, value)
        git(self.project, 'add', '-A')
        git(self.project, 'commit', '-qm', 'init')

    def totals_rule(self):
        registry.add(self.project, 'Totals keep two decimals', 'terminal', scope={'kind': 'pinned'})
        registry.guard(self.project, 'R1', guards.checked({'kind': 'test', 'command': ['node', 'check.js']}), 'person', 'terminal')
        return registry.holding(self.project, {})


class Contradictions(Closure):
    def test_a_rule_and_its_contradiction_stay_two_rules_and_a_plain_repeat_is_one(self):
        apart = [('البيانات تحفظ في قاعدة البيانات فقط', 'البيانات لا تحفظ في قاعدة البيانات فقط'),
                 ('Data is saved in the database only', 'Data is never saved in the database only'),
                 ('Prices come from the prices table on the admin pages', 'Prices come from the prices table on the public pages'),
                 ('A page shows at most 20 rows', 'A page shows at most 50 rows')]
        for first, second in apart: self.assertFalse(registry.alike(first, second), (first, second))
        same = [('البيانات تعيش في قاعدة البيانات بس، لا تكتب سجلات', 'البيانات تعيش في قاعدة البيانات بس! لا تكتب سجلات'),
                ('Never send the whole state on every save', 'never send the whole state on every save, please.')]
        for first, second in same: self.assertTrue(registry.alike(first, second), (first, second))
        registry.add(self.project, apart[0][0], 'chat')
        rule, before = registry.add(self.project, apart[0][1], 'chat')
        self.assertEqual((rule['id'], before, rule['near']), ('R2', 0, ['R1']), 'kept apart, and said to look like R1')


class NewWords(Closure):
    def test_new_words_never_keep_an_old_guard_as_their_protection_until_it_is_written_again_or_kept(self):
        rules = self.totals_rule()
        registry.change(self.project, 'R1', words='Totals keep two decimals, please.')      # the same rule: no cost
        self.assertIsNone(registry.find(registry.load(self.project), 'R1').get('pending'))
        registry.change(self.project, 'R1', words='Totals keep three decimals')
        rule = registry.find(registry.load(self.project), 'R1')
        self.assertEqual((rule['pending'], registry.in_force(rule)['kind']), ('words', 'none'))
        self.assertEqual(rule['history'][-1]['was']['guard']['command'], ['node', 'check.js'], 'the earlier guard kept in its history')
        (self.project / 'total.js').write_text(BROKEN)
        result = held.in_check(registry.holding(self.project, {}), self.project)[0]
        self.assertEqual((result['status'], result['waiting']), ('unguarded', 'words'), 'not run, never called held')
        registry.confirm(self.project, 'R1')
        self.assertEqual(held.in_check(registry.holding(self.project, {}), self.project)[0]['status'], 'broken')
        self.assertTrue(rules)


class WhatACommitHolds(Closure):
    def test_a_fix_left_unstaged_never_hides_a_staged_break_and_an_unstaged_break_never_refuses_a_sound_commit(self):
        rules = self.totals_rule()
        (self.project / 'total.js').write_text(BROKEN)
        git(self.project, 'add', 'total.js')
        (self.project / 'total.js').write_text(SOUND + '// fixed, not staged\n')
        self.assertTrue(changed.check(self.project, rules, staged=True, gates=False)['refused'])
        self.assertEqual((self.project / 'total.js').read_text(), SOUND + '// fixed, not staged\n', 'the working tree untouched')
        (self.project / 'total.js').write_text(SOUND + '// tidy\n')
        git(self.project, 'add', 'total.js')
        (self.project / 'total.js').write_text(BROKEN)
        self.assertFalse(changed.check(self.project, rules, staged=True, gates=False)['refused'])

    def test_a_staged_deletion_is_a_change_and_is_checked(self):
        rules = self.totals_rule()
        git(self.project, 'rm', '-q', 'total.js')
        found = changed.check(self.project, rules, staged=True, gates=False)
        self.assertEqual((found['changed'], found['refused']), (['total.js'], True))


class AssistantsCommands(Closure):
    def test_a_test_command_an_assistant_proposes_never_runs_before_the_person_approves_it(self):
        from eaos.interfaces.mcp_server import rules as tools
        marker = Path(self.tmp) / 'ran'
        registry.add(self.project, 'Totals keep two decimals', 'mcp', scope={'kind': 'pinned'})
        command = [sys.executable, '-c', f"open({str(marker)!r}, 'w').write('x')"]
        tools.rule('guard', id='R1', guard={'kind': 'test', 'command': command}, project=str(self.project))
        (self.project / 'total.js').write_text(BROKEN)
        held.in_check(registry.holding(self.project, {}), self.project)
        changed.check(self.project, registry.holding(self.project, {}), gates=False)
        self.assertFalse(marker.exists(), 'saved, checked and changed: never run')
        self.assertEqual(tools.rule('approve', id='R1', project=str(self.project))['status'], 'needs_the_person')
        with mock.patch.dict(os.environ, {'EAOS_STUDIO_RUN': 'r1'}), self.assertRaises(PermissionError):
            tools.rule('approve', id='R1', person_agreed=True, project=str(self.project))
        self.assertFalse(marker.exists())
        tools.rule('approve', id='R1', person_agreed=True, project=str(self.project))
        self.assertTrue(marker.exists(), 'approved by the person: it runs')

    def test_a_test_command_the_person_gives_runs_at_once(self):
        rules = self.totals_rule()
        self.assertIsNone(rules[0].get('pending'))
