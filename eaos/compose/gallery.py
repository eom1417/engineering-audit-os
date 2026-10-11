"""gallery/index.html: the UI gallery of the report, from the check's own records and local files only.

    Screens     every picture of live/screens.json (each page in its states, at phone and desktop width), with the
                visual reviewer's findings (nodes/visual_reviewer/findings.json) drawn on it as boxes over their region
    Journeys    every rrweb recording of live/journeys/rrweb/, replayed in the page by rrweb-player (copied beside it
                from the pinned toolchain), and the Playwright traces beside them
    City        the ground plan of architecture/city.cc.json (CodeCharta): a rectangle per file, its area the lines of
                code, its colour how often it changed; the 3D city opens in CodeCharta from the same file; and the
                dependency clusters of Emerge, each a local page
A part with nothing to show says why, from the run's manifest.
"""
import html
import json
import shutil
from pathlib import Path

WORDS = {
    'title': ('معرض الواجهة', 'UI gallery'),
    'screens': ('الشاشات بحالاتها', 'Screens in their states'),
    'journeys': ('رحلات المستخدم', 'User journeys'),
    'city': ('مدينة الكود', 'The code city'),
    'play': ('شغّل الرحلة', 'Play the journey'),
    'trace': ('تتبّع Playwright (افتحه بـ npx playwright show-trace)', 'Playwright trace (open with npx playwright show-trace)'),
    'city_note': ('المساحة عدد الأسطر، واللون كثرة التغيير؛ المدينة الثلاثية الأبعاد تنفتح في CodeCharta من الملف نفسه:',
                  'Area is lines of code, colour is how often it changed; the 3D city opens in CodeCharta from the same file:'),
    'clusters': ('مجموعات الاعتماد (Emerge)', 'Dependency clusters (Emerge)'),
    'none': ('ما فيه شي يُعرض هنا', 'Nothing to show here'),
}
STAGES = {'screens': 'screens', 'journeys': 'journeys', 'city': 'architecture'}


def _load(path, default):
    try: return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError): return default


def _why_not(report, part, ar):
    row = (_load(report / 'run-manifest.json', {}).get('stages') or {}).get(STAGES[part]) or {}
    return html.escape(row.get('reason') or WORDS['none'][0 if ar else 1])


def screens(report, ar):
    rows = [r for r in (_load(report / 'live/screens.json', {}).get('rows') or []) if r.get('screenshot')]
    if not rows: return f'<p>{_why_not(report, "screens", ar)}</p>'
    findings = {}
    for finding in _load(report / 'nodes/visual_reviewer/findings.json', {}).get('findings') or []:
        findings.setdefault(finding['file'], []).append(finding)
    out = ['<div class="grid">']
    for row in rows:
        boxes = ''.join(
            f'<span class="box {html.escape(f["severity"])}" title="{html.escape(f["title"] + ": " + f["why"])}" style="left:{f["region"]["x"] * 100:.1f}%;'
            f'top:{f["region"]["y"] * 100:.1f}%;width:{f["region"]["width"] * 100:.1f}%;height:{f["region"]["height"] * 100:.1f}%"></span>'
            for f in findings.get(row['screenshot'], []))
        notes = ''.join(f'<li><b>{html.escape(f["title"])}</b>: {html.escape(f["why"])}</li>' for f in findings.get(row['screenshot'], []))
        out.append(f'<figure><div class="shot"><img loading="lazy" src="../{html.escape(row["screenshot"])}" alt="">{boxes}</div>'
                   f'<figcaption>{html.escape(str(row.get("url")))} · {html.escape(str(row.get("viewport")))} · '
                   f'{html.escape(str(row.get("variant")))}</figcaption>{f"<ul>{notes}</ul>" if notes else ""}</figure>')
    return '\n'.join(out + ['</div>'])


def journeys(report, folder, ar):
    recordings = sorted((report / 'live/journeys/rrweb').glob('*.rrweb.json'))
    traces = sorted((report / 'live/journeys/traces').glob('*.zip'))
    if not recordings and not traces: return f'<p>{_why_not(report, "journeys", ar)}</p>'
    from ..toolchain import node_modules
    player = node_modules('rrweb') / 'rrweb-player/dist'
    if recordings and (player / 'rrweb-player.umd.cjs').is_file():
        (folder / 'vendor').mkdir(exist_ok=True)
        shutil.copyfile(player / 'rrweb-player.umd.cjs', folder / 'vendor/rrweb-player.js')
        shutil.copyfile(player / 'style.css', folder / 'vendor/rrweb-player.css')
    events = [_load(path, {}) for path in recordings]
    (folder / 'journeys.js').write_text('window.EAOS_JOURNEYS = ' + json.dumps(events, ensure_ascii=False) + ';\n', encoding='utf-8')
    out = []
    for index, journey in enumerate(events):
        out.append(f'<section class="journey"><h3>{html.escape(journey.get("title") or str(index + 1))}</h3>'
                   f'<button onclick="play({index}, this)">{WORDS["play"][0 if ar else 1]}</button><div id="j{index}"></div></section>')
    out += [f'<p><a href="../live/journeys/traces/{html.escape(t.name)}">{html.escape(t.name)}</a> — {WORDS["trace"][0 if ar else 1]}</p>'
            for t in traces]
    return '\n'.join(out)


