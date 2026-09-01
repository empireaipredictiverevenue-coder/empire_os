#!/usr/bin/env python3
"""content_engine.py — autonomous content generation for Empire OS.

Takes a niche/keyword and produces:
  - a long-form blog post (AEO-ready, ~800 words)
  - 3 social posts (X / LinkedIn / Reddit-style)
  - 1 nurture email
Uses OpenRouter (vault key) when available; falls back to a
credential-free template so the pipeline never stalls.

Credential-free by design: no external content API required.
"""
from __future__ import annotations
import os, sys, json, sqlite3, subprocess, time
from pathlib import Path

sys.path.insert(0, "/root/empire_os")
DB = "/root/empire_os/empire_os.db"
VAULT_KEY = "/root/empire_secrets/groq_api_key"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_KEY = "/root/empire_secrets/openrouter_api_key"
BAI_URL = "https://api.b.ai/v1/chat/completions"
BAI_KEY = "/root/empire_secrets/bai_api_key"
BAI_MODEL = "deepseek-v4-flash"  # fastest + non-reasoning + free via BAI (~6-9s, real content)
# OpenRouter GLM fallback (free tier) — secondary.
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_KEY = "/root/empire_secrets/openrouter_api_key"
OR_MODEL = "z-ai/glm-5.3-flash"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"


def _key(path: str) -> str | None:
    try:
        return open(path).read().strip()
    except Exception:
        return None


def _call(url: str, key: str, model: str, system: str, user: str,
          max_tokens: int) -> str | None:
    try:
        import urllib.request
        payload = json.dumps({
            "model": model, "max_tokens": max_tokens,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
        }).encode()
        req = urllib.request.Request(url, data=payload,
                                     headers={"Authorization": f"Bearer {key}",
                                               "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read().decode()
        # Fast-fail if the endpoint returned HTML (SPA) instead of JSON.
        if not raw.strip().startswith("{"):
            return None
        data = json.loads(raw)
        msg = data["choices"][0]["message"]
        content = msg.get("content")
        # GLM-5.3-flash is a reasoning model: final answer lives in
        # reasoning_content when content is empty.
        if not content:
            content = msg.get("reasoning_content")
        return content.strip() if content else None
    except Exception as e:
        print(f"[content_engine] LLM call failed ({url.split('/')[2]}): {e}")
        return None


def _llm(system: str, user: str, max_tokens: int = 900) -> str | None:
    # Primary: BAI GLM-5.3-flash (free, working). Fallback: template (no dead-key detours).
    bk = _key(BAI_KEY)
    if bk:
        return _call(BAI_URL, bk, BAI_MODEL, system, user, max_tokens)
    return None


def _template(niche: str, keyword: str) -> dict:
    """Credential-free fallback content."""
    title = f"How {niche.replace('_',' ').title()} Businesses Win More Leads in 2026"
    blog = f"""# {title}

The {niche.replace('_',' ')} market is more competitive than ever. Businesses that
systematize their lead generation — not just buy lists — win. Here's the playbook.

## Why {keyword} matters
Buyers research before they call. If your {niche.replace('_',' ')} business isn't
visible where intent lives, you lose the job to a competitor who is.

## The autonomous approach
Empire AI runs {niche.replace('_',' ')} lead generation on autopilot: it finds
in-market buyers, scores them with the Omega engine, and routes the hot ones to
your close. No dashboards to babysit.

## What you get
- Real {niche.replace('_',' ')} leads, not scraped junk
- Intent + fit + timing scoring on every contact
- Settlement in USDT — zero chargeback, zero processor fees

Ready to see qualified {niche.replace('_',' ')} leads land in your pipeline?
"""
    social = [
        f"Stop buying {niche.replace('_',' ')} lists. Start getting in-market buyers. Autonomous lead gen → empire-ai.co.uk",
        f"{keyword} is the #1 lever for {niche.replace('_',' ')} growth in 2026. We score every contact on intent + fit + timing.",
        f"Most {niche.replace('_',' ')} businesses lose jobs to visibility gaps. Fix it with autonomous lead intelligence.",
    ]
    email = f"Subject: Qualified {niche.replace('_',' ')} leads, on autopilot\n\nHi — we're generating in-market {niche.replace('_',' ')} buyers right now and routing the hot ones to businesses like yours. Reply 'yes' to see a sample batch."
    return {"title": title, "blog": blog, "social": social, "email": email,
            "source": "template"}


def generate(niche: str, keyword: str = "") -> dict:
    """Produce full content set for a niche."""
    kw = keyword or niche.replace("_", " ")
    if _key(BAI_KEY):
        sys_p = ("You are a B2B lead-generation content writer for Empire AI. "
                 "Write tight, no-fluff, conversion-focused copy. No em-dashes. "
                 "Plain English. Return JSON only.")
        usr = (f"Niche: {niche.replace('_',' ')}. Keyword: {kw}. "
               f"Return JSON: {{title, blog (500 words markdown), "
               f"social (3 strings), email (1 string)}}")
        out = _llm(sys_p, usr, max_tokens=1400)
        if out:
            try:
                # GLM reasoning model may wrap JSON in text or code fences.
                txt = out
                if "```" in txt:
                    txt = txt.split("```")[1].split("```")[0]
                # extract first balanced {...} block
                s = txt.find("{")
                e = txt.rfind("}")
                if s >= 0 and e > s:
                    d = json.loads(txt[s:e + 1])
                    d["source"] = "llm"
                    return d
            except Exception:
                pass
    return _template(niche, kw)


def save(niche: str, content: dict) -> str:
    """Persist content to DB + return blog path for distribution."""
    conn = sqlite3.connect(DB, timeout=30)
    conn.execute("""CREATE TABLE IF NOT EXISTS content_library (
        id INTEGER PRIMARY KEY AUTOINCREMENT, niche TEXT, title TEXT,
        blog TEXT, social TEXT, email TEXT, source TEXT, created_at TEXT)""")
    conn.execute("INSERT INTO content_library (niche, title, blog, social, email, source, created_at) "
                 "VALUES (?,?,?,?,?,?, datetime('now'))",
                 (niche, content.get("title", ""), content.get("blog", ""),
                  json.dumps(content.get("social", [])), content.get("email", ""),
                  content.get("source", "")))
    conn.commit(); conn.close()
    return f"content saved for {niche}"


if __name__ == "__main__":
    import sys
    niche = sys.argv[1] if len(sys.argv) > 1 else "hvac"
    c = generate(niche)
    print(save(niche, c))
    print("source:", c["source"], "| title:", c["title"])
