"""
Empire Omega OS — Pillar 5: The Creative
========================================
Generates high-converting video ads on payment.

Flow (Omega OS spec):
  Scout (P1) -> discovers leads
  Auditor (P2) -> scores leads (0-40), flags leak types
  Messenger (P3) -> sends emails
  Ledger (P4) -> handles payments; status: PAID  <-- TRIGGER
  Creative (P5) -> generates video ads            <-- THIS MODULE
  Portal (Dashboard) -> displays results

Our implementation replaces the spec's "ArcadsClient" with OUR OWN
video platform: hub POST /v1/video/brief -> ffmpeg MP4 at
/v1/renders/<id>.mp4.

Three components:
  1. AdGenerator  — script engine (Hook>Problem>Solution>CTA, niche +
                    leak-type detection, revenue impact quantified)
  2. VideoPlatformClient — posts script to our hub, polls/receives URL
  3. CreativeOrchestrator — watches Ledger for PAID, generates, renders,
                    stores asset, emits Portal-ready record.
"""
import os
import json
import time
import sqlite3
from datetime import datetime, timezone

sys_path = "/root/empire_os"
import sys
sys.path.insert(0, sys_path)

from empire_os.agents.ledger import pending_paid_unprocessed, mark_processed  # noqa

DB = os.getenv("EMPIRE_DB", "/root/empire_os/empire_os.db")
HUB = os.getenv("HUB_URL", "http://127.0.0.1:8081")
FB = "/root/empire_os/feedback"
os.makedirs(FB, exist_ok=True)
PROCESSED_FILE = os.path.join(FB, "creative_processed.json")


# ── 1. AdGenerator — Script Engine ─────────────────────────────────────
NICHE_TEMPLATES = {
    "hvac": {
        "hook": "Your AC just died in August. Now what?",
        "problem": "Most HVAC companies ghost you for days — and the bill surprises you.",
        "solution": "Our certified techs arrive in 2 hours, upfront price, done right.",
        "cta": "Book your fix before the heat wins. Tap now.",
    },
    "roofing": {
        "hook": "That roof leak isn't slowing down.",
        "problem": "Every rain costs you thousands in damage you can't see yet.",
        "solution": "Free 20-minute inspection. Insurance-ready report. Fixed fast.",
        "cta": "Claim your free inspection before the next storm.",
    },
    "plumbing": {
        "hook": "A burst pipe at 2am shouldn't ruin your week.",
        "problem": "Most plumbers quote blind and charge double when it's urgent.",
        "solution": "Upfront pricing, 60-minute response, no surprise fees.",
        "cta": "Stop the leak now — get a real quote in seconds.",
    },
    "electrical": {
        "hook": "Flickering lights are a warning, not a quirk.",
        "problem": "DIY fixes spark fires. Inspectors fail sloppy work.",
        "solution": "Licensed electricians, code-perfect, same-day availability.",
        "cta": "Get safe today. Book your inspection.",
    },
    "landscaping": {
        "hook": "Curb appeal sells the house before you do.",
        "problem": "Neglected yards drop property value and scare buyers.",
        "solution": "Design-build crews transform yards in days, not months.",
        "cta": "See your new yard. Free design consult.",
    },
    "general": {
        "hook": "Done-for-you, done right, done fast.",
        "problem": "Most contractors overpromise and underdeliver.",
        "solution": "Empire-verified pros, upfront price, guaranteed work.",
        "cta": "Get matched with a pro today.",
    },
}

# leak-type detection drives which pain point we lead with
LEAK_HOOKS = {
    "no_pixel": "You're paying for leads you can't even track. Fix the funnel first.",
    "no_video": "Businesses without video lose 80% of buyers before they call.",
    "slow_speed": "A 1-second delay costs you 7% of conversions. Speed kills — or sells.",
    "mobile": "70% of your buyers are on mobile. If it's not mobile-first, it's invisible.",
}


def _niche_key(niche):
    niche = (niche or "general").lower()
    for k in NICHE_TEMPLATES:
        if k in niche:
            return k
    return "general"


