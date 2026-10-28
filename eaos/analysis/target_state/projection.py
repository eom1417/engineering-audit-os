"""The target architecture: this project, with the same features, projected onto its reference type.

The default shape is a modular monolith (eaos/rules/reference-architectures.json): one target component per
feature in features.json, one per shared layer of the reference (ui, data-access, lib, config...), and a
platform component for what no code layer holds (build configuration, migrations, CI). A service outside
the one deployable needs a quality scenario that justifies it; none is proposed by default.

Every analysed file is placed: in its feature's component when exactly one feature uses it, otherwise in
the layer its path belongs to. A file moves when its current path is not where its target component
keeps files. An import is forbidden when the importing file's target layer may not depend on the
imported file's layer. Each of today's components (packages) then gets one disposition from
eaos/rules/disposition-rules.json, in its declared order, with the numbers that decided it:
delete, rebuild, retain, modify.

Infrastructure: every baseline item of the reference type is found present or absent from the facts,
with the evidence, a decision, the tool that fits (docs/TOOLCHAIN.md, role "recommends") or none with its
reason, and the cost of doing nothing.
"""
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from .references import by_id, layer_of, locate, rooted
from ...core.system.files import read_json

RULES = Path(__file__).resolve().parents[2] / 'rules/disposition-rules.json'
FEATURE_LAYERS = ('features', 'services', 'web', 'cli')
PLATFORM = 'platform'
TOOLS = {  # area -> (tool by reference id prefix, else default; None means no tool fits, with the reason)
    'ci': 'GitHub Actions + pre-commit',
    'dependencies': 'Renovate',
    'observability': {'python-desktop': None, 'python-cli': None, '': 'OpenTelemetry + SigNoz'},
    'tests': {'python': 'pytest + ApprovalTests', '': 'Playwright + Vitest'},
    'migrations': {'python': 'Alembic', 'react-tanstack-start-supabase': 'Supabase CLI', 'react-vite-supabase': 'Supabase CLI', '': None},
    'data': {'react-tanstack-start-supabase': 'supabase gen types', 'react-vite-supabase': 'supabase gen types',
             'react-vite-spa-rest': 'OpenAPI + oasdiff', 'nextjs-app': 'Prisma', '': None},
    'identity': {'react-tanstack-start-supabase': 'Supabase Auth + RLS', 'react-vite-supabase': 'Supabase Auth + RLS', '': None},
}
NO_TOOL = {'configuration': 'a code change: one typed settings module', 'secrets': "the host's own secret store",
           'backup': 'a feature of the application', 'data': 'a schema owner in code', 'migrations': 'the stack has no migration tool to add',
           'identity': 'a code change in the api-client',
           'observability': 'a local rotating log inside the application; there is no server to collect from'}
HOSTED = ('react-', 'nextjs', 'python-web')


# An architectural component is a package, not a symbol. Building one per symbol produced 10,938
# "components" on a 1,031-file repository, which is a symbol listing rather than an architecture.
PACKAGE_ROOT = ''


def package_of(path):
    """The architectural unit a file belongs to: its directory, or the root for a top-level file."""
    parent = str(Path(path).parent)
    return PACKAGE_ROOT if parent in ('.', '') else parent


def slug(text):
    return re.sub(r'[^a-z0-9]+', '-', str(text).lower()).strip('-') or 'root'


def facts_by_kind(out):
    by_kind = defaultdict(list)
    for path in sorted((Path(out) / 'facts').glob('*.json')):
        for fact in (read_json(path, {}) or {}).get('facts') or []:
            if isinstance(fact, dict): by_kind[fact.get('kind')].append(fact)
    return by_kind


def _feature_layer(reference):
    names = [layer['name'] for layer in reference['layers']]
    return next((name for name in FEATURE_LAYERS if name in names), names[0])


def _features_root(reference, layer_name):
    layer = next(l for l in reference['layers'] if l['name'] == layer_name)
    return layer['paths'][0].split('*')[0].rstrip('/')


def place(files, features, reference):
    """{path: (component name, layer)}: a file one feature uses goes to that feature; the rest to its layer."""
    owners = defaultdict(list)
    for feature in features:
        for path in feature.get('files') or []: owners[path].append(feature['name'])
    feature_layer = _feature_layer(reference)
    return {path: _placed(owners[path], layer_of(path, reference)[0], feature_layer) for path in files}


def _placed(owners, layer, feature_layer):
    """(component, layer) of one file: its one feature's, else its layer's, else the platform's."""
    if len(owners) == 1 and layer in (feature_layer, None): return f"feature:{slug(owners[0])}", feature_layer
    return (layer, layer) if layer else (PLATFORM, PLATFORM)


