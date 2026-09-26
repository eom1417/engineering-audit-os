"""The observability kit: an OpenTelemetry Collector, what to instrument, and SLOs, in each tool's own format.

  handover/otel/collector.yaml       OTLP in (gRPC and HTTP); memory limiter and batch; out to a file for the
                                     sandbox run (NS24 reads it) and over OTLP to the address in
                                     OTEL_EXPORTER_OTLP_ENDPOINT for production. No address is written.
                                     Judged by `otelcol-contrib validate`.
  handover/otel/INSTRUMENTATION.md   for the detected stack: the official OpenTelemetry packages and their
                                     start-up lines, and every surface of a critical feature that must carry
                                     a span, named by its route.
  handover/slo/<service>.yaml        Sloth (prometheus/v1): one SLO per measurable quality scenario of
                                     intake.json (availability, p95 latency, error rate), its objective
                                     from the scenario. Judged by `sloth validate`.
"""
import textwrap
from pathlib import Path

from .base import Emitted
from .project import profile, slug
from .yamltext import dump

STACKS = {
    'js': ('Browser (React SPA)', [
        'Install with npm: @opentelemetry/api, @opentelemetry/sdk-trace-web, @opentelemetry/instrumentation-fetch, '
        '@opentelemetry/instrumentation-document-load, @opentelemetry/exporter-trace-otlp-http and @opentelemetry/context-zone.',
        "In src/main.tsx, before the app renders: a WebTracerProvider with the service name, a BatchSpanProcessor over "
        "OTLPTraceExporter({ url: import.meta.env.VITE_OTEL_EXPORTER_OTLP_ENDPOINT + '/v1/traces' }), registered with "
        "ZoneContextManager, and registerInstrumentations({ instrumentations: [new FetchInstrumentation(), "
        "new DocumentLoadInstrumentation()] }).",
        'Each route renders inside a span named by its path (see the table), so a slow or failing screen is visible by name.']),
    'python': ('Python', [
        'pip install opentelemetry-distro opentelemetry-exporter-otlp && opentelemetry-bootstrap -a install',
        'Start the application under the agent: `opentelemetry-instrument --service_name SERVICE START_COMMAND`, '
        'with OTEL_EXPORTER_OTLP_ENDPOINT pointing at the Collector.',
        'Each user-facing action below opens a span: `tracer.start_as_current_span("SPAN NAME")`.']),
}


def collector():
    pipeline = {'receivers': ['otlp'], 'processors': ['memory_limiter', 'batch'], 'exporters': ['file/sandbox', 'otlp/production']}
    return dump({
        'receivers': {'otlp': {'protocols': {'grpc': {'endpoint': '0.0.0.0:4317'}, 'http': {'endpoint': '0.0.0.0:4318'}}}},
        'processors': {'memory_limiter': {'check_interval': '1s', 'limit_percentage': 80, 'spike_limit_percentage': 20},
                       'batch': {}},
        'exporters': {'file/sandbox': {'path': '${env:EAOS_TELEMETRY_FILE:-/tmp/eaos-telemetry.jsonl}'},
                      'otlp/production': {'endpoint': '${env:OTEL_EXPORTER_OTLP_ENDPOINT:-localhost:4317}'}},
        'service': {'pipelines': {'traces': pipeline, 'metrics': pipeline, 'logs': pipeline}},
    }, 'OpenTelemetry Collector, written by EAOS. Sandbox: spans go to EAOS_TELEMETRY_FILE, which the observability check reads.\n'
       'Production: set OTEL_EXPORTER_OTLP_ENDPOINT to your backend (SigNoz, or any OTLP receiver); no address is written here.')


def critical_surfaces(p):
    rows = []
    for feature in p['features']:
        if not feature.get('critical'): continue
        for surface in feature.get('surfaces') or []:
            if surface != '*' and (feature['name'], surface) not in rows: rows.append((feature['name'], surface))
    return rows


