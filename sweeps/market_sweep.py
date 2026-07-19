#!/usr/bin/env python3
"""
Empire OS — Market Sweep (keyless OSM Overpass lead acquisition)
===============================================================

Grows the crm_leads table using ONLY free, keyless public data:
  - OpenStreetMap Overpass API (business nodes/ways tagged for our verticals)

No ScrapeCreators / Serply / Serper keys required. The hub shares the SQLite
DB (WAL mode, busy_timeout=30000), so we commit in small batches and never
touch existing rows' niches.

Usage:
  python market_sweep.py --vertical roofing --metro phoenix --limit 500
  python market_sweep.py --all --limit 500
  python market_sweep.py --vertical roofing --metro test --limit 5   # smoke test

`--metro` accepts either a friendly slug ("phoenix") or a full label
("Phoenix, AZ"); `--all` loops every vertical x every configured metro.
"""
import argparse
import hashlib
import json
import sqlite3
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

# ── Config ───────────────────────────────────────────────────────────────────
DB_PATH = "/root/empire_os/empire_os.db"
SOURCE_NAME = "market_sweep"
RADIUS_M = 25000          # 25 km — covers a metro's suburbs
BATCH = 200               # commit every N inserts
REQUEST_TIMEOUT = 30

# Vertical -> OSM tag(s) that map to that pay-per-call niche.
# Tags verified to exist in OpenStreetMap (probe 2026-07-18). Each entry is a
# list of `key=value` Overpass expressions; a business matching ANY is kept.
VERTICAL_TAGS = {
    "roofing":            ['craft=roofer'],
    "hvac":               ['craft=hvac'],
    "plumbing":           ['craft=plumber'],
    "solar":              ['energy=solar', 'shop=solar'],
    "landscaping":        ['craft=gardener', 'craft=landscape', 'craft=tree_planting'],
    "construction":       ['office=construction_company', 'office=contractor'],
    "electrical":         ['craft=electrician'],
    "pest_control":       ['craft=pest_control', 'shop=pest_control'],
    "water_damage":       ['craft=water_damage_restoration', 'emergency=water_damage'],
    "fire_damage":        ['craft=fire_damage_restoration', 'emergency=fire_damage'],
    "mold_remediation":   ['craft=mold_remediation'],
    "mass_tort":          ['office=lawyer', 'office=attorney', 'lawyer=practice'],
    "legal_services":     ['office=lawyer', 'office=attorney', 'office=notary'],
    "debt_relief":        ['office=financial_advisor', 'office=debt_counseling', 'financial_advice=debt_relief'],
}

# US metros: friendly slug -> ("City, ST" label, lat, lon)
METROS = {
    "phoenix":     ("Phoenix, AZ",   33.448376, -112.074036),
    "houston":     ("Houston, TX",   29.763284,  -95.363271),
    "dallas":      ("Dallas, TX",    32.776672,  -96.796888),
    "austin":      ("Austin, TX",    30.267153,  -97.743057),
    "san-antonio": ("San Antonio, TX", 29.424122, -98.493628),
    "chicago":     ("Chicago, IL",   41.878113,  -87.629799),
    "atlanta":     ("Atlanta, GA",   33.749001,  -84.387978),
    "miami":       ("Miami, FL",     25.761680,  -80.191790),
    "denver":      ("Denver, CO",    39.739235, -104.990250),
    "los-angeles": ("Los Angeles, CA", 34.052235, -118.243683),
    "new-york":    ("New York, NY",  40.712776,  -74.005974),
    "seattle":     ("Seattle, WA",   47.606209, -122.332069),
    "charlotte":   ("Charlotte, NC", 35.227087,  -80.843127),
    "nashville":   ("Nashville, TN", 36.162664,  -86.781602),
    "tampa":       ("Tampa, FL",     27.950575,  -82.457177),
    # Special slug used only for smoke testing — points at Phoenix (roofing-rich)
    # so the test reliably returns real businesses instead of an empty set.
    "test":        ("Test, AZ",     33.448376, -112.074036),
}


def log(msg):
    print(f"[market_sweep] {msg}", flush=True)


def make_uid(metro_label, business_name):
    """Stable unique id from source + name + metro (dedupe-friendly)."""
    h = hashlib.sha256(
        f"{SOURCE_NAME}|{business_name}|{metro_label}".encode("utf-8")
    ).hexdigest()[:16]
    return f"ms_{h}"


def build_query(lat, lon, radius, tags):
    # `tags` is a list of `key=value` Overpass expressions. Wrap each in a
    # separate union clause so a business only needs to match ONE of them.
    clauses = "\n      ".join(
        f"node[{t}](around:{radius},{lat},{lon});\n      "
        f"way[{t}](around:{radius},{lat},{lon});"
        for t in tags
    )
    return f"""
    [out:json][timeout:25];
    (
      {clauses}
    );
    out center 1000;
    """


# Alternate public Overpass mirrors, used as fallbacks on timeout/5xx.
OVERPASS_MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]


