"""A single self-contained HTML view of a dossier: navigation, search, and no external assets."""
import html
import json
from pathlib import Path
import re

ORDER = ['DECISION-BRIEF.md', 'SYSTEM-MAP.md', 'FLOWS.md', 'DOMAIN-AND-DATA.md', 'CONTRACTS.md',
         'COUPLING-ATLAS.md', 'EVOLUTION.md', 'VERIFICATION-MAP.md', 'DELTA.md', 'PROVENANCE.md']
STYLE = """
:root{color-scheme:light dark;--line:#8883;--muted:#7a7a7a}
*{box-sizing:border-box}
body{margin:0;font:15px/1.6 system-ui,'Segoe UI',sans-serif;display:grid;grid-template-columns:260px 1fr}
nav{position:sticky;top:0;height:100vh;overflow:auto;padding:16px;border-inline-end:1px solid var(--line)}
nav a{display:block;padding:4px 0;text-decoration:none;color:inherit}
nav a:hover{text-decoration:underline}
main{padding:24px 32px;max-width:78ch}
h1{font-size:1.5rem} h2{font-size:1.15rem;margin-top:2rem;border-top:1px solid var(--line);padding-top:1rem}
table{border-collapse:collapse;width:100%;margin:12px 0;font-size:14px}
th,td{border:1px solid var(--line);padding:6px 8px;text-align:start;vertical-align:top}
blockquote{margin:0 0 16px;padding:10px 14px;border-inline-start:3px solid var(--line);color:var(--muted);font-size:14px}
pre{background:#8881;padding:12px;overflow:auto;font-size:13px}
input{width:100%;padding:8px;margin-bottom:12px;border:1px solid var(--line);border-radius:6px;background:transparent;color:inherit}
section[hidden]{display:none}
.marker{font-weight:600}
"""
SEARCH = """
const box=document.getElementById('q');
box.addEventListener('input',()=>{
  const term=box.value.trim().toLowerCase();
  document.querySelectorAll('main section').forEach(section=>{
    if(!term){section.hidden=false;section.querySelectorAll('tr').forEach(r=>r.hidden=false);return;}
    let any=section.textContent.toLowerCase().includes(term);
    section.hidden=!any;
    section.querySelectorAll('tbody tr').forEach(row=>{row.hidden=!row.textContent.toLowerCase().includes(term);});
  });
});
"""


def cells(line):
    return [cell.strip() for cell in line.strip().strip('|').split('|')]


def to_html(markdown):
    out, rows, in_table, in_code = [], [], False, False
    lines = markdown.split('\n')
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.startswith('```'):
            if in_code:
                out.append('</pre>'); in_code = False
            else:
                out.append('<pre>'); in_code = True
            index += 1
            continue
        if in_code:
            out.append(html.escape(line)); index += 1; continue
        if line.startswith('|'):
            rows.append(cells(line))
            in_table = True
            index += 1
            continue
        if in_table:
            out.append(render_table(rows)); rows = []; in_table = False
        if line.startswith('#'):
            level = len(line) - len(line.lstrip('#'))
            out.append(f'<h{level}>{html.escape(line[level:].strip())}</h{level}>')
        elif line.startswith('> '):
            out.append(f'<blockquote>{html.escape(line[2:])}</blockquote>')
        elif line.startswith('- '):
            items = []
            while index < len(lines) and lines[index].startswith('- '):
                items.append(f'<li>{html.escape(lines[index][2:])}</li>'); index += 1
            out.append('<ul>' + ''.join(items) + '</ul>')
            continue
        elif line.strip():
            out.append(f'<p>{html.escape(line)}</p>')
        index += 1
    if in_table: out.append(render_table(rows))
    return '\n'.join(out)


def render_table(rows):
    if not rows: return ''
    body = [row for row in rows[1:] if not all(re.fullmatch(r'-{2,}', cell or '') for cell in row)]
    head = '<tr>' + ''.join(f'<th>{html.escape(cell)}</th>' for cell in rows[0]) + '</tr>'
    lines = ''.join('<tr>' + ''.join(f'<td>{html.escape(cell)}</td>' for cell in row) + '</tr>' for row in body)
    return f'<table><thead>{head}</thead><tbody>{lines}</tbody></table>'


def build(out, title=None):
    out = Path(out)
    documents = [name for name in ORDER if (out / name).is_file()]
    if not documents: raise ValueError('No rendered artifacts found; build a dossier first')
    dossier = json.loads((out / 'dossier.json').read_text()) if (out / 'dossier.json').is_file() else {}
    heading = title or (dossier.get('provenance', {}).get('target') or 'Engineering dossier')
    sections, navigation = [], []
    for name in documents:
        anchor = name.replace('.md', '').lower()
        navigation.append(f'<a href="#{anchor}">{html.escape(name.replace(".md", ""))}</a>')
        sections.append(f'<section id="{anchor}">' + to_html((out / name).read_text(encoding='utf-8')) + '</section>')
    page = (f'<!doctype html><html dir="auto"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{html.escape(str(heading))}</title><style>{STYLE}</style></head><body>'
            f'<nav><input id="q" placeholder="search / بحث" aria-label="search">' + ''.join(navigation) + '</nav>'
            f'<main><h1>{html.escape(str(heading))}</h1>' + ''.join(sections) + '</main>'
            f'<script>{SEARCH}</script></body></html>')
    target = out / 'index.html'
    target.write_text(page, encoding='utf-8')
    return {'out': str(out), 'page': str(target), 'documents': documents, 'bytes': len(page),
            'limits': 'A rendering of the same records; it adds navigation, never content.'}
