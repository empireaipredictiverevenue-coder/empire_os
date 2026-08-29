#!/usr/bin/env python3
"""Retry network_error buyer_leads — re-deliver to buyer endpoints."""
import sqlite3, json, urllib.request, time, sys
from datetime import datetime, timezone

DB = "/root/empire_os/empire_os.db"
BATCH = int(sys.argv[1]) if len(sys.argv) > 1 else 500

def retry_batch():
    conn = sqlite3.connect(DB, timeout=60, isolation_level=None)
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row

    # Get network_error leads with endpoint info
    rows = conn.execute("""
        SELECT bl.id, bl.lane_lead_id, bl.buyer_id, bl.endpoint_response, bl.payout_usd,
               bl.niche, bl.metro
        FROM buyer_leads bl
        WHERE bl.endpoint_status='network_error'
          AND bl.endpoint_response IS NOT NULL
          AND bl.endpoint_response != ''
        ORDER BY bl.created_at ASC
        LIMIT ?
    """, (BATCH,)).fetchall()

    retried = 0
    succeeded = 0
    still_failed = 0

    for r in rows:
        # The endpoint_response may contain the endpoint URL or the error
        # We need to find the buyer's endpoint URL
        buyer = r["buyer_id"]
        # Parse previous response to extract endpoint
        try:
            prev = json.loads(r["endpoint_response"])
        except:
            prev = {}

        endpoint = prev.get("endpoint", "")
        if not endpoint:
            # Look up buyer endpoint from si_buyer_outreach
            ep = conn.execute("SELECT endpoint_url FROM si_buyer_outreach WHERE endpoint_url IS NOT NULL AND endpoint_url != '' AND active=1 LIMIT 1").fetchone()
            if ep:
                endpoint = ep[0]

        if not endpoint:
            still_failed += 1
            continue

        # Re-deliver the lead
        payload = json.dumps({
            "lane_lead_id": r["lane_lead_id"],
            "buyer_id": buyer,
            "niche": r["niche"],
            "metro": r["metro"],
            "payout_usd": r["payout_usd"],
        }).encode()

        try:
            req = urllib.request.Request(endpoint, data=payload, headers={"Content-Type": "application/json"}, method="POST")
            resp = urllib.request.urlopen(req, timeout=15)
            if resp.status == 200:
                conn.execute("UPDATE buyer_leads SET endpoint_status='http_200', endpoint_response=? WHERE id=?",
                             (json.dumps({"ok": True, "retried": True}), r["id"]))
                succeeded += 1
            else:
                still_failed += 1
        except Exception as e:
            conn.execute("UPDATE buyer_leads SET endpoint_response=? WHERE id=?",
                         (json.dumps({"error": str(e)[:200], "retried_at": datetime.now(timezone.utc).isoformat()}), r["id"]))
            still_failed += 1

        retried += 1
        time.sleep(0.05)  # gentle rate limit

    conn.close()
    return {"retried": retried, "succeeded": succeeded, "still_failed": still_failed}

if __name__ == "__main__":
    import json as _j
    print(f"retry_network_errors starting batch={BATCH}", flush=True)
    result = retry_batch()
    print(_j.dumps(result), flush=True)
