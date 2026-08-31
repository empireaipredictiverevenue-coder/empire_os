"""Empire AI email templates — branded HTML + plain-text, professional copy.

Brand: dark #0a1628, cyan #00BCD4, blue #2196F3, neon-green #00FF88.
Email-safe: 600px table layout, inline styles, no external assets.
Copy rules: no hype, no emoji, no ALL-CAPS headers, no price walls,
no raw wallet addresses in outbound blasts. One ask per email.
"""

BRAND_DARK = "#0a1628"
BRAND_CYAN = "#00BCD4"
BRAND_BLUE = "#2196F3"
BRAND_GREEN = "#00FF88"

ADDRESS = "Empire AI Ltd, 1 Revenue Row, London EC1A 1BB, United Kingdom"
UNSUB = "https://empire-ai.co.uk/unsubscribe"
PORTAL = "https://empire-ai.co.uk/buy-leads"


def _shell(preheader: str, content_rows: str) -> str:
    """Standard branded shell around content rows."""
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Empire AI</title></head>
<body style="margin:0;padding:0;background:#f2f4f7;">
<div style="display:none;max-height:0;overflow:hidden;">{preheader}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f2f4f7;padding:24px 0;">
<tr><td align="center">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:8px;overflow:hidden;font-family:Helvetica,Arial,sans-serif;">
<tr><td style="background:{BRAND_DARK};padding:20px 32px;">
<span style="color:{BRAND_CYAN};font-size:18px;font-weight:bold;letter-spacing:1px;">EMPIRE&nbsp;AI</span>
<span style="color:#8aa4b8;font-size:12px;display:block;margin-top:2px;">Lead intelligence for service markets</span>
</td></tr>
{content_rows}
<tr><td style="padding:20px 32px;background:{BRAND_DARK};">
<p style="color:#8aa4b8;font-size:11px;line-height:16px;margin:0;">
{ADDRESS}<br>
<a href="{UNSUB}" style="color:{BRAND_CYAN};text-decoration:none;">Unsubscribe</a> &middot;
<a href="{PORTAL}" style="color:{BRAND_CYAN};text-decoration:none;">Buyer portal</a></p>
</td></tr>
</table>
</td></tr></table>
</body></html>"""


def _button(url: str, label: str) -> str:
    return (f'<tr><td style="padding:8px 32px 28px;">'
            f'<a href="{url}" style="display:inline-block;background:{BRAND_BLUE};color:#ffffff;'
            f'font-size:15px;font-weight:bold;text-decoration:none;padding:12px 28px;border-radius:6px;">'
            f'{label}</a></td></tr>')


# ---------------------------------------------------------------- blast

def blast_subject(niche: str, metro: str, payout: float) -> str:
    """Quiet, specific subject. No brand name, no hype."""
    return f"{niche.title()} leads in {metro}, ${payout:.0f} per qualified lead"


CATALOGUE = [
    ("Pay-per-lead lane", "from $4.00/lead",
     "Exclusive leads in your niche and market. Verified, scored, pay only for qualified."),
    ("Lead Pack 50", "$497 one-time",
     "50 enrichment-complete leads (emails and phones), delivered in 48 hours."),
    ("Lead Pack 250", "$1,997 one-time",
     "250 enrichment-complete leads, delivered in 72 hours."),
    ("SERP Intent Sweep", "from $297",
     "100 or 250 businesses discovered from live search demand in your market, as CSV."),
    ("SERP Lane Feeder", "$897/month",
     "Automated weekly sweeps feeding your exclusive lane with fresh leads."),
    ("Deep Intel Report", "$997",
     "Competitor and revenue-leak analysis for one business, PDF within 24 hours."),
    ("SEO Audit / Content Brief", "from $97",
     "Technical audit of your site or a landing page brief built from real search demand."),
    ("AI Closer", "$299/month",
     "An agent that follows up and closes your leads, settled in USDT."),
    ("Enterprise Tier", "custom",
     "High-ticket enterprise onboarding: AI scoring + automated seller outreach, buyer_marketplace targeting, 13K leads/day pipeline. Requires registration and quote."),
]


def catalogue_text() -> str:
    lines = []
    for name, price, desc in CATALOGUE:
        lines.append(f"{name} ({price})\n  {desc}")
    return "\n".join(lines)


def blast_text(name: str, niche: str, metro: str, payout: float) -> str:
    first = name.split()[0] if name else "there"
    return f"""Hi {first},

