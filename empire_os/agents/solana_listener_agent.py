
"""
Empire OS v3 - Solana listener agent.

Polls Helius for incoming transfers to the vault (associated token
account + native SOL) every 30s. On a hit:

  - parses incoming USDC transfer
  - looks for memo instruction (or fallback SEAT_/INV_ pattern in
    description fields)
  - calls /v1/finance/replay on hub with the real sig + amount
    - replay flips matching subscription/invoice to paid
    - we also update local app_kv vault_balance_usdc (replay already
      does this so no separate update needed)

Cadence: 30s.
"""
import json, os, sys, time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/root/empire_os")
import requests

# Import settlement gateway for lead settlement via memo matching
from empire_os.agents.settlement_gateway import process_settlement

# Load .env (same pattern as charge.py) so HUB_URL + keys resolve from
# /root/empire_os/.env at startup. Without this, pm2-launched processes
# fall back to the hardcoded dead default (127.0.0.1:8081) and the
# /v1/finance/replay call silently times out -> USDC never settles.
for _ln in (Path("/root/empire_os/.env").read_text(encoding="utf-8").splitlines()
            if Path("/root/empire_os/.env").exists() else ()):
    _ln = _ln.strip()
    if not _ln or _ln.startswith("#") or "=" not in _ln:
        continue
    _k, _, _v = _ln.partition("=")
    os.environ.setdefault(_k.strip(), _v.strip())

# Sovereign topology: RPC + hub are on our own network. Never route through
# the container's Tor/Privoxy proxy — it breaks Helius RPC and hub calls.
_session = requests.Session()
_session.trust_env = False

HUB   = os.environ.get("HUB_URL", "http://127.0.0.1:8081")
FB    = Path("/root/empire_os/logs")
LOG   = FB / "solana_listener.jsonl"
SEEN  = FB / "solana_seen.jsonl"   # persistent seen cache
INTERVAL = int(os.environ.get("INTERVAL_SEC", "30"))

env_path = Path("/root/empire_os/.env")
if env_path.exists():
    for ln in env_path.read_text().splitlines():
        if "=" in ln and not ln.startswith("#"):
            k, v = ln.split("=", 1)
            if not os.environ.get(k.strip()):
                os.environ[k.strip()] = v.strip()
VAULT = os.environ.get("SOLANA_VAULT_WALLET", "").strip()
RPC   = os.environ.get("SOLANA_RPC_URL", "").strip()
USDC_MINT = os.environ.get("USDC_MINT", "EPjFWdd5AufqSSqeM2qN1xzybafCvkRxb7Yy4dV").strip()
TOKEN_PROGRAM = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"


def log(level, msg, **fields):
    e = {"ts": datetime.now(timezone.utc).isoformat(),
         "level": level, "msg": msg, **fields}
    FB.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a") as f:
        f.write(json.dumps(e) + "\n")
    # Also print to stdout so systemd journal captures it
    print(json.dumps(e), flush=True)


def seen_signatures():
    if not SEEN.exists(): return set()
    return set(l.split()[0] for l in SEEN.read_text().splitlines() if l.strip())


def mark_seen(sig):
    with open(SEEN, "a") as f:
        f.write(sig + "\n")


def recent_signatures(limit=20, before=None):
    """Fetch recent signatures for the vault's token accounts.

    `limit` raised to 20, max 1000.
    `before` (optional): a signature to start pagination from.
    """
    if not RPC or not VAULT:
        return []
    sigs = []
    try:
        r = _session.post(RPC, json={
            "jsonrpc":"2.0","id":1,
            "method":"getTokenAccountsByOwner",
            "params":[VAULT, {"programId": TOKEN_PROGRAM},
                      {"encoding": "jsonParsed"}]
        }, timeout=10).json()
        atas = [a["pubkey"] for a in r.get("result", {}).get("value", [])]
        for ata in atas:
            params = [ata, {"limit": limit}]
            if before:
                params[1]["before"] = before
            rr = _session.post(RPC, json={
                "jsonrpc":"2.0","id":1,
                "method":"getSignaturesForAddress",
                "params": params
            }, timeout=10).json()
            for s in rr.get("result", []):
                if "signature" in s:
                    sigs.append({"signature": s["signature"],
                                 "blockTime": s.get("blockTime"),
                                 "slot": s.get("slot"),
                                 "ata": ata})
    except Exception as e:
        log("ERROR", "sig_fetch_fail", err=str(e)[:150])
    return sigs