def moves(path, component, layer, reference):
    """Whether a file must move to reach its target component."""
    if component.startswith('feature:'):
        home = f"{_features_root(reference, layer)}/{component.split(':', 1)[1]}/"
        return not path.startswith(home)
    if component == PLATFORM: return False
    return layer_of(path, reference)[0] != layer


def forbidden(edges, placed, reference):
    """Imports whose importing file's target layer may not depend on the imported file's target layer."""
    allowed = {layer['name']: set(layer['allowed_dependencies']) for layer in reference['layers']}
    out = []
    for source, sink in edges:
        if source not in placed or sink not in placed: continue
        (_, a), (_, b) = placed[source], placed[sink]
        if a != b and a in allowed and b in allowed and b not in allowed[a]: out.append((source, sink))
    return out


def disposition(stats, rules):
    """(relation, reason with the numbers) for one of today's components."""
    numbers = (f"{stats['files']} file(s), {stats['moved']} to move ({stats['moved_share']:.0%}), "
               f"{stats['forbidden']} forbidden import(s), complexity_max {stats['complexity_max']}, "
               f"duplicated_lines {stats['duplicated_lines']}, {stats['unreachable']} unreachable, "
               f"{stats['critical']} critical debt item(s)")
    for relation in rules['order']:
        rule = rules[relation]
        holds = RELATION_HOLDS.get(relation)
        if holds and holds(stats, rule): return relation, f"{rule['why']} ({numbers})"
    return 'modify', numbers


def _deletes(stats, rule):
    return bool(stats['files']) and stats['unreachable'] / stats['files'] >= rule['unreachable_share_at_least']


def _rebuilds(stats, rule):
    # Rebuild needs a structural reason. Complexity alone, or a critical item, is changed in place (modify):
    # one function past the threshold sent a whole package to rebuild. Moving one or two files is a modify too.
    return stats['moved_share'] > rule['moved_share_above'] and stats['moved'] >= rule.get('moved_files_at_least', 1)


def _retains(stats, rule):
    return (stats['moved_share'] <= rule['moved_share_at_most'] and stats['forbidden'] <= rule['forbidden_edges_at_most']
            and stats['critical'] <= rule.get('critical_debt_at_most', 0)
            and stats['complexity_max'] < rule['complexity_max_below']
            and stats['duplicated_lines'] < rule['duplicated_lines_below'])


# relation -> whether a component's numbers call for it; 'modify' always does.
RELATION_HOLDS = {'delete': _deletes, 'rebuild': _rebuilds, 'retain': _retains, 'modify': lambda stats, rule: True}


def _tool(area, reference_id):
    choice = TOOLS.get(area)
    if isinstance(choice, dict):
        choice = choice.get(reference_id, choice.get(reference_id.split('-')[0], choice.get('')))
    return choice


MIGRATIONS = ('supabase/migrations', 'migrations', 'alembic', 'prisma/migrations', 'drizzle', 'server/migrations', 'db/migrations')
HOSTING = ('vercel.json', 'netlify.toml', 'Dockerfile', 'fly.toml', 'railway.json', 'railway.toml', 'Procfile', 'nixpacks.toml', 'render.yaml')


def infrastructure(reference, facts, target, files, prefix=''):
    """One decision per baseline item (and hosting), each present or absent by evidence. A file counts at the
    repository root or under the app root (a full-stack app keeps its app in app/ and its Dockerfile at the root)."""
    target = Path(target) if target else None
    observed = {**_observed_in_facts(facts), **_observed_in_files(_existing(target, prefix), files)}
    if not observed['data'][0] and (client := _typed_client(facts)): observed['data'] = (True, f'typed data client: {client}')
    return [_infrastructure_row(item, observed, reference['id']) for item in baseline_items(reference)]


DEPENDENCY_BOTS = ('renovate.json', '.github/renovate.json', '.github/dependabot.yml')


def _existing(target, prefix):
    """exists(*names): the names found at the repository root or under the app root."""
    def exists(*names):
        return [n for n in names for base in dict.fromkeys(('', prefix)) if target and (target / base / n).exists()]
    return exists


TYPED_CLIENTS = ('@prisma/client', 'drizzle-orm', 'kysely', 'sqlalchemy', 'sqlmodel')


def _typed_client(facts):
    """The typed data client the code imports (Drizzle's tables are its schema, in code), or None."""
    modules = {(f.get('value') or {}).get('module') or '' for f in facts.get('import_edge') or []}
    return next((client for client in TYPED_CLIENTS if any(m == client or m.startswith(client + '/') for m in modules)), None)


