"""The seeded mutations of the precision set: known defects planted into a copy of a project.

Each seed is a small set of new files whose every defect is known, because this module wrote it. The truth for
a seeded copy is therefore exact: every class is labelled exhaustively over the seeded files, and each planted
item names the detectors built to find it (its recall target). The originals are never touched: the files
are written under a copy only (tools/precision.py seed).

A line that carries a marker comment `@seed <name>` (or a pair `@seed <name>:start` / `@seed <name>:end`)
anchors a site; markers are resolved to line numbers after the files are written.
"""
import re

HEADER_TS = '// Planted by the EAOS precision harness (NS38.T1) in a copy of the project. Not product code.\n'
HEADER_PY = '"""Planted by the EAOS precision harness (NS38.T1) in a copy of the project. Not product code."""\n'


def _branchy_ts(name):
    lines = [f'export function {name}(kind: string, value: number, flags: {{ a?: boolean; b?: boolean }}) {{  // @seed complex:start']
    for i in range(26):
        lines += [f"  if (kind === 'k{i}') {{",
                  f"    if (value > {i}) {{ if (flags.a) {{ return 'k{i}-a'; }} else if (flags.b) {{ return 'k{i}-b'; }} }}",
                  f"    else if (value < -{i}) {{ return 'k{i}-n'; }}",
                  '  }']
    lines += ["  return 'none';", '}  // @seed complex:end']
    return '\n'.join(lines) + '\n'


def _branchy_py(name):
    lines = [f'def {name}(kind, value, flags):  # @seed complex:start']
    for i in range(26):
        lines += [f"    if kind == 'k{i}':",
                  f'        if value > {i}:',
                  "            if flags.get('a'):",
                  f"                return 'k{i}-a'",
                  "            elif flags.get('b'):",
                  f"                return 'k{i}-b'",
                  f'        elif value < -{i}:',
                  f"            return 'k{i}-n'"]
    lines += ["    return 'none'  # @seed complex:end"]
    return '\n'.join(lines) + '\n'


def _flat_table(comment, opener, closer, row):
    lines = [opener + f'  {comment} @seed flat:start']
    lines += [row.format(i=i) for i in range(160)]
    lines += [closer + f'  {comment} @seed flat:end']
    return '\n'.join(lines) + '\n'


PRICING_TS = HEADER_TS + '''export const SEED_TAX_RATE = {rate};  // @seed rate

export function {fn}({arg}: {{ price: number; quantity: number; discount?: number }}[]) {{  // @seed pricing:start
  let subtotal = 0;
  for (const {item} of {arg}) {{
    const gross = {item}.price * {item}.quantity;
    const discount = {item}.discount ? gross * {item}.discount : 0;
    subtotal += gross - discount;
  }}
  const tax = subtotal * SEED_TAX_RATE;
  const rounded = Math.round((subtotal + tax) * 100) / 100;
  if (rounded < 0) {{
    throw new Error('negative total');
  }}
  if (rounded > 1000000) {{
    console.warn('unusually large total', rounded);
  }}
  const lines = {arg}.length;
  const average = lines ? rounded / lines : 0;
  return {{ subtotal, tax, total: rounded, lines, average }};
}}  // @seed pricing:end
'''

PHONE_TS = HEADER_TS + ''.join('''
export function {prefix}%s(raw: string, country: string) {{  // @seed phone%s:start
  const digits = raw.replace(/[^0-9+]/g, '');
  if (digits.startsWith('+')) {{
    return digits;
  }}
  if (digits.startsWith('00')) {{
    return '+' + digits.slice(2);
  }}
  const prefix = country === 'SA' ? '+966' : '+1';
  const local = digits.startsWith('0') ? digits.slice(1) : digits;
  return prefix + local;
}}  // @seed phone%s:end
''' % (n, n, n) for n in (1, 2, 3))

