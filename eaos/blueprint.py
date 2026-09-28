"""Build a project from its plan (docs/BUILD-FROM-PLAN.md): the target structure first, then the build as cards.

An audit reads what exists, draws the target, and plans the way from one to the other. A project that exists only
as a plan (a PRD, notes, a pasted text) has no current state: the target is drawn from the plan itself, and the gap
is the whole build. EAOS lays it out so that what its audits look for never gets in:

  read_source     any plan the person has (Markdown, text, PDF, Word, HTML, or pasted words) as plain text.
  validate_spec   the product spec the assistant writes from it (SPEC below): every feature has a module, its data and
                  a way to check it; every piece of data has one owner. What is missing or undecided comes back as
                  questions with choices, for the assistant to research, recommend, and ask.
  choose_stack    one option per concern from eaos/data/stacks.json: the person's preference, else the recommendation.
  design          the target architecture (layers, one home per concept, each vendor behind one adapter folder), the
                  project's own eaos.policy.json, and plan.json: milestones of build cards, each with its files,
                  acceptance and tests, in the order that lets each card use only what exists.
  build_problems  the gates after every card, from one collection of facts on the built copy: layering, files outside
                  the plan, a vendor imported outside its adapter, import cycles, broken references, copied code; and,
                  when a milestone closes, dead code.

Nothing here calls a model: the assistant reads, researches and writes; EAOS gives the shape and the gates.
"""
import html
import json
import re
import subprocess
import zipfile
from pathlib import Path

DATA = Path(__file__).resolve().parent / 'data'
SOURCE_SUFFIXES = ('.md', '.markdown', '.txt', '.text', '.rst', '.pdf', '.docx', '.html', '.htm', '.json', '.yaml', '.yml')
ISOLATED = ('database', 'auth')          # concerns whose packages only their adapter folder may import
LINE_BUDGET = {'skeleton': 250, 'foundation': 200, 'module': 250, 'feature': 200, 'flow': 150}


def stacks():
    return json.loads((DATA / 'stacks.json').read_text(encoding='utf-8'))


# ---------------------------------------------------------------- 1. any plan, as text

def read_source(path=None, text=None):
    """The plan as plain text: pasted words as they are, or a file of any common kind."""
    if text and text.strip(): return text.strip()
    if not path: raise ValueError('no plan was given: pass the file path or paste its text')
    path = Path(path).expanduser()
    if not path.is_file(): raise ValueError(f'the plan file was not found: {path}')
    suffix = path.suffix.lower()
    if suffix == '.pdf': return _pdf(path)
    if suffix == '.docx': return _docx(path)
    raw = path.read_text(encoding='utf-8', errors='replace')
    if suffix in ('.html', '.htm'):
        raw = re.sub(r'(?is)<(script|style)\b.*?</\1>', '', raw)
        raw = re.sub(r'(?i)<br\s*/?>|</(p|div|li|h\d|tr)>', '\n', raw)
        raw = html.unescape(re.sub(r'<[^>]+>', '', raw))
    return re.sub(r'\n{3,}', '\n\n', raw).strip()


def _pdf(path):
    try:
        from pypdf import PdfReader        # when installed; the command-line tool otherwise
        return '\n\n'.join((page.extract_text() or '') for page in PdfReader(str(path)).pages).strip()
    except ImportError:
        pass
    try:
        done = subprocess.run(['pdftotext', '-layout', str(path), '-'], capture_output=True, text=True, timeout=120)
    except FileNotFoundError:
        raise ValueError('this PDF cannot be read here (no pypdf, no pdftotext): paste its text instead') from None
    if done.returncode: raise ValueError(f'the PDF could not be read: {done.stderr[-300:]}')
    return done.stdout.strip()


def _docx(path):
    """Word's text: the paragraphs of word/document.xml, one per line, tables row by row."""
    with zipfile.ZipFile(path) as archive:
        xml = archive.read('word/document.xml').decode('utf-8', errors='replace')
    xml = re.sub(r'</w:p>', '\n', xml)
    xml = re.sub(r'</w:tc>', ' | ', xml)
    return html.unescape(re.sub(r'<[^>]+>', '', xml)).strip()