def instrumentation(p, service):
    stack = 'js' if p['js'] else 'python' if p['python'] else None
    # A table row is one line, however long: a wrapped row is a broken table.
    lines = ['<!-- markdownlint-configure-file { "MD013": { "tables": false } } -->', '', f'# Instrumentation: {service}', '']
    if stack is None:
        return '\n'.join(lines + ['No supported stack was detected; the Collector and the SLOs still apply.', ''])
    title, steps = STACKS[stack]
    lines += textwrap.wrap(f'Stack: {title}. Every line below is one change, done in the infrastructure section of the plan.', 80)
    lines += ['', '## Set up', '']
    for index, step in enumerate(steps, 1):
        lines += textwrap.wrap(step, 80, initial_indent=f'{index}. ', subsequent_indent='   ', break_long_words=False, break_on_hyphens=False)
    surfaces = critical_surfaces(p)
    lines += ['', '## Surfaces that must carry a span', '',
              f'{len(surfaces)} surfaces of the features the owner marked critical (intake.json, features.json).', '',
              '| Feature | Surface | Span name |', '| --- | --- | --- |']
    lines += [f'| {feature} | `{surface}` | `{feature} {surface}` |' for feature, surface in surfaces] or ['| — | — | — |']
    return '\n'.join(lines) + '\n'


def slos(p, service):
    metric = 'http_client_request_duration_seconds' if p['js'] else 'http_server_request_duration_seconds'
    selector = f'service_name="{service}"'
    total = f'sum(rate({metric}_count{{{selector}}}[{{{{.window}}}}]))'
    found = []
    for scenario in (p['intake'] or {}).get('scenarios') or []:
        measure = scenario.get('measure') or {}
        name, objective, errors = None, None, None
        if measure.get('metric') == 'availability':
            name, objective = 'availability', float(measure['threshold'])
            errors = f'sum(rate({metric}_count{{{selector},http_response_status_code=~"5.."}}[{{{{.window}}}}]))'
        elif measure.get('metric') == 'error_rate':
            name, objective = 'errors', round(100 * (1 - float(measure['threshold'])), 3)
            errors = f'sum(rate({metric}_count{{{selector},error_type!=""}}[{{{{.window}}}}]))'
        elif measure.get('metric') == 'p95_ms':
            seconds = float(measure['threshold']) / 1000
            name, objective = 'latency', 95.0
            errors = f'({total} - sum(rate({metric}_bucket{{{selector},le="{seconds:g}"}}[{{{{.window}}}}])))'
        if name is None: continue
        found.append({'name': name, 'objective': objective,
                      'description': f"{scenario['id']}: {scenario['stimulus']}; {scenario['response']} "
                                     f"({measure['metric']} {measure['threshold']} {measure.get('unit', '')}, {scenario['source']}).",
                      'sli': {'events': {'error_query': errors, 'total_query': total}},
                      'alerting': {'name': f'{service}-{name}', 'labels': {'category': name},
                                   'page_alert': {'labels': {'severity': 'critical'}},
                                   'ticket_alert': {'labels': {'severity': 'warning'}}}})
    return found


def write(report):
    report = Path(report)
    p = profile(report)
    if p['root'] is None: return []
    service = slug(p['name'])
    folder = report / 'handover'
    (folder / 'otel').mkdir(parents=True, exist_ok=True)
    (folder / 'otel/collector.yaml').write_text(collector(), encoding='utf-8')
    (folder / 'otel/INSTRUMENTATION.md').write_text(instrumentation(p, service), encoding='utf-8')
    items = [Emitted('handover/otel/collector.yaml', 'otelcol-contrib', ('otelcol-contrib', 'validate', '--config', '{path}')),
             Emitted('handover/otel/INSTRUMENTATION.md', 'markdownlint-cli2', ('markdownlint-cli2', '{path}'))]
    objectives = slos(p, service)
    if objectives:
        (folder / 'slo').mkdir(parents=True, exist_ok=True)
        (folder / f'slo/{service}.yaml').write_text(dump(
            {'version': 'prometheus/v1', 'service': service, 'labels': {'owner': 'eaos-handover'}, 'slos': objectives},
            'Service level objectives from the quality scenarios in intake.json, written by EAOS for Sloth.\n'
            'Generate the Prometheus rules: sloth generate -i slo/'), encoding='utf-8')
        items.append(Emitted(f'handover/slo/{service}.yaml', 'sloth', ('sloth', 'validate', '-i', '{path}')))
    return items
