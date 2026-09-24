"""A two-route application for the sandbox acceptance test: /health answers ok, /env lists variable names."""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b'ok' if self.path == '/health' else json.dumps(sorted(os.environ)).encode()
        self.send_response(200 if self.path in ('/health', '/env') else 404)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


HTTPServer(('127.0.0.1', int(sys.argv[sys.argv.index('--port') + 1])), Handler).serve_forever()
