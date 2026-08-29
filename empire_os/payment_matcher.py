#!/usr/bin/env python3
"""payment_matcher.py — close the USDT(BSC) pay loop.

Detects individual USDT Transfer events to the Trust Wallet vault via
eth_getLogs (urllib, no web3 — mirrors bsc_listener.py), then matches the
amount to the oldest pending si_subscription seat (BSC USDT transfers carry
no on-chain memo, so we match by amount), activates it, and fires a
fulfillment email via Brevo. Unmatched deposits land in si_unmatched_deposits.

Run:
  payment_matcher.py            # one pass (for cron/manual)
  payment_matcher.py --daemon   # loop every 60s
"""
import os, sys, json, time, sqlite3, logging, argparse
from urllib.request import Request, urlopen

# ---- env ----
def _load_env(p):
    try:
        for ln in open(p):
            ln = ln.strip()
            if ln and "=" in ln and not ln.startswith("#"):
                k, v = ln.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    except FileNotFoundError:
        pass

_load_env("/root/empire_os/.env")
_load_env("/root/empire_secrets/llm.env")
for nm, envk in (("bsc_wallet_address", "BSC_WALLET_ADDRESS"),
                 ("bsc_usdt_contract", "BSC_USDT_CONTRACT")):
    sp = f"/root/empire_secrets/{nm}"
    if os.path.exists(sp) and not os.environ.get(envk):
        os.environ[envk] = open(sp).read().strip()

sys.path.insert(0, "/root/empire_os")
from empire_os import mail_sender as ms

DB = "/root/empire_os/empire_os.db"
VAULT = os.environ.get("BSC_WALLET_ADDRESS", "0x1339b487046B0ad924a10c20b1791608EA8595a8")
USDT = os.environ.get("BSC_USDT_CONTRACT", "0x55d398326f99059fF775485246999027B3197955")
RPC_ENDPOINTS = [
    "https://bsc-dataseed.binance.org",
    "https://bsc-dataseed1.binance.org",
    "https://bsc-dataseed2.binance.org",
]
TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
POLL_INTERVAL = 60

logging.basicConfig(level=logging.INFO, format="%(asctime)s [matcher] %(message)s")
log = logging.getLogger("matcher")


def _rpc(method, params, rpc_idx=0):
    rpc = RPC_ENDPOINTS[rpc_idx % len(RPC_ENDPOINTS)]
    payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    req = Request(rpc, data=payload, headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=12) as r:
        return json.loads(r.read())


def pad_addr(addr: str) -> str:
    return "0x000000000000000000000000" + addr[2:].lower()


def get_transfer_logs(from_block: int, to_block: str = "latest") -> list:
    """USDT Transfer events TO the vault within [from_block, to_block]."""
    params = [{
        "address": USDT,
        "topics": [TRANSFER_TOPIC, None, pad_addr(VAULT)],
        "fromBlock": hex(from_block),
        "toBlock": to_block,
    }]
    for i in range(len(RPC_ENDPOINTS)):
        try:
            res = _rpc("eth_getLogs", params, i)
            if "result" in res:
                return res["result"]
        except Exception as e:
            log.warning(f"eth_getLogs via rpc{i} failed: {e}")
    return []


def decode_transfer(log_entry: dict) -> dict:
    topics = log_entry.get("topics", [])
    from_addr = "0x" + topics[1][26:]
    to_addr = "0x" + topics[2][26:]
    amount = int(log_entry.get("data", "0x0"), 16) / 1e18
    return {
        "tx": log_entry.get("transactionHash"),
        "from": from_addr,
        "to": to_addr,
        "amount": round(amount, 6),
        "block": int(log_entry.get("blockNumber", "0x0"), 16),
    }


def conn():
    import time as _t
    for _ in range(5):
        try:
            c = sqlite3.connect(DB, timeout=30)
            c.row_factory = sqlite3.Row
            c.execute("PRAGMA busy_timeout=30000")
            c.execute("PRAGMA journal_mode=WAL")
            return c
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower():
                _t.sleep(0.5)
                continue
            raise
    raise sqlite3.OperationalError("db locked after retries")


def ensure_tables(c):
    c.executescript("""
        CREATE TABLE IF NOT EXISTS matcher_state (
            k TEXT PRIMARY KEY, v TEXT);
        CREATE TABLE IF NOT EXISTS matcher_seen_tx (
            tx TEXT PRIMARY KEY, amount REAL, from_addr TEXT, block INTEGER, seen_at TEXT);
        CREATE TABLE IF NOT EXISTS expected_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            amount_usd REAL, email TEXT, tenant_id TEXT, ref TEXT,
            status TEXT DEFAULT 'pending', created_at TEXT, matched_tx TEXT);
        CREATE TABLE IF NOT EXISTS si_unmatched_deposits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tx TEXT, from_addr TEXT, amount REAL, block INTEGER,
            reason TEXT, seen_at TEXT);
    """)
    c.commit()