def generate_script(lead):
    """Hook>Problem>Solution>CTA + leak-type detection + revenue impact."""
    niche = _niche_key(lead.get("niche"))
    tpl = NICHE_TEMPLATES[niche]
    payload = lead.get("payload", {}) or {}
    if not isinstance(payload, dict):
        payload = {}
    leaks = payload.get("leaks", []) or []
    amount = float(lead.get("amount_usd", 0.0) or 0.0)

    hook = tpl["hook"]
    # leak-type detection: lead with the dominant leak type
    if leaks:
        dominant = leaks[0]
        if dominant in LEAK_HOOKS:
            hook = LEAK_HOOKS[dominant]

    # revenue impact quantified in every script
    rev_line = ""
    if amount > 0:
        rev_line = f"Clients like you add ${amount:,.0f} in recovered revenue."

    script = {
        "hook": hook,
        "problem": tpl["problem"],
        "solution": tpl["solution"],
        "cta": tpl["cta"],
        "revenue_impact": rev_line,
        "leak_types": leaks,
        "niche": niche,
    }
    # 30s copy = concatenated spiel (ffmpeg renders as caption card)
    copy = " ".join([script["hook"], script["problem"],
                     script["solution"], script["revenue_impact"],
                     script["cta"]]).strip()
    script["copy"] = copy
    return script


# ── 2. VideoPlatformClient — OUR hub, not Arcads ───────────────────────
import requests  # noqa: E402


class VideoPlatformClient:
    def __init__(self, hub=HUB, timeout=60):
        self.hub = hub
        self.timeout = timeout

    def render(self, script, duration_s=30, brand="Empire AI"):
        """POST script to our video platform -> returns video URL."""
        try:
            r = requests.post(
                f"{self.hub}/v1/video/brief",
                json={"copy": script["copy"], "niche": script["niche"],
                      "duration_s": duration_s, "brand": brand},
                timeout=self.timeout,
            )
            data = r.json()
            if "error" in data:
                return {"ok": False, "error": data["error"]}
            return {"ok": True, "render_id": data.get("render_id"),
                    "url": data.get("url"), "path": data.get("path")}
        except Exception as e:
            return {"ok": False, "error": str(e)[:200]}


# ── 3. CreativeOrchestrator ────────────────────────────────────────────
def _load_processed():
    try:
        return set(json.load(open(PROCESSED_FILE)))
    except Exception:
        return set()


def _save_processed(s):
    json.dump(list(s), open(PROCESSED_FILE, "w"))


def _store_asset(lead_id, niche, script, video):
    c = sqlite3.connect(DB)
    c.execute(
        """CREATE TABLE IF NOT EXISTS creative_assets (
            lead_id TEXT PRIMARY KEY,
            niche TEXT,
            script TEXT,
            video_url TEXT,
            render_id TEXT,
            status TEXT,
            created_at TEXT
        )"""
    )
    c.execute(
        "INSERT OR REPLACE INTO creative_assets "
        "(lead_id, niche, script, video_url, render_id, status, created_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (lead_id, niche, json.dumps(script), video.get("url"),
         video.get("render_id"),
         "READY" if video.get("ok") else "FAILED",
         datetime.now(timezone.utc).isoformat()),
    )
    c.commit()
    c.close()


def run_once():
    processed = _load_processed()
    leads = pending_paid_unprocessed(processed)
    if not leads:
        return {"checked": True, "generated": 0}
    client = VideoPlatformClient()
    generated = 0
    for lead in leads:
        script = generate_script(lead)
        video = client.render(script, duration_s=30)
        _store_asset(lead["lead_id"], script["niche"], script, video)
        processed.add(lead["lead_id"])
        generated += 1
        print(json.dumps({"msg": "creative_generated", "lead_id": lead["lead_id"],
                          "niche": script["niche"], "video": video.get("url"),
                          "ok": video.get("ok")}), flush=True)
    _save_processed(processed)
    return {"checked": True, "generated": generated}


def main():
    print(f"[{datetime.now(timezone.utc).isoformat()}] P5 Creative online",
          flush=True)
    while True:
        try:
            run_once()
        except Exception as e:
            print(json.dumps({"level": "ERROR", "msg": "cycle",
                              "err": str(e)[:200]}), flush=True)
        time.sleep(int(os.getenv("CREATIVE_INTERVAL", "15")))


if __name__ == "__main__":
    main()
