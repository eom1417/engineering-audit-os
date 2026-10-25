"""The page routes a project's files make (the first layer of screen discovery, M5.2: rules): the folders a framework
turns into pages by their names (Next.js, Nuxt, SvelteKit, Astro, vite-plugin-pages, Expo Router, Streamlit's pages/),
so a page no link reaches is still opened (Vitesse's /README, Streamlit's pages, Expo's onboarding steps were never
pictured). A page with a parameter in its name ([id], :id, $id) is left to the links that fill it."""
import json
import re
from pathlib import Path

PAGES = ('.vue', '.md', '.mdx', '.tsx', '.jsx', '.ts', '.js', '.astro', '.svelte')
# (dependency, folder, the files of it that are pages): each dependency the app has adds its folder
LAYOUTS = (
    ('expo-router', 'app', 'any'),
    ('next', 'pages', 'any'), ('next', 'src/pages', 'any'), ('next', 'app', 'page'), ('next', 'src/app', 'page'),
    ('@sveltejs/kit', 'src/routes', '+page'),
    ('nuxt', 'pages', 'any'), ('astro', 'src/pages', 'any'),
    ('vite-plugin-pages', 'src/pages', 'any'), ('unplugin-vue-router', 'src/pages', 'any'),
)
FILE_ROUTER = re.compile(r'vue-router/(vite|unplugin)|unplugin-vue-router|vite-plugin-pages')
URL = re.compile(r'''^\s*path\(\s*['"]([^'"]*)['"]\s*,(?!\s*include)''', re.M)
INCLUDE = re.compile(r'''path\(\s*['"]([^'"]*)['"]\s*,\s*include\(\s*['"]([\w.]+)['"]''')
DYNAMIC = re.compile(r'[\[:$*]')
MOST = 80


def file_routes(root):
    """['/about', ...]: the page routes the files of the project at `root` make, MOST at most."""
    from ..setup_python import _requirements, folder as python_folder
    root = Path(root)
    found, python = _web_routes(root), python_folder(root)
    if python is not None and 'streamlit' in _requirements(root / python):
        found += [_streamlit(path) for path in sorted((root / python / 'pages').glob('*.py'))]
    if python is not None and (root / python / 'manage.py').is_file(): found += _django(root / python)
    return list(dict.fromkeys(route for route in found if route))[:MOST]


def _web_routes(root):
    """The routes of the JavaScript app's page folders, by the framework its package depends on."""
    from ..setup_detect import app_folder, dependencies
    web = app_folder(root)
    if web is None: return []
    app = root / web
    try: deps = dependencies(json.loads((app / 'package.json').read_text(encoding='utf-8')))
    except (OSError, ValueError): deps = {}
    if any(FILE_ROUTER.search(c.read_text(encoding='utf-8', errors='replace')) for c in app.glob('vite.config.*')):
        deps['vite-plugin-pages'] = ''      # Vue Router's own file routes (vue-router/vite): Vitesse
    return [route for dependency, folder, kind in LAYOUTS if dependency in deps for route in _routes(app / folder, kind)]


def _routes(folder, kind):
    """The routes of the page files under `folder`: every page file (`any`), or only those named page.* or +page.*."""
    routes = []
    for path in sorted(folder.rglob('*')) if folder.is_dir() else []:
        if path.suffix not in PAGES or not path.is_file() or 'node_modules' in path.parts: continue
        if kind != 'any' and path.stem != kind: continue
        route = _route(path.relative_to(folder), kind)
        if route: routes.append(route)
    return routes


def _route(relative, kind):
    """A page file's route, None for what is no page of its own: a layout, an API, a "not found", a parameter."""
    parts = list(relative.parent.parts) + ([] if kind != 'any' else [relative.stem])
    if any(map(_hidden, parts)): return None
    parts = [p for p in parts if not (p.startswith('(') and p.endswith(')'))]      # a route group adds nothing to the address
    if parts and parts[-1] == 'index': parts.pop()
    return '/' + '/'.join(parts)


def _django(app):
    """The pages of a Django project's URL configuration, each include's prefix joined (LocalLibrary's /catalog/books/:
    its catalog/urls.py says only books/)."""
    settings = next((p for p in sorted(app.glob('*/settings.py'))), None)
    root = re.search(r'''ROOT_URLCONF\s*=\s*['"]([\w.]+)''', settings.read_text(encoding='utf-8', errors='replace')) if settings else None
    return _urlconf(app, root[1], '/', 0) if root else []


def _urlconf(app, module, prefix, depth):
    """The routes without parameters of URL configuration `module`, under `prefix`, its includes three deep."""
    path = app / (module.replace('.', '/') + '.py')
    text = path.read_text(encoding='utf-8', errors='replace') if path.is_file() else ''
    routes = [prefix + route for route in URL.findall(text) if not DYNAMIC.search(route) and '<' not in route]
    for inner, included in INCLUDE.findall(text) if depth < 3 else []: routes += _urlconf(app, included, prefix + inner, depth + 1)
    return routes


def _hidden(part):
    """Whether a part of a page file's path makes it no page of its own: a layout, an API, a parameter."""
    return part.startswith(('_', '+', '.')) or part in ('api', 'components') or bool(DYNAMIC.search(part))


def _streamlit(path):
    """A Streamlit page's address: its file name without the number and marks before it (1_📈_Plotting.py: /Plotting)."""
    name = re.sub(r'^[\W\d_]+', '', path.stem)
    return '/' + name if name else None
