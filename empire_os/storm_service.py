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
from datetime import datetime, timedelta, timezone
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer

from empire_os.storm_predictor import StormPredictor
from empire_os.storm_intelligence_runtime import materialize_storm_intelligence
from empire_os.agi_wrapper import wrap_agent
from empire_os.agent_core import OllamaClient

logger = logging.getLogger("storm_service")
logging.basicConfig(level=logging.INFO, format="[storm-service] %(message)s")

PORT = int(os.environ.get("STORM_AGENT_PORT", "9101"))
INTERVAL = int(os.environ.get("NWS_POLL_INTERVAL", "300"))
REPO_ROOT = Path(os.environ.get("EMPIRE_REPO_ROOT", "/srv/empire_os"))
LEGACY_HUB_FORWARD = (
    os.environ.get("EMPIRE_STORM_LEGACY_HUB_FORWARD", "0").strip().lower()
    in {"1", "true", "yes", "on"}
)


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

    @staticmethod
    def _severity_label(value: int) -> str:
        """Map legacy ordinal severity to canonical bounded severity."""
        value = int(value)
        if value <= 1:
            return "minor"
        if value <= 3:
            return "moderate"
        if value == 4:
            return "severe"
        return "extreme"

    @staticmethod
    def _canonical_event_row(event) -> dict:
        """Legacy interval projection: OBSERVED refers only to the source record."""
        from empire_os.spatial_physical_adapters import event_evidence_from_storm_event, footprint_from_storm_event
        from empire_os.real_world_exposure_graph import normalized
        from empire_os.real_world_event_intelligence import normalized_event_evidence
        evidence = event_evidence_from_storm_event(
            event, retrieved_at=getattr(event, "retrieved_at", None) or datetime.now(timezone.utc))
        observed_at = evidence.issued_at
        ends_at = evidence.ends_at or evidence.expires_at
        if ends_at is None:
            raise ValueError("source_timestamp_missing")
        starts_at = evidence.onset_at or evidence.effective_at or observed_at
        if ends_at < starts_at:
            raise ValueError("source_interval_reversed")
        return {
            "tenant_id": "empire-internal", "event_id": evidence.source_record_id,
            "event_type": evidence.phenomenon,
            "severity": StormService._severity_label(event.severity),
            "starts_at": starts_at.isoformat(), "ends_at": ends_at.isoformat(),
            "truth_class": "OBSERVED", "truth_scope": "SOURCE_RECORD_ONLY",
            "event_truth_evidence": normalized_event_evidence(evidence),
            "geographic_footprint": normalized(footprint_from_storm_event(
                event, tenant_id="empire-internal", evidence=evidence)),
            "evidence": [{
                "tenant_id": "empire-internal", "ref": evidence.source_record_id,
                "source": evidence.source, "observed_at": observed_at.isoformat(),
                "valid_until": max(ends_at + timedelta(hours=6), observed_at + timedelta(hours=1)).isoformat(),
            }],
        }

    def _on_strike(self, event):
        """Observe one real NWS event without granting downstream authority."""
        self.metrics["strikes"] += 1

        logger.info(
            "STORM OBSERVATION: %s in %s (sev=%d)",
            event.event_type,
            event.area_description,
            event.severity,
        )

        # Deliberately no persistence or downstream dispatch here.
        # StormPredictor.scan() invokes this callback before it appends the
        # completed scan batch to predictor.events. The completed batch is
        # materialized once by _scan_and_materialize().
        if LEGACY_HUB_FORWARD:
            logger.warning(
                "legacy storm hub forwarding requested but blocked by grounded "
                "OBSERVE runtime"
            )

    def _scan_and_materialize(self):
        """Run one NWS scan and atomically materialize the bounded event set."""
        events = self.predictor.scan()

        # Bound retained detector history while preserving deterministic order.
        # The predictor itself remains the event-store owner.
        bounded = self.predictor.events[-100:]

        self.predictor.events[:] = bounded
        canonical_events = []
        rejections = list(getattr(self.predictor, "rejections", ()))
        identities = set()
        for index, event in enumerate(bounded):
            try:
                row = self._canonical_event_row(event)
            except (ValueError, TypeError, AttributeError) as exc:
                # Only allowlisted diagnostics; never echo raw source data.
                reason = str(exc)
                if not reason.startswith("source_"):
                    reason = "source_record_invalid"
                rejections.append({"index": index, "reason": reason})
                continue
            from empire_os.real_world_exposure_graph import digest
            identity = (row["event_id"], row["event_truth_evidence"]["raw_evidence_hash"],
                        digest(row["geographic_footprint"]))
            if identity not in identities:
                identities.add(identity)
                canonical_events.append(row)
        canonical_events.sort(key=lambda row: (row["event_id"], row["event_truth_evidence"]["raw_evidence_hash"],
                                                digest(row["geographic_footprint"])))

        snapshot = materialize_storm_intelligence(
            REPO_ROOT,
            events=canonical_events,
            source_rejections=rejections,
            subjects=(),
            matches=(),
            readiness=(),
            now=datetime.now(timezone.utc),
        )

        logger.info(
            "grounded storm batch materialized: scan=%d retained=%d "
            "canonical=%d candidates=%d authority=%s",
            len(events),
            len(bounded),
            len(canonical_events),
            snapshot["candidate_count"],
            snapshot["execution_authority"],
        )

        return events, snapshot

    def _poll_loop(self):
        """Continuous NWS poll loop."""
        logger.info("starting poll loop, interval=%ds", INTERVAL)
        while not self._stop.is_set():
            try:
                self._scan_and_materialize()
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
            events, snapshot = _service._scan_and_materialize()
            self._json(200, {
                "strikes": len(events),
                "events_valid": snapshot["diagnostics"]["events_valid"],
                "candidates": snapshot["candidate_count"],
                "authority": snapshot["execution_authority"],
            })
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
                    events, snapshot = _service._scan_and_materialize()
                    self._json(200, {
                        "action": "scan",
                        "strikes": len(events),
                        "events_valid": snapshot["diagnostics"]["events_valid"],
                        "candidates": snapshot["candidate_count"],
                        "authority": snapshot["execution_authority"],
                    })
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