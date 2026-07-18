#!/usr/bin/env python3
"""A2A settlement bridge: turn a2a_mesh agent quotes into payable charges.

Reads /root/feedback/a2a_mesh.jsonl, for each quote without a settled
charge, runs charge.charge(buyer_id=wallet, ...) to mint a Solana Pay
pay_url. Writes results to /root/feedback/a2a_settled.jsonl.

Idempotent-ish: skips quotes already in a2a_settled.jsonl by (ts,sku).
"""
import sys, json, sqlite3
sys.path.insert(0, "/root/empire_os")
from empire_os import charge

MESH = "/root/feedback/a2a_mesh.jsonl"
OUT = "/root/feedback/a2a_settled.jsonl"


def main():
    done = set()
    try:
        for line in open(OUT):
            try:
                d = json.loads(line)
                done.add((d["ts"], d["sku"]))
            except Exception:
                pass
    except FileNotFoundError:
        pass

    n = 0
    for line in open(MESH):
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except Exception:
            continue
        q = d.get("quote", {})
        sku = q.get("sku")
        ts = d.get("ts")
        if (ts, sku) in done:
            continue
        amt = int(float(q.get("price_usdc", 0)) * 100)
        if amt <= 0:
            continue
        res = charge.charge(
            buyer_id=d.get("wallet", "agent_unknown"),
            head=3, reason=f"A2A quote {sku} from {d.get('buyer_agent')}",
            amount_cents=amt, currency="USD")
        rec = {"ts": ts, "sku": sku, "buyer_agent": d.get("buyer_agent"),
               "wallet": d.get("wallet"), "charge_id": res.get("charge_id"),
               "status": res.get("status"), "pay_url": res.get("pay_url", ""),
               "memo": q.get("memo", "")}
        with open(OUT, "a") as f:
            f.write(json.dumps(rec) + "\n")
        n += 1
        print(f"  {sku}: {res.get('status')} charge={res.get('charge_id')} pay={'yes' if res.get('pay_url') else 'no'}")
    print(f"bridged {n} a2a quotes -> charges")


if __name__ == "__main__":
    main()
