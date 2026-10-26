"""Loopback-only GET static preview of the original private release candidate.

Never forwards POST, accesses CRM, or serves arbitrary local files.
"""
from __future__ import annotations

from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
import json
import os

# Explicitly enumerated private trees; never an arbitrary filesystem path.
_RELEASES = Path("/home/ubuntu/empire_releases/earned_media_saas_union_20261026")
_ROOTS = {
    "previous670": _RELEASES / "rebased_candidate",
    "current700": _RELEASES / "rebased_from_700_candidate",
}
_selected = os.environ.get("EMPIRE_SAAS_STATIC_PREVIEW_BASELINE", "previous670")
if _selected not in _ROOTS:
    raise SystemExit("INVALID_PRIVATE_SAAS_PREVIEW_BASELINE")
ROOT = _ROOTS[_selected]
PORT = 28964
GET_CATALOGUES = frozenset((
    "/v1/checkout/predictive-revenue/products",
    "/v1/checkout/commercial/offers",
    "/v1/checkout/brokerage/premium-discovery",
))


class PublicPreview(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Robots-Tag", "noindex, nofollow")
        super().end_headers()

    def do_POST(self):
        self.send_error(405, "No posting from preview")

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/_preview/health":
            data = b'{"status":"GET_ONLY_REBASED_STATIC_PREVIEW"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if path in GET_CATALOGUES:
            try:
                with urlopen(Request(
                    "http://127.0.0.1" + path,
                    headers={"Host": "empire-ai.co.uk"},
                    method="GET",
                ), timeout=4) as response:
                    if response.status != 200 or response.headers.get_content_type() != "application/json":
                        raise ValueError("untrusted GET catalogue")
                    body = response.read(150001)
                    if len(body) > 150000:
                        raise ValueError("oversized GET catalogue")
                    json.loads(body)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except Exception:
                self.send_error(503, "Read-only catalogue unavailable")
            return
        if path in {"/predictive-revenue", "/commercial"}:
            self.path = path + ".html"
        elif (not path.startswith(("/_next/static/", "/fonts/", "/brand/"))
              and path not in {"/predictive-revenue.txt", "/commercial.txt", "/icon.svg"}):
            self.send_error(404, "Outside first-party preview scope")
            return
        super().do_GET()


if __name__ == "__main__":
    if ROOT.is_symlink() or not ROOT.is_dir():
        raise SystemExit("Private rebased source unavailable")
    ThreadingHTTPServer(("127.0.0.1", PORT), PublicPreview).serve_forever()
