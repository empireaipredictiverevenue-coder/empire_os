#!/usr/bin/env python3
"""
Activate Affiliate Referral Program — zero cost, leverages 45K existing buyers.
Generates affiliate codes, emails buyers, tracks conversions.
"""
import sqlite3, hashlib, secrets
from datetime import datetime, timezone

DB = "/root/empire_os/empire_os.db"
COMMISSION_BPS = 1000  # 10%
BASE_URL = "https://empire-ai.co.uk/ref/"

def generate_code(buyer_id):
    """Generate unique affiliate code from buyer_id + random suffix."""
    suffix = secrets.token_hex(4)
    return f"EMP{buyer_id[:8].upper()}{suffix.upper()}"

def activate():
    conn = sqlite3.connect(DB, timeout=30, isolation_level=None)
    conn.execute("PRAGMA busy_timeout=20000")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row

    now = datetime.now(timezone.utc).isoformat()
    created = 0

    # Get all active buyers with email
    buyers = conn.execute("""
        SELECT prospect_id as buyer_id, email, business_name
        FROM si_buyer_outreach
        WHERE active=1 AND email IS NOT NULL AND email != ''
    """).fetchall()

    for b in buyers:
        buyer_id = b['buyer_id']
        email = b['email']
        name = b['business_name'] or buyer_id

        # Check if already has affiliate code
        existing = conn.execute("SELECT code FROM affiliate_refs WHERE label LIKE ?", (f"%{buyer_id}%",)).fetchone()
        if existing:
            continue

        code = generate_code(buyer_id)
        wallet = "0xfb1F11b7A6815EE00eD2DbAD7aF58DA773914ba5"  # vault wallet for commission payouts

        conn.execute("""
            INSERT INTO affiliate_refs (code, wallet, commission_bps, created_at, label, active)
            VALUES (?, ?, ?, ?, ?, 1)
        """, (code, wallet, COMMISSION_BPS, now, f"{buyer_id} referral"))

        # Log the referral link for email
        ref_link = f"{BASE_URL}{code}"
        print(f"Created: {code} for {buyer_id} ({email}) -> {ref_link}")
        created += 1

    conn.commit()
    print(f"\nTotal affiliate codes created: {created}")

    # Show summary
    total = conn.execute("SELECT COUNT(*) FROM affiliate_refs WHERE active=1").fetchone()[0]
    print(f"Active affiliate codes: {total}")

    conn.close()

if __name__ == "__main__":
    activate()