We supply exclusive {niche} leads in {metro} to a small number of buyers per
market. Each lead is verified and scored before delivery, and you only pay
for qualified ones: ${payout:.2f} per lead, settled on delivery.

If you prefer a fixed batch, we also sell one-time lead packs (50 or 250
leads in your niche and market) and one-off market sweeps built from live
search demand. Full catalogue with prices: {PORTAL}

No contracts, no card. You set a monthly volume, we send leads, you pay
what you used.

If you want to see a sample of what we have in {metro} right now, just
reply "sample" to this email and I will send it over today.

Best regards,
Phillip
Founder, Empire AI
{ADDRESS}

Not interested? {UNSUB}
"""


def blast_html(name: str, niche: str, metro: str, payout: float) -> str:
    first = name.split()[0] if name else "there"
    sample_btn = _button(
        "mailto:founder@empire-ai.co.uk?subject=Sample%20leads%20in%20" + metro.replace(" ", "%20"),
        'Reply "sample" for a market sample')
    rows = f"""
<tr><td style="padding:28px 32px 8px;">
<h2 style="margin:0 0 16px;font-size:20px;color:{BRAND_DARK};">{niche.title()} leads in {metro}</h2>
<p style="margin:0 0 14px;font-size:15px;line-height:23px;color:#33475b;">
Hi {first},</p>
<p style="margin:0 0 14px;font-size:15px;line-height:23px;color:#33475b;">
We supply exclusive {niche} leads in {metro} to a small number of buyers per
market. Each lead is verified and scored before delivery, and you only pay
for qualified ones.</p>
<table role="presentation" cellpadding="0" cellspacing="0" style="margin:18px 0;">
<tr>
<td style="background:{BRAND_DARK};border-radius:6px;padding:14px 22px;text-align:center;margin-right:10px;">
<span style="color:{BRAND_GREEN};font-size:20px;font-weight:bold;display:block;">${payout:.2f}</span>
<span style="color:#8aa4b8;font-size:11px;">per qualified lead</span></td>
<td style="background:{BRAND_DARK};border-radius:6px;padding:14px 22px;text-align:center;">
<span style="color:{BRAND_CYAN};font-size:20px;font-weight:bold;display:block;">{metro}</span>
<span style="color:#8aa4b8;font-size:11px;">exclusive market</span></td>
</tr></table>
<p style="margin:0 0 6px;font-size:15px;line-height:23px;color:#33475b;">
Prefer a fixed batch? We also sell one-time lead packs (50 or 250 leads in
your niche and market) and one-off demand sweeps.
<a href="{PORTAL}" style="color:{BRAND_BLUE};text-decoration:none;">Full catalogue and prices &rarr;</a></p>
</td></tr>
{sample_btn}
"""
    return _shell(f"Exclusive {niche} leads in {metro}. Pay only for qualified ones.", rows)


# ---------------------------------------------------------------- auto-responder

def paylink_subject() -> str:
    return "Your Empire AI buyer seat, activation link inside"


def paylink_text(first: str, per_lead: str, pay_url: str) -> str:
    return f"""Hi {first},

Your buyer seat is set up. To activate it, send the seat payment using the
secure link below (USDT on the BSC network). The seat opens as soon as the
payment settles, usually within a minute.

Your activation link:
{pay_url}

Rate: ${per_lead} per qualified lead, exclusive to your market. Leads start
flowing to your seat once it is active.

If anything looks off with the link, just reply to this email.

Best regards,
Phillip
Founder, Empire AI
{ADDRESS}
"""


def paylink_html(first: str, per_lead: str, pay_url: str) -> str:
    rows = f"""
