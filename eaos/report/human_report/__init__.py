"""human/index.html: the report for a person, in one self-contained page, Arabic and English.

The report's other files are written for AI agents and stay exactly as they are. This page reads the same
records (plan.json, dossier.json, debt-register.json, target-architecture.json, gap-matrix.json,
run-manifest.json, and the graph, flow and structure facts) and shows six reports on one page: the project
summary, the gaps and risks, the structure map (today's parts, their imports, files, functions and pages;
eaos/analysis/arch_map.py), the system map (every page, API, server handler, part and table; eaos/analysis/system_map.py),
the target structure with the gap each part has closed, and the plan with its progress, the work log
(progress['handover'], eaos/journeys/handover.py brief) and every task card. progress['eaos'] stamps the page with the
EAOS that built it; progress['report_errors'] and every part that failed show in a warning at the top. No external asset, no network: inline CSS, inline SVG, a little inline JS. Every
number on the page carries its meaning in words next to it.

Progress comes from the ledger when the caller passes one (progress={'waves': [...], 'ledger': L}): a card
is closed only when it is 'done' (an EAOS fix merged into the person's main branch); a problem a later check no
longer finds leaves the plan, it is not counted as closed; 'on_branch' waits for the person and is not closed. With no ledger, a card a batch
kept counts as done, as before.

What a problem is, its area and severity, and the health score are computed once, in eaos/analysis/model.py, and
read here: the Studio and this page show the same numbers.
"""
import json
from pathlib import Path

from ...analysis import model as M
from .. import pipeline_sheet
from ...core.markup import both as T, esc
from ...analysis.model import records, score, task_cards
from .assets import CSS, JS, MAP_JS, SYSTEM_JS
from .html import lit, num, tech, unavailable, w
from .layers import section_layers
from .plan import section_plan
from .structure import section_structure
from .summary import section_gaps, section_summary
from .system import pipeline_part, section_system
from .target import section_target
from .words import SECTIONS, W


# ---------------------------------------------------------------- data

def model(report, progress=None):
    """The one model (eaos/analysis/model.py), with the maps this page draws."""
    m = records(report, progress)
    return {**m, **M.maps(Path(report), m['target'], pipeline_builder=pipeline_sections)}


maps = M.maps
pipeline_sections = M.pipeline_sections
component_problems = M.component_problems


# ---------------------------------------------------------------- page

def branch_line(branch):
    """Which branch this report is for (the check, the fixes and the progress follow it), and the reports of the others."""
    if not branch: return ''
    main = (T(' (الفرع الرئيسي)', ' (the main branch)') if branch.get('main') == branch['name'] else
            T(f' · الفرع الرئيسي: {lit(branch["main"])}', f' · main branch: {lit(branch["main"])}') if branch.get('main') else '')
    others = ' '.join(f'<a href="{esc(o["href"])}">{lit(o["name"])}</a>' for o in branch.get('others') or [])
    return (f'<div class="branch" data-part="branch">{T("الفرع:", "Branch:")} <b>{lit(branch["name"])}</b>{main}'
            + (f' · {T("تقارير فروع أخرى:", "Other branches:")} {others}' if others else '') + '</div>')



def stamp(eaos, cls='stamp'):
    """Which EAOS built the page, from progress['eaos'] = {'version', 'commit', 'built' (ISO time)}; '' without it."""
    if not isinstance(eaos, dict) or not (eaos.get('version') or eaos.get('commit')): return ''
    part = ' data-part="stamp"' if cls == 'stamp' else ''
    return f'<div class="{cls} muted small"{part}>{T("بنته نسخة EAOS", "Built by EAOS")} {_stamp_line(eaos)}</div>'


def _stamp_line(eaos):
    """The stamp's known parts, joined: the version, the commit, the digest (in full on hover), when it was built."""
    built = str(eaos.get('built') or '').replace('T', ' ')[:16]
    bits = [lit(eaos['version']) if eaos.get('version') else '', lit(str(eaos['commit'])[:12]) if eaos.get('commit') else '',
            f'<span title="{esc(eaos["digest"])}">{lit(str(eaos["digest"])[:12])}</span>' if eaos.get('digest') else '',
            num(built, 'when this page was built (UTC)') if built else '']
    return ' · '.join(b for b in bits if b)


