"""
Empire OS v3 — State-Level Lead Crawler (Task B)

Generates a small (~100) batch of synthetic leads for each of the top 10 US
states and inserts them directly into the lane_leads table with the
state / zip / city / street columns populated, and inserts a matching
state-level lane into the lanes table.

Lane-id convention used here (per Task B spec):
    state-level lane:      "state:CA"
    state+city lane:       "state:CA:Sacramento"

Direct DB insert (rather than /v1/leads/direct) because that endpoint does
not yet forward state/zip/city/street columns — minimal patch surface.

Idempotent on (lane_id, prospect_id) for lane_leads.
Safe re-run: re-running upserts lanes and inserts additional leads with a
fresh timestamp; existing lane_leads rows are not duplicated (prospect_id
includes a per-run nonce).

Usage (inside the empire-hub container):
    python3 /root/empire_os/empire_os/state_lead_crawl.py
    python3 /root/empire_os/empire_os/state_lead_crawl.py --per-state 50
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = "/root/empire_os/empire_os.db"
# Log under /tmp — the /root/feedback dir inside the empire-hub container is
# owned by nobody:nogroup and not writable by root from this context.
LOG_PATH = Path("/tmp/state_lead_crawl.jsonl")
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

# Top 10 US states by population, with primary city + zip prefix samples
TOP_STATES = [
    {"code": "CA", "name": "California",      "primary_city": "Los Angeles",   "zips": ["90001", "90011", "90024", "90210", "92101", "94102"]},
    {"code": "TX", "name": "Texas",           "primary_city": "Houston",       "zips": ["77001", "77002", "75001", "75201", "78201", "73301"]},
    {"code": "FL", "name": "Florida",         "primary_city": "Miami",         "zips": ["33101", "33125", "33602", "32801", "32202", "33301"]},
    {"code": "NY", "name": "New York",        "primary_city": "New York",      "zips": ["10001", "10002", "10025", "11201", "11375", "10451"]},
    {"code": "IL", "name": "Illinois",        "primary_city": "Chicago",       "zips": ["60601", "60602", "60611", "60614", "60618", "60622"]},
    {"code": "PA", "name": "Pennsylvania",    "primary_city": "Philadelphia",  "zips": ["19101", "19102", "19103", "19104", "15201", "17101"]},
    {"code": "OH", "name": "Ohio",            "primary_city": "Columbus",      "zips": ["43201", "43202", "43215", "44101", "45202", "44114"]},
    {"code": "GA", "name": "Georgia",         "primary_city": "Atlanta",       "zips": ["30301", "30302", "30303", "30305", "30309", "30315"]},
    {"code": "NC", "name": "North Carolina",  "primary_city": "Charlotte",     "zips": ["28201", "28202", "28205", "27601", "27401", "27101"]},
    {"code": "MI", "name": "Michigan",        "primary_city": "Detroit",       "zips": ["48201", "48202", "48226", "48104", "49503", "48933"]},
]

# Niches to seed per state. (category, sub_niche, sub_label) — picked to
# span the highest-volume lanes.
NICHES = [
    ("mass_torts",         "camp_lejeune",       "Camp Lejeune Water Contamination"),
    ("home_services",      "residential_roofing", "Residential Roofing"),
    ("restoration",        "water_damage",       "Water Damage Restoration"),
    ("restoration",        "storm_damage",       "Storm & Wind Damage Restoration"),
    ("home_services",      "hvac",               "HVAC & Air Conditioning"),
    ("financial",          "debt_relief",        "Debt Relief & Settlement"),
    ("medical_health",     "weight_loss",        "Weight Loss & GLP-1 Programs"),
]

FIRST_NAMES = [
    "James", "Mary", "Robert", "Patricia", "John", "Jennifer", "Michael", "Linda",
    "David", "Elizabeth", "William", "Barbara", "Richard", "Susan", "Joseph", "Jessica",
    "Thomas", "Sarah", "Charles", "Karen", "Daniel", "Lisa", "Matthew", "Nancy",
]
LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
    "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson",
]
STREET_NAMES = [
    "Main St", "Oak Ave", "Maple Dr", "Cedar Ln", "Elm St", "Park Blvd",
    "Washington St", "Lake Rd", "Hill St", "Sunset Dr", "River Rd", "Forest Ave",
]


def log(level: str, msg: str, **fields) -> None:
    event = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "msg": msg,
        **fields,
    }
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(event) + "\n")
    print(json.dumps(event), flush=True)


def synth_lead(idx: int, state: dict, niche: tuple, run_nonce: str) -> dict:
    """Generate a single synthetic lead row."""
    first = FIRST_NAMES[idx % len(FIRST_NAMES)]
    last = LAST_NAMES[(idx * 7) % len(LAST_NAMES)]
    name = f"{first} {last}"
    zip_code = state["zips"][idx % len(state["zips"])]
    street_num = 100 + (idx * 13) % 9900
    street = f"{street_num} {STREET_NAMES[idx % len(STREET_NAMES)]}"
    email = f"{first.lower()}.{last.lower()}{idx}@example-{state['code'].lower()}.test"
    phone = f"+1{500 + (idx * 31) % 500:03d}{1000000 + (idx * 911) % 8999999:07d}"

    # lead_score: spread across tiers (gold/silver/bronze)
    score_cycle = [82, 68, 71, 55, 90, 60, 76, 49, 88, 64, 73, 58, 81, 67, 79]
    score = score_cycle[idx % len(score_cycle)]
    if score >= 75:
        tier = "gold"
    elif score >= 50:
        tier = "silver"
    else:
        tier = "bronze"

    cat, sub, sub_label = niche
    return {
        "prospect_id": f"prospect_state_{state['code']}_{run_nonce}_{idx:04d}",
        "niche": cat,
        "sub_niche": sub,
        "sub_label": sub_label,
        "name": name,
        "email": email,
        "phone": phone,
        "street": street,
        "city": state["primary_city"],
        "state": state["code"],
        "zip": zip_code,
        "score": score,
        "tier": tier,
    }


def ensure_lane(conn: sqlite3.Connection, state: dict, niche: tuple) -> str:
    """
    Insert (or no-op) a state-level lane for the given (state, niche) pair.

    Lane-id format: "state:CA" (state-level lane) per Task B spec.
    Mirrors lanes.py row schema: category, sub_niche, metro, metro_label.
    Uses state code as the metro slot and state name as metro_label.
    """
    cat, sub, sub_label = niche
    lane_id = f"state:{state['code']}"  # state-level lane
    now = datetime.now(timezone.utc).isoformat()

    # Idempotent: only insert if not already present for this (lane_id, sub_niche).
    existing = conn.execute(
        "SELECT id FROM lanes WHERE id=? AND sub_niche=?",
        (lane_id, sub),
    ).fetchone()
    if existing:
        return lane_id

    conn.execute(
        """
        INSERT OR IGNORE INTO lanes
            (id, category, category_label, sub_niche, sub_label,
             metro, metro_label, firm_tier, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'standard', ?, ?)
        """,
        (
            lane_id,
            cat,
            cat.replace("_", " ").title(),
            sub,
            sub_label,
            state["code"],
            f"State of {state['name']}",
            now,
            now,
        ),
    )
    return lane_id


def _with_retry(fn, *args, max_retries: int = 8, label: str = "", **kwargs):
    """
    Run `fn` with exponential backoff for SQLite 'database is locked' errors.

    Same retry shape as crawler_runner.post_lead — the container has
    15+ concurrent writers (lead_deliverer, intelligence_integration,
    hub, supervisor, …) so contention is normal. Backoff: 0.5s, 1s,
    2s, 4s, 8s, 16s, 32s (max ~63s).
    """
    last_err = None
    for attempt in range(max_retries):
        try:
            return fn(*args, **kwargs)
        except sqlite3.OperationalError as e:
            if "locked" not in str(e).lower():
                raise
            last_err = e
            wait = 0.5 * (2 ** attempt)
            log("RETRY", "db_locked",
                attempt=attempt + 1, max=max_retries,
                wait_s=round(wait, 1), label=label, error=str(e)[:80])
            time.sleep(wait)
    raise last_err  # type: ignore[misc]


def insert_lead(conn: sqlite3.Connection, lane_id: str, lead: dict, now: str) -> int:
    """Insert one lead row into lane_leads with full geo columns populated. Returns new id."""
    notes = (
        f"name={lead['name']} email={lead['email']} phone={lead['phone']} "
        f"city={lead['city']} state={lead['state']} zip={lead['zip']} "
        f"street={lead['street']} source=state_crawl"
    )
    cur = conn.execute(
        """
        INSERT INTO lane_leads
            (lane_id, prospect_id, status, omega_score, omega_tier,
             notes, niche, sub_niche, metro, city, state, zip, street,
             created_at)
        VALUES (?, ?, 'pending', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            lane_id,
            lead["prospect_id"],
            lead["score"],
            lead["tier"],
            notes,
            lead["niche"],
            lead["sub_niche"],
            lead["state"],  # metro slot populated with state code
            lead["city"],
            lead["state"],
            lead["zip"],
            lead["street"],
            now,
        ),
    )
    return cur.lastrowid


