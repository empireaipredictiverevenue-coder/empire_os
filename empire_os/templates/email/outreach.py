"""
Outreach templates — first-touch + follow-up sequences.

Each template:
    - subject(): (str) renders subject line, can be parameterized
    - render(vars: dict) -> (html: str, text: str)
    - Variables documented per template

Branded with Empire AI dark/neon palette. Each template accepts an
optional `avenue_id` to swap accent + footer for the business vertical
(leadgen / paypercall / saas / loans).
"""
from __future__ import annotations

from html import escape as _esc
from typing import Optional

from . import _chrome
from .brand import (
    BG_DEEP, BG_PANEL, BORDER,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    CYAN, NEON_GREEN,
    COMPANY_URL, get_avenue,
)


# ── First-touch: sample lead offer ────────────────────────

OUTREACH_FIRST_TOUCH_VARS = """
Required:
    recipient_name  str   "Hi {recipient_name}" — fallback "there"
    niche           str   "your {niche} firm"
    metro           str   "Dallas"
    source_detail   str   one-line context about the lead source
    sender_name     str   optional, falls back to "Empire OS team"

Optional:
    sample_url      str   CTA target (default: reply-to)
    tenant_id       str   for unsubscribe link (default "default")
    avenue_id       str   business vertical (default "leadgen")
"""


def outreach_first_touch_subject(
    niche: str, metro: str,
    avenue_id: Optional[str] = None,
) -> str:
    a = get_avenue(avenue_id)
    return f"{a['subject_prefix']}Sample {niche.strip()} lead for {metro.strip()}"


def outreach_first_touch(vars: dict) -> tuple[str, str]:
    """Returns (html, plain_text) for the first-touch outreach email."""
    avenue = get_avenue(vars.get("avenue_id"))
    name   = vars.get("recipient_name") or "there"
    niche  = vars.get("niche") or "home services"
    metro  = vars.get("metro") or "your market"
    detail = vars.get("source_detail") or "verified business listing"
    sender = vars.get("sender_name") or "Empire OS team"
    cta_url = vars.get("sample_url") or f"mailto:{vars.get('reply_to', 'ops@empire-ai.co.uk')}?subject=send%20sample"
    tenant  = vars.get("tenant_id", "default")

    # ── Plain text ──
    text = (
        f"Hi {name},\n\n"
        f"Quick one — we run a pay-per-delivered-lead service for "
        f"{niche} contractors in {metro}. Right now we're shipping a "
        f"sample lead (real customer, fresh) to verify quality before "
        f"any subscription.\n\n"
        f"From your listing: {detail[:140]}\n\n"
        f"Reply 'send sample' and we'll wire one free {niche} lead "
        f"in {metro} within 24h. No commitment, no card. "
        f"If it converts, we go from there.\n\n"
        f"-- {sender}\n"
    )
    text += _chrome.plain_signature(vars.get("avenue_id"))
    text += _chrome.plain_footer(vars.get("avenue_id"), tenant_id=tenant)

    # ── HTML ──
    preheader = f"Sample {niche} lead for {metro} — free, no commitment."
    html = _chrome.wrapper_open(preheader, avenue_id=vars.get("avenue_id"))
    html += _chrome.header_html(vars.get("avenue_id"))

    # Body
    accent = avenue["accent"]
    accent2 = avenue["accent2"]
    cta_label = avenue["primary_cta"]
    html += f"""
    <tr>
      <td class="pad" style="padding:32px;background:{BG_PANEL};font-family:-apple-system,Segoe UI,Roboto,sans-serif;color:{TEXT_PRIMARY};font-size:15px;line-height:24px;">
        <h1 style="margin:0 0 16px 0;font-size:22px;line-height:28px;color:{TEXT_PRIMARY};font-weight:700;">
          Hi {_esc(name)},
        </h1>
        <p style="margin:0 0 16px 0;color:{TEXT_PRIMARY};">
          Quick one — we run a <strong style="color:{accent};">pay-per-delivered-lead</strong>
          service for <strong>{_esc(niche)}</strong> contractors in
          <strong>{_esc(metro)}</strong>. We're shipping a sample lead
          (real customer, fresh) to verify quality before any subscription.
        </p>
        <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%"
               style="margin:20px 0;background:#0a1020;border-left:3px solid {accent};border-radius:4px;">
          <tr>
            <td style="padding:16px 20px;">
              <p style="margin:0 0 4px 0;font-size:11px;color:{TEXT_MUTED};text-transform:uppercase;letter-spacing:1px;">
                Listing context
              </p>
              <p style="margin:0;font-size:14px;line-height:20px;color:{TEXT_SECONDARY};">
                {_esc(detail[:200])}
              </p>
            </td>
          </tr>
        </table>
        <p style="margin:16px 0;color:{TEXT_PRIMARY};">
          Reply <strong style="color:{accent2};">'send sample'</strong> and we'll wire one
          free {_esc(niche)} lead in {_esc(metro)} within 24h.
          <span style="color:{TEXT_SECONDARY};">No commitment, no card.</span>
        </p>
    """
    html += _chrome.cta_button_html(cta_label, cta_url, avenue_id=vars.get("avenue_id"))
    html += f"""
        <p style="margin:24px 0 0 0;font-size:13px;color:{TEXT_MUTED};">
          — {_esc(sender)}
        </p>
      </td>
    </tr>
    """
    html += _chrome.footer_html(vars.get("avenue_id"), tenant_id=tenant)
    html += _chrome.wrapper_close()

    return html, text


# ── Follow-up #1 — nudge after 3 days ─────────────────────

def followup_nudge_subject(niche: str, metro: str, avenue_id: Optional[str] = None) -> str:
    a = get_avenue(avenue_id)
    return f"{a['subject_prefix']}Re: {niche.strip()} sample — still interested?"


