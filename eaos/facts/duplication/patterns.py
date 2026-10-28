"""One source per pattern (M15), read from the source: the look written outside the tokens file (look.py) and the element
trees repeated across the screens (element_trees.py). The near copies of code are jscpd's and the ways of working
ast-grep's (eaos/rules/ast-grep/rules/idioms.yml); eaos/analysis/assessments/one_source.py reads the four together.
"""
from collections import defaultdict

from .. import make
from ..source import language_of
from . import element_trees, look

NAME = 'patterns'
VERSION = '1'
LIMITATIONS = [
    'The look is read where it is written: a value a script computes at run time is seen only by the style census of '
    'the pictured pages (live/screens.json).',
    'An element tree is its tags and static classes; two trees alike in structure can still differ in what they mean.',
]
PLACES = 200         # places kept per value of the look (the fix gate counts them per file)


def _scan(source):
    """(the look's values by (kind, value), the files that are its home, the element-tree candidates, files read)."""
    by_value, homes, rows, read = defaultdict(list), [], [], 0
    for item in source.readable():
        rel = item['path']
        language = language_of(rel)
        if not (language or rel.endswith(look.STYLESHEETS + ('.html', '.htm'))): continue
        text = source.text(rel)
        if text is None: continue
        read += 1
        if look.is_tokens_file(rel, text): homes.append(rel)
        for kind, value, line in look.values(rel, text, language): by_value[(kind, value)].append({'path': rel, 'line': line})
        rows += element_trees.candidates(rel, element_trees.file_trees(text, rel, language))
    return by_value, homes, rows, read


def run(target, source, **options):
    by_value, homes, rows, read = _scan(source)
    sha = source.content_fingerprint
    facts = [make('look_value', NAME, VERSION, sha, places[0], {'kind': kind, 'value': value, 'count': len(places), 'places': places[:PLACES]},
                  limitations=LIMITATIONS[:1]) for (kind, value), places in sorted(by_value.items())]
    facts.append(make('look_home', NAME, VERSION, sha, {'path': homes[0] if homes else None}, {'paths': homes}))
    facts += [make('ui_pattern', NAME, VERSION, sha, {'path': group['members'][0]['path'], 'start_line': group['members'][0]['line']},
                   group, limitations=LIMITATIONS[1:]) for group in element_trees.repeated(rows)]
    summary = {'files_read': read, 'look_values': sum(len(p) for p in by_value.values()), 'tokens_files': homes,
               'element_trees': len(rows), 'ui_patterns': len(facts) - len(by_value) - 1}
    return {'facts': facts, 'summary': summary, 'available': True, 'input_sha': sha, 'reason': None}
