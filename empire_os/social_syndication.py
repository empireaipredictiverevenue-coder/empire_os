"""
social_syndication.py — Empire OS multi-platform video growth engine.

Pipeline:
  generate_script(topic)          -> LLM (OpenRouter) short-form script
  repurpose_footage(path)         -> claude-video /watch -> clip ideas
  render_video(script, platform)  -> ffmpeg caption-card mp4 (platform aspect)
  queue_item(item)                -> write JSON to queue dir (draft-mode)
  publish(item)                   -> adapter; posts if creds present, else draft-only

Platforms:
  youtube  -> LIVE adapter (needs OAuth creds in social.env)
  tiktok   -> draft until creds
  instagram-> draft until creds
  facebook -> draft until creds

Creds file: /root/.empire_secrets/social.env  (you populate, never printed)
Run: python3 social_syndication.py --generate "AI agents that close deals" --platform youtube
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/root/empire_os")

# Robust .env loader (shells choke on unquoted <>@ in values like EMPIRE_FROM)
def _load_env_file(path: str = "/root/empire_os/.env") -> None:
    if not os.path.exists(path):
        return
    try:
        with open(path) as f:
            for ln in f:
                ln = ln.strip()
                if not ln or ln.startswith("#") or "=" not in ln:
                    continue
                k, _, v = ln.partition("=")
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if k:
                    # OVERWRITE (don't skip if already in env): the container may
                    # have a stale systemd-injected env (e.g. redacted MINIMAX_API_KEY
                    # from a prior broken .env push). Always trust .env on disk.
                    os.environ[k] = v
    except Exception:
        pass
_load_env_file()

# Direct OpenRouter call (free Gemma-4-31b) defined below as _llm()

# Free OpenRouter model that works with the current key.
FREE_MODEL = "openai/gpt-oss-20b:free"

# Reuse claude-video wrapper for footage repurposing
from empire_os.video_intake import watch as watch_video

# Free OpenRouter model that works with the current key.
FREE_MODEL = "openai/gpt-oss-20b:free"


def _llm(messages: list[dict]) -> str:
    """Chat completion via MiniMax M3 if key present, else free OpenRouter.

    MiniMax endpoint is OpenAI-compatible. Returns text, or '__ERR__<msg>'.
    """
    import urllib.request, urllib.error

    # 1) MiniMax M3 (preferred — no free-tier throttle)
    mm_key = os.environ.get("MINIMAX_API_KEY", "").strip()
    if mm_key:
        base = os.environ.get("LLM_BASE_URL", "https://api.minimax.io/v1").strip()
        # Use M3 explicitly; .env may carry a free slug (tencent/hy3:free)
        # which is throttled — override to the paid M3 model.
        model = "MiniMax-M3"
        url = f"{base.rstrip('/')}/chat/completions"
        payload = json.dumps({"model": model, "messages": messages,
                              "stream": False, "temperature": 0.4}).encode()
        req = urllib.request.Request(
            url, data=payload,
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {mm_key}"})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode())
            content = (data.get("choices", [{}])[0]
                          .get("message", {})
                          .get("content", ""))
            if content:
                return content
            # empty content → log and fall through
            import sys as _s
            print(f"[llm] MiniMax empty content; resp={json.dumps(data)[:200]}", file=_s.stderr)
        except Exception as e:
            import sys as _s
            print(f"[llm] MiniMax fail {type(e).__name__}: {str(e)[:200]}; falling through", file=_s.stderr)
            # fall through to OpenRouter free tier
            pass

    # 2) Free OpenRouter fallback
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        return ""
    payload = json.dumps({
        "model": FREE_MODEL,
        "messages": messages,
        "stream": False,
        "temperature": 0.4,
    }).encode()
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(req, timeout=40) as resp:
            data = json.loads(resp.read().decode())
        return data.get("choices", [{}])[0].get("message", {}).get("content", "")
    except Exception as e:
        return f"__ERR__{e}"


SECRETS_ENV = Path("/root/.empire_secrets/social.env")
QUEUE_DIR = Path("/root/empire_os/empire_os/social_queue")
RENDER_DIR = Path("/root/empire_os/empire_os/social_render")
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# Platform specs: aspect ratio + target duration (sec) + caption style
PLATFORMS = {
    "youtube":  {"aspect": "16:9",  "w": 1280, "h": 720,  "dur": 45, "label": "YouTube"},
    "tiktok":   {"aspect": "9:16",  "w": 1080, "h": 1920, "dur": 30, "label": "TikTok"},
    "instagram":{"aspect": "9:16",  "w": 1080, "h": 1920, "dur": 30, "label": "Instagram Reels"},
    "facebook": {"aspect": "1:1",   "w": 1080, "h": 1080, "dur": 30, "label": "Facebook"},
}


def _load_secrets() -> dict:
    """Read social.env creds into a dict. Missing file -> empty (draft mode)."""
    env = {}
    if SECRETS_ENV.exists():
        for line in SECRETS_ENV.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def generate_script(topic: str, platform: str = "youtube", style: str = "hook") -> dict:
    """Generate a short-form video script via LLM.

    Returns {title, hook, beats:[{text,sec}], cta, hashtags}.
    If empire_os/style_profile/style_profile.json exists (from
    competitor_intel), its winning patterns are injected into the prompt so
    we mimic what wins (structure only, never copied words).
    """
    spec = PLATFORMS.get(platform, PLATFORMS["youtube"])
    if not os.environ.get("OPENROUTER_API_KEY") and not os.environ.get("MINIMAX_API_KEY"):
        return {"error": "no LLM key (OPENROUTER_API_KEY or MINIMAX_API_KEY) for script gen"}
    profile_hint = ""
    sp = Path("/root/empire_os/empire_os/style_profile/style_profile.json")
    if sp.exists():
        try:
            p = json.loads(sp.read_text())
            bits = []
            if p.get("top_hook_types"):
                bits.append("Hook type: " + ", ".join(t for t, _ in p["top_hook_types"]))
            if p.get("top_cta_style"):
                bits.append("CTA style: " + ", ".join(t for t, _ in p["top_cta_style"]))
            if p.get("top_emotional_triggers"):
                bits.append("Triggers: " + ", ".join(t for t, _ in p["top_emotional_triggers"]))
            if p.get("top_winning_tactics"):
                bits.append("Tactics: " + ", ".join(t for t, _ in p["top_winning_tactics"][:5]))
            if bits:
                profile_hint = "\n\nMIMIC THESE WINNING PATTERNS (structure only):\n" + "\n".join("- " + b for b in bits)
        except Exception:
            pass
    prompt = f"""You are a viral short-form video scriptwriter for Empire OS,
