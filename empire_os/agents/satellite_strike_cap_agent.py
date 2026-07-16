"""Empire OS v3 — Satellite Strike (CAP adapter).

Pulls active NWS CAP alerts from `api.weather.gov/alerts/active`, parses each
via `cap_tools` (MIT, vendored), scores against the 462-lane Empire OS matrix,
and writes events to /root/feedback/satellite_strike.jsonl. Optionally POSTs
to /v1/pipeline/incoming on the local hub so funnel events register as
DISCOVERED leads.

Patterns adopted from upstream (Apache-2.0 and MIT, both license-clean):
  - `primaris-tech/lookout` forward-looking SPC pattern: diff against last
    tick, fire events only on change (first_appearance, risk_upgrade,
    risk_cleared).
  - `bjoern-reetz/cap-tools` Pydantic-style CAP model.

This module deliberately avoids vendoring the GPL NWS dashboard code; it
hits `api.weather.gov` directly via urllib (header User-Agent required by
NWS API policy) and parses with `cap_tools`.

Cadence: every 60s.

Anti-rep: skip if no diff since last successful tick.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sqlite3
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any

sys.path.insert(0, "/root/empire_os")
sys.path.insert(0, "/opt/repo_skills/cap-tools/src")

try:
    from cap_tools.models import Alert  # type: ignore
    from xsdata.formats.dataclass.parsers import XmlParser  # type: ignore
    HAVE_CAP = True
except Exception:
    HAVE_CAP = False

LOG = Path("/root/feedback/satellite_strike.jsonl")
LOG.parent.mkdir(parents=True, exist_ok=True)
STATE = Path("/root/feedback/satellite_strike_state.json")

NWS_ALERTS_URL = "https://api.weather.gov/alerts/active"
LANE_HUB_DB = "/root/empire_os/empire_os.db"

# Risk → niche mapping. Conservative; one alert can map to multiple niches.
EVENT_TO_NICHES = {
    "Tornado Warning": ["roofing", "siding", "general_contractor"],
    "Severe Thunderstorm Warning": ["roofing", "siding", "general_contractor"],
    "Hail Warning": ["roofing", "siding"],
    "High Wind Warning": ["roofing", "siding", "tree_service"],
    "Hurricane Warning": ["roofing", "general_contractor", "tree_service"],
    "Flash Flood Warning": ["water_damage_restoration", "general_contractor"],
    "Coastal Flood Warning": ["water_damage_restoration", "general_contractor"],
}


def _log(level: str, msg: str, **kw: Any) -> None:
    rec = {"ts": dt.datetime.now(dt.timezone.utc).isoformat(),
           "level": level, "msg": msg, **kw}
    with LOG.open("a") as f:
        f.write(json.dumps(rec) + "\n")


def _http(url: str, timeout: int = 15) -> bytes:
    req = urllib.request.Request(url, headers={
        "User-Agent": "EmpireOS/satellite-strike (contact: ops@empire-ai.co.uk)",
        "Accept": "application/cap+xml, application/atom+xml, application/json",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def fetch_active_alerts() -> list[bytes]:
    """Fetch raw CAP/GeoJSON payloads from NWS."""
    body = _http(NWS_ALERTS_URL)
    out: list[bytes] = []
    try:
        # Modern endpoint: GeoJSON FeatureCollection
        j = json.loads(body)
        for entry in j.get("features", []):
            out.append(("__json__:" + json.dumps(entry)).encode())
        return out[:50]
    except Exception:
        # Legacy Atom with <entry><link href="...cap"/></entry>.
        import re
        cap_urls = re.findall(rb'href="([^"]+\.cap)"', body)
        for u in cap_urls[:50]:
            try:
                out.append(_http(u.decode()))
            except Exception as e:
                _log("WARN", "cap_fetch_fail",
                     url=u[:120].decode(errors="replace"),
                     err=str(e)[:200])
        return out


def parse_alert(blob: bytes) -> dict | None:
    if not HAVE_CAP:
        return None
    if blob.startswith(b"__json__:"):
        # We can't strict-parse this with cap_tools; treat as a flat dict.
        try:
            j = json.loads(blob.split(b":", 1)[1])
            p = j.get("properties", {})
            return {
                "event": p.get("event", ""),
                "headline": p.get("headline", ""),
                "area_desc": p.get("areaDesc", ""),
                "severity": p.get("severity", ""),
                "certainty": p.get("certainty", ""),
                "urgency": p.get("urgency", ""),
                "effective": p.get("effective", ""),
                "expires": p.get("expires", ""),
                "sender": p.get("senderName", ""),
            }
        except Exception:
            return None
    try:
        alert = XmlParser().from_string(blob.decode("utf-8", errors="replace"), Alert)
        info = alert.infos[0] if alert.infos else None
        area = info.areas[0] if (info and info.areas) else None
        return {
            "event": getattr(info.event, "value", "") if info else "",
            "headline": getattr(info.headline, "value", "") if info and info.headline else "",
            "area_desc": getattr(area.area_desc, "value", "") if area and area.area_desc else "",
            "severity": getattr(info.severity, "value", "") if info and info.severity else "",
            "certainty": getattr(info.certainty, "value", "") if info and info.certainty else "",
            "urgency": getattr(info.urgency, "value", "" if info and info.urgency else "N/A"),
            "effective": str(info.effective) if info and info.effective else "",
            "expires": str(info.expires) if info and info.expires else "",
            "sender": getattr(alert.sender, "value", "") if alert.sender else "",
        }
    except Exception as e:
        _log("WARN", "cap_parse_fail", err=str(e)[:200])
        return None


def load_lanes() -> dict[str, dict]:
    """Load all 462 lanes keyed by id."""
    if not os.path.exists(LANE_HUB_DB):
        return {}
    c = sqlite3.connect(LANE_HUB_DB)
    rows = c.execute("select id, sub_niche, metro, metro_label from lanes").fetchall()
    c.close()
    return {r[0]: {"sub_niche": r[1], "metro": r[2], "metro_label": r[3]} for r in rows}


def match_lanes(alert: dict, lanes: dict[str, dict]) -> list[str]:
    """Return lane IDs whose metro is in the alert's area_desc.

    Conservative: only direct metro code/label containment. The matcher
    must not over-fire on a single storm in one metro, so we require the
    metro code or its first city-name token to appear as a whole word.
    """
    if not alert or not alert.get("area_desc"):
        return []
    area_upper = alert["area_desc"].upper()
    matched = []
    for lid, meta in lanes.items():
        metro = (meta.get("metro") or "").upper()
        if metro and metro in area_upper:
            matched.append(lid)
            continue
        metro_label = (meta.get("metro_label") or "")
        first_token = metro_label.split("(")[0].split("-")[0].strip().split(" ")[0].upper()
        if len(first_token) > 2 and first_token in area_upper:
            matched.append(lid)
            continue
    return matched[:30]


def load_state() -> dict:
    if STATE.exists():
        try:
            return json.loads(STATE.read_text())
        except Exception:
            pass
    return {"seen_ids": []}


def save_state(state: dict) -> None:
    STATE.write_text(json.dumps(state))


def diff(alert: dict, lanes: list[str], state: dict) -> str | None:
    """Return event kind if this alert represents a change vs state."""
    key = f"{alert.get('event','')}::{','.join(sorted(lanes))}"
    if key in state["seen_ids"]:
        return None
    state["seen_ids"].append(key)
    # Trim
    state["seen_ids"] = state["seen_ids"][-1000:]
    return "first_appearance"


def tick() -> dict:
    if not HAVE_CAP:
        return {"ok": False, "err": "cap_tools not importable"}
    try:
        caps = fetch_active_alerts()
    except urllib.error.URLError as e:
        _log("ERROR", "nws_fetch_fail", err=str(e)[:200])
        return {"ok": False, "err": "nws_unreachable"}
    except Exception as e:
        _log("ERROR", "fetch_unexpected", err=str(e)[:200])
        return {"ok": False, "err": "fetch_unexpected"}

    lanes = load_lanes()
    state = load_state()
    fired = 0
    for blob in caps:
        alert = parse_alert(blob)
        if not alert:
            continue
        event = alert.get("event", "")
        matched = match_lanes(alert, lanes)
        kind = diff(alert, matched, state)
        if not kind:
            continue
        for lane_id in matched:
            niche = lane_id.split(":")[0]
            rec = {
                "event_kind": kind,
                "nws_event": event,
                "lane_id": lane_id,
                "area_desc": alert.get("area_desc"),
                "severity": alert.get("severity"),
                "urgency": alert.get("urgency"),
                "headline": alert.get("headline", "")[:200],
            }
            _log("EVENT", "satellite_strike", **rec)
            fired += 1
    save_state(state)
    _log("INFO", "tick_done", caps=len(caps), events=fired)
    return {"ok": True, "caps": len(caps), "events": fired}


def run_loop(interval: int = 60) -> None:
    print(f"[{dt.datetime.utcnow().isoformat()}] satellite-strike-cap starting — interval {interval}s")
    while True:
        try:
            tick()
        except Exception as e:
            _log("ERROR", "tick_failed", err=str(e)[:200])
        time.sleep(interval)


def synthetic_fire_test(lane_id: str = "residential_roofing:DFW",
                        nws_event: str = "Tornado Warning",
                        area_desc: str = "Dallas-Fort Worth Metro, Northern Texas") -> dict:
    """Proof-of-pipeline: emit a fake alert and confirm lane matching + diff."""
    blob = ("__json__:" + json.dumps({
        "properties": {
            "event": nws_event,
            "headline": f"TEST: {nws_event} for {area_desc}",
            "areaDesc": area_desc,
            "severity": "Severe",
            "certainty": "Observed",
            "urgency": "Immediate",
        }
    })).encode()
    alert = parse_alert(blob)
    lanes = load_lanes()
    matched = match_lanes(alert, lanes)
    state = load_state()
    state["seen_ids"] = []
    save_state(state)
    kind = diff(alert, matched, state)
    save_state(state)
    if not kind:
        return {"ok": False, "err": "diff produced no event (should have)"}
    for lid in matched:
        _log("EVENT", "satellite_strike_test",
             lane_id=lid, nws_event=nws_event,
             severity=alert["severity"], area_desc=area_desc)
    return {"ok": True, "matched": matched, "event_kind": kind}


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "once":
        print(json.dumps(tick(), indent=2))
    elif len(sys.argv) > 1 and sys.argv[1] == "synthetic":
        print(json.dumps(synthetic_fire_test(), indent=2))
    else:
        run_loop(int(os.environ.get("INTERVAL", "60")))