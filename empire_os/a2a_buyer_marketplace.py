#!/usr/bin/env python3
"""A2A (Agent-to-Agent) Buyer Marketplace Pusher — Empire OS v3.

Matches tier B+ leads (lane_leads.omega_tier IN tier_a|tier_b|gold|silver)
to active buyers (si_buyer_outreach) by niche + metro, then records the
assignment in `buyer_leads` and stamps `lane_leads.buyer_id` so subsequent
runs (and crawler_runner.py's process_lead() return value) can see the
match. Optionally POSTs the assignment to a per-buyer webhook if the buyer
row carries an `endpoint_url`.

Designed to be idempotent: skips lane_leads rows that already have a
buyer_id set. Designed to be additive: never deletes or downgrades
existing buyer_leads rows.

Run modes:
  - default:  one tick (matches, writes, returns counts)
  - --daemon: same logic in a 5-minute loop (used by the systemd timer
              only when you want in-process loop instead of the timer)
  - --dry-run: match + count only, no DB writes, no HTTP
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
DB_PATH = Path(os.environ.get("EMPIRE_DB_PATH", "/root/empire_os/empire_os.db"))
FEEDBACK_LOG = Path("/root/feedback/a2a_buyer_marketplace.jsonl")
FEEDBACK_LOG.parent.mkdir(parents=True, exist_ok=True)

# Tier B+ = anything lane_leads.omega_tier that ranks as B or better.
# "tier_a" and "tier_b" are the canonical labels used by the AI
# intelligence pipeline; "gold"/"silver" are omega labels used on
# residential_roofing — treat both as B+.
TIER_BPLUS = ("tier_a", "tier_b", "gold", "silver")

# Cap how many leads we push per buyer per cycle. Prevents one buyer from
# gobbling the whole lane in the first run.
DEFAULT_PER_BUYER_CAP = 25

# HTTP timeout for buyer webhook POSTs.
HTTP_TIMEOUT = 15


# ---------------------------------------------------------------------------
# Schema bootstrap (idempotent)
# ---------------------------------------------------------------------------
SCHEMA_STATEMENTS = [
    # Track which buyer has been assigned to a lane lead. Crawler already
    # touches lane_leads so we keep the column nullable.
    """
    ALTER TABLE lane_leads ADD COLUMN buyer_id TEXT
    """,
    # Optional buyer marketplace config that we'll backfill defaults for
    # if absent. These are kept on si_buyer_outreach to avoid creating a
    # parallel buyers table — si_buyer_outreach already holds 30k buyer
    # candidates and is the source of truth for outreach state.
    """
    ALTER TABLE si_buyer_outreach ADD COLUMN niches TEXT DEFAULT ''
    """,
    """
    ALTER TABLE si_buyer_outreach ADD COLUMN metros TEXT DEFAULT ''
    """,
    """
    ALTER TABLE si_buyer_outreach ADD COLUMN wallet TEXT DEFAULT ''
    """,
    """
    ALTER TABLE si_buyer_outreach ADD COLUMN payout_per_lead REAL DEFAULT 0
    """,
    """
    ALTER TABLE si_buyer_outreach ADD COLUMN endpoint_url TEXT DEFAULT ''
    """,
    """
    ALTER TABLE si_buyer_outreach ADD COLUMN active INTEGER DEFAULT 1
    """,
    # Assignment ledger. One row per (lane_lead, buyer) push so re-runs
    # don't lose history and buyer invoicing can join back to it.
    """
    CREATE TABLE IF NOT EXISTS buyer_leads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        buyer_id TEXT NOT NULL,
        lane_lead_id INTEGER NOT NULL,
        prospect_id TEXT,
        niche TEXT,
        metro TEXT,
        omega_tier TEXT,
        match_score REAL,
        payout_usd REAL DEFAULT 0,
        endpoint_status TEXT DEFAULT 'pending',
        endpoint_response TEXT DEFAULT '',
        created_at TEXT DEFAULT (datetime('now')),
        UNIQUE(buyer_id, lane_lead_id)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_buyer_leads_buyer ON buyer_leads(buyer_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_buyer_leads_lane_lead ON buyer_leads(lane_lead_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_lane_leads_buyer ON lane_leads(buyer_id)
    """,
]


def _column_exists(cur: sqlite3.Cursor, table: str, col: str) -> bool:
    rows = cur.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r[1] == col for r in rows)


def ensure_schema(conn: sqlite3.Connection) -> dict:
    """Apply additive schema changes. Returns counts of what was applied."""
    cur = conn.cursor()
    applied = {"columns_added": [], "tables_created": [], "skipped": []}
    for stmt in SCHEMA_STATEMENTS:
        s = stmt.strip().lower()
        if s.startswith("alter table"):
            # Parse "alter table <tbl> add column <col>"
            parts = s.split()
            tbl, col = parts[2], parts[5]
            if _column_exists(cur, tbl, col):
                applied["skipped"].append(f"{tbl}.{col}")
                continue
            try:
                cur.execute(stmt)
                applied["columns_added"].append(f"{tbl}.{col}")
            except sqlite3.OperationalError as e:
                # Duplicate column from a race / partial run.
                if "duplicate column" in str(e).lower():
                    applied["skipped"].append(f"{tbl}.{col}")
                else:
                    raise
        elif s.startswith("create"):
            cur.execute(stmt)
            applied["tables_created"].append(
                s.split("exists")[1].strip().split("(")[0].strip()
                if "if not exists" in s
                else s.split("table")[1].split("(")[0].strip()
            )
    conn.commit()

    # Backfill buyer config: derive niches/metros from the row's existing
    # single-value niche/metro columns so legacy buyers become matchable
    # without manual configuration. New buyers can still override by
    # setting niches/metros directly.
    conn.execute(
        """
        UPDATE si_buyer_outreach
           SET niches    = COALESCE(NULLIF(niches,    ''), niche),
               metros    = COALESCE(NULLIF(metros,    ''), metro),
               active    = COALESCE(active, 1),
               payout_per_lead = COALESCE(payout_per_lead, 0)
         WHERE niches = '' OR niches IS NULL
            OR metros = '' OR metros IS NULL
        """
    )
    conn.commit()
    return applied


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------
def _split_csv(value: str) -> list[str]:
    if not value:
        return []
    return [v.strip().lower() for v in value.replace("|", ",").split(",") if v.strip()]


def _norm(value: str | None) -> str:
    return (value or "").strip().lower()


def _overlap(a: str, b: str) -> bool:
    """True if either side contains the other (loose match: 'roofing' matches
    'commercial_roofing')."""
    a, b = _norm(a), _norm(b)
    if not a or not b:
        return False
    if a == b:
        return True
    if a in b or b in a:
        return True
    # Token-level overlap for snake_case values like 'water_damage'
    a_toks = set(a.replace("-", "_").split("_"))
    b_toks = set(b.replace("-", "_").split("_"))
    return bool(a_toks & b_toks)


def score_match(buyer: dict, lead: dict) -> float:
    """Return a 0..1 confidence score for buyer<->lead match. 0 = no match."""
    b_niches = _split_csv(buyer.get("niches", "")) or [_norm(buyer.get("niche", ""))]
    b_metros = _split_csv(buyer.get("metros", "")) or [_norm(buyer.get("metro", ""))]
    lead_niche = _norm(lead.get("niche"))
    lead_metro = _norm(lead.get("metro"))

    niche_hit = any(_overlap(bn, lead_niche) for bn in b_niches if bn)
    metro_hit = any(_overlap(bm, lead_metro) for bm in b_metros if bm)

    if not niche_hit and not metro_hit:
        return 0.0
    # Niche is the hard filter; metro is a tiebreaker. If buyer only
    # matches niche, give 0.7; if both, 1.0.
    if niche_hit and metro_hit:
        return 1.0
    return 0.7


def fetch_active_buyers(conn: sqlite3.Connection) -> list[dict]:
    cur = conn.execute(
        """
        SELECT prospect_id, business_name, email, niche, metro,
               niches, metros, wallet, payout_per_lead, endpoint_url, active
          FROM si_buyer_outreach
         WHERE COALESCE(active, 1) = 1
        """
    )
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def fetch_unassigned_leads(conn: sqlite3.Connection, limit: int) -> list[dict]:
    placeholders = ",".join("?" for _ in TIER_BPLUS)
    cur = conn.execute(
        f"""
        SELECT id, lane_id, prospect_id, status, omega_tier, niche, metro
          FROM lane_leads
         WHERE buyer_id IS NULL
           AND COALESCE(omega_tier, '') IN ({placeholders})
         ORDER BY
           CASE omega_tier WHEN 'gold' THEN 0 WHEN 'silver' THEN 1
                           WHEN 'tier_a' THEN 2 WHEN 'tier_b' THEN 3
                           ELSE 9 END,
           id ASC
         LIMIT ?
        """,
        (*TIER_BPLUS, limit),
    )
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def fetch_already_assigned_ids(conn: sqlite3.Connection, lane_lead_ids: list[int]) -> set[int]:
    if not lane_lead_ids:
        return set()
    placeholders = ",".join("?" for _ in lane_lead_ids)
    rows = conn.execute(
        f"SELECT lane_lead_id FROM buyer_leads WHERE lane_lead_id IN ({placeholders})",
        lane_lead_ids,
    ).fetchall()
    return {r[0] for r in rows}


# ---------------------------------------------------------------------------
# Push
# ---------------------------------------------------------------------------
def post_to_buyer(endpoint: str, payload: dict) -> tuple[str, str]:
    """POST payload to buyer endpoint. Returns (status, response_text)."""
    if not endpoint:
        return ("no_endpoint", "")
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        endpoint, data=body, method="POST",
        headers={"Content-Type": "application/json",
                 "User-Agent": "EmpireOS-A2A/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            return (f"http_{resp.status}", resp.read(2048).decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        return (f"http_{e.code}", e.read(2048).decode("utf-8", "replace"))
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return ("network_error", str(e)[:500])


def push_cycle(conn: sqlite3.Connection,
               *,
               lead_limit: int = 500,
               per_buyer_cap: int = DEFAULT_PER_BUYER_CAP,
               dry_run: bool = False,
               post_webhook: bool = True) -> dict:
    """One push cycle. Returns a summary dict (also written to feedback log)."""
    buyers = fetch_active_buyers(conn)
    leads = fetch_unassigned_leads(conn, limit=lead_limit)
    already = fetch_already_assigned_ids(conn, [int(l["id"]) for l in leads])
    leads = [l for l in leads if int(l["id"]) not in already]

    # Pre-build a per-token buyer index so we only score buyers that share
    # at least one niche token with the lead. 30k buyers x 500 leads would
    # otherwise be 15M score_match calls. With token prefilter we typically
    # consider <50 buyers per lead.
    buyers_by_token: dict[str, list[dict]] = {}
    for b in buyers:
        tokens = set(_split_csv(b.get("niches", "")) or [_norm(b.get("niche", ""))])
        for t in tokens:
            if not t:
                continue
            # Also index the raw token and each underscore-split piece so
            # 'residential_roofing' on the lead side finds buyers stored as
            # 'roofing'.
            buyers_by_token.setdefault(t, []).append(b)
            for piece in t.split("_"):
                if piece and len(piece) > 2:
                    buyers_by_token.setdefault(piece, []).append(b)

    assignments: list[dict] = []
    buyer_usage: dict[str, int] = {}
    skipped_no_match = 0

    for lead in leads:
        # Gather candidate buyers by overlapping tokens.
        lead_tokens: set[str] = set()
        ln = _norm(lead.get("niche"))
        if ln:
            lead_tokens.add(ln)
            lead_tokens.update(piece for piece in ln.split("_") if piece and len(piece) > 2)
        candidates: list[dict] = []
        seen: set[str] = set()
        for tok in lead_tokens:
            for b in buyers_by_token.get(tok, []):
                bid = b.get("prospect_id", "")
                if bid in seen:
                    continue
                seen.add(bid)
                candidates.append(b)

        best = None
        best_score = 0.0
        for b in candidates:
            if buyer_usage.get(b.get("prospect_id", ""), 0) >= per_buyer_cap:
                continue
            s = score_match(b, lead)
            if s > best_score:
                best_score = s
                best = b

        if not best:
            skipped_no_match += 1
            continue

        buyer_id = best.get("prospect_id", "")
        buyer_usage[buyer_id] = buyer_usage.get(buyer_id, 0) + 1

        assignment = {
            "buyer_id": buyer_id,
            "buyer_name": best.get("business_name", ""),
            "buyer_email": best.get("email", ""),
            "buyer_wallet": best.get("wallet", ""),
            "lane_lead_id": int(lead["id"]),
            "lane_id": lead.get("lane_id", ""),
            "prospect_id": lead.get("prospect_id", ""),
            "niche": lead.get("niche", ""),
            "metro": lead.get("metro", ""),
            "omega_tier": lead.get("omega_tier", ""),
            "match_score": best_score,
            "payout_usd": float(best.get("payout_per_lead") or 0),
            "endpoint_url": best.get("endpoint_url", ""),
        }
        assignments.append(assignment)

    # Write to DB.
    written = 0
    if not dry_run and assignments:
        for a in assignments:
            try:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO buyer_leads
                        (buyer_id, lane_lead_id, prospect_id, niche, metro,
                         omega_tier, match_score, payout_usd,
                         endpoint_status, endpoint_response)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', '')
                    """,
                    (a["buyer_id"], a["lane_lead_id"], a["prospect_id"],
                     a["niche"], a["metro"], a["omega_tier"],
                     a["match_score"], a["payout_usd"]),
                )
                conn.execute(
                    "UPDATE lane_leads SET buyer_id = ? WHERE id = ? AND buyer_id IS NULL",
                    (a["buyer_id"], a["lane_lead_id"]),
                )
                written += 1
            except sqlite3.Error as e:
                print(f"  db error lead={a['lane_lead_id']}: {e}", file=sys.stderr)
        conn.commit()

    # Fire webhooks (only after DB write so we don't claim a lead we couldn't
    # claim).
    webhooks_sent = 0
    if post_webhook and not dry_run:
        for a in assignments:
            # Resolve endpoint: 1) explicit endpoint_url, 2) generated local
            # receiver for priced buyers (delivers to test_receive).
            ep = a["endpoint_url"] or ""
            if not ep and a["payout_usd"] > 0:
                ep = "http://10.118.155.218:8081/v1/buyers/test_receive"
            if not ep:
                # No endpoint — mark as such so downstream dashboards see it.
                conn.execute(
                    "UPDATE buyer_leads SET endpoint_status='no_endpoint' "
                    "WHERE buyer_id=? AND lane_lead_id=? AND endpoint_status='pending'",
                    (a["buyer_id"], a["lane_lead_id"]),
                )
                continue
            status, body = post_to_buyer(ep, {
                "buyer_id": a["buyer_id"],
                "lane_lead_id": a["lane_lead_id"],
                "prospect_id": a["prospect_id"],
                "niche": a["niche"],
                "metro": a["metro"],
                "tier": a["omega_tier"],
                "match_score": a["match_score"],
                "payout_usd": a["payout_usd"],
                "ts": datetime.now(timezone.utc).isoformat(),
            })
            conn.execute(
                "UPDATE buyer_leads SET endpoint_status=?, endpoint_response=? "
                "WHERE buyer_id=? AND lane_lead_id=?",
                (status, body[:500], a["buyer_id"], a["lane_lead_id"]),
            )
            webhooks_sent += 1
        conn.commit()

    summary = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "dry_run": dry_run,
        "buyers_considered": len(buyers),
        "leads_eligible": len(leads),
        "assignments": len(assignments),
        "written": written,
        "skipped_no_match": skipped_no_match,
        "webhooks_sent": webhooks_sent,
        "buyers_used": len([c for c in buyer_usage.values() if c > 0]),
        "per_buyer_cap": per_buyer_cap,
    }

    # Append to feedback log (newline-delimited JSON).
    with FEEDBACK_LOG.open("a") as f:
        f.write(json.dumps({"summary": summary, "assignments": assignments}) + "\n")

    return summary


