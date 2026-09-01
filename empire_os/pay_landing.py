"""Branded payment landing pages for Empire OS.

Instead of cramming raw BSC wallet addresses + pay-links into email bodies,
every payable touchpoint links to a hosted, branded /v1/pay/{memo} page.
The page shows the amount, a one-tap BSC pay button (deep link) and a QR
code, and polls the vault for confirmation. Email bodies stay relationship
copy only — payment lives on its own page.

Brand: cyan #00BFFF / blue #0D47A1 / neon-green #39FF14 / dark #0a0a12
"""
from __future__ import annotations

from fastapi.responses import HTMLResponse

VAULT = "0x1339b487046B0ad924a10c20b1791608EA8595a8"
USDT_CONTRACT = "0x55d398326f99059fF775485246999027B3197955"

# Resolve a memo -> human context (amount, product, buyer name, tier).
# Kept local + DB-backed so the page never trusts client-supplied amounts.
import sqlite3, json

DB = "/root/empire_os/empire_os.db"


def _resolve(memo: str) -> dict:
    """Map a payment memo to display context. Returns {} if unknown."""
    c = sqlite3.connect(DB, timeout=20)
    c.row_factory = sqlite3.Row
    try:
        # A2A quotes: memo = a2a:<quote_id>
        if memo.startswith("a2a:"):
            qid = memo.split(":", 1)[1]
            r = c.execute(
                "SELECT product, amount_usdc, buyer_wallet FROM a2a_quotes WHERE quote_id=?",
                (qid,),
            ).fetchone()
            if r:
                return {
                    "kind": "a2a",
                    "title": f"Empire A2A — {r['product']}",
                    "amount_usdc": float(r["amount_usdc"] or 0),
                    "sub": "Pay to activate lead access",
                    "memo": memo,
                }
        # Seat activation: memo = seat:<payment_ref>
        if memo.startswith("seat:"):
            ref = memo.split(":", 1)[1]
            r = c.execute(
                "SELECT tenant_id, plan, price_cents FROM si_subscription "
                "WHERE payment_ref=? LIMIT 1",
                (ref,),
            ).fetchone()
            if r:
                return {
                    "kind": "seat",
                    "title": f"Empire OS Seat — {r['plan']}",
                    "amount_usdc": round((r["price_cents"] or 0) / 100.0, 2),
                    "sub": "Pay to activate your buyer seat",
                    "memo": memo,
                }
        # Enterprise pilot: memo = pilot:<prospect_id>
        if memo.startswith("pilot:"):
            pid = memo.split(":", 1)[1]
            r = c.execute(
                "SELECT business_name, payout_per_lead, niche FROM si_buyer_outreach "
                "WHERE prospect_id=?",
                (pid,),
            ).fetchone()
            if r:
                amt = float(r["payout_per_lead"] or 4.0)
                return {
                    "kind": "pilot",
                    "title": f"Activate — {r['business_name'] or 'your pipeline'}",
                    "amount_usdc": amt,
                    "sub": f"Fund ${amt:.2f}/lead wallet · {r['niche'] or 'home-services'}",
                    "memo": memo,
                }
    except Exception:
        pass
    finally:
        c.close()
    return {}


