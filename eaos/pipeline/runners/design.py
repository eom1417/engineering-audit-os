"""What a check writes of the project's look and of how to extend it, beside its reports: the design inventory, its gallery, the proposed tokens, the guide's draft."""
import json
from pathlib import Path


def design_inventory(context):
    """What the screens really show, from the pages the lock saved (eaos/analysis/design/inventory.py): design/inventory.json."""
    from ...analysis.design.inventory import write as inventory
    runtime = getattr(context, 'runtime', None)
    if runtime:
        inventory(Path(runtime) / 'behavior-lock' / 'look' / 'original', context.out, context.target)


def design_gallery(context):
    from ...analysis.design.inventory import with_pictures
    from ...report.human_report.design import gallery
    drawn = with_pictures(context.out)
    if drawn: (context.out / 'design' / 'gallery.html').write_text(gallery(drawn), encoding='utf-8')


def proposed_tokens(context):
    """The tokens the look calls for, for the person and the card: design/tokens.proposed.json, W3C 2025.10."""
    from ...analysis.assessments.one_source_look import proposed
    tokens = proposed(context.out)
    if not tokens: return
    (context.out / 'design').mkdir(parents=True, exist_ok=True)
    (context.out / 'design' / 'tokens.proposed.json').write_text(json.dumps(tokens, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')


def guide_draft(context):
    """The project's extension guide as EAOS would write it, in extending/ of the report (M18.3), for its card and batch."""
    from ...analysis.repair import project_guide
    drawn = project_guide.drawn_from_report(context.target, context.out)
    if not drawn: return                 # a path that does not read the layers has none to draw it from
    (context.out / 'extending').mkdir(parents=True, exist_ok=True)
    (context.out / 'extending' / project_guide.NAME).write_text(project_guide.text(drawn, Path(context.target).name), encoding='utf-8')
