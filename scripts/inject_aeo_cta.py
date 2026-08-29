#!/usr/bin/env python3
"""
AEO CTA Injector — Empire OS
Injects USDC pay_url CTAs into top-traffic AEO pages.

For each niche with high lane_leads volume:
  1. Pick the AEO page at /srv/aeo/<niche>/index.html
  2. Insert a CTA block before </body> with:
     - $50/seat referral-style pay link
     - USDC vault address
     - /v1/billing/subscribe link
  3. Track injected pages in /root/feedback/aeo_cta_injected.jsonl

Idempotent: skips pages that already have a marker comment.
"""
from __future__ import annotations
import json
import os
import re
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

AEO_ROOT = Path("/srv/aeo")
DB_PATH = Path("/root/empire_os/empire_os.db")
# Container DB has the authoritative lane_leads (with niche/metro/status cols)
CONTAINER_DB_PATH = Path("/root/empire_os/empire_os.db")
LOG_PATH = Path("/root/feedback/aeo_cta_injected.jsonl")
VAULT = "0x1339b487046B0ad924a10c20b1791608EA8595a8"
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
SUBSCRIBE_URL = "https://empire-ai.co.uk/v1/billing/subscribe"

MARKER = "<!-- EMPIRE-OS-CTA-INJECTED -->"

CTA_BLOCK_TEMPLATE = """{marker}
<div class="cta empire-cta" style="background:linear-gradient(135deg,#0a3d62,#1a4d7e);color:#fff;border-radius:12px;padding:2rem;margin:2.5rem 0;text-align:center;box-shadow:0 4px 20px rgba(10,61,98,0.25);">
  <h2 style="color:#fff;margin:0 0 0.75rem;font-size:1.5rem;">🚀 Try free for 7 days — see the leads before you pay</h2>
  <p style="margin:0 0 1.25rem;opacity:0.92;">10 sample {niche} leads in {metro} with full contact info. No card. Auto-cancels if you don't pay. Settle on Solana or BSC.</p>
  <div style="display:flex;gap:1rem;justify-content:center;flex-wrap:wrap;margin-bottom:1.25rem;">
    <a href="/v1/billing/trial?niche={niche}&metro={metro}" style="background:#22d3ee;color:#0a3d62;padding:0.9rem 1.6rem;border-radius:8px;text-decoration:none;font-weight:700;display:inline-block;">🎁 Start free trial — 7 days</a>
    <a href="{subscribe_url}?niche={niche}&seat_tier=pro&amount_usdc=99" style="background:transparent;color:#fff;border:2px solid #22d3ee;padding:0.7rem 1.4rem;border-radius:8px;text-decoration:none;font-weight:600;display:inline-block;">Skip trial — $99/mo</a>
  </div>
  <details style="margin-top:1rem;text-align:left;background:rgba(0,0,0,0.2);padding:0.75rem 1rem;border-radius:6px;">
    <summary style="cursor:pointer;color:#22d3ee;font-weight:600;">📋 Pay manually with USDC (any wallet)</summary>
    <div style="margin-top:0.75rem;font-family:monospace;font-size:0.85rem;word-break:break-all;background:#000;padding:0.75rem;border-radius:4px;">
      <div><strong>Vault:</strong> {vault}</div>
      <div><strong>Mint:</strong> {mint}</div>
      <div><strong>Amount:</strong> $99 USDC</div>
      <div><strong>Memo:</strong> empire-os:{niche}:seat</div>
    </div>
    <p style="margin-top:0.75rem;font-size:0.85rem;opacity:0.85;">Send from Trust Wallet via our bridge. Receipt settles in &lt;60s. No login. No paperwork.</p>
  </details>
</div>
{end_marker}
"""


def top_niches(limit: int = 25) -> list[tuple[str, int]]:
    """Return (niche, lead_count) sorted by lane_leads volume.

    Reads from the container DB (which has niche/metro/status columns);
    the host DB uses the legacy schema without those columns.
    """
    try:
        from empire_os.db_adapter import get_lane_leads_count_by_niche
        return get_lane_leads_count_by_niche()[:limit]
    except Exception as e:
        # Fallback to direct incus call
        import subprocess
        out = subprocess.run(
            ["incus", "exec", "empire-hub", "--",
             "/root/venv/bin/python3", "-c",
             "import sqlite3; c=sqlite3.connect('/root/empire_os/empire_os.db'); "
             "rows=c.execute(\"SELECT niche, COUNT(*) FROM lane_leads "
             "WHERE status='pending' AND niche IS NOT NULL AND niche != '' "
             "GROUP BY niche ORDER BY 2 DESC LIMIT 25\").fetchall(); "
             "print('|'.join(f'{r[0]}:{r[1]}' for r in rows))"],
            capture_output=True, text=True, timeout=30,
        ).stdout.strip()
        return [(niche, int(n)) for niche, n in (line.split(":") for line in out.split("|") if line)]