an AI agent platform that automates lead-gen and closes deals on autopilot.
Write a {spec['dur']}-second {spec['label']} script about: {topic}.
{profile_hint}
MANDATORY: the FIRST beat must be a DIRECT ANSWER to the topic question.
No fluff, no intro. A viewer must get the answer in the first 40 words.

Return STRICT JSON only:
{{
  "title": "short punchy title (a question form works best)",
  "answer": "one sentence that directly answers the topic question",
  "hook": "first 1-2 sentence attention grabber",
  "beats": [{{"text":"caption for scene 1 (must open with the answer)","sec":5}}, ...],
  "cta": "call to action (follow / link in bio / dm us)",
  "hashtags": ["#empireos","#aiagents", ...]
}}
Make it punchy, founder-energy, psychology-driven (attention, scarcity, proof)."""
    try:
        text = _llm([{"role": "user", "content": prompt}])
        if text.startswith("__ERR__"):
            return {"error": f"LLM call failed: {text[7:]}"}
        start = text.find("{")
        if start < 0:
            return {"error": "no JSON in LLM response", "raw": text[:300]}
        # brace-balanced extraction (handles trailing commentary / nested })
        depth, end = 0, -1
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        if end < 0:
            return {"error": "unbalanced JSON in LLM response", "raw": text[:300]}
        blob = text[start:end]
        blob = blob.replace("```json", "").replace("```", "")
        import re as _re
        blob = _re.sub(r",\s*([}\]])", r"\1", blob)
        try:
            return json.loads(blob)
        except Exception as je:
            return {"error": f"JSON parse failed: {je}", "raw": blob[:300]}
    except Exception as e:
        return {"error": f"script gen failed: {e}"}


def repurpose_footage(path: str, max_clips: int = 4) -> dict:
    """Turn existing footage into clip ideas via claude-video /watch."""
    res = watch_video(path, detail="efficient", max_frames=max_clips,
                      out_dir="/tmp/social_repurp")
    if not res["ok"]:
        return {"error": res.get("error", "watch failed")}
    transcript = res["transcript"]
    # watch() returns a sentinel string when no captions/whisper available.
    # Never feed that error text to the LLM (would prompt fabrication).
    if not transcript or "No transcript available" in transcript:
        return {"clips": [], "note": "no usable transcript (captions/whisper "
                "missing on source) — enable Whisper in claude-video to "
                "repurpose footage", "transcript_len": 0}
    # Use LLM to pull clip-worthy moments from transcript
    prompt = f"""From this video transcript, extract {max_clips} short-form
