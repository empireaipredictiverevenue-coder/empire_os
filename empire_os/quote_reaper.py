#!/usr/bin/env python3
"""GRIP quote reaper — expire stale a2a_quotes, digest for founder.

Schedule: every 1h via systemd timer. Idempotent, atomic per row.
ALWAYS sys.exit(0).
"""
import sqlite3, os, sys, json
from datetime import datetime, timezone

DB = "/root/empire_os/empire_os.db"
LOG = "/root/empire_os/feedback/grip_quote_reaper.jsonl"
SQLITE_TIMEOUT = 10


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


def json_set_expired(meta_json):
    """Best-effort merge of `$.expired_reason` into a meta JSON string."""
    if not meta_json:
        meta = {}
    else:
        try:
            meta = json.loads(meta_json)
        except Exception:
            meta = {"_raw": meta_json[:200]}
    meta["expired_reason"] = "grip_reaper"
    return json.dumps(meta, separators=(",", ":"))


def main():
    ts = now()
    try:
        c = open_db()
        # 1. find expired-but-not-yet-marked quotes
        candidates = c.execute(
            """
            SELECT quote_id, product, amount_usdc, buyer_wallet, expires_at, meta
            FROM a2a_quotes
            WHERE status IN ('pending','funded') AND expires_at < datetime('now')
            ORDER BY amount_usdc DESC
            """
        ).fetchall()
    except Exception as e:
        write_log({"ts": ts, "error": str(e)[:300]})
        sys.exit(0)

    expired = []
    for quote_id, product, amount_usdc, buyer_wallet, expires_at, meta in candidates:
        new_meta = json_set_expired(meta)
        try:
            c.execute(
                "UPDATE a2a_quotes SET status='expired', meta=? "
                "WHERE quote_id=? AND status IN ('pending','funded')",
                (new_meta, quote_id),
            )
            if c.execute("SELECT changes()").fetchone()[0]:
                expired.append(
                    {
                        "quote_id": quote_id,
                        "product": product,
                        "amount_usdc": amount_usdc,
                        "buyer_wallet": buyer_wallet,
                        "expires_at": expires_at,
                    }
                )
        except Exception as e:
            write_log({"ts": ts, "error": str(e)[:300], "quote_id": quote_id})

    c.commit()
    c.close()

    total_usdc = round(sum(q["amount_usdc"] or 0 for q in expired), 6)
    digest = {
        "ts": ts,
        "expired_count": len(expired),
        "total_usdc": total_usdc,
        "top_quotes": expired[:3],
    }
    write_log(digest)
    print(
        "quote_reaper expired_count={} total_usdc={}".format(digest["expired_count"], total_usdc)
    )
    sys.exit(0)


if __name__ == "__main__":
    main()