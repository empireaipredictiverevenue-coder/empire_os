"""
Internal/system templates — onboarding, billing, alerts.

Distinct from outreach.py (external B2B) — these go to operators,
internal staff, or trusted partners. Same brand kit, different tone.
"""
from __future__ import annotations

from html import escape as _esc
from typing import Optional

from . import _chrome
from .brand import BG_PANEL, BORDER, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED, NEON_GREEN, CYAN, get_avenue


# ── Lead delivered (operator notification) ────────────────

def lead_delivered_subject(niche: str, metro: str) -> str:
    return f"[Empire OS] New {niche.strip()} lead delivered — {metro.strip()}"


def lead_delivered(vars: dict) -> tuple[str, str]:
    """Sent to the buyer the moment a lead settles in their queue."""
    name    = vars.get("recipient_name") or "team"
    niche   = vars.get("niche") or "home services"
    metro   = vars.get("metro") or "your market"
    lead_id = vars.get("lead_id") or "n/a"
    cta_url = vars.get("lead_url") or "https://empire-ai.co.uk/dashboard"
    tenant  = vars.get("tenant_id", "default")

    text = (
        f"Hi {name},\n\n"
        f"A new {niche} lead just landed in your queue ({metro}).\n\n"
        f"Lead ID: {lead_id}\n"
        f"Open it: {cta_url}\n\n"
        f"You have 10 minutes to claim before it expires.\n\n"
    )
    text += _chrome.plain_signature("leadgen")
    text += _chrome.plain_footer("leadgen", tenant_id=tenant)

    preheader = f"New {niche} lead in {metro} — claim within 10 min."
    html = _chrome.wrapper_open(preheader, avenue_id="leadgen")
    html += _chrome.header_html("leadgen")
    html += f"""
    <tr>
      <td class="pad" style="padding:32px;background:{BG_PANEL};font-family:-apple-system,Segoe UI,Roboto,sans-serif;color:{TEXT_PRIMARY};font-size:15px;line-height:24px;">
        <h1 style="margin:0 0 12px 0;font-size:22px;color:{TEXT_PRIMARY};font-weight:700;">
          New lead delivered
        </h1>
        <p style="margin:0 0 16px 0;color:{TEXT_SECONDARY};">
          Hi {_esc(name)} — a fresh <strong style="color:{NEON_GREEN};">{_esc(niche)}</strong>
          lead just landed in your queue ({_esc(metro)}).
        </p>
        <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%"
               style="margin:20px 0;background:#0a1020;border:1px solid {BORDER};border-radius:6px;">
          <tr>
            <td style="padding:16px 20px;">
              <p style="margin:0 0 4px 0;font-size:11px;color:{TEXT_MUTED};text-transform:uppercase;letter-spacing:1px;">
                Lead ID
              </p>
              <p style="margin:0;font-family:'SF Mono',Menlo,Consolas,monospace;font-size:14px;color:{CYAN};">
                {_esc(lead_id)}
              </p>
            </td>
          </tr>
        </table>
        <p style="margin:16px 0;color:{TEXT_PRIMARY};">
          You have <strong style="color:{NEON_GREEN};">10 minutes</strong> to claim
          before it expires.
        </p>
    """
    html += _chrome.cta_button_html("Claim lead", cta_url, avenue_id="leadgen")
    html += """
      </td>
    </tr>
    """
    html += _chrome.footer_html("leadgen", tenant_id=tenant)
    html += _chrome.wrapper_close()

    return html, text


# ── Payout settled (operator notification) ────────────────

def payout_settled_subject(amount: str, period: str = "this week") -> str:
    return f"[Empire OS] Payout settled — {amount} ({period})"


def payout_settled(vars: dict) -> tuple[str, str]:
    name   = vars.get("recipient_name") or "team"
    amount = vars.get("amount") or "$0.00"
    period = vars.get("period") or "this week"
    method = vars.get("method") or "USDC"
    txid   = vars.get("tx_id") or "n/a"
    tenant = vars.get("tenant_id", "default")

    text = (
        f"Hi {name},\n\n"
        f"Payout settled: {amount} ({period})\n"
        f"Method: {method}\n"
        f"Tx: {txid}\n\n"
    )
    text += _chrome.plain_signature("leadgen")
    text += _chrome.plain_footer("leadgen", tenant_id=tenant)

    preheader = f"Payout {amount} sent via {method}."
    html = _chrome.wrapper_open(preheader, avenue_id="leadgen")
    html += _chrome.header_html("leadgen")
    html += f"""
    <tr>
      <td class="pad" style="padding:32px;background:{BG_PANEL};font-family:-apple-system,Segoe UI,Roboto,sans-serif;color:{TEXT_PRIMARY};font-size:15px;line-height:24px;">
        <h1 style="margin:0 0 12px 0;font-size:22px;color:{TEXT_PRIMARY};font-weight:700;">
          Payout settled
        </h1>
        <p style="margin:0 0 16px 0;color:{TEXT_SECONDARY};">
          Hi {_esc(name)} — {_esc(amount)} sent via {_esc(method)} for {_esc(period)}.
        </p>
        <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%"
               style="margin:20px 0;background:#0a1020;border:1px solid {BORDER};border-radius:6px;">
          <tr>
            <td style="padding:16px 20px;">
              <p style="margin:0 0 4px 0;font-size:11px;color:{TEXT_MUTED};text-transform:uppercase;letter-spacing:1px;">
                Transaction
              </p>
              <p style="margin:0;font-family:'SF Mono',Menlo,Consolas,monospace;font-size:13px;color:{CYAN};word-break:break-all;">
                {_esc(txid)}
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
    """
    html += _chrome.footer_html("leadgen", tenant_id=tenant)
    html += _chrome.wrapper_close()

    return html, text


# ── Registry ──────────────────────────────────────────────

INTERNAL_TEMPLATES: dict[str, dict] = {
    "lead_delivered": {
        "subject_fn": lead_delivered_subject,
        "render_fn":  lead_delivered,
        "description": "Operator notification: new lead ready to claim.",
    },
    "payout_settled": {
        "subject_fn": payout_settled_subject,
        "render_fn":  payout_settled,
        "description": "Operator notification: payout settled.",
    },
}


def list_internal() -> list[str]:
    return list(INTERNAL_TEMPLATES.keys())