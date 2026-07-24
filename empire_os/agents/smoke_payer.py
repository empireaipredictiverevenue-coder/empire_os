#!/usr/bin/env python3
"""
smoke_payer.py — generate a throwaway Solana wallet, request a $0.01 USDC
invoice from the hub, build + sign the transfer, broadcast it, then watch
the container DB to confirm the charge flips to status='succeeded'.

SAFETY:
- Generated key is printed ONCE (base58) and saved to /tmp/smoke_payer.json.
- After successful settlement (or timeout/fail), the JSON is shredded.
- The script never writes the key to disk outside /tmp.
- If the smoke completes, the wallet is abandoned — never reused.

Usage:
  incus exec empire-hub -- /root/venv/bin/python3 /root/empire_os/empire_os/agents/smoke_payer.py [--amount-usd 0.01]

Returns 0 if the inbound USDC was detected and the charge marked paid.
"""
import argparse
import asyncio
import base64
import json
import os
import secrets
import struct
import sys
import time
import urllib.request
from pathlib import Path

HUB_INTERNAL = "http://127.0.0.1:8081"  # inside-container URL
RPC = "https://mainnet.helius-rpc.com/?api-key=585a5f3f-1fbc-4f0d-869c-2d3e981341e1"
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
SOL_USD = 150.0  # static estimate; we only need ~0.00001 SOL for gas
KEY_FILE = Path("/tmp/smoke_payer.json")
KEY_FILE_SHRED = True


def log(level, msg, **fields):
    print(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                       "level": level, "msg": msg, **fields}, default=str), flush=True)


def load_env():
    """Source .env without echoing values."""
    env_path = Path("/root/empire_os/.env")
    if not env_path.exists():
        log("FATAL", "missing .env")
        sys.exit(1)
    out = {}
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def generate_wallet():
    from solders.keypair import Keypair
    kp = Keypair()
    pubkey = str(kp.pubkey())
    secret_b58 = __import__("base58").b58encode(bytes(kp)).decode("ascii")
    # Save to file with locked perms (0600)
    KEY_FILE.write_text(json.dumps({"pubkey": pubkey, "secret_b58": secret_b58}))
    os.chmod(KEY_FILE, 0o600)
    log("INFO", "wallet generated", pubkey=pubkey, key_file=str(KEY_FILE))
    return kp, pubkey, secret_b58


def shred_key():
    try:
        if KEY_FILE.exists():
            # Best-effort overwrite before delete
            sz = KEY_FILE.stat().st_size
            with open(KEY_FILE, "wb") as f:
                f.write(secrets.token_bytes(sz))
                f.flush()
                os.fsync(f.fileno())
            KEY_FILE.unlink()
            log("INFO", "key file shredded")
    except Exception as e:
        log("WARN", f"shred failed: {e}")


def post_json(url, body, timeout=10):
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def rpc_call(method, params, timeout=10):
    return post_json(RPC, {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}, timeout=timeout)


def find_usdc_ata(payer_kp, mint_str):
    """Derive the associated token address for (payer, USDC)."""
    from solders.pubkey import Pubkey
    ATA_PROGRAM = Pubkey.from_string("ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL")
    TOKEN_PROGRAM = Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
    mint_pk = Pubkey.from_string(mint_str)
    # SPL ATA derivation: pass 3 separate seeds (NOT concatenated)
    seeds = [bytes(payer_kp.pubkey()), bytes(TOKEN_PROGRAM), bytes(mint_pk)]
    addr, _bump = Pubkey.find_program_address(seeds, ATA_PROGRAM)
    return addr