SEQUENCE_TS = HEADER_TS + ''.join('''
export function {verb}%s(input: Record<string, unknown>) {{  // @seed sequence%s:start
  const checked = validateSeed(input);
  const clean = normalizeSeed(checked);
  const saved = persistSeed(clean);
  notifySeed(saved);
  return saved;
}}  // @seed sequence%s:end
''' % (n, n, n) for n in (1, 2, 3)) + '''
function validateSeed(input: Record<string, unknown>) {{ return input; }}
function normalizeSeed(input: Record<string, unknown>) {{ return input; }}
function persistSeed(input: Record<string, unknown>) {{ return input; }}
function notifySeed(input: Record<string, unknown>) {{ return input; }}
'''

MODELS_TS = HEADER_TS + '''export interface SeedCustomer {  // @seed customer
  id: string;
  name: string;
  email: string;
  createdAt: string;
}

export interface SeedInvoice {  // @seed invoice
  id: string;
  customerId: string;
  total: number;
  issuedAt: string;
}

export interface SeedCustomerCardProps {  // @seed props
  customer: SeedCustomer;
  onSelect: (id: string) => void;
}

export type SeedViewMode = 'grid' | 'list';  // @seed viewmode
'''

STATE_TS = HEADER_TS + '''let seedCounter = 0;  // @seed counter

export function nextSeedId() {
  seedCounter += 1;
  return seedCounter;
}

export const seedCache: Record<string, number> = {};  // @seed cache

export function rememberSeed(key: string, value: number) {
  seedCache[key] = value;
}
'''

WRITER_TS = HEADER_TS + '''declare const supabase: any;

export async function {fn}(order: {{ id: string; total: number }}) {{
  return supabase.from('seed_orders').{verb}(order);  // @seed write
}}
'''

TWIN_TSX = HEADER_TS + '''import {{ useState }} from 'react';

export default function {name}({{ customerId }}: {{ customerId: string }}) {{  // @seed page:start
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [saving, setSaving] = useState(false);
  async function save() {{
    setSaving(true);
    await fetch('/api/seed-customers/' + customerId, {{ method: 'PUT', body: JSON.stringify({{ name, email }}) }});
    setSaving(false);
  }}
  async function remove() {{
    await fetch('/api/seed-customers/' + customerId, {{ method: 'DELETE' }});
  }}
  return (
    <div style={{{{ width: 1200 }}}}>{{/* @seed width */}}
      <img src="/seed-logo.png" />{{/* @seed img */}}
      <h1>{title}</h1>
      <input value={{name}} onChange={{(e) => setName(e.target.value)}} />{{/* @seed label */}}
      <input value={{email}} onChange={{(e) => setEmail(e.target.value)}} />{{/* @seed label2 */}}
      <button onClick={{save}} disabled={{saving}}>Save</button>
      <button onClick={{remove}}><span className="icon-trash" /></button>{{/* @seed icon_button */}}
    </div>
  );
}}  // @seed page:end
'''

REDUNDANT_TS = HEADER_TS + '''export async function loadSeedRows(ids: string[]) {
  const rows = [];
  for (const id of ids) {
    const response = await fetch('/api/seed-rows/' + id);  // @seed n_plus_one
    rows.push(await response.json());
  }
  return rows;
}
'''

CYCLE_TS = HEADER_TS + '''import {{ {other} }} from './{other_file}';  // @seed import

export function {mine}(depth: number): number {{
  return depth <= 0 ? 0 : {other}(depth - 1) + 1;
}}
'''

FLAT_TS = HEADER_TS + _flat_table('//', 'export const SEED_UNITS = [', '];', "  {{ code: 'U{i}', label: 'Unit {i}', factor: {i} }},")
COMPLEX_TS = HEADER_TS + _branchy_ts('classifySeedReading')

SQL_SEED = '''-- Planted by the EAOS precision harness (NS38.T1) in a copy of the project. Not product code.
create table public.seed_ledger (  -- @seed ledger
  id uuid primary key default gen_random_uuid(),
  amount numeric not null,
  created_at timestamptz not null default now()
);

create table public.seed_notes (  -- @seed notes
  id uuid primary key default gen_random_uuid(),
  body text not null
);
alter table public.seed_notes enable row level security;
create policy "anyone can write seed notes" on public.seed_notes for insert with check (true);  -- @seed open_policy
'''

