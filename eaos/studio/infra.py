"""studio/infra.json: where the project runs and what it depends on outside its code, today and in the target.

Read only from records the check already wrote; a lane EAOS has no reader for says so instead of looking empty.

    hosting        facts/runtime.json deployment_target: Dockerfile ports, compose services, hosting manifests
    ci             facts/runtime.json ci_step, by workflow file (GitHub Actions) or package.json scripts
    environments   facts/config.json env_read (variable names, never values; secret-shaped ones counted), the
                   sensitive files no extractor reads, and environments named by the hosts the code calls
                   (`*-staging.*`, `*-production.*`)
    databases      Supabase calls (facts/entrypoints.json data_access), database client packages
                   (facts/resolve.json module_edge EXTERNAL), tables declared in code (facts/domain.json data_table)
                   and migrations (facts/runtime.json migration_step), connection pools
    queues         queue client packages the code imports; none found is a measured empty lane, read only against
                   the packages listed in PACKAGES
    services       outbound hosts (facts/runtime.json integration_target, with its resilience_policy) and service
                   SDK packages
    observability  facts/runtime.json observability_signal, and telemetry packages

The target is target-architecture.json `infrastructure`: per area, present or not, and the decision (keep or
introduce) with its tool. A lane the target says nothing about is "not measured yet" for the target, never "fine".
Files the scan classes as tests are left out: a fixture's Dockerfile is not where the project runs.
"""
import re
from collections import defaultdict
from pathlib import Path

from .. import arch_map

LANES = ('hosting', 'ci', 'environments', 'databases', 'queues', 'services', 'observability')
RELATION = {'hosting': 'deployed_to', 'ci': 'built_by', 'environments': 'configured_by', 'databases': 'stores_in',
            'queues': 'queues_on', 'services': 'calls', 'observability': 'reports_to'}
# The target's infrastructure areas (eaos/target_projection.py) in the lane each belongs to.
AREA_LANE = {'hosting': 'hosting', 'ci': 'ci', 'tests': 'ci', 'dependencies': 'ci', 'configuration': 'environments',
             'secrets': 'environments', 'identity': 'environments', 'data': 'databases', 'migrations': 'databases',
             'backup': 'databases', 'observability': 'observability'}