# ---------------------------------------------------------------- 2. the product spec

SPEC = {
    'name': 'the product name',
    'summary': 'what it is and for whom, in two or three sentences',
    'users': [{'id': 'owner', 'name': 'who they are', 'needs': ['what they come to do']}],
    'modules': [{'id': 'orders', 'name': 'Orders', 'responsibility': 'one sentence: what this part alone is responsible for'}],
    'entities': [{'id': 'order', 'name': 'Order', 'module': 'orders',
                  'fields': [{'name': 'total', 'type': 'money | text | number | date | boolean | id | enum | json', 'required': True}]}],
    'features': [{'id': 'F1', 'name': 'Place an order', 'module': 'orders', 'priority': 'must | should | could',
                  'entities': ['order'], 'roles': ['customer'], 'description': 'what the user can do',
                  'acceptance': ['Given ..., when ..., then ... (each becomes a test)']}],
    'flows': [{'id': 'FL1', 'name': 'First order', 'actor': 'customer', 'features': ['F1'], 'steps': ['...']}],
    'roles': [{'id': 'customer', 'name': 'Customer', 'can': ['F1']}],
    'integrations': [{'id': 'payments', 'name': 'Stripe', 'purpose': 'take payments'}],
    'nonfunctional': {'expected_users': 1000, 'languages': ['ar', 'en'], 'data_sensitivity': 'personal | health | payment | none',
                      'platforms': ['web', 'mobile web']},
    'stack_preferences': {'database': 'an option id from the catalogue, or empty to take the recommendation'},
    'decisions': [{'id': 'D1', 'question': 'an open product question', 'options': ['A', 'B'], 'recommendation': 'A',
                   'why': 'the research behind it', 'chosen': 'A, once the person chose (empty until then)'}],
}


def validate_spec(spec):
    """(problems, questions): what makes the spec unbuildable, and what the person should decide."""
    problems, questions = [], []
    if not isinstance(spec, dict): return ['the spec must be one JSON object shaped like the example'], []
    for key in ('name', 'summary'):
        if not str(spec.get(key) or '').strip(): problems.append(f'`{key}` is empty')
    modules = {m.get('id') for m in spec.get('modules') or [] if isinstance(m, dict)}
    entities = {e.get('id'): e for e in spec.get('entities') or [] if isinstance(e, dict)}
    features = {f.get('id'): f for f in spec.get('features') or [] if isinstance(f, dict)}
    roles = {r.get('id') for r in spec.get('roles') or [] if isinstance(r, dict)}
    if not modules: problems.append('no module: group the features into parts, each with one responsibility')
    if not features: problems.append('no feature: list what a user can do')
    for module in spec.get('modules') or []:
        if not str(module.get('responsibility') or '').strip(): problems.append(f"module {module.get('id')}: its responsibility is empty")
        if not any(f.get('module') == module.get('id') for f in features.values()):
            problems.append(f"module {module.get('id')}: no feature belongs to it (merge it, or give it one)")
    for entity_id, entity in entities.items():
        if entity.get('module') not in modules:
            problems.append(f'entity {entity_id}: its owning module is not one of the modules (every piece of data has one owner)')
        if not entity.get('fields'): problems.append(f'entity {entity_id}: it has no fields')
        if not any(entity_id in (f.get('entities') or []) for f in features.values()):
            problems.append(f'entity {entity_id}: no feature uses it (remove it, or say which feature needs it)')
    for feature_id, feature in features.items():
        if feature.get('module') not in modules: problems.append(f'feature {feature_id}: its module is not one of the modules')
        for entity_id in feature.get('entities') or []:
            if entity_id not in entities: problems.append(f'feature {feature_id}: uses {entity_id}, which is not an entity')
        for role in feature.get('roles') or []:
            if roles and role not in roles: problems.append(f'feature {feature_id}: role {role} is not one of the roles')
        if not [a for a in feature.get('acceptance') or [] if str(a).strip()]:
            problems.append(f'feature {feature_id}: no acceptance criterion (how do we know it works? each becomes a test)')
    for flow in spec.get('flows') or []:
        for feature_id in flow.get('features') or []:
            if feature_id not in features: problems.append(f"flow {flow.get('id')}: uses {feature_id}, which is not a feature")
    catalogue = stacks()['concerns']
    for concern, choice in (spec.get('stack_preferences') or {}).items():
        if concern in catalogue and choice and choice not in catalogue[concern]['options']:
            questions.append({'id': f'stack-{concern}', 'kind': 'choice', 'text': f"{catalogue[concern]['title']}: which one?",
                              'options': list(catalogue[concern]['options']), 'recommendation': catalogue[concern]['recommended'],
                              'why': f'{choice!r} is not one EAOS lays out yet'})
    for decision in spec.get('decisions') or []:
        if not str(decision.get('chosen') or '').strip():
            questions.append({'id': decision.get('id'), 'kind': 'choice', 'text': decision.get('question'),
                              'options': decision.get('options') or [], 'recommendation': decision.get('recommendation'),
                              'why': decision.get('why')})
    if not spec.get('flows'): questions.append({'id': 'flows', 'kind': 'yes_no', 'text': 'The plan names no user journey from start to finish. '
                                                'May the assistant write the main ones from the features?', 'recommendation': 'yes'})
    return problems, questions