def get_last_block(c) -> int:
    row = c.execute("SELECT v FROM matcher_state WHERE k='last_block'").fetchone()
    if row:
        return int(row["v"])
    # first run: start from a recent window (Binance RPC rejects huge ranges)
    return max(0, _current_block() - 5000)


def set_last_block(c, blk):
    c.execute("INSERT OR REPLACE INTO matcher_state (k, v) VALUES ('last_block', ?)", (str(blk),))
    c.commit()


def fulfill_email(email: str, amount: float, tenant_id: str):
    """Send seat-activated fulfillment email via Brevo."""
    subject = "Empire OS — your seat is ACTIVE"
    body = (
        f"Hi,<br><br>Payment received: <b>{amount:.2f} USDT (BSC)</b>.<br>"
        f"Your Empire OS buyer seat is now <b>active</b>.<br><br>"
        f"Access your leads dashboard and start pulling exclusive leads in your lane.<br>"
        f"<a href='https://empire-ai.co.uk/v1/buyer/login'>Open Empire OS</a><br><br>"
        f"Empire AI — empire-ai.co.uk"
    )
    try:
        res = ms._brevo_api_send(email, subject, body)
        if isinstance(res, dict) and res.get("ok"):
            log.info(f"fulfill email sent -> {email} (tenant {tenant_id})")
            return True
        log.warning(f"fulfill email FAILED -> {email}: {res}")
    except Exception as e:
        log.warning(f"fulfill email error -> {email}: {e}")
    return False


def match_and_fulfill(c, tx: str, amount: float, from_addr: str, block: int):
    if c.execute("SELECT 1 FROM matcher_seen_tx WHERE tx=?", (tx,)).fetchone():
        return  # already processed
    c.execute("INSERT INTO matcher_seen_tx (tx, amount, from_addr, block, seen_at) VALUES (?,?,?,?,datetime('now'))",
              (tx, amount, from_addr, block))

    # match oldest pending si_subscription by amount (no on-chain memo on BSC USDT)
    seat = c.execute(
        "SELECT s.tenant_id, t.email, s.price_cents FROM si_subscription s "
        "JOIN si_tenant t ON t.tenant_id=s.tenant_id "
        "WHERE s.status='awaiting_payment' AND abs(s.price_cents/100.0 - ?) < 0.01 "
        "AND t.email IS NOT NULL AND t.email!='' "
        "ORDER BY s.created_at ASC LIMIT 1", (amount,)).fetchone()

    if seat:
        c.execute("UPDATE si_subscription SET status='active', updated_at=datetime('now') WHERE tenant_id=?",
                  (seat["tenant_id"],))
        c.execute("INSERT INTO expected_payments (amount_usd, email, tenant_id, status, matched_tx, created_at) "
                  "VALUES (?,?,?,'paid',?,datetime('now'))",
                  (amount, seat["email"], seat["tenant_id"], tx))
        c.commit()
        log.info(f"MATCHED {amount} USDT -> tenant {seat['tenant_id']} ({seat['email']}) tx {tx}")
        fulfill_email(seat["email"], amount, seat["tenant_id"])
    else:
        c.execute("INSERT INTO si_unmatched_deposits (tx, from_addr, amount, block, reason, seen_at) "
                  "VALUES (?,?,?,?,'no pending seat for amount',datetime('now'))",
                  (tx, from_addr, amount, block))
        c.commit()
        log.warning(f"UNMATCHED {amount} USDT from {from_addr} tx {tx} — logged for review")
    c.commit()


def run_once():
    c = conn()
    ensure_tables(c)
    last = get_last_block(c)
    logs = get_transfer_logs(last + 1)
    if not logs:
        set_last_block(c, max(last, _current_block()))
        c.close()
        return
    newest = last
    for entry in logs:
        tx = entry.get("transactionHash")
        try:
            d = decode_transfer(entry)
        except Exception as e:
            log.warning(f"decode fail {tx}: {e}")
            continue
        match_and_fulfill(c, d["tx"], d["amount"], d["from"], d["block"])
        newest = max(newest, d["block"])
    set_last_block(c, newest)
    c.close()
    log.info(f"scan complete: {len(logs)} transfer(s), tip={newest}")


def _current_block():
    for i in range(len(RPC_ENDPOINTS)):
        try:
            res = _rpc("eth_blockNumber", [], i)
            if "result" in res:
                return int(res["result"], 16)
        except Exception:
            pass
    return 30_000_000


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--daemon", action="store_true")
    a = ap.parse_args()
    if a.daemon:
        log.info("payment_matcher daemon start")
        while True:
            try:
                run_once()
            except Exception as e:
                log.warning(f"cycle error: {e}")
            time.sleep(POLL_INTERVAL)
    else:
        run_once()


if __name__ == "__main__":
    main()
