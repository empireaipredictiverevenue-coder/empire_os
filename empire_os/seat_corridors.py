"""Seats Corridors — Empire OS lane seating + lead routing layer.

Seats every active buyer (Supabase `buyers` table) into the 462 lane
corridors (SQLite `lanes` table) by niche -> category:sub_niche, then
routes si_buyer_outreach prospects into OCCUPIED lanes so the
lead_deliverer can bill across ALL niches (not just roofing).

Writes to SQLite require the hub to be stopped (WAL lock). This script is
run on the host or inside empire-hub with the hub service stopped:

    systemctl stop empire-hub-8081.service
    /root/venv/bin/python3 seat_corridors.py seat
    /root/venv/bin/python3 seat_corridors.py route --sample 1000
    systemctl start empire-hub-8081.service

Keep KISS. No invented payouts — we use buyers.base_payout * buyers.fee_rate.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/root/empire_os")

from empire_os.lanes import CATEGORIES, METROS

DB_PATH = "/root/empire_os/empire_os.db"
FEEDBACK_DIR = Path("/root/feedback")
SEAT_LOG = FEEDBACK_DIR / "seat_corridors.jsonl"

# Sub-niche sets per category (from lanes.py CATEGORIES)
SUBS = {cat: list(d["subs"].keys()) for cat, d in CATEGORIES.items()}


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def nicheslug(niche: str) -> str:
    return _slug(niche or "buyer")


def get_conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


# ── Buyer -> lane mapping ────────────────────────────────────────────
def buyer_lane_match(category: str, sub: str) -> str:
    """Lane id for a category:sub combo across ALL metros (wildcard)."""
    return f"{sub}:*"  # placeholder; real lanes are sub:metro


def map_buyer_to_lanes(buyer: dict) -> list[tuple[str, str, str]]:
    """Return list of (category, sub_niche, metro) tuples for a buyer.

    metro is resolved from buyer.metro, falling back to DFW. Mass-tort /
    financial / medical broad matches use DFW + NYC (top two metros) so we
    cover the largest buyer pools.
    """
    niche = (buyer.get("niche") or "").lower()
    buyer_metro = (buyer.get("metro") or "").strip().upper()
    # Only valid metro codes
    if buyer_metro not in METROS:
        buyer_metro = "DFW"

    # Default metros to seat for broad ("*") categories: top 2 metros
    # (always cover DFW + NYC for the highest-volume buyer pools).
    broad_metros = ["DFW", "NYC"]

    matches: list[tuple[str, str, str]] = []

    # Order matters: more specific first.
    if "mass tort" in niche or "legal" in niche or "class action" in niche:
        for sub in SUBS["mass_torts"]:
            for m in broad_metros:
                matches.append(("mass_torts", sub, m))
        return matches

    if "roof" in niche:
        # residential + commercial, use buyer metro (Dallas -> DFW)
        for sub in ("residential_roofing", "commercial_roofing"):
            matches.append(("home_services", sub, buyer_metro))
        return matches

    if "insurance" in niche or "auto insurance" in niche:
        matches.append(("financial", "insurance", buyer_metro))
        return matches

    if "cpa" in niche or any(k in niche for k in ("debt", "mortgage", "loan", "financial")):
        for sub in SUBS["financial"]:
            for m in broad_metros:
                matches.append(("financial", sub, m))
        return matches

    if any(k in niche for k in ("medical", "addiction", "dental", "health")):
        for sub in SUBS["medical_health"]:
            for m in broad_metros:
                matches.append(("medical_health", sub, m))
        return matches

    if any(k in niche for k in ("plumb", "hvac", "electric")):
        for sub in SUBS["home_services"]:
            for m in broad_metros:
                matches.append(("home_services", sub, m))
        return matches

    return matches


# ── Seating ──────────────────────────────────────────────────────────
def fetch_active_buyers():
    from empire_os.sb import select
    rows = (select("buyers", "*", filters={"status": "ACTIVE"}, limit=1000)
            + select("buyers", "*", filters={"status": "active"}, limit=1000))
    # de-dup by id
    by_id = {}
    for r in rows:
        by_id[r["id"]] = r
    out = []
    for r in by_id.values():
        if r.get("is_active", False):
            out.append(r)
    return out


def seat_buyers(conn: sqlite3.Connection, dry_run: bool = False) -> dict:
    """Seat all active buyers into matching lanes. Returns summary stats."""
    buyers = fetch_active_buyers()
    FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)

    stats = {
        "buyers_total": len(buyers),
        "buyers_seated": 0,
        "lanes_occupied_target": 0,
        "by_category": {},
        "skipped_zero_payout": [],
    }

    for buyer in buyers:
        niche = buyer.get("niche") or ""
        base = float(buyer.get("base_payout") or 0)
        fee = float(buyer.get("fee_rate") or 0)
        seat_price = round(base * fee, 4)
        nslug = nicheslug(niche)

        lane_targets = map_buyer_to_lanes(buyer)
        if not lane_targets:
            stats["skipped_zero_payout"].append(
                {"buyer": niche, "reason": "no lane mapping"})
            continue

        seated_any = False
        for category, sub, metro in lane_targets:
            lane_id = f"{sub}:{metro}"
            lane = conn.execute(
                "SELECT * FROM lanes WHERE id=?", (lane_id,)).fetchone()
            if not lane:
                continue
            # Already occupied by someone else? skip (don't clobber).
            if lane["occupied_by"] and lane["occupied_by"] != nslug:
                continue
            if seat_price <= 0:
                # Can't seat profitably — log but do NOT write (no $0 seats).
                continue

            if not dry_run:
                conn.execute(
                    "UPDATE lanes SET occupied_by=?, firm_slug=?, firm_tier=?, "
                    "seat_price=?, updated_at=datetime('now') WHERE id=?",
                    (nslug, niche, "active", seat_price, lane_id),
                )
            seated_any = True
            stats["by_category"].setdefault(category, 0)
            stats["by_category"][category] += 1
            stats["lanes_occupied_target"] += 1

            # Log every seat assignment
            with SEAT_LOG.open("a") as f:
                f.write(json.dumps({
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "action": "seat",
                    "buyer_id": buyer.get("id"),
                    "buyer_niche": niche,
                    "lane_id": lane_id,
                    "category": category,
                    "sub_niche": sub,
                    "metro": metro,
                    "seat_price": seat_price,
                    "base_payout": base,
                    "fee_rate": fee,
                    "dry_run": dry_run,
                }) + "\n")

        if seated_any:
            stats["buyers_seated"] += 1
        elif seat_price <= 0:
            stats["skipped_zero_payout"].append(
                {"buyer": niche, "reason": "base_payout*fee_rate = 0"})

    if not dry_run:
        conn.commit()
    return stats


# ── Lead routing ─────────────────────────────────────────────────────
# Prospect niche -> (category, sub_niche) mapping. Built to align with the
# actual si_buyer_outreach.niche strings we observed.
PROSPECT_MAP = {
    # mass_torts
    "class action lawyer": ("mass_torts", "roundup"),
    "mass tort": ("mass_torts", "roundup"),
    "personal injury": ("mass_torts", "roundup"),
    # financial
    "debt relief": ("financial", "debt_relief"),
    "debt consolidation": ("financial", "debt_relief"),
    "debt relief company": ("financial", "debt_relief"),
    "business loan broker": ("financial", "mortgage"),
    "mortgage broker": ("financial", "mortgage"),
    "auto insurance": ("financial", "insurance"),
    "insurance agent": ("financial", "insurance"),
    "medicare advantage agent": ("financial", "insurance"),
    "life insurance agent": ("financial", "insurance"),
    "final expense insurance": ("financial", "insurance"),
    "investment advisor": ("financial", "investing"),
    "tax preparer": ("financial", "tax_prep"),
    "real estate agent": ("financial", "real_estate"),
    # medical_health
    "addiction treatment center": ("medical_health", "addiction"),
    "medical claims": ("medical_health", "addiction"),
    "mental health clinic": ("medical_health", "pt_rehab"),
    "home health agency": ("medical_health", "pt_rehab"),
    "assisted living": ("medical_health", "addiction"),
    "dental": ("medical_health", "dental"),
    "vision": ("medical_health", "vision"),
    # home_services
    "roofing": ("home_services", "residential_roofing"),
    "commercial roofing": ("home_services", "commercial_roofing"),
    "hvac": ("home_services", "hvac"),
    "plumbing": ("home_services", "plumbing"),
    "electrical": ("home_services", "electrical"),
    "general contractor": ("home_services", "residential_roofing"),
    # restoration
    "restoration": ("restoration", "water_damage"),
    "water_mitigation": ("restoration", "water_damage"),
    "water damage": ("restoration", "water_damage"),
    "fire damage": ("restoration", "fire_damage"),
    "mold": ("restoration", "mold_remediation"),
    "storm": ("restoration", "storm_damage"),
    "emergency services": ("restoration", "disaster_restoration"),
}

PRIORITY_CATS = ["mass_torts", "restoration"]  # highest $ first


def map_prospect_niche(niche: str) -> tuple[str, str] | None:
    n = (niche or "").strip().lower()
    if n in PROSPECT_MAP:
        return PROSPECT_MAP[n]
    # fuzzy substring fallback
    for key, val in PROSPECT_MAP.items():
        if key in n:
            return val
    return None


def route_leads_to_lanes(conn: sqlite3.Connection, sample: int | None = None,
                         dry_run: bool = False) -> dict:
    """Route si_buyer_outreach prospects into OCCUPIED lanes.

    Prioritizes mass_torts + restoration (highest $) lanes first.
    """
    # Only route into lanes that are actually occupied.
    occupied = conn.execute(
        "SELECT id, sub_niche, metro, category FROM lanes "
        "WHERE occupied_by IS NOT NULL").fetchall()
    occ_by_sub_metro = {}
    for l in occupied:
        occ_by_sub_metro[(l["sub_niche"], l["metro"])] = l["id"]

    # Pull prospects
    q = "SELECT prospect_id, niche, metro, score FROM si_buyer_outreach"
    if sample:
        q += f" LIMIT {int(sample)}"
    prospects = conn.execute(q).fetchall()

    # Group prospects by target (category, sub) to prioritize
    grouped: dict[str, list] = {}
    for p in prospects:
        mapped = map_prospect_niche(p["niche"])
        if not mapped:
            continue
        cat, sub = mapped
        grouped.setdefault(cat, []).append((sub, p))

    # Order: priority cats first, then rest
    order = sorted(grouped.keys(),
                   key=lambda c: (0 if c in PRIORITY_CATS else 1, c))

    stats = {
        "prospects_scanned": len(prospects),
        "inserted": 0,
        "skipped_dup": 0,
        "skipped_no_occupied_lane": 0,
        "by_niche_group": {},
    }

    inserted_total = 0
    for cat in order:
        for sub, p in grouped[cat]:
            metro = (p["metro"] or "").strip().upper()
            if metro not in METROS:
                metro = "DFW"
            lane_id = occ_by_sub_metro.get((sub, metro))
            if not lane_id:
                # try any metro where this sub is occupied
                lane_id = None
                for (s, m), lid in occ_by_sub_metro.items():
                    if s == sub:
                        lane_id = lid
                        break
            if not lane_id:
                stats["skipped_no_occupied_lane"] += 1
                continue
            pid = p["prospect_id"]
            # dedupe: skip if already in that lane
            existing = conn.execute(
                "SELECT 1 FROM lane_leads WHERE lane_id=? AND prospect_id=?",
                (lane_id, pid)).fetchone()
            if existing:
                stats["skipped_dup"] += 1
                continue
            omega = float(p["score"]) if p["score"] is not None else None
            if not dry_run:
                conn.execute(
                    "INSERT INTO lane_leads (lane_id, prospect_id, status, "
                    "omega_score, niche) VALUES (?,?,?,?,?)",
                    (lane_id, pid, "pending", omega, p["niche"]))
            inserted_total += 1
            stats["by_niche_group"].setdefault(p["niche"], 0)
            stats["by_niche_group"][p["niche"]] += 1

    stats["inserted"] = inserted_total
    if not dry_run:
        conn.commit()
    return stats


# ── CLI ──────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description="Seats corridors layer")
    ap.add_argument("cmd", choices=["seat", "route", "dryrun-seat", "dryrun-route"])
    ap.add_argument("--sample", type=int, default=None,
                    help="prospect sample size for route")
    args = ap.parse_args()

    if args.cmd.startswith("dryrun"):
        dry = True
        action = args.cmd.split("-", 1)[1]
    else:
        dry = False
        action = args.cmd

    conn = get_conn()
    try:
        if action == "seat":
            stats = seat_buyers(conn, dry_run=dry)
            print(json.dumps(stats, indent=2, default=str))
        elif action == "route":
            stats = route_leads_to_lanes(conn, sample=args.sample, dry_run=dry)
            print(json.dumps(stats, indent=2, default=str))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
