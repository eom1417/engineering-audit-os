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

from .reference_architecture import by_id, choose, layer_of

RULES = Path(__file__).resolve().parent / 'rules/disposition-rules.json'
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


def _load(path, default):
    try: return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError): return default


def _facts(out):
    by_kind = defaultdict(list)
    for path in sorted((Path(out) / 'facts').glob('*.json')):
        for fact in (_load(path, {}) or {}).get('facts') or []:
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
    placed = {}
    for path in files:
        layer, _ = layer_of(path, reference)
        if len(owners[path]) == 1 and layer in (feature_layer, None):
            placed[path] = (f"feature:{slug(owners[path][0])}", feature_layer)
        elif layer: placed[path] = (layer, layer)
        elif len(owners[path]) == 1: placed[path] = (f"feature:{slug(owners[path][0])}", feature_layer)
        else: placed[path] = (PLATFORM, PLATFORM)
    return placed


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
        if relation == 'delete' and stats['files'] and stats['unreachable'] / stats['files'] >= rule['unreachable_share_at_least']:
            return 'delete', f"{rule['why']} ({numbers})"
        if relation == 'rebuild' and (stats['moved_share'] > rule['moved_share_above'] or stats['complexity_max'] > rule['complexity_max_above']
                                      or (rule['critical_debt'] and stats['critical'])):
            return 'rebuild', f"{rule['why']} ({numbers})"
        if relation == 'retain' and (stats['moved_share'] <= rule['moved_share_at_most'] and stats['forbidden'] <= rule['forbidden_edges_at_most']
                                     and stats['complexity_max'] < rule['complexity_max_below']
                                     and stats['duplicated_lines'] < rule['duplicated_lines_below']):
            return 'retain', f"{rule['why']} ({numbers})"
        if relation == 'modify': return 'modify', f"{rule['why']} ({numbers})"
    return 'modify', numbers


def _tool(area, reference_id):
    choice = TOOLS.get(area)
    if isinstance(choice, dict):
        choice = choice.get(reference_id, choice.get(reference_id.split('-')[0], choice.get('')))
    return choice


def infrastructure(reference, facts, target, files):
    """One decision per baseline item (and hosting), each present or absent by evidence."""
    target = Path(target) if target else None
    exists = lambda *names: [n for n in names if target and (target / n).exists()]
    tests = [f for f in facts['source_file'] if (f.get('value') or {}).get('category') == 'test']
    env_files = sorted({f['location']['path'] for f in facts['env_read']})
    secrets = [f for f in facts['committed_credential'] if (f.get('value') or {}).get('severity') not in ('public', 'test')]
    tables = [f for f in facts['data_table'] if 'rls_enabled' in (f.get('value') or {})]
    observed = {
        'ci': (bool(facts['ci_step']), f"{len(facts['ci_step'])} CI step(s) in the repository"),
        'configuration': (len(env_files) <= 1, f"the environment is read in {len(env_files)} file(s)"
                          + (f": {', '.join(env_files[:4])}" if env_files else '')),
        'tests': (bool(tests), f"{len(tests)} test file(s)"),
        'observability': (bool(facts['observability_signal']), f"{len(facts['observability_signal'])} observability signal(s)"),
        'secrets': (not secrets, f"{len(secrets)} secret-class credential(s) committed"),
        'dependencies': (bool(exists('renovate.json', '.github/renovate.json', '.github/dependabot.yml')),
                         'renovate or dependabot configuration: ' + (', '.join(exists('renovate.json', '.github/renovate.json', '.github/dependabot.yml')) or 'none')),
        'migrations': (bool(exists('supabase/migrations', 'migrations', 'alembic', 'prisma/migrations')),
                       'migrations folder: ' + (', '.join(exists('supabase/migrations', 'migrations', 'alembic', 'prisma/migrations')) or 'none')),
        'identity': ((bool(tables) and all(f['value']['rls_enabled'] for f in tables)) if tables else False,
                     f"{sum(1 for f in tables if f['value']['rls_enabled'])} of {len(tables)} tables with row-level security"),
        'data': (any(re.search(r'(supabase/types\.ts|openapi\.(ya?ml|json)|schema\.prisma|alembic/)', p) for p in files),
                 'typed schema source: ' + (next((p for p in files if re.search(r'(supabase/types\.ts|openapi\.|schema\.prisma|alembic/)', p)), None) or 'none')),
        'backup': (any('backup' in p.lower() for p in files), 'backup code: ' + (next((p for p in files if 'backup' in p.lower()), None) or 'none')),
        'hosting': (bool(exists('vercel.json', 'netlify.toml', 'Dockerfile', 'fly.toml')),
                    'hosting configuration: ' + (', '.join(exists('vercel.json', 'netlify.toml', 'Dockerfile', 'fly.toml')) or 'none')),
    }
    rows = []
    items = list(reference['infrastructure_baseline'])
    # A desktop program or a command is not hosted; it is released as a build, which the ci item covers.
    if reference['id'].startswith(HOSTED) and not any(item['area'] == 'hosting' for item in items):
        items.append({'area': 'hosting', 'item': 'The deployment target is declared in the repository',
                      'reason': 'A host configured only in a dashboard cannot be rebuilt or reviewed.',
                      'success_measure': 'A clean checkout deploys with one documented command.'})
    for item in items:
        present, evidence = observed.get(item['area'], (False, 'no fact reads this area'))
        tool = _tool(item['area'], reference['id'])
        rows.append({'area': item['area'], 'present': bool(present),
                     'decision': (f"Keep: {item['item']}. The check: {item['success_measure']}" if present
                                  else f"Introduce: {item['item']}. Why: {item['reason']}"),
                     'tool': tool, 'tool_reason': None if tool else NO_TOOL.get(item['area'], 'no adopted tool fits this item'),
                     'evidence': evidence,
                     'alternative': f"Do nothing: {item['reason'][0].lower() + item['reason'][1:]}"})
    return rows


