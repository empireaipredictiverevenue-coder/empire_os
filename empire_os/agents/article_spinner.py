#!/usr/bin/env python3
"""
article_spinner.py — REAL article spinning via LLM (not spin-syntax junk).

Takes a seed article (or a topic + brief) and produces N unique rewrites that
keep the facts/intent but use different wording, structure and angle. Each
variant is genuinely distinct (passes duplicate-content checks) so we can
superscale the SEO moat: one researched brief -> many city/niche landing pages.

LLM priority: GOOGLE_API_KEY (free Gemini) -> GROQ_API_KEY (free tier) ->
OPENROUTER_API_KEY (paid). No secrets in code: keys read from env at runtime.
"""
import os, sys, json, time
sys.path.insert(0, os.path.dirname(__file__))
from openai import OpenAI

MODEL = os.getenv("SPIN_MODEL", "openai/gpt-4o-mini")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")


def _client():
    """Return (OpenAI client, provider_name). Gemini free tier preferred."""
    gkey = os.getenv("GOOGLE_API_KEY")
    if gkey:
        return (OpenAI(api_key=gkey,
                        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                        timeout=60.0),
                "gemini")
    gqkey = os.getenv("GROQ_API_KEY")
    if gqkey:
        return OpenAI(api_key=gqkey, base_url="https://api.groq.com/openai/v1"), "groq"
    okey = os.getenv("OPENROUTER_API_KEY") or os.getenv("SCRAPECREATORS_API_KEY")
    if okey:
        return OpenAI(api_key=okey, base_url="https://openrouter.ai/api/v1"), "openrouter"
    raise RuntimeError(
        "no LLM key (GOOGLE_API_KEY, GROQ_API_KEY, or OPENROUTER_API_KEY) in env")


def _model_name(provider):
    if provider == "gemini":
        return GEMINI_MODEL
    if provider == "groq":
        return GROQ_MODEL
    return MODEL


def spin(text: str, niche: str, metro: str = "", n: int = 3,
         tone: str = "authoritative, local, buyer-intent") -> list:
    """Return N unique rewritten articles for (niche, metro)."""
    c, provider = _client()
    model = _model_name(provider)
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
    c, provider = _client()
    model = _model_name(provider)
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
