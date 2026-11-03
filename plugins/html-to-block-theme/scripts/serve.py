#!/usr/bin/env python3
"""Static server for a design directory, with the comparison harness and a results sink.

    serve.py --dir <design-dir> --port <port> --harness <viewport.html> --sink-dir <dir> [--id <token>]

Serves <design-dir> on 127.0.0.1:<port>, uncached. Three paths are added to it:

  GET  /_h2bt/viewport.html   the comparison harness, read from --harness and never from the
                              design directory
  POST /_h2bt/sink/<name>     writes the request body to <sink-dir>/<name>.json
  GET  /_h2bt/id              the token given as --id. serve-html.sh asks for it to tell
                              whether the server it recorded is still the one on the port: a
                              process id is reused, and so is a port.

The sink exists because a browser automation tool cuts long results short: the harness posts a
measurement here and a script reads it from disk.

Everything is loopback-only. The server binds 127.0.0.1, refuses a request whose Host header is
not a loopback name (so a page that rebinds its own name to 127.0.0.1 cannot read the design
files), refuses a sink request from any origin that is not loopback, and writes nothing outside
<sink-dir>.
"""
import argparse
import functools
import http.server
import os
import re
import urllib.parse

LOOPBACK_HOST = r'(?:localhost|127\.0\.0\.1|\[::1\]|[a-z0-9.-]+\.localhost)(?::\d+)?'
HOST = re.compile(r'^%s$' % LOOPBACK_HOST, re.I)
ORIGIN = re.compile(r'^https?://%s$' % LOOPBACK_HOST, re.I)
SINK = re.compile(r'^/_h2bt/sink/([A-Za-z0-9_-]{1,60})$')
HARNESS_PATH = '/_h2bt/viewport.html'
ID_PATH = '/_h2bt/id'
MAX_BODY = 32 * 1024 * 1024


class Handler(http.server.SimpleHTTPRequestHandler):
    harness = ''
    sink_dir = ''
    token = ''

    def _refused(self):
        """Answer 403 and return True when the request did not come for a loopback name."""
        if HOST.match(self.headers.get('Host') or ''):
            return False
        self.send_error(403, 'Loopback hosts only')
        return True

    def _loopback_origin(self):
        origin = self.headers.get('Origin')
        return origin if origin and ORIGIN.match(origin) else None

    def _cors(self):
        origin = self._loopback_origin()
        if origin:
            self.send_header('Access-Control-Allow-Origin', origin)
            self.send_header('Access-Control-Allow-Headers', 'content-type')
            self.send_header('Vary', 'Origin')

    def end_headers(self):
        # A comparison must never read a stale copy of a file that was just regenerated.
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()

    def translate_path(self, path):
        if urllib.parse.urlsplit(path).path == HARNESS_PATH:
            return self.harness
        return super().translate_path(path)

    def do_GET(self):
        if self._refused():
            return
        if urllib.parse.urlsplit(self.path).path == ID_PATH:
            body = self.token.encode()
            self.send_response(200 if body else 404)
            self.send_header('Content-Type', 'text/plain')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()

    def do_HEAD(self):
        if not self._refused():
            super().do_HEAD()

    def do_OPTIONS(self):
        if self._refused():
            return
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_POST(self):
        if self._refused():
            return
        match = SINK.match(urllib.parse.urlsplit(self.path).path)
        if not match:
            self.send_error(404)
            return
        if self.headers.get('Origin') and not self._loopback_origin():
            self.send_error(403, 'Loopback origins only')
            return
        try:
            length = int(self.headers.get('Content-Length') or 0)
        except ValueError:
            length = -1
        if length < 0 or length > MAX_BODY:
            self.send_error(413)
            return
        body = self.rfile.read(length)
        with open(os.path.join(self.sink_dir, match.group(1) + '.json'), 'wb') as handle:
            handle.write(body)
        self.send_response(200)
        self._cors()
        self.send_header('Content-Type', 'text/plain')
        self.end_headers()
        self.wfile.write(str(len(body)).encode())


def main():
    parser = argparse.ArgumentParser(description='Serve a design directory with the h2bt harness and sink.')
    parser.add_argument('--dir', required=True)
    parser.add_argument('--port', required=True, type=int)
    parser.add_argument('--harness', required=True)
    parser.add_argument('--sink-dir', required=True)
    parser.add_argument('--id', default='')
    args = parser.parse_args()

    Handler.harness = os.path.abspath(args.harness)
    Handler.sink_dir = os.path.abspath(args.sink_dir)
    Handler.token = args.id
    os.makedirs(Handler.sink_dir, exist_ok=True)

    handler = functools.partial(Handler, directory=os.path.abspath(args.dir))
    http.server.ThreadingHTTPServer(('127.0.0.1', args.port), handler).serve_forever()


if __name__ == '__main__':
    main()
