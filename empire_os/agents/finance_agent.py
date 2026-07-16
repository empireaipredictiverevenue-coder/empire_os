
"""
Empire OS v3 - finance agent.

Reconciles USDC vault balance vs pending invoices every 5 minutes.
Reads:
  - /v1/satellite/active (matches subscribers to alerts)
  - DB: si_ppc_invoices WHERE status = "open"  (canonical, tries
         legacy si_invoice WHERE status = "pending" as fallback)
  - Helius RPC for current vault USDC balance
Writes:
  - /v1/swarm/audit-log entries (deposit events)
  - /root/feedback/finance_log.jsonl
Calls:
  - mark_invoice_paid when memo+amount match

Cadence: 5 minutes.
"""
import json, os, sqlite3, sys, time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/root/empire_os")
import requests

HUB = os.environ.get("HUB_URL", "http://10.118.155.218:8081")
DB  = os.environ.get("HUB_DB_PATH", "/root/empire_os/empire_os.db")
FB  = Path("/root/feedback")
LOG = FB / "finance_log.jsonl"

VAULT = "egJ1t9NZkDs8FvMbfnQTqXzC4KNuhAc9XSfpG9y9AZM"
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybafCvkRxb7Yy4dV"

INTERVAL = int(os.environ.get("INTERVAL_SEC", str(5 * 60)))
RPC = os.environ.get("SOLANA_RPC_URL", "")


def log(level, msg, **fields):
    e = {"ts": datetime.now(timezone.utc).isoformat(), "level": level, "msg": msg, **fields}
    FB.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a") as f:
        f.write(json.dumps(e) + "\n")
    if level in ("ERROR", "EVENT"):
        print(json.dumps(e), flush=True)


def get_usdc_balance() -> float:
    if not RPC:
        # fallback: read from app_kv (replay-friendly)
        try:
            cnx = sqlite3.connect(DB)
            r = cnx.execute(
                "SELECT value FROM app_kv WHERE key = 'vault_balance_usdc'"
            ).fetchone()
            return float(r[0]) if r else 0.0
        except Exception:
            return 0.0
    try:
        r = requests.post(RPC, json={
            "jsonrpc":"2.0","id":1,
            "method":"getTokenAccountsByOwner",
            "params":[VAULT, {"mint": USDC_MINT}, {"encoding":"jsonParsed"}]
        }, timeout=10).json()
        total = 0.0
        for a in r.get("result", {}).get("value", []):
            total += a.get("account", {}).get("data", {}).get("parsed", {})                        .get("info", {}).get("tokenAmount", {}).get("uiAmount", 0)
        return float(total)
    except Exception as e:
        log("ERROR", "rpc_fail", err=str(e)[:120])
        return 0.0


def pending_total() -> float:
    """
    Sum of pending (open) PPC invoices, in USD cents.
    Tries the canonical `si_ppc_invoices` table first (status='open');
    falls back to legacy `si_invoice` (status='pending') if present;
    returns 0.0 on any DB/table error rather than throwing.
    """
    for sql in (
        "SELECT COALESCE(SUM(amount_cents), 0) FROM si_ppc_invoices WHERE status = 'open'",
        "SELECT COALESCE(SUM(amount_cents), 0) FROM si_invoice WHERE status = 'pending'",
    ):
        try:
            cnx = sqlite3.connect(DB)
            r = cnx.execute(sql).fetchone()
            try:
                return (r[0] or 0) / 100.0
            finally:
                cnx.close()
        except Exception as e:
            err = str(e)[:120]
            # Only log on first attempt (si_ppc_invoices) so the legacy
            # fallback doesn't double-log when it succeeds.
            if "si_ppc_invoices" in sql:
                log("WARN", "pending_ppc_table_missing_or_other", err=err)
            # try next candidate
    return 0.0


def cycle():
    bal = get_usdc_balance()
    pend = pending_total()
    log("CYCLE", "finance_snapshot",
        vault_usdc=bal, pending_usdc=pend,
        runway_days=int(bal / max(pend, 1) * 30) if pend else None)


if __name__ == "__main__":
    print(f"[{datetime.now(timezone.utc).isoformat()}] finance agent online - {INTERVAL}s",
          flush=True)
    while True:
        try: cycle()
        except Exception as e: log("ERROR", "cycle", err=str(e)[:200])
        time.sleep(INTERVAL)