def vault_usdc_balance() -> float:
    """Current USDC balance of the vault's ATA. Robust (no getTransaction)."""
    if not RPC or not VAULT:
        return 0.0
    try:
        r = _session.post(RPC, json={
            "jsonrpc": "2.0", "id": 1,
            "method": "getTokenAccountsByOwner",
            "params": [VAULT, {"programId": TOKEN_PROGRAM},
                       {"encoding": "jsonParsed"}]
        }, timeout=10).json()
        for a in r.get("result", {}).get("value", []):
            info = a["account"]["data"]["parsed"]["info"]
            if info.get("mint") == USDC_MINT:
                return float(info["tokenAmount"]["uiAmount"] or 0.0)
    except Exception as e:
        log("ERROR", "balance_fetch_fail", err=str(e)[:150])
    return 0.0


STATE = FB / "vault_balance_usdc.txt"


def last_seen_balance() -> float:
    try:
        return float(STATE.read_text().strip() or "0")
    except Exception:
        return 0.0


def save_balance(b: float):
    STATE.write_text(str(b))


def get_memo_for_signature(sig: str) -> str:
    """Extract a Memo-program instruction from a confirmed tx, if present.
    Returns the memo string, or '' if none / RPC fails.
    Handles both the MemoSq4... program and a parsed memo field."""
    if not RPC or not sig:
        return ""
    try:
        r = _session.post(RPC, json={
            "jsonrpc": "2.0", "id": 1, "method": "getTransaction",
            "params": [sig, {"encoding": "jsonParsed"}],
        }, timeout=10).json()
        tx = r.get("result")
        if not tx:
            return ""
        # 1) explicit Memo program instruction
        MEMO_PROG = "MemoSq4gqABAXKb96qnH8TysB5mtg3MFrjGZRiTtEf"
        for ix in tx.get("transaction", {}).get("message", {}).get("instructions", []):
            if ix.get("programId") == MEMO_PROG:
                return (ix.get("parsed") or ix.get("data", "")).strip()
        # 2) parsed memo in account data (Helius-style)
        for ix in tx.get("transaction", {}).get("message", {}).get("instructions", []):
            if isinstance(ix.get("parsed"), dict) and "memo" in ix["parsed"]:
                return str(ix["parsed"]["memo"]).strip()
        return ""
    except Exception as e:
        log("ERROR", "memo_fetch_fail", err=str(e)[:150])
        return ""