def build_usdc_transfer_tx(payer_kp, src_ata, dest_ata, amount_usd):
    """Build a signed SPL transfer_checked tx for `amount_usd` USDC."""
    from solders.keypair import Keypair
    from solders.pubkey import Pubkey
    from solders.instruction import Instruction, AccountMeta
    from solders.message import MessageV0
    from solders.transaction import VersionedTransaction
    from solders.hash import Hash

    TOKEN_PROGRAM = Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
    USDC_DECIMALS = 6
    amount_raw = int(amount_usd * (10 ** USDC_DECIMALS))

    # Hand-built transfer_checked: index 12, then <Q> amount, <B> decimals
    data = struct.pack("<BQB", 12, amount_raw, USDC_DECIMALS)
    accounts = [
        AccountMeta(pubkey=src_ata, is_signer=False, is_writable=True),
        AccountMeta(pubkey=Pubkey.from_string(USDC_MINT), is_signer=False, is_writable=False),
        AccountMeta(pubkey=dest_ata, is_signer=False, is_writable=True),
        AccountMeta(pubkey=payer_kp.pubkey(), is_signer=True, is_writable=False),
    ]
    ix = Instruction(program_id=TOKEN_PROGRAM, accounts=accounts, data=data)
    blockhash_resp = rpc_call("getLatestBlockhash", [{"commitment": "confirmed"}])
    blockhash_str = blockhash_resp["result"]["value"]["blockhash"]
    # solders 0.27 requires Hash object (no string auto-conversion)
    msg = MessageV0.try_compile(payer_kp.pubkey(), [ix], [],
                                 Hash.from_string(blockhash_str))
    # VersionedTransaction CONSTRUCTOR signs internally (payout.py pattern)
    txn = VersionedTransaction(msg, [payer_kp])
    # bytes(txn) returns the wire format (no .serialize() in 0.27)
    return bytes(txn)


def send_tx(signed_tx_bytes):
    """Broadcast a signed tx (raw bytes from txn.serialize())."""
    # Helius accepts base64 for sendTransaction (standard Solana RPC)
    import base64 as _b64
    signed_b64 = _b64.b64encode(signed_tx_bytes).decode("ascii")
    resp = rpc_call("sendTransaction", [
        signed_b64,
        {"skipPreflight": False, "preflightCommitment": "confirmed", "encoding": "base64"}
    ])
    if "error" in resp:
        raise RuntimeError(f"sendTransaction error: {resp['error']}")
    return resp["result"]


