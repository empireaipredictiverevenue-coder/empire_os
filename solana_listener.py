#!/usr/bin/env python3
"""
Empire OS — USDC/SOL Settlement Listener (Solana mainnet).

Watches the Empire vault wallet for incoming payments, reconciles them
against OPEN invoices in empire_os.db, and settles them (marks charge
succeeded + invoice paid + emits a 'settled' funnel event).

This is the INCOME RAIL. Previously this listener only wrote to a jsonl
log and never settled — so money arrived on-chain but never landed in
the ledger. Now it calls crypto_charge.reconcile_open_invoices() every
tick, which does the real settlement write.

Requires: SOLANA_RPC_URL, USDC_MINT, SOLANA_VAULT_WALLET in .env.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# load .env without external dep (matches agent_core.py style)
def _load_env():
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    try:
        for line in open(p):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())
    except Exception:
        pass

_load_env()


def listen(once: bool = False, interval: int = 20):
    """Reconcile open invoices against on-chain inbound payments."""
    from empire_os.crypto_charge import reconcile_open_invoices

    while True:
        try:
            settled = reconcile_open_invoices()
            for s in settled:
                print(
                    f"[settle] INVOICE {s['invoice_id']} PAID via "
                    f"{s['signature'][:12]} amount={s['amount']} USDC",
                    flush=True,
                )
        except Exception as e:
            sys.stderr.write(f"listen err: {e}\n")
        if once:
            break
        time.sleep(interval)


if __name__ == "__main__":
    listen(once=False, interval=20)
