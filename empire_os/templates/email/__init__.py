"""
Empire AI branded email templates.

Dark theme · neon green + cyan accents · multi-avenue aware.

Layout:
    brand.py          — palette, type, identity strings, avenue registry
    _chrome.py        — shared HTML header/footer/CTA + plain-text helpers
    outreach.py       — first-touch + follow-up templates (external B2B)
    internal.py       — operator notifications (delivered / settled)
    __init__.py       — public API

Public API:
    from empire_os.templates.email import (
        list_outreach, list_internal, render,
        OUTREACH_FIRST_TOUCH_VARS, brand,
    )
    html, text = render("outreach_first_touch", {
        "recipient_name": "Sarah",
        "niche": "roofing",
        "metro": "Dallas, TX",
        "source_detail": "23 verified reviews on Google",
    })

CLI:
    python -m empire_os.templates.email.cli list
    python -m empire_os.templates.email.cli render outreach_first_touch
       --recipient "Sarah" --niche roofing --metro "Dallas, TX"
       --source-detail "23 verified reviews on Google"
"""
from __future__ import annotations

from .brand import (
    AVENUES,
    DEFAULT_AVENUE,
    avenue_ids,
    get_avenue,
    css_vars,
    COMPANY_NAME, COMPANY_PARENT, COMPANY_URL,
    SUPPORT_EMAIL, UNSUB_BASE,
    NEON_GREEN, CYAN,
    BG_DEEP, BG_PANEL, BG_ELEVATED,
    BORDER, BORDER_STRONG,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
)
from .outreach import (
    outreach_first_touch, outreach_first_touch_subject, OUTREACH_FIRST_TOUCH_VARS,
    followup_nudge, followup_nudge_subject,
    followup_final, followup_final_subject,
    TEMPLATES as OUTREACH_TEMPLATES,
    list_templates as list_outreach,
    render_template,
)
from .internal import (
    lead_delivered, lead_delivered_subject,
    payout_settled, payout_settled_subject,
    INTERNAL_TEMPLATES,
    list_internal,
)


def render(template_name: str, vars: dict) -> tuple[str, str]:
    """Render (html, text) for a template by name. Searches both registries."""
    if template_name in OUTREACH_TEMPLATES:
        return OUTREACH_TEMPLATES[template_name]["render_fn"](vars)
    if template_name in INTERNAL_TEMPLATES:
        return INTERNAL_TEMPLATES[template_name]["render_fn"](vars)
    raise KeyError(
        f"unknown template '{template_name}'. "
        f"outreach: {list_outreach()}. internal: {list_internal()}"
    )


def render_subject(template_name: str, vars: dict) -> str:
    """Render the subject line for a template by name."""
    if template_name in OUTREACH_TEMPLATES:
        return OUTREACH_TEMPLATES[template_name]["subject_fn"](
            vars.get("niche", ""), vars.get("metro", ""),
            avenue_id=vars.get("avenue_id"),
        )
    if template_name in INTERNAL_TEMPLATES:
        if template_name == "lead_delivered":
            return lead_delivered_subject(vars.get("niche", ""), vars.get("metro", ""))
        if template_name == "payout_settled":
            return payout_settled_subject(vars.get("amount", ""), vars.get("period", "this week"))
    raise KeyError(f"unknown template '{template_name}'")


def list_all() -> list[str]:
    """All templates across both registries."""
    return list_outreach() + list_internal()


__all__ = [
    "AVENUES", "DEFAULT_AVENUE", "get_avenue", "avenue_ids",
    "NEON_GREEN", "CYAN",
    "BG_DEEP", "BG_PANEL", "BG_ELEVATED",
    "BORDER", "BORDER_STRONG",
    "TEXT_PRIMARY", "TEXT_SECONDARY", "TEXT_MUTED",
    "COMPANY_NAME", "COMPANY_PARENT", "COMPANY_URL",
    "OUTREACH_FIRST_TOUCH_VARS",
    "render", "render_subject",
    "list_outreach", "list_internal", "list_all",
]