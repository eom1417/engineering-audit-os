"""The first layer of screen discovery (M5.2): the pages a project's files and code name, at the address that shows
each, every one a page of its own; the corpus apps whose screens were missed."""
import json
import unittest
from pathlib import Path

from eaos.live.screens.crawl import code_routes, distinct
from eaos.live.screens.file_routes import file_routes
from shared_fixture import scratch


def project(files):
    root = Path(scratch())
    for name, text in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text if isinstance(text, str) else json.dumps(text))
    return root


class FileRouteTests(unittest.TestCase):
    def test_framework_page_folders_make_pages_and_parameters_layouts_and_apis_do_not(self):
        vitesse = project({'package.json': {'scripts': {'dev': 'vite'}, 'devDependencies': {'vite': '6'}},
                           'vite.config.ts': "import VueRouter from 'vue-router/vite'\n",
                           'src/pages/index.vue': '', 'src/pages/README.md': '', 'src/pages/hi/[name].vue': '', 'src/pages/[...all].vue': ''})
        self.assertEqual(file_routes(vitesse), ['/README', '/'])
        expo = project({'package.json': {'scripts': {'start': 'expo start'}, 'dependencies': {'expo': '53', 'expo-router': '5'}},
                        'app/_layout.tsx': '', 'app/+not-found.tsx': '', 'app/(tabs)/explore.tsx': '', 'app/onboarding/step-1.tsx': ''})
        self.assertEqual(file_routes(expo), ['/explore', '/onboarding/step-1'])
        next_app = project({'package.json': {'scripts': {'dev': 'next dev'}, 'dependencies': {'next': '15'}},
                            'app/page.tsx': '', 'app/about/page.tsx': '', 'app/api/x/route.ts': '', 'app/about/card.tsx': ''})
        self.assertCountEqual(file_routes(next_app), ['/', '/about'])

    def test_streamlit_pages_and_django_urls_with_their_include_prefixes(self):
        streamlit = project({'requirements.txt': 'streamlit\n', 'app.py': 'import streamlit\n', 'pages/1_📈_Plotting.py': '', 'pages/chat.py': ''})
        self.assertEqual(file_routes(streamlit), ['/Plotting', '/chat'])
        django = project({'manage.py': '', 'requirements.txt': 'Django\n', 'site/settings.py': "ROOT_URLCONF = 'site.urls'\n",
                          'site/urls.py': "urlpatterns = [\n    path('catalog/', include('catalog.urls')),\n    path('admin/', admin.site.urls),\n]\n",
                          'catalog/urls.py': "urlpatterns = [\n    path('', views.index),\n    path('books/', views.books),\n"
                                             "    path('book/<int:pk>', views.book),\n]\n"})
        self.assertEqual(file_routes(django), ['/admin/', '/catalog/', '/catalog/books/'])


class CodeRouteTests(unittest.TestCase):
    def test_an_app_routing_by_the_hash_has_its_menu_s_paths_as_hash_routes(self):
        # CoreUI: the router in App.jsx, the menu's addresses in a file of their own
        coreui = project({'src/App.jsx': 'import { HashRouter } from "react-router-dom"\n<HashRouter/>\n',
                          'src/_nav.jsx': "export default [{ to: '/forms/form-control' }, { to: '/charts' }]\n"})
        self.assertEqual(code_routes(coreui), ['/#/forms/form-control', '/#/charts'])

    def test_pages_the_code_declares_are_each_their_own_however_many_siblings(self):
        pages = ['/catalog/books/', '/catalog/authors/', '/catalog/genres/', '/catalog/languages/', '/catalog/mybooks/', '/catalog/borrowed/']
        self.assertEqual(len(distinct(pages)), 1, 'six siblings the code does not name are one template with other data')
        self.assertEqual(len(distinct(pages, declared=pages[:5])), 6)


if __name__ == '__main__':
    unittest.main()


class VisitorTests(unittest.TestCase):
    def test_a_signed_in_check_still_pictures_the_sign_in_and_sign_up_pages_as_a_visitor(self):
        # flask-microblog: signed in by rules, its /auth/login and /auth/register opened its home page
        from unittest import mock
        from eaos.pipeline import pages
        out = Path(scratch())
        state = out / 'session.json'
        state.write_text('{}')
        groups = {'/index': ['/index'], '/auth/login': ['/auth/login'], '/auth/register': ['/auth/register']}
        rows = [{'url': 'http://h/auth/login', 'landed': 'http://h/auth/login', 'password': 1, 'status': 'observed', 'http': 200},
                {'url': 'http://h/auth/register', 'landed': 'http://h/auth/register', 'password': 2, 'status': 'observed', 'http': 200}]
        context = mock.MagicMock(out=out)
        with mock.patch.object(pages, '_audit_pages', return_value=({'rows': rows}, None)) as audit:
            seen = pages._visitor(context, (None, 'http://h', [(None, state)]), groups, None)
        self.assertEqual(list(audit.call_args.args[1]), ['/auth/login', '/auth/register'])
        self.assertFalse(audit.call_args.args[5].is_file(), 'opened with no session')
        self.assertEqual([(r['kind'], r.get('unseen')) for r in seen], [('visitor', None), ('visitor', None)])
        self.assertEqual(pages._visitor(context, (None, 'http://h', [(None, out / 'none.json')]), groups, None), [],
                         'a check that never signed in pictured them already')