# ---------------------------------------------------------------- 3. the stack

def choose_stack(spec, chosen=None):
    """{concern: {'id', 'name', 'why', 'switch', 'packages', 'alternatives'}}: the person's choice, their plan's
    preference, else the recommendation; a database or sign-in the plan does not need is 'none'."""
    catalogue = stacks()['concerns']
    wanted = {**(spec.get('stack_preferences') or {}), **(chosen or {})}
    needs_data = bool(spec.get('entities'))
    needs_auth = bool(spec.get('roles')) or any(f.get('roles') for f in spec.get('features') or [])
    stack = {}
    for concern, entry in catalogue.items():
        pick = wanted.get(concern) if wanted.get(concern) in entry['options'] else entry['recommended']
        if concern == 'database' and not needs_data and not wanted.get(concern): pick = 'none'
        if concern == 'auth' and not needs_auth and not wanted.get(concern): pick = 'none'
        option = entry['options'][pick]
        stack[concern] = {'id': pick, 'name': option['name'], 'why': option['why'], 'switch': option['switch'],
                          'packages': option['packages'], 'title': entry['title'],
                          'alternatives': [{'id': key, 'name': other['name'], 'why': other['why']}
                                           for key, other in entry['options'].items() if key != pick]}
    if stack['database']['id'] == 'supabase' and not wanted.get('api'):
        stack['api'] = {**stack['api']}                  # a server still holds the rules; Supabase is its database
    return stack


# ---------------------------------------------------------------- 4. the target, and the build as cards

def slug(text):
    return re.sub(r'[^a-z0-9]+', '-', str(text).lower()).strip('-') or 'part'


def layout(stack):
    """The folders of the project and the layer each is; the server's layers exist only with a server."""
    server = stack['api']['id'] != 'none'
    layers = {'shared': ['shared/src/**'],
              'web-app': ['web/src/app/**', 'web/src/main.tsx', 'web/src/*.css'], 'web-features': ['web/src/features/**'],
              'web-ui': ['web/src/ui/**'], 'web-api': ['web/src/api/**'],
              # Tests and configuration are named first ('_' sorts before letters), so a test beside the code it tests is a test.
              '_tests': ['**/*.test.ts', '**/*.test.tsx', 'e2e/**', '**/tests/**'],
              '_config': ['*.json', '*.md', '*.config.*', '*/*.json', '*/*.config.*', '*/index.html', '.*', '*/.*', 'docs/**']}
    rules = [({'from': 'shared', 'to': []}, 'Shared types and rules depend on nothing, so both sides can use them.'),
             ({'from': 'web-ui', 'to': ['shared']}, 'The shared look knows no feature and no server.'),
             ({'from': 'web-api', 'to': ['shared']}, 'The one client of the server knows no screen.'),
             ({'from': 'web-features', 'to': ['web-ui', 'web-api', 'shared']},
              'A screen uses the shared look and the one client; it never reaches into another feature.'),
             ({'from': 'web-app', 'to': ['web-features', 'web-ui', 'web-api', 'shared']}, 'The app shell composes features.')]
    if server:
        layers.update({'domain': ['server/src/domain/**'], 'application': ['server/src/application/**'],
                       'infrastructure': ['server/src/infrastructure/**'], 'interface': ['server/src/interface/**'],
                       'composition': ['server/src/main.ts', 'server/src/config.ts']})
        rules += [({'from': 'domain', 'to': ['shared']}, 'Business rules are pure: no database, no web framework, no vendor.'),
                  ({'from': 'application', 'to': ['domain', 'shared']}, 'Use cases call rules and the ports they declare, never a vendor.'),
                  ({'from': 'infrastructure', 'to': ['application', 'domain', 'shared']},
                   'Adapters implement the ports; they are the only place a vendor is used.'),
                  ({'from': 'interface', 'to': ['application', 'shared']}, 'Routes call use cases; they hold no rule and no query.')]
    return layers, rules