def error_banner(errors):
    """What could not be built, and why, at the top of the page; '' when everything was built."""
    if not errors: return ''
    items = ''.join(f'<li>{T("لم يُبنَ:", "Not built:", cls="lbl")} <b>{esc(e.get("section") or "")}</b> {tech(e.get("error"))}</li>' if isinstance(e, dict)
                    else f'<li>{tech(str(e))}</li>' for e in errors)
    return (f'<div class="wrap"><div class="card errors" data-part="report-errors" role="alert"><h4>{T("أجزاء من هذا التقرير لم تُبنَ", "Parts of this report could not be built")}</h4>'
            f'<p class="small">{T("بقية الصفحة سليمة. هذه الأجزاء تقول «غير متاح» حتى يُصلح سببها:", "The rest of the page is sound. These parts say “not available” until their cause is fixed:")}</p>'
            f'<ul class="small">{items}</ul></div></div>')


INTRO = {'summary': ('صحة المشروع في صفحة واحدة: الدرجة، والمجالات الخمسة، وأهم المشاكل، وما لم نفحصه.',
                     'The health of the project on one page: the score, the five areas, the main problems, and what we did not check.'),
         'gaps': ('كل مشكلة: أين هي، وما حالها الآن وما المطلوب، وخطورتها، وهل يصلحها EAOS آليًا.',
                  'Every problem: where it is, what it is now and what it should be, how serious it is, and whether EAOS fixes it.'),
         'layers': ('النظام كطبقات كما تقرؤه شركة برمجيات: ما يصل إلى المتصفح، وحماية كل نقطة طلب، وقواعد البيانات، ومكان قواعد العمل، والتشغيل، والاختبارات.',
                    'The system as layers, as a software firm reads it: what ships to the browser, the guard of every endpoint, the data rules, where the business rules live, operations and tests.'),
         'structure': ('أجزاء المشروع اليوم وأين تتركز المشاكل، وكيف يعتمد كل جزء على غيره، حتى الملفات والدوال والصفحات.',
                       'The parts of the project today, where problems gather, and how each depends on the others, down to files, functions and pages.'),
         'system': ('النظام من أوله إلى آخره: كل صفحة، وكل نقطة API تستدعيها، والكود في الخادم الذي يجيبها، وما يستخدمه، والجداول والخدمات التي يصل إليها.',
                    'The system end to end: every page, every API it calls, the server code that answers it, what that code uses, and the tables and services it reaches.'),
         'target': ('ما سيصبح عليه البرنامج: طبقاته وأجزاؤه، ومن أين يأتي كل جزء من اليوم، وكم أُغلق من الفجوة في كل جزء.',
                    'What the program will become: its layers and parts, where each part comes from today, and how much of the gap each has closed.'),
         'plan': ('أين وقف العمل ومن عمل ماذا، وترتيب العمل مرحلة بعد مرحلة، وما أُنجز، وكل بطاقة مهمة وحالتها، وما ينتظر قرارك.',
                  'Where the work stopped and who did what, the order of the work milestone by milestone, what is done, every task card and its state, and what waits for your decision.')}


def failure(section, error):
    return {'section': section, 'error': f'{type(error).__name__}: {error}'[:300]}


def _with_cards(m, errors):
    """The model with its task cards; none, with the failure noted, when they cannot be built."""
    try: return dict(m, cards=task_cards(m))
    except Exception as error:
        errors.append(failure('cards', error))
        return dict(m, cards=[])


def _parts(m, name, errors):
    """{section: its HTML}; a section that cannot be built says "not available" and its failure is noted."""
    parts = {}
    for section, build in (('summary', lambda: section_summary(m, name)), ('gaps', lambda: section_gaps(m)), ('layers', lambda: section_layers(m)),
                           ('structure', lambda: section_structure(m)), ('system', lambda: section_system(m) + pipeline_part(m)),
                           ('target', lambda: section_target(m)), ('plan', lambda: section_plan(m))):
        try: parts[section] = build()
        except Exception as error:     # one broken record costs its section, not the page or the audit
            parts[section] = unavailable(section, error)
            errors.append(failure(section, error))
    return parts


