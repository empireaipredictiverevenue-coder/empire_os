"""
Empire OS v3 — Outreach Agent
==============================

Discovers prospective buyers (agencies) per metro + niche, prepares
1-on-1 outreach messages, sends first-touch emails via Resend, tracks
replies. Designed to run as an agentic loop inside the outreach container.

Pipeline:
  discover() → list of targets with email + agency name + metro + niche
  qualify()  → score + filter (focus on agencies with 10+ reviews & active)
  draft()    → personalized email body (uses copywriter agent if loaded)
  send()     → Resend email OR push to email-agent queue
  track()    → log send + tag in si_buyer_outreach table

Each cycle runs every 6h. Discovers ~10-20 new targets per cycle.
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, "/root/empire_os")

from empire_os.lead_sources import _import_sources, infer_niche
# yelp removed per blueprint v3 (paid API, replaced by OSM/free sources)
try:
    from empire_os.lead_sources.yelp import run as yelp_run  # noqa: F401
except ImportError:
    yelp_run = None

# Branded email templates (dark theme, neon green + cyan, multi-avenue)
try:
    from empire_os.templates.email import render as render_email
    from empire_os.templates.email import render_subject as email_subject
    EMAIL_TEMPLATES_AVAILABLE = True
except ImportError:
    EMAIL_TEMPLATES_AVAILABLE = False


OUTREACH_LOG = Path("/root/feedback/outreach.jsonl")
OUTREACH_LOG.parent.mkdir(parents=True, exist_ok=True)
PROSPECTS_PATH = Path("/root/feedback/prospects.jsonl")

METROS = ["NYC", "LAX", "CHI", "DFW", "SEA", "BOS", "WDC", "PHX", "MIN", "ATL"]

NICHES_BY_CATEGORY = {
    "plumbing": ["emergency_plumbing", "plumbing"],
    "roofing": ["roofing", "residential_roofing"],
    "hvac": ["hvac", "emergency_hvac"],
    "electrical": ["electrical"],
    "landscaping": ["landscaping"],
    "painting": ["painting", "interior_painting"],
    "general": ["general_contractor", "carpentry"],
    "restoration": ["water_damage_restoration", "fire_damage_restoration",
                    "mold_remediation", "disaster_recovery"],
}


def _log(level, msg, **fields):
    event = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "msg": msg,
        **fields,
    }
    with open(OUTREACH_LOG, "a") as f:
        f.write(json.dumps(event) + "\n")
    print(json.dumps(event))


def discover_targets(metro: str) -> list:
    """Pull businesses in target metro via Yelp.

    Returns list of dicts with name, phone, niche, metro, state, url, score.
    """
    _import_sources()
    targets = []
    # yelp removed — use empire-leads orchestrator instead (multi-source: OSM, Reddit, etc.)
    try:
        sys.path.insert(0, "/root/empire-leads")
        from empire_leads.engine import discover as el_discover
        # Run for several niches per metro
        niches = ["roofing", "plumbing", "hvac"]
        for niche in niches:
            try:
                r = el_discover(niche=niche, near=metro, limit_per_source=5)
            except Exception:
                continue
            for lead in r.leads:
                targets.append({
                    "name": getattr(lead, "business_name", "") or getattr(lead, "name", ""),
                    "phone": getattr(lead, "phone", ""),
                    "niche": niche,
                    "metro": metro,
                    "state": "",
                    "url": getattr(lead, "source_url", "") or getattr(lead, "url", ""),
                    "score": 60,
                    "details": getattr(lead, "description", ""),
                })
    except ImportError:
        pass
    return targets


def qualify_target(target: dict, min_score: int = 60) -> bool:
    """Filter out low-quality prospects."""
    if target.get("score", 0) < min_score:
        return False
    if not target.get("phone"):
        return False
    return True


def draft_email(target: dict, prospect_email: str,
                template: str = "outreach_first_touch",
                avenue_id: str = "leadgen") -> tuple[str, str, str]:
    """Render a branded outreach email via the template engine.

    Returns (subject, body_html, source_tag). For clients that need
    plain text, callers can derive from body_html or use the legacy
    inline fallback.

    Templates: outreach_first_touch | followup_nudge | followup_final
    Avenues:   leadgen | paypercall | saas | loans | default
    """
    name = target.get("name", "there")
    niche = target.get("niche", "").replace("_", " ")
    metro = target.get("metro", "your market")
    details = target.get("details", "")

    if EMAIL_TEMPLATES_AVAILABLE:
        vars = {
            "recipient_name": name,
            "niche": niche,
            "metro": metro,
            "source_detail": details,
            "avenue_id": avenue_id,
            "tenant_id": "outreach",
            "reply_to": "ops@empire-ai.co.uk",
            "sender_name": "Empire OS team",
        }
        try:
            html, _text = render_email(template, vars)
            subj = email_subject(template, vars)
            return subj, html, f"branded:{template}:{avenue_id}"
        except (KeyError, Exception) as e:
            _log("WARN", "template_render_failed",
                 template=template, avenue=avenue_id, error=str(e)[:200])

    # Legacy fallback — plain text only, no brand
    subject = f"Sample lead for {niche} in {metro}"
    body = (
        f"Hi {name},\n\n"
        f"Quick one — pay-per-delivered-lead for {niche} in {metro}. "
        f"Reply 'send sample' for one free lead in 24h.\n\n"
        f"-- Empire OS\n"
        f"   https://empire-ai.co.uk\n"
    )
    return subject, body, "outreach_v1_plain"


def send_outreach(target: dict, prospect_email: str, dry_run: bool = False) -> bool:
    """Send outreach email via lead_deliverer's send_email."""
    from empire_os.agents.lead_deliverer_agent import send_email

    if not prospect_email:
        _log("SKIP", "no_email", name=target.get("name"))
        return False

    subject, body, source_tag = draft_email(target, prospect_email)
    if dry_run:
        _log("DRYRUN", "draft", name=target.get("name"),
             subject=subject[:60])
        return False

    ok, info = send_email(
        prospect_email, subject, body,
        metadata={"source": source_tag, "prospect": target.get("name", "")},
    )
    _log("SEND" if ok else "ERROR",
         "outreach",
         name=target.get("name"), email=prospect_email,
         metro=target.get("metro"), info=str(info)[:200])
    return ok


