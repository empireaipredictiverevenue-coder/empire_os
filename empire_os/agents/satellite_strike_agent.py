
"""
Empire OS v3 - Satellite Strike product.

Tier-gated real-time event subscription. Polls NOAA + NWS alerts
every 5 minutes. For each active alert above a severity threshold:
  1. pull its polygon (from NWS CAP feed)
  2. find Empire OS subscribers whose home metro is inside polygon
  3. fan-out alert via:
     - Resend email
     - webhook to subscriber
     - in-app via /v1/satellite/active endpoint

Pipeline:
  scrape NOAA  ->  match polygon  ->  notify subscribers
  --------------------------------------------
  Cadence: 5 minutes.

Pricing (handled by marketplace tiers):
  diamond+ tiers get satellite_strike (max 4h response SLA)
  empire+ tiers get satellite_strike PRO (custom polygons)
  titanium  gets satellite_strike ATOMIC (real-time, 30min SLA)

Public endpoints:
  GET  /v1/satellite/active    - active storm cells + matching subscribers
  POST /v1/satellite/subscribe - subscribe polygon + callback
"""
import json, os, sys, time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/root/empire_os")
import requests

HUB  = os.environ.get("HUB_URL", "http://localhost:8000")
FB   = Path("/root/feedback")
LOG  = FB / "satellite_strike.jsonl"
INTERVAL = int(os.environ.get("INTERVAL_SEC", str(5 * 60)))

NWS_ALERTS_URL = "https://api.weather.gov/alerts/active"


def log(level, msg, **fields):
    e = {"ts": datetime.now(timezone.utc).isoformat(), "level": level, "msg": msg, **fields}
    FB.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a") as f:
        f.write(json.dumps(e) + "\n")
    if level in ("ERROR", "EVENT"):
        print(json.dumps(e), flush=True)


def fetch_alerts() -> list:
    """Poll NWS for active alerts. Filter to severe weather impacting metros."""
    try:
        r = requests.get(NWS_ALERTS_URL,
                         params={"status": "actual",
                                 "message_type": "alert"},
                         timeout=15,
                         headers={"User-Agent": "EmpireOS/3.0"})
        if r.status_code != 200: return []
        return r.json().get("features", [])
    except Exception as e:
        log("ERROR", "nws_fail", err=str(e)[:150])
        return []


def is_severe(feature: dict) -> bool:
    props = feature.get("properties", {})
    severity = props.get("severity", "")
    event    = props.get("event", "")
    severe_events = ("Tornado", "Hurricane", "Severe Thunderstorm",
                     "Flash Flood", "Tropical Storm", "Storm Surge",
                     "Blizzard", "Ice Storm", "Wildfire")
    return severity in ("Severe", "Extreme") or any(s in event for s in severe_events)


def alert_polygon(feature: dict) -> dict:
    """Extract polygon + severity + headline."""
    p = feature.get("properties") or {}
    geom = feature.get("geometry") or {}
    coords = None
    if geom.get("type") == "Polygon":
        coords = geom["coordinates"]
    return {
        "id": feature.get("id"),
        "headline": p.get("headline", ""),
        "event":    p.get("event", ""),
        "severity": p.get("severity", ""),
        "area":     p.get("areaDesc", ""),
        "polygon":  coords,
        "sent":     p.get("sent"),
    }


def notify_subscribers(alert: dict) -> int:
    """Find subscribers whose lanes touch this alert polygon and emit
    notification via hub /v1/satellite/strike."""
    try:
        resp = requests.post(f"{HUB}/v1/satellite/strike",
                             json=alert, timeout=8)
        if resp.status_code != 200:
            log("WARN", "notify_http", code=resp.status_code)
            return 0
        try:
            j = resp.json()
        except Exception:
            return 0
        return (j or {}).get("notified", 0)
    except Exception as e:
        log("ERROR", "notify_fail", err=str(e)[:150])
        return 0


def cycle():
    feats = fetch_alerts()
    severe = [f for f in feats if is_severe(f)]
    log("CYCLE_START", "satellite cycle",
        total=len(feats), severe=len(severe))
    notified_total = 0
    for f in severe:
        a = alert_polygon(f)
        n = notify_subscribers(a)
        notified_total += n
        log("EVENT", "alert_notified",
            id=a["id"], event=a["event"], severity=a["severity"],
            notified=n)
    log("CYCLE_END", "satellite cycle complete",
        severe=len(severe), notified=notified_total)


if __name__ == "__main__":
    print(f"[{datetime.now(timezone.utc).isoformat()}] satellite-strike starting - {INTERVAL}s",
          flush=True)
    time.sleep(30)
    while True:
        try: cycle()
        except Exception as e: log("ERROR", "cycle", err=str(e)[:200])
        time.sleep(INTERVAL)
