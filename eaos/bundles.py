"""Five bundles: every artifact the engagement ships, grouped for who reads them."""
from pathlib import Path
import shutil
import json
from . import discover
from .canonical_home import suggest as suggest_canonical
from .facts.store import read_set


NAME = 'bundles'
VERSION = '1'
LIMITATIONS = [
    'A bundle is a view; if the underlying artifact is regenerated, the bundle changes.',
    'The five bundles are a reading order, not the only way to consume the dossier.',
    'A bundle contains what the engine can produce; missing artifacts stay gaps, never guesses.',
]


PLAN = [
    ('00-ENGAGEMENT', ['engagement.json']),
    ('01-DISCOVERY', ['facts/', 'SYSTEM-MAP.md', 'FLOWS.md', 'DATA-MODEL.md', 'CONTRACTS.md',
                      'DEPLOYMENT.md', 'OBSERVABILITY.md', 'SECURITY-SURFACE.md', 'EVOLUTION.md',
                      'INTEGRATIONS.md']),
    ('02-ASSESSMENT', ['SUSTAINABILITY.md', 'DUPLICATION-ATLAS.md', 'RISK-REGISTER.md',
                        'VERIFICATION-MAP.md', 'POLICY.md']),
    ('03-TARGET', ['TARGET-ARCHITECTURE.md', 'CANONICAL-HOMES.md', 'gap-matrix.json',
                    'transform-plan.json', 'transform-plan.md']),
    ('04-TRANSFORM', ['transform-plan.json', 'transform-plan.md', 'STAGES.md', 'WAVES.md', 'KPI.md']),
    ('SUMMARY', ['EXECUTIVE.md', 'PROVENANCE.md', 'dossier.json']),
]


def _write_if_present(out, name, content, json_mode=False):
    if content is None: return
    path = out / name
    if json_mode:
        path.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding='utf-8')
    else:
        path.write_text(content, encoding='utf-8')