PRICING_PY = HEADER_PY + '''SEED_TAX_RATE = {rate}  # @seed rate


def {fn}({arg}):  # @seed pricing:start
    subtotal = 0
    for {item} in {arg}:
        gross = {item}['price'] * {item}['quantity']
        discount = gross * {item}['discount'] if {item}.get('discount') else 0
        subtotal += gross - discount
    tax = subtotal * SEED_TAX_RATE
    rounded = round(subtotal + tax, 2)
    if rounded < 0:
        raise ValueError('negative total')
    if rounded > 1000000:
        print('unusually large total', rounded)
    lines = len({arg})
    average = rounded / lines if lines else 0
    return {{'subtotal': subtotal, 'tax': tax, 'total': rounded, 'lines': lines, 'average': average}}  # @seed pricing:end
'''

PHONE_PY = HEADER_PY + ''.join('''

def {prefix}%s(raw, country):  # @seed phone%s:start
    digits = ''.join(ch for ch in raw if ch.isdigit() or ch == '+')
    if digits.startswith('+'):
        return digits
    if digits.startswith('00'):
        return '+' + digits[2:]
    prefix = '+966' if country == 'SA' else '+1'
    local = digits[1:] if digits.startswith('0') else digits
    return prefix + local  # @seed phone%s:end
''' % (n, n, n) for n in (1, 2, 3))

SEQUENCE_PY = HEADER_PY + ''.join('''

def {verb}%s(record):  # @seed sequence%s:start
    checked = validate_seed(record)
    clean = normalize_seed(checked)
    saved = persist_seed(clean)
    notify_seed(saved)
    return saved  # @seed sequence%s:end
''' % (n, n, n) for n in (1, 2, 3)) + '''

def validate_seed(record):
    return record


def normalize_seed(record):
    return record


def persist_seed(record):
    return record


def notify_seed(record):
    return record
'''

MODELS_PY = HEADER_PY + '''from dataclasses import dataclass


@dataclass
class SeedCustomer:  # @seed customer
    id: str
    name: str
    email: str
    created_at: str


@dataclass
class SeedInvoice:  # @seed invoice
    id: str
    customer_id: str
    total: float
    issued_at: str


@dataclass
class SeedRenderOptions:  # @seed props
    width: int = 80
    colour: bool = True
'''

STATE_PY = HEADER_PY + '''_COUNTER = 0  # @seed counter
REGISTRY = {}  # @seed cache
LIMIT = 10  # @seed limit


def bump():
    global _COUNTER
    _COUNTER += 1
    return _COUNTER


def register(key, value):
    REGISTRY[key] = value
'''

WRITER_PY = HEADER_PY + '''from eaos_seed import state


def {fn}(value):
    state.LIMIT = value  # @seed write
'''

BROKEN_PY = HEADER_PY + '''import eaos_seed.missing_module  # @seed missing


def total_with_fee(amount):
    return amount + UNDEFINED_SEED_FEE  # @seed undefined


LABELS = {'draft': 'Draft', 'paid': 'Paid', 'draft': 'Drafted'}  # @seed duplicate_key
'''

REDUNDANT_PY = HEADER_PY + '''def expensive_seed_lookup(config):
    return sorted(config.items())


def apply_seed(rows, config, db):
    out = []
    for row in rows:
        table = expensive_seed_lookup(config)  # @seed hoistable
        found = db.execute('select * from seed where id = ?', (row['id'],))  # @seed n_plus_one
        out.append((row, table, found))
    return out
'''

CYCLE_PY = HEADER_PY + '''from eaos_seed import {other_module}  # @seed import


def {mine}(depth):
    return 0 if depth <= 0 else {other_module}.{other}(depth - 1) + 1
'''

FLAT_PY = HEADER_PY + _flat_table('#', 'SEED_UNITS = [', ']', "    {{'code': 'U{i}', 'label': 'Unit {i}', 'factor': {i}}},")
COMPLEX_PY = HEADER_PY + _branchy_py('classify_seed_reading')