clip ideas (15-30s each) for Empire OS socials. Return STRICT JSON:
{{"clips":[{{"title":"...","hook":"...","quote":"verbatim line from transcript"}}]}}
Transcript:
{transcript[:3000]}"""
    try:
        t = _llm([{"role": "user", "content": prompt}])
        if not t.startswith("__ERR__"):
            s, e = t.find("{"), t.rfind("}") + 1
            if s >= 0 and e > s:
                return json.loads(t[s:e])
    except Exception:
        pass
    return {"clips": [], "note": "transcript-only, no LLM clip extraction",
            "transcript_len": len(transcript)}


def repurpose_to_post(path: str, platform: str = "youtube", max_clips: int = 3) -> dict:
    """Full footage->post flow using claude-video /watch.

    1. watch() extracts transcript + frames
    2. LLM pulls clip-worthy moments from transcript
    3. best clip -> platform script (generate_script on the clip hook)
    4. render + queue
    Returns the queued item (or error).
    """
    ideas = repurpose_footage(path, max_clips=max_clips)
    if "error" in ideas:
        return ideas
    clips = ideas.get("clips", [])
    if not clips:
        # nothing extracted; fall back to a generic script from transcript
        return _generate_and_queue(
            ideas.get("transcript", "")[:200] or "Empire OS highlight",
            platform, source=path)
    # pick the first clip as the hero
    clip = clips[0]
    topic = f"{clip.get('title','')} — {clip.get('hook','')}"
    return _generate_and_queue(topic, platform, source=path,
                               clip_quote=clip.get("quote", ""))


def _generate_and_queue(topic: str, platform: str, source: str = "",
                        clip_quote: str = "") -> dict:
    script = generate_script(topic, platform)
    if "error" in script:
        return script
    if clip_quote:
        # prepend the verbatim quote as the hook for authenticity
        script["hook"] = clip_quote[:160]
    rendered = render_video(script, platform)
    if not rendered.get("ok"):
        return {"error": "render failed", "detail": rendered}
    item = {
        "id": f"{platform}-{int(time.time())}",
        "platform": platform,
        "topic": topic,
        "source": source,
        "clip_quote": clip_quote,
        "video": rendered["out"],
        "script": script,
        "status": "draft",
    }
    queue_item(item)
    return item



def _beats_to_cards(script: dict) -> list[str]:
    beats = script.get("beats", [])
    if not beats:
        # fallback: split hook + cta
        return [script.get("hook", ""), script.get("cta", "")]
    return [b.get("text", "") for b in beats if b.get("text")]


def clean_caption(text: str) -> str:
    """Normalize LLM script text for on-screen captions.

    - collapse whitespace, strip leading/trailing
    - curly quotes/apostrophes (drawtext-safe)
    - fix the most common LLM typos
    """
    if not text:
        return ""
    t = text.replace('"', "\u201d").replace("'", "\u2019")
    # strip em/en dashes (mandate: no em dashes; use plain hyphen or none)
    t = t.replace("\u2014", " ").replace("\u2013", " ").replace("--", " ")
    fixes = {
        " its ": " it's ",
        "dont": "don't",
        "cant": "can't",
        "wont": "won't",
        "im ": "I'm ",
        "ive": "I've",
        "youre": "you're",
        "thats": "that's",
        "didnt": "didn't",
        "isnt": "isn't",
        "wasnt": "wasn't",
        "wouldnt": "wouldn't",
        "couldnt": "couldn't",
        "shouldnt": "shouldn't",
        "doesnt": "doesn't",
    }
    low = t.lower()
    for bad, good in fixes.items():
        low = low.replace(bad, good)
    # restore original case for the first char only (cheap)
    t = low
    t = re.sub(r"\s+", " ", t).strip()
    return t


def fact_check(text: str) -> dict:
    """Guard rail: reject invented stats/numbers not in APPROVED_CLAIMS.

    Returns {ok, reason}. Blocks specific quant claims the LLM fabricates.
    Allowed claims are exact phrases we stand behind (real agent behavior).
    """
    if not text:
        return {"ok": True}
    # patterns that signal a concrete invented claim
    import re as _re
    stats = _re.findall(r"(\d+(?:\.\d+)?\s?%(?:\s+more|\s+of|\s+in)?"
                        r"|\$\d[\d,]*|"
                        r"\d+\s?(?:x|times)\s+(?:more|faster)|"
                        r"(?:studies|research|data)\s+show)",
                        text, _re.I)
    if not stats:
        return {"ok": True}
    # allowlist of approved factual phrases (expand as we verify)
    APPROVED = (
        "reply in 8 seconds",
        "24/7",
        "around the clock",
        "no sleep",
    )
    lowered = text.lower()
    for a in APPROVED:
        if a in lowered:
            return {"ok": True}
    return {"ok": False, "reason": f"unverified stat claim: {stats[0]!r}"}


def render_video(script: dict, platform: str = "youtube", out_path: str = "") -> dict:
    """Render an ANIMATED caption-card mp4 via ffmpeg (no external API).

    Motion: each beat fades in/out on a timeline, accent bar slides,
    a progress bar tracks position, background hue breathes. 720p/9:16.
    """
    if not shutil.which("ffmpeg"):
        return {"ok": False, "error": "ffmpeg missing"}
    spec = PLATFORMS.get(platform, PLATFORMS["youtube"])
    cards = [clean_caption(b) for b in _beats_to_cards(script)]
    if not cards:
        return {"ok": False, "error": "no script beats to render"}
    RENDER_DIR.mkdir(parents=True, exist_ok=True)
    out = Path(out_path) if out_path else \
        RENDER_DIR / f"{platform}_{int(time.time())}.mp4"

    scene_dur = max(3, spec["dur"] // len(cards))
    total = scene_dur * len(cards)
    W, H = spec["w"], spec["h"]
    fs = int(H * 0.05)

    # build animated drawtext chains per beat (fade+scale in, hold, fade out)
    draws = []
    for i, card in enumerate(cards):
        txt = card[:90].replace("'", "\u2019").replace('"', "\u201d")
        txt = re.sub(r"\s+", " ", txt).strip()
        # insert line break near middle for wrap
        if len(txt) > 28:
            mid = len(txt) // 2
            sp = txt.find(" ", mid)
            if sp != -1:
                txt = txt[:sp] + "\\n" + txt[sp + 1:]
        t0 = i * scene_dur
        t1 = t0 + scene_dur
        fin = t0 + 0.4          # fade-in done
        fout = t1 - 0.4         # fade-out start
        alpha = ("if(lt(t," + str(fin) + "),t/" + str(fin) +
                 ",if(lt(t," + str(fout) + "),1,(" + str(t1) + "-t)/(" +
                 str(t1) + "-" + str(fout) + ")))")
        draws.append(
            f"drawtext=fontfile={FONT}:text='{txt}':"
            f"fontcolor=white:fontsize={fs}:"
            f"x=(w-text_w)/2:y=(h-text_h)/2:"
            f"box=1:boxcolor=black@0.55:boxborderw=24:"
            f"text_align=center:"
            f"alpha='{alpha}':"
            f"enable='between(t,{t0},{t1})'")
    # prompt pop-in (hook): a pulsing keyword that bounces in at t=0
    prompt_word = clean_caption(script.get("hook", "") or cards[0])[:22]
    prompt_word = re.sub(r"\s+", " ", prompt_word).strip().replace("'", "\u2019")
    draws.append(
        f"drawtext=fontfile={FONT}:text='{prompt_word}':"
        f"fontcolor=0x00E6A0:fontsize={int(fs*0.7)}:"
        f"x=(w-text_w)/2:y=h*0.12:"
        f"text_align=center:alpha='if(lt(t,0.5),t*2,if(lt(t,1.2),1,(1-(t-1.2)/0.4)))':enable='between(t,0,1.6)'")
    # lower-third CTA callout slides in at the end
    cta_txt = "CLICK TO SUBSCRIBE"
    cta_start = total - 2
    draws.append(
        "drawtext=fontfile=" + FONT + ":text='" + cta_txt + "':"
        "fontcolor=white:fontsize=" + str(int(fs * 0.6)) + ":"
        "x='if(lt(t," + str(cta_start) + "),-w,t-" + str(cta_start) + ")*1+40':"
        "y=h*0.82:"
        "box=1:boxcolor=0x00E6A0@0.9:boxborderw=14:"
        "text_align=center:enable='gte(t," + str(cta_start) + ")'")
    # progress bar (bottom): width grows with t/total
    draws.append(
        f"drawbox=x=0:y={H-12}:w='iw*(t/{total})':h=12:"
        f"color=0x00E6A0@0.9:t=fill:enable='gte(t,0)'")
    # sliding accent bar (top): x moves left->right loop
    draws.append(
        f"drawbox=x='mod(t*120,{W})':y=0:w=160:h=8:"
        f"color=0x00E6A0@0.8:t=fill:enable='gte(t,0)'")
    vf = (f"color=c=0x0a0a0a:s={W}x{H}:d={total}," +
          ",".join(draws))
    cmd = [
        "ffmpeg", "-y", "-f", "lavfi", "-i", vf,
        "-pix_fmt", "yuv420p",
        "-r", "30", "-b:v", "2M", "-minrate", "1M", "-maxrate", "2M",
        "-bufsize", "4M",
        "-c:v", "libx264", "-preset", "medium", "-t", str(total),
        str(out),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if r.returncode != 0 or not out.exists():
        return {"ok": False, "error": "ffmpeg animated render failed",
                "stderr": (r.stderr or "")[-300:]}
    return {"ok": True, "out": str(out), "platform": platform,
            "aspect": spec["aspect"], "duration_sec": total,
            "animated": True}


def queue_item(item: dict) -> dict:
    """Write a queued post (draft-mode) to the queue dir."""
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    item.setdefault("ts", datetime.now(timezone.utc).isoformat())
    item.setdefault("status", "draft")
    fid = item.get("id") or f"{item.get('platform')}-{int(time.time())}"
    item["id"] = fid
    path = QUEUE_DIR / f"{fid}.json"
    path.write_text(json.dumps(item, indent=2))
    return {"ok": True, "queued": str(path)}


def publish(item: dict) -> dict:
    """Route to platform adapter. Posts if creds present, else draft-only."""
    platform = item.get("platform")
    secrets = _load_secrets()
    if platform == "youtube":
        from empire_os.social_youtube import publish_youtube
        return publish_youtube(item, secrets)
    # draft-mode stubs until creds land
    return {"ok": False, "status": "draft_only",
            "reason": f"no adapter/creds for {platform} yet",
            "note": "video rendered + queued; add creds to social.env to go live"}


# ---------- CLI ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--generate", help="topic to generate a script + render + queue")
    ap.add_argument("--repurpose", help="local video / URL -> clip ideas only")
    ap.add_argument("--repurpose-post", help="footage -> full post (watch->script->render->queue)")
    ap.add_argument("--platform", default="youtube",
                    choices=list(PLATFORMS))
    ap.add_argument("--render", help="render a queued item id")
    ap.add_argument("--queue", action="store_true", help="queue after render")
    ap.add_argument("--publish", help="publish a queued item id")
    ap.add_argument("--list", action="store_true", help="list queued items")
    args = ap.parse_args()

    if args.list:
        QUEUE_DIR.mkdir(exist_ok=True)
        for p in sorted(QUEUE_DIR.glob("*.json")):
            d = json.loads(p.read_text())
            print(f"{d.get('id')} | {d.get('platform')} | {d.get('status')} | "
                  f"{d.get('video') or d.get('topic','')}")
        return

    if args.repurpose:
        print(json.dumps(repurpose_footage(args.repurpose), indent=2))
        return

    if args.repurpose_post:
        res = repurpose_to_post(args.repurpose_post, args.platform)
        print("REPURPOSED:", json.dumps(res, indent=2)[:800])
        return

    if args.generate:
        script = generate_script(args.generate, args.platform)
        print("SCRIPT:", json.dumps(script, indent=2)[:800])
        if "error" in script:
            return
        rendered = render_video(script, args.platform)
        print("RENDER:", rendered)
        if rendered.get("ok"):
            item = {
                "id": f"{args.platform}-{int(time.time())}",
                "platform": args.platform,
                "topic": args.generate,
                "video": rendered["out"],
                "script": script,
                "status": "draft",
            }
            if args.queue:
                print("QUEUE:", queue_item(item))
            else:
                # still queue by default so nothing is lost
                print("QUEUE:", queue_item(item))
        return

    if args.render:
        p = QUEUE_DIR / f"{args.render}.json"
        if not p.exists():
            print("no such queued item"); return
        item = json.loads(p.read_text())
        script = item.get("script", {})
        if not script:
            print("item has no script"); return
        r = render_video(script, item.get("platform", "youtube"))
        print("RENDER:", r)
        if r.get("ok"):
            item["video"] = r["out"]
            p.write_text(json.dumps(item, indent=2))
        return

    if args.publish:
        p = QUEUE_DIR / f"{args.publish}.json"
        if not p.exists():
            print("no such queued item"); return
        item = json.loads(p.read_text())
        res = publish(item)
        print("PUBLISH:", res)
        if res.get("status") == "published":
            item["status"] = "published"
            item["published_at"] = datetime.now(timezone.utc).isoformat()
            p.write_text(json.dumps(item, indent=2))
        return

    ap.print_help()


# ── Fleet cadence entrypoint ───────────────────────────────────────────
TOPICS = [
    "AI agents that close deals while you sleep",
    "The psychology of why leads go cold in 5 minutes",
    "How to book 10 calls a day on autopilot",
    "Your sales team is now software",
    "Founder story: building Empire OS",
]


def run_cycle(platform: str = "youtube") -> dict:
    """One autonomous content cycle: pick a topic, generate, render, queue."""
    import random
    topic = random.choice(TOPICS)
    script = generate_script(topic, platform)
    if "error" in script:
        return {"ok": False, "error": script["error"]}
    rendered = render_video(script, platform)
    if not rendered.get("ok"):
        return {"ok": False, "error": "render failed", "detail": rendered}
    item = {
        "id": f"{platform}-{int(time.time())}",
        "platform": platform,
        "topic": topic,
        "video": rendered["out"],
        "script": script,
        "status": "draft",
    }
    queue_item(item)
    # attempt publish (draft-only until creds present)
    res = publish(item)
    return {"ok": True, "topic": topic, "video": rendered["out"],
            "publish": res.get("status", "draft_only")}


def daemon(platform: str = "youtube", interval: int = 3600):
    """Run content cycles on a cadence (fleet-managed)."""
    print(f"[social-syndication] online platform={platform} interval={interval}s",
          flush=True)
    while True:
        try:
            r = run_cycle(platform)
            print(json.dumps({"cycle": r}, default=str)[:300])
        except Exception as e:
            print(json.dumps({"error": str(e)[:200]}))
        time.sleep(interval)


if __name__ == "__main__":
    import sys as _sys
    if "--daemon" in _sys.argv:
        daemon()
    else:
        main()
