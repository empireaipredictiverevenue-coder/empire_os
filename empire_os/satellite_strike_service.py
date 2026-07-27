# Satellite Strike Ingestion Service
#
# Provides the same logic as Empire OS Hub's /v1/satellite/strike endpoint.
#
# Public API:
#   ingest_strike(request_dict) -> {
#       "ok": bool,
#       "lead_id": int | None,
#       "already": bool,
#       "event": str,
#       "metro": str,
#       "niche": str,
#       "notified": int
#   }
#
# For tests:
#   _COUNTY_TO_METRO: mapping from county tokens to metro codes (public)
#   classify_event(event) -> niche
#   resolve_metro(coords, area, event) -> metro_code

import json
import os
import sqlite3
import time
from datetime import datetime

DB_PATH = "/root/empire_os/empire_os.db"
FEED_DIR = "/root/feedback"
FEED_FILE = os.path.join(FEED_DIR, "satellite_strike_events.jsonl")
STATE_FILE = os.path.join(FEED_DIR, "satellite_strike_state.json")

# ========= EVENTS → NICHE =========
_EVENT_TO_NICHES = {
    # Storm-related
    "tornado": "storm_damage",
    "hurricane": "storm_damage",
    "wind": "storm_damage",
    "thunderstorm": "storm_damage",
    "storm": "storm_damage",
    "snow": "storm_damage",
    "winter": "storm_damage",
    "ice": "storm_damage",
    "blizzard": "storm_damage",
    # Floods
    "flood": "water_damage",
    # Fires
    "fire": "fire_damage",
    "wildfire": "fire_damage",
    # Heat
    "heat": "hvac",
    "excessive heat": "hvac",
    # Earthquakes
    "earthquake": "general_contractor",
}


def _niche_from_event(event: str) -> str:
    key = (event or "").lower()
    for needle, niche in _EVENT_TO_NICHES.items():
        if needle in key:
            return niche
    return "storm_damage"


def classify_event(event: str) -> str:
    """Public helper for tests."""
    return _niche_from_event(event)


# ========= METRO RESOLUTION =========
_COUNTY_TO_METRO = {
    # NYC
    "new york, ny": "NYC", "kings, ny": "NYC", "queens, ny": "NYC",
    "bronx, ny": "NYC", "richmond, ny": "NYC",
    "nassau, ny": "NYC", "westchester, ny": "NYC",
    # LAX
    "los angeles, ca": "LAX", "orange, ca": "LAX",
    "san bernardino, ca": "LAX",
    # SFO
    "san francisco, ca": "SFO", "san mateo, ca": "SFO",
    "alameda, ca": "SFO",
    # HOU
    "harris, tx": "HOU", "fort bend, tx": "HOU",
    "montgomery, tx": "HOU", "brazoria, tx": "HOU",
    # DFW
    "dallas, tx": "DFW", "tarrant, tx": "DFW",
    "collin, tx": "DFW", "denton, tx": "DFW",
    "ellis, tx": "DFW", "johnson, tx": "DFW",
    # CHI
    "cook, il": "CHI", "dupage, il": "CHI", "lake, il": "CHI",
    "kane, il": "CHI", "will, il": "CHI",
    # MIA
    "miami-dade, fl": "MIA", "broward, fl": "MIA",
    "palm beach, fl": "MIA",
    # PHL
    "philadelphia, pa": "PHL", "delaware, pa": "PHL",
    "montgomery, pa": "PHL", "bucks, pa": "PHL",
    "chester, pa": "PHL",
    # BOS, ATL, WDC
    "suffolk, ma": "BOS", "middlesex, ma": "BOS",
    "norfolk, ma": "BOS",
    "fulton, ga": "ATL", "dekalb, ga": "ATL",
    "cobb, ga": "ATL", "gwinnett, ga": "ATL",
    "district of columbia, dc": "WDC",
    "arlington, va": "WDC", "alexandria, va": "WDC",
    "fairfax, va": "WDC", "prince william, va": "WDC",
}


def _metro_from_latlon(lat: float, lon: float) -> str | None:
    boxes = [
        ("NYC", 40.40, 40.95, -74.30, -73.65),
        ("LAX", 33.70, 34.35, -118.85, -117.65),
        ("SFO", 37.30, 38.00, -123.00, -121.80),
        ("HOU", 29.40, 30.30, -95.85, -94.90),
        ("DFW", 32.50, 33.40, -97.65, -96.45),
        ("CHI", 41.45, 42.35, -88.45, -87.30),
        ("MIA", 25.40, 26.40, -80.85, -80.05),
        ("PHL", 39.80, 40.40, -75.55, -74.85),
        ("BOS", 42.10, 42.70, -71.45, -70.65),
        ("ATL", 33.55, 34.05, -84.65, -84.15),
        ("WDC", 38.65, 39.30, -77.40, -76.65),
    ]
    for code, la_min, la_max, lo_min, lo_max in boxes:
        if la_min <= lat <= la_max and lo_min <= lon <= lo_max:
            return code
    return None


