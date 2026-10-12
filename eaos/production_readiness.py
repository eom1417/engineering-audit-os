"""How the program would hold up in production and under pressure, from the facts and the intake: readiness.json.

What the old handover kits wrote as files in other tools' formats (the k6, Toxiproxy and ZAP plans, the Goss file, the
OpenTelemetry Collector and the Sloth SLOs) is computed here as findings instead, each with its evidence, so the
person's assistant can judge every aspect when it plans the ideal. Nothing runs here; the only measurement read is the
k6 baseline the `baseline` stage took (live/baseline.json), when it ran in this check.

    resilience      every external dependency a fault would hit (the Toxiproxy plan: latency, timeout, down) and the
                    timeout, retry and circuit breaker the code shows on its calls
    security        the routes a passive security scan would request (the ZAP plan), the authentication and rate
                    limits the code declares
    observability   a health route, telemetry in the code (traces, metrics, error capture), and which intake
                    scenarios an SLO could be written for
    performance     the k6 baseline: each load scenario's measured p95 and error rate against the intake's threshold

Each finding: {id, aspect, status (ok | gap | unmeasured), title, detail, evidence: [fact ids or record paths]}.
"""
import json
from pathlib import Path

from .nfr import _facts, _load, dependencies, routes, scenarios

ASPECTS = ('resilience', 'security', 'observability', 'performance')
TOXICS = ('latency 2000 ms', 'timeout', 'down')
HEALTH_WORDS = ('health', 'healthz', 'ready', 'readyz', 'live', 'livez', 'status', 'ping')
TELEMETRY = {'trace': 'traces', 'metric': 'metrics', 'sentry': 'error capture (Sentry)'}
SLO_METRICS = ('availability', 'p95_ms', 'error_rate')


def _row(aspect, key, status, title, detail='', evidence=()):
    return {'id': f'RDY-{aspect}-{key}', 'aspect': aspect, 'status': status, 'title': title, 'detail': detail,
            'evidence': [e for e in dict.fromkeys(evidence) if e][:8]}


def _resilience(report):
    rows = []
    policies = {}
    for fact in _facts(report, 'resilience_policy'):
        value = fact.get('value') or {}
        policies.setdefault(value.get('host'), []).append(fact)
    found = dependencies(report)
    if not found:
        return [_row('resilience', 'dependencies', 'ok', 'No external dependency a fault could hit was found in the code')]
    for name, variable, features in found:
        guards = policies.get(name) or []
        values = [(k[4:], v) for f in guards for k, v in (f.get('value') or {}).items() if k.startswith('has_')]
        missing = sorted({k for k, v in values if v is False})
        status = 'gap' if missing else 'ok' if values and all(v is True for _, v in values) else 'unmeasured'
        detail = (f"A fault plan would put a proxy in front of it ({variable}) and inject {', '.join(TOXICS)}; "
                  f"{len(features)} feature(s) depend on it" + (f": {', '.join(features[:5])}" if features else '') + '. '
                  + (f"Its calls show no {', '.join(m.replace('_', ' ') for m in missing)}." if missing else
                     'Its calls show a timeout, a retry and a circuit breaker.' if status == 'ok' else
                     'No call guard could be read for it.'))
        rows.append(_row('resilience', name, status, f'External dependency {name}', detail, [f.get('id') for f in guards]))
    return rows


def _security(report):
    paths = routes(report)
    auth = _facts(report, 'security_surface')
    limits = _facts(report, 'rate_limit')
    rows = [_row('security', 'scan', 'unmeasured' if paths else 'ok',
                 f'{len(paths)} route(s) a passive security scan (OWASP ZAP) would request' if paths else
                 'No route a security scan could request without a fixture',
                 ('Spider from the start page, then request: ' + ', '.join(paths[:12]) + (f' and {len(paths) - 12} more' if len(paths) > 12 else '')
                  + '. No scan ran in this check.') if paths else '', ['features.json'])]
    if not paths: return rows                          # nothing reachable to guard: the scan row says so
    rows.append(_row('security', 'authentication', 'ok' if auth else 'gap',
                     'Authentication is declared in the code' if auth else 'No authentication guard was found in the code',
                     ', '.join(sorted({(f.get('value') or {}).get('hint') for f in auth if (f.get('value') or {}).get('hint')}))[:200],
                     [f.get('id') for f in auth]))
    rows.append(_row('security', 'rate_limit', 'ok' if limits else 'gap',
                     'A rate limit is declared' if limits else 'No rate limit was found in the code or its configuration',
                     ', '.join(sorted({(f.get('value') or {}).get('mechanism') or '' for f in limits}))[:200], [f.get('id') for f in limits]))
    return rows