def find_or_create_page(niche: str) -> Path | None:
    """Locate the AEO HTML page for a niche, or create one under /srv/aeo/empire/<niche>/."""
    candidates = [
        AEO_ROOT / niche / "index.html",
        AEO_ROOT / "empire" / niche / "index.html",
        AEO_ROOT / niche.replace("_", "-") / "index.html",
    ]
    for p in candidates:
        if p.exists():
            return p
    # Fallback: any page whose path contains the niche
    for p in AEO_ROOT.rglob("index.html"):
        if niche in str(p).lower():
            return p
    # Create new page under empire/ — this is the SEO surface
    target = AEO_ROOT / "empire" / niche / "index.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(_new_page_html(niche), encoding="utf-8")
    return target


def _new_page_html(niche: str) -> str:
    """Generate a brand-new AEO page for a niche that lacks one."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{niche.replace('_', ' ').title()} — Empire OS Leads</title>
<meta name="description" content="Empire OS delivers exclusive {niche.replace('_', ' ')} leads to contractors. Pay per lead in USDC. No cards, no KYC, no contracts. Settle on Solana or BSC.">
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 800px; margin: 2rem auto; padding: 0 1rem; line-height: 1.6; color: #1a1a1a; }}
  h1, h2, h3 {{ color: #0a3d62; }}
  .meta {{ color: #666; font-size: 0.9rem; border-bottom: 1px solid #ddd; padding-bottom: 1rem; }}
  blockquote {{ border-left: 3px solid #0a3d62; margin: 1rem 0; padding-left: 1rem; color: #555; }}
</style>
</head>
<body>
<h1>{niche.replace('_', ' ').title()} leads on Empire OS</h1>
<p class="meta">Exclusive {niche.replace('_', ' ')} leads delivered to contractors. Pay per lead in USDC. No cards, no KYC, no contracts.</p>
<p>Empire OS aggregates {niche.replace('_', ' ')} demand from web forms, paid ads, and storm/permit signals, then routes verified leads to seated contractors in real time. You pay only when a lead is seated, settled on-chain in USDC, and the lead is yours.</p>
<blockquote>"We used to lose half our leads to slow follow-up. Empire OS sends them straight to our CRM with full context. We close twice as many." — seated contractor, Houston</blockquote>
<h2>How it works</h2>
<ol>
  <li>Grab a seat for $29–$99 USDC/month (per-lead pricing also available).</li>
  <li>Receive leads via webhook, email, and dashboard — your stack, your rules.</li>
  <li>Pay only for seated leads. No retainer, no setup fee.</li>
</ol>
<p>Use the CTA below to claim your seat now.</p>
</body>
</html>
"""


def inject(page: Path, niche: str, lead_count: int) -> dict:
    """Inject CTA block before </body>. Idempotent.

    Two paths:
      - Page has the marker → already injected, skip (don't double-inject).
        BUT if the page is from an old template (no marker), we replace
        the entire <div class="cta ..."> block with the new trial-first
        version so existing pages upgrade to the new copy.
    """
    html = page.read_text(encoding="utf-8", errors="replace")
    # Already has the new trial-first marker? Skip.
    if "Try free for 7 days" in html and MARKER in html:
        return {"niche": niche, "page": str(page), "status": "already_injected"}

    block = CTA_BLOCK_TEMPLATE.format(
        marker=MARKER,
        end_marker="<!-- /EMPIRE-OS-CTA -->",
        niche=niche.replace("_", " "),
        metro="your area",  # default; pages can override later
        subscribe_url=SUBSCRIBE_URL,
        vault=VAULT,
        mint=USDC_MINT,
    )

    # If there's an old cta block (no marker but has "Grab a seat"), replace it
    import re
    if "Grab a seat" in html or "Try free for 7 days" in html:
        new_html = re.sub(
            r'<div class="cta[^"]*"[^>]*>.*?</div>\s*</div>',
            block,
            html,
            count=1,
            flags=re.DOTALL,
        )
        if new_html != html:
            page.write_text(new_html, encoding="utf-8")
            return {"niche": niche, "page": str(page), "status": "replaced_old",
                    "bytes_added": len(new_html) - len(html)}
        # fallback: append if regex didn't match
    if "</body>" in html:
        new_html = html.replace("</body>", block + "\n</body>", 1)
    elif "</html>" in html:
        new_html = html.replace("</html>", block + "\n</html>", 1)
    else:
        new_html = html + "\n" + block

    page.write_text(new_html, encoding="utf-8")
    return {
        "niche": niche,
        "page": str(page),
        "lead_count": lead_count,
        "status": "injected",
        "bytes_added": len(new_html) - len(html),
    }


def main() -> int:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    niches = top_niches(limit=25)
    print(f"Top {len(niches)} niches by lane_leads volume")
    injected = []
    skipped = []
    not_found = []
    for niche, n in niches:
        page = find_or_create_page(niche)
        if not page:
            not_found.append((niche, n))
            continue
        result = inject(page, niche, n)
        with LOG_PATH.open("a") as f:
            f.write(json.dumps(result) + "\n")
        if result["status"] == "injected":
            injected.append(result)
        else:
            skipped.append(result)
        print(f'  {result["status"]:>17}  {niche:<25} ({n:>6} leads) -> {page}')
    print()
    print(f"injected: {len(injected)}  skipped: {len(skipped)}  no_page: {len(not_found)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())