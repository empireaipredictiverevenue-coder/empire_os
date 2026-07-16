"""
Shared HTML chrome — header bar, logo block, footer with compliance.
Used by every branded email template. Plain text version returned
alongside HTML for clients that refuse HTML.
"""
from __future__ import annotations

from html import escape as _esc
from typing import Optional

from .brand import (
    BG_DEEP, BG_PANEL, BG_ELEVATED, BORDER, BORDER_STRONG,
    NEON_GREEN, NEON_GREEN_DIM, CYAN, CYAN_DIM,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    COMPANY_NAME, COMPANY_PARENT, COMPANY_URL, SUPPORT_EMAIL, UNSUB_BASE,
    css_vars, get_avenue,
)


# ── Logo SVG ──────────────────────────────────────────────
# Minimal mark: stylized "EA" with a neon slash. Inline so emails
# don't need external asset hosting.
LOGO_SVG = """\
<svg xmlns="http://www.w3.org/2000/svg" width="120" height="32" viewBox="0 0 120 32" role="img" aria-label="Empire AI">
  <defs>
    <linearGradient id="g" x1="0" x2="1" y1="0" y2="1">
      <stop offset="0%" stop-color="#39ff88"/>
      <stop offset="100%" stop-color="#22e3ff"/>
    </linearGradient>
  </defs>
  <rect x="0" y="4" width="3" height="24" fill="url(#g)"/>
  <text x="10" y="23" font-family="-apple-system,Segoe UI,Roboto,sans-serif"
        font-size="18" font-weight="700" fill="#e6f1ff" letter-spacing="0.5">
    EMPIRE<tspan fill="url(#g)"> AI</tspan>
  </text>
</svg>
"""


def header_html(avenue_id: Optional[str] = None) -> str:
    """Top header bar with logo + avenue tagline."""
    a = get_avenue(avenue_id)
    return f"""
    <tr>
      <td style="padding:24px 32px 16px 32px;background:{BG_DEEP};border-bottom:1px solid {BORDER};">
        <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%">
          <tr>
            <td align="left">{LOGO_SVG}</td>
            <td align="right" style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;font-size:12px;color:{TEXT_MUTED};">
              {_esc(a['tagline'])}
            </td>
          </tr>
        </table>
      </td>
    </tr>
    """


def footer_html(
    avenue_id: Optional[str] = None,
    *,
    tenant_id: str = "default",
    include_unsub: bool = True,
) -> str:
    """Bottom footer with compliance, identity, unsubscribe."""
    a = get_avenue(avenue_id)
    unsub_url = f"{UNSUB_BASE}/{tenant_id}"
    year = "2026"
    return f"""
    <tr>
      <td style="padding:24px 32px;background:{BG_PANEL};border-top:1px solid {BORDER};font-family:-apple-system,Segoe UI,Roboto,sans-serif;font-size:12px;line-height:18px;color:{TEXT_MUTED};">
        <p style="margin:0 0 8px 0;color:{TEXT_SECONDARY};">
          <strong style="color:{TEXT_PRIMARY};">{_esc(COMPANY_NAME)}</strong> · {_esc(COMPANY_PARENT)} platform
        </p>
        <p style="margin:0 0 8px 0;">
          <a href="{COMPANY_URL}" style="color:{CYAN};text-decoration:none;">{COMPANY_URL}</a>
          &nbsp;·&nbsp;
          <a href="mailto:{SUPPORT_EMAIL}" style="color:{CYAN};text-decoration:none;">{SUPPORT_EMAIL}</a>
        </p>
        <p style="margin:8px 0 0 0;">
          {_esc(a['name'])} · {year} · {_esc(a['id'])} channel
        </p>
        {f'<p style="margin:12px 0 0 0;"><a href="{unsub_url}" style="color:{CYAN_DIM};text-decoration:underline;">Unsubscribe from {_esc(a["name"])}</a></p>' if include_unsub else ''}
      </td>
    </tr>
    """


def cta_button_html(label: str, url: str, avenue_id: Optional[str] = None) -> str:
    """Solid neon button. Falls back gracefully in clients without button support."""
    a = get_avenue(avenue_id)
    accent = a["accent"]
    accent_dim = a["accent2"]
    return f"""
    <table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:24px 0;">
      <tr>
        <td style="background:{accent};border-radius:6px;">
          <a href="{url}" target="_blank"
             style="display:inline-block;padding:14px 28px;font-family:-apple-system,Segoe UI,Roboto,sans-serif;font-size:15px;font-weight:700;color:{BG_DEEP};text-decoration:none;letter-spacing:0.3px;">
            {_esc(label)} &rarr;
          </a>
        </td>
      </tr>
    </table>
    """


def wrapper_open(preheader: str = "", avenue_id: Optional[str] = None) -> str:
    """Outer HTML doc + body open. preheader is hidden preview text."""
    a = get_avenue(avenue_id)
    return f"""<!DOCTYPE html>
<html lang="en" xmlns="http://www.w3.org/1999/xhtml" xmlns:o="urn:schemas-microsoft-com:office:office">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="color-scheme" content="dark">
  <meta name="supported-color-schemes" content="dark">
  <title>{_esc(a['name'])}</title>
  <style>{css_vars(avenue_id)}
    body {{ margin:0;padding:0;background:{BG_DEEP};color:{TEXT_PRIMARY};font-family:-apple-system,Segoe UI,Roboto,sans-serif;-webkit-font-smoothing:antialiased; }}
    a {{ color:{CYAN}; }}
    table {{ border-collapse:collapse; }}
    .preheader {{ display:none !important;visibility:hidden;mso-hide:all;font-size:1px;color:{BG_DEEP};line-height:1px;max-height:0;max-width:0;opacity:0;overflow:hidden; }}
    @media only screen and (max-width:600px) {{
      .container {{ width:100% !important; }}
      .pad {{ padding-left:20px !important;padding-right:20px !important; }}
    }}
  </style>
</head>
<body style="background:{BG_DEEP};">
  <span class="preheader">{_esc(preheader)}</span>
  <table role="presentation" class="container" cellpadding="0" cellspacing="0" border="0" width="600" align="center" style="width:600px;margin:0 auto;background:{BG_PANEL};border:1px solid {BORDER};border-radius:8px;overflow:hidden;">
"""


def wrapper_close() -> str:
    return """
  </table>
</body>
</html>
"""


# ── Plain-text companions ─────────────────────────────────

def plain_footer(avenue_id: Optional[str] = None, *, tenant_id: str = "default") -> str:
    a = get_avenue(avenue_id)
    unsub_url = f"{UNSUB_BASE}/{tenant_id}"
    return (
        f"\n\n--\n"
        f"{a['name']}\n"
        f"{COMPANY_URL}\n"
        f"{SUPPORT_EMAIL}\n"
        f"Unsubscribe: {unsub_url}\n"
    )


def plain_signature(avenue_id: Optional[str] = None) -> str:
    a = get_avenue(avenue_id)
    return (
        f"-- \n"
        f"{COMPANY_NAME} | {a['name']}\n"
        f"{COMPANY_URL}\n"
    )