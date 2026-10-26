"""Isolated GET-only static preview of original two-page candidate, no POST."""
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json, requests
from urllib.parse import urlsplit
ROOT=Path("/home/ubuntu/empire_worktrees/website_solar_commercial_premium_20261026/apps/empire-public-site/out")
class Preview(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args,directory=str(ROOT),**kwargs)
    def do_GET(self):
        path=urlsplit(self.path).path
        if path in {"/v1/checkout/commercial/offers", "/v1/checkout/brokerage/premium-discovery"}:
            try:
                r=requests.get("https://empire-ai.co.uk"+path,timeout=12,
                    headers={"Accept":"application/json"})
                if r.status_code!=200 or not r.headers.get("content-type","").startswith("application/json"):
                    raise ValueError("CURRENT_PUBLIC_CATALOG_UNAVAILABLE")
                body=r.content
                parsed=json.loads(body)
                if not isinstance(parsed,dict):
                    raise ValueError("UNTRUSTED_PUBLIC_GET_SOURCE")
                if path.endswith("/offers") and (parsed.get("status")!="FOUNDER_LED_ENQUIRY_AVAILABLE" or not isinstance(parsed.get("offers"),list)):
                    raise ValueError("UNTRUSTED_CATALOG_RESPONSE")
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.send_header("Cache-Control","no-store")
                self.send_header("Content-Length",str(len(body)))
                self.end_headers();self.wfile.write(body)
            except Exception:
                b=b'{"status":"UNAVAILABLE","offers":[]}'
                self.send_response(503)
                self.send_header("Content-Type","application/json")
                self.send_header("Content-Length",str(len(b)))
                self.end_headers();self.wfile.write(b)
            return
        p=path
        if not p.endswith(("/",".txt",".html",".js",".css",".svg",".png",".jpg",".jpeg",".webp",".ico",".woff2",".json")):
            path=p+".html"
        elif p.endswith("/"):
            path=p.rstrip("/")+"/index.html" if p!="/" else "/index.html"
        self.path=path
        super().do_GET()
    def do_POST(self):
        self.send_error(405,"NO_FORM_POST_IN_CANDIDATE_REVIEW")
    def log_message(self,format,*args):
        if "POST" in format%args:print("PROHIBITED_REQUEST",format%args,flush=True)
if __name__=="__main__":
    ThreadingHTTPServer(("127.0.0.1",28842),Preview).serve_forever()