def adapter_folder(stack, concern):
    if stack['api']['id'] == 'none': return f'web/src/infrastructure/{concern}/'
    return f'server/src/infrastructure/{concern}/'


def policy(stack):
    layers, rules = layout(stack)
    if stack['api']['id'] == 'none':
        layers['web-infrastructure'] = ['web/src/infrastructure/**']
        rules.append(({'from': 'web-infrastructure', 'to': ['shared']}, 'Hosted services are reached from one adapter folder.'))
        rules = [(({**rule, 'to': rule['to'] + ['web-infrastructure']} if rule['from'] in ('web-api',) else rule), why) for rule, why in rules]
    return {'schema_version': 1, 'layers': layers,
            'rules': [{'allow_only': rule, 'reason': why} for rule, why in rules],
            # A vendor lives in its adapter, and, for its browser half (a sign-in client), in the one client of the server.
            'vendors': {concern: {'packages': stack[concern]['packages'], 'only_in': sorted({adapter_folder(stack, concern), 'web/src/api/'})}
                        for concern in ISOLATED if stack[concern]['id'] != 'none'},
            'notes': 'Written by EAOS from the blueprint: the target structure as a checked contract. eaos policy check reads it.'}


def design(spec, stack):
    """{'architecture', 'policy', 'plan'}: the target and the build, from the spec and the stack alone."""
    server = stack['api']['id'] != 'none'
    modules = [m for m in spec['modules']]
    features = spec['features']
    entities = spec.get('entities') or []
    cards, milestones = [], []

    def card(milestone, kind, title, module, paths, acceptance, tests, depends=(), feature=None, why=''):
        number = len(cards) + 1
        row = {'id': f'BLD-{number:03d}', 'kind': 'build', 'pattern': f'build_{kind}', 'milestone': milestone, 'title': title,
               'module': module, 'paths': paths, 'acceptance': acceptance, 'tests': tests, 'depends_on': list(depends),
               'feature': feature, 'why': why, 'budget_lines': LINE_BUDGET[kind],
               'decision': {'kind': 'build', 'readiness': 'ready'}, 'status': 'planned'}
        cards.append(row)
        return row['id']

    # M01: the skeleton, with every check running from the first commit.
    skeleton = card('M01', 'skeleton', 'The project skeleton: workspaces, strict TypeScript, lint, tests, and one smoke test per part', None,
                    ['package.json', 'tsconfig.base.json', 'eslint.config.js', '.gitignore', 'shared/', 'web/'] + (['server/'] if server else []),
                    ['npm install, then npm run typecheck, npm run lint and npm test all pass at the root',
                     'the web app shows its shell page' + ('; the server answers GET /health with ok' if server else '')],
                    ['web/src/app/app.test.tsx'] + (['server/src/main.test.ts'] if server else []),
                    why='Every later card is checked by these scripts, so they exist before any feature.')
    # M02: one home for each shared concept, so nothing is written twice later.
    foundations = [skeleton]
    foundations.append(card('M02', 'foundation', 'One home for errors and input validation', None,
                            ['shared/src/errors.ts', 'shared/src/validation.ts'],
                            ['every error the app shows has one type and one place that builds it',
                             'input is validated by the one schema helper, on the server and in the screens alike'],
                            ['shared/src/validation.test.ts'], [skeleton],
                            why='Validation and errors are where copied code starts; one home keeps them single.'))
    if server:
        foundations.append(card('M02', 'foundation', 'One home for configuration', None, ['server/src/config.ts'],
                                ['the environment is read once, typed, in config.ts; nothing else reads process.env',
                                 'a missing required value stops the server at start with its name'],
                                ['server/src/config.test.ts'], [skeleton]))
    if stack['database']['id'] != 'none':
        foundations.append(card('M02', 'foundation', f"The database adapter ({stack['database']['name']})", None,
                                [adapter_folder(stack, 'database')],
                                ['the connection and migrations live only in the database adapter folder',
                                 'a repository port is declared in application/ and implemented here'],
                                [adapter_folder(stack, 'database') + 'database.test.ts'], [skeleton],
                                why='Only this folder knows the database, so changing it later is replacing one folder.'))
    if stack['auth']['id'] != 'none':
        foundations.append(card('M02', 'foundation', f"Sign-in ({stack['auth']['name']})", None,
                                [adapter_folder(stack, 'auth'), 'web/src/features/auth/'] + (['server/src/interface/http/auth/'] if server else []),
                                ['a person can sign up, sign in and sign out',
                                 'one function answers who the current user is, and every protected route uses it'],
                                ['web/src/features/auth/auth.test.tsx'], foundations[-1:] if stack['database']['id'] != 'none' else [skeleton]))
    foundations.append(card('M02', 'foundation', 'The app shell, the shared look and the one server client', None,
                            ['web/src/app/', 'web/src/ui/', 'web/src/api/'],
                            ['every screen uses the shared components in web/src/ui (buttons, inputs, forms, tables, messages)',
                             'every call to the server goes through web/src/api'],
                            ['web/src/ui/ui.test.tsx'], [skeleton]))
    # M03…: one milestone per module, in the order its data allows: owners of data another module uses come first.
    uses = {m['id']: set() for m in modules}
    owner = {e['id']: e['module'] for e in entities}
    for feature in features:
        for entity_id in feature.get('entities') or []:
            if owner.get(entity_id) and owner[entity_id] != feature['module']: uses[feature['module']].add(owner[entity_id])
    ordered, placed = [], set()
    while len(ordered) < len(modules):
        ready = [m for m in modules if m['id'] not in placed and uses[m['id']] <= placed] or \
                [m for m in modules if m['id'] not in placed][:1]           # a cycle between modules: the plan breaks it in order
        for m in ready: ordered.append(m); placed.add(m['id'])
    last_of = {}
    for index, module in enumerate(ordered, start=3):
        mid = f'M{index:02d}'
        base = [foundations[-1]] + [last_of[other] for other in sorted(uses[module['id']]) if other in last_of]
        owned = [e for e in entities if e['module'] == module['id']]
        folder = slug(module['id'])
        data_card = None
        if owned:
            paths = [f'shared/src/{folder}/'] + ([f'server/src/domain/{folder}/', f'server/src/application/{folder}/'] if server else [])
            if stack['database']['id'] != 'none': paths.append(adapter_folder(stack, 'database') + f'{folder}.ts')
            data_card = card(mid, 'module', f"{module['name']}: its data and rules ({', '.join(e['name'] for e in owned)})", module['id'], paths,
                             [f"{e['name']} is defined once (shared types and one schema), stored by this module's repository only" for e in owned]
                             + [f"only the {module['name']} module writes {', '.join(e['name'] for e in owned)}; others ask it"],
                             [f'shared/src/{folder}/{folder}.test.ts'], base,
                             why='The data has one owner: other modules call it rather than touching its tables.')
        previous = data_card or base[-1]
        for feature in [f for f in features if f['module'] == module['id']]:
            fslug = slug(feature['name'])[:40]
            paths = [f'web/src/features/{folder}/{fslug}/'] + ([f'server/src/application/{folder}/{fslug}.ts', f'server/src/interface/http/{folder}/'] if server else [])
            previous = card(mid, 'feature', f"{module['name']}: {feature['name']}", module['id'], paths,
                            list(feature.get('acceptance') or []), [f'web/src/features/{folder}/{fslug}/{fslug}.test.tsx']
                            + ([f'server/src/application/{folder}/{fslug}.test.ts'] if server else []),
                            [previous] + ([data_card] if data_card and data_card != previous else []), feature=feature['id'],
                            why=feature.get('description') or '')
        last_of[module['id']] = previous
    # The last milestone: every journey end to end in a real browser.
    flows = spec.get('flows') or []
    if flows:
        mid = f'M{len(ordered) + 3:02d}'
        for flow in flows:
            card(mid, 'flow', f"Journey: {flow['name']}", None, ['e2e/'],
                 [f"a {flow.get('actor') or 'user'} completes it in the browser: " + ' → '.join(map(str, flow.get('steps') or []))[:400]],
                 [f"e2e/{slug(flow['name'])[:40]}.spec.ts"], [last_of[m['id']] for m in ordered if m['id'] in last_of][-1:])
    names = {'M01': ('الهيكل', 'The skeleton'), 'M02': ('الأساسات المشتركة', 'Shared foundations')}
    for index, module in enumerate(ordered, start=3): names[f'M{index:02d}'] = (module['name'], module['name'])
    if flows: names[f'M{len(ordered) + 3:02d}'] = ('الرحلات كاملة', 'Journeys end to end')
    for mid, (ar, en) in names.items():
        ids = [c['id'] for c in cards if c['milestone'] == mid]
        if ids: milestones.append({'id': mid, 'name': en, 'name_ar': ar, 'tasks': ids,
                                   'goal': f'{en}: built, every card through its gates.', 'exit': 'every card here passes its gates and its tests'})
    architecture = target(spec, stack, ordered)
    return {'architecture': architecture, 'policy': policy(stack),
            'plan': {'contract_version': 1, 'kind': 'blueprint', 'tasks': cards, 'milestones': milestones, 'waves': [], 'sections': [], 'decisions': []}}