def project(out, target=None):
    """The whole projection for one report: reference, components, placements, dispositions, infrastructure."""
    out = Path(out)
    target = target or ((_load(out / 'dossier.json', {}) or {}).get('provenance') or {}).get('target')
    reference_id = choose(target) if target and Path(target).is_dir() else None
    if reference_id is None: return None
    reference = by_id(reference_id)
    facts = _facts(out)
    features = (_load(out / 'features.json', {}) or {}).get('features') or []
    nodes = {f['location']['path']: f['value'] for f in facts['graph_node']}
    files = sorted(nodes)
    placed = place(files, features, reference)
    edges = [(path, sink) for path, node in nodes.items() for sink in node.get('depends_on') or []]
    bad = forbidden(edges, placed, reference)
    measured = {row['path']: row for row in (_load(out / 'measurements.json', {}) or {}).get('files') or []}
    unreachable = {f['location']['path'] for f in facts['engine_finding'] if (f.get('value') or {}).get('rule') == 'unreachable-module'}
    critical = defaultdict(int)
    for item in (_load(out / 'debt-register.json', {}) or {}).get('items') or []:
        if item['severity'] == 'critical':
            for path in item['files']: critical[path] += 1

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
    by_component = defaultdict(list)
    for path, (component, _) in placed.items(): by_component[component].append(path)
    for name, component in components.items():
        members = sorted(by_component.get(name, []))
        component['files'] = len(members)
        component['moves_in'] = sum(moves(p, name, placed[p][1], reference) for p in members)
        component['forbidden_edges_removed'] = sum(1 for source, _ in bad if source in members)
        component['paths'] = members[:50]

    rules = json.loads(RULES.read_text(encoding='utf-8'))
    packages = defaultdict(list)
    for path in files: packages[package_of(path)].append(path)
    current = {}
    for package, members in packages.items():
        moved = sum(moves(p, placed[p][0], placed[p][1], reference) for p in members)
        stats = {'files': len(members), 'moved': moved, 'moved_share': moved / len(members),
                 'forbidden': sum(1 for source, _ in bad if source in members),
                 'complexity_max': max([measured.get(p, {}).get('complexity_max') or 0 for p in members] or [0]),
                 'duplicated_lines': sum(measured.get(p, {}).get('duplicated_lines') or 0 for p in members),
                 'unreachable': sum(1 for p in members if p in unreachable),
                 'critical': sum(critical[p] for p in members)}
        relation, reason = disposition(stats, rules)
        home = Counter(placed[p][0] for p in members).most_common(1)[0][0]
        current[package] = {'relation': relation, 'reason': reason, 'target_component': home, 'stats': stats}
    return {'reference': reference_id, 'target_components': sorted(components.values(), key=lambda c: c['name']),
            'placements': {p: c for p, (c, _) in placed.items()}, 'forbidden_edges': bad, 'current': current,
            'features': {f['name']: f"feature:{slug(f['name'])}" for f in features},
            'infrastructure': infrastructure(reference, facts, target, files)}