def followup_nudge(vars: dict) -> tuple[str, str]:
    """3-day nudge. Low-friction. Includes soft out per email_expert rules."""
    avenue = get_avenue(vars.get("avenue_id"))
    name   = vars.get("recipient_name") or "there"
    niche  = vars.get("niche") or "home services"
    metro  = vars.get("metro") or "your market"
    tenant = vars.get("tenant_id", "default")
    accent = avenue["accent"]

    text = (
        f"Hi {name},\n\n"
        f"Following up on the {niche} sample lead offer for {metro}.\n\n"
        f"Still a fit? Reply 'send sample' and we'll wire one free lead\n"
        f"in 24h. Not a fit? Reply 'no thanks' and I'll close the loop.\n\n"
    )
    text += _chrome.plain_signature(vars.get("avenue_id"))
    text += _chrome.plain_footer(vars.get("avenue_id"), tenant_id=tenant)

    preheader = f"Quick follow-up on the {niche} sample offer."
    html = _chrome.wrapper_open(preheader, avenue_id=vars.get("avenue_id"))
    html += _chrome.header_html(vars.get("avenue_id"))
    html += f"""
    <tr>
      <td class="pad" style="padding:32px;background:{BG_PANEL};font-family:-apple-system,Segoe UI,Roboto,sans-serif;color:{TEXT_PRIMARY};font-size:15px;line-height:24px;">
        <h1 style="margin:0 0 16px 0;font-size:20px;color:{TEXT_PRIMARY};font-weight:700;">
          Hi {_esc(name)},
        </h1>
        <p style="margin:0 0 16px 0;color:{TEXT_PRIMARY};">
          Following up on the <strong style="color:{accent};">{_esc(niche)} sample lead</strong>
          offer for <strong>{_esc(metro)}</strong>.
        </p>
        <p style="margin:0 0 16px 0;color:{TEXT_PRIMARY};">
          Still a fit? Reply <strong style="color:{accent};">'send sample'</strong> and we'll wire
          one free lead in 24h.
        </p>
        <p style="margin:0;color:{TEXT_SECONDARY};">
          Not a fit? Reply <em>no thanks</em> and I'll close the loop.
        </p>
      </td>
    </tr>
    """
    html += _chrome.footer_html(vars.get("avenue_id"), tenant_id=tenant)
    html += _chrome.wrapper_close()

    return html, text


# ── Follow-up #2 — final close (7 days) ────────────────────

def followup_final_subject(niche: str, metro: str, avenue_id: Optional[str] = None) -> str:
    a = get_avenue(avenue_id)
    return f"{a['subject_prefix']}Closing the loop — {niche.strip()} {metro.strip()}"


def followup_final(vars: dict) -> tuple[str, str]:
    avenue = get_avenue(vars.get("avenue_id"))
    name   = vars.get("recipient_name") or "there"
    niche  = vars.get("niche") or "home services"
    metro  = vars.get("metro") or "your market"
    tenant = vars.get("tenant_id", "default")

    text = (
        f"Hi {name},\n\n"
        f"Last note on the {niche} sample for {metro}. I'm closing\n"
        f"this thread — no further follow-up unless you reply.\n\n"
        f"If timing changes, the door is open: just hit reply.\n\n"
    )
    text += _chrome.plain_signature(vars.get("avenue_id"))
    text += _chrome.plain_footer(vars.get("avenue_id"), tenant_id=tenant)

    preheader = "Closing the loop — no further follow-up."
    html = _chrome.wrapper_open(preheader, avenue_id=vars.get("avenue_id"))
    html += _chrome.header_html(vars.get("avenue_id"))
    html += f"""
    <tr>
      <td class="pad" style="padding:32px;background:{BG_PANEL};font-family:-apple-system,Segoe UI,Roboto,sans-serif;color:{TEXT_PRIMARY};font-size:15px;line-height:24px;">
        <h1 style="margin:0 0 16px 0;font-size:20px;color:{TEXT_PRIMARY};font-weight:700;">
          Hi {_esc(name)},
        </h1>
        <p style="margin:0 0 16px 0;color:{TEXT_PRIMARY};">
          Last note on the <strong>{_esc(niche)} sample</strong> for {_esc(metro)}.
          I'm closing this thread — no further follow-up unless you reply.
        </p>
        <p style="margin:0;color:{TEXT_SECONDARY};">
          If timing changes, the door is open: just hit reply.
        </p>
      </td>
    </tr>
    """
    html += _chrome.footer_html(vars.get("avenue_id"), tenant_id=tenant)
    html += _chrome.wrapper_close()

    return html, text


# ── Template registry ─────────────────────────────────────

TEMPLATES: dict[str, dict] = {
    "outreach_first_touch": {
        "subject_fn": outreach_first_touch_subject,
        "render_fn":  outreach_first_touch,
        "vars_doc":   OUTREACH_FIRST_TOUCH_VARS,
        "description": "First-touch cold outreach with free sample lead offer.",
    },
    "followup_nudge": {
        "subject_fn": followup_nudge_subject,
        "render_fn":  followup_nudge,
        "description": "3-day nudge with soft opt-out. Low-friction.",
    },
    "followup_final": {
        "subject_fn": followup_final_subject,
        "render_fn":  followup_final,
        "description": "7-day close. Explicit 'closing the loop' message.",
    },
}


def list_templates() -> list[str]:
    return list(TEMPLATES.keys())


def render_template(name: str, vars: dict) -> tuple[str, str]:
    """Render (html, text) for a named template. Raises KeyError on bad name."""
    tpl = TEMPLATES[name]
    return tpl["render_fn"](vars)