def target(spec, stack, modules):
    """target-architecture.json for a project not built yet: the same shape an audit writes, so the report for people
    and the `structure` tool read it the same way."""
    server = stack['api']['id'] != 'none'
    components = []
    for module in modules:
        folder = slug(module['id'])
        paths = [f'shared/src/{folder}/', f'web/src/features/{folder}/'] + ([f'server/src/domain/{folder}/', f'server/src/application/{folder}/',
                                                                            f'server/src/interface/http/{folder}/'] if server else [])
        components.append({'id': f'T-{folder}', 'name': module['name'], 'kind': 'module', 'relation': 'build',
                           'responsibility': module.get('responsibility') or '', 'paths': paths, 'files': 0,
                           'reason': 'A part of the product with one responsibility (from the plan).'})
    for concern in ISOLATED:
        if stack[concern]['id'] != 'none':
            components.append({'id': f'T-{concern}', 'name': stack[concern]['name'], 'kind': 'adapter', 'relation': 'build',
                               'responsibility': f'the only place that uses {stack[concern]["name"]}', 'paths': [adapter_folder(stack, concern)],
                               'files': 0, 'reason': stack[concern]['switch']})
    layers, rules = layout(stack)
    return {'schema_version': 1, 'status': 'blueprint', 'current_components': [], 'components': components,
            'target_components': components, 'target_edges': [{'from': rule['from'], 'to': to} for rule, _ in rules for to in rule['to']],
            'forbidden_edges': [{'from': rule['from'], 'rule': 'only ' + (', '.join(rule['to']) or 'nothing'), 'reason': why} for rule, why in rules],
            'decisions': [{'id': f'ADR-{concern}', 'concern': stack[concern]['title'], 'chosen': stack[concern]['name'], 'why': stack[concern]['why'],
                           'alternatives': stack[concern]['alternatives'], 'how_to_change_later': stack[concern]['switch']} for concern in stack],
            'gap_matrix': [], 'limits': 'A target drawn from a plan: nothing exists yet, so every part is to be built.'}


