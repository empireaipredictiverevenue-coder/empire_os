#!/usr/bin/env python3
"""
Outreach Pipeline — Queues outbound emails for scored, uncontacted leads.

Queries crm_leads for leads with icp_tier IN ('A','B','C') AND status='new'
AND (outreach_count IS NULL OR outreach_count < 3), then generates personalized
email bodies and prints an outreach plan in dry-run mode.

Usage:
    python3 outreach_pipeline.py                  # dry-run mode (default)
    python3 outreach_pipeline.py --dry-run        # explicit dry-run
    python3 outreach_pipeline.py --send           # queue emails for real (stub)
"""

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone

# ── Config ──────────────────────────────────────────────────────────────
DB_PATH = "/root/empire_os/empire_os.db"
OUTREACH_TEMPLATE = """Hi {contact_name},

We noticed {business_name} operates in the {niche} sector in {metro}. We have a
lead-generation opportunity that could bring you qualified projects in your
service area — no upfront cost, only pay per qualified lead.

Would you be open to a quick chat to see if this is a fit?

Best,
Empire AI Outreach Team
"""


# ── DB Helpers ──────────────────────────────────────────────────────────

def get_db() -> sqlite3.Connection:
    """Connect to the empire_os.db inside the container via incus exec."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def fetch_candidates(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Fetch leads ready for outreach."""
    query = """
        SELECT id, lead_uid, business_name, contact_name, email, phone,
               metro, niche, status, icp_tier, icp_fit_score,
               COALESCE(outreach_count, 0) AS outreach_count
        FROM crm_leads
        WHERE icp_tier IN ('A', 'B', 'C')
          AND status IN ('new', 'raw', 'qualifying')
          AND (outreach_count IS NULL OR outreach_count < 3)
        ORDER BY icp_fit_score DESC, outreach_count ASC
    """
    rows = conn.execute(query).fetchall()
    return rows


def mark_outreach(conn: sqlite3.Connection, lead_id: int) -> None:
    """Increment outreach_count for a lead."""
    conn.execute(
        "UPDATE crm_leads SET outreach_count = COALESCE(outreach_count, 0) + 1, "
        "updated_at = ? WHERE id = ?",
        (datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%f'), lead_id),
    )


# ── Email Generation ───────────────────────────────────────────────────

def generate_email(lead: sqlite3.Row) -> dict:
    """Generate a personalized outreach email. Returns dict with subject/body."""
    business_name = lead["business_name"] or "Your Business"
    contact_name = lead["contact_name"] or business_name
    niche = lead["niche"] or "home services"
    metro = lead["metro"] or "your area"

    # Clean up business name for greeting
    greeting_name = contact_name if contact_name and contact_name != business_name else business_name

    body = OUTREACH_TEMPLATE.format(
        contact_name=greeting_name,
        business_name=business_name,
        niche=niche,
        metro=metro,
    )

    return {
        "lead_id": lead["id"],
        "business_name": business_name,
        "contact_name": contact_name,
        "email": lead["email"],
        "phone": lead["phone"] or "",
        "niche": niche,
        "metro": metro,
        "icp_tier": lead["icp_tier"],
        "icp_fit_score": lead["icp_fit_score"],
        "outreach_count": lead["outreach_count"],
        "subject": f"Lead Generation Opportunity for {business_name}",
        "body": body.strip(),
        "has_email": bool(lead["email"] and lead["email"].strip()),
    }


# ── Queue (stub) ────────────────────────────────────────────────────────

def queue_email(entry: dict) -> bool:
    """
    Queue an email for sending. Stub for now — logs to file.
    Returns True on success.
    """
    # TODO: Wire to actual email-sending pipeline (Resend / SMTP / hub endpoint)
    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "to_email": entry["email"],
        "subject": entry["subject"],
        "lead_id": entry["lead_id"],
    }
    # Append to queue log
    with open("/root/empire_os/outbound/queue_log.jsonl", "a") as f:
        f.write(json.dumps(log_entry) + "\n")
    return True


# ── Main ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Outreach pipeline for Empire OS")
    parser.add_argument(
        "--send", action="store_true",
        help="Actually queue emails (default: dry-run / print only)"
    )
    parser.add_argument(
        "--dry-run", action="store_true", dest="dry_run",
        help="Explicit dry-run mode (default if --send is absent)"
    )
    args = parser.parse_args()
    dry_run = not args.send or args.dry_run

    conn = get_db()
    candidates = fetch_candidates(conn)

    if not candidates:
        print(f"[{datetime.now(timezone.utc).isoformat()}] No candidates found for outreach.")
        print("  (No A/B/C tier leads with status='new' and outreach_count < 3)")
        conn.close()
        return

    print(f"=== Outreach Pipeline — {'DRY RUN' if dry_run else 'LIVE'} ===")
    print(f"Found {len(candidates)} candidate(s) for outreach")
    print(f"Time: {datetime.now(timezone.utc).isoformat()}")
    print()

    plan_lines = []
    queued_count = 0

    for lead in candidates:
        entry = generate_email(lead)
        plan_lines.append(entry)

        status_icon = "✅" if entry["has_email"] else "⚠️"
        outreach_status = f"({entry['outreach_count']}/3 attempts used)"

        print(f"{status_icon} Lead #{entry['lead_id']}: {entry['business_name']}")
        print(f"   Contact: {entry['contact_name']}")
        print(f"   Email:   {entry['email'] or '— MISSING —'}")
        print(f"   Phone:   {entry['phone'] or '—'}")
        print(f"   Niche:   {entry['niche']} | Metro: {entry['metro']}")
        print(f"   ICP:     Tier {entry['icp_tier']} (score: {entry['icp_fit_score']}) {outreach_status}")
        print()

        if dry_run:
            print(f"   ┌─ EMAIL BODY (dry-run) ──────────────────────────────")
            print(f"   │ To: {entry['email'] or 'MISSING'}")
            print(f"   │ Subject: {entry['subject']}")
            for line in entry["body"].split("\n"):
                print(f"   │ {line}")
            print(f"   └────────────────────────────────────────────────────")
            print()

        if not dry_run and entry["has_email"]:
            if queue_email(entry):
                mark_outreach(conn, entry["lead_id"])
                queued_count += 1

    # Commit outreach counter updates if live
    if not dry_run:
        conn.commit()
        print(f"\n=== Queued {queued_count}/{len(candidates)} emails ===")
    else:
        print(f"=== DRY RUN — {len(candidates)} leads processed, no emails sent ===")
        print("Run with --send to queue emails for real.")
        print()

    conn.close()


if __name__ == "__main__":
    main()
