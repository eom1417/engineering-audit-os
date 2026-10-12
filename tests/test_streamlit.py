"""A Streamlit script that renders at module level is a web page; a module of view functions is not."""
from shared_fixture import Workspace

from eaos.facts.entrypoints import Context
from eaos.facts.frameworks import streamlit


def detect(rel, text):
    return [(row['route'], row['framework']) for row in streamlit.detect(Context(rel, text, 'python', []))]


class StreamlitTests(Workspace):
    def test_rendering_scripts_and_their_pages_are_routes_and_view_modules_are_not(self):
        self.assertEqual(detect('app.py', 'import streamlit as st\nst.set_page_config(layout="wide")\n'), [('/', 'streamlit')])
        self.assertEqual(detect('pages/2_Reports.py', 'import streamlit as st\nst.title("r")\n'), [('/Reports', 'streamlit')])
        text = 'import streamlit as st\npg = st.navigation([st.Page("v/a.py", url_path="alpha"), st.Page("v/b.py")])\n'
        self.assertEqual(detect('main.py', text), [('/alpha', 'streamlit'), ('/b', 'streamlit')])
        self.assertEqual(detect('views/a.py', 'import streamlit as st\n\ndef render():\n    st.title("a")\n'), [])
        self.assertEqual(detect('run_app.py', 'import streamlit.web.cli as stcli\nstcli.main()\n'), [])
        self.assertEqual(detect('util.py', 'st.title("not streamlit")\n'), [])