# ---------------------------------------------------------------- 5. the gates

def build_problems(root, out, rules, closing=False):
    """What a built copy breaks, from the facts collected into `out`: [{'gate', 'where', 'what'}]."""
    from .facts.store import read_set
    from .policy import violations
    sets = {}
    for name in ('resolve', 'graph', 'broken', 'metrics', 'deadcode'):
        if (Path(out) / 'facts' / f'{name}.json').is_file(): sets[name] = read_set(out, name)
    found = []
    if 'resolve' in sets and 'graph' in sets:
        broken, outside = violations(rules, sets)
        found += [{'gate': 'layers', 'where': f"{row['from_path']}:{row['line'] or 1}",
                   'what': f"{row['from_layer']} may not use {row['to_layer']} ({row['to_path']}): {row['reason']}"} for row in broken]
        found += [{'gate': 'structure', 'where': path, 'what': 'this file is outside every planned folder: put it where the plan says'}
                  for path in outside]
        for concern, vendor in (rules.get('vendors') or {}).items():
            for edge in sets['resolve']['facts']:
                module, source = edge['value'].get('module') or '', edge['location']['path']
                named = any(module == package or module.startswith(package + '/') for package in vendor['packages'])
                homes = [vendor['only_in']] if isinstance(vendor['only_in'], str) else vendor['only_in']
                if named and not any(source.startswith(home) for home in homes) and not re.search(r'\.test\.tsx?$', source):
                    found.append({'gate': 'vendor', 'where': f"{source}:{edge['location'].get('start_line') or 1}",
                                  'what': f"{module} is used outside {' and '.join(homes)}: only the {concern} adapter may use it, "
                                          'so it can be changed in one place'})
    for fact in (sets.get('graph') or {}).get('facts', []):
        if fact['kind'] == 'graph_cycle':
            found.append({'gate': 'cycle', 'where': fact['value']['members'][0], 'what': 'these files import each other in a loop: '
                          + ', '.join(fact['value']['members'][:6])})
    for fact in (sets.get('broken') or {}).get('facts', []):
        if fact['value'].get('severity') == 'high':
            found.append({'gate': 'broken', 'where': fact['location'].get('path'), 'what': fact['value']['message']})
    for fact in (sets.get('metrics') or {}).get('facts', []):
        if fact['kind'] != 'clone_cluster': continue
        places = [o for o in fact['value']['occurrences'] if not re.search(r'(\.test\.|/tests?/|e2e/|\.config\.)', o['path'])]
        if len(places) >= 2:
            found.append({'gate': 'copy', 'where': places[0]['path'], 'what': 'the same lines are written in '
                          + ', '.join(f"{o['path']}:{o['start_line']}" for o in places[:4]) + ': give them one home and call it'})
    if closing:
        for fact in (sets.get('deadcode') or {}).get('facts', []):
            found.append({'gate': 'dead', 'where': fact['location'].get('path'), 'what': fact['value'].get('message')})
    return found