def save_prospect(target: dict):
    """Append to prospects log so we never duplicate."""
    if PROSPECTS_PATH.exists():
        for line in PROSPECTS_PATH.read_text().splitlines():
            try:
                p = json.loads(line)
                if p.get("name") == target.get("name") and p.get("metro") == target.get("metro"):
                    return False
            except Exception:
                continue

    with open(PROSSPECTS_PATH if False else PROSPECTS_PATH, "a") as f:
        f.write(json.dumps({**target, "first_seen_at": time.time()}) + "\n")
    return True


def run_cycle(metros: list = None, dry_run: bool = False, per_metro: int = 5):
    """One outreach cycle. Finds targets, qualifies, drafts, sends."""
    if metros is None:
        metros = METROS

    _log("INFO", "cycle_start", metros=metros, dry_run=dry_run)

    sent = 0
    for metro in metros:
        try:
            targets = discover_targets(metro)
        except Exception as e:
            _log("ERROR", "discover_failed", metro=metro, error=str(e))
            continue

        qualified = [t for t in targets if qualify_target(t)]
        _log("INFO", "metro_scanned",
             metro=metro, total=len(targets), qualified=len(qualified))

        for t in qualified[:per_metro]:
            # TODO: extract prospect email from Yelp detail page (requires
            # extra Yelp call). For now, skip if no email known — the
            # push_to_close path is via reply-to-tout placeholder.
            save_prospect(t)
            # Defer actual send until email-enrichment step.
            sent += 1

    _log("INFO", "cycle_done", qualified=sent)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--metros", nargs="+", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--per-metro", type=int, default=5)
    args = parser.parse_args()
    run_cycle(metros=args.metros, dry_run=args.dry_run,
              per_metro=args.per_metro)
