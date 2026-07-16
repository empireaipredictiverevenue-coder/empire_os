"""
Empire OS v3 — Solana USDC Payment Listener

Polls Helius for USDC transfers into the vault wallet, matches each
transfer to a pending si_invoice, and auto-marks the invoice as paid.

Matching rules (in priority order):
  1. Memo field contains "INV_<invoice_id>" — exact match
  2. Memo field contains "<invoice_id>" substring
  3. Amount matches a pending invoice exactly (USDC 6 decimals)

Each match logs to /root/feedback/solana_payments.jsonl with:
  - tx_signature
  - invoice_id
  - amount_usdc
  - amount_cents
  - from_address
  - matched_at
  - matched_rule
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

LOG_PATH = Path("/root/feedback/solana_payments.jsonl")
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

ENV_PATH = Path("/root/empire_os/.env")

USDC_MINT_MAINNET = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"

# Polling interval
POLL_INTERVAL = 30  # seconds
# How long back to scan on first run (Unix timestamp)
INITIAL_LOOKBACK_SECONDS = 7 * 24 * 3600  # 7 days
# Don't reprocess transactions older than this
MAX_TX_AGE_SECONDS = 14 * 24 * 3600  # 14 days


def load_env():
    """Load .env into a dict. Never logs the values."""
    env = {}
    if not ENV_PATH.exists():
        raise RuntimeError("Missing %s — run scripts/write_env.py first" % ENV_PATH)
    for line in ENV_PATH.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, val = line.split("=", 1)
        env[key.strip()] = val.strip()
    return env


def rpc_call(env: dict, method: str, params: list) -> dict:
    """Call Helius JSON-RPC."""
    url = env["SOLANA_RPC_URL"]
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())


def get_recent_signatures(env: dict, vault: str, limit: int = 20) -> list:
    """Get recent transaction signatures for the vault wallet."""
    resp = rpc_call(env, "getSignaturesForAddress",
                    [vault, {"limit": limit}])
    return resp.get("result", [])


def get_transaction(env: dict, signature: str) -> dict:
    """Fetch the full parsed transaction by signature."""
    resp = rpc_call(env, "getTransaction",
                    [signature, {"encoding": "jsonParsed",
                                  "maxSupportedTransactionVersion": 0}])
    return resp.get("result", {})


def is_usdc_transfer(tx: dict, env: dict) -> tuple[bool, int, str]:
    """Detect if a tx is a USDC transfer TO the vault.

    Returns (is_usdc, amount_usdc_micro, from_address).
    USDC has 6 decimals, so 1 USDC = 1,000,000 micro-units.
    """
    if not tx:
        return False, 0, ""
    vault = env["SOLANA_VAULT_WALLET"]
    mint = env.get("USDC_MINT", USDC_MINT_MAINNET)

    meta = tx.get("meta") or {}
    if meta.get("err"):
        return False, 0, ""

    # Walk through SPL token balance changes
    pre = (meta.get("preTokenBalances") or [])
    post = (meta.get("postTokenBalances") or [])

    for p in post:
        if p.get("mint") != mint:
            continue
        owner = p.get("owner", "")
        if owner != vault:
            continue
        # Find the matching pre balance
        amount = float(p.get("uiTokenAmount", {}).get("amount", 0))
        for pre_b in pre:
            if (pre_b.get("accountIndex") == p.get("accountIndex")
                    and pre_b.get("mint") == mint
                    and pre_b.get("owner") == vault):
                pre_amount = float(pre_b.get("uiTokenAmount", {}).get("amount", 0))
                diff = amount - pre_amount
                if diff > 0:
                    # Find the sender from inner instructions
                    from_addr = _find_sender(tx, p.get("accountIndex"))
                    return True, int(diff), from_addr
    return False, 0, ""


def _find_sender(tx: dict, vault_account_index: int) -> str:
    """Find the address that sent the USDC (best effort)."""
    instructions = tx.get("transaction", {}).get("message", {}).get("instructions", [])
    keys = tx.get("transaction", {}).get("message", {}).get("accountKeys", [])
    for ins in instructions:
        if "parsed" in ins:
            info = ins.get("parsed", {}).get("info", {})
            src = info.get("source", "")
            if src and src != "system":
                return src
    # Fallback: accountKeys[0] is usually the fee payer
    if keys:
        return keys[0].get("pubkey", "") if isinstance(keys[0], dict) else str(keys[0])
    return ""


def get_memo(tx: dict) -> str:
    """Extract memo instruction text if present."""
    instructions = tx.get("transaction", {}).get("message", {}).get("instructions", [])
    for ins in instructions:
        parsed = ins.get("parsed", {})
        if parsed.get("type") == "memo":
            return parsed.get("info", {}).get("memo", "") or ""
    return ""


def find_invoice_for_amount(amount_micro: int, env: dict) -> dict | None:
    """Find a pending invoice matching this amount (in USDC micro-units)."""
    # amount_micro is the USDC amount * 1e6
    # si_invoice stores amount_cents where $1 = 100 cents
    # So cents = usdc * 100 (since 1 USDC = $1)
    expected_cents = amount_micro // 10000  # 1_000_000 micro-USDC = $1 = 100 cents

    script = (
        "import sqlite3, json, sys\n"
        "c = sqlite3.connect('/root/empire_os/empire_os.db')\n"
        "c.row_factory = sqlite3.Row\n"
        "cur = c.execute('SELECT invoice_id, tenant_id, subscription_id, "
        "amount_cents, status, created_at FROM si_invoice "
        "WHERE status=\"pending\" AND amount_cents = ? "
        "ORDER BY created_at ASC LIMIT 1', (sys.argv[1],))\n"
        "row = cur.fetchone()\n"
        "c.close()\n"
        "if row:\n"
        "    print(json.dumps(dict(row), default=str))\n"
        "else:\n"
        "    print('NONE')\n"
    )
    try:
        r = subprocess.run(
            ["incus", "exec", "empire-hub", "--",
             "/root/venv/bin/python3", "-c", script, str(expected_cents)],
            capture_output=True, text=True, timeout=15
        )
        out = r.stdout.strip().split("\n")[-1]
        if out == "NONE" or not out:
            return None
        return json.loads(out)
    except Exception as e:
        log_event("ERROR", "find_invoice_for_amount failed: %s" % e)
        return None


def find_invoice_by_memo(memo: str, env: dict) -> dict | None:
    """Match a memo containing 'INV_<id>' against a pending invoice."""
    if not memo:
        return None
    # Look for INV_xxxx pattern
    m = re.search(r"INV_([a-f0-9]+)", memo)
    if m:
        invoice_id = "inv_" + m.group(1)
        script = (
            "import sqlite3, json, sys\n"
            "c = sqlite3.connect('/root/empire_os/empire_os.db')\n"
            "c.row_factory = sqlite3.Row\n"
            "cur = c.execute('SELECT invoice_id, tenant_id, subscription_id, "
            "amount_cents, status FROM si_invoice WHERE invoice_id=?', (sys.argv[1],))\n"
            "row = cur.fetchone()\n"
            "c.close()\n"
            "if row:\n"
            "    print(json.dumps(dict(row), default=str))\n"
            "else:\n"
            "    print('NONE')\n"
        )
        try:
            r = subprocess.run(
                ["incus", "exec", "empire-hub", "--",
                 "/root/venv/bin/python3", "-c", script, invoice_id],
                capture_output=True, text=True, timeout=15
            )
            out = r.stdout.strip().split("\n")[-1]
            if out == "NONE" or not out:
                return None
            return json.loads(out)
        except Exception:
            return None
    return None


def mark_invoice_paid(invoice_id: str, reference: str) -> bool:
    """Mark an invoice as paid via the marketplace module."""
    script = (
        "import sys\n"
        "sys.path.insert(0, '/root/empire_os')\n"
        "from empire_os.marketplace import mark_invoice_paid\n"
        "print('OK' if mark_invoice_paid(sys.argv[1], sys.argv[2]) else 'FAIL')\n"
    )
    r = subprocess.run(
        ["incus", "exec", "empire-hub", "--",
         "/root/venv/bin/python3", "-c", script,
         invoice_id, reference],
        capture_output=True, text=True, timeout=15
    )
    out = r.stdout.strip()
    return out == "OK"


def log_event(level: str, msg: str, **extra):
    """Append a structured event to the log."""
    event = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "msg": msg,
    }
    event.update(extra)
    with LOG_PATH.open("a") as f:
        f.write(json.dumps(event, default=str) + "\n")
    if level in ("ERROR", "WARN", "MATCH"):
        print(f"[{level}] {msg} {extra if extra else ''}")


def load_processed_sigs() -> set:
    """Return the set of tx signatures already processed."""
    if not LOG_PATH.exists():
        return set()
    sigs = set()
    for line in LOG_PATH.read_text().splitlines():
        if not line.strip():
            continue
        try:
            d = json.loads(line)
            sig = d.get("signature")
            if sig:
                sigs.add(sig)
        except Exception:
            continue
    return sigs


def poll_once(env: dict, processed: set, lookback_seconds: int = 3600) -> set:
    """One polling pass. Returns updated processed set."""
    vault = env["SOLANA_VAULT_WALLET"]
    sigs = get_recent_signatures(env, vault, limit=30)
    now_ts = int(time.time())

    for sig_info in sigs:
        sig = sig_info.get("signature")
        if not sig or sig in processed:
            continue
        block_time = sig_info.get("blockTime", 0)
        if block_time and (now_ts - block_time) > MAX_TX_AGE_SECONDS:
            continue

        try:
            tx = get_transaction(env, sig)
        except Exception as e:
            log_event("WARN", "getTransaction failed", signature=sig[:16] + "...",
                      error=str(e)[:100])
            continue

        is_usdc, amount_micro, from_addr = is_usdc_transfer(tx, env)
        if not is_usdc:
            log_event("SKIP", "not a USDC transfer", signature=sig[:16] + "...",
                      block_time=block_time)
            processed.add(sig)
            continue

        memo = get_memo(tx)
        amount_usdc = amount_micro / 1_000_000

        # Try memo match first
        invoice = find_invoice_by_memo(memo, env)
        rule = "memo" if invoice else None

        # Fall back to amount match
        if not invoice:
            invoice = find_invoice_for_amount(amount_micro, env)
            rule = "amount"

        if not invoice:
            log_event("UNMATCHED", "no matching invoice",
                      signature=sig, amount_usdc=amount_usdc,
                      memo=memo, from_addr=from_addr)
            processed.add(sig)
            continue

        # Mark invoice as paid
        ok = mark_invoice_paid(invoice["invoice_id"], sig)
        if ok:
            log_event("MATCH", "invoice paid",
                      signature=sig, invoice_id=invoice["invoice_id"],
                      amount_usdc=amount_usdc, amount_cents=invoice["amount_cents"],
                      from_addr=from_addr, rule=rule, memo=memo)
        else:
            log_event("ERROR", "mark_invoice_paid failed",
                      signature=sig, invoice_id=invoice["invoice_id"])

        processed.add(sig)

    return processed


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--once", action="store_true",
                   help="Run one poll cycle and exit")
    p.add_argument("--interval", type=int, default=POLL_INTERVAL,
                   help="Polling interval in seconds")
    p.add_argument("--lookback", type=int, default=INITIAL_LOOKBACK_SECONDS,
                   help="Initial lookback window (seconds)")
    p.add_argument("--dry-run", action="store_true",
                   help="Detect matches but don't mark invoices paid")
    args = p.parse_args()

    env = load_env()
    required = ["SOLANA_VAULT_WALLET", "SOLANA_RPC_URL", "USDC_MINT"]
    for k in required:
        if k not in env:
            print("Missing %s in .env" % k, file=sys.stderr)
            sys.exit(1)

    log_event("INFO", "listener started",
              vault=env["SOLANA_VAULT_WALLET"][:8] + "...",
              mint=env["USDC_MINT"][:8] + "...",
              interval_s=args.interval,
              dry_run=args.dry_run)

    processed = load_processed_sigs()
    log_event("INFO", "loaded %d processed signatures" % len(processed))

    while True:
        try:
            processed = poll_once(env, processed, args.lookback)
        except KeyboardInterrupt:
            log_event("INFO", "interrupted, shutting down")
            break
        except Exception as e:
            log_event("ERROR", "poll error: %s" % e)
        if args.once:
            break
        time.sleep(args.interval)


if __name__ == "__main__":
    main()