def document(spec, stack, built):
    """BLUEPRINT.md: the plan's target in words a person reads."""
    plan, lines = built['plan'], [f"# {spec['name']}: the blueprint", '', spec['summary'], '', '## The parts', '']
    for module in spec['modules']:
        lines.append(f"- **{module['name']}**: {module.get('responsibility') or ''}")
    lines += ['', '## The technologies, and how to change each later', '', '| Concern | Chosen | Why | To change it later |', '| --- | --- | --- | --- |']
    for concern, row in stack.items():
        lines.append(f"| {row['title']} | {row['name']} | {row['why']} | {row['switch']} |")
    lines += ['', '## The rules the structure keeps', '']
    lines += [f"- {rule['reason']}" for rule in built['policy']['rules']]
    lines += [f"- Only {' and '.join(f'`{home}`' for home in v['only_in'])} use {', '.join(v['packages'])}." for v in built['policy']['vendors'].values()]
    lines += ['', '## The build, in order', '']
    for milestone in plan['milestones']:
        lines.append(f"### {milestone['id']} · {milestone['name']}")
        for card_id in milestone['tasks']:
            card = next(c for c in plan['tasks'] if c['id'] == card_id)
            lines.append(f"- {card_id}: {card['title']}")
        lines.append('')
    return '\n'.join(lines)


