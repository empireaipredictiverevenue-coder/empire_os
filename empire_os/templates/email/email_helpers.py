"""Empire OS outbound email helpers (Phase 0).

Renders dark/neon-green/cyan branded HTML. All links go through the cloak
(/r/) and the payment page (/pay/) — never a raw vault address in the body.
Outbound only via Brevo (EMAIL_BACKEND=brevo). No SendGrid.
"""
import urllib.parse as _up

COMPANY = "Empire OS"
FROM = "Empire OS <founder@empire-ai.co.uk>"
UNSUB_BASE = "https://empire-ai.co.uk/unsub"
PIXEL_BASE = "https://empire-ai.co.uk/px"
HUB_REGISTER = "http://127.0.0.1:8081/v1/link/register"

_BG = "#050810"; _PANEL = "#0c1320"; _ELEV = "#131c2e"; _BORDER = "#1f2a44"
_GREEN = "#39ff88"; _CYAN = "#22e3ff"; _TXT = "#e6f1ff"; _MUTED = "#5a6c85"


def wrap(subject: str, preheader: str, body_html: str, email: str,
         unsub_url: str = None) -> str:
    unsub = unsub_url or f"{UNSUB_BASE}?email={_up.quote(email or '')}"
    pixel = f"{PIXEL_BASE}/{_up.quote(email or 'anon')}"
    return f"""<!doctype html><html><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>{subject}</title></head><body style="margin:0;background:{_BG};
padding:24px 0;font-family:-apple-system,Segoe UI,Roboto,sans-serif">
<center><table width=600 cellpadding=0 cellspacing=0 style="max-width:600px;
background:{_PANEL};border:1px solid {_BORDER};border-radius:14px;
overflow:hidden"><tr><td style="padding:28px 32px">
<div style="font-size:13px;letter-spacing:.08em;text-transform:uppercase;
color:{_GREEN};font-weight:700">{COMPANY}</div>
<h1 style="color:{_TXT};font-size:22px;margin:8px 0 4px">{subject}</h1>
<div style="color:{_MUTED};font-size:13px;margin-bottom:20px">{preheader}</div>
<div style="color:{_TXT};font-size:15px;line-height:1.6">{body_html}</div>
</td></tr><tr><td style="padding:18px 32px;background:{_ELEV};border-top:1px solid {_BORDER}">
<div style="color:{_MUTED};font-size:11px;line-height:1.5">
You received this because you opted in to Empire OS operator updates.<br>
<a href="{unsub}" style="color:{_CYAN}">Unsubscribe</a> ·
<a href="https://empire-ai.co.uk" style="color:{_CYAN}">empire-ai.co.uk</a>
</div></td></tr></table></center>
<img src="{pixel}" width=1 height=1 alt="" style="display:none">
</body></html>"""


def pay_link(memo: str, amt_usdc: float) -> str:
    return f"https://empire-ai.co.uk/pay/{_up.quote(memo)}?amt={amt_usdc:.2f}"


def cloak(long_url: str, source: str = None) -> str:
    try:
        import urllib.request, json
        q = f"?url={_up.quote(long_url)}"
        if source:
            q += f"&source={_up.quote(source)}"
        req = urllib.request.Request(HUB_REGISTER + q, method="POST")
        with urllib.request.urlopen(req, timeout=10) as r:
            d = json.load(r)
            if d.get("short_url"):
                return d["short_url"]
    except Exception:
        pass
    return long_url
