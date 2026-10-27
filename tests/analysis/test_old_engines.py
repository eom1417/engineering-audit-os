"""Old engines still wired in (M13): switches fixed to one value, two engines doing one job, code that never ran."""
import json
import unittest
from pathlib import Path

from eaos.analysis.assessments import never_run, old_engines
from eaos.analysis.claims import from_old_engines
from eaos.engines.code import ast_grep
from eaos.facts.run import collect, read_available
from eaos.live.testing import ran
from shared_fixture import scratch

APP = {
    'src/engine.js': """export const USE_LEGACY = false;
const SHOW = true;
export function generate(month) {
  if (USE_LEGACY) { return legacyGenerate(month); }
  if (SHOW) console.log(month);
  return freshGenerate(month);
}
function legacyGenerate(month) { return [month]; }
function freshGenerate(month) { return []; }
function helper() { const OFF = false; if (OFF) { return sharedStep(); } return 1; }
function sharedStep() { return 2; }
export function other() { return sharedStep() + helper(); }
""",
    'src/flags.js': "export const DEBUG = process.env.DEBUG === '1';\nexport function log(x) { if (DEBUG) { trace(x); } }\nfunction trace(x) { return x; }\n",
    'src/report.js': "export function totalV1(rows) { return rows.length; }\nexport function totalV2(rows) { return rows.length; }\n"
                     "export function report(rows) { return totalV1(rows) + totalV2(rows); }\nexport function token() { return 1; }\n"
                     "export function newToken() { return token(); }\n",
    'app/export.py': "import json\nUSE_OLD_EXPORT = False\n\n\ndef old_export(state):\n    return json.dumps(state)\n\n\n"
                     "def export(state):\n    if USE_OLD_EXPORT:\n        return old_export(state)\n    return json.dumps(state, indent=0)\n",
}


class TheCode(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if ast_grep.version() != ast_grep.PINNED: raise unittest.SkipTest('ast-grep is not installed at its pin')
        cls.root, out = Path(scratch('eaos-old-')), Path(scratch('eaos-old-facts-'))
        for path, text in APP.items():
            (cls.root / path).parent.mkdir(parents=True, exist_ok=True)
            (cls.root / path).write_text(text, encoding='utf-8')
        collect(cls.root, out, engines=['ast-grep'])
        cls.sets, cls.out = read_available(out), out

    def test_a_switch_fixed_off_closes_its_branch_and_the_function_only_it_calls_is_an_old_engine(self):
        rows = {(r['path'], r['switch']): r for r in old_engines.switched_off(self.sets, self.root)}
        js, py = rows[('src/engine.js', 'USE_LEGACY')], rows[('app/export.py', 'USE_OLD_EXPORT')]
        self.assertEqual(([e['name'] for e in js['engines']], js['replaced_by']), (['legacyGenerate'], ['freshGenerate']))
        self.assertEqual([e['name'] for e in py['engines']], ['old_export'])

    def test_what_must_stay_is_left_a_switch_read_from_the_environment_one_on_a_local_and_a_function_called_elsewhere(self):
        found = old_engines.switched_off(self.sets, self.root)
        self.assertFalse({r['switch'] for r in found} & {'DEBUG', 'SHOW', 'OFF'}, found)
        self.assertNotIn('sharedStep', {e['name'] for r in found for e in r['engines']})

    def test_two_engines_are_a_version_apart_in_one_place_and_a_name_s_meaning_is_no_marker(self):
        pairs = [(r['old'], r['new']) for r in old_engines.two_engines(self.sets)]
        self.assertIn(('totalV1', 'totalV2'), pairs)
        self.assertNotIn(('token', 'newToken'), pairs)                         # `new` there is the name's meaning

    def test_each_is_one_card_in_both_languages_whose_probe_closes_it_when_the_code_no_longer_shows_it(self):
        claims = from_old_engines.old_engine_claims(self.out, self.sets, self.root, 0)
        kinds = sorted(c['render']['params']['kind'] for c in claims)
        self.assertEqual(kinds, ['switched_off', 'switched_off', 'two_engines'])
        card = next(c for c in claims if c['render']['params'].get('switch') == 'USE_LEGACY')
        self.assertIn('replaced by freshGenerate', card['statement']); self.assertIn('محرك قديم', card['render']['params']['ar'])
        spec = card['probe_spec']['specification']
        self.assertEqual(from_old_engines.present(spec, self.sets)[0], 'CONFIRMED')
        self.assertEqual(from_old_engines.present(spec, {'external': {'facts': []}, 'syntax': self.sets['syntax']})[0], 'REFUTED')


def symbol(path, name, line, end):
    return {'id': f'S-{name}', 'kind': 'symbol', 'location': {'path': path, 'start_line': line, 'end_line': end},
            'value': {'name': name, 'kind': 'function', 'signature': {'parameters': []}}}


class WhatRan(unittest.TestCase):
    def test_a_function_never_run_in_a_file_that_ran_and_a_reached_module_no_run_read_are_suspects(self):
        out = Path(scratch('eaos-ran-'))
        ran.record(out, 'server', {'src/a.js': {'ran': ['go'], 'never': ['old']}})
        ran.record(out, 'tests', {'app/b.py': {'lines': [[2, 3]]}})
        sets = {'syntax': {'facts': [symbol('src/a.js', 'go', 1, 3), symbol('src/a.js', 'old', 4, 6),
                                     symbol('app/b.py', 'used', 1, 3), symbol('app/b.py', 'unused', 5, 8)]},
                'graph': {'facts': [{'id': 'G1', 'kind': 'graph_node', 'location': {'path': 'src/c.js'},
                                     'value': {'entry_distance': 1, 'depends_on': []}},
                                    {'id': 'G2', 'kind': 'graph_node', 'location': {'path': 'src/a.js'},
                                     'value': {'entry_distance': 0, 'depends_on': ['src/c.js']}}]}}
        found = never_run.records(out)
        self.assertEqual(never_run.never_run_functions(sets, found),
                         {'app/b.py': {'never': ['unused'], 'around': ['used']}, 'src/a.js': {'never': ['old'], 'around': ['go']}})
        self.assertEqual(never_run.never_run_modules(sets, found), [{'path': 'src/c.js', 'around': ['src/a.js']}])

    def test_coverage_is_read_as_the_project_s_own_functions_and_lines(self):
        root = Path(scratch('eaos-ran-root-'))
        (root / 'src').mkdir(); (root / 'src/App.jsx').write_text('x', encoding='utf-8')
        v8 = Path(scratch('eaos-v8-'))
        script = lambda url, name, count: {'url': url, 'functions': [{'functionName': name, 'ranges': [{'count': count}]}]}
        (v8 / 'cov.json').write_text(json.dumps({'result': [script(f'file://{root}/src/App.jsx', 'go', 1),
                                                            script(f'file://{root}/node_modules/x/i.js', 'lib', 1)]}), encoding='utf-8')
        self.assertEqual(ran.merged(ran.v8(v8, root)), {'src/App.jsx': {'ran': ['go'], 'never': []}})
        page = ran.browser([script('http://127.0.0.1:5173/src/App.jsx?t=1', 'draw', 0), script('http://127.0.0.1:5173/assets/i.js', 'x', 1)], root)
        self.assertEqual(ran.merged(page), {'src/App.jsx': {'ran': [], 'never': ['draw']}})
        self.assertEqual(ran._numbits(bytes([0b110, 0b1])), {1, 2, 8})


if __name__ == '__main__':
    unittest.main()
