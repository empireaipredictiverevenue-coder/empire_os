"""
Satellite Service — standalone HTTP + poller for the satellite scanner.

Run via pm2:
  pm2 start /root/empire_os/pm2/satellite-agent.json
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from empire_os.satellite_scanner import SatelliteScanner, WarehouseLead
from empire_os.agi_wrapper import wrap_agent
from empire_os.agent_core import OllamaClient

logger = logging.getLogger("satellite_service")
logging.basicConfig(level=logging.INFO, format="[satellite-service] %(message)s")

PORT = int(os.environ.get("SATELLITE_AGENT_PORT", "9102"))
INTERVAL = int(os.environ.get("SATELLITE_POLL_INTERVAL", "600"))


class SatelliteService:
    def __init__(self):
        llm = OllamaClient(timeout=60)
        cache_dir = Path(os.environ.get("CACHE_DIR", "/root/.empire/satellite_cache"))
        self.scanner = SatelliteScanner(cache_dir=cache_dir, llm=llm)
        self.wrapped = wrap_agent("satellite-agent", self.scanner, llm=llm)
        self._stop = threading.Event()
        self._thread: threading.Thread = None
        self.metrics = {"scans": 0, "started_at": time.time()}

    def _poll_loop(self):
        logger.info("starting poll loop, interval=%ds", INTERVAL)
        # In real deployment, listen to storm events from hub and scan those zips
        while not self._stop.is_set():
            try:
                # Demo: scan a known warehouse-dense zip
                self.scanner.scan_zip("33101")
                self.metrics["scans"] += 1
            except Exception as e:
                logger.exception("scan failed: %s", e)
            self._stop.wait(INTERVAL)

    def start(self):
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()
        logger.info("satellite service started")

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)


_service: SatelliteService = None


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
            self._json(200, {"status": "online", "service": "satellite-agent"})
        elif self.path == "/metrics":
            self._json(200, {
                "agent": "satellite-agent",
                "scans": _service.metrics["scans"],
                "results_count": len(_service.scanner.results),
                "cache_size": len(list(_service.scanner.cache_dir.glob("*.jpg"))),
                "started_at": _service.metrics["started_at"],
            })
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        if self.path.startswith("/scan/"):
            zip_code = self.path.split("/")[-1]
            result = _service.scanner.scan_zip(zip_code)
            self._json(200, {
                "zip": zip_code,
                "warehouses": result.warehouses_detected,
                "damage_score": result.damage_score,
                "method": result.method,
                "image_url": result.image_url,
            })
        elif self.path == "/dispatch":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                payload = json.loads(body)
                if payload.get("action") == "scan_zone":
                    zone = payload.get("zone", {})
                    lead = _service.scanner.scan_zone(zone)
                    self._json(200, {"lead": {
                        "zip": lead.zip_code, "warehouses": lead.warehouses_detected,
                        "damage": lead.damage_score,
                    }})
                else:
                    self._json(200, {"echo": payload, "service": "satellite-agent"})
            except Exception as e:
                self._json(400, {"error": str(e)})
        else:
            self._json(404, {"error": "not found"})


def main():
    global _service
    _service = SatelliteService()
    _service.start()
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    logger.info("satellite-agent listening on :%d", PORT)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        _service.stop()
        server.shutdown()


if __name__ == "__main__":
    main()