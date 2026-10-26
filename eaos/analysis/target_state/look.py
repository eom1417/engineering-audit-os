"""The look, drawn and reviewed at almost no tokens: free pinned design libraries (eaos/data/toolchain.json, stage S06)
held to one EAOS standard (eaos/data/design.json). The assistant spends its judgement on taste only: it reads the
sources, picks or blends a direction, and writes the result as one DESIGN.md (Google Stitch's format). A build turns it
into design tokens and shadcn/ui components; a check's screen review judges every page against it (the redesign of an
existing project: its departures become design cards, fixed in batches like any other)."""
import json
import subprocess
from pathlib import Path

DATA = Path(__file__).resolve().parents[2] / 'data' / 'design.json'
# What each pinned source offers, inside its checkout.
SOURCES = {'ui-ux-pro-max': ('src/ui-ux-pro-max/scripts/search.py', 'styles, palettes, font pairings and UX rules by product type'),
           'awesome-design-md': ('design-md', 'reference design systems, one DESIGN.md each, with light and dark previews'),
           'tweakcn-themes': ('registry/themes', 'light and dark themes in the shadcn/ui token format'),
           'anthropic-skills': ('skills/frontend-design/SKILL.md', 'craft guidance for building distinctive screens')}
NAME = 'DESIGN.md'


def standard():
    return json.loads(DATA.read_text(encoding='utf-8'))


def brief(product=''):
    """{standard, components, fonts, sources, suggestion}: what a look is drawn from. `suggestion`: the design system
    UI UX Pro Max recommends for `product` (its own offline search), when it is installed."""
    from ...core.toolchain import checkout, registry
    tools = {t['name']: t for t in registry()['tools']}
    sources = {}
    for name, (inside, offers) in SOURCES.items():
        where = checkout(tools[name]) / inside
        sources[name] = ({'path': str(where), 'offers': offers} if where.exists()
                         else {'missing': True, 'offers': offers, 'install': f'python -m eaos tools install --only {name}'})
    return {**standard(), 'sources': sources, 'suggestion': _suggest(sources['ui-ux-pro-max'], product) if product else None}


def _suggest(source, product):
    from ...core.toolchain import tool_env
    if source.get('missing'): return None
    done = subprocess.run(['python3', source['path'], product, '--design-system', '--format', 'markdown'],  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit -- the pinned design-system script, a list argv, no shell
                          capture_output=True, text=True, timeout=120, env=tool_env())
    return done.stdout.strip()[:8000] if done.returncode == 0 else None


def target(report):
    """The project's chosen look (DESIGN.md beside its report), or None: the screen review judges every page against it."""
    path = Path(report).parent / NAME
    return path.read_text(encoding='utf-8')[:12000] if path.is_file() else None


def for_report(report, product=''):
    """design_brief: the sources and the standard, the suggestion for `product`, and the project's look today."""
    return {**brief(product), 'current': target(report),
            'what_now': 'Search the sources for this product (the suggestion is UI UX Pro Max\'s), look at the reference '
                        'DESIGN.md files and the project\'s own screen pictures, then propose the person two or three '
                        'directions, your recommendation first. Write the chosen one as one DESIGN.md in Google Stitch\'s '
                        'format, held to `standard` (the fonts from `fonts.arabic` when the app speaks Arabic), and save it '
                        'with design_choose.'}


def choose(report, content):
    """design_choose: the chosen look saved beside the report; the screen review then judges every page against it."""
    if not str(content or '').strip().startswith('#'): raise ValueError('the design must be a DESIGN.md: Markdown starting with its title')
    path = Path(report).parent / NAME
    path.write_text(content.strip() + '\n', encoding='utf-8')
    return {'saved': str(path),
            'what_now': 'Run the screen review again against it: audit with again_from="visual" (the rest of the check is '
                        'kept). Every page that departs from DESIGN.md becomes a design card; fix them in a batch like any other.'}