def _observed_in_facts(facts):
    tests = [f for f in facts['source_file'] if (f.get('value') or {}).get('category') == 'test']
    env_files = sorted({f['location']['path'] for f in facts['env_read']})
    return {
        'ci': (bool(facts['ci_step']), f"{len(facts['ci_step'])} CI step(s) in the repository"),
        'configuration': (len(env_files) <= 1, f"the environment is read in {len(env_files)} file(s)"
                          + (f": {', '.join(env_files[:4])}" if env_files else '')),
        'tests': (bool(tests), f"{len(tests)} test file(s)"),
        'observability': (bool(facts['observability_signal']), f"{len(facts['observability_signal'])} observability signal(s)"),
        'secrets': _secrets_item(facts),
        'identity': _identity_item(facts),
    }


def _secrets_item(facts):
    """(present, evidence) of the secrets item: no secret-class credential is committed."""
    secrets = [f for f in facts['committed_credential'] if (f.get('value') or {}).get('severity') not in ('public', 'test')]
    return not secrets, f"{len(secrets)} secret-class credential(s) committed"


def _identity_item(facts):
    """(present, evidence) of the identity item: every table declares row-level security."""
    tables = [f for f in facts['data_table'] if 'rls_enabled' in (f.get('value') or {})]
    return (bool(tables) and all(f['value']['rls_enabled'] for f in tables),
            f"{sum(1 for f in tables if f['value']['rls_enabled'])} of {len(tables)} tables with row-level security")


def _observed_in_files(exists, files):
    bots, migrations, hosting = exists(*DEPENDENCY_BOTS), exists(*MIGRATIONS), exists(*HOSTING)
    return {
        'dependencies': (bool(bots), 'renovate or dependabot configuration: ' + (', '.join(bots) or 'none')),
        'migrations': (bool(migrations), 'migrations folder: ' + (', '.join(migrations) or 'none')),
        **_observed_in_code(files),
        'hosting': (bool(hosting), 'hosting configuration: ' + (', '.join(hosting) or 'none')),
    }


def _observed_in_code(files):
    """The data and backup items: a typed schema source, and code that backs the data up."""
    schema = next((p for p in files if re.search(r'(supabase/types\.ts|openapi\.|schema\.prisma|alembic/)', p)), None)
    backup = next((p for p in files if 'backup' in p.lower()), None)
    return {'data': (any(re.search(r'(supabase/types\.ts|openapi\.(ya?ml|json)|schema\.prisma|alembic/)', p) for p in files),
                     'typed schema source: ' + (schema or 'none')),
            'backup': (any('backup' in p.lower() for p in files), 'backup code: ' + (backup or 'none'))}


def baseline_items(reference):
    items = list(reference['infrastructure_baseline'])
    # A desktop program or a command is not hosted; it is released as a build, which the ci item covers.
    if reference['id'].startswith(HOSTED) and not any(item['area'] == 'hosting' for item in items):
        items.append({'area': 'hosting', 'item': 'The deployment target is declared in the repository',
                      'reason': 'A host configured only in a dashboard cannot be rebuilt or reviewed.',
                      'success_measure': 'A clean checkout deploys with one documented command.'})
    return items


def _infrastructure_row(item, observed, reference_id):
    present, evidence = observed.get(item['area'], (False, 'no fact reads this area'))
    tool = _tool(item['area'], reference_id)
    return {'area': item['area'], 'present': bool(present),
            'decision': (f"Keep: {item['item']}. The check: {item['success_measure']}" if present
                         else f"Introduce: {item['item']}. Why: {item['reason']}"),
            'tool': tool, 'tool_reason': None if tool else NO_TOOL.get(item['area'], 'no adopted tool fits this item'),
            'evidence': evidence,
            'alternative': f"Do nothing: {item['reason'][0].lower() + item['reason'][1:]}"}


def project(out, target=None):
    """The whole projection for one report: reference, components, placements, dispositions, infrastructure."""
    out = Path(out)
    target, reference_id, prefix = _reference_of(out, target)
    if reference_id is None: return None
    reference = rooted(by_id(reference_id), prefix)
    facts = facts_by_kind(out)
    features = (read_json(out / 'features.json', {}) or {}).get('features') or []
    nodes = {f['location']['path']: f['value'] for f in facts['graph_node']}
    files = sorted(nodes)
    placed = place(files, features, reference)
    edges = [(path, sink) for path, node in nodes.items() for sink in node.get('depends_on') or []]
    bad = forbidden(edges, placed, reference)
    known = _known(out, facts)
    components = _target_components(features, placed, reference, reference_id)
    _fill_components(components, placed, bad, reference)
    return {'reference': reference_id, 'root': prefix, 'target_components': sorted(components.values(), key=lambda c: c['name']),
            'target_edges': _target_edges(edges, placed, bad),
            'placements': {p: c for p, (c, _) in placed.items()}, 'forbidden_edges': bad,
            'current': _current_packages(files, placed, reference, bad, known),
            'infrastructure': infrastructure(reference, facts, target, files, prefix)}


