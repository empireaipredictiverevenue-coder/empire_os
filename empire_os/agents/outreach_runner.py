"""
Empire OS v3 — Outreach Agent (production loop)
================================================

Lives inside outreach-agent Incus container.
Loops every 60 minutes:
  1. Discovers prospects via hub HTTP /v1/outreach/prospects/pending
  2. Filters already-contacted
  3. Enriches email (Hunter.io, falls back to skip)
  4. Pulls sample lead from /v1/leads/sample
  5. Drafts + sends via Resend
  6. Tracks via /v1/outreach/prospect/touched
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

# Sovereign topology: outbound to Resend / Hunter / hub is on our own network
# or known hosts. Never route through the container's dead Privoxy/Tor proxy.
_http = requests.Session()
_http.trust_env = False

RESEND_OWNER = os.environ.get("RESEND_OWNER", "Founder <founder@empire-ai.co.uk>")
HUB_URL = os.environ.get("HUB_URL", "http://10.118.155.218:8081")
INTERVAL_SECONDS = int(os.environ.get("INTERVAL", "3600"))
CYCLE_PROSPECT_LIMIT = int(os.environ.get("LIMIT", "20"))
# sequence spacing in days per step + max step
STEP_GAP_DAYS = {0: 0, 1: 3, 2: 4, 3: 7}
MAX_STEP = 3
RESEND_OWNER = os.environ.get("RESEND_OWNER", "Founder <founder@empire-ai.co.uk>")
RESEND_REPLY_TO = os.environ.get("EMPIRE_REPLY_TO", "founder@empire-ai.co.uk")
ALLOWED_SEND_DOMAIN = os.environ.get("ALLOWED_SEND_DOMAIN", "empire-ai.co.uk")
LOG_PATH = Path("/root/feedback/outreach_log.jsonl")
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)


def _log(level, msg, **fields):
    event = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "msg": msg,
        **fields,
    }
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(event) + "\n")
    print(json.dumps(event), flush=True)


def hub_get(path: str, **params) -> dict:
    try:
        r = _http.get(f"{HUB_URL}{path}", params=params, timeout=10)
        return r.json() if r.status_code == 200 else {}
    except Exception as e:
        _log("ERROR", "hub_get_failed", path=path, error=str(e)[:200])
        return {}


def hub_post(path: str, body: dict) -> dict:
    try:
        r = _http.post(f"{HUB_URL}{path}", json=body, timeout=10)
        return r.json() if r.status_code < 300 else {"error": r.text[:200]}
    except Exception as e:
        _log("ERROR", "hub_post_failed", path=path, error=str(e)[:200])
        return {"error": str(e)}


def pull_prospects(metro: str = None, niche: str = None) -> list:
    """Read pending prospects from hub."""
    body = hub_get("/v1/outreach/prospects/pending", metro=metro,
                   niche=niche, limit=CYCLE_PROSPECT_LIMIT)
    return body.get("prospects", [])


def register_prospect(p: dict) -> bool:
    r = hub_post("/v1/outreach/prospect/register", p)
    return r.get("ok", False)


def mark_touched(p: dict, sent: bool, sample_lead_id: str = "") -> bool:
    r = hub_post("/v1/outreach/prospect/touched", {
        **p, "sent": sent, "sample_lead_id": sample_lead_id,
    })
    return r.get("ok", False)


def get_prospect(prospect_id: str) -> dict:
    return hub_get(f"/v1/outreach/prospect/{prospect_id}")


def find_sample_lead(niche: str, metro: str) -> dict | None:
    r = hub_get("/v1/leads/sample", niche=niche, metro=metro)
    if r.get("found"):
        return r["lead"]
    return None


def enrich_email(prospect: dict) -> str:
    """Try Hunter.io free tier (50 req/mo). Falls back to skip.

    Public API: https://api.hunter.io/v2/domain-search?domain=DOMAIN&api_key=KEY
    """
    env = Path("/root/empire_os/.env")
    hunter_key = ""
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("HUNTER_API_KEY="):
                hunter_key = line.split("=", 1)[1].strip()
                break

    url = prospect.get("url", "")
    if not hunter_key or not url:
        return ""

    try:
        domain = re.sub(r"https?://", "", url).split("/")[0]
        r = _http.get(
            f"https://api.hunter.io/v2/domain-search",
            params={"domain": domain, "api_key": hunter_key},
            timeout=8,
        )
        if r.status_code == 200:
            emails = r.json().get("data", {}).get("emails", [])
            # Prefer info@/contact@ over personal
            for e in emails:
                local = e.get("value", "").split("@")[0]
                if local in ("info", "contact", "sales", "hello", "team",
                             "office", "support"):
                    return e["value"]
            return emails[0]["value"] if emails else ""
    except Exception:
        pass
    return ""


def pick_aeo(niche: str, metro: str) -> str:
    """Return a real value-drop line from our 210 AEO pages (local cache)."""
    import glob
    base = "/root/empire_os/scripts/_aeo_pages"
    cand = sorted(glob.glob(f"{base}/*{niche}*.html") +
                  glob.glob(f"{base}/*{metro}*.html"))
    if not cand:
        cand = sorted(glob.glob(f"{base}/*.html"))
    if not cand:
        return ""
    try:
        txt = Path(cand[0]).read_text(errors="ignore")
        # grab first <h2>/<p> snippet as the insight
        m = re.search(r"<h2[^>]*>(.*?)</h2>", txt, re.S) or \
            re.search(r"<p[^>]*>(.*?)</p>", txt, re.S)
        if m:
            return re.sub("<.*?>", "", m.group(1)).strip()[:160]
    except Exception:
        pass
    return ""


def b2b_block() -> str:
    """Cross-pitch the B2B product suite (satellite/warehouse/AI tools)."""
    return (
        "\nAlso — if you run ops beyond lead-gen, we license B2B tools "
        "settled in USDC (no card, no KYC):\n"
        "  - Idle-asset & logistics wastage monitor ($49/mo)\n"
        "  - Warehouse asset reporting ($39/mo)\n"
        "  - AI agent skill audit for your team (NVIDIA SkillSpector, $39/mo)\n"
        "  - Open-source video studio for your marketing ($49/mo)\n"
        "  - White-label agent framework + templates (your brand)\n"
        "See the full suite: https://empire-ai.co.uk/buy-leads\n"
    )


def draft_email(prospect: dict, sample: dict | None, step: int = 0) -> tuple[str, str]:
    """Value-first nurture sequence. Step 0 intro, 1 value, 2 soft CTA."""
    name = prospect.get("business_name", "there")
    raw_niche = (prospect.get("niche", "your specialty") or "")
    niche = raw_niche.replace("_", " ") if raw_niche != "b2b" else "your business"
    metro = prospect.get("metro", "") or "your area"

    if sample:
        sample_text = (
            f"Real lead live in our pipeline right now:\n"
            f"  - {sample.get('name', '')[:50]}\n"
            f"  - {sample.get('details', '')[:140]}\n"
        )
    else:
        sample_text = (
            f"We're delivering fresh {niche} leads into {metro} daily. "
            f"Reply 'sample' and I'll wire you the next one free.\n"
        )

    if step == 0:
        subject = f"Exclusive {niche} leads — pay in USDC, no cards, no KYC"
        body = (
            f"Hi {name},\n\n"
            f"Quick one - I run a lead exchange for {niche} contractors in "
            f"{metro}. Exclusive leads delivered real-time, settled in USDC "
            f"- no credit cards, no KYC, no processor.\n\n"
            f"{sample_text}"
            f"How it works: grab a seat (pay-per-lead in USDC to our Solana "
            f"vault), we deliver verified {niche} leads to your dashboard + "
            f"email + webhook. You only pay when seated.\n\n"
            f"See + claim a lane: https://empire-ai.co.uk/buy-leads\n"
            f"Vault: egJ1t9NZkDs8FvMbfnQTqXzC4KNuhAc9XSfpG9y9AZM\n\n"
            f"Reply 'sample' for a free live lead.\n\n- Empire OS"
            f"{b2b_block()}"
        )
    elif step == 1:
        insight = pick_aeo(niche, metro)
        subject = f"{niche.title()} in {metro}: what's converting right now"
        body = (
            f"Hi {name},\n\n"
            f"Following up with something useful, no ask. We track "
            f"{niche} demand across {metro} daily. One pattern we're seeing:\n"
            f"  {insight}\n\n"
            f"{sample_text}"
            f"When you're ready to put that demand to work, seats are open "
            f"at https://empire-ai.co.uk/buy-leads (USDC settle, no card).\n\n"
            f"- Empire OS"
            f"{b2b_block()}"
        )
    else:  # step 2+ soft CTA
        subject = f"Your {niche} lane in {metro} is still open"
        body = (
            f"Hi {name},\n\n"
            f"Last one - your {niche} seat for {metro} is still available. "
            f"Exclusive leads, USDC settlement, cancel anytime.\n\n"
            f"Claim it: https://empire-ai.co.uk/buy-leads\n"
            f"Vault: egJ1t9NZkDs8FvMbfnQTqXzC4KNuhAc9XSfpG9y9AZM\n\n"
            f"If the timing's off, just reply 'later' and I'll close your "
            f"file. No hard feelings.\n\n- Empire OS"
            f"{b2b_block()}"
        )
    return subject, body


def send_via_resend(to: str, subject: str, body: str, metadata: dict) -> tuple[bool, str]:
    env = Path("/root/empire_os/.env")
    api_key = ""
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("RESEND_API_KEY="):
                api_key = line.split("=", 1)[1].strip()
                break
    if not api_key:
        return False, "no_resend_key"
    if f"@{ALLOWED_SEND_DOMAIN}" not in RESEND_OWNER:
        return False, f"from '{RESEND_OWNER}' not on allowed domain @{ALLOWED_SEND_DOMAIN}"

    try:
        r = _http.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "from": RESEND_OWNER,
                "to": [to],
                "reply_to": [RESEND_REPLY_TO],
                "subject": subject,
                "text": body,
                "metadata": {str(k): str(v) for k, v in metadata.items()},
            },
            timeout=10,
        )
        if r.status_code < 300:
            return True, f"sent {r.status_code}: {r.text[:200]}"
        return False, f"HTTP {r.status_code}: {r.text[:200]}"
    except Exception as e:
        return False, f"request_error: {str(e)[:200]}"


def recent_touched(prospect_id: str) -> bool:
    p = get_prospect(prospect_id)
    if not p.get("known"):
        return False
    rs = p.get("reply_state", "")
    if rs in ("contacted", "replied", "unsubscribed"):
        return True
    return False


def process_prospect(p, counters):
    """Process one prospect through the nurture sequence. Returns delta
    (sent_inc, skipped_inc)."""
    sent_inc = 0
    skipped_inc = 0
    rs = p.get("reply_state", "cold")
    if rs in ("replied", "unsubscribed", "seated", "converted"):
        return 0, 1
    step = int(p.get("seq_step") or 0)
    last = p.get("last_touch_at") or ""
    if step > 0 and last:
        try:
            lt = datetime.fromisoformat(last.replace("Z", "+00:00"))
            days = (datetime.now(timezone.utc) - lt).days
            if days < STEP_GAP_DAYS.get(step, 3):
                return 0, 1
        except Exception:
            pass
    if step > MAX_STEP:
        return 0, 1
    register_prospect(p)
    email = p.get("email", "")
    if not email:
        email = enrich_email(p)
        if email:
            p["email"] = email
            register_prospect(p)
    if not email:
        _log("SKIP", "no_email", prospect_id=p.get("prospect_id"))
        return 0, 1
    sample = find_sample_lead(p.get("niche", ""), p.get("metro", ""))
    sample_id = str(sample["id"]) if sample else ""
    subject, body = draft_email(p, sample, step)
    ok, info = send_via_resend(
        email, subject, body,
        metadata={"source": "outreach", "step": step,
                  "prospect_id": p.get("prospect_id", ""),
                  "metro": p.get("metro", ""),
                  "niche": p.get("niche", ""),
                  "sample_lead_id": sample_id},
    )
    try:
        _http.post(f"{HUB_URL}/v1/outreach/prospect/touched", json={
            **p, "sent": ok, "sample_lead_id": sample_id,
            "seq_step": step + 1,
        }, timeout=10)
    except Exception:
        pass
    if ok:
        _log("SENT", "nurture", step=step,
             prospect_id=p.get("prospect_id"),
             email=email, name=str(p.get("business_name", ""))[:30],
             metro=p.get("metro"), niche=p.get("niche"))
    else:
        _log("ERROR", "send_failed",
             prospect_id=p.get("prospect_id"), info=info[:200])
    time.sleep(2)
    return (1 if ok else 0), 0


def run_cycle():
    """One nurture cycle — value-first sequence, spaced over days."""
    _log("INFO", "cycle_start")

    metros = ["NYC", "LAX", "CHI", "DFW", "SEA", "BOS", "WDC", "PHX"]
    sent = 0
    skipped = 0
    processed = 0

    health = hub_get("/health")
    if not health or health.get("status") not in ("ok", "online"):
        _log("ERROR", "hub_unhealthy", body=health)
        return

    for metro in metros:
        if sent >= CYCLE_PROSPECT_LIMIT:
            break
        prospects = pull_prospects(metro)
        _log("INFO", "metro_scanned", metro=metro, count=len(prospects))

        for p in prospects:
            if sent >= CYCLE_PROSPECT_LIMIT:
                break
            processed += 1
            s, sk = process_prospect(p, None)
            sent += s
            skipped += sk

    # B2B pass — niche='b2b' business buyers (real firms, cross-pitch suite)
    for p in pull_prospects(niche="b2b"):
        if sent >= CYCLE_PROSPECT_LIMIT:
            break
        processed += 1
        s, sk = process_prospect(p, None)
        sent += s
        skipped += sk

    _log("INFO", "cycle_done", processed=processed, sent=sent, skipped=skipped)


def seed_from_permits_if_empty() -> int:
    """Seed si_buyer_outreach cold prospects from lane_leads permits.

    Idempotent — only seeds if there are no current prospects.
    """
    body = hub_get("/v1/outreach/prospects/pending", limit=100)
    if body.get("prospects"):
        return 0

    try:
        r = _http.get(f"{HUB_URL}/v1/leads/counts", timeout=10)
        if r.status_code != 200:
            return 0
        # Pull permits via direct DB
        # Use hub_sql via a fake query — actually use a new endpoint
        # Simpler: pull from existing /v1/leads/?source=permits_nyc&limit=N
        r = _http.get(
            f"{HUB_URL}/v1/lanes/leads/by-source",
            params={"source": "permits_nyc", "limit": 100},
            timeout=10,
        )
        if r.status_code != 200:
            return 0
        leads = r.json().get("leads", [])
        count = 0
        for lead in leads:
            lane_id = lead.get("lane_id", "")
            niche = lane_id.split(":")[0] if ":" in lane_id else ""
            p = {
                "prospect_id": f"permits_nyc_{lead['id']}",
                "business_name": (lead.get("name", "")).split("(")[0].strip(),
                "email": "",
                "metro": lead.get("metro", ""),
                "niche": niche,
                "phone": lead.get("phone", ""),
                "source": "permits_nyc",
                "score": 70,
                "url": "",
            }
            if register_prospect(p):
                count += 1
        return count
    except Exception as e:
        _log("ERROR", "seed_failed", error=str(e)[:200])
        return 0


if __name__ == "__main__":
    print(f"[{datetime.now(timezone.utc).isoformat()}] outreach-agent starting "
          f"- interval {INTERVAL_SECONDS}s, limit {CYCLE_PROSPECT_LIMIT}", flush=True)

    while True:
        try:
            run_cycle()
        except Exception as e:
            _log("ERROR", "cycle_exception", error=str(e))
        time.sleep(INTERVAL_SECONDS)