def _observability(report):
    every = [s for f in (_load(Path(report) / 'features.json', {}) or {}).get('features') or [] for s in f.get('surfaces') or []]
    health = sorted({s for s in every if isinstance(s, str) and any(w in s.lower().split('/')[-1] for w in HEALTH_WORDS)})
    signals = _facts(report, 'observability_signal')
    kinds = {(f.get('value') or {}).get('kind') for f in signals}
    telemetry = [TELEMETRY[k] for k in TELEMETRY if k in kinds]
    measurable = [s for s in scenarios(report) if (s.get('measure') or {}).get('metric') in SLO_METRICS]
    return [
        _row('observability', 'health', 'ok' if health else 'gap',
             f"A health route: {', '.join(health[:3])}" if health else 'No health route a load balancer or uptime check could call',
             '' if health else 'A running release cannot be checked from outside without one.', ['features.json']),
        _row('observability', 'telemetry', 'ok' if telemetry else 'gap',
             f"Telemetry in the code: {', '.join(telemetry)}" if telemetry else 'No traces, metrics or error capture in the code',
             '' if telemetry else 'A slow or failing request in production would be invisible until a user reports it.',
             [f.get('id') for f in signals if (f.get('value') or {}).get('kind') in TELEMETRY]),
        _row('observability', 'slo', 'ok' if measurable else 'gap',
             f"{len(measurable)} intake scenario(s) an SLO can be written for" if measurable else 'No intake scenario an SLO can measure',
             '; '.join(f"{s['id']}: {s['measure']['metric']} {s['measure']['threshold']} {s['measure'].get('unit', '')} ({s.get('source')})"
                       for s in measurable)[:400], ['intake.json']),
    ]


def _performance(report, measured):
    """The k6 baseline against the intake's thresholds; unmeasured, with why, when the baseline did not run here."""
    load = [s for s in scenarios(report) if s.get('kind') == 'load']
    baseline = _load(Path(report) / 'live/baseline.json', None) if measured else None
    if not baseline:
        return [_row('performance', s['id'], 'unmeasured', f"{s['id']}: {s['stimulus']}",
                     f"Threshold p95 {s['measure']['threshold']} {s['measure'].get('unit', 'ms')}; the app did not run under load in "
                     'this check, so its speed is only estimated (load-model.json).', ['intake.json', 'load-model.json']) for s in load] or \
               [_row('performance', 'load', 'unmeasured', 'No load scenario in the intake', '', ['intake.json'])]
    rows = []
    for scenario in baseline.get('scenarios') or []:
        before = scenario.get('before') or {}
        p95, threshold = before.get('p95_ms'), scenario.get('threshold')
        status = 'unmeasured' if p95 is None else 'ok' if threshold is None or p95 <= threshold else 'gap'
        rows.append(_row('performance', scenario.get('id'), status,
                         f"{scenario.get('id')}: p95 {p95} ms against a threshold of {threshold} ms",
                         f"error rate {before.get('error_rate')}; conditions: {json.dumps(baseline.get('conditions'))[:200]}",
                         ['live/baseline.json']))
    return rows


def build(report, measured=False):
    """The readiness record of a report; `measured`: the baseline stage ran in this check, so live/baseline.json is
    this check's and not an earlier one's."""
    report = Path(report)
    findings = _resilience(report) + _security(report) + _observability(report) + _performance(report, measured)
    summary = {aspect: {status: sum(1 for f in findings if f['aspect'] == aspect and f['status'] == status)
                        for status in ('ok', 'gap', 'unmeasured')} for aspect in ASPECTS}
    return {'schema_version': 1, 'findings': findings, 'summary': summary,
            'limits': 'Read from the code and the intake; no fault was injected and no security scan ran. Only the k6 '
                      'baseline, when it ran in this check, is a measurement.'}


def write(report, measured=False):
    record = build(report, measured)
    (Path(report) / 'readiness.json').write_text(json.dumps(record, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    return record
