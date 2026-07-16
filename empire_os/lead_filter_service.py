"""
Lead Filter Service — standalone HTTP daemon for lead filtering + 2FA.

Run via pm2:
  pm2 start /root/empire_os/pm2/lead-filter-agent.json
"""
from __future__ import annotations

import json
import logging
import os
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

from empire_os.lead_filter import LeadFilter, TwoFactorGate
from empire_os.agi_wrapper import wrap_agent
from empire_os.agent_core import OllamaClient

logger = logging.getLogger("lead_filter_service")
logging.basicConfig(level=logging.INFO, format="[lead-filter] %(message)s")

PORT = int(os.environ.get("LEAD_FILTER_PORT", "9104"))


class LeadFilterService:
    def __init__(self):
        llm = OllamaClient(timeout=60)
        secret = os.environ.get("TWO_FA_SECRET", "empire-os-default-secret")
        ttl = int(os.environ.get("TOTP_TTL_SECONDS", "300"))
        gate = TwoFactorGate(secret=secret, ttl_seconds=ttl)
        self.filter = LeadFilter(two_factor=gate)
        self.wrapped = wrap_agent("lead-filter-agent", self.filter, llm=llm)

    def ingest(self, leads: list) -> dict:
        return self.filter.filter_batch(leads)

    def request_2fa(self, deal_id: str, msisdn: str = "") -> str:
        return self.filter.two_factor.request_authorization(deal_id, msisdn)

    def verify_2fa(self, deal_id: str, code: str) -> bool:
        return self.filter.two_factor.verify(deal_id, code)


_service: LeadFilterService = None


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        logger.info(fmt, *args)

    def _json(self, status, payload):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode())

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length).decode())

    def do_GET(self):
        if self.path == "/health":
            self._json(200, {"status": "online", "service": "lead-filter"})
        elif self.path == "/metrics":
            self._json(200, _service.filter.observe())
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        if self.path == "/filter":
            body = self._read_body()
            leads = body.get("leads", [])
            result = _service.ingest(leads)
            self._json(200, result)
        elif self.path == "/2fa/request":
            body = self._read_body()
            code = _service.request_2fa(body.get("deal_id", ""), body.get("msisdn", ""))
            self._json(200, {"code": code})
        elif self.path == "/2fa/verify":
            body = self._read_body()
            ok = _service.verify_2fa(body.get("deal_id", ""), body.get("code", ""))
            self._json(200, {"verified": ok})
        elif self.path == "/dispatch":
            body = self._read_body()
            action = body.get("action", "")
            if action == "filter_leads":
                result = _service.ingest(body.get("leads", []))
                self._json(200, {"result": result})
            else:
                self._json(200, {"echo": body, "service": "lead-filter"})
        else:
            self._json(404, {"error": "not found"})


def main():
    global _service
    _service = LeadFilterService()
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    logger.info("lead-filter-agent listening on :%d", PORT)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()