#!/usr/bin/env python3
"""
Settlement Gateway Daemon — Empire OS v3

Watches the Empire USDT vault (0xe646cb6a2befc6fd88f418e7e19a32abe4aed7fb)
for new incoming SPL token transfers and reconciles them against awaiting
invoices, subscriptions, leads, and A2A escrow rows.

The existing `empire_os/agents/solana_listener_agent.py` polls ATA balance
delta every 30s and routes through /v1/finance/replay. This daemon is the
*tx-level* complement:

  - polls getSignaturesForAddress(vault, {limit:50}) every 60s
  - per new signature, fetches the parsed transaction
  - extracts incoming USDT amount (SPL Token transferChecked pre→vault)
  - extracts on-chain memo (SPL Memo program)
  - posts to hub /v1/finance/replay — hub already handles:
      * SEAT_<sub_id>            -> si_subscription awaiting_payment -> active
      * INV_<invoice_id>         -> si_ppc_invoices / si_invoice -> paid
      * LANE_<lane_id>           -> lane occupation
      * SKU_<sku>                -> product subscription
      * LEAD_<lead_id>           -> si_funnel_event -> settled + si_settlements
      * EVAL_<buyer>__<lead_ref> -> evaluation_settlements
      * EVALBUY_<buyer>_<pack>   -> credit pack activation
      * no-memo (Trust/TokenPocket) -> buyer activation by amount match
  - maintains a persistent `seen_signatures` cache so retried posts never
    double-fire (defence-in-depth on top of the hub's own dedup)

Idempotent. Always sys.exit(0) on success. Short timeouts (RPC slow at peak).
Logs every cycle to /root/empire_os/feedback/settlement_gateway.jsonl.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# ── Config (env-overridable, sane defaults) ──────────────────────────
# BSC mainnet RPC — default to Binance seed node (public, rate-limited).
# Override with BSC_RPC env var for your own endpoint.
RPC      = os.environ.get("BSC_RPC", "https://bsc-dataseed.binance.org/").strip()
VAULT    = os.environ.get("BSC_WALLET_ADDRESS", "0xe646cb6a2befc6fd88f418e7e19a32abe4aed7fb").strip()
BSC_USDT_CONTRACT= os.environ.get("BSC_USDT_CONTRACT", "EPjFWdd5AufqSSqeM2qN1xzybafC8G4wEGGkZwyTDt1v").strip()
HUB_URL  = os.environ.get("HUB_URL", "http://127.0.0.1:8080").strip()
INTERVAL = int(os.environ.get("INTERVAL_SEC", "60"))
SIG_LIMIT= int(os.environ.get("SIG_LIMIT", "50"))

LOG_DIR  = Path("/root/empire_os/feedback")
LOG_FILE = LOG_DIR / "settlement_gateway.jsonl"
SEEN_FILE= LOG_DIR / "settlement_gateway_seen.jsonl"
RPC_TMO  = float(os.environ.get("RPC_TIMEOUT", "10"))
HUB_TMO  = float(os.environ.get("HUB_TIMEOUT", "6"))

# SPL constants
TOKEN_PROGRAM = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
MEMO_PROGRAM  = "MemoSq4gqABAXKb96qnH8TysB5mtg3MFrjGZRiTtEf"
SPL_MEMO      = "spl-memo"
USDC_DECIMALS = 6

# Lightweight DB path (for seens + audit, not blocking)
DB = "/root/empire_os/empire_os.db"

LOG_DIR.mkdir(parents=True, exist_ok=True)


def log(level: str, msg: str, **fields) -> None:
    e = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "msg": msg,
        **fields,
    }
    line = json.dumps(e, separators=(",", ":"))
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")
    print(line, flush=True)


def _rpc(method: str, params: list) -> dict:
    """Single-shot JSON-RPC. Short timeout. Returns {result|error}."""
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method,
                       "params": params}).encode()
    req = urllib.request.Request(
        RPC, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=RPC_TMO) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return {"error": f"http {e.code}",
                "body": e.read().decode(errors="replace")[:200]}
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"[:200]}


def _post_hub(path: str, body: dict) -> dict:
    """POST to hub. Returns dict (ok=True on 2xx) or {ok:False, error:..}."""
    try:
        req = urllib.request.Request(
            f"{HUB_URL}{path}",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
            method="POST")
        with urllib.request.urlopen(req, timeout=HUB_TMO) as r:
            raw = r.read().decode(errors="replace")
            try:
                parsed = json.loads(raw) if raw else {}
            except Exception:
                parsed = {"raw": raw[:200]}
            if not isinstance(parsed, dict):
                parsed = {"raw": str(parsed)[:200]}
            parsed.setdefault("ok", True)
            parsed["status"] = r.status
            return parsed
    except urllib.error.HTTPError as e:
        return {"ok": False, "status": e.code,
                "error": "http_error",
                "body": e.read().decode(errors="replace")[:200]}
    except Exception as e:
        return {"ok": False,
                "error": f"{type(e).__name__}: {e}"[:200]}


# ── Seen cache (file-backed, then DB-backed) ─────────────────────────

def load_seen() -> set:
    s = set()
    if SEEN_FILE.exists():
        for line in SEEN_FILE.read_text().splitlines():
            line = line.strip()
            if line:
                try:
                    s.add(json.loads(line).get("sig", ""))
                except Exception:
                    # legacy plain text
                    s.add(line)
    return {x for x in s if x}


def append_seen(sig: str) -> None:
    with open(SEEN_FILE, "a") as f:
        f.write(json.dumps({"sig": sig,
                            "ts": datetime.now(timezone.utc).isoformat()})
                + "\n")


# ── On-chain parsing ─────────────────────────────────────────────────

def fetch_signatures() -> list[dict]:
    r = _rpc("getSignaturesForAddress",
             [VAULT, {"limit": SIG_LIMIT, "commitment": "finalized"}])
    if "error" in r:
        log("WARN", "sig_fetch_fail", err=r["error"])
        return []
    return [s for s in (r.get("result") or []) if s.get("signature")]


def fetch_tx(sig: str) -> dict | None:
    r = _rpc("getTransaction", [sig, {
        "encoding": "jsonParsed",
        "commitment": "finalized",
        "maxSupportedTransactionVersion": 0}])
    if "error" in r or not r.get("result"):
        return None
    return r["result"]


def _extract_memo(tx: dict) -> str:
    """Best-effort memo extraction from jsonParsed instructions.

    Two on-chain encodings:
      a) SPL Memo program instructions with `parsed: {memo: <str>}` or `data: <b64/str>`.
      b) Helius-style "parsed" memo on inner instructions.
    Returns '' if no memo found.
    """
    if not tx:
        return ""
    msg = tx.get("transaction", {}).get("message", {}) or {}
    for ix in (msg.get("instructions") or []):
        parsed = ix.get("parsed")
        if isinstance(parsed, dict):
            if "memo" in parsed:
                return str(parsed["memo"]).strip()
        if ix.get("programId") == MEMO_PROGRAM:
            data = ix.get("data")
            if isinstance(data, str):
                return data.strip()
    # Also scan inner instructions (some wallets add the memo as inner)
    meta = tx.get("meta") or {}
    for inner in (meta.get("innerInstructions") or []):
        for ix in (inner.get("instructions") or []):
            parsed = ix.get("parsed")
            if isinstance(parsed, dict) and "memo" in parsed:
                return str(parsed["memo"]).strip()
            if ix.get("program") == SPL_MEMO or ix.get("programId") == MEMO_PROGRAM:
                d = ix.get("data")
                if isinstance(d, str):
                    return d.strip()
    return ""


def _extract_incoming_usdc(tx: dict) -> float:
    """Find a transferChecked (or transfer) into VAULT of BSC_USDT_CONTRACT.

    Returns the USDT amount in dollars (float), or 0.0 if none.
    """
    if not tx:
        return 0.0
    msg = tx.get("transaction", {}).get("message", {}) or {}
    accounts = msg.get("accountKeys") or []
    meta     = tx.get("meta") or {}
    pre_bal  = meta.get("preTokenBalances") or []
    post_bal = meta.get("postTokenBalances") or []

    # Build (account_index, mint, uiAmount_before, uiAmount_after) by mint+owner
    def by_ata(mint, owner):
        before = 0.0
        after  = 0.0
        for b in pre_bal:
            if b.get("mint") == mint and b.get("owner") == owner:
                amt = (b.get("uiTokenAmount") or {}).get("uiAmount") or 0
                before = float(amt or 0)
        for a in post_bal:
            if a.get("mint") == mint and a.get("owner") == owner:
                amt = (a.get("uiTokenAmount") or {}).get("uiTokenAmount") or \
                      (a.get("uiTokenAmount") or {}).get("uiAmount") or 0
                after = float(amt or 0)
        return before, after

    # Easier: pull any post balance with mint==USDT and account owned by VAULT
    for a in post_bal:
        if a.get("mint") != BSC_USDT_CONTRACT:
            continue
        owner = a.get("owner")
        if owner and owner != VAULT:
            continue
        idx = a.get("accountIndex")
        # find matching pre
        pre_amt = 0.0
        for b in pre_bal:
            if b.get("accountIndex") == idx and b.get("mint") == BSC_USDT_CONTRACT:
                pre_amt = float(
                    (b.get("uiTokenAmount") or {}).get("uiAmount") or 0)
                break
        post_amt = float(
            (a.get("uiTokenAmount") or {}).get("uiAmount")
            or (a.get("uiTokenAmount") or {}).get("uiTokenAmount") or 0)
        delta = post_amt - pre_amt
        if delta > 0:
            return round(delta, USDC_DECIMALS)
    return 0.0


def _first_signer(tx: dict) -> str:
    """Best-effort 'wallet_from' = first non-vault signer."""
    keys = (tx.get("transaction", {}).get("message", {}) or {}).get(
        "accountKeys") or []
    for k in keys:
        pubkey = k.get("pubkey") if isinstance(k, dict) else k
        if pubkey and pubkey != VAULT:
            return pubkey
    return ""


# ── One cycle ────────────────────────────────────────────────────────

def process_one(sig: str) -> dict:
    """Process a single new signature. Returns result dict."""
    tx = fetch_tx(sig)
    if not tx:
        return {"ok": False, "sig": sig, "error": "tx_not_found"}

    # Skip failed txs
    if (tx.get("meta") or {}).get("err"):
        return {"ok": False, "sig": sig, "skipped": "tx_errored"}

    amount_usdc = _extract_incoming_usdc(tx)
    if amount_usdc <= 0:
        # Not an incoming USDT transfer (could be SOL, or outbound, or dust)
        return {"ok": False, "sig": sig, "skipped": "not_inbound_usdc"}

    memo = _extract_memo(tx)
    wallet_from = _first_signer(tx)

    body = {
        "amount_usdc": amount_usdc,
        "memo": memo,
        "wallet_from": wallet_from,
        "tx_signature": sig,
        "force_status": "paid",
        "note": "settlement_gateway_daemon: getSignaturesForAddress watcher",
    }
    res = _post_hub("/v1/finance/replay", body)
    return {
        "ok": bool(res.get("ok")),
        "sig": sig,
        "amount_usdc": amount_usdc,
        "memo": memo,
        "wallet_from": wallet_from,
        "matched_to": res.get("matched_to"),
        "paid_invoice_id": res.get("paid_invoice_id"),
        "paid_subscription_id": res.get("paid_subscription_id"),
        "hub_status": res.get("status") or res.get("error"),
    }


def cycle() -> dict:
    """One poll cycle. Returns cycle summary."""
    sigs = fetch_signatures()
    if not sigs:
        return {"ok": True, "sigs_seen": 0, "sigs_new": 0, "settlements": 0}
    seen = load_seen()
    new = [s for s in sigs if s.get("signature") not in seen]
    if not new:
        return {"ok": True, "sigs_seen": len(sigs), "sigs_new": 0,
                "settlements": 0}

    log("INFO", "cycle_start", sigs_seen=len(sigs), sigs_new=len(new))

    settlements = 0
    for s in new:
        sig = s["signature"]
        try:
            r = process_one(sig)
        except Exception as e:
            r = {"ok": False, "sig": sig,
                 "error": f"{type(e).__name__}: {e}"[:200]}
        # Mark seen ONLY if we got any answer (good or hard fail).
        # A transient RPC failure will be retried on the next cycle.
        if "error" not in r or r.get("skipped"):
            append_seen(sig)
        if r.get("ok") and r.get("paid_invoice_id") or r.get("paid_subscription_id"):
            settlements += 1
            log("INFO", "settlement_recorded",
                **r)
        elif r.get("ok") and r.get("matched_to"):
            log("INFO", "settlement_matched", **r)
        elif r.get("skipped"):
            log("DEBUG", "sig_skipped", **r)
        else:
            log("WARN", "settlement_replay_failed", **r)

    return {"ok": True, "sigs_seen": len(sigs), "sigs_new": len(new),
            "settlements": settlements}


def main() -> int:
    log("INFO", "startup",
        rpc=RPC, vault=VAULT, usdc_mint=BSC_USDT_CONTRACT,
        hub=HUB_URL, interval=INTERVAL, sig_limit=SIG_LIMIT)
    # Always exit 0 on graceful shutdown so systemd timer doesn't flap.
    try:
        while True:
            t0 = time.time()
            try:
                summary = cycle()
                log("INFO", "cycle_end", **summary)
            except Exception as e:
                log("ERROR", "cycle_failed",
                    err=f"{type(e).__name__}: {e}"[:200])
            dt = time.time() - t0
            sleep_for = max(1, INTERVAL - int(dt))
            time.sleep(sleep_for)
    except KeyboardInterrupt:
        log("INFO", "shutdown", reason="SIGINT")
    return 0


if __name__ == "__main__":
    sys.exit(main())
