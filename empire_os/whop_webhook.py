"""Whop webhook receiver — verifies HMAC signature and marks invoices paid.

Receives POST from whop webhook, verifies signature, then:
  UPDATE si_invoice SET status='paid', paid_method=<method>, paid_at=<timestamp>
  where the payload maps to the invoice (by buyer_id or invoice_id).

Run as: python3 -u whop_webhook.py
Exposes local endpoint at http://localhost:8082/whop/webhook
(Use ngrok or your preferred tunnel to make it reachable by whop.)
"""

import hashlib, hmac, json, os, sys
from datetime import datetime, timezone
from flask import Flask, request, abort

app = Flask(__name__)

# Config — set these from your whop dashboard or .env
WHOP_SECRET = os.environ.get("WHOP_WEBHOOK_SECRET", "change-me")
DB = "/root/empire_os/empire_os.db"

# Simple in-memory tenant cache to avoid repeated DB hits
_tenant_cache = {}


def _get_tenant(buyer_id):
    """Look up tenant_id from buyer_id via a simple map or DB scan.
    si_tenant schema: tenant_id, name, email, paypal_payer_id, crypto_wallet, ...
    Falls back to invoice_id pattern match if no direct link."""
    import sqlite3
    conn = sqlite3.connect(DB, timeout=30)
    try:
        c = conn.cursor()
        # Try matching tenant via email/tenant_id substring
        c.execute("SELECT tenant_id FROM si_tenant WHERE tenant_id=? OR email=? OR crypto_wallet=? LIMIT 1",
                  (buyer_id, buyer_id, buyer_id))
        row = c.fetchone()
        if row:
            return row[0]
        # Fallback: scan invoices for this buyer pattern
        c.execute("SELECT tenant_id FROM si_invoice WHERE invoice_id LIKE ? LIMIT 1",
                  (f"%{buyer_id}%",))
        rows = c.fetchall()
        if rows:
            return rows[0][0]
    finally:
        conn.close()
    return None


def _mark_paid(invoice_id, method, timestamp_iso):
    """UPDATE si_invoice SET status='paid', paid_method, paid_at."""
    import sqlite3
    for attempt in range(3):
        try:
            conn = sqlite3.connect(DB, timeout=60)
            c = conn.cursor()
            c.execute("PRAGMA busy_timeout=60000")
            c.execute(
                "UPDATE si_invoice SET status='paid', paid_method=?, paid_at=? WHERE invoice_id=?",
                (method, timestamp_iso, invoice_id),
            )
            conn.commit()
            n = c.rowcount
            conn.close()
            return n  # rows updated
        except sqlite3.OperationalError:
            import time
            time.sleep(2 ** attempt)
    return 0


@app.route("/whop/webhook", methods=["POST"])
def webhook():
    # Whop sends: X-Whop-Signature header + body
    sig = request.headers.get("X-Whop-Signature", "")
    payload = request.get_data(as_text=True)

    # Verify HMAC
    mac = hmac.new(WHOP_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(mac, sig):
        abort(400, "invalid signature")

    data = json.loads(payload)
    # Expected whop payload fields (adjust to your actual webhook schema):
    # - invoice_id: the invoice identifier
    # - buyer_id: the buyer/user identifier
    # - payment_method: the method name (e.g. "usdt", "usdc", "manual")
    # - paid_at: ISO timestamp of payment
    invoice_id = data.get("invoice_id") or data.get("id")
    buyer_id = data.get("buyer_id")
    method = data.get("payment_method") or data.get("method") or "unknown"
    paid_at = data.get("paid_at") or datetime.now(timezone.utc).isoformat()

    if not invoice_id or not buyer_id:
        abort(400, "missing invoice_id or buyer_id in payload")

    tenant = _get_tenant(buyer_id)
    rows_updated = _mark_paid(invoice_id, method, paid_at)

    print(f"[whop] invoice={invoice_id} buyer={buyer_id} method={method} "
          f"tenant={tenant} rows_updated={rows_updated}")

    return {"status": "ok", "rows_updated": rows_updated, "tenant": tenant}, 200


if __name__ == "__main__":
    # Listen on all interfaces so tunnel tools can reach it
    app.run(host="0.0.0.0", port=8082, threaded=True)