# Packages that name a piece of infrastructure: (lane, name). Matched on the package's own name, or its scope.
PACKAGES = {
    '@supabase/supabase-js': ('databases', 'Supabase'), 'pg': ('databases', 'PostgreSQL'), 'postgres': ('databases', 'PostgreSQL'),
    'psycopg2': ('databases', 'PostgreSQL'), 'psycopg': ('databases', 'PostgreSQL'), 'asyncpg': ('databases', 'PostgreSQL'),
    'mysql2': ('databases', 'MySQL'), 'mysql': ('databases', 'MySQL'), 'pymysql': ('databases', 'MySQL'),
    'mongodb': ('databases', 'MongoDB'), 'mongoose': ('databases', 'MongoDB'), 'pymongo': ('databases', 'MongoDB'),
    'redis': ('databases', 'Redis'), 'ioredis': ('databases', 'Redis'), '@upstash/redis': ('databases', 'Redis'),
    'better-sqlite3': ('databases', 'SQLite'), 'sqlite3': ('databases', 'SQLite'), '@prisma/client': ('databases', 'Prisma'),
    'drizzle-orm': ('databases', 'Drizzle ORM'), 'sqlalchemy': ('databases', 'SQLAlchemy'), 'firebase-admin': ('databases', 'Firebase'),
    'bullmq': ('queues', 'BullMQ'), 'bull': ('queues', 'Bull'), 'bee-queue': ('queues', 'Bee-Queue'), 'amqplib': ('queues', 'RabbitMQ'),
    'pika': ('queues', 'RabbitMQ'), 'kafkajs': ('queues', 'Kafka'), 'kafka': ('queues', 'Kafka'), '@aws-sdk/client-sqs': ('queues', 'Amazon SQS'),
    '@google-cloud/pubsub': ('queues', 'Google Pub/Sub'), 'celery': ('queues', 'Celery'), 'rq': ('queues', 'RQ'), 'dramatiq': ('queues', 'Dramatiq'),
    'nats': ('queues', 'NATS'), '@upstash/qstash': ('queues', 'QStash'), 'inngest': ('queues', 'Inngest'), '@trigger.dev/sdk': ('queues', 'Trigger.dev'),
    'stripe': ('services', 'Stripe'), 'openai': ('services', 'OpenAI'), '@anthropic-ai/sdk': ('services', 'Anthropic'), 'anthropic': ('services', 'Anthropic'),
    'resend': ('services', 'Resend (email)'), '@sendgrid/mail': ('services', 'SendGrid (email)'), 'nodemailer': ('services', 'SMTP email'),
    'twilio': ('services', 'Twilio'), '@googlemaps/js-api-loader': ('services', 'Google Maps'), 'firebase': ('services', 'Firebase'),
    'boto3': ('services', 'AWS'), '@aws-sdk': ('services', 'AWS'), '@lovable.dev': ('services', 'Lovable Cloud'), 'posthog-js': ('services', 'PostHog'),
    '@opentelemetry': ('observability', 'OpenTelemetry'), 'opentelemetry': ('observability', 'OpenTelemetry'),
    '@sentry': ('observability', 'Sentry'), 'sentry_sdk': ('observability', 'Sentry'), 'prom-client': ('observability', 'Prometheus'),
    'prometheus_client': ('observability', 'Prometheus'), 'pino': ('observability', 'Pino (logs)'), 'winston': ('observability', 'Winston (logs)'),
}
# Hosts in code that are names, not services the project calls: XML namespaces, documentation examples.
NOT_SERVICES = re.compile(r'(^|\.)(w3\.org|example\.(com|org|net)|schema\.org|xmlsoap\.org|purl\.org|json-schema\.org)$|^\.+$|[${}]')
ENVIRONMENT = re.compile(r'(?:^|[-.])(production|prod|staging|stage|preview|dev|development|test|qa)(?:[-.]|$)')
ENV_WORD = {'prod': 'production', 'stage': 'staging', 'dev': 'development'}
TEST_PATH = re.compile(r'(^|/)(tests?|__tests__|spec|fixtures?|e2e)/|\.(test|spec)\.[a-z]+$|(^|/)test_[^/]+\.py$')
MAX_LANE_NODES = 8
SHOWN = 12
SRC = {
    'hosting': 'facts/runtime.json#deployment_target',
    'ci': 'facts/runtime.json#ci_step',
    'environments': 'facts/config.json#env_read (names) + config_file_unread',
    'databases': 'facts/entrypoints.json#data_access[client=supabase] + facts/resolve.json#module_edge[EXTERNAL] + facts/domain.json#data_table + facts/runtime.json#migration_step',
    'queues': 'facts/resolve.json#module_edge[EXTERNAL] matched against eaos/studio/infra.py PACKAGES',
    'services': 'facts/runtime.json#integration_target + resilience_policy + facts/resolve.json#module_edge[EXTERNAL]',
    'observability': 'facts/runtime.json#observability_signal + facts/resolve.json#module_edge[EXTERNAL]',
    'target': 'target-architecture.json#infrastructure',
}


def _measure(value, src, unit='count'):
    return {'value': value, 'src': src, 'unit': unit}


def _site(fact):
    location = fact.get('location') or {}
    return {'path': location.get('path') or '', 'line': location.get('start_line'), 'fact': fact.get('id')}


def package_of(module):
    """`@aws-sdk/client-sqs/dist` -> `@aws-sdk/client-sqs`; `celery.app` -> `celery`; a relative import -> None."""
    module = str(module or '')
    if not module or module.startswith(('.', '/', '@/', '~/', 'node:')): return None
    parts = module.split('/')
    return '/'.join(parts[:2]) if module.startswith('@') else re.split(r'[./]', module)[0]


def _known(package):
    """(lane, name) of a package, by its full name or its scope (`@sentry/react` -> Sentry)."""
    if not package: return None
    return PACKAGES.get(package) or PACKAGES.get(package.split('/')[0])


class _Lanes:
    """The nodes of each lane, each with its evidence sites (the first SHOWN) and their count."""
    def __init__(self):
        self.nodes = {lane: {} for lane in LANES}

    def add(self, lane, nid, name, kind, fact=None, detail=None, item=None):
        node = self.nodes[lane].setdefault(nid, {'id': nid, 'lane': lane, 'name': name, 'kind': kind, 'detail': {},
                                                 'items': [], 'sites': [], 'evidence': 0})
        if fact is not None:
            node['evidence'] += 1
            if len(node['sites']) < SHOWN: node['sites'].append(_site(fact))
        for key, value in (detail or {}).items():
            if isinstance(value, int) and not isinstance(value, bool): node['detail'][key] = node['detail'].get(key, 0) + value
            else: node['detail'][key] = value
        if item and item not in node['items']: node['items'].append(item)
        return node


