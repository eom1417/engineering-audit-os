"""Build a project from its plan (docs/BUILD-FROM-PLAN.md): the target structure first, then the build as cards.

An audit reads what exists, draws the target, and plans the way from one to the other. A project that exists only
as a plan (a PRD, notes, a pasted text) has no current state: the target is drawn from the plan itself, and the gap
is the whole build. EAOS lays it out so that what its audits look for never gets in:

  read_plan       any plan the person has (Markdown, text, PDF, Word, HTML, pasted words, a folder of them, and pictures
                  of its screens), eaos/analysis/plan_source.py.
  validate_spec   the product spec the assistant writes from it (SPEC, eaos/report/blueprint_spec.py): every feature has
                  a module, its data and a way to check it; every piece of data has one owner. What is missing or
                  undecided comes back as questions with choices, for the assistant to research, recommend, and ask.
  choose_stack    one option per concern from eaos/data/stacks.json: the person's preference, else the recommendation.
  design          the target architecture (layers, one home per concept, each vendor behind one adapter folder), the
                  project's own eaos.policy.json, and plan.json: milestones of build cards, each with its files,
                  acceptance and tests, in the order that lets each card use only what exists.
The gates after every card are the ones every change passes (eaos/analysis/gates.py), held to the policy `design` drew.

Nothing here calls a model: the assistant reads, researches and writes; EAOS gives the shape and the gates.
"""
import re

from .blueprint_spec import SPEC, _applicable, _nonfunctional, answer, stacks, validate_spec  # noqa: F401  (SPEC, answer, validate_spec: read here by others)

ISOLATED = ('database', 'auth')          # concerns whose packages only their adapter folder may import
LINE_BUDGET = {'skeleton': 250, 'foundation': 200, 'module': 250, 'feature': 200, 'flow': 150, 'release': 200}


# ---------------------------------------------------------------- 3b. the cards every product needs (data/product-standard.json)

def standard_cards(spec, stack, stage):
    """The standard cards of one stage (foundation | release), their words filled from the spec and the stack."""
    nf, server = _nonfunctional(spec), stack['api']['id'] != 'none'
    out = []
    for row, entry, key in _applicable(spec):
        if row['stage'] != stage: continue
        words = {'name': entry.get('name') or entry.get('id', ''), 'id': slug(entry.get('id', '')), 'users': nf.get('expected_users'),
                 'adapter': adapter_folder(stack, slug(entry.get('id', ''))), 'languages': ', '.join(map(str, nf.get('languages') or []))}
        fill = lambda texts: [str(text).format(**words) for text in texts]
        out.append({'key': key, 'title': fill([row['title']])[0], 'acceptance': fill(row['acceptance']),
                    'paths': fill(row['paths'] + (row.get('server_paths', []) if server else [])),
                    'tests': fill(row['tests'] + (row.get('server_tests', []) if server else []))})
    return out


# ---------------------------------------------------------------- 3. the stack

def choose_stack(spec, chosen=None):
    """{concern: {'id', 'name', 'why', 'switch', 'packages', 'alternatives'}}: the person's choice, their plan's
    preference, else the recommendation; a database or sign-in the plan does not need is 'none'."""
    catalogue = stacks()['concerns']
    wanted = {**(spec.get('stack_preferences') or {}), **(chosen or {})}
    needs = {'database': bool(spec.get('entities')),
             'auth': bool(spec.get('roles')) or any(f.get('roles') for f in spec.get('features') or [])}
    stack = {concern: _option(entry, _pick(concern, entry, wanted, needs)) for concern, entry in catalogue.items()}
    if stack['database']['id'] == 'supabase' and not wanted.get('api'):
        stack['api'] = {**stack['api']}                  # a server still holds the rules; Supabase is its database
    return stack


def _pick(concern, entry, wanted, needs):
    """One concern's option: the one wanted, else the recommendation; none for a database or sign-in not needed
    (`needs`) and not wanted."""
    pick = wanted.get(concern) if wanted.get(concern) in entry['options'] else entry['recommended']
    if concern in needs and not needs[concern] and not wanted.get(concern): return 'none'
    return pick


