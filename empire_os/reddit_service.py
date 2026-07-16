"""
Reddit Service — standalone HTTP + poller for the Reddit sniper.

Run via pm2:
  pm2 start /root/empire_os/pm2/reddit-sniper-agent.json
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

from empire_os.reddit_sniper import RedditSniper
from empire_os.agi_wrapper import wrap_agent
from empire_os.agent_core import OllamaClient

logger = logging.getLogger("reddit_service")
logging.basicConfig(level=logging.INFO, format="[reddit-service] %(message)s")

PORT = int(os.environ.get("REDDIT_AGENT_PORT", "9103"))
INTERVAL = int(os.environ.get("REDDIT_POLL_INTERVAL", "900"))


class RedditService:
    def __init__(self):
        llm = OllamaClient(timeout=60)
        self.sniper = RedditSniper()
        self.wrapped = wrap_agent("reddit-sniper-agent", self.sniper, llm=llm)
        self._stop = threading.Event()
        self._thread: threading.Thread = None
        self.metrics = {"scans": 0, "started_at": time.time()}

    def _poll_loop(self):
        logger.info("starting poll loop, interval=%ds", INTERVAL)
        while not self._stop.is_set():
            if self.sniper.is_configured():
                try:
                    leads = self.sniper.scrape()
                    self.metrics["scans"] += 1
                    self.sniper.write_output()
                except Exception as e:
                    logger.exception("scrape failed: %s", e)
            else:
                logger.debug("Reddit API not configured; skipping")
            self._stop.wait(INTERVAL)

    def start(self):
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()
        logger.info("reddit service started")

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)


_service: RedditService = None


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        logger.info(fmt, *args)

    def _json(self, status, payload):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode())

    def do_GET(self):
        if self.path == "/health":
            self._json(200, {"status": "online", "service": "reddit-sniper"})
        elif self.path == "/metrics":
            self._json(200, {
                "agent": "reddit-sniper",
                "scans": _service.metrics["scans"],
                "leads_total": len(_service.sniper.leads),
                "configured": _service.sniper.is_configured(),
            })
        elif self.path == "/leads":
            self._json(200, {
                "total": len(_service.sniper.leads),
                "qualified": sum(1 for l in _service.sniper.leads if l.get("qualified")),
                "leads": _service.sniper.leads[:50],
            })
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        if self.path == "/scan":
            leads = _service.sniper.scrape()
            self._json(200, {"scanned": True, "leads": len(leads)})
        elif self.path == "/dispatch":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                payload = json.loads(body)
                if payload.get("action") == "scan_now":
                    leads = _service.sniper.scrape()
                    self._json(200, {"leads": len(leads)})
                else:
                    self._json(200, {"echo": payload, "service": "reddit-sniper"})
            except Exception as e:
                self._json(400, {"error": str(e)})
        else:
            self._json(404, {"error": "not found"})


def main():
    global _service
    _service = RedditService()
    _service.start()
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    logger.info("reddit-sniper-agent listening on :%d", PORT)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        _service.stop()
        server.shutdown()


if __name__ == "__main__":
    main()