def _commit_with_retry(conn: sqlite3.Connection, label: str, max_retries: int = 10) -> None:
    """Commit with exponential backoff on lock contention."""
    last_err: Exception | None = None
    for attempt in range(max_retries):
        try:
            conn.commit()
            return
        except sqlite3.OperationalError as e:
            if "locked" not in str(e).lower():
                raise
            last_err = e
            wait = 0.5 * (2 ** attempt)
            log("RETRY", "commit_locked",
                attempt=attempt + 1, max=max_retries,
                wait_s=round(wait, 1), label=label, error=str(e)[:80])
            time.sleep(wait)
    if last_err:
        raise last_err


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-state", type=int, default=100,
                        help="Leads to generate per state (default 100).")
    args = parser.parse_args()

    per_state = max(1, min(args.per_state, 1000))
    run_nonce = uuid.uuid4().hex[:8]
    now = datetime.now(timezone.utc).isoformat()

    log("INFO", "state_crawl_start",
        per_state=per_state, states=len(TOP_STATES),
        run_nonce=run_nonce)

    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    totals = {"leads": 0, "lanes_new": 0, "lanes_existing": 0, "errors": 0}
    per_state_counts: dict[str, int] = {}
    per_state_lanes_new: dict[str, int] = {}
    per_state_lanes_existing: dict[str, int] = {}

    # ── pre-build all work in memory (no DB contention) ──
    plan: list[tuple[dict, list[tuple[str, dict]]]] = []
    for state in TOP_STATES:
        state_code = state["code"]
        per_niche = max(1, per_state // len(NICHES))
        plan_for_state: list[tuple[str, dict]] = []
        idx_global = 0
        for niche in NICHES:
            lane_id = f"state:{state_code}"
            for i in range(per_niche):
                lead = synth_lead(
                    idx=idx_global,
                    state=state,
                    niche=niche,
                    run_nonce=run_nonce,
                )
                plan_for_state.append((lane_id, lead))
                idx_global += 1
        plan.append((state, plan_for_state))

    try:
        for state, work in plan:
            state_code = state["code"]
            inserted_for_state = 0
            lanes_new_for_state = 0
            lanes_existing_for_state = 0

            # Try the whole state's transaction with retry-on-lock.
            success = False
            for attempt in range(6):
                try:
                    # Ensure clean slate (previous attempt may have left tx open)
                    try:
                        conn.execute("ROLLBACK")
                    except Exception:
                        pass

                    conn.execute("BEGIN IMMEDIATE")

                    # 1. ensure each niche's lane exists for this state
                    lane_seen: set[tuple[str, str]] = set()
                    for lane_id, lead in work:
                        key = (lane_id, lead["sub_niche"])
                        if key in lane_seen:
                            continue
                        lane_seen.add(key)
                        # build niche tuple from lead
                        niche_t = (lead["niche"], lead["sub_niche"], lead.get("sub_label", lead["sub_niche"]))
                        before_count = conn.execute(
                            "SELECT COUNT(*) FROM lanes WHERE id=? AND sub_niche=?",
                            (lane_id, lead["sub_niche"]),
                        ).fetchone()[0]
                        ensure_lane(conn, state, niche_t)
                        after_count = conn.execute(
                            "SELECT COUNT(*) FROM lanes WHERE id=? AND sub_niche=?",
                            (lane_id, lead["sub_niche"]),
                        ).fetchone()[0]
                        if after_count > before_count:
                            lanes_new_for_state += 1
                        else:
                            lanes_existing_for_state += 1

                    # 2. insert all leads
                    for lane_id, lead in work:
                        insert_lead(conn, lane_id, lead, now)
                        inserted_for_state += 1

                    # 3. commit with retry
                    _commit_with_retry(conn, label=f"state:{state_code}")
                    success = True
                    break
                except sqlite3.OperationalError as e:
                    if "locked" not in str(e).lower():
                        raise
                    try:
                        conn.execute("ROLLBACK")
                    except Exception:
                        pass
                    wait = 0.5 * (2 ** attempt)
                    log("RETRY", "state_tx_locked",
                        state=state_code, attempt=attempt + 1,
                        wait_s=round(wait, 1), error=str(e)[:80])
                    time.sleep(wait)

            if not success:
                totals["errors"] += 1
                log("ERROR", "state_failed_after_retries", state=state_code)
                inserted_for_state = 0
                lanes_new_for_state = 0
                lanes_existing_for_state = 0

            totals["leads"] += inserted_for_state
            totals["lanes_new"] += lanes_new_for_state
            totals["lanes_existing"] += lanes_existing_for_state
            per_state_counts[state_code] = inserted_for_state
            per_state_lanes_new[state_code] = lanes_new_for_state
            per_state_lanes_existing[state_code] = lanes_existing_for_state
            log("INFO", "state_done",
                state=state_code, leads=inserted_for_state,
                lanes_new=lanes_new_for_state,
                lanes_existing=lanes_existing_for_state)

    except Exception as e:
        conn.rollback()
        log("FATAL", "crawl_crashed", error=str(e))
        return 1
    finally:
        conn.close()

    log("INFO", "state_crawl_done",
        total_leads=totals["leads"],
        total_lanes_new=totals["lanes_new"],
        total_lanes_existing=totals["lanes_existing"],
        errors=totals["errors"],
        per_state=per_state_counts)

    return 0


if __name__ == "__main__":
    sys.exit(main())