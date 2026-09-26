"""The handover site: the four reports, the roadmap, the decisions, the architecture and the runbooks, in one place.

  handover/mkdocs.yml       the navigation; read by Zensical and MkDocs alike. Judged by `zensical build --strict`,
                            which fails on a broken link: a link to a document the site does not carry becomes
                            the document's name in code, never a dead link.
  handover/docs/            index, reports/ (the four reports and ROADMAP.md), architecture/ (the target's layers
                            and components as Mermaid, and both Structurizr models), adr/ (every MADR decision),
                            runbooks/ (operate, roll back, respond to an incident), written from this project's
                            commands, checklist and quality scenarios.

EAOS's own index.html stays the internal reading tool; this site is handed to the owner and published from
their repository.
"""
import json
import posixpath
import re
import shutil
from pathlib import Path

from .base import Emitted
from .project import profile, reference, slug
from .yamltext import dump

REPORTS = ('CURRENT-STATE.md', 'TARGET-STATE.md', 'GAP-AND-STRATEGY.md', 'EXECUTION-PLAN.md', 'ROADMAP.md')
LINK = re.compile(r'\[([^\]]*)\]\(([^)\s]+)\)')
MERMAID = ('markdown_extensions:\n  - tables\n  - admonition\n  - pymdownx.superfences:\n      custom_fences:\n'
           '        - name: mermaid\n          class: mermaid\n          format: !!python/name:pymdownx.superfences.fence_code_format\n')


def _load(path, default):
    try: return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError): return default


def relink(text, source, mapping):
    """Links resolved from the report's layout to the site's; a link the site cannot follow becomes plain code."""
    here = posixpath.dirname(mapping[source])

    def replace(match):
        label, href = match.groups()
        if re.match(r'^[a-z]+:|^#', href): return match.group(0)
        path, _, anchor = href.partition('#')
        wanted = posixpath.normpath(posixpath.join(posixpath.dirname(source), path))
        if wanted in mapping:
            return f"[{label}]({posixpath.relpath(mapping[wanted], here or '.')}{'#' + anchor if anchor else ''})"
        return f'{label} (`{wanted}`)' if label and label != wanted else f'`{wanted}`'
    return LINK.sub(replace, text)


def architecture(p, ref):
    target = p['target'] or {}
    components = target.get('target_components') or []
    lines = ['# Target architecture', '',
             f"Reference type: `{target.get('reference', '—')}`. Each box is a layer; each arrow is a dependency the layer "
             'may have. Anything else is a boundary violation, checked in CI (`.dependency-cruiser.cjs`, `semgrep/`).', '',
             '```mermaid', 'flowchart TB']
    layers = ref['layers'] if ref else []
    for index, layer in enumerate(layers):
        members = [c for c in components if c.get('layer') == layer['name']]
        lines.append(f'    subgraph L{index}["{layer["name"]}"]')
        lines += [f'        C{index}_{n}["{c["name"]}<br/>{c.get("files", 0)} files"]' for n, c in enumerate(members[:8])]
        if len(members) > 8: lines.append(f'        C{index}_more["+{len(members) - 8} more"]')
        if not members: lines.append(f'        C{index}_none["(no component yet)"]')
        lines.append('    end')
    names = {layer['name']: index for index, layer in enumerate(layers)}
    for layer in layers:
        lines += [f"    L{names[layer['name']]} --> L{names[other]}" for other in layer['allowed_dependencies'] if other in names]
    lines += ['```', '', '## Components', '', '| Component | Layer | Files | Responsibility |', '| --- | --- | --- | --- |']
    lines += [f"| {c['name']} | {c.get('layer', '—')} | {c.get('files', 0)} | {c.get('responsibility', '—')} |" for c in components]
    return '\n'.join(lines) + '\n'


def model(title, dsl):
    return f'# {title}\n\nThe Structurizr model EAOS wrote and Structurizr validated. Render it with Structurizr Lite or `structurizr-cli export`.\n\n```text\n{dsl.rstrip()}\n```\n'


def runbooks(p, report):
    checklist = _load(Path(report) / 'handover/readiness/checklist.json', {}).get('items') or []
    command = {item['id']: item['command'] for item in checklist}
    intake = {q['id']: q.get('answer') for q in (p['intake'] or {}).get('questions') or []}
    start = (p['intake'] or {}).get('run_command') or ('python run_app.py' if 'run_app.py' in p['files'] else 'see the README')
    env = '`.env.example` lists the variables it needs.' if '.env.example' in p['files'] else \
        'No `.env.example` was found: list every variable the start needs before the first hand-over.'
    operate = ['# Operate', '', '## Start', '', f'```bash\n{command.get("RDY-02", "")}\n{start}\n```'.replace('\n\n', '\n'), '',
               f'Configuration: {env}', '', '## Is it healthy?', '', '```bash\ngoss -g readiness/goss.yaml validate\n```', '',
               'Traces, metrics and logs go through the Collector (`otel/collector.yaml`); the objectives it is held to are in `slo/`.',
               '', '## Before a release', '', 'Every item of `readiness/checklist.json` passes:', '']
    operate += [f"- **{item['id']}** {item['title']}: `{item['command']}`" for item in checklist]
    hosting = intake.get('hosting')
    redeploy = (f'Redeploy the reverted commit on {hosting} (or promote its previous deployment).' if hosting and hosting != 'unknown'
                else 'Redeploy the reverted commit the way the application is deployed.')
    rollback = ['# Roll back', '', 'When a release breaks what the behaviour lock protects, go back one commit, prove it, redeploy.', '',
                '1. Find the last good commit: `git log --oneline`.', '2. Revert, never rewrite history: `git revert --no-edit <commit>`.',
                f"3. Prove it: `{command.get('RDY-02', 'build')}` then `{command.get('RDY-03', 'the behaviour lock')}`.",
                f'4. {redeploy}', '5. Check health: `goss -g readiness/goss.yaml validate`, and watch the SLO alerts for one hour.']
    data = command.get('RDY-07') or command.get('RDY-08')
    incident = ['# Respond to an incident', '',
                '1. **Detect.** An SLO page alert (`slo/`) or a failed health check. Note the time and the objective burning.',
                '2. **Locate.** Open the traces of the failing route: its span is named by the route (`otel/INSTRUMENTATION.md`).',
                '3. **Mitigate.** If the last release caused it, roll back ([runbook](rollback.md)) before diagnosing further.',
                ('4. **Restore data** only from a backup proven by the readiness check: `' + data + '`.') if data else
                '4. **Restore data**: the project keeps no database of its own; nothing to restore here.',
                '5. **Learn.** Write what happened, the time to detect and to recover, and the check that would have caught it; '
                'add that check to CI or the checklist.']
    return {'operate.md': '\n'.join(operate) + '\n', 'rollback.md': '\n'.join(rollback) + '\n', 'incident.md': '\n'.join(incident) + '\n'}