def _option(entry, pick):
    """The stack's row for one concern: the option picked, why, how to switch later, its packages and the others."""
    option = entry['options'][pick]
    return {'id': pick, 'name': option['name'], 'why': option['why'], 'switch': option['switch'],
            'packages': option['packages'], 'title': entry['title'],
            'alternatives': [{'id': key, 'name': other['name'], 'why': other['why']}
                             for key, other in entry['options'].items() if key != pick]}


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
    entities = spec.get('entities') or []
    cards = _Cards()
    look = spec.get('look') or {}
    foundations = _foundations(cards, stack, look, standard_cards(spec, stack, 'foundation'))
    ordered, uses = _module_order(spec['modules'], spec['features'], entities)
    last_of = {}
    for index, module in enumerate(ordered, start=3):
        base = [foundations[-1]] + [last_of[other] for other in sorted(uses[module['id']]) if other in last_of]
        last_of[module['id']] = _module_cards(cards, f'M{index:02d}', module, base, spec['features'], entities, stack, look)
    flows = spec.get('flows') or []
    _journey_cards(cards, flows, ordered, last_of)
    # The last milestone, once the product exists: what makes it ready to release (accessibility, speed, load, CI).
    release = f'M{len(ordered) + 3 + bool(flows):02d}'
    for row in standard_cards(spec, stack, 'release'):
        cards.add(release, 'release', row['title'], None, row['paths'], row['acceptance'], row['tests'], [cards[-1]['id']], source=row['key'])
    _covers(cards, spec)
    return {'architecture': target(spec, stack, ordered), 'policy': policy(stack),
            'plan': {'contract_version': 1, 'kind': 'blueprint', 'tasks': cards, 'milestones': _milestones(cards, ordered, flows, release), 'waves': [],
                     'sections': [], 'decisions': []}}


def _journey_cards(cards, flows, ordered, last_of):
    """The journeys' milestone: every journey end to end in a real browser, after the last module."""
    for flow in flows:
        cards.add(f'M{len(ordered) + 3:02d}', 'flow', f"Journey: {flow['name']}", None, ['e2e/'],
                  [f"a {flow.get('actor') or 'user'} completes it in the browser: " + ' → '.join(map(str, flow.get('steps') or []))[:400]],
                  [f"e2e/{slug(flow['name'])[:40]}.spec.ts"], [last_of[m['id']] for m in ordered if m['id'] in last_of][-1:],
                  source=flow.get('id'))


class _Cards(list):
    """The build's cards in order: each one added gets the next number."""

    def add(self, milestone, kind, title, module, paths, acceptance, tests, depends=(), feature=None, why='', source=None):
        row = {'id': f'BLD-{len(self) + 1:03d}', 'kind': 'build', 'pattern': f'build_{kind}', 'milestone': milestone, 'title': title,
               'module': module, 'paths': paths, 'acceptance': acceptance, 'tests': tests, 'depends_on': list(depends),
               'feature': feature, 'source': source or feature, 'why': why, 'budget_lines': LINE_BUDGET[kind],
               'decision': {'kind': 'build', 'readiness': 'ready'}, 'status': 'planned'}
        self.append(row)
        return row['id']


def _covers(cards, spec):
    """Each card names the plan's requirements it builds (requirements[].covered_by: its feature, flow or standard key)."""
    for card in cards:
        card['covers'] = [r['id'] for r in spec.get('requirements') or [] if isinstance(r, dict) and card['source'] in (r.get('covered_by') or [])]


def _foundations(cards, stack, look, standard):
    """M01, the skeleton, and M02, one home for each shared concept and the standard foundations every product needs
    (languages, privacy, security...): their card ids, the skeleton first, the app shell last."""
    server = stack['api']['id'] != 'none'
    # M01: the skeleton, with every check running from the first commit.
    skeleton = cards.add('M01', 'skeleton', 'The project skeleton: workspaces, strict TypeScript, lint, tests, and one smoke test per part', None,
                    ['package.json', 'tsconfig.base.json', 'eslint.config.js', '.gitignore', 'shared/', 'web/'] + (['server/'] if server else []),
                    ['npm install, then npm run typecheck, npm run lint and npm test all pass at the root',
                     'npm run e2e runs the browser journeys (Playwright, its webServer starting the app), so the last milestone '
                     'proves every journey in a real browser',
                     'the web app shows its shell page' + ('; the server answers GET /health with ok' if server else '')],
                    ['web/src/app/app.test.tsx'] + (['server/src/main.test.ts'] if server else []),
                    why='Every later card is checked by these scripts, so they exist before any feature.')
    # M02: one home for each shared concept, so nothing is written twice later.
    foundations = [skeleton]
    foundations.append(cards.add('M02', 'foundation', 'One home for errors and input validation', None,
                            ['shared/src/errors.ts', 'shared/src/validation.ts'],
                            ['every error the app shows has one type and one place that builds it',
                             'input is validated by the one schema helper, on the server and in the screens alike'],
                            ['shared/src/validation.test.ts'], [skeleton],
                            why='Validation and errors are where copied code starts; one home keeps them single.'))
    if server:
        foundations.append(cards.add('M02', 'foundation', 'One home for configuration', None, ['server/src/config.ts'],
                                ['the environment is read once, typed, in config.ts; nothing else reads process.env',
                                 'a missing required value stops the server at start with its name'],
                                ['server/src/config.test.ts'], [skeleton]))
    if stack['database']['id'] != 'none':
        foundations.append(cards.add('M02', 'foundation', f"The database adapter ({stack['database']['name']})", None,
                                [adapter_folder(stack, 'database')],
                                ['the connection and migrations live only in the database adapter folder',
                                 'a repository port is declared in application/ and implemented here'],
                                [adapter_folder(stack, 'database') + 'database.test.ts'], [skeleton],
                                why='Only this folder knows the database, so changing it later is replacing one folder.'))
    if stack['auth']['id'] != 'none':
        foundations.append(cards.add('M02', 'foundation', f"Sign-in ({stack['auth']['name']})", None,
                                [adapter_folder(stack, 'auth'), 'web/src/features/auth/'] + (['server/src/interface/http/auth/'] if server else []),
                                ['a person can sign up, sign in and sign out',
                                 'one function answers who the current user is, and every protected route uses it'],
                                ['web/src/features/auth/auth.test.tsx'], foundations[-1:] if stack['database']['id'] != 'none' else [skeleton]))
    foundations += [cards.add('M02', 'foundation', row['title'], None, row['paths'], row['acceptance'], row['tests'], [skeleton],
                              source=row['key']) for row in standard]
    foundations.append(_shell(cards, look, foundations))
    return foundations


