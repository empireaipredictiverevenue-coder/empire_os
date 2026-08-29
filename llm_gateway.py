#!/usr/bin/env python3
"""llm_gateway.py — ONE brain for all Empire OS agents.

Single entry llm(task, prompt). Provider fallback: Bai (api.b.ai,
deepseek-v4-flash, free) -> Groq (llama-3.1-8b-instant, free) -> fail.

Task routing (weights only — one brain, no per-dept scatter):
  bulk/classify (email-infer, scoring, scout) -> low max_tokens
  reasoning (sales, closer, research)         -> high max_tokens

All secrets: /root/empire_secrets/{bai,groq}_api_key. One failure point.
"""
from __future__ import annotations
import json, os, time, urllib.request, urllib.error

SECRETS = "/root/empire_secrets"

PROVIDERS = [
    {"name": "bai", "url": "https://api.b.ai/v1/chat/completions",
     "model": "deepseek-v4-flash", "key_file": "bai_api_key", "prefix": "BAI_API_KEY="},
    {"name": "groq", "url": "https://api.groq.com/openai/v1/chat/completions",
     "model": "openai/gpt-oss-20b", "key_file": "groq_api_key", "prefix": "GROQ_API_KEY="},
]

TASK_TOKENS = {"bulk": 500, "reason": 1200}
_last: dict[str, float] = {}


def log(m): print(f"[llm_gateway] {m}", flush=True)


def _key(pf: dict) -> str:
    p = os.path.join(SECRETS, pf["key_file"])
    try:
        return open(p).read().strip().replace(pf["prefix"], "")
    except Exception:
        return os.environ.get(pf["key_file"].upper(), "")


def llm(task: str, prompt: str, temperature: float = 0.1) -> str:
    """Call the first healthy provider. Returns text ('' on total failure)."""
    max_tokens = TASK_TOKENS.get(task, 300)
    for pf in PROVIDERS:
        key = _key(pf)
        if not key:
            continue
        # simple per-provider pacing (avoid 429)
        now = time.time()
        wait = 0.5 - (now - _last.get(pf["name"], 0))
        if wait > 0:
            time.sleep(wait)
        body = json.dumps({
            "model": pf["model"],
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens, "temperature": temperature,
        }).encode()
        for attempt in range(2):
            try:
                req = urllib.request.Request(pf["url"], data=body, headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {key}",
                    "User-Agent": "empire-gateway/1.0"})
                with urllib.request.urlopen(req, timeout=30) as r:
                    resp = json.loads(r.read().decode())
                _last[pf["name"]] = time.time()
                msg = resp["choices"][0]["message"]
                txt = (msg.get("content") or "") + " " + (msg.get("reasoning_content") or "")
                return txt.strip()
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    time.sleep(2 * (attempt + 1))
                    continue
                log(f"{pf['name']} HTTP {e.code}: {e}")
                break  # next provider
            except Exception as e:
                log(f"{pf['name']} err: {e}")
                break  # next provider
    return ""


def health() -> dict:
    """One 'ok' ping per provider. For scheduler/cron status checks."""
    out = {}
    for pf in PROVIDERS:
        t0 = time.time()
        r = llm("bulk", "reply with exactly: ok")
        out[pf["name"]] = {"ok": bool(r), "ms": int((time.time() - t0) * 1000),
                           "model": pf["model"]}
        break  # health = first provider only (fallback chain head)
    return out


if __name__ == "__main__":
    import sys
    t = sys.argv[1] if len(sys.argv) > 1 else "bulk"
    p = sys.argv[2] if len(sys.argv) > 2 else "reply with exactly: ok"
    print(repr(llm(t, p)))