def _resolve_metro_from_event(coords: list, area: str, event: str) -> str:
    """Find our metro code (NYC/HOU/DFW/...) from an NWS alert.

    Order:
      1. polygon centroid -> reverse-geocode via a lat/lon -> metro
         heuristic (cover the 11 supported metros with city bounding boxes).
      2. area string -> parse "Montgomery, MD" style tokens to a county,
         then look up in _COUNTY_TO_METRO.
      3. Fallback to the first token of area.
    """
    # 1. polygon centroid -> nearest supported metro by lat/lon bbox
    if coords and isinstance(coords, list) and coords:
        try:
            # Extract lon/lat from the polygon coordinates
            flat = []
            for pt in coords[:50]:
                if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                    flat.append(float(pt[0]))  # longitude
                    flat.append(float(pt[1]))  # latitude
            if len(flat) >= 2:
                lon = sum(flat[0::2]) / max(1, len(flat[0::2]))
                lat = sum(flat[1::2]) / max(1, len(flat[1::2]))
                hit = _metro_from_latlon(lat, lon)
                if hit:
                    return hit
        except Exception:
            pass

    # 2. area string -> county lookup
    if area:
        for token in (t.strip() for t in area.split(";")):
            low = token.lower()
            for k, metro in _COUNTY_TO_METRO.items():
                if k in low or low.startswith(k.split(",")[0]):
                    return metro

    # 3. fallback
    return area.split(";")[0].strip() if area else "Unknown"


def resolve_metro(coords, area, event):
    return _resolve_metro_from_event(coords, area, event)


# ========= CORE SERVICE =========
def _now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _feed_event(rec: dict) -> None:
    os.makedirs(FEED_DIR, exist_ok=True)
    try:
        with open(FEED_FILE, "a") as f:
            f.write(json.dumps(rec) + "\n")
    except Exception:
        pass


def _import_ai_intel() -> None:
    try:
        mod = __import__("empire_os.agents.empire_ai_intel", fromlist=["score_leads"])
        mod.score_leads(batch_size=50)
    except Exception:
        pass


def _db_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ingest_strike(req: dict) -> dict:
    """
    Public API — ingestion entry point.
    Mirrors the hub's /v1/satellite/strike but is a pure business-logic module.
    """
    event = req.get("event", "Unknown")
    severity = req.get("severity", "Unknown")
    area = req.get("area", "")
    headline = req.get("headline", "")
    event_id = req.get("id", "")
    coords = req.get("polygon") or []

    # Niche
    niche = _niche_from_event(event)

    # Metro
    metro = _resolve_metro_from_event(coords, area, event)

    # Lead ID
    # For tests — inject deterministic lead_uid from test event if present
    lead_uid = (
        (event.get("test_lead_uid") if event.get("test_lead_uid") else
         (f"storm_{event_id.split('/')[-1][:32]}" if event_id
          else f"storm_{int(time.time())}"))
    )

    # Severity → score
    sev_score = {
        "Severe": 70.0,
        "Extreme": 85.0,
        "Moderate": 50.0,
        "Minor": 30.0,
    }.get(severity, 50.0)

    now = _now_iso()

    # DB transaction
    with _db_conn() as conn:
        # Idempotent check
        cur = conn.execute(
            "SELECT id FROM crm_leads WHERE lead_uid = ?", (lead_uid,)
        )
        existing = cur.fetchone()
        if existing:
            return {
                "ok": True,
                "already": True,
                "lead_id": existing["id"],
                "event": event,
                "metro": metro,
                "niche": niche,
                "notified": 0,
            }

        # Insert lead
        cur = conn.execute(
            """
            INSERT INTO crm_leads
              (lead_uid, source, niche, metro, business_name, notes,
               status, omega_score, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                lead_uid,
                "satellite_strike",
                niche,
                metro,
                f"Storm Event — {event}",
                (f"{headline} | {area} | severity={severity}" if headline
                 else f"{event} in {area}"),
                "new",
                sev_score,
                now,
                now,
            ),
        )
        lead_id = cur.lastrowid

        # Activity audit
        conn.execute(
            "INSERT INTO crm_activities (lead_id, act_type, summary, actor) "
            "VALUES (?, 'system', ?, 'satellite_strike')",
            (
                lead_id,
                f"Storm event: {event} in {metro} (niche={niche})",
            ),
        )

        # Feedback file
        _feed_event({
            "ts": now,
            "engine": "satellite_strike",
            "event": event,
            "severity": severity,
            "area": area,
            "metro": metro,
            "niche": niche,
            "lead_score": sev_score,
            "headline": headline,
            "event_id": event_id,
            "polygon_points": len(coords),
        })

        # Optional AI intel
        _import_ai_intel()

        # Subscribers with consent gate
        cur = conn.execute(
            """
            SELECT br.prospect_id
            FROM si_buyer_outreach br
            LEFT JOIN si_prospect_consent c ON c.prospect_id = br.prospect_id
            WHERE br.metro = ? AND br.niche = ? AND br.active = 1
              AND (c.opted_in = 1 OR c.opted_in IS NULL)
            ORDER BY RANDOM() LIMIT 25""",
            (metro, niche),
        )
        buyers = cur.fetchall()
        notified = 0
        for br in buyers:
            conn.execute(
                "INSERT INTO crm_activities (lead_id, act_type, summary, actor) "
                "VALUES (?, 'notification', ?, 'satellite_strike')",
                (
                    lead_id,
                    f"storm_alert broadcast to {br['prospect_id']}",
                ),
            )
            notified += 1

        conn.commit()

    return {
        "ok": True,
        "already": False,
        "lead_id": lead_id,
        "event": event,
        "metro": metro,
        "niche": niche,
        "notified": notified,
    }


# Public exports (for import)
__all__ = [
    "ingest_strike",
    "DB_PATH",
    "FEED_FILE",
    "STATE_FILE",
    # Test helpers
    "classify_event",
    "resolve_metro",
    "_COUNTY_TO_METRO",
]