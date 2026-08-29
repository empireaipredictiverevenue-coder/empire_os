#!/usr/bin/env python3
"""Empire OS Prometheus exporter.

Serves the health-butler generated metrics.prom on :9105/metrics.
Run as a long-lived service. If health-butler is inactive, the file is stale
but still served (Prometheus will see last known values).
"""
import http.server
import socketserver
import os

PORT = 9105
METRICS = "/root/empire_os/feedback/metrics.prom"


class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/metrics", "/"):
            try:
                body = open(METRICS, "rb").read() if os.path.exists(METRICS) else b"# no metrics yet\n"
            except OSError:
                body = b"# error reading metrics\n"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    with socketserver.TCPServer(("", PORT), H) as srv:
        print(f"empire-exporter on :{PORT}/metrics")
        srv.serve_forever()