def typescript_files(base):
    """The planted files of a TypeScript project, under `base` (its source folder)."""
    pricing = dict(arg='lines', item='line')
    return {
        f'{base}/pricing-a.ts': PRICING_TS.format(rate='0.15', fn='computeSeedInvoiceTotal', **pricing),
        f'{base}/pricing-b.ts': PRICING_TS.format(rate='0.16', fn='computeSeedQuoteTotal', arg='items', item='entry'),
        f'{base}/phone-a.ts': PHONE_TS.format(prefix='normalizeSeedPhoneA'),
        f'{base}/phone-b.ts': PHONE_TS.format(prefix='normalizeSeedPhoneB'),
        f'{base}/sequence.ts': SEQUENCE_TS.format(verb='saveSeedRecord'),
        f'{base}/models.ts': MODELS_TS,
        f'{base}/state.ts': STATE_TS,
        f'{base}/writer-a.ts': WRITER_TS.format(fn='createSeedOrder', verb='insert'),
        f'{base}/writer-b.ts': WRITER_TS.format(fn='replaceSeedOrder', verb='upsert'),
        f'{base}/EditSeedCustomerPage.tsx': TWIN_TSX.format(name='EditSeedCustomerPage', title='Edit customer'),
        f'{base}/SeedCustomerDetailsPage.tsx': TWIN_TSX.format(name='SeedCustomerDetailsPage', title='Customer details'),
        f'{base}/redundant.ts': REDUNDANT_TS,
        f'{base}/cycle-a.ts': CYCLE_TS.format(other='seedDepthB', other_file='cycle-b', mine='seedDepthA'),
        f'{base}/cycle-b.ts': CYCLE_TS.format(other='seedDepthA', other_file='cycle-a', mine='seedDepthB'),
        f'{base}/units.ts': FLAT_TS,
        f'{base}/complex.ts': COMPLEX_TS,
    }


def python_files(base):
    pricing = dict(arg='lines', item='line')
    return {
        f'{base}/__init__.py': HEADER_PY,
        f'{base}/pricing_a.py': PRICING_PY.format(rate='0.15', fn='compute_seed_invoice_total', **pricing),
        f'{base}/pricing_b.py': PRICING_PY.format(rate='0.16', fn='compute_seed_quote_total', arg='items', item='entry'),
        f'{base}/phone_a.py': PHONE_PY.format(prefix='normalize_seed_phone_a'),
        f'{base}/phone_b.py': PHONE_PY.format(prefix='normalize_seed_phone_b'),
        f'{base}/sequence.py': SEQUENCE_PY.format(verb='save_seed_record'),
        f'{base}/models.py': MODELS_PY,
        f'{base}/state.py': STATE_PY,
        f'{base}/writer_a.py': WRITER_PY.format(fn='raise_seed_limit'),
        f'{base}/writer_b.py': WRITER_PY.format(fn='lower_seed_limit'),
        f'{base}/broken.py': BROKEN_PY,
        f'{base}/redundant.py': REDUNDANT_PY,
        f'{base}/cycle_a.py': CYCLE_PY.format(other_module='cycle_b', other='seed_depth_b', mine='seed_depth_a'),
        f'{base}/cycle_b.py': CYCLE_PY.format(other_module='cycle_a', other='seed_depth_a', mine='seed_depth_b'),
        f'{base}/units.py': FLAT_PY,
        f'{base}/complex.py': COMPLEX_PY,
    }


MARK = re.compile(r'@seed (?P<name>[\w]+)(?::(?P<edge>start|end))?')


def anchors(text):
    """{name: (start, end)} for every marker in a planted file."""
    found, open_ = {}, {}
    for number, line in enumerate(text.splitlines(), start=1):
        for match in MARK.finditer(line):
            name, edge = match.group('name'), match.group('edge')
            if edge == 'start': open_[name] = number
            elif edge == 'end': found[name] = (open_.pop(name), number)
            else: found[name] = (number, number)
    return found


