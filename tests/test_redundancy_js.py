"""Redundant data work in JavaScript and TypeScript, judged from the recorded loops, calls and data accesses."""
from shared_fixture import Workspace

from eaos.facts.redundancy import _index_js, _js_redundancies

PATH = 'src/services/orders.ts'


def at(fact_kind, start, end=None, **value):
    return {'kind': fact_kind, 'location': {'path': PATH, 'start_line': start, 'end_line': end or start, 'symbol': value.pop('symbol', None)},
            'value': value}


def access(line, target='orders', operation='select'):
    return {'kind': 'data_access', 'location': {'path': PATH, 'start_line': line},
            'value': {'client': 'supabase', 'target': target, 'operation': operation}}


class JsRedundancyTests(Workspace):
    def rows(self, structure, accesses, text=''):
        index = _index_js(structure, accesses)
        return _js_redundancies(PATH, index[PATH], text)

    def test_a_query_inside_a_for_loop_or_an_iterating_callback_is_n_plus_one(self):
        structure = [at('scope', 1, 30, kind='function', symbol='load'), at('loop', 3, 6, kind='for'),
                     at('call_site', 10, 14, callee='map')]
        rows = self.rows(structure, [access(4), access(12, 'items'), access(20)])
        self.assertEqual([(r['kind'], r['start_line']) for r in rows], [('n_plus_one', 4), ('n_plus_one', 12)])
        self.assertEqual(rows[0]['symbol'], 'load')

    def test_a_one_line_chain_is_not_a_loop_around_its_own_query(self):
        structure = [at('call_site', 5, 5, callee='filter')]
        self.assertEqual(self.rows(structure, [access(5)]), [])

    def test_a_fetch_counts_as_data_access(self):
        structure = [at('loop', 2, 4, kind='for'), at('call_site', 3, callee='fetch')]
        self.assertEqual([r['callee'] for r in self.rows(structure, [])], ['http.get fetch'])

    def test_the_same_read_twice_on_one_path_is_repeated(self):
        structure = [at('scope', 1, 20, kind='function', symbol='load')]
        text = '\n'.join(['function load() {', '  const a = read();', '  log(a);', '  const b = read();', '}'])
        rows = self.rows(structure, [access(2), access(4)], text)
        self.assertEqual([(r['kind'], r['start_line'], r['end_line']) for r in rows], [('repeated_call', 2, 4)])

    def test_reads_in_alternative_arms_or_a_fallback_are_not_repeated(self):
        structure = [at('scope', 1, 20, kind='function', symbol='load')]
        for between in ('  } else if (y) {', '  } catch (err) {', '  if (x) return a;', '    case 2:'):
            text = '\n'.join(['function load() {', '  const a = read();', between, '  const b = read();', '}'])
            self.assertEqual(self.rows(structure, [access(2), access(4)], text), [], between)

    def test_without_the_facts_a_typescript_file_is_blocked_not_clean(self):
        from unittest import mock
        from eaos.facts import redundancy
        source = mock.Mock()
        source.readable.return_value = [{'path': 'a.ts'}]
        source.text.return_value = 'export const a = 1;\n'
        blocked = redundancy.run(self.tmp, source, symbols=[])
        observed = redundancy.run(self.tmp, source, symbols=[], structure=[], entrypoints=[])
        self.assertEqual((blocked['summary']['files_blocked'], blocked['summary']['files_observed']), (1, 0))
        self.assertEqual((observed['summary']['files_blocked'], observed['summary']['files_observed']), (0, 1))