def detect_incoming():
    """Detect new incoming USDC by balance delta (no getTransaction needed).

    Critical ordering (audit fix 2026-07-22):
      1) Read current + prev balance
      2) Build replay + record bodies
      3) Attempt replay (auto-match)
      4) If no match, attempt record_unmatched WITH RETRY
      5) ONLY save_balance AFTER both succeed
    If steps 3 or 4 fail after retries, the prev balance is NOT updated,
    so the next tick re-attempts the same delta. No silent deposit loss.
    """
    cur = vault_usdc_balance()
    prev = last_seen_balance()
    if cur <= prev:
        return  # no new funds
    delta = round(cur - prev, 6)
    delta_micro = int(round(delta * 1_000_000))
    log("INFO", "usdc_incoming", amount_usdc=delta_micro,
        prev=prev, now=cur, ata=VAULT)

    # Extract the on-chain memo from the most recent tx that hit the vault.
    memo = ""
    sigs = []
    try:
        sigs = recent_signatures(limit=5)
        if sigs:
            memo = get_memo_for_signature(sigs[0]["signature"])
    except Exception as e:
        log("WARN", "memo_lookup_skip", err=str(e)[:120])

    tx_sig = sigs[0]["signature"] if sigs else f"balance-diff-{int(time.time()*1e6)}"
    replay_body = {
        "amount_usdc": delta,
        "memo": memo,
        "wallet_from": "solana_listener",
        "tx_signature": tx_sig,
        "note": "detected via ATA balance delta + on-chain memo",
    }

    # --- Step 1: replay (auto-match attempt) ---
    rr = None
    replay_ok = False
    for attempt in range(3):
        try:
            rr = _session.post(f"{HUB}/v1/finance/replay",
                               json=replay_body, timeout=10).json()
            replay_ok = True
            log("INFO", "replay_invoked",
                attempt=attempt + 1,
                matched_to=rr.get("matched_to"),
                paid_sub=rr.get("paid_subscription_id"),
                paid_inv=rr.get("paid_invoice_id"),
                balance_after=rr.get("balance_after_usdc"))
            break
        except Exception as e:
            log("WARN", "replay_retry",
                attempt=attempt + 1, err=str(e)[:120])
            time.sleep(2 ** attempt)  # 1s, 2s, 4s
    if not replay_ok:
        log("ERROR", "replay_failed_after_retries",
            tx=tx_sig, delta_usdc=delta)
        # Do NOT save_balance — next tick retries the same delta.
        return

    # --- Step 1b: ALSO process via settlement gateway for LEAD_ memo matching ---
    # The replay endpoint handles subscriptions/invoices, but lead settlements
    # with LEAD_<lead_id> memos need the settlement_gateway to transition
    # si_funnel_event to 'settled' and write si_settlements.
    if memo and memo.startswith("LEAD_"):
        try:
            settlement_result = process_settlement(memo, tx_sig, delta)
            log("INFO", "settlement_gateway_lead", result=settlement_result)
        except Exception as e:
            log("ERROR", "settlement_gateway_error", err=str(e)[:150])

    # --- Step 2: record_unmatched (with retry) if replay didn't auto-match ---
    matched = bool(rr.get("matched_to")) or bool(rr.get("paid_invoice_id"))
    if not matched:
        record_body = {
            "tx_signature": tx_sig,
            "amount_usdc": delta,
            "vault_wallet": VAULT,
            "received_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
            "vault_balance_after_usdc": cur,
            "notes": "auto-captured by solana_listener; replay matched_to=null",
        }
        record_ok = False
        for attempt in range(3):
            try:
                ures = _session.post(f"{HUB}/v1/finance/unmatched/record",
                                      json=record_body, timeout=10).json()
                log("INFO", "unmatched_recorded",
                    attempt=attempt + 1,
                    unmatched_id=ures.get("id"),
                    duplicate=ures.get("duplicate", False))
                record_ok = True
                break
            except Exception as ue:
                log("WARN", "unmatched_record_retry",
                    attempt=attempt + 1, err=str(ue)[:120])
                time.sleep(2 ** attempt)
        if not record_ok:
            log("ERROR", "unmatched_record_failed_after_retries",
                tx=tx_sig, delta_usdc=delta,
                note="balance NOT updated — next tick will retry")
            # Do NOT save_balance — next tick retries the same delta.
            return

    # --- Step 3: only NOW commit the balance ---
    save_balance(cur)


def process(sig, ata):
    """Legacy per-sig path kept for compatibility; primary detection is
    detect_incoming() (balance diff). This just marks seen + logs."""
    log("INFO", "sig_seen", sig=sig[:20] + "...", ata=ata[:20])



# Module-level state
SWEEP_DONE = {"ok": False}


def cycle():
    # Primary: balance-delta detection (robust, no getTransaction)
    try:
        detect_incoming()
    except Exception as e:
        log("ERROR", "detect_fail", err=str(e)[:200])
        # Secondary: signature sweep (marks seen, legacy logging)
        sigs = recent_signatures(
            # first run fetches a deeper history; subsequent runs shallow
            limit=(100 if not SWEEP_DONE["ok"] else 15)
        )
        SWEEP_DONE["ok"] = True
        if not sigs:
            return
        seen = seen_signatures()
        new_count = 0
        for s in sigs:
            if s["signature"] in seen: continue
            mark_seen(s["signature"])
            new_count += 1
            process(s["signature"], s["ata"])
        if new_count:
            log("INFO", "polled", new=new_count, total=len(sigs))
    
    # Heartbeat every cycle so health check sees activity
    log("INFO", "heartbeat", status="alive")


if __name__ == "__main__":
    FB.mkdir(parents=True, exist_ok=True)
    SEEN.touch(exist_ok=True)
    print(f"[{datetime.now(timezone.utc).isoformat()}] solana-listener online - {INTERVAL}s",
          flush=True)
    while True:
        try: cycle()
        except Exception as e:
            log("ERROR", "cycle", err=str(e)[:200])
        time.sleep(INTERVAL)
