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
    """Each Supabase call is reported with its client, target and operation; a look-alike chain is not."""

    def test_each_supabase_call_shape_is_reported_once_with_its_target_and_operation(self):
        calls = list(supabase_access.extract_calls(SOURCE))
        # myClient.from('things') is not Supabase, and `.storage.from(...)` is not also a table call.
        self.assertEqual(len(calls), 4, [record for _, _, record in calls])
        records = {(record['symbol'], record['operation']): record for _, _, record in calls}
        self.assertEqual(set(records), {('from', 'select'), ('from', 'insert'), ('rpc', 'rpc'), ('storage', 'storage')})
        self.assertEqual(records[('from', 'select')]['target'], 'users')
        self.assertEqual(records[('from', 'select')]['client'], 'supabase')
        self.assertEqual(records[('from', 'insert')]['target'], 'imports')
        self.assertEqual(records[('rpc', 'rpc')]['target'], 'daily_report')
        self.assertEqual(records[('storage', 'storage')]['target'], 'avatars')
        [(_, _, auth)] = supabase_access.extract_calls('await supabase.auth.signOut();')
        self.assertEqual((auth['operation'], auth['target'], auth['symbol']), ('signOut', 'auth', 'auth'))
        # `context.supabase.from(...)` is the real-world shape used by finance-os; lines are one-based.
        [(_, line, prop)] = supabase_access.extract_calls('const x = 1;\nawait context.supabase.from("movements").insert({});')
        self.assertEqual((line, prop['target'], prop['operation']), (2, 'movements', 'insert'))
        written = [r for _, _, r in supabase_access.extract_calls(
            "supabase.from('vehicles').insert([{ plate, vin: v }]);\nsupabase.from('vehicles').update(row).eq('id', 1);\n")]
        self.assertEqual([(r['operation'], r.get('keys')) for r in written], [('insert', ['plate', 'vin']), ('update', None)])

    def test_a_supabase_name_in_an_earlier_statement_or_block_does_not_leak_into_a_later_chain(self):
        for source in ('const supabase = setup();\nmyClient.from("x").select("*");\n',
                       'function unrelated() {\n  const supabase = setup();\n  return 1;\n}\nmyClient.from("x").select("*");\n'):
            self.assertEqual(list(supabase_access.extract_calls(source)), [], source)


class SupabaseBindingThroughTheAuditTests(unittest.TestCase):
    """A service that inherits its client calls it `this.client`; the audit must still see its table calls."""

    def test_a_service_extending_a_base_that_holds_the_client_is_bound_and_its_calls_are_facts(self):
        texts = {'src/services/BaseService.ts': 'import type { SupabaseClient } from "@supabase/supabase-js";\n'
                                                'export class BaseService { constructor(protected client: SupabaseClient) {} }\n',
                 'src/services/Orders.ts': 'import { BaseService } from "./BaseService";\n'
                                           'export class Orders extends BaseService {\n'
                                           '  list() { return this.client\n    .from("orders")\n    .select("*"); }\n}\n',
                 'src/lib/types.ts': 'export type X = 1;\n',
                 'src/lib/arrays.ts': 'import { X } from "./types";\nconst y = Array.from(z);\n'}
        self.assertEqual(supabase_access.bound_files(texts), {'src/services/BaseService.ts': {'client'}, 'src/services/Orders.ts': {'client'}})
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
