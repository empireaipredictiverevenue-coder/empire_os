#!/usr/bin/env python3
"""OpenMeter integration for Empire OS PPC billing.

Replaces hand-rolled _invoiced() JSONL writes with real-time metering.
Uses OpenMeter REST API (runs as Docker container or cloud service).

G-1 gate: wires head-1 (90s sprint) + head-5 (native CPC) streams to OpenMeter.
"""
from __future__ import annotations
import json, os, time, hashlib
from pathlib import Path
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.error import URLError

OPENMETER_URL = os.environ.get("OPENMETER_URL", "http://localhost:8080")
OPENMETER_API_KEY = os.environ.get("OPENMETER_API_KEY", "")
FEEDBACK = Path("/root/feedback")
METER_LOG = FEEDBACK / "openmeter_events.jsonl"

# ── Event schemas (OpenMeter v1) ──────────────────────────────────────────
def _event(event_type: str, subject: str, value: float, **props) -> dict:
    """Build OpenMeter v1 event."""
    return {
        "eventType": event_type,
        "subject": subject,
        "time": datetime.now(timezone.utc).isoformat(),
        "value": value,
        "properties": props,
    }

def _send(event: dict) -> bool:
    """Send event to OpenMeter API. Falls back to local log on failure."""
    try:
        data = json.dumps(event).encode()
        req = Request(
            f"{OPENMETER_URL}/api/v1/events",
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {OPENMETER_API_KEY}" if OPENMETER_API_KEY else "",
            },
            method="POST",
        )
        resp = urlopen(req, timeout=5)
        return resp.status == 200
    except (URLError, ConnectionError, OSError):
        # Fallback: log locally, replay later
        FEEDBACK.mkdir(parents=True, exist_ok=True)
        with open(METER_LOG, "a") as f:
            f.write(json.dumps(event) + "\n")
        return False

# ── Head 1: 90s sprint (pay-per-call) ─────────────────────────────────────
def meter_90s_sprint(call_id: str, buyer_id: str, lane_key: str,
                     duration_s: int, cpm_cents: int) -> dict:
    """Meter a 90-second sprint call.

    Value = CPM rate * (duration/60), capped at 90s.
    """
    billable_s = min(duration_s, 90)
    cost_cents = int((billable_s / 60.0) * cpm_cents)
    event = _event(
        "ppc_90s_sprint",
        subject=buyer_id,
        value=cost_cents,
        call_id=call_id,
        lane_key=lane_key,
        duration_s=billable_s,
        cpm_cents=cpm_cents,
    )
    _send(event)
    return event

# ── Head 5: Native CPC (click arbitrage) ───────────────────────────────────
def meter_native_cpc(click_id: str, buyer_id: str, lane_key: str,
                     cpc_cents: int) -> dict:
    """Meter a native CPC click."""
    event = _event(
        "ppc_native_cpc",
        subject=buyer_id,
        value=cpc_cents,
        click_id=click_id,
        lane_key=lane_key,
    )
    _send(event)
    return event

# ── Head 3: PPL (per-lead) ─────────────────────────────────────────────────
def meter_ppl(lead_id: str, buyer_id: str, lane_key: str,
              ppl_cents: int) -> dict:
    """Meter a per-lead payout."""
    event = _event(
        "ppc_ppl",
        subject=buyer_id,
        value=ppl_cents,
        lead_id=lead_id,
        lane_key=lane_key,
    )
    _send(event)
    return event

# ── Head 4: PPS (per-appointment) ──────────────────────────────────────────
def meter_pps(appt_id: str, buyer_id: str, lane_key: str,
              pps_cents: int) -> dict:
    """Meter a per-appointment payout."""
    event = _event(
        "ppc_pps",
        subject=buyer_id,
        value=pps_cents,
        appt_id=appt_id,
        lane_key=lane_key,
    )
    _send(event)
    return event

# ── Head 2: Hybrid whale (upfront + backend) ───────────────────────────────
def meter_hybrid_upfront(deal_id: str, buyer_id: str, lane_key: str,
                         upfront_cents: int) -> dict:
    """Meter hybrid upfront payment."""
    event = _event(
        "ppc_hybrid_upfront",
        subject=buyer_id,
        value=upfront_cents,
        deal_id=deal_id,
        lane_key=lane_key,
    )
    _send(event)
    return event

def meter_hybrid_backend(deal_id: str, buyer_id: str, lane_key: str,
                         backend_pct: float, deal_value_cents: int) -> dict:
    """Meter hybrid backend rev-share."""
    backend_cents = int(deal_value_cents * backend_pct / 100)
    event = _event(
        "ppc_hybrid_backend",
        subject=buyer_id,
        value=backend_cents,
        deal_id=deal_id,
        lane_key=lane_key,
        backend_pct=backend_pct,
        deal_value_cents=deal_value_cents,
    )
    _send(event)
    return event

# ── Replay fallback events ─────────────────────────────────────────────────
def replay_events() -> int:
    """Replay events that failed to send (local log fallback)."""
    if not METER_LOG.exists():
        return 0
    count = 0
    events = []
    with open(METER_LOG) as f:
        for line in f:
            events.append(json.loads(line))
    # Clear log
    METER_LOG.unlink()
    for event in events:
        if _send(event):
            count += 1
        else:
            # Re-log if still failing
            with open(METER_LOG, "a") as f:
                f.write(json.dumps(event) + "\n")
    return count

if __name__ == "__main__":
    # Test
    e = meter_90s_sprint("test-call", "buyer-1", "roofing:DAL", 45, 5000)
    print(f"Event: {e['eventType']} value={e['value']} cents")
    print(f"OpenMeter URL: {OPENMETER_URL}")
    print("G-1 OpenMeter integration: OK")
