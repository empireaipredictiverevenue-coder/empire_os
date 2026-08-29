"""Branded HTML email templates — Empire AI.

Brand: cyan #00BFFF / blue #0D47A1 / neon-green #39FF14 / dark #0a0a12
Rule: NO raw wallet / pay-link in body. Body = relationship + value.
Payment lives on /v1/pay/{memo} (branded page). Body links there.
"""
from __future__ import annotations

HUB_BASE = "http://10.118.155.218:8081"
VAULT = "0x1339b487046B0ad924a10c20b1791608EA8595a8"

_LOGO = """<div style="font:800 20px/1 -apple-system,Segoe UI,Roboto,sans-serif">
  Empire <span style="color:#00BFFF">AI</span> <span style="color:#39FF14">PAY</span>
</div>"""

_BTN = (
    '<a href="{url}" style="display:inline-block;background:#39FF14;color:#0a0a12;'
    'font:800 15px/1 sans-serif;text-decoration:none;padding:14px 28px;'
    'border-radius:10px;margin:18px 0">⚡ Activate &amp; Pay</a>'
)


def _wrap(inner: str) -> str:
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;background:#0a0a12;padding:24px">
<table width="100%" cellpadding="0" cellspacing="0"><tr><td align="center">
<table width="100%" cellpadding="0" cellspacing="0"
 style="max-width:520px;background:linear-gradient(160deg,#0d47a1,#0a0a12);
 border:1px solid rgba(0,191,255,.3);border-radius:16px;overflow:hidden">
 <tr><td style="padding:28px 30px 10px">{_LOGO}
   <div style="color:#7fa8c9;font:11px/1 sans-serif;letter-spacing:2px;
    text-transform:uppercase;margin-top:6px">Exclusive B2B Lead Marketplace</div></td></tr>
 <tr><td style="padding:10px 30px 30px;color:#e6f1ff;
   font:15px/1.6 -apple-system,Segoe UI,Roboto,sans-serif">{inner}</td></tr>
 <tr><td style="padding:0 30px 26px;color:#4a5a6a;font:12px/1.5 sans-serif">
   Empire AI · founder@empire-ai.co.uk · Reply to this email anytime.
 </td></tr>
</table></td></tr></table></body></html>"""


def pilot_activate(name: str, niche: str, amount: float, memo: str) -> tuple[str, str]:
    """Enterprise pilot activation — relationship first, pay on separate page."""
    url = f"{HUB_BASE}/v1/pay/{memo}"
    subject = f"Philip — your {niche} leads are scored & ready (one click to activate)"
    inner = f"""
<p style="margin:0 0 14px">Hi {name or 'there'},</p>
<p style="margin:0 0 14px">We pulled <b>4,666 Omega-scored {niche or 'home-services'}</b> buyers
through our network — BRONZE to PLATINUM, each with verified intent and a funding path.
Your lane is reserved; nobody else gets those leads.</p>
<p style="margin:0 0 14px">Most buyers sit on leads that never convert. Ours settle in USDT on
BSC the moment a deal closes — you only pay per qualified lead that lands in your CRM.</p>
<p style="margin:0 0 4px;color:#39FF14;font-weight:700">What you get</p>
<p style="margin:0 0 14px">• Exclusive lane · zero competition<br>
• HMAC-signed lead POSTs straight to your endpoint<br>
• ${amount:.2f}/lead, 2.9% take-rate, no gas fees</p>
{_BTN.format(url=url)}
<p style="margin:0;color:#9fb6cc;font-size:13px">One payment activates the stream.
Questions? Just hit reply — I read every one.</p>
"""
    return subject, _wrap(inner)


def value_first_audit(name: str, niche: str, memo: str) -> tuple[str, str]:
    """Campaign A — value first, free audit, soft CTA to pay page."""
    url = f"{HUB_BASE}/v1/pay/{memo}"
    subject = f"Free {niche} lead audit — 3 min, no card"
    inner = f"""
<p style="margin:0 0 14px">Hi {name or 'there'},</p>
<p style="margin:0 0 14px">Quick one: we mapped the {niche or 'home-services'} buyer demand in your
metro and found gaps most agencies miss. I'll send your free audit — no strings.</p>
<p style="margin:0 0 14px">If the numbers look right, you can flip on a $10 trial and get live
Omega-scored leads in your inbox within the hour.</p>
{_BTN.format(url=url)}
<p style="margin:0;color:#9fb6cc;font-size:13px">Worst case you get a free audit. Best case,
your pipeline fills itself. Reply 'AUDIT' and I'll personalize it.</p>
"""
    return subject, _wrap(inner)


def a2a_pay(name: str, product: str, amount: float, memo: str) -> tuple[str, str]:
    """A2A quote reminder — links to branded pay page, no raw wallet in body."""
    url = f"{HUB_BASE}/v1/pay/{memo}"
    subject = f"Your {product} access is one tap from live"
    inner = f"""
<p style="margin:0 0 14px">Hi {name or 'Buyer'},</p>
<p style="margin:0 0 14px">Your <b>{product}</b> quote ({amount:.2f} USDT) is locked in.
Pay and verified leads start streaming to your endpoint immediately — HMAC-signed,
zero manual work.</p>
{_BTN.format(url=url)}
<p style="margin:0;color:#9fb6cc;font-size:13px">Memo is pre-filled. Pay, and we auto-activate.
Stuck? Reply and I'll sort it.</p>
"""
    return subject, _wrap(inner)


def seat_nudge(name: str, plan: str, amount: float, memo: str) -> tuple[str, str]:
    """Seat reservation nudge — branded, pay on page."""
    url = f"{HUB_BASE}/v1/pay/{memo}"
    subject = f"Your Empire OS {plan} seat is held — activate when ready"
    inner = f"""
<p style="margin:0 0 14px">Hi {name or 'there'},</p>
<p style="margin:0 0 14px">Your <b>{plan}</b> buyer seat (${amount:.0f}/mo) is reserved — exclusive
leads in your lane, nobody else competes for them.</p>
<p style="margin:0 0 14px">Activate whenever you're ready. The seat stays warm until you do.</p>
{_BTN.format(url=url)}
<p style="margin:0;color:#9fb6cc;font-size:13px">Seat ref pre-filled. One payment = live in minutes.</p>
"""
    return subject, _wrap(inner)
