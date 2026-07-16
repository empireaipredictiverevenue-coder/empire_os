"""
Empire OS — Firm Import (manual CSV ingestion).

Lets the operator paste CSV text and ingest it as firm candidates into
si_firm_candidates. Source defaults to 'manual_csv' so dedup works
across imports.

The point:
  Empire OS never had a clean "give the system a list of firms"
  endpoint. Until now, the only path was to scrape or test-inject
  rows directly into si_buyer_payment_methods. This makes the
  human-in-the-loop flow honest.

CSV columns recognized (case-insensitive, flexible ordering):
  name (required)
  vertical (required)       -- 'roofing', 'hvac', 'plumber', 'mass_tort'
  source_id (optional)       -- provider key; auto-generated if absent
  source (optional)          -- default 'manual_csv'
  address, city, state, postcode, country
  phone, website, email
  lat, lon                   -- decimal strings OK
  classification             -- e.g. "craft=roofer"
  notes                      -- any extra column goes into notes

Strict behavior:
  - UNIQUE(source, source_id) — re-importing same source_id is a no-op
    (unless ?update=1 is set)
  - Empty name or vertical = row rejected, returned in errors[]
  - Phone numbers are normalized to +1NNN.NNN.NNNN if US shape

Two modes:
  dry_run=true (default) -> no DB writes; returns what would happen
  dry_run=false          -> writes; returns counts
"""
from __future__ import annotations

import csv
import io
import re
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from typing import Any

sys.path.insert(0, "/root/empire_os")

DB_PATH_DEFAULT = "/root/empire_os/empire_os.db"

ALLOWED_VERTICALS = {"roofing", "hvac", "plumber", "mass_tort",
                     "lawyer", "legal", "hvac_plumbing"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm_phone(raw: str | None) -> str | None:
    if not raw:
        return None
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 10:
        return "+1" + digits
    if len(digits) == 11 and digits.startswith("1"):
        return "+" + digits
    return raw.strip() or None


def parse_csv(csv_text: str) -> tuple[list[dict], list[dict]]:
    """Parse CSV text. Returns (records, errors)."""
    records: list[dict] = []
    errors: list[dict] = []
    if not csv_text or not csv_text.strip():
        errors.append({"row": 0, "reason": "empty_csv"})
        return records, errors
    reader = csv.DictReader(io.StringIO(csv_text))
    if not reader.fieldnames:
        errors.append({"row": 0, "reason": "no_header"})
        return records, errors
    rows = []
    for raw_row in reader:
        row = {}
        for k, v in raw_row.items():
            row[(k or "").strip().lower()] = (v or "").strip()
        rows.append(row)
    for i, row in enumerate(rows, start=2):
        name = row.get("name", "")
        vertical = row.get("vertical", "").lower()
        if not name:
            errors.append({"row": i, "reason": "missing_name", "row_data": row})
            continue
        if vertical not in ALLOWED_VERTICALS:
            errors.append({"row": i, "reason": "missing_or_invalid_vertical",
                           "allowed": sorted(ALLOWED_VERTICALS),
                           "got": vertical})
            continue
        source = row.get("source", "manual_csv").strip() or "manual_csv"
        source_id = (row.get("source_id", "") or "").strip()
        if not source_id:
            seed = "|".join([
                name.lower(), vertical,
                (row.get("city", "") or "").lower(),
                re.sub(r"\D", "", row.get("phone", "") or ""),
            ])
            source_id = "csv-" + (
                uuid.uuid5(uuid.NAMESPACE_DNS, seed).hex[:12])
        try:
            lat = float(row.get("lat")) if row.get("lat") else None
            lon = float(row.get("lon")) if row.get("lon") else None
        except Exception:
            lat = lon = None
        rec = {
            "source": source,
            "source_id": source_id,
            "vertical": vertical,
            "name": name[:200],
            "address": (row.get("address") or "").strip() or None,
            "city": (row.get("city") or "").strip() or None,
            "state": (row.get("state") or "").strip() or None,
            "postcode": (row.get("postcode") or "").strip() or None,
            "country": (row.get("country") or "US").strip() or "US",
            "phone": _norm_phone(row.get("phone")),
            "website": (row.get("website") or "").strip() or None,
            "email": (row.get("email") or "").strip() or None,
            "lat": lat,
            "lon": lon,
            "classification": (row.get("classification") or "").strip() or None,
            "notes": (row.get("notes") or "").strip() or None,
        }
        records.append(rec)
    return records, errors


def upsert(records: list[dict], *, db_path: str = DB_PATH_DEFAULT,
           update: bool = False) -> tuple[int, int, int]:
    """Returns (inserted, updated, total_seen)."""
    inserted = updated = 0
    cnx = sqlite3.connect(db_path)
    try:
        for r in records:
            if update:
                cur = cnx.execute(
                    "UPDATE si_firm_candidates "
                    "SET vertical=?, name=?, address=?, city=?, "
                    "    state=?, postcode=?, country=?, phone=?, "
                    "    website=?, email=?, lat=?, lon=?, "
                    "    classification=?, payload=COALESCE(payload, '{}') "
                    "WHERE source=? AND source_id=?",
                    (r["vertical"], r["name"], r["address"], r["city"],
                     r["state"], r["postcode"], r["country"], r["phone"],
                     r["website"], r["email"], r["lat"], r["lon"],
                     r["classification"],
                     r["source"], r["source_id"]))
                if cur.rowcount > 0:
                    updated += 1
                    continue
            cur = cnx.execute(
                "INSERT OR IGNORE INTO si_firm_candidates "
                "(ts, source, source_id, vertical, name, address, city, "
                " state, postcode, country, phone, website, email, lat, lon, "
                " classification, payload, status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "
                "        ?, ?, 'uncontacted')",
                (now_iso(),
                 r["source"], r["source_id"], r["vertical"], r["name"],
                 r["address"], r["city"], r["state"], r["postcode"],
                 r["country"], r["phone"], r["website"], r["email"],
                 r["lat"], r["lon"], r["classification"],
                 '{"csv_import":true}'))
            if cur.rowcount > 0:
                inserted += 1
        cnx.commit()
    finally:
        cnx.close()
    return inserted, updated, len(records)


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS si_firm_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    source TEXT NOT NULL,
    source_id TEXT NOT NULL,
    vertical TEXT NOT NULL,
    name TEXT NOT NULL,
    address TEXT,
    city TEXT,
    state TEXT,
    postcode TEXT,
    country TEXT,
    lat REAL,
    lon REAL,
    phone TEXT,
    website TEXT,
    classification TEXT,
    email TEXT,
    payload TEXT,
    status TEXT NOT NULL DEFAULT 'uncontacted',
    matched_lane_id TEXT,
    contacted_at TEXT,
    contacted_via TEXT,
    blacklisted_reason TEXT,
    UNIQUE(source, source_id)
);
"""


def ensure_schema(db_path: str = DB_PATH_DEFAULT) -> None:
    cnx = sqlite3.connect(db_path)
    try:
        cnx.executescript(SCHEMA_SQL)
        cnx.commit()
    finally:
        cnx.close()
