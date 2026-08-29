"""Select-Serve portal — self-serve buyer seat + lane apply.

Exposes:
  GET  /v1/select-serve        -> HTML portal (free lanes + tier pricing)
  POST /v1/select-serve/apply -> onboard buyer, return Solana Pay URL
"""
from __future__ import annotations
import sqlite3
from pathlib import Path
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from empire_os import auto_onboard as ao

DB = "/root/empire_os/empire_os.db"
TIER_ORDER = ["bronze", "silver", "gold", "platinum"]

router = APIRouter(prefix="/v1/select-serve", tags=["select-serve"])


def _db():
    c = sqlite3.connect(DB, timeout=30)
    c.row_factory = sqlite3.Row
    return c


def _free_lanes(limit: int = 50) -> list[dict]:
    c = _db()
    try:
        rows = c.execute(
            "SELECT id, category, sub_niche, metro, seat_price FROM lanes "
            "WHERE occupied_by IS NULL ORDER BY category, sub_niche, metro LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        c.close()


def _tier_options() -> list[dict]:
    out = []
    for t in TIER_ORDER:
        r = ao.rate_for_tier(t)
        out.append({
            "tier": t,
            "monthly_usd": r["monthly"] / 100,
            "per_lead_usd": r["per_lead"] / 100,
        })
    return out


def _portal_html() -> str:
    lanes = _free_lanes()
    tiers = _tier_options()
    tier_rows = "".join(
        f"<tr><td>{t['tier'].title()}</td><td>${t['monthly_usd']:.0f}/mo</td>"
        f"<td>${t['per_lead_usd']:.2f}/lead</td></tr>" for t in tiers
    )
    lane_opts = "".join(
        f"<option value='{l['id']}'>{l['category']} / {l['sub_niche']} / {l['metro']}"
        f" (${l['seat_price']:.0f})</option>" for l in lanes
    )
    tier_opts = "".join(
        f"<option value='{t['tier']}'>{t['tier'].title()} — ${t['monthly_usd']:.0f}/mo</option>"
        for t in tiers
    )
    return f"""<!doctype html><html><head><meta charset=utf-8>
<title>Empire OS — Select &amp; Serve</title>
<style>body{{font-family:system-ui;background:#0b0e14;color:#e6e6e6;max-width:760px;margin:auto;padding:24px}}
h1{{color:#7cf}}table{{width:100%;border-collapse:collapse}}td,th{{padding:8px;border-bottom:1px solid #222;text-align:left}}
select,input,button{{background:#161b22;color:#e6e6e6;border:1px solid #333;padding:8px;margin:6px 0;width:100%}}
button{{background:#1f6feb;cursor:pointer;font-weight:600}}</style></head><body>
<h1>Empire OS — Select &amp; Serve</h1>
<p>Claim a lane seat. Pay USDT on BSC. Get a Solana Pay link instantly.</p>
<h3>Tier pricing</h3><table><tr><th>Tier</th><th>Monthly seat</th><th>Per-lead</th></tr>{tier_rows}</table>
<h3>Apply</h3>
<form id=f onsubmit="return apply(event)">
<label>Name<input name=name required></label>
<label>Email<input name=email type=email required></label>
<label>Tier<select name=tier>{tier_opts}</select></label>
<label>Niche<input name=niche placeholder="roofing / hvac / mass_torts" required></label>
<label>Lane<select name=lane_id>{lane_opts}</select></label>
<button type=submit>Get my seat</button></form>
<pre id=out></pre>
<script>
async function apply(e){{e.preventDefault();
const fd=new FormData(document.getElementById('f'));
const body=Object.fromEntries(fd);
const r=await fetch('/v1/select-serve/apply',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(body)}});
const j=await r.json();
document.getElementById('out').textContent=JSON.stringify(j,null,2);
}}</script></body></html>"""


@router.get("", response_class=HTMLResponse)
async def portal():
    return _portal_html()


@router.post("/apply")
async def apply(req: Request):
    try:
        data = await req.json()
    except Exception:
        return JSONResponse(status_code=400, content={"ok": False, "error": "invalid json"})
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip()
    niche = (data.get("niche") or "").strip()
    tier = (data.get("tier") or ao.DEFAULT_TIER).lower()
    if not name or not email or not niche:
        return JSONResponse(status_code=400, content={"ok": False, "error": "name, email, niche required"})
    res = ao.onboard(name, niche, tier, delivery_email=email, source="select_serve")
    if not res.get("ok"):
        return JSONResponse(status_code=500, content={"ok": False, "error": "onboard failed", "detail": res})
    pay = res.get("payment") or {}
    return JSONResponse(content={
        "ok": True,
        "tenant_id": res.get("tenant_id"),
        "subscription_id": res.get("subscription_id"),
        "tier": res.get("tier"),
        "amount_usdc_due": res.get("amount_usdc_due"),
        "pay_url": pay.get("pay_url", ""),
        "vault_wallet": pay.get("vault_wallet", ""),
        "memo": pay.get("memo", ""),
        "seated": res.get("seated"),
    })
