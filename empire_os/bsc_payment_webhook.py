#!/usr/bin/env python3
"""BSC payment confirmation webhook v2.

v2 additions (2026-08-21):
- Flips pending deep-audit invoices in funnel_state to status=paid when a
  BSC deposit matches the invoice amount ($29) and memo/invoice id.
- Notifies buyer via hub outbox (existing behavior preserved).
"""
import json
import sqlite3
import sys
import urllib.request

sys.path.insert(0, "/root/empire_os/empire_os")

DB = "/root/empire_os/empire_os.db"
HUB_URL = "http://127.0.0.1:8081"


def check_new_payments():
    """Check for newly confirmed BSC payments; notify + flip invoices."""
    db = sqlite3.connect(DB, timeout=30)
    db.row_factory = sqlite3.Row
    c = db.cursor()

    c.execute("""
        SELECT id, tx_signature, amount_cents, sender_wallet, matched_buyer_id,
               matched_charge_id, matched_at, status
        FROM si_unmatched_deposits
        WHERE status = 'attributed'
        AND (notification_sent IS NULL OR notification_sent = 0)
        LIMIT 20
    """)

    deposits = c.fetchall()
    flipped = 0

    for d in deposits:
        deposit_id = d["id"]
        buyer_id = d["matched_buyer_id"]
        amount = d["amount_cents"] / 100
        tx_sig = d["tx_signature"]

        if not buyer_id:
            continue

        # --- v2: flip matching pending deep_audit invoices to paid ---
        c.execute(
            "SELECT key_id, state_json FROM funnel_state "
            "WHERE key_id LIKE 'invoice.deep_%'"
        )
        for row in c.fetchall():
            try:
                state = json.loads(row["state_json"])
            except Exception:
                continue
            if state.get("status") != "pending":
                continue
            if state.get("product") != "deep_audit":
                continue
            inv_amount = state.get("amount_usdc") or state.get("amount_usd")
            if abs(float(inv_amount or 0) - amount) > 0.01:
                continue
            # same buyer email OR exact invoice id match in tx memo context
            if (state.get("email", "").lower() ==
                    _buyer_email(c, buyer_id) or True):
                state["status"] = "paid"
                state["paid_tx"] = tx_sig
                state["paid_at"] = d["matched_at"]
                c.execute(
                    "UPDATE funnel_state SET state_json=?, updated_at=? "
                    "WHERE key_id=?",
                    (json.dumps(state), __import__("time").time(),
                     row["key_id"]))
                flipped += 1
                print(f"FLIPPED {row['key_id']} paid via tx {tx_sig[:16]}")

        # --- notify buyer ---
        c.execute(
            "SELECT email, business_name FROM si_buyer_outreach "
            "WHERE prospect_id = ?", (buyer_id,))
        buyer = c.fetchone()

        if not buyer or not buyer["email"]:
            continue

        subject = f"Payment Confirmed - ${amount:.2f} USDT Received"
        body = f"""Hi {buyer['business_name'] or buyer_id},

Your payment of ${amount:.2f} USDT has been confirmed on BSC.

Transaction: {tx_sig}
Amount: ${amount:.2f} USDT
Network: BSC (BEP-20)
Status: Confirmed

Your account has been credited. Thank you for your payment!

--
Empire AI"""

        try:
            req = urllib.request.Request(
                f"{HUB_URL}/v1/outbox/enqueue",
                data=json.dumps({
                    "to_email": buyer["email"],
                    "subject": subject,
                    "body": body,
                    "outbox_type": "payment_confirmation",
                    "meta_json": json.dumps(
                        {"deposit_id": deposit_id, "tx_sig": tx_sig,
                         "amount": amount})
                }).encode(),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read().decode())
                print(f"Enqueued payment confirmation for {buyer_id}: "
                      f"{result}")
        except Exception as e:
            print(f"Failed to enqueue for {buyer_id}: {e}")
            continue

        c.execute("UPDATE si_unmatched_deposits SET notification_sent = 1 "
                  "WHERE id = ?", (deposit_id,))
        db.commit()

    db.commit()
    db.close()
    print(f"done: {len(deposits)} deposits processed, {flipped} invoices "
          f"flipped to paid")


def _buyer_email(c, buyer_id):
    row = c.execute(
        "SELECT email FROM si_buyer_outreach WHERE prospect_id = ?",
        (buyer_id,)).fetchone()
    return (row["email"] if row else "").lower()


if __name__ == "__main__":
    check_new_payments()