def _site(files, path, name):
    start, end = anchors(files[path])[name]
    return {'path': path, 'start': start, 'end': end}


def _whole(files, path):
    return {'path': path, 'start': 1, 'end': len(files[path].splitlines())}


def items(files, language, sql_path=None, sql=None):
    """The truth of a seeded copy: (items, scopes). `detectors` on an item names what is built to find it."""
    ts = language == 'typescript'
    p = (lambda name: next(path for path in files if path.rsplit('/', 1)[1] == name))
    name = (lambda ts_name, py_name: p(ts_name if ts else py_name))
    rows = []

    def add(cls, label, subject, sites, reason, detectors=()):
        rows.append({'class': cls, 'label': label, 'subject': subject, 'sites': sites, 'reason': reason,
                     'detectors': list(detectors), 'seeded': True})

    a, b = name('pricing-a.ts', 'pricing_a.py'), name('pricing-b.ts', 'pricing_b.py')
    add('duplication', 'positive', 'seed pricing total copied with renamed variables',
        [_site(files, a, 'pricing'), _site(files, b, 'pricing')], 'a type-2 clone: the same 20-line function in two files',
        ['engine_cluster:literal_duplication', 'engine_cluster:duplication'])
    add('duplication', 'positive', 'SEED_TAX_RATE defined twice with different values',
        [_site(files, a, 'rate'), _site(files, b, 'rate')], 'one business rule (the tax rate) with two answers', ['duplicated_rule'])
    pa, pb = name('phone-a.ts', 'phone_a.py'), name('phone-b.ts', 'phone_b.py')
    add('duplication', 'positive', 'phone normaliser written six times',
        [_site(files, path, f'phone{n}') for path in (pa, pb) for n in (1, 2, 3)],
        'six renamed copies of one normaliser', ['structural_duplicate', 'engine_cluster:duplication', 'engine_cluster:literal_duplication'])
    sq = name('sequence.ts', 'sequence.py')
    add('duplication', 'positive', 'validate-normalize-persist-notify orchestration copied three times',
        [_site(files, sq, f'sequence{n}') for n in (1, 2, 3)], 'the same ordered call sequence in three functions',
        ['sequence_duplicate'])
    models = name('models.ts', 'models.py')
    add('data_model', 'positive', 'SeedCustomer', [_site(files, models, 'customer')], 'a business entity', ['data_model'])
    add('data_model', 'positive', 'SeedInvoice', [_site(files, models, 'invoice')], 'a business entity', ['data_model'])
    add('data_model', 'negative', 'SeedCustomerCardProps' if ts else 'SeedRenderOptions', [_site(files, models, 'props')],
        'component props / rendering options, not a record of the business')
    if ts:
        add('data_model', 'negative', 'SeedViewMode', [_site(files, models, 'viewmode')], 'a UI mode union, not a record')
    state = name('state.ts', 'state.py')
    add('mutable_state', 'positive', 'seed counter', [_site(files, state, 'counter')], 'module-level value reassigned by a function',
        ['mutable_global'])
    add('mutable_state', 'positive', 'seed cache', [_site(files, state, 'cache')], 'module-level object mutated by a function',
        ['mutable_global'])
    wa, wb = name('writer-a.ts', 'writer_a.py'), name('writer-b.ts', 'writer_b.py')
    add('multiple_writers', 'positive', 'seed_orders' if ts else 'state.LIMIT',
        [_site(files, wa, 'write'), _site(files, wb, 'write')], 'the same data written from two modules',
        [] if ts else ['external_write', 'data_owners'])
    cx, flat = name('complex.ts', 'complex.py'), name('units.ts', 'units.py')
    add('complexity', 'positive', 'classify seed reading', [_site(files, cx, 'complex')], 'one function with ~100 branches nested three deep',
        ['hotspot', 'engine_cluster:complexity'])
    add('complexity', 'negative', 'seed units table', [_site(files, flat, 'flat')], 'long but flat: a static table')
    red = name('redundant.ts', 'redundant.py')
    add('redundant_work', 'positive', 'request per row', [_site(files, red, 'n_plus_one')], 'one query per loop iteration (N+1)',
        ['redundant_work'])
    if not ts:
        add('redundant_work', 'positive', 'loop-invariant lookup', [_site(files, red, 'hoistable')],
            'the same call with the same argument on every iteration', ['redundant_work'])
    ca, cb = name('cycle-a.ts', 'cycle_a.py'), name('cycle-b.ts', 'cycle_b.py')
    add('cycle', 'positive', 'seed cycle', [_site(files, ca, 'import'), _site(files, cb, 'import')], 'two modules import each other',
        ['import_cycle', 'engine_cluster:cycle'])
    if ts:
        edit, details = p('EditSeedCustomerPage.tsx'), p('SeedCustomerDetailsPage.tsx')
        add('overlap', 'positive', 'two pages editing the same customer', [_site(files, edit, 'page'), _site(files, details, 'page')],
            'both pages load, edit and delete one customer through the same endpoint')
        add('duplication', 'positive', 'twin customer pages', [_site(files, edit, 'page'), _site(files, details, 'page')],
            'the second page is a copy of the first with another title',
            ['engine_cluster:literal_duplication', 'engine_cluster:duplication'])
        add('multiple_writers', 'positive', 'PUT/DELETE /api/seed-customers/:id', [_site(files, edit, 'page'), _site(files, details, 'page')],
            'two pages write the same endpoint')
        for page in (edit, details):
            for marker, why in (('width', 'a fixed 1200px width overflows a phone'), ('img', 'image without alt text'),
                                ('label', 'input without a label'), ('label2', 'input without a label'),
                                ('icon_button', 'icon-only button without an accessible name')):
                add('ui_defect', 'positive', why, [_site(files, page, marker)], why)
            add('ui_defect', 'positive', 'delete without confirmation', [_site(files, page, 'icon_button')],
                'a destructive action runs on one click with no confirmation')
    else:
        broken = p('broken.py')
        for marker, why in (('missing', 'import of a module that does not exist'), ('undefined', 'undefined name'),
                            ('duplicate_key', 'dictionary key written twice')):
            add('broken_code', 'positive', why, [_site(files, broken, marker)], why, ['broken_code'])
    if not ts:
        add('mutable_state', 'positive', 'state.LIMIT', [_site(files, state, 'limit')],
            'module-level value reassigned at runtime by two other modules (writer_a, writer_b)', ['mutable_global'])
    for path in files:
        add('dead_code', 'positive', path.rsplit('/', 1)[1], [_whole(files, path)], 'a planted module nothing imports',
            ['dead_code', 'engine_cluster:dead_code'])
    scopes = [{'class': cls, 'paths': sorted(files), 'note': 'seeded files: every planted defect is listed'}
              for cls in ('duplication', 'overlap', 'multiple_writers', 'data_model', 'ui_defect', 'dead_code', 'broken_code',
                          'complexity', 'mutable_state', 'redundant_work', 'cycle', 'access_gap')]
    if sql_path:
        sites = anchors(sql)
        add('access_gap', 'positive', 'seed_ledger', [{'path': sql_path, 'start': sites['ledger'][0], 'end': sites['ledger'][0]}],
            'a table served to the browser with row-level security never enabled', ['access_gap_no_rls'])
        add('access_gap', 'positive', 'anyone can write seed notes',
            [{'path': sql_path, 'start': sites['open_policy'][0], 'end': sites['open_policy'][0]}],
            'an insert policy whose check is true', ['access_gap_open_write'])
        add('data_model', 'positive', 'seed_ledger table', [{'path': sql_path, 'start': sites['ledger'][0], 'end': sites['ledger'][0]}],
            'a business table', ['data_table'])
        add('data_model', 'positive', 'seed_notes table', [{'path': sql_path, 'start': sites['notes'][0], 'end': sites['notes'][0]}],
            'a business table', ['data_table'])
        for scope in scopes: scope['paths'] = sorted(scope['paths'] + [sql_path])
    return rows, scopes
