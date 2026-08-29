#!/usr/bin/env python3
"""GRIP lead rotator — per-metro distribution health check.

Schedule: every 10 min via systemd timer. Pure SQL aggregation, no LLM.
ALWAYS sys.exit(0).
"""
import sqlite3, os, sys, json
from datetime import datetime, timezone

DB = "/root/empire_os/empire_os.db"
LOG = "/root/empire_os/feedback/grip_lead_rotator.jsonl"
SQLITE_TIMEOUT = 10
COVERAGE_THRESHOLD = 0.01  # <1% delivery = alert


def now():
    return datetime.now(timezone.utc).isoformat()


def open_db():
    uri = f"file:{DB}?mode=rw"
    c = sqlite3.connect(uri, uri=True, timeout=SQLITE_TIMEOUT)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA busy_timeout=30000")
    return c


def write_log(entry):
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")


def main():
    ts = now()
    try:
        c = open_db()
        # metro-level rollup: total leads + delivered count + most-recent delivery
        rows = c.execute(
            """
            SELECT metro,
                   COUNT(*) AS total,
                   SUM(CASE WHEN status IN ('delivered','delivered_processed') THEN 1 ELSE 0 END) AS delivered,
                   MAX(CASE WHEN status IN ('delivered','delivered_processed') THEN created_at END) AS last_delivered
            FROM lane_leads
            WHERE metro <> ''
            GROUP BY metro
            """
        ).fetchall()
        c.close()
    except Exception as e:
        write_log({"ts": ts, "error": str(e)[:300]})
        sys.exit(0)

    metros = []
    for metro, total, delivered, last_delivered in rows:
        delivered = delivered or 0
        total = total or 0
        rate = (delivered / total) if total else 0.0

        alert = None
        action = "ok"

        if total == 0:
            alert = "empty_metro"
            action = "skip"
        elif delivered == 0:
            # any delivered? no. stale if rows are >7 days old
            alert = "no_delivery_evidence"
            action = "investigate"
        else:
            # stale delivery? check last_delivered
            if last_delivered is None:
                alert = "no_delivered_recent"
                action = "investigate"
            elif rate < COVERAGE_THRESHOLD:
                alert = f"low_coverage_{rate:.4f}"
                action = "rotate_focus"

        entry = {
            "ts": ts,
            "metro": metro,
            "total_leads": total,
            "delivered": delivered,
            "rate": round(rate, 6),
            "alert": alert,
            "action": action,
            "last_delivered": last_delivered,
        }
        write_log(entry)
        metros.append(entry)

    # Top-3 under-performers (lowest rate among metros with leads)
    candidates = [m for m in metros if m["total_leads"] > 0 and m["delivered"] > 0]
    candidates.sort(key=lambda m: m["rate"])
    bottom = candidates[:3]

    if bottom:
        rec = {
            "ts": ts,
            "type": "recommendation",
            "top_underperformers": [
                {
                    "metro": m["metro"],
                    "rate": m["rate"],
                    "delivered": m["delivered"],
                    "total": m["total_leads"],
                    "suggested_action": "rotate_to_higher_rate_lane",
                }
                for m in bottom
            ],
        }
        write_log(rec)
        print(
            "lead_rotator metros={} alerts={} bottom3={}".format(
                len(metros), sum(1 for m in metros if m["alert"]), [m["metro"] for m in bottom]
            )
        )
    else:
        print("lead_rotator metros={} no_underperformers".format(len(metros)))

    sys.exit(0)


if __name__ == "__main__":
    main()