def _shell(cards, look, foundations):
    """The app shell, the shared look and the one server client: the last foundation, after every other one."""
    tokens = ', '.join(f'{name} {value}' for name, value in (look.get('colors') or {}).items())
    return cards.add('M02', 'foundation', 'The app shell, the shared look and the one server client', None,
                     ['web/src/app/', 'web/src/ui/', 'web/src/api/'],
                     ['web/DESIGN.md is the spec\'s look.design_md; the shared components come from shadcn/ui through its '
                      'CLI (rtl true when the app speaks Arabic) and the fonts from Fontsource, served by the app',
                      'every screen works at 375 px wide first, with touch targets of 44 px, logical start/end layout and '
                      'text contrast of 4.5:1 in light and dark (eaos/data/design.json)',
                      'every screen uses the shared components in web/src/ui (' + ', '.join(look.get('components') or
                      ['buttons', 'inputs', 'forms', 'tables', 'messages']) + ')',
                      f"the one {look.get('theme') or 'light'} theme is design tokens in web/src/ui/theme.css" + (f' ({tokens})' if tokens else '')
                      + (f" with the fonts {', '.join(look['fonts'])}" if look.get('fonts') else '') + '; no screen sets its own colour or font',
                      'every call to the server goes through web/src/api'],
                     ['web/src/ui/ui.test.tsx'], foundations)


def _module_order(modules, features, entities):
    """M03…: one milestone per module, in the order its data allows: owners of data another module uses come first.
    (the modules in that order, {module: the modules whose data it uses})."""
    uses = _uses(modules, features, entities)
    ordered, placed = [], set()
    while len(ordered) < len(modules):
        ready = [m for m in modules if m['id'] not in placed and uses[m['id']] <= placed] or \
                [m for m in modules if m['id'] not in placed][:1]           # a cycle between modules: the plan breaks it in order
        for m in ready: ordered.append(m); placed.add(m['id'])
    return ordered, uses


def _uses(modules, features, entities):
    """{module: the other modules whose data its features use}."""
    uses = {m['id']: set() for m in modules}
    owner = {e['id']: e['module'] for e in entities}
    for feature in features:
        for entity_id in feature.get('entities') or []:
            if owner.get(entity_id) not in (None, '', feature['module']): uses[feature['module']].add(owner[entity_id])
    return uses


def _module_cards(cards, mid, module, base, features, entities, stack, look):
    """A module's milestone: its data card when it owns data, then a card per feature, each after the one before.
    The id of its last card, which later modules wait for."""
    owned = [e for e in entities if e['module'] == module['id']]
    data_card = _data_card(cards, mid, module, owned, base, stack) if owned else None
    previous = data_card or base[-1]
    for feature in [f for f in features if f['module'] == module['id']]:
        previous = _feature_card(cards, mid, module, feature, _after(previous, data_card), stack, _screens_of(look, feature))
    return previous


def _after(previous, data_card):
    """What a feature card waits for: the card before it, and its module's data card."""
    return [previous] + ([data_card] if data_card and data_card != previous else [])


def _screens_of(look, feature):
    """The screens of the look that show a feature."""
    return [x for x in look.get('screens') or [] if feature['id'] in (x.get('features') or [])]


def _data_card(cards, mid, module, owned, base, stack):
    folder = slug(module['id'])
    paths = [f'shared/src/{folder}/'] + ([f'server/src/domain/{folder}/', f'server/src/application/{folder}/'] if stack['api']['id'] != 'none' else [])
    if stack['database']['id'] != 'none': paths.append(adapter_folder(stack, 'database') + f'{folder}.ts')
    return cards.add(mid, 'module', f"{module['name']}: its data and rules ({', '.join(e['name'] for e in owned)})", module['id'], paths,
                     [f"{e['name']} is defined once (shared types and one schema), stored by this module's repository only" for e in owned]
                     + [f"only the {module['name']} module writes {', '.join(e['name'] for e in owned)}; others ask it"],
                     [f'shared/src/{folder}/{folder}.test.ts'], base,
                     why='The data has one owner: other modules call it rather than touching its tables.')


