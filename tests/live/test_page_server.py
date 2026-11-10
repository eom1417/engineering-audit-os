"""A production build that serves only its pages is refused before its baseline is accepted
(eaos/live/app/page_server.py)."""
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock

from eaos.live.app import page_server


class PageServer(unittest.TestCase):
    def serve(self, api):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                body = b'{"ok": true}' if api and self.path.startswith('/api/') else b'<html>the app</html>'
                if api == 'signin' and self.path.startswith('/api/'): return self.send_error(401)
                if api == 'missing' and self.path.startswith('/api/'): return self.send_error(404)
                self.send_response(200)
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_): pass
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return f'http://127.0.0.1:{server.server_address[1]}'

    def test_a_server_of_the_pages_alone_is_refused_and_one_of_the_program_passes(self):
        # A `vite preview` fallback answers /api/* with the page itself: the baseline must run the program behind it.
        with mock.patch.object(page_server, 'server_routes',
                               return_value=['/', '/api/session', '/api/runs', '/index.html']):
            with self.assertRaisesRegex(page_server.PagesOnly, 'serves only its pages'):
                page_server.refuse_a_page_server('report', self.serve(api=False))
            # its routes not found: still the pages
            with self.assertRaisesRegex(page_server.PagesOnly, 'serves only its pages'):
                page_server.refuse_a_page_server('report', self.serve(api='missing'))
            page_server.refuse_a_page_server('report', self.serve(api=True))
            page_server.refuse_a_page_server('report', self.serve(api='signin'))  # the program, behind its sign-in
        page_server.refuse_a_page_server(None, 'http://127.0.0.1:1')               # no report: nothing to compare


if __name__ == '__main__':
    unittest.main()
