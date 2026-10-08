"""Supabase client calls must be reported as data_access facts; a non-Supabase .from must not.

The detector does not guess: it matches only chains whose name contains `supabase`. A custom data
layer using `.from(...)` without that name is ignored, so the ledger stays clean.
"""
import unittest

from eaos.facts.frameworks import supabase_access


SOURCE = """\
const supabase = createClient(URL, KEY);

async function readUsers() {
  const { data, error } = await supabase.from("users").select("id, name");
}

async function logEvent() {
  await supabase.from("imports").insert({ kind: "click" });
}

async function runReport() {
  const { data } = await supabase.rpc("daily_report", { since: "2026-01-01" });
}

async function uploadAvatar(file) {
  const { error } = await supabase.storage.from("avatars").upload("p.png", file);
}

async function custom() {
  // Not a Supabase client: an unrelated SDK with a similar surface.
  await myClient.from("things").select("*");
}
"""


class SupabaseAccessDetectionTests(unittest.TestCase):
    """The detector must report each Supabase call with the right client, target and operation,
    and must not be tricked into reporting a non-Supabase call that uses the same verbs."""

    def test_each_of_the_four_supabase_call_shapes_is_reported_once(self):
        calls = list(supabase_access.extract_calls(SOURCE))
        operations = sorted(record['operation'] for _, _, record in calls)
        self.assertEqual(operations, ['insert', 'rpc', 'select', 'storage'])

    def test_each_record_carries_the_real_target_and_operation(self):
        records = {(record['symbol'], record['operation']): record for _, _, record in supabase_access.extract_calls(SOURCE)}
        self.assertEqual(records[('from', 'select')]['target'], 'users')
        self.assertEqual(records[('from', 'select')]['client'], 'supabase')
        self.assertEqual(records[('from', 'insert')]['target'], 'imports')
        self.assertEqual(records[('rpc', 'rpc')]['target'], 'daily_report')
        self.assertEqual(records[('storage', 'storage')]['target'], 'avatars')

    def test_a_written_row_gives_its_columns(self):
        records = [r for _, _, r in supabase_access.extract_calls(
            "supabase.from('vehicles').insert([{ plate, vin: v }]);\nsupabase.from('vehicles').update(row).eq('id', 1);\n")]
        self.assertEqual([(r['operation'], r.get('keys')) for r in records], [('insert', ['plate', 'vin']), ('update', None)])

    def test_a_non_supabase_chain_is_not_a_supabase_call(self):
        # myClient.from('things').select('*') sits inside the same source; the detector
        # must report four facts, not five.
        calls = list(supabase_access.extract_calls(SOURCE))
        self.assertEqual(len(calls), 4, [record for _, _, record in calls])

    def test_a_storage_call_is_not_also_a_table_call(self):
        # `.storage.from("avatars")` ends in `.from(...)`; without guarding against the storage
        # prefix, the table-call matcher would emit a second fact for the same site.
        records = [record for _, _, record in supabase_access.extract_calls(SOURCE)
                   if record['target'] == 'avatars']
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]['operation'], 'storage')

    def test_auth_calls_are_reported_separately(self):
        source = 'await supabase.auth.signOut();'
        calls = list(supabase_access.extract_calls(source))
        self.assertEqual(len(calls), 1)
        _, _, record = calls[0]
        self.assertEqual(record['operation'], 'signOut')
        self.assertEqual(record['target'], 'auth')
        self.assertEqual(record['symbol'], 'auth')

    def test_supabase_property_access_is_accepted(self):
        # `context.supabase.from(...)` is the real-world shape used by finance-os.
        source = 'await context.supabase.from("movements").insert({});'
        calls = list(supabase_access.extract_calls(source))
        self.assertEqual(len(calls), 1)
        _, _, record = calls[0]
        self.assertEqual(record['target'], 'movements')
        self.assertEqual(record['operation'], 'insert')

    def test_lines_are_one_based(self):
        source = 'const x = 1;\nawait supabase.from("t").select("*");'
        calls = list(supabase_access.extract_calls(source))
        self.assertEqual(calls[0][1], 2)


    def test_a_supabase_mention_in_an_unrelated_statement_does_not_make_a_non_supabase_chain_match(self):
        # The earlier change made the prefix walk back only as far as the previous `;` (or
        # `{`, `}`, `=`). A `supabase = setup();` declaration that ended at `;` cannot leak the
        # name forward into the next statement, so `myClient.from(...)` following it stays
        # a non-Supabase chain.
        source = ('const supabase = setup();\n'
                  'myClient.from("x").select("*");\n')
        calls = list(supabase_access.extract_calls(source))
        self.assertEqual(calls, [])

    def test_a_supabase_mention_in_an_unrelated_braced_block_does_not_make_a_non_supabase_chain_match(self):
        # The same boundary principle inside a block: the brace that closes the block isolates
        # a Supabase identifier from a later chain.
        source = ('function unrelated() {\n'
                  '  const supabase = setup();\n'
                  '  return 1;\n'
                  '}\n'
                  'myClient.from("x").select("*");\n')
        calls = list(supabase_access.extract_calls(source))
        self.assertEqual(calls, [])


class SupabaseBindingThroughTheAuditTests(unittest.TestCase):
    """A service that inherits its client calls it `this.client`; the audit must still see its table calls."""

    def test_a_service_extending_a_base_that_holds_the_client_is_bound(self):
        texts = {'src/services/BaseService.ts': 'import type { SupabaseClient } from "@supabase/supabase-js";\n'
                                                'export class BaseService { constructor(protected client: SupabaseClient) {} }\n',
                 'src/services/Orders.ts': 'import { BaseService } from "./BaseService";\n'
                                           'export class Orders extends BaseService {\n'
                                           '  list() { return this.client\n    .from("orders")\n    .select("*"); }\n}\n',
                 'src/lib/types.ts': 'export type X = 1;\n',
                 'src/lib/arrays.ts': 'import { X } from "./types";\nconst y = Array.from(z);\n'}
        self.assertEqual(supabase_access.bound_files(texts), {'src/services/BaseService.ts': {'client'}, 'src/services/Orders.ts': {'client'}})

    def test_the_audit_writes_data_access_facts_for_an_injected_client(self):
        import json, tempfile
        from pathlib import Path
        from eaos.facts.run import collect
        with tempfile.TemporaryDirectory() as tmp:
            repo, out = Path(tmp) / 'repo', Path(tmp) / 'out'
            (repo / 'src/services').mkdir(parents=True)
            (repo / 'src/services/BaseService.ts').write_text(
                'import type { SupabaseClient } from "@supabase/supabase-js";\n'
                'export class BaseService { constructor(protected client: SupabaseClient) {} }\n')
            (repo / 'src/services/Orders.ts').write_text(
                'import { BaseService } from "./BaseService";\nexport class Orders extends BaseService {\n'
                '  list() { return this.client\n    .from("orders")\n    .select("*"); }\n'
                '  add(o) { return this.client.from("orders").insert(o); }\n}\n')
            collect(repo, out, ['syntax', 'entrypoints'])
            facts = [f for f in json.loads((out / 'facts/entrypoints.json').read_text())['facts'] if f['kind'] == 'data_access']
            self.assertEqual(sorted((f['value']['target'], f['value']['operation'], f['location']['start_line']) for f in facts),
                             [('orders', 'insert', 6), ('orders', 'select', 4)])
