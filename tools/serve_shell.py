#!/usr/bin/env python3
"""Serve the static shell locally, arranged the way CloudFront arranges it.

Three things have to be true for the shell to work, and all three are things
the distribution does rather than things the shell does. This reproduces them
so a broken layout is found here rather than after an upload:

  /api/*     proxied to the Flask app, so the fetches are same-origin and no
             CORS or mixed-content question ever comes up
  /static/*  served from app/static, the way the bucket's static/ prefix is
  anything   else with no file behind it falls back to index.html, which is
             what makes client-side routing work on a bucket

    python3 tools/serve_shell.py            # http://localhost:5010
    python3 tools/serve_shell.py --api http://localhost:5003 --port 5010
"""

import argparse
import urllib.error
import urllib.request
from functools import partial
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHELL = ROOT / "static_site"
STATIC = ROOT / "app" / "static"

# Hop-by-hop headers describe one connection and must not be copied onto
# another; passing Transfer-Encoding through is how a proxy ends up sending a
# chunked header in front of a body it has already de-chunked.
SKIP = {"transfer-encoding", "connection", "keep-alive", "content-encoding"}


class Handler(SimpleHTTPRequestHandler):
    api = "http://localhost:5003"

    def do_GET(self):  # noqa: N802 -- BaseHTTPRequestHandler's naming
        if self.path.startswith("/api/"):
            return self.proxy()
        return super().do_GET()

    def proxy(self):
        try:
            with urllib.request.urlopen(self.api + self.path, timeout=10) as upstream:
                body, status, headers = upstream.read(), upstream.status, upstream.headers
        except urllib.error.HTTPError as exc:
            body, status, headers = exc.read(), exc.code, exc.headers
        except OSError as exc:
            self.send_error(502, f"upstream {self.api} unreachable: {exc}")
            return

        self.send_response(status)
        for key, value in headers.items():
            if key.lower() not in SKIP:
                self.send_header(key, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def translate_path(self, path):
        clean = path.split("?", 1)[0].split("#", 1)[0]
        if clean.startswith("/static/"):
            return str(STATIC / clean[len("/static/"):])
        target = SHELL / clean.lstrip("/")
        # The fallback. A request for /projects/foo has no file behind it and
        # is not meant to -- the router reads the URL once index.html loads.
        if not target.is_file():
            return str(SHELL / "index.html")
        return str(target)

    def log_message(self, fmt, *args):
        if "/static/" not in (args[0] if args else ""):
            super().log_message(fmt, *args)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=5010)
    parser.add_argument("--api", default="http://localhost:5003")
    args = parser.parse_args()

    Handler.api = args.api.rstrip("/")
    print(f"Shell   http://localhost:{args.port}")
    print(f"API     {Handler.api} (proxied at /api/)")
    HTTPServer(("127.0.0.1", args.port), partial(Handler, directory=str(SHELL))).serve_forever()


if __name__ == "__main__":
    main()