def title_of(text, fallback):
    return next((line[2:].strip() for line in text.splitlines() if line.startswith('# ')), fallback)


def write(report):
    report = Path(report)
    p = profile(report)
    if p['root'] is None or not (report / 'CURRENT-STATE.md').is_file(): return []
    ref = reference(p)
    root = report / 'handover'
    docs = root / 'docs'
    if docs.exists(): shutil.rmtree(docs)
    for folder in ('reports', 'architecture', 'adr', 'runbooks'): (docs / folder).mkdir(parents=True, exist_ok=True)
    mapping = {name: f'reports/{name}' for name in REPORTS if (report / name).is_file()}
    adrs = sorted((report / 'adr').glob('ADR-*.md')) if (report / 'adr').is_dir() else []
    mapping.update({f'adr/{path.name}': f'adr/{path.name}' for path in adrs})
    mapping.update({'TARGET-ARCHITECTURE.md': 'architecture/target.md'})
    for source, destination in mapping.items():
        if source == 'TARGET-ARCHITECTURE.md': continue
        (docs / destination).write_text(relink((report / source).read_text(encoding='utf-8'), source, mapping), encoding='utf-8')
    (docs / 'architecture/target.md').write_text(architecture(p, ref), encoding='utf-8')
    models = []
    for side in ('current', 'target'):
        dsl = report / f'architecture/{side}/workspace.dsl'
        if dsl.is_file():
            (docs / f'architecture/{side}-model.md').write_text(model(f'{side.capitalize()} model (C4)', dsl.read_text(encoding='utf-8')), encoding='utf-8')
            models.append({f'{side.capitalize()} model (C4)': f'architecture/{side}-model.md'})
    for name, text in runbooks(p, report).items(): (docs / 'runbooks' / name).write_text(text, encoding='utf-8')
    reading = [f"- [{title_of((docs / mapping[name]).read_text(encoding='utf-8'), name)}]({mapping[name]})" for name in REPORTS if name in mapping]
    (docs / 'index.md').write_text('\n'.join([f"# {p['name']}: handover", '',
                                              'Everything the audit found and decided, and how to run the result. Read in this order:', '']
                                             + reading + ['', 'Then the [target architecture](architecture/target.md), the decisions under '
                                                          '[ADR](adr/' + (adrs[0].name if adrs else '') + '), and the runbooks: '
                                                          '[operate](runbooks/operate.md), [roll back](runbooks/rollback.md), '
                                                          '[incident](runbooks/incident.md).']) + '\n', encoding='utf-8')
    if not adrs: (docs / 'index.md').write_text((docs / 'index.md').read_text(encoding='utf-8').replace(', the decisions under [ADR](adr/)', ''), encoding='utf-8')
    arabic = bool(re.search(r'[؀-ۿ]', (report / 'CURRENT-STATE.md').read_text(encoding='utf-8')))
    nav = [{'Home': 'index.md'},
           {'Reports': [{title_of((docs / mapping[n]).read_text(encoding='utf-8'), n): mapping[n]} for n in REPORTS if n in mapping]},
           {'Architecture': [{'Target architecture': 'architecture/target.md'}] + models}]
    if adrs: nav.append({'Decisions': [{title_of((docs / f'adr/{a.name}').read_text(encoding='utf-8'), a.stem): f'adr/{a.name}'} for a in adrs]})
    nav.append({'Runbooks': [{'Operate': 'runbooks/operate.md'}, {'Roll back': 'runbooks/rollback.md'}, {'Incident': 'runbooks/incident.md'}]})
    config = dump({'site_name': f"{p['name']} — handover", 'docs_dir': 'docs', 'site_dir': 'site',
                   'theme': {'language': 'ar' if arabic else 'en'}, 'nav': nav},
                  f"The handover site of {slug(p['name'])}, written by EAOS. Build: zensical build (or mkdocs build).")
    (root / 'mkdocs.yml').write_text(config + MERMAID, encoding='utf-8')
    return [Emitted('handover/mkdocs.yml', 'zensical', ('zensical', 'build', '--strict', '-f', '{path}'))]
