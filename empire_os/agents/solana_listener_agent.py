
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
    """Detect new incoming USDC by balance delta (no getTransaction needed)."""
    cur = vault_usdc_balance()
    prev = last_seen_balance()
    save_balance(cur)
    if cur <= prev:
        return  # no new funds
    delta = round(cur - prev, 6)
    delta_micro = int(round(delta * 1_000_000))  # micro-USDC to match si_ppc_invoices
    log("INFO", "usdc_incoming", amount_usdc=delta_micro,
        prev=prev, now=cur, ata=VAULT)
    # Extract the on-chain memo from the most recent tx that hit the vault,
    # so replay can match SEAT_/INV_/LANE_ memos (not just amount).
    memo = ""
    try:
        sigs = recent_signatures(limit=5)
        if sigs:
            memo = get_memo_for_signature(sigs[0]["signature"])
    except Exception as e:
        log("WARN", "memo_lookup_skip", err=str(e)[:120])
    replay_body = {
        "amount_usdc": delta_micro,   # micro-units, matches invoice schema
        "memo": memo,
        "wallet_from": "solana_listener",
        "tx_signature": sigs[0]["signature"] if sigs else "balance-diff",
        "note": "detected via ATA balance delta + on-chain memo",
    }
    try:
        rr = _session.post(f"{HUB}/v1/finance/replay",
                           json=replay_body, timeout=10).json()
        log("INFO", "replay_invoked", matched_to=rr.get("matched_to"),
            paid_sub=rr.get("paid_subscription_id"),
            paid_inv=rr.get("paid_invoice_id"),
            balance_after=rr.get("balance_after_usdc"))
    except Exception as e:
        log("ERROR", "replay_call_fail", err=str(e)[:150])


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