def _tests(report):
    files = {arch_map.path_of(f) for f in arch_map.facts(report, 'syntax', 'source_file')
             if ((f.get('value') or {}).get('category')) == 'test'}
    return lambda path: path in files or bool(TEST_PATH.search(path))


def infra(report, lang='ar'):
    """The section's body: {app, lanes, counts, target, src}."""
    report = Path(report)
    is_test = _tests(report)
    live = lambda rows: [f for f in rows if not is_test(arch_map.path_of(f))]
    lanes = _Lanes()

    for fact in live(arch_map.facts(report, 'runtime', 'deployment_target')):
        v = fact.get('value') or {}
        if v.get('kind') == 'dockerfile':
            lanes.add('hosting', f'host:docker:{arch_map.path_of(fact)}', 'Docker', 'container', fact, item=f"port {v.get('port')}")
        elif v.get('kind') == 'compose':
            lanes.add('hosting', f'host:compose:{v.get("service")}', str(v.get('service')), 'compose_service', fact)
        elif v.get('kind') == 'hosting':
            lanes.add('hosting', f'host:{v.get("host")}', str(v.get('host')), 'platform', fact)

    for fact in live(arch_map.facts(report, 'runtime', 'ci_step')):
        path, name = arch_map.path_of(fact), str((fact.get('value') or {}).get('name') or '')
        if name.startswith('npm:'):
            lanes.add('ci', f'ci:{path}', 'npm scripts', 'scripts', fact, {'steps': 1}, item=name[4:])
        else:
            label = name if name and name != 'run: ' else None
            lanes.add('ci', f'ci:{path}', 'GitHub Actions · ' + Path(path).stem, 'workflow', fact, {'steps': 1}, item=label)

    names, secret = defaultdict(list), set()
    for fact in live(arch_map.facts(report, 'config', 'env_read')):
        v = fact.get('value') or {}
        if v.get('name'):
            names[v['name']].append(fact)
            if v.get('secret_shaped'): secret.add(v['name'])
    if names:
        node = lanes.add('environments', 'env:variables', 'Environment variables', 'variables', None,
                         {'variables': len(names), 'secret_shaped': len(secret),
                          'without_default': sum(1 for n in names if not any((f.get('value') or {}).get('has_default') for f in names[n]))})
        for name in sorted(names):
            lanes.add('environments', 'env:variables', '', 'variables', names[name][0], item=name)
    for fact in arch_map.facts(report, 'config', 'config_file_unread'):
        lanes.add('environments', f'env:file:{arch_map.path_of(fact)}', arch_map.path_of(fact), 'sensitive_file', fact)

    hosts = defaultdict(list)
    for fact in live(arch_map.facts(report, 'runtime', 'integration_target')):
        host = str((fact.get('value') or {}).get('host') or '').lower()
        if host and not NOT_SERVICES.search(host): hosts[host].append(fact)
    resilience = defaultdict(lambda: {'timeout': False, 'retry': False})
    for fact in arch_map.facts(report, 'runtime', 'resilience_policy'):
        v = fact.get('value') or {}
        flags = resilience[str(v.get('host') or '').lower()]
        flags['timeout'] |= bool(v.get('has_timeout'))
        flags['retry'] |= bool(v.get('has_retry'))
    for host, facts in sorted(hosts.items()):
        if host.endswith('.supabase.co'):  # the project's own Supabase: its database, not a service beside it
            for fact in facts: lanes.add('databases', 'databases:Supabase', 'Supabase', 'database', fact, item=host)
            continue
        for fact in facts:
            lanes.add('services', f'svc:{host}', host, 'host', fact, {'timeout': resilience[host]['timeout'], 'retry': resilience[host]['retry']})
        named = ENVIRONMENT.search(host.split('.')[0])  # the host's own name: `.dev` is a top-level domain, not an environment
        if named:
            word = ENV_WORD.get(named.group(1), named.group(1))
            lanes.add('environments', f'env:named:{word}', word, 'environment', facts[0], item=host)

    sb = live([f for f in arch_map.facts(report, 'entrypoints', 'data_access') if (f.get('value') or {}).get('client') == 'supabase'])
    for fact in sb:
        lanes.add('databases', 'databases:Supabase', 'Supabase', 'database', fact, {'calls': 1})
    for fact in live(arch_map.facts(report, 'resolve', 'module_edge')):
        if fact.get('resolution') != 'EXTERNAL': continue
        package = package_of((fact.get('value') or {}).get('module'))
        known = _known(package)
        if known:
            lane, name = known
            lanes.add(lane, f'{lane}:{name}', name, 'package', fact, item=package)
    tables = live(arch_map.facts(report, 'domain', 'data_table'))
    if tables:
        keys = {str((f.get('value') or {}).get('name') or '').lower() for f in tables if not (f.get('value') or {}).get('dropped')}
        rls = {str((f.get('value') or {}).get('name') or '').lower() for f in tables if (f.get('value') or {}).get('rls_enabled')}
        node = lanes.add('databases', 'db:schema', 'Tables declared in code', 'schema', None,
                         {'tables': len(keys), 'row_level_security': len(rls & keys) if any('rls_enabled' in (f.get('value') or {}) for f in tables) else None})
        for fact in tables[:SHOWN]: node['sites'].append(_site(fact))
        node['evidence'] = len(tables)
    for fact in live(arch_map.facts(report, 'runtime', 'migration_step')):
        lanes.add('databases', 'db:migrations', 'Migrations', 'migrations', fact, {'files': 1})
    for fact in live(arch_map.facts(report, 'runtime', 'connection_pool')):
        v = fact.get('value') or {}
        lanes.add('databases', 'db:pool', 'Connection pool', 'pool', fact, item=f"{v.get('resource')} {v.get('declared_size') or ''}".strip())

    for fact in live(arch_map.facts(report, 'runtime', 'observability_signal')):
        kind = str((fact.get('value') or {}).get('kind') or '')
        lanes.add('observability', f'obs:{kind}', kind, 'signal', fact, {'files': 1})

    out_lanes = []
    for lane in LANES:
        nodes = sorted(lanes.nodes[lane].values(), key=lambda n: (-n['evidence'], n['id']))
        for node in nodes: node['items'] = node['items'][:40]
        state = 'measured' if nodes else 'empty'
        reason = 'found' if nodes else ('no_known_queue_library' if lane == 'queues' else 'nothing_found')
        shown, folded = nodes[:MAX_LANE_NODES - 1] if len(nodes) > MAX_LANE_NODES else nodes, nodes[MAX_LANE_NODES - 1:] if len(nodes) > MAX_LANE_NODES else []
        out_lanes.append({'id': lane, 'relation': RELATION[lane], 'state': state, 'reason': reason,
                          'count': _measure(len(nodes), SRC[lane] + ' (distinct nodes)'),
                          'nodes': shown, 'folded': folded})

    record = arch_map._load(report / 'target-architecture.json', {}) or {}
    items = [i for i in record.get('infrastructure') or [] if isinstance(i, dict) and i.get('area')]
    target = None
    if record:
        by_lane = defaultdict(list)
        for item in items:
            by_lane[AREA_LANE.get(item['area'], 'observability')].append({
                'area': item['area'], 'present': bool(item.get('present')), 'op': 'keep' if item.get('present') else 'introduce',
                'decision': str(item.get('decision') or '')[:400], 'tool': item.get('tool'), 'evidence': str(item.get('evidence') or '')[:300]})
        target = {'reference': record.get('reference'), 'status': record.get('status'),
                  'lanes': [{'id': lane, 'state': 'measured' if by_lane.get(lane) else 'not_measured',
                             'reason': 'decided' if by_lane.get(lane) else 'target_silent', 'items': by_lane.get(lane, [])}
                            for lane in LANES]}
    total = sum(len(lanes.nodes[lane]) for lane in LANES)
    return {
        'app': {'reference': record.get('reference'), 'src': 'target-architecture.json#reference'},
        'lanes': out_lanes,
        'counts': {
            'nodes': _measure(total, 'lanes[].nodes + folded (count)'),
            'lanes_found': _measure(sum(1 for lane in LANES if lanes.nodes[lane]), 'lanes[state=measured] (count)'),
            'introduce': _measure(sum(i['op'] == 'introduce' for l in (target or {}).get('lanes', []) for i in l['items']) if target else None,
                                  SRC['target'] + '[present=false] (count)'),
            'keep': _measure(sum(i['op'] == 'keep' for l in (target or {}).get('lanes', []) for i in l['items']) if target else None,
                             SRC['target'] + '[present=true] (count)'),
            'target_silent': _measure(sum(l['state'] == 'not_measured' for l in target['lanes']) if target else None,
                                      'target.lanes[state=not_measured] (count)'),
        },
        'target': target,
        'src': SRC,
    }
