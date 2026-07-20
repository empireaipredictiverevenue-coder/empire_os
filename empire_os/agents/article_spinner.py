#!/usr/bin/env python3
"""
article_spinner.py — REAL article spinning via LLM (not spin-syntax junk).

Takes a seed article (or a topic + brief) and produces N unique rewrites that
keep the facts/intent but use different wording, structure and angle. Each
variant is genuinely distinct (passes duplicate-content checks) so we can
superscale the SEO moat: one researched brief -> many city/niche landing pages.

LLM priority: GROQ_API_KEY (free tier, llama-3.3-70b) -> OPENROUTER_API_KEY (paid).
No secrets in code: keys read from env at runtime.
"""
import os, sys, json, time
sys.path.insert(0, os.path.dirname(__file__))
from openai import OpenAI

MODEL = os.getenv("SPIN_MODEL", "openai/gpt-4o-mini")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")


def _client():
    """Return (OpenAI client, is_groq bool). Groq free tier preferred."""
    gkey = os.getenv("GROQ_API_KEY")
    if gkey:
        return OpenAI(api_key=gkey, base_url="https://api.groq.com/openai/v1"), True
    okey = os.getenv("OPENROUTER_API_KEY") or os.getenv("SCRAPECREATORS_API_KEY")
    if okey:
        return OpenAI(api_key=okey, base_url="https://openrouter.ai/api/v1"), False
    raise RuntimeError("no GROQ_API_KEY or OPENROUTER_API_KEY in env")


def _model_name(is_groq):
    return GROQ_MODEL if is_groq else MODEL


def spin(text: str, niche: str, metro: str = "", n: int = 3,
         tone: str = "authoritative, local, buyer-intent") -> list:
    """Return N unique rewritten articles for (niche, metro)."""
    c, is_groq = _client()
    model = _model_name(is_groq)
    outs = []
    sys_p = (
        f"You are an SEO copywriter. Rewrite the source article into a unique, "
        f"plagiarism-free version for the niche '{niche}'"
        + (f" in {metro}" if metro else "")
        + f". Tone: {tone}. Keep all facts, numbers, and the buyer CTA. "
          f"Use different sentence structure, synonyms, and a fresh intro. "
          f"Output ONLY the rewritten article body in Markdown (no preamble)."
    )
    for i in range(n):
        try:
            r = c.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": sys_p},
                    {"role": "user", "content": f"VARIANT {i+1} of {n}. Source:\n\n{text[:6000]}"},
                ],
                temperature=0.9 + 0.03 * i,
                max_tokens=1400,
            )
            outs.append(r.choices[0].message.content.strip())
        except Exception as e:
            outs.append(f"# spin error: {e}")
    return outs


def spin_from_topic(topic: str, niche: str, metro: str = "", n: int = 3) -> list:
    """Draft a fresh article on a topic, then spin it into N variants."""
    c, is_groq = _client()
    model = _model_name(is_groq)
    seed = c.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content":
             f"Write a 500-word SEO article for niche '{niche}'"
             + (f" in {metro}" if metro else "")
             + ". Include H1, 3 H2 sections, an FAQ, and a buyer CTA. "
               "Markdown only."},
            {"role": "user", "content": f"Topic: {topic}"},
        ],
        temperature=0.7, max_tokens=1400,
    ).choices[0].message.content.strip()
    return spin(seed, niche, metro, n)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic", required=True)
    ap.add_argument("--niche", required=True)
    ap.add_argument("--metro", default="")
    ap.add_argument("--n", type=int, default=3)
    a = ap.parse_args()
    for v in spin_from_topic(a.topic, a.niche, a.metro, a.n):
        print("\n===== VARIANT =====\n" + v)