<tr><td style="padding:28px 32px 8px;">
<h2 style="margin:0 0 16px;font-size:20px;color:{BRAND_DARK};">Your buyer seat is ready</h2>
<p style="margin:0 0 14px;font-size:15px;line-height:23px;color:#33475b;">
Hi {first},</p>
<p style="margin:0 0 18px;font-size:15px;line-height:23px;color:#33475b;">
To activate your seat, send the seat payment below. It is USDT on the BSC
network and opens automatically once the payment settles, usually within a
minute.</p>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"
 style="background:{BRAND_DARK};border-radius:8px;margin:0 0 18px;">
<tr><td style="padding:18px 22px;">
<span style="color:#8aa4b8;font-size:11px;text-transform:uppercase;letter-spacing:1px;">Seat rate</span><br>
<span style="color:{BRAND_GREEN};font-size:24px;font-weight:bold;">${per_lead} per qualified lead</span><br>
<span style="color:#8aa4b8;font-size:12px;">Exclusive to your market. Pay only for what you use.</span>
</td></tr></table>
</td></tr>
{_button(pay_url, "Activate buyer seat")}
<tr><td style="padding:0 32px 24px;">
<p style="margin:0;font-size:12px;line-height:18px;color:#7a8ea0;">
Link not working? Copy this into your browser:<br>
<span style="word-break:break-all;">{pay_url}</span></p>
</td></tr>
"""
    return _shell("Your Empire AI buyer seat and activation link.", rows)


def info_text() -> str:
    return f"""Hi,

Thanks for getting in touch. Empire AI supplies exclusive, verified and
scored B2B leads, settled in USDT on the BSC network. You pay per qualified
lead, with no contract and no card.

What we sell:

{catalogue_text()}

You can browse everything with prices here:
{PORTAL}

Or reply to this email with the market and volume you need, and we will set
up your buyer seat with a pay link straight away.

Best regards,
Phillip
Founder, Empire AI
{ADDRESS}
"""


def info_html() -> str:
    items = "".join(
        f'<tr><td style="padding:10px 0;border-bottom:1px solid #e3e8ef;">'
        f'<span style="font-size:14px;font-weight:bold;color:{BRAND_DARK};">{name}</span> '
        f'<span style="font-size:12px;color:{BRAND_BLUE};font-weight:bold;">{price}</span><br>'
        f'<span style="font-size:13px;line-height:19px;color:#5a6b7d;">{desc}</span></td></tr>'
        for name, price, desc in CATALOGUE)
    rows = f"""
<tr><td style="padding:28px 32px 8px;">
<h2 style="margin:0 0 16px;font-size:20px;color:{BRAND_DARK};">What we sell</h2>
<p style="margin:0 0 14px;font-size:15px;line-height:23px;color:#33475b;">
Thanks for getting in touch. Empire AI supplies verified and scored leads to
a small number of buyers per market. Everything is settled in USDT on the
BSC network. No contract, no card.</p>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0">
{items}
</table>
</td></tr>
{_button(PORTAL, "Browse the full catalogue")}
<tr><td style="padding:0 32px 24px;">
<p style="margin:0;font-size:14px;line-height:21px;color:#33475b;">
Or reply with the market and volume you need and we will set up your buyer
seat with an activation link straight away.</p>
</td></tr>
"""
    return _shell("Products, lead packs and pricing.", rows)


def unsub_text() -> str:
    return f"""Hi,

You have been removed from our list and will not receive further emails
from us. If this was a mistake, reply to this email and we will put you
back on.

Best regards,
Phillip
Founder, Empire AI
{ADDRESS}
"""


def unsub_html() -> str:
    rows = """
<tr><td style="padding:28px 32px 28px;">
<h2 style="margin:0 0 16px;font-size:20px;color:#%s;">You are unsubscribed</h2>
<p style="margin:0;font-size:15px;line-height:23px;color:#33475b;">
You have been removed from our list and will not receive further emails
from us. If this was a mistake, reply to this email and we will put you
back on.</p>
</td></tr>
""" % BRAND_DARK.lstrip("#")
    return _shell("Unsubscription confirmed.", rows)