def _generate_engagement(out, language):
    """Default engagement contract for the bundle."""
    out = Path(out); ar = language == 'ar'
    from .engagement import read_contract, render_contract
    destination = out / 'engagement.json'
    if destination.exists(): return read_contract(destination)
    contract = render_contract()
    destination.write_text(json.dumps(contract, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return contract


def _generate_discovery(out, language):
    """Generate the discovery documents on demand; do not silently skip them."""
    return discover.write_all(out, language=language)


SHOWN_CLUSTERS = 12
SHOWN_STAGES = 20


def _generate_canonical_homes(out, language):
    """Return (document, record). The document shows the first clusters; the record holds them all."""
    out = Path(out); ar = language == 'ar'
    sets = {}
    for name in ['fingerprint', 'graph', 'resolve']:
        path = out / 'facts' / (name + '.json')
        if path.is_file(): sets[name] = read_set(out, name)
    clusters = [f for f in sets.get('fingerprint', {}).get('facts', [])
                if f['kind'] == 'duplicate_cluster']
    lines = ['# ' + ('المواضع المرجعية' if ar else 'Canonical homes'),
              '',
              ('> لكل عنقود تكرار، الموضع المرجعي الذي اختاره المحرك.' if ar else
                '> For every duplicate cluster, the canonical home the engine picked.')]
    lines += [str(len(clusters)) + ' ' + ('عنقود' if ar else 'cluster(s)') + '.']
    record = {'schema_version': 1, 'clusters': [], 'total': len(clusters),
              'shown_in_document': min(SHOWN_CLUSTERS, len(clusters))}
    for position, cluster in enumerate(clusters):
        result = suggest_canonical(out, cluster)
        best = result['candidates'][0] if result['candidates'] else None
        cluster_value = cluster['value']
        record['clusters'].append({'shape_sha': cluster_value['shape_sha'], 'canonical_home': best,
                                   'occurrences': cluster_value['occurrences']})
        if position >= SHOWN_CLUSTERS:
            continue
        lines += ['', '## cluster `' + cluster_value['shape_sha'][:12] + '...`']
        if best:
            lines += ['- ' + ('الموضع المرجعي' if ar else 'canonical home')
                       + ': `' + str(best['path']) + '`']
            lines += ['- ' + ('محتوى بالفعل' if ar else 'home already')
                       + ': ' + str(best['home_already'])]
            lines += ['- ' + ('مخالفات السياسة' if ar else 'policy violations')
                       + ': ' + str(best['policy_violations'])]
        for occ in cluster_value['occurrences'][:8]:
            lines += ['  - ' + occ['path'] + ':' + str(occ['start_line'])
                       + ' ' + occ['symbol']]
        if len(cluster_value['occurrences']) > 8:
            lines += ['  - ' + ('… البقية في `canonical-homes.json`' if ar
                                else '… the rest are in `canonical-homes.json`')]
    if len(clusters) > SHOWN_CLUSTERS:
        lines += ['', (f'عُرض {SHOWN_CLUSTERS} من {len(clusters)}؛ الباقي في `canonical-homes.json`.' if ar
                       else f'Showing {SHOWN_CLUSTERS} of {len(clusters)}; the rest are in `canonical-homes.json`.')]
    return '\n'.join(lines) + '\n', record


def _generate_gap_matrix(out, language):
    out = Path(out); ar = language == 'ar'
    target_path = out / 'target-architecture.json'
    if not target_path.is_file(): return None
    target = json.loads(target_path.read_text())
    return {'rows': target.get('gap_matrix', []),
            'covered': sum(1 for r in target.get('gap_matrix', []) if r['gap'] == 'covered'),
            'total': len(target.get('gap_matrix', []))}


def _generate_kpi(out, language):
    out = Path(out); ar = language == 'ar'
    dash_path = out / 'facts' / 'fingerprint.json'
    if not dash_path.is_file(): return None
    from .sustainability import compute
    dashboard = compute(out)
    lines = ['# ' + ('مؤشرات الأداء' if ar else 'KPI'), '']
    for row in dashboard['rows']:
        if not row.get('measured', True):
            lines += ['- **' + row['indicator'] + '**: '
                       + ('لم يقس' if ar else 'not measured')]
            continue
        gap = row['gap'] if row['gap'] is not None else '-'
        lines += ['- **' + row['indicator'] + '**: value=' + str(row['value'])
                   + ', target=' + str(row['target']) + ', gap=' + str(gap)]
    return '\n'.join(lines) + '\n'


def _generate_stages(out, language):
    out = Path(out); ar = language == 'ar'
    plan_path = out / 'transform-plan.json'
    if not plan_path.is_file(): return None
    plan = json.loads(plan_path.read_text())
    stages = plan.get('stages', [])
    lines = ['# ' + ('المراحل' if ar else 'Stages'), '']
    for stage in stages[:SHOWN_STAGES]:
        lines += ['', '## Stage ' + str(stage['stage']) + ': ' + stage['move']]
        if 'canonical_home' in stage:
            lines += ['- ' + ('موضع مرجعي' if ar else 'canonical home')
                       + ': `' + str(stage.get('canonical_home') or '-') + '`']
        if 'sites' in stage:
            lines += ['- ' + ('مواضع' if ar else 'sites')
                       + ': ' + str(len(stage['sites']))]
        if 'predicted' in stage:
            for k, v in stage['predicted'].items():
                lines += ['- predicted ' + str(k) + ': ' + str(v)]
    if len(stages) > SHOWN_STAGES:
        lines += ['', (f'عُرضت {SHOWN_STAGES} من {len(stages)}؛ البقية في `transform-plan.json`.' if ar
                       else f'Showing {SHOWN_STAGES} of {len(stages)}; the rest are in `transform-plan.json`.')]
    return '\n'.join(lines) + '\n'


def _generate_waves(out, language):
    out = Path(out); ar = language == 'ar'
    plan_path = out / 'transform-plan.json'
    if not plan_path.is_file(): return None
    plan = json.loads(plan_path.read_text())
    stages = plan.get('stages', [])
    canonicalize = [s for s in stages if s['move'] == 'canonicalize']
    eliminate = [s for s in stages if s['move'] == 'eliminate_redundancy']
    lines = ['# ' + ('موجات التنفيذ' if ar else 'Waves'), '']
    if canonicalize:
        lines += ['', '## ' + ('موجة 1: التجميع' if ar else 'Wave 1: canonicalize')]
        for stage in canonicalize:
            rule = stage.get('rule', '')[:12]
            lines += ['- Stage ' + str(stage['stage']) + ': ' + rule + '...']
    if eliminate:
        lines += ['', '## ' + ('موجة 2: إزالة التكرار' if ar else 'Wave 2: eliminate redundancy')]
        for stage in eliminate:
            lines += ['- Stage ' + str(stage['stage']) + ': '
                       + str(stage.get('redundancy_kind', ''))]
    return '\n'.join(lines) + '\n'


def build(out, source_files=None, language='ar'):
    """Create the bundle directories, generating every artifact the engine can produce."""
    out = Path(out)
    bundles_dir = out / 'bundles'
    if bundles_dir.exists(): shutil.rmtree(bundles_dir)
    bundles_dir.mkdir()
    _generate_engagement(out, language=language)
    _generate_discovery(out, language=language)
    canonical_md, canonical_record = _generate_canonical_homes(out, language=language)
    gap_obj = _generate_gap_matrix(out, language=language)
    kpi_md = _generate_kpi(out, language=language)
    stages_md = _generate_stages(out, language=language)
    waves_md = _generate_waves(out, language=language)
    _write_if_present(out, 'CANONICAL-HOMES.md', canonical_md)
    _write_if_present(out, 'canonical-homes.json', canonical_record, json_mode=True)
    _write_if_present(out, 'gap-matrix.json', gap_obj, json_mode=True)
    _write_if_present(out, 'KPI.md', kpi_md)
    _write_if_present(out, 'STAGES.md', stages_md)
    _write_if_present(out, 'WAVES.md', waves_md)
    written = []
    missing = []
    for name, entries in PLAN:
        directory = bundles_dir / name
        directory.mkdir()
        for entry in entries:
            source = out / entry
            if not source.exists():
                missing.append({'bundle': name, 'artifact': entry, 'reason': 'not produced in this run'})
                continue
            target = directory / entry
            if source.is_dir():
                target.mkdir(exist_ok=True)
                for child in source.iterdir():
                    destination = target / child.name
                    if child.is_file(): shutil.copy2(child, destination)
                    elif child.is_dir():
                        if destination.exists(): shutil.rmtree(destination)
                        shutil.copytree(child, destination)
            else:
                shutil.copy2(source, target)
        written.append(name)
    manifest = {'language': language, 'bundles': written, 'missing_artifacts': missing}
    (bundles_dir / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return {'bundles_dir': str(bundles_dir), 'bundles': written, 'missing_artifacts': missing,
            'limits': ' '.join(LIMITATIONS)}
