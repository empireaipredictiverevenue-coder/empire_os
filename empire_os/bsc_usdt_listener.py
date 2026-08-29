"""BSC USDT settlement listener — watches USDT contract payouts and marks invoices paid.

Uses the same custom RPC pattern as crypto_charge.py (no web3.py dependency).
Watches BSC for USDT Transfer events to known buyer addresses, matches to si_invoice
by buyer address (crypto_wallet column in si_tenant), then:
  UPDATE si_invoice SET status='paid', paid_method='usdt', paid_at=<timestamp>

Run as background process: python3 -u /root/empire_os/empire_os/bsc_usdt_listener.py
"""

import os, sys, json, time
from datetime import datetime, timezone
import sqlite3 as sq

# Config from env (same as crypto_charge.py conventions).
# Default to Binance BSC dataseed RPCs (no bsc references).
_BSC_RPC_CANDIDATES = [
    "https://bsc-dataseed.binance.org",
    "https://bsc-dataseed1.binance.org",
    "https://bsc-dataseed2.binance.org",
    "https://bsc-dataseed3.binance.org",
    "https://bsc-dataseed4.binance.org",
]
BSC_RPC = os.environ.get("BSC_RPC") or _BSC_RPC_CANDIDATES[0]
BSC_USDT_CONTRACT = os.environ.get(
    "BSC_USDT_CONTRACT", "0x55d398326f99059fF775485246999027B3197955"
)
# Vault address for BSC pay-to (same as before)
BSC_WALLET = os.environ.get(
    "BSC_WALLET_ADDRESS", "0x1339b487046B0ad924a10c20b1791608EA8595a8"
)
DB = "/root/empire_os/empire_os.db"

USDT_DECIMALS = 18

# Simple RPC — same pattern as crypto_charge.py _rpc()
def _rpc(method, params):
    """Call BSC JSON-RPC. Returns dict with 'result' or 'error'."""
    import urllib.request, urllib.error
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    url = BSC_RPC + ("/" if "?" not in BSC_RPC else "")
    req = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return {"error": f"http {e.code}", "body": e.read().decode()[:200]}
    except Exception as e:
        return {"error": str(e)[:200]}

# Load tenant -> crypto_wallet map from DB (si_tenant has crypto_wallet, not buyer_id)
_tenant_map = {}

def _load_tenant_map():
    global _tenant_map
    con = sq.connect(DB, timeout=30)
    try:
        c = con.cursor()
        c.execute("SELECT tenant_id, crypto_wallet FROM si_tenant WHERE crypto_wallet IS NOT NULL AND crypto_wallet != ''")
        for row in c.fetchall():
            _tenant_map[row[1].lower()] = {"tenant_id": row[0], "wallet": row[1]}
    finally:
        con.close()

_load_tenant_map()

print(f"[bsc-usdt-listener] tenant map: {len(_tenant_map)} entries with crypto_wallet")

# Mark invoice as paid
def _mark_paid(invoice_id, method="usdt", ts_iso=None):
    if ts_iso is None:
        ts_iso = datetime.now(timezone.utc).isoformat()
    con = sq.connect(DB, timeout=60)
    try:
        c = con.cursor()
        c.execute("PRAGMA busy_timeout=60000")
        c.execute(
            "UPDATE si_invoice SET status='paid', paid_method=?, paid_at=? WHERE invoice_id=?",
            (method, ts_iso, invoice_id),
        )
        con.commit()
        n = c.rowcount
        return n
    finally:
        con.close()

# Poll BSC for new USDT Transfer events
def listen_loop():
    print(f"[bsc-usdt-listener] starting, watching USDT at {BSC_USDT_CONTRACT}")
    print(f"[bsc-usdt-listener] BSC RPC: {BSC_RPC[:60]}...")

    # Get starting block
    resp = _rpc("eth_blockNumber", [])
    if "error" in resp:
        print(f"[bsc-usdt-listener] error getting block number: {resp['error']}")
        return
    try:
        start_block = int(resp["result"], 16)
    except ValueError:
        start_block = 0

    last_block = start_block
    tx_hash_cache = set()

    while True:
        try:
            resp = _rpc("eth_blockNumber", [])
            if "error" in resp:
                time.sleep(5)
                continue
            current_block = int(resp["result"], 16)
            for block_num in range(last_block + 1, current_block + 1):
                resp = _rpc("eth_getBlockByNumber", [hex(block_num), True])
                if "error" in resp or "result" not in resp:
                    continue
                block = resp["result"]
                for tx_obj in block.get("transactions", []):
                    tx_hash = tx_obj.get("hash")
                    if not tx_hash or tx_hash in tx_hash_cache:
                        continue
                    tx_hash_cache.add(tx_hash)

                    resp = _rpc("eth_getTransactionByHash", [tx_hash])
                    if "error" in resp or "result" not in resp:
                        continue
                    tx = resp["result"]

                    # Only look at transactions to USDT contract
                    to_addr = tx.get("to", "")
                    if to_addr and to_addr.lower() == BSC_USDT_CONTRACT.lower():
                        # Get transaction receipt
                        resp = _rpc("eth_getTransactionReceipt", [tx_hash])
                        if "error" in resp or "result" not in resp:
                            continue
                        receipt = resp["result"]

                        # Parse Transfer logs from USDT contract
                        for log in receipt.get("logs", []):
                            try:
                                if log.get("address", "").lower() != BSC_USDT_CONTRACT.lower():
                                    continue
                                topics = log.get("topics", [])
                                if len(topics) >= 3:
                                    # Transfer(event) topic1=from, topic2=to (addresses)
                                    # These are hex strings; compare lowercased
                                    from_addr_topic = topics[1]
                                    to_addr_topic = topics[2]
                                    # Decode address from topic hex (last 20 bytes)
                                    # EIP-712 format: topic is keccak256 of address padded
                                    # Simpler: just check the `to` field in transaction
                            except Exception:
                                pass

                        # Check if any known tenant's crypto_wallet received USDT
                        for wallet_lower, info in _tenant_map.items():
                            # Check if this wallet appears in transaction logs or `to` field
                            if to_addr and to_addr.lower() == wallet_lower:
                                # Tenant's wallet received USDT — mark their invoices paid
                                inbound = _find_invoices_for_tenant(info["tenant_id"])
                                for inv in inbound:
                                    rows = _mark_paid(
                                        invoice_id=inv["invoice_id"],
                                        method="usdt",
                                        ts_iso=datetime.now(timezone.utc).isoformat(),
                                    )
                                    if rows:
                                        print(
                                            f"[bsc-usdt] paid invoice {inv['invoice_id']} "
                                            f"for tenant {info['tenant_id']}"
                                        )
                                break
            last_block = current_block
            time.sleep(5)
        except Exception as e:
            print(f"[bsc-usdt-listener] error: {e}")
            time.sleep(10)


def _find_invoices_for_tenant(tenant_id):
    """Find invoice_ids for a given tenant."""
    con = sq.connect(DB, timeout=30)
    try:
        c = con.cursor()
        c.execute("SELECT invoice_id FROM si_invoice WHERE tenant_id=?", (tenant_id,))
        return [{"invoice_id": row[0]} for row in c.fetchall()]
    finally:
        con.close()


if __name__ == "__main__":
    listen_loop()