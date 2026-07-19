"""
Storm Service — standalone HTTP + polling daemon for the storm predictor.

Run via pm2:
  pm2 start /root/empire_os/pm2/storm-agent.json

Endpoints:
  GET  /health       — liveness
  GET  /metrics      — strike count, events tracked
  POST /scan         — trigger an immediate NWS scan
  POST /strike       — webhook for new storm events
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

from empire_os.storm_predictor import StormPredictor
from empire_os.agi_wrapper import wrap_agent
from empire_os.agent_core import OllamaClient

logger = logging.getLogger("storm_service")
logging.basicConfig(level=logging.INFO, format="[storm-service] %(message)s")

PORT = int(os.environ.get("STORM_AGENT_PORT", "9101"))
INTERVAL = int(os.environ.get("NWS_POLL_INTERVAL", "300"))


class StormService:
    """Background poller + AGI wrapper around StormPredictor."""

    def __init__(self):
        llm = OllamaClient(timeout=60)
        self.predictor = StormPredictor(
            on_strike=self._on_strike,
        )
        self.wrapped = wrap_agent("storm-agent", self.predictor, llm=llm)
        self._stop = threading.Event()
        self._thread: threading.Thread = None
        self.metrics = {"scans": 0, "strikes": 0, "started_at": time.time()}

    def _on_strike(self, event):
        """Forward new storm to hub + push to AGI wrapper."""
        self.metrics["strikes"] += 1
        logger.warning("STRIKE: %s in %s (sev=%d)",
                       event.event_type, event.area_description, event.severity)
        # Notify big hub satellite-strike endpoint
        hub_url = os.environ.get("EMPIRE_HUB_URL", "http://127.0.0.1:8081")
        if hub_url:
            try:
                import urllib.request
                req = urllib.request.Request(
                    f"{hub_url}/v1/satellite/strike",
                    data=json.dumps({
                        "event": event.event_type,
                        "severity": f"Severity-{event.severity}",
                        "area": event.area_description,
                        "headline": event.headline or event.event_type,
                        "id": event.event_id,
                    }).encode(),
                    headers={"Content-Type": "application/json"},
                )
                urllib.request.urlopen(req, timeout=5).read()
            except Exception as e:
                logger.debug("hub forward failed: %s", e)

    def _poll_loop(self):
        """Continuous NWS poll loop."""
        logger.info("starting poll loop, interval=%ds", INTERVAL)
        while not self._stop.is_set():
            try:
                self.predictor.scan()
                self.metrics["scans"] += 1
            except Exception as e:
                logger.exception("scan failed: %s", e)
            self._stop.wait(INTERVAL)

    def start(self):
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()
        logger.info("storm service started")

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)


# ── HTTP handler ───────────────────────────────────────────────────

_service: StormService = None


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
            self._json(200, {"status": "online", "service": "storm-agent"})
        elif self.path == "/metrics":
            self._json(200, {
                "agent": "storm-agent",
                "scans": _service.metrics["scans"],
                "strikes": _service.metrics["strikes"],
                "events_tracked": len(_service.predictor.events),
                "started_at": _service.metrics["started_at"],
            })
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        if self.path == "/scan":
            events = _service.predictor.scan()
            self._json(200, {"strikes": len(events)})
        elif self.path == "/strike":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                payload = json.loads(body)
                _service.metrics["strikes"] += 1
                self._json(200, {"received": payload})
            except Exception as e:
                self._json(400, {"error": str(e)})
        elif self.path == "/dispatch":
            # Cross-container message from hub or other agents
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                payload = json.loads(body)
                action = payload.get("action", "")
                if action == "scan_now":
                    events = _service.predictor.scan()
                    self._json(200, {"action": "scan", "strikes": len(events)})
                else:
                    self._json(200, {"echo": payload, "service": "storm-agent"})
            except Exception as e:
                self._json(400, {"error": str(e)})
        else:
            self._json(404, {"error": "not found"})


def main():
    global _service
    _service = StormService()
    _service.start()
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    logger.info("storm-agent listening on :%d", PORT)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        _service.stop()
        server.shutdown()


if __name__ == "__main__":
    main()