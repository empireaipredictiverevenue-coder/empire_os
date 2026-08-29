#!/usr/bin/env python3
"""
BSC USDT Listener — monitors BSC wallet for inbound USDT (BEP20) transfers.
Reconciles with si_charges/si_settlements by polling balance.

Runs every 60s via systemd. Zero gas needed to receive USDT on BSC.
"""
import os, sys, json, time, logging, urllib.request
from pathlib import Path

sys.path.insert(0, "/root/empire_os")
for _ln in open("/root/empire_os/.env"):
    _ln = _ln.strip()
    if _ln and "=" in _ln and not _ln.startswith("#"):
        _k, _v = _ln.split("=", 1)
        os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

BSC_WALLET = os.environ.get("BSC_WALLET_ADDRESS") or "0x1339b487046B0ad924a10c20b1791608EA8595a8"
if BSC_WALLET.lower() in {
    "0xe646cb6a2befc6fd88f418e7e19a32abe4aed7fb",
    "0xfb1f11b7a6815ee00ed2dbad7af58da773914ba5",
}:
    # REVENUE LOCKDOWN: never silently revert to a banned placeholder wallet.
    raise RuntimeError("REVENUE LOCKDOWN: BSC_WALLET_ADDRESS resolved to a banned "
                       "placeholder address. Fix /root/empire_os/.env.")
USDT_CONTRACT = os.environ.get("BSC_USDT_CONTRACT", "0x55d398326f99059fF775485246999027B3197955")
HUB_URL = "http://127.0.0.1:8081"
POLL_INTERVAL = 60

logging.basicConfig(level=logging.INFO, format="%(asctime)s [bsc] %(message)s")
log = logging.getLogger("bsc_listener")

def get_usdt_balance(address, rpc):
    """Check USDT balance via eth_call — works on free RPCs, no rate limit."""
    data = "0x70a08231000000000000000000000000" + address[2:].lower()
    payload = json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "eth_call",
        "params": [{"to": USDT_CONTRACT, "data": data}, "latest"]
    }).encode()
    req = urllib.request.Request(rpc, data=payload, headers={"Content-Type": "application/json"})
    resp = urllib.request.urlopen(req, timeout=10)
    result = json.loads(resp.read())
    if "result" in result and result["result"] != "0x":
        return int(result["result"], 16) / 1e18
    return 0.0

def reconcile_settlement(delta, cycle):
    """Notify hub of inbound USDT payment via /v1/finance/replay.

    Hub expects: amount_usdc, memo, wallet_from, tx_signature.
    memo is OPTIONAL — Trust Wallet/Trust USDT transfers carry none, so
    hub falls back to amount-match on awaiting invoices.
    """
    payload = json.dumps({
        "amount_usdc": round(delta, 6),
        "memo": "",
        "wallet_from": BSC_WALLET,
        "tx_signature": f"bsc_balance_{cycle}",
    }).encode()
    try:
        req = urllib.request.Request(
            f"{HUB_URL}/v1/finance/replay",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        resp = urllib.request.urlopen(req, timeout=10)
        return json.loads(resp.read())
    except Exception as e:
        log.warning(f"hub reconcile failed: {e}")
        return None

BASELINE_FILE = "/root/empire_os/logs/bsc_last_balance.txt"

def load_last_balance() -> float:
    """Persisted balance from previous run. Prevents restarts from
    re-counting the whole vault balance as INBOUND (phantom revenue)."""
    try:
        with open(BASELINE_FILE) as f:
            return float(f.read().strip() or 0.0)
    except Exception:
        return 0.0

def save_last_balance(bal: float) -> None:
    try:
        Path(BASELINE_FILE).parent.mkdir(parents=True, exist_ok=True)
        with open(BASELINE_FILE, "w") as f:
            f.write(f"{bal:.6f}")
    except Exception:
        pass

def main():
    log.info(f"BSC USDT listener started — wallet={BSC_WALLET} interval={POLL_INTERVAL}s")
    last_balance = load_last_balance()
    cycle = 0
    RPC_ENDPOINTS = [
        "https://bsc-dataseed.binance.org",
        "https://bsc-dataseed1.binance.org",
        "https://bsc-dataseed2.binance.org",
    ]
    rpc_idx = 0
    while True:
        cycle += 1
        rpc = RPC_ENDPOINTS[rpc_idx % len(RPC_ENDPOINTS)]
        try:
            current_balance = get_usdt_balance(BSC_WALLET, rpc)
            delta = current_balance - last_balance
            if delta > 0:
                log.info(f"INBOUND USDT: +{delta} (new balance: {current_balance})")
                result = reconcile_settlement(delta, cycle)
                if result:
                    log.info(f"settled: {json.dumps(result)[:200]}")
                last_balance = current_balance
                save_last_balance(current_balance)
            elif delta < 0:
                # Outbound payout — just move baseline, never settle negatives
                last_balance = current_balance
                save_last_balance(current_balance)
            log.info(f"cycle_end ok=true balance={current_balance} delta={delta}")
            rpc_idx = 0
        except Exception as e:
            log.warning(f"cycle error on {rpc}: {e}")
            rpc_idx += 1
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()