def render_parts(m, name, lang='ar'):
    """(the page, [{section, error}] of every part that could not be built): a section that fails shows "not available"."""
    errors = list(m.get('map_errors') or [])
    m = _with_cards(m, errors)
    parts = _parts(m, name, errors)
    progress = m.get('progress') or {}
    told = _told(progress)
    nav = ''.join(f'<a href="#{s}" data-tab="{s}">{w(s)}</a>' for s in SECTIONS)
    body = ''.join(f'<section id="{s}" class="report" data-report="{s}"><header class="sec-head"><h2>{w(s)}</h2>'
                   f'<p class="muted">{T(*map(esc, INTRO[s]))}</p></header>{parts[s]}</section>' for s in SECTIONS)
    date = _audit_date(m) + branch_line(progress.get('branch')) + stamp(progress.get('eaos'))
    direction = 'rtl' if lang == 'ar' else 'ltr'
    text = (f'<!doctype html><html lang="{lang}" dir="{direction}" data-lang="{lang}"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1"><title>{esc(W["title"][0 if lang == "ar" else 1])}: {esc(name)}</title>'
            f'<style>{CSS}{pipeline_sheet.CSS}</style></head><body><header class="top"><div class="wrap top-in"><div class="brand">'
            f'<div class="kicker">{T("تقرير EAOS", "EAOS report")}</div><h1>{w("title")}: {lit(name)}</h1>{date}</div>'
            f'<div class="actions"><button type="button" id="lang" class="btn">{T("English", "العربية")}</button>'
            f'<button type="button" id="print" class="btn ghost">{T("طباعة / PDF", "Print / PDF")}</button></div></div>'
            f'<nav class="tabs wrap" aria-label="reports">{nav}</nav></header>{error_banner(told + errors)}'
            f'<main class="wrap">{body}</main><footer class="wrap muted small">'
            f'{T("هذه الصفحة للقراءة. الملفات التقنية في المجلد نفسه مكتوبة للمساعد الذكي ولم تتغير.", "This page is for reading. The technical files in the same folder are written for the AI assistant and are unchanged.")}'
            f'{stamp(progress.get("eaos"), "stamp-foot")}</footer><script>{JS}{MAP_JS}{SYSTEM_JS}</script></body></html>')
    return text, errors


def _told(progress):
    """The failures the caller noted in progress['report_errors'], each a sentence."""
    return [e for e in progress.get('report_errors') or [] if isinstance(e, str) and e.strip()]


def _audit_date(m):
    """The audit's date under the page's title, from the dossier; '' without one."""
    generated = ((m['dossier'].get('provenance') or {}).get('generated_at') or '')[:10]
    return (f'<span class="muted">{T("تاريخ الفحص:", "Audit date:")} {num(generated, "the date of the audit")}</span>' if generated else '')


def render(m, name, lang='ar'):
    return render_parts(m, name, lang)[0]


def empty(progress=None):
    return {'rows': [], 'statuses': {}, 'coverage': {}, 'score': score([], 0, known=False), 'plan': {}, 'target': {},
            'gap_matrix': {}, 'manifest': {}, 'dossier': {}, 'progress': progress or {}, 'cmap': None, 'drill': None, 'flows': None,
            'system': None, 'system_layout': None, 'pipeline': None, 'map_errors': []}


def write(report, lang='ar', name=None, progress=None):
    """Write <report>/human/index.html from the report's records and return its path.

    Never raises for missing or broken records: a section it cannot build says "not available".
    What could not be built is also written to <report>/human/errors.json as [{section, error}], [] when all was.
    """
    report = Path(report)
    errors = []
    try:
        m = model(report, progress)
    except Exception as error:
        m = empty(progress)
        errors.append(failure('records', error))
    if name is None:
        name = Path(str((m['manifest'] or {}).get('target') or report)).name
    page = report / 'human' / 'index.html'
    page.parent.mkdir(parents=True, exist_ok=True)
    lang = 'ar' if lang == 'ar' else 'en'
    try:
        text, failed = render_parts(dict(m, map_errors=errors + list(m.get('map_errors') or [])), name, lang)
    except Exception as error:
        failed = errors + [failure('page', error)]
        text = render(dict(empty(progress), map_errors=failed), name, lang)
    page.write_text(text, encoding='utf-8')
    try: (page.parent / 'errors.json').write_text(json.dumps(failed, ensure_ascii=False, indent=1), encoding='utf-8')
    except OSError: pass
    return page


# ---------------------------------------------------------------- the readability indicator