def page(spec, stack, built, progress=None):
    """BLUEPRINT.html: the blueprint for a person, in the look of the report for people (eaos/human_report.py),
    with every milestone's progress when `progress` (the state's `built` list) is given."""
    from html import escape
    from .human_report import CSS
    done = {card for record in progress or [] for card in record.get('kept') or []}
    delivered = {record['milestone']: record.get('branch') for record in progress or []}
    rtl = any('؀' <= ch <= 'ۿ' for ch in spec.get('name', '') + spec.get('summary', ''))
    parts = ''.join(f'<div class="card"><h4>{escape(m["name"])}</h4><p class="muted small">{escape(m.get("responsibility") or "")}</p>'
                    f'<p class="small">{escape(", ".join(f["name"] for f in spec["features"] if f.get("module") == m["id"]))}</p></div>'
                    for m in spec['modules'])
    rows = ''.join(f'<tr><td><b>{escape(row["title"])}</b></td><td>{escape(row["name"])}</td><td>{escape(row["why"])}</td>'
                   f'<td class="small">{escape(row["switch"])}</td></tr>' for row in stack.values())
    rules = ''.join(f'<li>{escape(rule["reason"])}</li>' for rule in built['policy']['rules'])
    cards = {c['id']: c for c in built['plan']['tasks']}
    stages = []
    for milestone in built['plan']['milestones']:
        ids = milestone['tasks']
        share = round(100 * sum(c in done for c in ids) / len(ids)) if ids else 0
        badge = ('✅ ' + escape(delivered[milestone['id']])) if milestone['id'] in delivered else f'{sum(c in done for c in ids)} / {len(ids)}'
        items = ''.join(f'<li>{"✅" if c in done else "⬜"} {escape(cards[c]["title"])}</li>' for c in ids)
        stages.append(f'<div class="card"><h4>{escape(milestone.get("name_ar") if rtl else milestone["name"])} '
                      f'<span class="muted small" data-meaning="cards built of this milestone">{badge}</span></h4>'
                      f'<div style="height:8px;background:var(--surface-2);border-radius:99px;overflow:hidden;margin:8px 0">'
                      f'<div style="width:{share}%;height:100%;background:var(--good)"></div></div><ul class="small">{items}</ul></div>')
    label = (lambda ar, en: ar if rtl else en)
    return f"""<!doctype html><html lang="{'ar' if rtl else 'en'}" dir="{'rtl' if rtl else 'ltr'}" data-lang="{'ar' if rtl else 'en'}">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(spec['name'])}</title>
<style>{CSS} .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px}} table{{width:100%;border-collapse:collapse}}
td,th{{border-bottom:1px solid var(--line);padding:10px;text-align:start;vertical-align:top}}</style></head>
<body><header class="top"><div class="wrap top-in"><div><div class="kicker">EAOS · {label('مخطط البناء', 'Blueprint')}</div>
<h1>{escape(spec['name'])}</h1></div></div></header><main class="wrap">
<p>{escape(spec['summary'])}</p>
<h3>{label('الأجزاء', 'The parts')}</h3><div class="grid">{parts}</div>
<h3>{label('التقنيات، ولماذا، وكيف تُغيَّر لاحقًا', 'The technologies, why, and how to change each later')}</h3>
<div class="card"><table><tr><th>{label('الجانب', 'Concern')}</th><th>{label('المختار', 'Chosen')}</th><th>{label('لماذا', 'Why')}</th><th>{label('لتغييره لاحقًا', 'To change it later')}</th></tr>{rows}</table></div>
<h3>{label('القواعد التي يحفظها الهيكل', 'The rules the structure keeps')}</h3><div class="card"><ul>{rules}</ul></div>
<h3>{label('البناء، مرحلة مرحلة', 'The build, milestone by milestone')}</h3><div class="grid">{''.join(stages)}</div>
</main></body></html>"""