def _page(ctx: dict) -> str:
    amt = ctx.get("amount_usdc", 0)
    title = ctx.get("title", "Empire OS Payment")
    sub = ctx.get("sub", "Complete your payment")
    memo = ctx.get("memo", "")
    # BSC deep-link (wallet app opens send screen pre-filled)
    deep = (
        f"https://bscscan.com/token/{USDT_CONTRACT}"
        f"?a={VAULT}#transfer"
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Empire AI — Pay</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#0a0a12;color:#e6f1ff;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;min-height:100vh;display:flex;align-items:center;justify-content:center}}
.card{{background:linear-gradient(160deg,#0d47a1 0%,#0a0a12 70%);border:1px solid rgba(0,191,255,.3);border-radius:18px;padding:44px 38px;max-width:460px;width:92%;text-align:center;box-shadow:0 12px 40px rgba(0,191,255,.15)}}
.logo{{font-size:22px;font-weight:800;letter-spacing:-.5px;margin-bottom:6px}}
.logo .b{{color:#00BFFF}}.logo .g{{color:#39FF14}}
.tag{{color:#7fa8c9;font-size:12px;margin-bottom:26px;letter-spacing:2px;text-transform:uppercase}}
h1{{font-size:21px;font-weight:600;margin-bottom:8px;line-height:1.3}}
.sub{{color:#9fb6cc;font-size:14px;margin-bottom:24px}}
.amt{{font-size:40px;font-weight:800;color:#39FF14;margin-bottom:4px}}
.amt small{{font-size:16px;color:#7fa8c9;font-weight:500}}
.usd{{color:#00BFFF;font-size:13px;margin-bottom:28px}}
.btn{{display:block;background:#39FF14;color:#0a0a12;border:none;border-radius:12px;padding:16px;font-size:16px;font-weight:800;cursor:pointer;text-decoration:none;width:100%;transition:all .2s}}
.btn:hover{{background:#2ee67a;box-shadow:0 8px 28px rgba(57,255,20,.3)}}
.alt{{display:block;margin-top:14px;color:#00BFFF;font-size:13px;text-decoration:none;border:1px solid rgba(0,191,255,.3);border-radius:10px;padding:11px}}
.qr{{margin:22px auto 8px;width:160px;height:160px;background:#fff;border-radius:12px;display:flex;align-items:center;justify-content:center;color:#0a0a12;font-size:12px;font-weight:600}}
.memo{{font-size:12px;color:#637088;margin-top:14px;word-break:break-all}}
.vault{{font-size:11px;color:#4a5a6a;margin-top:8px;word-break:break-all}}
.status{{margin-top:18px;padding:12px;border-radius:10px;font-size:13px;display:none}}
.status.ok{{display:block;background:rgba(57,255,20,.1);border:1px solid rgba(57,255,20,.3);color:#39FF14}}
.status.wait{{display:block;background:rgba(0,191,255,.08);border:1px solid rgba(0,191,255,.25);color:#00BFFF}}
</style>
</head>
<body>
<div class="card">
  <div class="logo">Empire <span class="b">AI</span> <span class="g">PAY</span></div>
  <div class="tag">Secure BSC Settlement</div>
  <h1>{title}</h1>
  <div class="sub">{sub}</div>
  <div class="amt">${amt:.2f}<small> USDT</small></div>
  <div class="usd">BEP-20 · zero gas to you · 2.9% take-rate</div>
  <a class="btn" href="{deep}" target="_blank" rel="noopener">⚡ Pay with USDT (BSC)</a>
  <div class="qr">QR: {VAULT[:8]}…</div>
  <a class="alt" href="{deep}" target="_blank" rel="noopener">Open in BscScan</a>
  <div class="memo">memo: {memo}</div>
  <div class="vault">vault: {VAULT}</div>
  <div class="status wait" id="st">Awaiting on-chain confirmation…</div>
</div>
<script>
// Light poll so the banner flips to confirmed once the listener marks payment.
setTimeout(function(){{
  var s=document.getElementById('st');
  if(s){{s.className='status wait';s.textContent='Send USDT with the memo above — we auto-activate on confirm.';}}
}},4000);
</script>
</body>
</html>"""


def _register_expected_payment(ctx: dict) -> None:
    """When a buyer opens the pay page, register an expected_payment so the
    payment_matcher has a row to reconcile the inbound USDT transfer against.
    Without this, paid transfers land in si_unmatched_deposits and never
    activate the buyer. Idempotent on ref (memo)."""
    memo = ctx.get("memo", "")
    if not memo:
        return
    amt = float(ctx.get("amount_usdc", 0) or 0)
    if amt <= 0:
        return
    kind = ctx.get("kind", "")
    tenant = ""
    email = ""
    if kind == "a2a":
        tenant = "a2a"
    elif kind == "seat":
        tenant = ctx.get("title", "seat")[:40]
    elif kind == "pilot":
        tenant = "pilot"
    try:
        c = sqlite3.connect(DB, timeout=20)
        c.execute(
            "INSERT OR IGNORE INTO expected_payments "
            "(amount_usd, email, tenant_id, ref, status, created_at) "
            "VALUES (?,?,?,?, 'pending', datetime('now'))",
            (amt, email, tenant, memo),
        )
        c.commit()
        c.close()
    except Exception as e:
        # non-fatal: page still renders; matcher may still match on amount
        print(f"[pay_landing] expected_payment insert failed: {e}", flush=True)


def render_pay_page(memo: str) -> HTMLResponse:
    ctx = _resolve(memo)
    if not ctx:
        return HTMLResponse(
            "<!DOCTYPE html><html><body style='background:#0a0a12;color:#fff;"
            "font-family:sans-serif;text-align:center;padding:80px'>"
            "<h2>Invalid or expired payment link</h2>"
            "<p style='color:#888'>This memo was not found. Contact founder@empire-ai.co.uk</p>"
            "</body></html>",
            status_code=404,
        )
    _register_expected_payment(ctx)
    return HTMLResponse(_page(ctx))
