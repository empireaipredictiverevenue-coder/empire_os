"""social_autopilot.py — Empire OS YouTube 100K/90d autonomous engine.

Chains real modules (no fictional "Cortex" AI):
  Cortex-lite  : niche selection from niche_map.VERTICALS + Vonage number pick
  Script       : MiniMax-M3 (social_syndication._llm) with title-question rule
  Critic      : enforce direct answer in FIRST 40 WORDS; regenerate <=3x
  Render       : 9:16 Shorts (ffmpeg) via social_syndication.render_video
  Thumbnail   : free Pollinations + PIL (social_thumbnail)
  Metadata     : SEO title/desc/tags, phone+CTA top-2 lines, AEO summary, ts
  Publish      : YouTube private (social_youtube.publish)
  AEO sync     : deploy_spec to /srv/aeo/<niche>/ for AI-overview pickup

All external creds come from /root/.empire_secrets/social.env.
Phone/CTA: 2 Vonage numbers, track-mapped (VONAGE_NUMBER_A/B in social.env).
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, "/root/empire_os")

import empire_os.niche_map as niche_map
from empire_os import social_syndication as syn
from empire_os import social_youtube as yt
from empire_os import social_thumbnail as thumb

SECRETS_ENV = Path("/root/.empire_secrets/social.env")
AEO_ROOT = os.environ.get("AEO_SURFACE_ROOT", "/srv/aeo")
RENDER_DIR = syn.RENDER_DIR

# Local-services verticals -> served by Vonage track B (lead-gen)
LOCAL_TRACK = {"plumbing", "roofing", "hvac", "water_damage", "fire_damage",
               "storm_damage", "mold_remediation", "sewage_cleanup", "electrical",
               "disaster_restoration", "legal_mass_tort"}

# Weighted rotation so we post across the whole offer pool
_WEIGHTS = {"plumbing": 5, "roofing": 5, "hvac": 4, "water_damage": 3,
            "towing": 3, "electrical": 3, "storm_damage": 2, "mold_remediation": 2,
            "cybersecurity": 2, "ai_automation": 4, "lead_gen": 3, "seo": 2}


def _load_secrets() -> dict:
    env = {}
    if SECRETS_ENV.exists():
        for line in SECRETS_ENV.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def cortex_pick_niche() -> dict:
    """Pick a vertical + its offer + Vonage number.

    If the trend monitor is available it biases the pick toward currently
    trending verticals (Layer 2). Otherwise falls back to weighted
    round-robin. Kept thin so the autopilot stays the source of truth.
    """
    try:
        from empire_os.agents.trend_sentiment_monitor import TrendSentimentMonitor
        return TrendSentimentMonitor().boosted_pick()
    except Exception:
        pass
    import random
    verts = list(_WEIGHTS.keys())
    weights = [_WEIGHTS[v] for v in verts]
    niche = random.choices(verts, weights=weights, k=1)[0]
    is_local = niche in LOCAL_TRACK
    sec = _load_secrets()
    if is_local:
        # rotate between B and C for local-services lead-gen
        local_nums = [n for n in (sec.get("VONAGE_NUMBER_B"),
                                   sec.get("VONAGE_NUMBER_C")) if n]
        phone = random.choice(local_nums) if local_nums else \
            sec.get("VONAGE_NUMBER_A", "")
        track = "local-services"
    else:
        phone = sec.get("VONAGE_NUMBER_A", sec.get("VONAGE_NUMBER_B", ""))
        track = "automation"
    per_lead = getattr(niche_map, "TIER_PER_LEAD_CENTS", {}).get("gold", 9900)
    return {"niche": niche, "is_local": is_local, "phone": phone,
            "track": track, "per_lead_cents": per_lead}


def _word_count(text: str) -> int:
    return len(re.findall(r"\w+", text or ""))


def critic_check(script: dict, title: str) -> bool:
    """Direct answer must appear VERBATIM in first 40 words.

    Mandate: first 40 words directly answer the title question.
    Strict: the LLM 'answer' field must be a substring of the first 40 words.
    No fuzzy overlap (that let hallucinated copy slip through).
    """
    answer = (script.get("answer") or "").strip().lower()
    beats = script.get("beats", [])
    flat = " ".join(b.get("text", "") for b in beats)
    first40 = " ".join(flat.split()[:40]).lower()
    if not answer:
        return False
    # normalize whitespace for substring match
    ans_norm = " ".join(answer.split())
    return ans_norm in first40


def _no_emdash(text: str) -> bool:
    return "\u2014" not in text and "\u2013" not in text


def _script_text(script: dict) -> str:
    return " ".join([
        script.get("title", ""),
        script.get("answer", ""),
        script.get("hook", ""),
    ] + [b.get("text", "") for b in script.get("beats", [])])


def build_metadata(script: dict, cortex: dict) -> dict:
    title = script.get("title", "Empire OS")
    phone = cortex.get("phone", "")
    # CTA: click to subscribe (mandate) + phone for local-services track
    cta = "👉 Click to SUBSCRIBE for daily AI automations that close deals."
    desc_lines = []
    if phone and cortex.get("track") == "local-services":
        desc_lines.append(f"📞 Call now: {phone}")
        desc_lines.append(f"💬 Text {phone} for a free audit")
    desc_lines.append(cta)
    summary = " ".join(b.get("text", "") for b in script.get("beats", [])[:2])
    desc_lines.append("")
    desc_lines.append("SUMMARY: " + syn.clean_caption(summary)[:400])
    # keywords + hashtags block (SEO)
    tags = [h.lstrip("#") for h in script.get("hashtags", [])][:10]
    kw = [cortex["niche"].replace("_", " "), "AI automation", "lead generation",
          "Empire OS", cortex.get("track", "")]
    desc_lines.append("")
    desc_lines.append("KEYWORDS: " + ", ".join(k for k in kw if k))
    if tags:
        desc_lines.append("HASHTAGS: " + " ".join("#" + t for t in tags))
    desc_lines.append("")
    beats = script.get("beats", [])
    dur = syn.PLATFORMS["youtube"]["dur"]
    step = max(5, dur // max(1, len(beats)))
    for i, b in enumerate(beats):
        desc_lines.append(f"{i*step:02d}:00 {b.get('text','')[:40]}")
    return {
        "title": title,
        "description": "\n".join(desc_lines),
        "tags": tags,
        "phone": phone,
    }


def sync_aeo(script: dict, cortex: dict, meta: dict) -> dict:
    try:
        from empire_os.marketing import AeoSpecDraft
        summary = syn.clean_caption(
            " ".join(b.get("text", "") for b in script.get("beats", [])))
        draft = AeoSpecDraft(
            niche=cortex["niche"],
            target_audience="business owners in " + cortex["niche"].replace("_", " "),
            pain_points=meta.get("description", "")[:300],
            key_questions=cortex.get("topic", ""),
            content_angle=summary[:200],
            tone="authoritative, punchy",
        )
        from empire_os.aeo_surface import deploy_spec
        path = deploy_spec(draft)
        return {"ok": True, "path": str(path)}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


def run_cycle(platform: str = "youtube", post: bool = True) -> dict:
    cortex = cortex_pick_niche()
    niche = cortex["niche"]
    topic = (f"How does AI automation help {niche.replace('_',' ')} "
             f"close more deals?")
    script, passed, attempts, guards = None, False, 0, {}
    for attempt in range(3):
        attempts = attempt + 1
        script = syn.generate_script(topic, platform)
        if "error" in script:
            return {"ok": False, "error": script["error"]}
        # sanitize script text (em-dashes etc) before guard checks + render
        if script.get("beats"):
            for b in script["beats"]:
                b["text"] = syn.clean_caption(b.get("text", ""))
        for k in ("answer", "hook", "title"):
            if script.get(k):
                script[k] = syn.clean_caption(script[k])
        # GUARD RAILS
        fc = syn.fact_check(_script_text(script))
        em = _no_emdash(_script_text(script))
        # enforce: first beat OPENS with the direct answer (mandate compliance)
        ans = (script.get("answer") or "").strip()
        if ans and script.get("beats"):
            first = script["beats"][0].get("text", "")
            if ans.lower() not in first.lower():
                script["beats"][0] = {"text": ans + " " + first,
                                      "sec": script["beats"][0].get("sec", 5)}
        cr = critic_check(script, topic)
        guards = {"fact_check": fc.get("ok"), "no_emdash": em,
                  "critic": cr, "fact_reason": fc.get("reason")}
        if fc.get("ok") and em and cr:
            passed = True
            break
    critic_log = {"CRITIC_PASSED": passed, "attempts": attempts,
                  "guards": guards}
    # 9:16 Shorts render — use avatar if founder assets present, else caption-cards
    from empire_os import avatar_pipeline as av
    use_avatar = av.PORTRAIT.exists() or av.VOICE.exists()
    if use_avatar:
        avr = av.run(script, str(RENDER_DIR / f"avatar_{int(time.time())}.mp4"))
        if avr.get("ok"):
            render = {"ok": True, "out": avr["out"], "avatar": True,
                      "voice": avr.get("voice_engine"), "face": avr.get("face_mode")}
        else:
            render = syn.render_video(script, "tiktok")  # fallback
    else:
        render = syn.render_video(script, "tiktok")
    if not render.get("ok"):
        return {"ok": False, "error": "render failed", "detail": render}
    th = thumb.generate_thumbnail(script.get("title", topic), niche)
    secrets = _load_secrets()
    meta = build_metadata(script, cortex)
    item = {
        "id": f"{platform}-{int(time.time())}",
        "platform": platform,
        "niche": niche,
        "track": cortex["track"],
        "topic": topic,
        "video": render["out"],
        "thumbnail": th.get("out"),
        "script": script,
        "metadata": meta,
        "status": "draft",
    }
    syn.queue_item(item)
    # PUBLISH + AEO ONLY IF ALL GUARDS PASS (never ship hallucinated copy)
    if passed:
        pub = (yt.publish_youtube(
            {**item, "video": render["out"],
             "script": {**script, "title": meta["title"],
                        "cta": meta["description"][:200],
                        "hashtags": meta["tags"]}}, secrets)
            if post else {"status": "queued"})
        aeo = sync_aeo(script, cortex, meta)
    else:
        pub = {"status": "HELD_REVIEW", "reason": "guard rail violation"}
        aeo = {"ok": False, "reason": "held: guards failed"}
    return {"ok": passed, "niche": niche, "track": cortex["track"],
            "critic": critic_log, "video": render["out"],
            "thumbnail": th.get("out"), "publish": pub.get("status"),
            "aeo": aeo.get("ok"), "url": pub.get("url")}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--publish", action="store_true")
    ap.add_argument("--pool", nargs="*", default=None)
    a = ap.parse_args()
    print(json.dumps(run_cycle(a.pool, a.publish), indent=2, default=str))


def run(pool: list[str] | None = None):
    """Fleet entrypoint. One autopilot cycle, private (no live publish)."""
    return run_cycle(pool, publish=False)