def _feature_card(cards, mid, module, feature, depends, stack, screens):
    server = stack['api']['id'] != 'none'
    folder, fslug = slug(module['id']), slug(feature['name'])[:40]
    paths = [f'web/src/features/{folder}/{fslug}/'] + ([f'server/src/application/{folder}/{fslug}.ts', f'server/src/interface/http/{folder}/'] if server else [])
    looks = [f"the screen {x['name']} follows its picture {x['picture']}, with the shared look only" if x.get('picture') else
             f"the screen {x['name']} is built from the shared look only" for x in screens]
    return cards.add(mid, 'feature', f"{module['name']}: {feature['name']}", module['id'], paths,
                     list(feature.get('acceptance') or []) + looks, [f'web/src/features/{folder}/{fslug}/{fslug}.test.tsx']
                     + ([f'server/src/application/{folder}/{fslug}.test.ts'] if server else []),
                     depends, feature=feature['id'], why=feature.get('description') or '')


def _milestones(cards, ordered, flows, release):
    """The plan's milestones, each with its cards: the skeleton, the foundations, one per module, the journeys, and
    what makes the product ready to release."""
    names = {'M01': ('الهيكل', 'The skeleton'), 'M02': ('الأساسات المشتركة', 'Shared foundations')}
    for index, module in enumerate(ordered, start=3): names[f'M{index:02d}'] = (module['name'], module['name'])
    if flows: names[f'M{len(ordered) + 3:02d}'] = ('الرحلات كاملة', 'Journeys end to end')
    names[release] = ('جاهز للإطلاق', 'Ready to release')
    milestones = []
    for mid, (ar, en) in names.items():
        ids = [c['id'] for c in cards if c['milestone'] == mid]
        if ids: milestones.append({'id': mid, 'name': en, 'name_ar': ar, 'tasks': ids,
                                   'goal': f'{en}: built, every card through its gates.', 'exit': 'every card here passes its gates and its tests'})
    return milestones


def target(spec, stack, modules):
    """target-architecture.json for a project not built yet, in the shape a check writes (target_architecture.document):
    the policy's layers are the target's parts, each with what it may use; the plan's modules, and the adapter that keeps
    each vendor in one place, are listed beside them. Nothing exists yet, so every part is to be built."""
    from .target_architecture import document
    server, drawn = stack['api']['id'] != 'none', policy(stack)
    reasons = {rule['allow_only']['from']: rule['reason'] for rule in drawn['rules']}
    layers = [{'id': f'TL-{name}', 'name': name, 'layer': name, 'kind': 'layer', 'relation': 'build', 'files': 0, 'paths': globs,
               'responsibility': reasons.get(name, '')} for name, globs in drawn['layers'].items() if not name.startswith('_')]
    parts = [_module_part(module, server) for module in modules]
    parts += [{'id': f'T-{concern}', 'name': stack[concern]['name'], 'kind': 'adapter', 'relation': 'build',
               'responsibility': f'the only place that uses {stack[concern]["name"]}', 'paths': [adapter_folder(stack, concern)],
               'files': 0, 'reason': stack[concern]['switch']} for concern in ISOLATED if stack[concern]['id'] != 'none']
    decided = [{'id': f'ADR-{concern}', 'concern': stack[concern]['title'], 'chosen': stack[concern]['name'], 'why': stack[concern]['why'],
                'alternatives': stack[concern]['alternatives'], 'how_to_change_later': stack[concern]['switch']} for concern in stack]
    edges = [{'from': rule['allow_only']['from'], 'to': to} for rule in drawn['rules'] for to in rule['allow_only']['to']]
    return document([], layers, decided, [], limits='A target drawn from a plan: nothing exists yet, so every part is to be built.',
                    status='blueprint', parts=parts, target_edges=edges, forbidden_edges=0)


def _module_part(module, server):
    """One module of the plan as a part of the target: its folders on each side, to be built."""
    folder = slug(module['id'])
    paths = [f'shared/src/{folder}/', f'web/src/features/{folder}/'] + ([f'server/src/domain/{folder}/', f'server/src/application/{folder}/',
                                                                        f'server/src/interface/http/{folder}/'] if server else [])
    return {'id': f'T-{folder}', 'name': module['name'], 'kind': 'module', 'relation': 'build',
            'responsibility': module.get('responsibility') or '', 'paths': paths, 'files': 0,
            'reason': 'A part of the product with one responsibility (from the plan).'}
