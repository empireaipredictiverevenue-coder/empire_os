#!/usr/bin/env python3
"""render_founder_email.py — render the branded Empire OS founder email.

Usage:
  from render_founder_email import render_email
  html, text, subject = render_email(
      business_name="ABC Roofing",
      city="Houston",
      state="TX",
      niche="roofing"
  )

Template: dark theme with neon green (#39ff14) + cyan (#00ffff) accents,
fully inline-CSS for maximum email client compatibility.
"""
import re
from pathlib import Path

TEMPLATE_DIR = Path("/root/empire_os/email_templates")


def _strip_html(html: str) -> str:
    """Best-effort HTML→text for the text alternative."""
    text = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&#39;", "'", text)
    text = re.sub(r"&quot;", chr(34), text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def render_email(
    business_name: str,
    city: str,
    state: str,
    niche: str,
    metro: str | None = None,
    phone: str | None = None,
    extra_intro: str | None = None,
) -> tuple[str, str, str]:
    """Return (html, text, subject) for the founder pricing email.

    Variables substituted:
      {business_name}, {city}, {state}, {niche}, {business_short},
      {metro}, {phone}, {extra_intro}
    """
    html = (TEMPLATE_DIR / "founder_pricing_dark.html").read_text()
    text = (TEMPLATE_DIR / "founder_pricing_dark.txt").read_text()

    business_short = re.sub(r"[^A-Za-z0-9]", "",
                             (business_name or "team").split()[0])[:12] or "team"
    city_display = city or metro or "your area"
    metro_used = metro or city or "your area"

    vars_ = {
        "business_name": business_name or "there",
        "business_short": business_short,
        "city": city_display,
        "metro": metro_used,
        "niche": niche or "service",
        "state": state or "",
        "phone": phone or "",
        "extra_intro": extra_intro or "",
    }

    for k, v in vars_.items():
        html = html.replace("{" + k + "}", v)
        text = text.replace("{" + k + "}", v)

    # Strip any unreplaced placeholders in text
    text = _strip_html(html) if not text.strip() else text
    text = re.sub(r"\{[a-z_]+\}", "", text)

    subject = f"Empire OS — B2B leads for {business_name or business_short} in {city_display}"
    return html, text, subject


if __name__ == "__main__":
    # Demo render
    html, text, subj = render_email(
        business_name="ABC Roofing & Exteriors",
        city="Houston",
        state="TX",
        niche="roofing",
        phone="(281) 555-0100",
    )
    print(f"Subject: {subj}")
    print(f"HTML: {len(html)} chars")
    print(f"Text: {len(text)} chars")
    print()
    print("--- HTML preview (first 500 chars) ---")
    print(html[:500])
