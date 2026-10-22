"""HTTP server: the score entry page plus a small JSON API."""

import hmac
import json
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .tournament import MatchError

_PAGE = os.path.join(os.path.dirname(__file__), "static", "index.html")


def make_server(desk, code, host="0.0.0.0", port=8080):
    """Serve the page; every /api/ request must carry the tournament code."""

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # the director's terminal belongs to tsh

        def _json(self, status, body):
            data = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def _code_ok(self):
            given = self.headers.get("X-Access-Code", "").strip().upper()
            if hmac.compare_digest(given.encode(), code.upper().encode()):
                return True
            time.sleep(1)  # slow down anyone guessing codes
            self._json(401, {"error": "Wrong tournament code."})
            return False

        def _call(self, fn, *args):
            if not self._code_ok():
                return
            try:
                self._json(200, fn(*args))
            except MatchError as e:
                self._json(409, {"error": str(e)})
            except (KeyError, TypeError, ValueError) as e:
                self._json(400, {"error": f"Bad request: {e}"})
            except OSError as e:
                self._json(500, {"error": f"Couldn't read tournament files: {e}"})

        def do_GET(self):
            url = urlparse(self.path)
            query = {k: v[0] for k, v in parse_qs(url.query).items()}
            if url.path == "/":
                with open(_PAGE, "rb") as f:
                    page = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(page)))
                self.end_headers()
                self.wfile.write(page)
            elif url.path == "/api/divisions":
                self._call(desk.divisions)
            elif url.path == "/api/match":
                self._call(lambda: desk.match(query["division"], query["player"]))
            else:
                self._json(404, {"error": "Not found"})

        def do_POST(self):
            if urlparse(self.path).path != "/api/score":
                return self._json(404, {"error": "Not found"})
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length) or b"{}")
            except ValueError:
                return self._json(400, {"error": "Bad request body"})
            self._call(lambda: desk.record(
                body["division"], body["player"], body["round"],
                body["player_score"], body["opponent_score"]))

    return ThreadingHTTPServer((host, port), Handler)