def _tree(nodes, attributes):
    """[(path, lines, changes, complexity, children)] of the cc.json tree, folders summing their files."""
    out = []
    for node in nodes:
        if node.get('type') == 'File':
            row = attributes.get(node['id']) or {}
            out.append((node['name'], row.get('rloc') or row.get('loc') or 0, row.get('number_of_commits') or 0, row.get('complexity'), []))
        else:
            children = [(f"{node['name']}/{c[0]}",) + c[1:] for c in _tree(node.get('children') or [], attributes)]
            if children: out.append((node['name'], sum(c[1] for c in children), max(c[2] for c in children), None, children))
    return [row for row in out if row[1] > 0]


def _plan(rows, x, y, width, height, vertical, peak, out):
    """Slice the rectangle among `rows` by their lines, alternating the direction at each folder level."""
    total = sum(row[1] for row in rows) or 1
    for name, lines, changes, complexity, children in rows:
        share = lines / total
        w, h = (width * share, height) if vertical else (width, height * share)
        if children: _plan(children, x, y, w, h, not vertical, peak, out)
        else:
            heat = int(230 - 180 * (changes / peak if peak else 0))
            out.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{max(w, 0.1):.2f}" height="{max(h, 0.1):.2f}" fill="rgb(240,{heat},{heat})" '
                       f'stroke="#fff" stroke-width="0.3"><title>{html.escape(name)}: {lines} lines, {changes} changes, '
                       f'complexity {complexity}</title></rect>')
        x, y = (x + w, y) if vertical else (x, y + h)


def city(report, ar):
    record = _load(report / 'architecture/map.json', {})
    data = _load(report / 'architecture/city.cc.json', {})
    out = []
    if data:
        rows = _tree(data.get('files') or [], ((data.get('lenses') or {}).get('metrics') or {}).get('attributes') or {})
        peak, rects = max((row[2] for row in rows), default=0), []
        _plan(rows, 0, 0, 1000, 600, True, peak, rects)
        out += [f'<p>{WORDS["city_note"][0 if ar else 1]} <a href="../architecture/city.cc.json">city.cc.json</a></p>',
                f'<svg viewBox="0 0 1000 600" class="city" role="img">{"".join(rects)}</svg>']
    pages = ((record.get('clusters') or {}).get('pages') or {})
    if pages:
        out += [f'<h3>{WORDS["clusters"][0 if ar else 1]}</h3>'] + [f'<p><a href="../architecture/{html.escape(page)}">{html.escape(language)}</a></p>'
                                                                  for language, page in sorted(pages.items())]
    return '\n'.join(out) or f'<p>{_why_not(report, "city", ar)}</p>'


STYLE = """body{font-family:system-ui,sans-serif;margin:0 auto;max-width:1200px;padding:16px;line-height:1.5}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:16px}figure{margin:0}
.shot{position:relative}.shot img{width:100%;display:block;border:1px solid #ccc}
.box{position:absolute;border:2px solid #d32f2f;background:rgba(211,47,47,.12)}.box.medium{border-color:#ef6c00}.box.low{border-color:#f9a825}
figcaption{font-size:13px;color:#555}.city{width:100%;height:auto;border:1px solid #ccc}button{min-height:44px;padding:0 16px}"""


def write(report, language='ar'):
    """gallery/index.html; returns the parts that had something to show."""
    report, ar = Path(report), language == 'ar'
    folder = report / 'gallery'
    folder.mkdir(exist_ok=True)
    parts = {'screens': screens(report, ar), 'journeys': journeys(report, folder, ar), 'city': city(report, ar)}
    body = ''.join(f'<h2>{WORDS[name][0 if ar else 1]}</h2>{text}' for name, text in parts.items())
    script = ('<link rel="stylesheet" href="vendor/rrweb-player.css"><script src="vendor/rrweb-player.js"></script><script src="journeys.js"></script>'
              '<script>function play(i,b){b.remove();new rrwebPlayer({target:document.getElementById("j"+i),'
              'props:{events:window.EAOS_JOURNEYS[i].events,width:800,height:450}});}</script>') if (folder / 'vendor/rrweb-player.js').is_file() else ''
    (folder / 'index.html').write_text(f'<!doctype html><html lang="{language}" dir="{"rtl" if ar else "ltr"}"><head><meta charset="utf-8">'
                                       f'<meta name="viewport" content="width=device-width,initial-scale=1"><title>{WORDS["title"][0 if ar else 1]}</title>'
                                       f'<style>{STYLE}</style>{script}</head><body><h1>{WORDS["title"][0 if ar else 1]}</h1>{body}</body></html>\n',
                                       encoding='utf-8')
    return [name for name, text in parts.items() if not text.startswith('<p>') or '<a ' in text]
