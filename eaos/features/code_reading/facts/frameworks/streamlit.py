"""Streamlit applications: a script that renders at module level is a web page, served at `/`.

A Streamlit app is a web interface even when it is started by a command (`streamlit run app.py`, or a
launcher that calls it): the command is one surface, the page it serves is another. Only a file that
imports streamlit and calls it at the top level renders; a module whose Streamlit calls sit inside
functions is a view the app composes, not a page. Pages of a multi-page app are read from
`st.Page("file.py", url_path="x")` and from the `pages/` folder, where Streamlit drops a leading number.
"""
import re

LANGUAGES = ('python',)
IMPORT = re.compile(r'^(?:import streamlit\b|from streamlit\b)', re.M)
RENDER = re.compile(r'^(?:st|streamlit)\.(?:set_page_config|title|header|markdown|write|sidebar|navigation|tabs|columns)\b', re.M)
PAGE = re.compile(r'''\bst\.Page\(\s*(['"])(?P<file>[^'"]+)\1(?P<rest>[^)]*)\)''')
URL_PATH = re.compile(r'''url_path\s*=\s*(['"])(?P<path>[^'"]*)\1''')


def detect(context):
    if not IMPORT.search(context.text): return []
    found = []
    rel = context.rel
    render = RENDER.search(context.text)
    if render:
        parts = rel.split('/')
        if 'pages' in parts[:-1]:
            route = '/' + re.sub(r'^\d+[_ -]*', '', parts[-1].rsplit('.', 1)[0])
        else:
            route = '/'
        found.append({'surface': 'page', 'route': route, 'http_method': 'GET', 'handler': '<module>',
                      'framework': 'streamlit', 'line': context.line_of(render.start())})
    for match in PAGE.finditer(context.text):
        explicit = URL_PATH.search(match.group('rest'))
        stem = match.group('file').rsplit('/', 1)[-1].rsplit('.', 1)[0]
        route = '/' + (explicit.group('path') if explicit else re.sub(r'^\d+[_ -]*', '', stem))
        found.append({'surface': 'page', 'route': route, 'http_method': 'GET', 'handler': match.group('file'),
                      'framework': 'streamlit', 'line': context.line_of(match.start())})
    return found