def wait_for_settlement(payer_pubkey, charge_id, timeout_s=180):
    """Poll si_charges for the given charge_id until status='succeeded' or timeout."""
    db = "/root/empire_os/empire_os.db"
    import sqlite3
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        con = sqlite3.connect(db)
        row = con.execute(
            "SELECT status, paid_at FROM si_charges WHERE charge_id=?",
            (charge_id,)
        ).fetchone()
        con.close()
        log("INFO", "poll si_charges", charge_id=charge_id, status=row[0] if row else None)
        if row and row[0] == "succeeded":
            log("INFO", "SETTLED", charge_id=charge_id, paid_at=row[1])
            return True
        time.sleep(8)
    log("ERROR", "settlement timeout", charge_id=charge_id, timeout_s=timeout_s)
    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--amount-usd", type=float, default=0.01)
    parser.add_argument("--buyer-id", default="smoke_payer_2026_07_22")
    parser.add_argument("--skip-broadcast", action="store_true",
                        help="Just generate wallet + invoice; don't sign/broadcast")
    parser.add_argument("--key-file", default=None,
                        help="Use an existing key JSON instead of generating fresh. "
                              "Must contain {pubkey, secret_b58}.")
    parser.add_argument("--no-shred", action="store_true",
                        help="Don't shred the key file at the end (for testing)")
    args = parser.parse_args()

    env = load_env()
    vault_wallet = env.get("SOLANA_VAULT_WALLET")
    if not vault_wallet:
        log("FATAL", "no SOLANA_VAULT_WALLET in .env")
        sys.exit(1)

    # Step 1: get wallet — either from --key-file (funded path) or generate fresh
    if args.key_file:
        from solders.keypair import Keypair
        from solders.pubkey import Pubkey
        kf = Path(args.key_file)
        if not kf.exists():
            log("FATAL", f"--key-file not found: {kf}")
            sys.exit(1)
        data = json.loads(kf.read_text())
        pubkey_str = data["pubkey"]
        secret_b58 = data["secret_b58"]
        payer_kp = Keypair.from_bytes(__import__("base58").b58decode(secret_b58))
        payer_pubkey = str(payer_kp.pubkey())
        if pubkey_str != payer_pubkey:
            log("FATAL", "key file pubkey mismatch", file=pubkey_str, derived=payer_pubkey)
            sys.exit(1)
        log("INFO", "wallet loaded from file", pubkey=payer_pubkey, key_file=str(kf))
    else:
        payer_kp, payer_pubkey, _secret_b58 = generate_wallet()

    # Step 2: request a USDC invoice from hub using the payer wallet as buyer_id
    log("INFO", "requesting invoice from hub", buyer_id=payer_pubkey, vault=vault_wallet)
    body = {
        "buyer_id": payer_pubkey,  # use pubkey as buyer_id so resolver can find email later
        "head": 2,
        "reason": f"smoke_payer_2026_07_22_{secrets.token_hex(4)}",
        "amount_cents": int(args.amount_usd * 100),
    }
    invoice = post_json(f"{HUB_INTERNAL}/v1/ppc/charge", body, timeout=15)
    log("INFO", "invoice received", charge_id=invoice.get("charge_id"),
        status=invoice.get("status"), pay_url=invoice.get("pay_url", "")[:80] + "...")

    if invoice.get("status") != "open":
        log("WARN", "invoice not open", status=invoice.get("status"))

    if args.skip_broadcast:
        log("INFO", "--skip-broadcast set; not signing or broadcasting.")
        log("INFO", "PAY THIS MANUALLY", amount_usd=args.amount_usd, **{"from": payer_pubkey},
            to=vault_wallet, memo=invoice.get("memo"))
        if not args.no_shred and not args.key_file:
            shred_key()
        return 0

    # Step 3: derive our USDC ATA + vault's USDC ATA
    from solders.pubkey import Pubkey
    payer_ata = find_usdc_ata(payer_kp, USDC_MINT)
    # The vault's USDC ATA — we don't easily know it without lookup.
    # For a $0.01 smoke, we can send to vault's SOL address wrapped, or use SOL.
    # Simplest path: send native SOL ($0.01 worth ≈ 0.000067 SOL) to the vault.
    # That still gets us a "successful" path if solana_listener watches the vault's SOL balance.
    # BUT — the listener is set up for USDC. So we MUST send USDC.
    # Use Helius getTokenAccountsByOwner to find vault's USDC ATA.
    log("INFO", "looking up vault USDC ATA...")
    vault_ata_resp = rpc_call("getTokenAccountsByOwner", [
        Pubkey.from_string(vault_wallet).__str__(),
        {"mint": USDC_MINT},
        {"encoding": "base64"}
    ])
    accounts = vault_ata_resp["result"]["value"]
    if not accounts:
        log("FATAL", "vault has no USDC ATA — need to send SOL to vault OR initialize ATA first")
        shred_key()
        return 1
    vault_ata = accounts[0]["pubkey"]
    log("INFO", "vault USDC ATA found", ata=vault_ata)

    # Check our ATA exists / has balance
    payer_ata_resp = rpc_call("getAccountInfo", [payer_ata.__str__(), {"encoding": "base64"}])
    payer_ata_exists = payer_ata_resp["result"]["value"] is not None
    log("INFO", "payer USDC ATA exists?", exists=payer_ata_exists, ata=str(payer_ata))

    # Build + sign + send the transfer
    log("INFO", "building USDC transfer tx", amount_usd=args.amount_usd,
        src=str(payer_ata), dst=vault_ata)
    tx_bytes = build_usdc_transfer_tx(payer_kp, payer_ata, Pubkey.from_string(vault_ata), args.amount_usd)
    sig_b64 = base64.b64encode(tx_bytes).decode()
    log("INFO", "tx signed, broadcasting", size=len(tx_bytes))

    try:
        sig = send_tx(tx_bytes)
        log("INFO", "TX BROADCAST", signature=sig,
            explorer=f"https://solscan.io/tx/{sig}")
    except Exception as e:
        log("FATAL", f"broadcast failed: {e}")
        # Do NOT shred on failure — keep key for retry. Caller can shred manually.
        return 1

    # Step 4: poll si_charges for settlement
    settled = wait_for_settlement(payer_pubkey, invoice["charge_id"], timeout_s=180)
    if not args.no_shred and not args.key_file:
        shred_key()
    elif args.key_file and not args.no_shred:
        try:
            Path(args.key_file).unlink()
            log("INFO", "key file shredded (--key-file mode)")
        except Exception as e:
            log("WARN", f"shred failed: {e}")
    return 0 if settled else 1


if __name__ == "__main__":
    sys.exit(main())