# ---------------------------------------------------------------------------
# Entrypoints
# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description="Empire OS v3 A2A buyer marketplace pusher")
    ap.add_argument("--dry-run", action="store_true",
                    help="Match + report only; no DB writes, no HTTP")
    ap.add_argument("--limit", type=int, default=500,
                    help="Max lane_leads to consider per cycle")
    ap.add_argument("--per-buyer-cap", type=int, default=DEFAULT_PER_BUYER_CAP,
                    help="Max leads per buyer per cycle")
    ap.add_argument("--no-webhook", action="store_true",
                    help="Skip buyer endpoint POSTs (still write DB)")
    ap.add_argument("--daemon", action="store_true",
                    help="Loop every --interval seconds (used only if you don't "
                         "want to rely on the systemd timer)")
    ap.add_argument("--interval", type=int, default=300,
                    help="Daemon loop interval in seconds (default 300 = 5min)")
    args = ap.parse_args()

    if not DB_PATH.exists():
        print(f"FATAL: DB not found at {DB_PATH}", file=sys.stderr)
        return 2

    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    # WAL + busy_timeout prevent "database is locked" errors when multiple
    # agents (cortex, content_engine, a2a-push) hit the DB concurrently.
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.row_factory = None
    schema_report = ensure_schema(conn)
    if schema_report["columns_added"] or schema_report["tables_created"]:
        print(f"schema: +{len(schema_report['columns_added'])} cols, "
              f"+{len(schema_report['tables_created'])} tables; "
              f"skipped existing {len(schema_report['skipped'])}")

    if args.daemon:
        print(f"a2a_buyer_marketplace: daemon mode, interval={args.interval}s")
        while True:
            try:
                s = push_cycle(conn,
                               lead_limit=args.limit,
                               per_buyer_cap=args.per_buyer_cap,
                               dry_run=args.dry_run,
                               post_webhook=not args.no_webhook)
                print(f"  cycle: {s['assignments']} assignments "
                      f"({s['written']} written, {s['webhooks_sent']} webhooks, "
                      f"{s['skipped_no_match']} no-match)")
            except Exception as e:
                print(f"  cycle error: {e}", file=sys.stderr)
            time.sleep(args.interval)

    s = push_cycle(conn,
                   lead_limit=args.limit,
                   per_buyer_cap=args.per_buyer_cap,
                   dry_run=args.dry_run,
                   post_webhook=not args.no_webhook)
    print(json.dumps(s, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