def _known(out, facts):
    """What decides a package's disposition beside its placement: each file's measurements, the unreachable modules,
    the critical debt items per file."""
    return {'measured': {row['path']: row for row in (read_json(out / 'measurements.json', {}) or {}).get('files') or []},
            'unreachable': {f['location']['path'] for f in facts['engine_finding'] if (f.get('value') or {}).get('rule') == 'unreachable-module'},
            'critical': _critical_by_file(out)}


def _reference_of(out, target):
    """(the target folder, its reference type, its app root); the type is None when the target is not a folder."""
    target = target or ((read_json(out / 'dossier.json', {}) or {}).get('provenance') or {}).get('target')
    reference_id, prefix = locate(target) if target and Path(target).is_dir() else (None, '')
    return target, reference_id, prefix


def _critical_by_file(out):
    critical = defaultdict(int)
    items = (read_json(out / 'debt-register.json', {}) or {}).get('items') or []
    for item in (item for item in items if item['severity'] == 'critical'):
        for path in item['files']: critical[path] += 1
    return critical


def _target_components(features, placed, reference, reference_id):
    """One component per feature, then one per layer (or the platform) a file is placed in."""
    layers = {layer['name']: layer for layer in reference['layers']}
    feature_layer = _feature_layer(reference)
    components = {}
    for feature in features:
        components[f"feature:{slug(feature['name'])}"] = {
            'name': f"feature:{slug(feature['name'])}", 'layer': feature_layer, 'reference': reference_id,
            'responsibility': f"{feature['name']}: {feature.get('description') or 'one feature of the program'}",
            'feature': feature['name']}
    for name in sorted({c for c, _ in placed.values()} - set(components)):
        layer = layers.get(name)
        components[name] = {'name': name, 'layer': name if layer else PLATFORM, 'reference': reference_id,
                            'responsibility': layer['responsibility'] if layer else
                            'Build, deployment and repository configuration: what no code layer holds'}
    return components


def _fill_components(components, placed, bad, reference):
    by_component = defaultdict(list)
    for path, (component, _) in placed.items(): by_component[component].append(path)
    for name, component in components.items():
        members = sorted(by_component.get(name, []))
        component['files'] = len(members)
        component['moves_in'] = sum(moves(p, name, placed[p][1], reference) for p in members)
        component['forbidden_edges_removed'] = sum(1 for source, _ in bad if source in members)
        component['paths'] = members[:50]


def _measured_stats(members, measured):
    """A package's largest file complexity and its lines copied elsewhere."""
    return {'complexity_max': max([measured.get(p, {}).get('complexity_max') or 0 for p in members] or [0]),
            'duplicated_lines': sum(measured.get(p, {}).get('duplicated_lines') or 0 for p in members)}


def _package_stats(members, placed, reference, bad, known):
    moved = sum(moves(p, placed[p][0], placed[p][1], reference) for p in members)
    return {'files': len(members), 'moved': moved, 'moved_share': moved / len(members),
            'forbidden': sum(1 for source, _ in bad if source in members), **_measured_stats(members, known['measured']),
            'unreachable': sum(1 for p in members if p in known['unreachable']),
            'critical': sum(known['critical'][p] for p in members)}


def _current_packages(files, placed, reference, bad, known):
    """Each of today's packages: what happens to it, why, and the target component most of its files go to."""
    rules = json.loads(RULES.read_text(encoding='utf-8'))
    packages = defaultdict(list)
    for path in files: packages[package_of(path)].append(path)
    current = {}
    for package, members in packages.items():
        stats = _package_stats(members, placed, reference, bad, known)
        relation, reason = disposition(stats, rules)
        home = Counter(placed[p][0] for p in members).most_common(1)[0][0]
        current[package] = {'relation': relation, 'reason': reason, 'target_component': home, 'stats': stats}
    return current


def _target_edges(edges, placed, bad):
    # The target's own dependencies: imports between different target components that the layer rules allow.
    refused = set(bad)
    flows = Counter((placed[a][0], placed[b][0]) for a, b in edges
                    if a in placed and b in placed and placed[a][0] != placed[b][0] and (a, b) not in refused)
    return [{'from': a, 'to': b, 'imports': n} for (a, b), n in sorted(flows.items())]