def fetch_overpass(lat, lon, tags, limit):
    """Query Overpass (with mirror fallback + retries) → normalized dicts."""
    q = build_query(lat, lon, RADIUS_M, tags)
    data = None
    last_err = None
    for attempt in range(3):
        for url in OVERPASS_MIRRORS:
            try:
                req = urllib.request.Request(
                    url,
                    data=urllib.parse.urlencode({"data": q}).encode(),
                    headers={"User-Agent": "EmpireOS-MarketSweep/1.0"},
                )
                raw = urllib.request.urlopen(
                    req, timeout=REQUEST_TIMEOUT).read().decode("utf-8", "ignore")
                data = json.loads(raw)
                break
            except Exception as e:
                last_err = e
                continue
        if data is not None:
            break
        time.sleep(3 * (attempt + 1))  # polite backoff before retrying

    if data is None:
        log(f"Overpass fetch failed after retries: {last_err}")
        return []

    out = []
    for el in data.get("elements", []):
        tags_ = el.get("tags", {})
        name = tags_.get("name", "").strip()
        if not name:
            continue
        lat_ = el.get("lat") or el.get("center", {}).get("lat")
        lon_ = el.get("lon") or el.get("center", {}).get("lon")
        street = tags_.get("addr:street", "")
        housenum = tags_.get("addr:housenumber", "")
        city = tags_.get("addr:city", "")
        state = tags_.get("addr:state", "")
        street_full = f"{housenum} {street}".strip()
        out.append({
            "business_name": name,
            "street": street_full,
            "city": city,
            "state": state,
            "lat": lat_,
            "lon": lon_,
        })
        if len(out) >= limit:
            break
    return out


def open_db():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def existing_keys(conn, metro_label):
    """Return set of (lead_uid, business_name, metro) already present."""
    cur = conn.execute(
        "SELECT lead_uid, business_name, metro FROM crm_leads "
        "WHERE metro = ?", (metro_label,)
    )
    return {(r[0], r[1], r[2]) for r in cur.fetchall()}


def sweep_vertical_metro(conn, vertical, metro_slug, limit):
    if metro_slug not in METROS:
        log(f"unknown metro '{metro_slug}' — skipping")
        return 0
    metro_label, lat, lon = METROS[metro_slug]
    tags = VERTICAL_TAGS.get(vertical)
    if not tags:
        log(f"unknown vertical '{vertical}' — skipping")
        return 0

    log(f"sweeping vertical='{vertical}' metro='{metro_label}' (limit {limit})")
    rows = fetch_overpass(lat, lon, tags, limit)
    log(f"  Overpass returned {len(rows)} raw businesses")

    have = existing_keys(conn, metro_label)
    now = datetime.now(timezone.utc).isoformat()
    inserted = 0
    pending = []

    for r in rows:
        biz = r["business_name"]
        uid = make_uid(metro_label, biz)
        if (uid, biz, metro_label) in have:
            continue  # dedupe against existing rows
        have.add((uid, biz, metro_label))  # also dedupe within this batch
        pending.append((
            uid, SOURCE_NAME, biz, "", "", "",            # contact/email/phone
            metro_label, vertical, r["street"], r["city"], r["state"], "",  # zip
            "",                                           # website
            now,
        ))

    if not pending:
        log("  nothing new to insert")
        return 0

    sql = """
        INSERT OR IGNORE INTO crm_leads (
            lead_uid, source, business_name, contact_name, email, phone,
            metro, niche, street, city, state, zip, website,
            status, created_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?, 'raw', ?)
    """
    # INSERT OR IGNORE guards against any uid collision on the PK too.
    for i in range(0, len(pending), BATCH):
        chunk = pending[i:i + BATCH]
        conn.executemany(sql, chunk)
        conn.commit()
        inserted += len(chunk)
        log(f"  inserted {inserted}/{len(pending)} (committed batch)")
    return inserted


def run_all(conn, limit):
    total = 0
    for vertical in VERTICAL_TAGS:
        for metro_slug in METROS:
            if metro_slug == "test":
                continue  # never auto-run the smoke-test metro
            total += sweep_vertical_metro(conn, vertical, metro_slug, limit)
            time.sleep(1.0)  # be polite to the public endpoint
    return total


def main():
    ap = argparse.ArgumentParser(description="Market sweep (keyless OSM Overpass)")
    ap.add_argument("--vertical", help="one vertical: " + ", ".join(VERTICAL_TAGS))
    ap.add_argument("--metro", help="one metro slug or 'City, ST' label: "
                                    + ", ".join(METROS) + " (or --all)")
    ap.add_argument("--limit", type=int, default=500, help="max businesses per query")
    ap.add_argument("--all", action="store_true",
                    help="loop every vertical x every configured metro")
    args = ap.parse_args()

    if args.all:
        conn = open_db()
        try:
            total = run_all(conn, args.limit)
            log(f"--all complete: {total} new leads inserted")
        finally:
            conn.close()
        return

    if not args.vertical or not args.metro:
        ap.error("--vertical and --metro are required unless --all is given")

    # Allow either a slug or a full "City, ST" label for --metro.
    metro_slug = args.metro
    if metro_slug not in METROS:
        match = next((k for k, v in METROS.items() if v[0] == metro_slug), None)
        if match:
            metro_slug = match
        else:
            ap.error(f"unknown metro '{args.metro}'. Use one of: "
                     + ", ".join(METROS))

    conn = open_db()
    try:
        n = sweep_vertical_metro(conn, args.vertical, metro_slug, args.limit)
        log(f"done: {n} new leads inserted for "
            f"{args.vertical}/{metro_slug}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
