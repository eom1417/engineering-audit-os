"""A Streamlit script that renders at module level is a web page; a module of view functions is not."""
from shared_fixture import Workspace

from eaos.facts.entrypoints import Context
from eaos.facts.frameworks import streamlit


def detect(rel, text):
    return [(row['route'], row['framework']) for row in streamlit.detect(Context(rel, text, 'python', []))]


class StreamlitTests(Workspace):
    def test_a_script_that_renders_is_the_page_at_the_root(self):
        self.assertEqual(detect('app.py', 'import streamlit as st\nst.set_page_config(layout="wide")\n'), [('/', 'streamlit')])

    def test_view_functions_and_a_launcher_are_not_pages(self):
        self.assertEqual(detect('views/a.py', 'import streamlit as st\n\ndef render():\n    st.title("a")\n'), [])
        self.assertEqual(detect('run_app.py', 'import streamlit.web.cli as stcli\nstcli.main()\n'), [])
        self.assertEqual(detect('util.py', 'st.title("not streamlit")\n'), [])

    def test_the_pages_of_a_multi_page_app_have_their_own_routes(self):
        self.assertEqual(detect('pages/2_Reports.py', 'import streamlit as st\nst.title("r")\n'), [('/Reports', 'streamlit')])
        text = 'import streamlit as st\npg = st.navigation([st.Page("v/a.py", url_path="alpha"), st.Page("v/b.py")])\n'
        self.assertEqual(detect('main.py', text), [('/alpha', 'streamlit'), ('/b', 'streamlit')])
